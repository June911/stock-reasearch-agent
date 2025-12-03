"""
Stock Research Pipeline Orchestrator

按层级并行执行所有研究 agents，生成完整的投资备忘录。

Usage:
    uv run python run_pipeline.py --ticker NVDA --model sonnet
    uv run python run_pipeline.py --ticker AAPL --model haiku --skip-layer1
"""

import argparse
import asyncio
import os
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from single_agent import run_agent, ensure_directories
from preprocess_sec import preprocess_ticker

# 定义各层的 agents
LAYER1_AGENTS = ["deep-history", "deep-business", "deep-industrial"]
LAYER2_AGENTS = ["view-7powers", "view-genesis", "view-order", "view-ecology", "view-disruptor"]
LAYER3_AGENTS = ["summary", "challenge"]


def print_header(text: str):
    """打印格式化的标题"""
    width = 70
    print("\n" + "=" * width)
    print(f"  {text}")
    print("=" * width)


def print_progress(layer: str, agents: list[str], status: str = "running"):
    """打印进度信息"""
    icons = {
        "running": "🔄",
        "done": "✅",
        "error": "❌",
        "skip": "⏭️",
    }
    icon = icons.get(status, "•")
    print(f"\n{icon} {layer}: {', '.join(agents)}")


async def run_layer(
    layer_name: str,
    agents: list[str],
    ticker: str,
    model: str,
    parallel: bool = True,
) -> dict[str, bool]:
    """
    运行一层 agents。

    Returns:
        dict mapping agent name to success status
    """
    print_progress(layer_name, agents, "running")
    start_time = time.time()
    results = {}

    async def run_single(agent: str) -> tuple[str, bool]:
        try:
            print(f"  → Starting {agent}...")
            await run_agent(agent, ticker, model, instruction=None)
            print(f"  ✓ {agent} completed")
            return (agent, True)
        except Exception as e:
            print(f"  ✗ {agent} failed: {e}")
            return (agent, False)

    if parallel:
        # 并行执行
        tasks = [run_single(agent) for agent in agents]
        completed = await asyncio.gather(*tasks, return_exceptions=True)
        for item in completed:
            if isinstance(item, tuple):
                results[item[0]] = item[1]
            else:
                # Exception case
                print(f"  ✗ Unexpected error: {item}")
    else:
        # 顺序执行
        for agent in agents:
            agent_name, success = await run_single(agent)
            results[agent_name] = success

    elapsed = time.time() - start_time
    success_count = sum(1 for v in results.values() if v)
    status = "done" if success_count == len(agents) else "error"
    print(
        f"\n  {layer_name} completed: {success_count}/{len(agents)} succeeded ({elapsed:.1f}s)"
    )

    return results


def check_layer1_outputs(ticker: str) -> bool:
    """检查 Layer 1 的输出文件是否存在"""
    base_dir = Path("files") / ticker / "notes"
    required_files = [
        base_dir / "deep-history" / "evolution_analysis.md",
        base_dir / "business-model" / "business_model.md",
        base_dir / "industry" / "layer3_judgment.md",
    ]
    missing = [f for f in required_files if not f.exists()]
    if missing:
        print(f"\n⚠️  Missing Layer 1 outputs:")
        for f in missing:
            print(f"   - {f}")
        return False
    return True


def check_layer2_outputs(ticker: str) -> bool:
    """检查 Layer 2 的输出文件是否存在"""
    base_dir = Path("files") / ticker / "notes" / "views"
    required_files = [
        base_dir / "view_7powers.md",
        base_dir / "view_genesis.md",
        base_dir / "view_order.md",
        base_dir / "view_ecology.md",
    ]
    missing = [f for f in required_files if not f.exists()]
    if missing:
        print(f"\n⚠️  Missing Layer 2 outputs:")
        for f in missing:
            print(f"   - {f}")
        return False
    return True


async def run_pipeline(
    ticker: str,
    model: str,
    force_preprocess: bool = False,
    skip_layer1: bool = False,
    skip_layer2: bool = False,
    skip_layer3: bool = False,
):
    """运行完整的研究流程"""

    print_header(f"Stock Research Pipeline: {ticker}")
    print(f"Model: {model}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    pipeline_start = time.time()
    all_results = {}

    # 确保目录和预处理
    base_dir = ensure_directories(ticker, ensure_notes_dir=True)

    # Layer 0: 预处理 SEC 文件
    print_header("Layer 0: SEC 文件预处理")
    index_file = base_dir / "_index.json"
    raw_dir = base_dir / "raw"
    files_exist = index_file.exists() and raw_dir.exists() and any(raw_dir.iterdir())

    if files_exist and not force_preprocess:
        print(f"✓ 预处理文件已存在: {base_dir}")
        print(f"  (使用 --force-preprocess 强制重新处理)")
    else:
        if force_preprocess and files_exist:
            print(f"🔄 强制重新预处理 {ticker} 的 SEC 文件...")
        else:
            print(f"📥 预处理 {ticker} 的 SEC 文件...")
        preprocess_ticker(
            ticker, filing_types=["10-K", "10-Q", "DEF 14A"], verbose=True
        )

    # Layer 1: 知识构建
    if skip_layer1:
        print_header("Layer 1: 知识构建 [SKIPPED]")
        if not check_layer1_outputs(ticker):
            print("❌ Cannot skip Layer 1: required files missing")
            return
    else:
        print_header("Layer 1: 知识构建")
        results = await run_layer(
            "Layer 1", LAYER1_AGENTS, ticker, model, parallel=True
        )
        all_results.update(results)

        # 检查是否可以继续
        if not all(results.values()):
            print("\n⚠️  Some Layer 1 agents failed. Continue anyway? (y/n)")
            # 在非交互模式下继续

    # Layer 2: 观点生成
    if skip_layer2:
        print_header("Layer 2: 观点生成 [SKIPPED]")
        if not check_layer2_outputs(ticker):
            print("❌ Cannot skip Layer 2: required files missing")
            return
    else:
        print_header("Layer 2: 观点生成")

        # 检查 Layer 1 输出
        if not check_layer1_outputs(ticker):
            print("❌ Cannot run Layer 2: Layer 1 outputs missing")
            return

        results = await run_layer(
            "Layer 2", LAYER2_AGENTS, ticker, model, parallel=True
        )
        all_results.update(results)

    # Layer 3: 综合输出
    if skip_layer3:
        print_header("Layer 3: 综合输出 [SKIPPED]")
    else:
        print_header("Layer 3: 综合输出")

        # 检查 Layer 2 输出
        if not check_layer2_outputs(ticker):
            print("❌ Cannot run Layer 3: Layer 2 outputs missing")
            return

        # Layer 3 顺序执行（challenge 依赖 summary）
        results = await run_layer(
            "Layer 3", LAYER3_AGENTS, ticker, model, parallel=False
        )
        all_results.update(results)

    # 总结
    total_time = time.time() - pipeline_start
    print_header("Pipeline 完成")

    print(f"\n📊 执行统计:")
    print(f"   Ticker: {ticker}")
    print(f"   Model: {model}")
    print(f"   Total time: {total_time / 60:.1f} minutes")

    success_count = sum(1 for v in all_results.values() if v)
    total_count = len(all_results)
    print(f"   Agents: {success_count}/{total_count} succeeded")

    if all_results:
        print(f"\n📁 输出文件:")
        notes_dir = Path("files") / ticker / "notes"
        print(f"   {notes_dir / 'investment_memo.md'}")
        print(f"   {notes_dir / 'investment_memo_challenge.md'}")

    # 列出失败的 agents
    failed = [k for k, v in all_results.items() if not v]
    if failed:
        print(f"\n❌ Failed agents: {', '.join(failed)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the full stock research pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline
  uv run python run_pipeline.py --ticker NVDA --model sonnet

  # Skip Layer 1 (use existing research)
  uv run python run_pipeline.py --ticker NVDA --model sonnet --skip-layer1

  # Only run Layer 3 (regenerate memo)
  uv run python run_pipeline.py --ticker NVDA --model sonnet --skip-layer1 --skip-layer2
        """,
    )
    parser.add_argument(
        "--ticker",
        required=True,
        help="Stock ticker symbol (e.g., NVDA, AAPL)",
    )
    parser.add_argument(
        "--model",
        default="sonnet",
        choices=["haiku", "sonnet", "opus"],
        help="Claude model to use (default: sonnet)",
    )
    parser.add_argument(
        "--force-preprocess",
        action="store_true",
        help="Force re-download and preprocess SEC files",
    )
    parser.add_argument(
        "--skip-layer1",
        action="store_true",
        help="Skip Layer 1 (knowledge building) - use existing files",
    )
    parser.add_argument(
        "--skip-layer2",
        action="store_true",
        help="Skip Layer 2 (view generation) - use existing files",
    )
    parser.add_argument(
        "--skip-layer3",
        action="store_true",
        help="Skip Layer 3 (summary & challenge)",
    )
    return parser.parse_args()


async def main():
    load_dotenv()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit(
            "Error: ANTHROPIC_API_KEY not found. Set it in your environment or .env file."
        )

    args = parse_args()
    ticker = args.ticker.strip().upper()

    if not ticker:
        raise SystemExit("Ticker symbol is required.")

    await run_pipeline(
        ticker=ticker,
        model=args.model,
        force_preprocess=args.force_preprocess,
        skip_layer1=args.skip_layer1,
        skip_layer2=args.skip_layer2,
        skip_layer3=args.skip_layer3,
    )


if __name__ == "__main__":
    asyncio.run(main())
