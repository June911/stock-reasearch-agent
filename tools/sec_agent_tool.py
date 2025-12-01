"""
SEC Edgar Tool for Claude Agent SDK

Provides a custom tool that allows agents to fetch SEC filing data directly
from the Edgar API. This tool wraps the SECTools class to make it available
as an agent tool.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from claude_agent_sdk import create_sdk_mcp_server, tool

from .sec_tools import SECTools


class SECAgentTool:
    """Agent tool wrapper for SEC Edgar functionality."""

    def __init__(self):
        """Initialize SEC tools with proper user agent."""
        self.sec = SECTools()

    def get_company_filings(self, ticker: str) -> str:
        """
        Fetch latest SEC filings for a company (10-K, 10-Q, DEF 14A).

        This tool is useful for getting:
        - IPO date and initial valuation
        - Latest annual report (10-K) details
        - Latest quarterly report (10-Q) details
        - Latest proxy statement (DEF 14A) for governance info

        Args:
            ticker: Stock ticker symbol (e.g., "NVDA", "AAPL")

        Returns:
            JSON string with filing metadata and links
        """
        try:
            ticker = ticker.strip().upper()
            result = {
                "ticker": ticker,
                "filings": {
                    "latest_10k": None,
                    "latest_10q": None,
                    "latest_proxy": None,
                },
                "note": "Use these URLs to get detailed filing information from SEC.gov",
            }

            # Get latest 10-K
            ten_k = self.sec.get_latest_10k(ticker)
            if ten_k:
                result["filings"]["latest_10k"] = {
                    "filing_date": ten_k.get("filing_date"),
                    "report_date": ten_k.get("report_date"),
                    "url": ten_k.get("url"),
                    "description": "Annual report with full financial statements and business description",
                }

            # Get latest 10-Q
            ten_q = self.sec.get_latest_10q(ticker)
            if ten_q:
                result["filings"]["latest_10q"] = {
                    "filing_date": ten_q.get("filing_date"),
                    "report_date": ten_q.get("report_date"),
                    "url": ten_q.get("url"),
                    "description": "Quarterly report with interim financial statements",
                }

            # Get latest proxy statement
            proxy = self.sec.get_latest_proxy(ticker)
            if proxy:
                result["filings"]["latest_proxy"] = {
                    "filing_date": proxy.get("filing_date"),
                    "url": proxy.get("url"),
                    "description": "Proxy statement with executive compensation and governance details",
                }

            return json.dumps(result, indent=2)

        except Exception as e:
            return json.dumps(
                {
                    "error": str(e),
                    "ticker": ticker,
                    "note": "SEC data not available. Make sure SEC_CONTACT is set in .env",
                },
                indent=2,
            )

    def get_financial_snapshot(self, ticker: str) -> str:
        """
        Fetch latest financial metrics from SEC XBRL company facts.

        This tool extracts structured financial data including:
        - Revenue, gross profit, operating income, net income
        - Total assets, liabilities, equity
        - Operating cash flow, capital expenditures, free cash flow
        - EPS (basic and diluted)

        Args:
            ticker: Stock ticker symbol (e.g., "NVDA", "AAPL")

        Returns:
            JSON string with financial metrics
        """
        try:
            ticker = ticker.strip().upper()

            # First get latest 10-K to get the filing URL
            ten_k = self.sec.get_latest_10k(ticker)
            if not ten_k:
                return json.dumps(
                    {"error": "No 10-K filing found", "ticker": ticker}, indent=2
                )

            # Extract financial tables using the filing URL
            financials = self.sec.extract_financial_tables(ten_k["url"])

            result = {
                "ticker": ticker,
                "source": financials.get("source"),
                "income_statement": self._format_financial_item(
                    financials["income_statement"]
                ),
                "balance_sheet": self._format_financial_item(
                    financials["balance_sheet"]
                ),
                "cash_flow": self._format_financial_item(
                    financials["cash_flow_statement"]
                ),
                "note": "All values in USD unless otherwise specified",
            }

            return json.dumps(result, indent=2)

        except Exception as e:
            return json.dumps(
                {
                    "error": str(e),
                    "ticker": ticker,
                    "note": "Financial data extraction failed. Company may not report in XBRL format or SEC_CONTACT may not be set.",
                },
                indent=2,
            )

    def extract_sec_sections(
        self, file_path: str, sections: Optional[List[str]] = None
    ) -> str:
        """
        Extract key sections from a local SEC HTML filing file.

        This tool extracts specific sections (like Item 1, Item 1A, Item 7) from
        SEC HTML files and returns clean text, significantly reducing token usage
        compared to reading the entire file.

        Args:
            file_path: Path to local SEC HTML file (e.g., files/CRCL/filings/.../file.htm)
            sections: Optional list of sections to extract. Default: ["Item 1", "Item 1A", "Item 7"]

        Returns:
            JSON string with extracted sections
        """
        try:
            result = self.sec.extract_sec_sections(file_path, sections)
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {
                    "error": str(e),
                    "file_path": file_path,
                    "note": "Failed to extract sections. Make sure the file path is correct.",
                },
                indent=2,
            )

    def _format_financial_item(self, items: Dict[str, Any]) -> Dict[str, Any]:
        """Format financial items for better readability."""
        formatted = {}
        for key, value in items.items():
            if value is None:
                formatted[key] = "N/A"
            elif isinstance(value, dict):
                # Extract value and metadata
                val = value.get("value")
                if val is not None:
                    formatted[key] = {
                        "value": val,
                        "fiscal_year": value.get("fy"),
                        "fiscal_period": value.get("fp"),
                        "end_date": value.get("end"),
                    }
                else:
                    formatted[key] = "N/A"
            else:
                formatted[key] = value
        return formatted


# Tool definitions for Agent SDK
SEC_TOOL_DEFINITIONS = {
    "get_company_filings": {
        "description": (
            "Fetch SEC Edgar filings for a company including latest 10-K (annual report), "
            "10-Q (quarterly report), and DEF 14A (proxy statement). "
            "Useful for getting IPO dates, filing URLs, and governance information."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g., NVDA, AAPL)",
                }
            },
            "required": ["ticker"],
        },
    },
    "get_financial_snapshot": {
        "description": (
            "Extract latest financial metrics from SEC XBRL data including revenue, "
            "profit margins, assets, liabilities, cash flows, and EPS. "
            "Returns structured financial data from the most recent annual report."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g., NVDA, AAPL)",
                }
            },
            "required": ["ticker"],
        },
    },
    "extract_sec_sections": {
        "description": (
            "Extract key sections (Item 1, Item 1A, Item 7) from a local SEC HTML filing file. "
            "This tool removes HTML tags and XBRL metadata, returning only clean text. "
            "Use this instead of reading the entire file to save significant tokens (90%+ reduction). "
            "File path should be relative to project root, e.g., 'files/CRCL/filings/.../file.htm'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to local SEC HTML file (relative to project root)",
                },
                "sections": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of sections to extract. Default: ['Item 1', 'Item 1A', 'Item 7']",
                },
            },
            "required": ["file_path"],
        },
    },
}


def create_sec_tool_handler():
    """
    Create a handler function for SEC tools that can be registered with Agent SDK.

    Returns:
        Handler function that routes SEC tool calls
    """
    sec_tool = SECAgentTool()

    def handler(tool_name: str, tool_input: Dict[str, Any]) -> str:
        """Route SEC tool calls to appropriate methods."""
        if tool_name == "get_company_filings":
            return sec_tool.get_company_filings(tool_input["ticker"])
        elif tool_name == "get_financial_snapshot":
            return sec_tool.get_financial_snapshot(tool_input["ticker"])
        elif tool_name == "extract_sec_sections":
            sections = tool_input.get("sections")
            return sec_tool.extract_sec_sections(tool_input["file_path"], sections)
        else:
            return json.dumps({"error": f"Unknown SEC tool: {tool_name}"})

    return handler


def build_sec_mcp_server(sec_tool: SECAgentTool | None = None):
    """
    Create an in-process MCP server exposing SEC tools to Claude agents.

    Args:
        sec_tool: Optional shared SECAgentTool instance. If not provided, a new
            instance will be created.

    Returns:
        McpSdkServerConfig object that can be passed to ClaudeAgentOptions.mcp_servers.
    """

    sec_tool = sec_tool or SECAgentTool()

    @tool(
        name="get_company_filings",
        description=SEC_TOOL_DEFINITIONS["get_company_filings"]["description"],
        input_schema=SEC_TOOL_DEFINITIONS["get_company_filings"]["parameters"],
    )
    async def get_company_filings_tool(args: Dict[str, Any]) -> Dict[str, Any]:
        result = sec_tool.get_company_filings(args["ticker"])
        return {"content": [{"type": "text", "text": result}]}

    @tool(
        name="get_financial_snapshot",
        description=SEC_TOOL_DEFINITIONS["get_financial_snapshot"]["description"],
        input_schema=SEC_TOOL_DEFINITIONS["get_financial_snapshot"]["parameters"],
    )
    async def get_financial_snapshot_tool(args: Dict[str, Any]) -> Dict[str, Any]:
        result = sec_tool.get_financial_snapshot(args["ticker"])
        return {"content": [{"type": "text", "text": result}]}

    @tool(
        name="extract_sec_sections",
        description=SEC_TOOL_DEFINITIONS["extract_sec_sections"]["description"],
        input_schema=SEC_TOOL_DEFINITIONS["extract_sec_sections"]["parameters"],
    )
    async def extract_sec_sections_tool(args: Dict[str, Any]) -> Dict[str, Any]:
        sections = args.get("sections")
        result = sec_tool.extract_sec_sections(args["file_path"], sections)
        return {"content": [{"type": "text", "text": result}]}

    return create_sdk_mcp_server(
        name="sec-tools",
        version="1.0.0",
        tools=[
            get_company_filings_tool,
            get_financial_snapshot_tool,
            extract_sec_sections_tool,
        ],
    )


if __name__ == "__main__":
    # Test the SEC tool
    print("Testing SEC Agent Tool...")
    tool = SECAgentTool()

    ticker = "NVDA"
    print(f"\n1. Getting filings for {ticker}:")
    print(tool.get_company_filings(ticker))

    print(f"\n2. Getting financial snapshot for {ticker}:")
    print(tool.get_financial_snapshot(ticker))
