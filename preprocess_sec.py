"""
SEC 文件预处理脚本

功能：
1. 下载公司的 SEC filings (10-K, 10-Q, DEF 14A, S-1, 8-K)
2. 提取关键章节为 markdown 文件
3. 生成 _index.json 索引文件

使用方法：
    python preprocess_sec.py TICKER [--filings 10-K,10-Q,DEF-14A]

输出结构：
    files/{TICKER}/
    ├── _index.json              # 索引文件
    ├── filings/                  # 原始 HTML 文件
    │   └── {date}_{type}_{accession}/
    │       ├── *.htm
    │       └── metadata.json
    └── raw/                      # 预处理后的 markdown
        └── {date}_{type}/
            ├── item1_business.md
            ├── item1a_risk_factors.md
            ├── item7_mda.md
            └── financial_snapshot.json
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
load_dotenv()

from tools.sec_tools import SECTools

PROJECT_ROOT = Path(__file__).resolve().parent
FILES_ROOT = PROJECT_ROOT / "files"

# 每种 filing 类型要提取的章节
FILING_SECTIONS = {
    "10-K": ["Item 1", "Item 1A", "Item 7", "Item 7A", "Item 8"],
    "10-Q": ["Item 1", "Item 2", "Item 1A"],
    "DEF 14A": [],  # Proxy 需要特殊处理
    "S-1": ["Item 1", "Item 1A", "Item 7"],
    "8-K": [],  # 8-K 结构不固定
}

# 章节名称映射（用于文件名）
SECTION_FILENAME_MAP = {
    "Item 1": "item1_business",
    "Item 1A": "item1a_risk_factors",
    "Item 2": "item2_mda",
    "Item 7": "item7_mda",
    "Item 7A": "item7a_market_risk",
    "Item 8": "item8_financials",
}


def preprocess_ticker(
    ticker: str,
    filing_types: list[str] | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """
    预处理指定 ticker 的 SEC 文件。

    Args:
        ticker: 股票代码
        filing_types: 要处理的文件类型列表，默认 ["10-K", "10-Q", "DEF 14A"]
        verbose: 是否打印进度信息

    Returns:
        索引字典，包含所有处理过的文件信息
    """
    if filing_types is None:
        filing_types = ["10-K", "10-Q", "DEF 14A"]

    ticker = ticker.upper()
    tools = SECTools()

    ticker_dir = FILES_ROOT / ticker
    raw_dir = ticker_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    index = {
        "ticker": ticker,
        "preprocessed_at": datetime.now().isoformat(),
        "filings": [],
    }

    if verbose:
        print(f"\n{'='*60}")
        print(f"预处理 {ticker} 的 SEC 文件")
        print(f"{'='*60}")

    # 获取各类型最新 filing
    for filing_type in filing_types:
        if verbose:
            print(f"\n📄 获取 {filing_type}...")

        try:
            if filing_type in ["10-K", "10-K/A"]:
                filing = tools.get_latest_10k(ticker)
            elif filing_type in ["10-Q", "10-Q/A"]:
                filing = tools.get_latest_10q(ticker)
            elif filing_type == "DEF 14A":
                filing = tools.get_latest_proxy(ticker)
            else:
                if verbose:
                    print(f"  ⚠️ 不支持的类型: {filing_type}")
                continue

            if not filing:
                if verbose:
                    print(f"  ⚠️ 未找到 {filing_type}")
                continue

            if verbose:
                print(f"  ✓ 找到: {filing.get('filing_date')} ({filing.get('accession_number')})")

            # 创建输出目录
            report_date = filing.get("report_date") or filing.get("filing_date") or "unknown"
            output_dir = raw_dir / f"{report_date}_{filing_type.replace('/', '-')}"
            output_dir.mkdir(parents=True, exist_ok=True)

            filing_info = {
                "type": filing_type,
                "filing_date": filing.get("filing_date"),
                "report_date": filing.get("report_date"),
                "accession_number": filing.get("accession_number"),
                "local_path": filing.get("local_path"),
                "extracted_sections": [],
            }

            # 提取章节
            local_path = filing.get("local_path")
            if local_path and Path(local_path).exists():
                sections_to_extract = FILING_SECTIONS.get(filing_type, [])

                if sections_to_extract:
                    if verbose:
                        print(f"  📑 提取章节: {', '.join(sections_to_extract)}")

                    result = tools.extract_sec_sections(local_path, sections_to_extract)
                    sections = result.get("sections", {})

                    for section_name, content in sections.items():
                        if "[Section" in content and "not found" in content:
                            continue

                        # 生成文件名
                        filename = SECTION_FILENAME_MAP.get(section_name, section_name.lower().replace(" ", "_"))
                        md_path = output_dir / f"{filename}.md"

                        # 写入 markdown
                        md_content = f"# {section_name}\n\n"
                        md_content += f"**Source**: {filing_type} ({report_date})\n"
                        md_content += f"**Accession**: {filing.get('accession_number')}\n\n"
                        md_content += "---\n\n"
                        md_content += content

                        md_path.write_text(md_content, encoding="utf-8")
                        filing_info["extracted_sections"].append({
                            "section": section_name,
                            "file": str(md_path.relative_to(ticker_dir)),
                            "size_bytes": len(content),
                        })

                        if verbose:
                            print(f"    ✓ {section_name} → {md_path.name} ({len(content):,} bytes)")

            # 获取财务快照
            if filing_type in ["10-K", "10-Q"]:
                if verbose:
                    print(f"  📊 获取财务数据...")
                try:
                    snapshot = tools.extract_financial_tables(filing["url"])
                    snapshot_path = output_dir / "financial_snapshot.json"
                    snapshot_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
                    filing_info["financial_snapshot"] = str(snapshot_path.relative_to(ticker_dir))
                    if verbose:
                        print(f"    ✓ 财务快照 → financial_snapshot.json")
                except Exception as e:
                    if verbose:
                        print(f"    ⚠️ 财务数据获取失败: {e}")

            index["filings"].append(filing_info)

        except Exception as e:
            if verbose:
                print(f"  ❌ 错误: {e}")
            continue

    # 保存索引
    index_path = ticker_dir / "_index.json"
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")

    if verbose:
        print(f"\n{'='*60}")
        print(f"✅ 预处理完成")
        print(f"   索引文件: {index_path}")
        print(f"   处理文件数: {len(index['filings'])}")
        total_sections = sum(len(f.get('extracted_sections', [])) for f in index['filings'])
        print(f"   提取章节数: {total_sections}")
        print(f"{'='*60}\n")

    return index


def main():
    parser = argparse.ArgumentParser(
        description="预处理 SEC 文件，提取关键章节为 markdown"
    )
    parser.add_argument(
        "ticker",
        help="股票代码，如 NVDA, VEEV",
    )
    parser.add_argument(
        "--filings",
        default="10-K,10-Q,DEF 14A",
        help="要处理的文件类型，逗号分隔 (默认: 10-K,10-Q,DEF 14A)",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="安静模式，不打印进度",
    )

    args = parser.parse_args()

    filing_types = [f.strip() for f in args.filings.split(",")]

    try:
        index = preprocess_ticker(
            ticker=args.ticker,
            filing_types=filing_types,
            verbose=not args.quiet,
        )

        if args.quiet:
            print(json.dumps(index, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
