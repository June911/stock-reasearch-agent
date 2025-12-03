"""
SEC Filing Tools - Edgar Integration

This module integrates with SEC's public Edgar data endpoints to look up
company filings (10-K, 10-Q, DEF 14A) and extract key financial metrics from
XBRL company facts.

Usage requires identifying yourself with a descriptive User-Agent that
includes contact information per SEC's fair access policy. Set one of:
    SEC_USER_AGENT="StockResearchAgent/0.1 (your.email@example.com)"
or
    SEC_CONTACT="your.email@example.com"  # optional SEC_APP_NAME override
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
CACHE_DIR = Path(__file__).parent / ".sec_cache"
CACHE_TTL_SECONDS = 60 * 60 * 24  # refresh ticker map daily
DEFAULT_DELAY = float(os.getenv("SEC_REQUEST_DELAY", "0.2"))
PROJECT_ROOT = Path(__file__).resolve().parent.parent
FILES_ROOT = PROJECT_ROOT / "files"

logger = logging.getLogger(__name__)


class SECTools:
    """Helper class for interacting with SEC Edgar endpoints."""

    def __init__(self, *, user_agent: Optional[str] = None):
        self.user_agent = user_agent or self._build_user_agent()
        self._last_request_ts: float = 0.0
        self.request_delay = max(DEFAULT_DELAY, 0.1)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        FILES_ROOT.mkdir(parents=True, exist_ok=True)
        self._tickers_cache = CACHE_DIR / "company_tickers.json"
        self._ticker_to_cik: Dict[str, str] = {}
        self._filing_url_to_cik: Dict[str, str] = {}

    def get_latest_10k(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch the latest 10-K (annual report) metadata."""
        return self._get_latest_filing(ticker, ["10-K", "10-K/A", "10-K405"])

    def get_latest_10q(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch the latest 10-Q (quarterly report) metadata."""
        return self._get_latest_filing(ticker, ["10-Q", "10-Q/A"])

    def get_latest_proxy(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch the latest proxy statement (DEF 14A)."""
        return self._get_latest_filing(ticker, ["DEF 14A"])

    def get_latest_s1(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch the latest S-1/424B prospectus (IPO filing).

        424B4 is the final prospectus, S-1 is the registration statement.
        For recently IPO'd companies, this contains the most comprehensive
        business description, risk factors, and financial information.
        """
        return self._get_latest_filing(
            ticker, ["424B4", "424B3", "424B2", "424B1", "S-1", "S-1/A"]
        )

    def extract_sec_sections(
        self, file_path: str, sections: Optional[List[str]] = None, filing_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract key sections from a local SEC HTML filing file.

        This method extracts specific sections (like Item 1, Item 1A, Item 7) from
        SEC HTML files and returns clean text, significantly reducing token usage
        compared to reading the entire file.

        Args:
            file_path: Path to local SEC HTML file
            sections: List of sections to extract. Default: ["Item 1", "Item 1A", "Item 7"]
                     Can also include: "Item 2", "Item 3", "Item 8", etc.
            filing_type: Type of filing ("10-K", "10-Q", "S-1", etc.) to help disambiguate
                        sections with same name but different content. If not provided,
                        will try to infer from file path.

        Returns:
            Dictionary with extracted sections as keys and clean text as values
        """
        if sections is None:
            sections = ["Item 1", "Item 1A", "Item 7"]

        # Try to infer filing type from file path if not provided
        if filing_type is None:
            file_path_upper = str(file_path).upper()
            if "10-K" in file_path_upper or "10K" in file_path_upper:
                filing_type = "10-K"
            elif "10-Q" in file_path_upper or "10Q" in file_path_upper:
                filing_type = "10-Q"
            elif "S-1" in file_path_upper or "S1" in file_path_upper:
                filing_type = "S-1"

        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            return {"error": f"File not found: {file_path}", "sections": {}}

        try:
            html_content = file_path_obj.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            return {"error": f"Failed to read file: {str(e)}", "sections": {}}

        # Remove XBRL metadata and hidden content
        # Remove content between <ix:header> tags
        html_content = re.sub(
            r"<ix:header>.*?</ix:header>",
            "",
            html_content,
            flags=re.DOTALL | re.IGNORECASE,
        )
        # Remove hidden divs
        html_content = re.sub(
            r'<div[^>]*style\s*=\s*["\']display\s*:\s*none["\'][^>]*>.*?</div>',
            "",
            html_content,
            flags=re.DOTALL | re.IGNORECASE,
        )

        # Extract text content using HTMLParser
        class TextExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.text = []
                self.skip_tags = {"script", "style"}
                self.current_tag = None
                self.skip_content = False

            def handle_starttag(self, tag, attrs):
                tag_lower = tag.lower()
                self.current_tag = tag_lower
                # Skip XBRL and hidden content
                if tag_lower in {"script", "style"} or tag_lower.startswith("ix:"):
                    self.skip_content = True

            def handle_endtag(self, tag):
                if tag.lower().startswith("ix:") or tag.lower() in {"script", "style"}:
                    self.skip_content = False
                self.current_tag = None

            def handle_data(self, data):
                if not self.skip_content and self.current_tag not in self.skip_tags:
                    cleaned = data.strip()
                    if cleaned:
                        self.text.append(cleaned)

        parser = TextExtractor()
        parser.feed(html_content)
        full_text = " ".join(parser.text)

        # Extract sections using regex patterns
        extracted_sections = {}

        for section_name in sections:
            # Pattern to match section headers (case insensitive, flexible spacing)
            # Matches: "Item 1", "ITEM 1", "Item 1.", "ITEM 1.", "Item 1 -", etc.
            section_patterns = [
                rf'(?i)item\s+{re.escape(section_name.replace("Item ", ""))}\s*[\.\-\:]?\s*',
                rf'(?i)item\s+{re.escape(section_name.replace("Item ", ""))}\s*[\.\-\:]?\s*[^\d]',
            ]

            # Also try exact match for section names like "Item 1A"
            # Prioritize uppercase "ITEM" format (actual content) over lowercase "item" (often in TOC)
            if section_name == "Item 1A":
                section_patterns.insert(
                    0, r"ITEM\s+1A\s*[\.\-\:]?\s*(?:RISK\s+FACTORS)?"
                )
                section_patterns.insert(
                    1, r"(?i)item\s+1a\s*[\.\-\:]?\s*(?:risk\s+factors)?"
                )
            elif section_name == "Item 1":
                # Different patterns for 10-K vs 10-Q:
                # - 10-K Item 1 = Business Description
                # - 10-Q Item 1 = Financial Statements (Part I)
                if filing_type == "10-K" or filing_type == "S-1":
                    # For 10-K/S-1: prioritize "BUSINESS"
                    section_patterns.insert(
                        0, r"ITEM\s+1[\.\s]+BUSINESS"
                    )
                    section_patterns.insert(
                        1, r"(?i)item\s+1[\.\s]+business"
                    )
                    # Fallback: match Item 1 not followed by 'a', 'A', 'b', 'B', 'c', 'C' (avoid Item 1A, 1B, 1C)
                    section_patterns.insert(
                        2, r"(?i)item\s+1(?!\s*[a-cA-C])\s*[\.\-\:]?\s*(?:business)?"
                    )
                else:
                    # For 10-Q: prioritize "FINANCIAL STATEMENTS" or "UNAUDITED"
                    section_patterns.insert(
                        0, r"ITEM\s+1\s*[\.\-\:]?\s*(?:UNAUDITED|FINANCIAL\s+STATEMENTS)"
                    )
                    section_patterns.insert(
                        1, r"(?i)item\s+1\s*[\.\-\:]?\s*(?:unaudited|financial\s+statements)"
                    )
                    # Fallback
                    section_patterns.insert(
                        2, r"(?i)item\s+1(?!\s*[aA])\s*[\.\-\:]?\s*"
                    )
            elif section_name == "Item 2":
                # For 10-Q: Part I Item 2 = MD&A, Part II Item 2 = Unregistered Sales
                # Prioritize MD&A (Management's Discussion)
                section_patterns.insert(
                    0, r"ITEM\s+2\s*[\.\-\:]?\s*(?:MANAGEMENT|MD&A)"
                )
                section_patterns.insert(
                    1, r"(?i)item\s+2\s*[\.\-\:]?\s*(?:management|md&a)"
                )
            elif section_name == "Item 5":
                # Part II Item 5 = Other Information (高管交易计划等)
                section_patterns.insert(
                    0, r"ITEM\s+5\s*[\.\-\:]?\s*(?:OTHER\s+INFORMATION)"
                )
                section_patterns.insert(
                    1, r"(?i)item\s+5\s*[\.\-\:]?\s*(?:other\s+information)"
                )
            elif section_name == "Item 7":
                section_patterns.insert(
                    0, r"ITEM\s+7\s*[\.\-\:]?\s*(?:MANAGEMENT[^\']*DISCUSSION|MDA)?"
                )
                section_patterns.insert(
                    1, r"(?i)item\s+7\s*[\.\-\:]?\s*(?:management[^\']*discussion|mda)?"
                )

            section_text = None
            for pattern in section_patterns:
                # Find all matches (there may be multiple - TOC and actual content)
                matches = list(re.finditer(pattern, full_text))
                if not matches:
                    continue

                # Prefer matches that are further into the document (skip TOC at beginning)
                # Also prefer matches with actual content (longer text after match)
                best_match = None
                best_score = -1
                for match in matches:
                    # Skip matches in first 2% of document (likely TOC)
                    if match.start() < len(full_text) * 0.02:
                        continue

                    # Check content after match
                    lookahead = full_text[match.start() : match.start() + 500]
                    lookahead_upper = lookahead.upper()

                    # Special handling for Item 1 based on filing type
                    if section_name == "Item 1":
                        if filing_type == "10-K" or filing_type == "S-1":
                            # For 10-K/S-1: prioritize "BUSINESS"
                            if "BUSINESS" in lookahead_upper:
                                best_match = match
                                break  # Found the right one
                            elif "LEGAL PROCEEDINGS" in lookahead_upper:
                                # This is Part II Item 1 in 10-Q - skip it
                                continue
                        else:
                            # For 10-Q: prioritize "FINANCIAL STATEMENTS" or "UNAUDITED"
                            if (
                                "UNAUDITED" in lookahead_upper
                                or "FINANCIAL STATEMENTS" in lookahead_upper
                            ):
                                best_match = match
                                break
                            elif "LEGAL PROCEEDINGS" in lookahead_upper:
                                continue

                    # Special handling for Item 2: prioritize MD&A over Unregistered Sales
                    if section_name == "Item 2":
                        if (
                            "MANAGEMENT" in lookahead_upper
                            or "MD&A" in lookahead_upper
                            or "DISCUSSION AND ANALYSIS" in lookahead_upper
                        ):
                            # This is Part I Item 2 (MD&A) - prioritize it
                            best_match = match
                            break
                        elif "UNREGISTERED" in lookahead_upper:
                            # This is Part II Item 2 - skip it
                            continue

                    # Score: prefer matches further into document and with more content
                    score = match.start() / len(full_text)  # Position score (0-1)

                    # If it contains substantial text (not just numbers/page refs), boost score
                    if len([c for c in lookahead if c.isalpha()]) > 100:
                        score += 0.3  # Boost for content-rich matches

                    if score > best_score:
                        best_score = score
                        best_match = match

                if best_match:
                    start_pos = best_match.start()
                    # Find the next Item or end of document
                    # Look for next Item pattern (case insensitive)
                    next_item_pattern = r"(?i)ITEM\s+\d+[a-z]?\s*[\.\-\:]"
                    next_match = re.search(
                        next_item_pattern, full_text[start_pos + 200 :]
                    )

                    # If no uppercase match, try lowercase
                    if not next_match:
                        next_item_pattern = r"(?i)item\s+\d+[a-z]?\s*[\.\-\:]"
                        next_match = re.search(
                            next_item_pattern, full_text[start_pos + 200 :]
                        )

                    if next_match:
                        end_pos = start_pos + 200 + next_match.start()
                        section_text = full_text[start_pos:end_pos]
                    else:
                        # Take remaining text but limit to reasonable length
                        section_text = full_text[
                            start_pos : start_pos + 50000
                        ]  # Max 50k chars per section

                    if section_text:
                        # Clean up: remove excessive whitespace
                        section_text = re.sub(r"\s+", " ", section_text)
                        # Limit length to prevent token explosion
                        if len(section_text) > 50000:
                            section_text = section_text[:50000] + "... [truncated]"
                        break

            if section_text:
                extracted_sections[section_name] = section_text
            else:
                extracted_sections[section_name] = (
                    f"[Section '{section_name}' not found in filing]"
                )

        return {
            "file_path": str(file_path),
            "sections": extracted_sections,
            "note": "Extracted sections are cleaned of HTML tags and XBRL metadata. "
            "Use this instead of reading the full file to save tokens.",
        }

    def extract_financial_tables(self, filing_url: str) -> Dict[str, Any]:
        """
        Extract core financial metrics from company facts associated with the filing.

        Args:
            filing_url: URL returned by `get_latest_*` helpers (Archives link).

        Returns:
            Structured snapshot of income statement, balance sheet, and cash flow metrics.
        """
        cik = self._filing_url_to_cik.get(filing_url) or self._cik_from_url(filing_url)
        if not cik:
            raise ValueError(
                "Unable to infer CIK from filing URL. Pass a URL returned by SECTools."
            )

        facts = self._fetch_json(COMPANY_FACTS_URL.format(cik=cik))
        return {
            "source": COMPANY_FACTS_URL.format(cik=cik),
            "income_statement": {
                "total_revenue": self._latest_fact(facts, "Revenues"),
                "gross_profit": self._latest_fact(facts, "GrossProfit"),
                "operating_income": self._latest_fact(facts, "OperatingIncomeLoss"),
                "net_income": self._latest_fact(facts, "NetIncomeLoss"),
                "eps_basic": self._latest_fact(facts, "EarningsPerShareBasic"),
                "eps_diluted": self._latest_fact(facts, "EarningsPerShareDiluted"),
            },
            "balance_sheet": {
                "total_assets": self._latest_fact(facts, "Assets"),
                "total_liabilities": self._latest_fact(facts, "Liabilities"),
                "total_equity": self._latest_fact(facts, "StockholdersEquity"),
                "cash_and_equivalents": self._latest_fact(
                    facts, "CashAndCashEquivalentsAtCarryingValue"
                ),
            },
            "cash_flow_statement": {
                "operating_cash_flow": self._latest_fact(
                    facts, "NetCashProvidedByUsedInOperatingActivities"
                ),
                "capital_expenditures": self._latest_fact(
                    facts,
                    "PaymentsToAcquirePropertyPlantAndEquipment",
                ),
                "free_cash_flow": self._compute_free_cash_flow(facts),
            },
        }

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------

    def _build_user_agent(self) -> str:
        if user_agent := os.getenv("SEC_USER_AGENT"):
            return user_agent

        contact = os.getenv("SEC_CONTACT") or os.getenv("SEC_EMAIL")
        if not contact:
            raise RuntimeError(
                "SEC Edgar requests require identifying contact information. "
                "Set SEC_USER_AGENT or SEC_CONTACT/SEC_EMAIL."
            )

        app_name = os.getenv("SEC_APP_NAME", "StockResearchAgent")
        return f"{app_name} (mailto:{contact})"

    def _rate_limited_get(self, url: str) -> bytes:
        elapsed = time.time() - self._last_request_ts
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        request = Request(
            url, headers={"User-Agent": self.user_agent, "Accept": "application/json"}
        )
        with urlopen(request, timeout=30) as response:
            data = response.read()
        self._last_request_ts = time.time()
        return data

    def _fetch_json(self, url: str) -> Dict[str, Any]:
        try:
            raw = self._rate_limited_get(url)
            return json.loads(raw.decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(f"SEC API error for {url}: {exc}") from exc
        except URLError as exc:
            raise RuntimeError(f"Network error fetching {url}: {exc}") from exc

    def _load_ticker_map(self) -> Dict[str, str]:
        if self._ticker_to_cik:
            return self._ticker_to_cik

        data: Optional[Dict[str, Any]] = None
        if self._tickers_cache.exists():
            age = time.time() - self._tickers_cache.stat().st_mtime
            if age < CACHE_TTL_SECONDS:
                data = json.loads(self._tickers_cache.read_text(encoding="utf-8"))

        if data is None:
            data = self._fetch_json(COMPANY_TICKERS_URL)
            self._tickers_cache.write_text(json.dumps(data), encoding="utf-8")

        mapping: Dict[str, str] = {}
        for entry in data.values():
            ticker = entry.get("ticker")
            cik = entry.get("cik_str")
            if ticker and cik:
                mapping[ticker.upper()] = str(cik).zfill(10)

        if not mapping:
            raise RuntimeError(
                "Failed to build ticker → CIK map from SEC reference data."
            )

        self._ticker_to_cik = mapping
        return mapping

    def _get_cik(self, ticker: str) -> str:
        ticker = ticker.strip().upper()
        mapping = self._load_ticker_map()
        if ticker not in mapping:
            raise ValueError(f"Ticker {ticker} not found in SEC company listings.")
        return mapping[ticker]

    def _get_latest_filing(
        self, ticker: str, accepted_forms: List[str]
    ) -> Optional[Dict[str, Any]]:
        cik = self._get_cik(ticker)
        submissions = self._fetch_json(SUBMISSIONS_URL.format(cik=cik))
        recent = submissions.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accession_numbers = recent.get("accessionNumber", [])
        filing_dates = recent.get("filingDate", [])
        report_dates = recent.get("reportDate", [])
        primary_docs = recent.get("primaryDocument", [])
        for idx, form in enumerate(forms):
            if form not in accepted_forms:
                continue
            accession_number = (
                accession_numbers[idx] if idx < len(accession_numbers) else None
            )
            doc = primary_docs[idx] if idx < len(primary_docs) else None
            if not accession_number or not doc:
                continue
            accession = accession_number.replace("-", "")
            filing_url = (
                f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/{doc}"
            )
            payload = {
                "ticker": ticker.upper(),
                "cik": cik,
                "filing_type": form,
                "filing_date": filing_dates[idx] if idx < len(filing_dates) else None,
                "report_date": report_dates[idx] if idx < len(report_dates) else None,
                "accession_number": accession_number,
                "url": filing_url,
                "document_name": doc,
            }
            local_path = self._cache_filing_document(payload)
            if local_path is not None:
                payload["local_path"] = str(local_path)
            self._filing_url_to_cik[filing_url] = cik
            return payload
        return None

    def _cik_from_url(self, filing_url: str) -> Optional[str]:
        match = re.search(r"/data/(\d+)/", filing_url)
        if not match:
            return None
        return match.group(1).zfill(10)

    def _latest_fact(
        self, facts: Dict[str, Any], concept: str, unit: str = "USD"
    ) -> Optional[Dict[str, Any]]:
        series = (
            facts.get("facts", {})
            .get("us-gaap", {})
            .get(concept, {})
            .get("units", {})
            .get(unit, [])
        )
        if not series:
            return None
        latest = max(series, key=lambda item: item.get("end") or "")
        return {
            "value": latest.get("val"),
            "fy": latest.get("fy"),
            "fp": latest.get("fp"),
            "end": latest.get("end"),
        }

    def _compute_free_cash_flow(
        self, facts: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        ocf = self._latest_fact(facts, "NetCashProvidedByUsedInOperatingActivities")
        capex = self._latest_fact(facts, "PaymentsToAcquirePropertyPlantAndEquipment")
        if not ocf or not capex:
            return None
        if ocf.get("end") != capex.get("end"):
            # Use the more recent period if they differ
            reference = max([ocf, capex], key=lambda item: item.get("end") or "")
            end_date = reference.get("end")
        else:
            end_date = ocf.get("end")
        return {
            "value": (ocf["value"] or 0) - (capex["value"] or 0),
            "fy": ocf.get("fy") or capex.get("fy"),
            "fp": ocf.get("fp") or capex.get("fp"),
            "end": end_date,
        }

    def _cache_filing_document(self, payload: Dict[str, Any]) -> Optional[Path]:
        ticker = payload.get("ticker")
        accession_number = payload.get("accession_number")
        document_name = payload.get("document_name")
        url = payload.get("url")
        if not (ticker and accession_number and document_name and url):
            return None

        accession_folder = accession_number.replace("-", "")
        folder_name = self._build_filing_folder_name(payload, accession_folder)
        filing_dir = FILES_ROOT / ticker / "filings" / folder_name
        filing_dir.mkdir(parents=True, exist_ok=True)
        doc_path = filing_dir / document_name
        metadata_path = filing_dir / "metadata.json"

        if not doc_path.exists():
            try:
                document_bytes = self._rate_limited_get(url)
                doc_path.write_bytes(document_bytes)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Unable to download filing %s: %s", url, exc)
                return None

        metadata = dict(payload)
        metadata["local_path"] = str(doc_path)
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return doc_path

    def _build_filing_folder_name(
        self, payload: Dict[str, Any], accession_suffix: str
    ) -> str:
        """Generate a human-readable folder name for cached filings.

        Format: {report_or_filing_date}_{filing_type}_{accession}
        Example: 2025-07-31_10-Q_000139305225000067
        """

        def _normalize(value: str) -> str:
            sanitized = (
                value.strip()
                .upper()
                .replace(" ", "-")
                .replace("/", "-")
                .replace(":", "-")
            )
            return sanitized or "UNSPECIFIED"

        date = payload.get("report_date") or payload.get("filing_date") or "undated"
        filing_type = payload.get("filing_type") or "filing"
        safe_date = _normalize(date)
        safe_type = _normalize(filing_type)

        return f"{safe_date}_{safe_type}_{accession_suffix}"


if __name__ == "__main__":
    tools = SECTools()
    ticker = "NVDA"
    ten_k = tools.get_latest_10k(ticker)
    print(f"Latest 10-K: {ten_k}")
    ten_q = tools.get_latest_10q(ticker)
    print(f"Latest 10-Q: {ten_q}")
    proxy = tools.get_latest_proxy(ticker)
    print(f"Latest DEF 14A: {proxy}")
    if ten_k:
        tables = tools.extract_financial_tables(ten_k["url"])
        print("Financial snapshot:", json.dumps(tables, indent=2))
