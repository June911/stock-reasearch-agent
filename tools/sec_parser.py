#!/usr/bin/env python3
"""
SEC Filing Parser - 将 SEC HTML 文件预处理为结构化 Markdown

功能：
1. 从 filings/ 目录读取原始 HTML
2. 按 Item 切分章节，输出到 raw/ 目录
3. 生成 _index.json 元数据索引

使用方法：
    python -m tools.sec_parser --ticker CRCL
    python -m tools.sec_parser --ticker CRCL --filing 2025-09-30_10-Q
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# 加载 .env 文件
from dotenv import load_dotenv

load_dotenv()

from .sec_tools import SECTools

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FILES_ROOT = PROJECT_ROOT / "files"

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


class SECParser:
    """SEC 财报解析器，将 HTML 转为结构化 Markdown 文件。"""

    # Item 映射：Item 名称 -> 输出文件名
    ITEM_FILE_MAP = {
        "Item 1": "item1.md",  # 10-Q: Financial Statements / 10-K: Business
        "Item 1A": "item1a_risks.md",
        "Item 1B": "item1b_comments.md",
        "Item 2": "item2.md",  # 10-Q: MD&A / 10-K: Properties
        "Item 3": "item3.md",
        "Item 4": "item4.md",
        "Item 5": "item5_other_info.md",  # Part II: Other Info (高管交易计划等)
        "Item 6": "item6.md",
        "Item 7": "item7_mda.md",
        "Item 7A": "item7a_market_risk.md",
        "Item 8": "item8_financials.md",
    }

    # S-1/424B4 招股书章节映射
    S1_SECTION_MAP = {
        "Prospectus Summary": "prospectus_summary.md",
        "Risk Factors": "risk_factors.md",
        "Use of Proceeds": "use_of_proceeds.md",
        "Business": "business.md",
        "Management's Discussion": "mda.md",
        "Management": "management.md",
        "Executive Compensation": "executive_compensation.md",
        "Certain Relationships": "related_party.md",
        "Principal Stockholders": "principal_stockholders.md",
        "Description of Capital Stock": "capital_stock.md",
    }

    # 10-K 和 10-Q 的默认提取 Items
    DEFAULT_ITEMS_10K = ["Item 1", "Item 1A", "Item 7", "Item 7A"]
    DEFAULT_ITEMS_10Q = ["Item 1", "Item 1A", "Item 2", "Item 3", "Item 5"]  # Item 5: 高管交易计划

    # S-1/424B4 默认提取章节
    DEFAULT_SECTIONS_S1 = [
        "Prospectus Summary",
        "Risk Factors",
        "Business",
        "Management's Discussion",
        "Management",
        "Executive Compensation",
        "Principal Stockholders",
    ]

    def __init__(self, ticker: str):
        self.ticker = ticker.upper()
        self.ticker_dir = FILES_ROOT / self.ticker
        self.filings_dir = self.ticker_dir / "filings"
        self.raw_dir = self.ticker_dir / "raw"
        self.index_path = self.ticker_dir / "_index.json"
        self.sec_tools = SECTools()

    def parse_all(self) -> Dict[str, Any]:
        """解析 ticker 下所有 filings。"""
        if not self.filings_dir.exists():
            logger.error(f"Filings 目录不存在: {self.filings_dir}")
            return {"error": "filings directory not found"}

        results = []
        for filing_dir in sorted(self.filings_dir.iterdir()):
            if filing_dir.is_dir():
                result = self.parse_filing(filing_dir.name)
                if "error" not in result:
                    results.append(result)

        # 更新索引
        self._update_index(results)

        return {
            "ticker": self.ticker,
            "parsed_count": len(results),
            "filings": results,
        }

    def parse_filing(self, filing_folder: str) -> Dict[str, Any]:
        """
        解析单个 filing 目录。

        Args:
            filing_folder: filing 目录名，如 "2025-09-30_10-Q_000187604225000047"

        Returns:
            解析结果字典
        """
        filing_path = self.filings_dir / filing_folder
        if not filing_path.exists():
            return {"error": f"Filing 目录不存在: {filing_path}"}

        # 解析目录名获取元数据
        meta = self._parse_folder_name(filing_folder)
        if not meta:
            return {"error": f"无法解析目录名: {filing_folder}"}

        # 查找 HTML 文件
        html_file = self._find_html_file(filing_path)
        if not html_file:
            return {"error": f"未找到 HTML 文件: {filing_path}"}

        # 读取 metadata.json 补充信息
        metadata_file = filing_path / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file, "r", encoding="utf-8") as f:
                file_meta = json.load(f)
                meta["filing_date"] = file_meta.get("filing_date")
                meta["accession_number"] = file_meta.get("accession_number")

        # 确定要提取的 Items/Sections
        filing_type = meta["filing_type"]
        is_s1 = filing_type in ["S-1", "S-1/A", "424B4", "424B1"]

        if is_s1:
            sections_to_extract = self.DEFAULT_SECTIONS_S1
            section_map = self.S1_SECTION_MAP
        elif filing_type in ["10-K", "10-K/A"]:
            sections_to_extract = self.DEFAULT_ITEMS_10K
            section_map = self.ITEM_FILE_MAP
        else:
            sections_to_extract = self.DEFAULT_ITEMS_10Q
            section_map = self.ITEM_FILE_MAP

        # 提取 sections
        logger.info(f"📄 解析: {filing_folder}")

        if is_s1:
            # S-1 使用专门的提取方法
            extract_result = self._extract_s1_sections(str(html_file), sections_to_extract)
        else:
            extract_result = self.sec_tools.extract_sec_sections(
                str(html_file), sections=sections_to_extract
            )

        if "error" in extract_result:
            return {"error": extract_result["error"]}

        # 创建输出目录
        raw_subdir = f"{meta['report_date']}_{meta['filing_type'].replace('/', '-')}"
        output_dir = self.raw_dir / raw_subdir
        output_dir.mkdir(parents=True, exist_ok=True)

        # 写入 Markdown 文件
        sections_written = []
        for section_name, content in extract_result.get("sections", {}).items():
            if content.startswith("[Section"):
                # Section 未找到，跳过
                continue

            safe_name = section_name.lower().replace(" ", "_").replace("'", "")
            filename = section_map.get(section_name, f"{safe_name}.md")
            output_file = output_dir / filename

            # 添加元数据头
            header = f"# {section_name}\n\n"
            header += f"> Source: {html_file.name}\n"
            header += f"> Report Date: {meta['report_date']}\n"
            header += f"> Filing Type: {meta['filing_type']}\n\n"
            header += "---\n\n"

            file_size = len(header) + len(content)
            output_file.write_text(header + content, encoding="utf-8")
            sections_written.append({
                "name": filename.replace(".md", ""),
                "chars": file_size,
                "tokens_est": file_size // 4,  # 粗略估算：1 token ≈ 4 chars
            })
            logger.info(f"  ✅ {section_name} -> {filename} ({len(content):,} chars)")

        # 计算统计信息
        total_raw_chars = sum(s["chars"] for s in sections_written)
        total_raw_tokens = sum(s["tokens_est"] for s in sections_written)
        source_file_size = html_file.stat().st_size
        source_tokens_est = source_file_size // 4

        result = {
            "report_date": meta["report_date"],
            "filing_type": meta["filing_type"],
            "filing_date": meta.get("filing_date"),
            "fiscal_quarter": self._infer_quarter(meta["report_date"]),
            "fiscal_year": meta["report_date"][:4],
            "source_file": f"filings/{filing_folder}/{html_file.name}",
            "raw_dir": f"raw/{raw_subdir}/",
            "sections": [s["name"] for s in sections_written],
            "processed_at": datetime.now().isoformat(),
            # Token 统计
            "stats": {
                "source_size_bytes": source_file_size,
                "source_tokens_est": source_tokens_est,
                "extracted_chars": total_raw_chars,
                "extracted_tokens_est": total_raw_tokens,
                "token_savings_pct": round((1 - total_raw_tokens / source_tokens_est) * 100, 1) if source_tokens_est > 0 else 0,
            },
            "sections_detail": sections_written,
        }

        return result

    def _parse_folder_name(self, folder_name: str) -> Optional[Dict[str, str]]:
        """
        解析 filing 目录名。

        格式: {report_date}_{filing_type}_{accession}
        示例: 2025-09-30_10-Q_000187604225000047
        """
        parts = folder_name.split("_")
        if len(parts) < 2:
            return None

        report_date = parts[0]
        filing_type = parts[1]

        # 验证日期格式
        try:
            datetime.strptime(report_date, "%Y-%m-%d")
        except ValueError:
            return None

        return {
            "report_date": report_date,
            "filing_type": filing_type,
        }

    def _find_html_file(self, filing_path: Path) -> Optional[Path]:
        """查找 filing 目录下的主 HTML 文件。"""
        # 优先查找 .htm 文件
        htm_files = list(filing_path.glob("*.htm"))
        if htm_files:
            # 排除 metadata，选择最大的文件（通常是主文档）
            htm_files = [f for f in htm_files if "metadata" not in f.name.lower()]
            if htm_files:
                return max(htm_files, key=lambda f: f.stat().st_size)

        # 其次查找 .html 文件
        html_files = list(filing_path.glob("*.html"))
        if html_files:
            html_files = [f for f in html_files if "metadata" not in f.name.lower()]
            if html_files:
                return max(html_files, key=lambda f: f.stat().st_size)

        return None

    def _extract_s1_sections(
        self, file_path: str, sections: List[str]
    ) -> Dict[str, Any]:
        """
        从 S-1/424B4 招股书中提取章节。

        S-1 使用章节标题而非 Item 编号，需要特殊处理。
        """
        from html.parser import HTMLParser

        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            return {"error": f"File not found: {file_path}", "sections": {}}

        try:
            html_content = file_path_obj.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            return {"error": f"Failed to read file: {str(e)}", "sections": {}}

        # 清理 HTML
        html_content = re.sub(
            r"<ix:header>.*?</ix:header>", "", html_content, flags=re.DOTALL | re.IGNORECASE
        )

        # 提取文本
        class TextExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.text = []
                self.skip = False

            def handle_starttag(self, tag, attrs):
                if tag.lower() in {"script", "style"} or tag.lower().startswith("ix:"):
                    self.skip = True

            def handle_endtag(self, tag):
                if tag.lower() in {"script", "style"} or tag.lower().startswith("ix:"):
                    self.skip = False

            def handle_data(self, data):
                if not self.skip:
                    cleaned = data.strip()
                    if cleaned:
                        self.text.append(cleaned)

        parser = TextExtractor()
        parser.feed(html_content)
        full_text = " ".join(parser.text)

        # S-1 章节按顺序排列，用于确定边界
        # 格式: (章节名, 起始模式, 结束模式)
        s1_section_order = [
            ("Prospectus Summary", r"Prospectus\s+summary\s+This\s+summary\s+highlights", r"RISK\s+FACTORS"),
            ("Risk Factors", r"RISK\s+FACTORS\s+(?:Investing|You\s+should|An\s+investment)", r"(?:CAUTIONARY|FORWARD.LOOKING|USE\s+OF\s+PROCEEDS)"),
            ("Use of Proceeds", r"USE\s+OF\s+PROCEEDS", r"DIVIDEND\s+POLICY"),
            ("Business", r"BUSINESS\s+(?:Overview|Our\s+Mission|Founded|Circle)", r"MANAGEMENT(?!\s*[''`]S)"),
            ("Management's Discussion", r"MANAGEMENT.S\s+DISCUSSION\s+AND\s+ANALYSIS", r"(?:BUSINESS\s+Overview|BUSINESS\s+Our|BUSINESS\s+Founded)"),
            ("Management", r"MANAGEMENT\s+(?:The\s+following|Executive\s+Officers|Our\s+executive)", r"EXECUTIVE\s+COMPENSATION"),
            ("Executive Compensation", r"EXECUTIVE\s+COMPENSATION", r"CERTAIN\s+RELATIONSHIPS"),
            ("Certain Relationships", r"CERTAIN\s+RELATIONSHIPS", r"(?:PRINCIPAL|SECURITY\s+OWNERSHIP|BENEFICIAL)"),
            ("Principal Stockholders", r"(?:PRINCIPAL\s+STOCKHOLDERS|SECURITY\s+OWNERSHIP|BENEFICIAL\s+OWNERSHIP)", r"DESCRIPTION\s+OF"),
            ("Description of Capital Stock", r"DESCRIPTION\s+OF\s+(?:CAPITAL|OUR\s+CAPITAL|SECURITIES)", r"(?:SHARES\s+ELIGIBLE|MATERIAL\s+U\.?S)"),
        ]

        extracted_sections = {}

        for section_name, start_pattern, end_pattern in s1_section_order:
            if section_name not in sections:
                continue

            # 查找起始位置
            matches = list(re.finditer(start_pattern, full_text, re.IGNORECASE))
            if not matches:
                extracted_sections[section_name] = f"[Section '{section_name}' not found in filing]"
                continue

            # 跳过目录（前2%），找实际内容
            best_match = None
            for match in matches:
                pos_pct = match.start() / len(full_text)
                if pos_pct > 0.02:
                    # 检查是否有实质内容
                    lookahead = full_text[match.start():match.start() + 500]
                    alpha_count = len([c for c in lookahead if c.isalpha()])
                    if alpha_count > 150:
                        best_match = match
                        break

            if not best_match:
                for match in matches:
                    if match.start() / len(full_text) > 0.02:
                        best_match = match
                        break
                if not best_match and matches:
                    best_match = matches[-1]

            if not best_match:
                extracted_sections[section_name] = f"[Section '{section_name}' not found in filing]"
                continue

            start_pos = best_match.start()

            # 用结束模式找边界
            end_match = re.search(end_pattern, full_text[start_pos + 500:], re.IGNORECASE)
            if end_match:
                end_pos = start_pos + 500 + end_match.start()
            else:
                # 没找到结束模式，取固定长度
                end_pos = min(start_pos + 80000, len(full_text))

            section_text = full_text[start_pos:end_pos]

            # 清理
            section_text = re.sub(r"\s+", " ", section_text).strip()

            # 限制长度
            if len(section_text) > 80000:
                section_text = section_text[:80000] + "... [truncated]"

            extracted_sections[section_name] = section_text

        return {
            "file_path": str(file_path),
            "sections": extracted_sections,
            "note": "Extracted from S-1/424B4 prospectus",
        }

    def _infer_quarter(self, report_date: str) -> str:
        """从报告日期推断季度。"""
        month = int(report_date[5:7])
        if month <= 3:
            return "Q1"
        elif month <= 6:
            return "Q2"
        elif month <= 9:
            return "Q3"
        else:
            return "Q4"

    def _update_index(self, filings: List[Dict[str, Any]]) -> None:
        """更新 _index.json 文件。"""
        # 读取现有索引
        index = {"ticker": self.ticker, "company_name": "", "updated_at": "", "filings": []}

        if self.index_path.exists():
            with open(self.index_path, "r", encoding="utf-8") as f:
                index = json.load(f)

        # 更新 filings 列表（按 report_date 去重）
        existing_dates = {f["report_date"] + "_" + f["filing_type"]: i for i, f in enumerate(index.get("filings", []))}

        for filing in filings:
            key = filing["report_date"] + "_" + filing["filing_type"]
            if key in existing_dates:
                # 更新现有记录
                index["filings"][existing_dates[key]] = filing
            else:
                # 添加新记录
                index["filings"].append(filing)

        # 按日期排序（最新的在前）
        index["filings"].sort(key=lambda x: x["report_date"], reverse=True)
        index["updated_at"] = datetime.now().isoformat()

        # 写入文件
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)

        logger.info(f"📋 索引已更新: {self.index_path}")

    def get_index(self) -> Dict[str, Any]:
        """读取当前索引。"""
        if not self.index_path.exists():
            return {"ticker": self.ticker, "filings": []}

        with open(self.index_path, "r", encoding="utf-8") as f:
            return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="SEC Filing Parser")
    parser.add_argument("--ticker", "-t", required=True, help="股票代码，如 CRCL")
    parser.add_argument("--filing", "-f", help="指定 filing 目录名（可选，默认处理全部）")
    parser.add_argument("--list", "-l", action="store_true", help="列出可用的 filings")

    args = parser.parse_args()

    sec_parser = SECParser(args.ticker)

    if args.list:
        # 列出可用的 filings
        if not sec_parser.filings_dir.exists():
            print(f"❌ 目录不存在: {sec_parser.filings_dir}")
            return

        print(f"\n📁 {args.ticker} 可用 Filings:\n")
        for filing_dir in sorted(sec_parser.filings_dir.iterdir()):
            if filing_dir.is_dir():
                print(f"  - {filing_dir.name}")
        print()
        return

    if args.filing:
        # 处理指定 filing
        result = sec_parser.parse_filing(args.filing)
    else:
        # 处理全部 filings
        result = sec_parser.parse_all()

    print(f"\n📊 处理结果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
