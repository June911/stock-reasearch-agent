"""Run a single specialized Stock Research agent without the lead coordinator."""

import argparse
import asyncio
import os
from datetime import datetime
from pathlib import Path

import yfinance as yf
from dotenv import load_dotenv
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    HookMatcher,
    ResultMessage,
)

from utils.message_handler import process_assistant_message
from utils.subagent_tracker import SubagentTracker
from utils.transcript import setup_session, TranscriptWriter
from tools.sec_agent_tool import SECAgentTool, build_sec_mcp_server
from preprocess_sec import preprocess_ticker

PROMPTS_DIR = Path(__file__).parent / "prompts"

AGENT_PRESETS = {
    "history": {
        "prompt_file": "history_researcher.txt",
        "tools": [
            "WebSearch",
            "Write",
            "Read",
            "get_company_filings",
            "get_financial_snapshot",
            "extract_sec_sections",
        ],
        "task_template": (
            "Research the full company history for {ticker} and save concise notes to "
            "files/{ticker}/notes/history.md following the required format."
        ),
        "ensure_notes_dir": True,
    },
    "deep-history": {
        "prompt_file": "deep_history_researcher.txt",
        "tools": [
            "WebSearch",
            "Write",
            "Read",
            "Glob",
            "get_financial_snapshot",
            "extract_sec_sections",
        ],
        "task_template": (
            "对 {ticker} 进行深度历史研究，遵循 3 阶段方法论："
            "(1) 先读取 files/{ticker}/_index.json 和 raw/*.md 预处理文件，构建时间线；"
            "(2) 调查 2-3 个重要疑点；"
            "(3) 综合输出完整时间线和演进分析（中文）。"
            "所有输出保存到 files/{ticker}/notes/deep-history/。"
        ),
        "ensure_notes_dir": True,
        "needs_preprocessing": True,
    },
    "business": {
        "prompt_file": "business_researcher.txt",
        "tools": ["WebSearch", "Write"],
        "task_template": (
            "Research the business model, revenue drivers, and competitive position for {ticker}. "
            "Save concise notes to files/{ticker}/notes/business.md following the required format."
        ),
        "ensure_notes_dir": True,
    },
    "deep-business": {
        "prompt_file": "deep_business_researcher.txt",
        "tools": [
            "WebSearch",
            "Write",
            "Read",
            "Glob",
            "get_financial_snapshot",
            "extract_sec_sections",
        ],
        "task_template": (
            "对 {ticker} 进行商业模式深度研究："
            "(1) 先读取 files/{ticker}/_index.json 和 raw/*.md 预处理文件；"
            "(2) 按 9 个模块分析商业模式（价值主张、产品、客户、运营、盈利、生意特性、核心能力、规模化、风险）；"
            "(3) 输出到 files/{ticker}/notes/business-model/business_model.md（中文）。"
        ),
        "ensure_notes_dir": True,
        "needs_preprocessing": True,
    },
    "organization": {
        "prompt_file": "org_researcher.txt",
        "tools": ["WebSearch", "Write"],
        "task_template": (
            "Research the leadership team, board, and ownership structure for {ticker}. "
            "Save concise notes to files/{ticker}/notes/organization.md following the required format."
        ),
        "ensure_notes_dir": True,
    },
    "report": {
        "prompt_file": "report_writer.txt",
        "tools": ["Glob", "Read", "Write"],
        "task_template": (
            "Read all research notes inside files/{ticker}/notes/ and synthesize the official "
            "Investment Memo for {ticker}, saving it to files/{ticker}/report.md."
        ),
        "ensure_notes_dir": False,
    },
    "deep-industrial": {
        "prompt_file": "deep_industrial_researcher.txt",
        "tools": [
            "WebSearch",
            "Write",
            "Read",
            "Glob",
        ],
        "task_template": (
            "对 {ticker} 所在行业进行深度研究，遵循 3 层递进方法论："
            "(1) 第 1 层：赛道画像（是什么）→ 输出 layer1_landscape.md；"
            "(2) 第 2 层：运行机制（为什么）→ 输出 layer2_mechanism.md；"
            "(3) 第 3 层：投资判断（所以呢）→ 输出 layer3_judgment.md。"
            "所有文件保存到 files/{ticker}/notes/industry/（中文撰写）。"
        ),
        "ensure_notes_dir": True,
    },
    # ==================== View Agents ====================
    "view-order": {
        "prompt_file": "view/观点_秩序.md",
        "tools": ["Read", "Write"],
        "task_template": (
            "基于以下 3 个精简版文件对 {ticker} 进行秩序分析框架评估：\n"
            "1. files/{ticker}/notes/business-model/_summary.md（商业模式摘要）\n"
            "2. files/{ticker}/notes/deep-history/_summary.md（历史演进摘要）\n"
            "3. files/{ticker}/notes/industry/_summary.md（行业分析摘要）\n\n"
            "只读取这 3 个文件，不要读取其他文件。"
            "识别其创生公式、权力场强度、坍塌位置和范式脆弱性，"
            "最终给出「换还是不换」的压倒性判断。"
            "输出保存到 files/{ticker}/notes/views/view_order.md（中文）。"
        ),
        "ensure_notes_dir": True,
    },
    "view-7powers": {
        "prompt_file": "view/观点_7powers.md",
        "tools": ["Read", "Write"],
        "task_template": (
            "基于以下 2 个精简版文件对 {ticker} 进行 7 Powers 框架评估：\n"
            "1. files/{ticker}/notes/business-model/_summary.md（商业模式摘要）\n"
            "2. files/{ticker}/notes/industry/_summary.md（行业分析摘要）\n\n"
            "只读取这 2 个文件，不要读取其他文件。"
            "严格按照 prompt 中的输出模板格式输出，不要展开详细分析。"
            "输出保存到 files/{ticker}/notes/views/view_7powers.md（中文）。"
        ),
        "ensure_notes_dir": True,
    },
    "view-ecology": {
        "prompt_file": "view/观点_生态猎手.md",
        "tools": ["Read", "Write"],
        "task_template": (
            "基于以下 3 个精简版文件对 {ticker} 进行生态位猎手分析：\n"
            "1. files/{ticker}/notes/business-model/_summary.md（商业模式摘要）\n"
            "2. files/{ticker}/notes/industry/_summary.md（行业分析摘要）\n"
            "3. files/{ticker}/notes/deep-history/_summary.md（历史演进摘要）\n\n"
            "只读取这 3 个文件，不要读取其他文件。"
            "解码：位置真相、价值逻辑、死亡倒计时、进化引擎，"
            "最终回答：这是正在变强的捕食者，还是正在变肥的猎物？"
            "输出保存到 files/{ticker}/notes/views/view_ecology.md（中文）。"
        ),
        "ensure_notes_dir": True,
    },
    "view-genesis": {
        "prompt_file": "view/观点_创生公式.md",
        "tools": ["Read", "Write"],
        "task_template": (
            "基于以下 2 个精简版文件对 {ticker} 进行「看相的艺术」分析：\n"
            "1. files/{ticker}/notes/business-model/_summary.md（商业模式摘要）\n"
            "2. files/{ticker}/notes/industry/_summary.md（行业分析摘要）\n\n"
            "只读取这 2 个文件，不要读取其他文件。"
            "识别创生公式、评估权力场、定位新稀缺、判断认知折价，"
            "回答这家公司是否代表「压倒性的更高品质秩序系统」。"
            "输出保存到 files/{ticker}/notes/views/view_genesis.md（中文）。"
        ),
        "ensure_notes_dir": True,
    },
    # ==================== Summary Agent ====================
    "summary": {
        "prompt_file": "summary_agent.txt",
        "tools": ["Read", "Write"],
        "task_template": (
            "综合 {ticker} 的知识库和观点分析，生成投资备忘录。\n"
            "**重要**：请使用精简版文件以减少 token 消耗，依次读取以下 7 个文件：\n"
            "【知识库精简版】\n"
            "1. files/{ticker}/notes/business-model/_summary.md（商业模式摘要）\n"
            "2. files/{ticker}/notes/industry/_summary.md（行业分析摘要）\n"
            "3. files/{ticker}/notes/deep-history/_summary.md（历史演进摘要）\n"
            "【观点层输出】\n"
            "4. files/{ticker}/notes/views/view_7powers.md\n"
            "5. files/{ticker}/notes/views/view_order.md\n"
            "6. files/{ticker}/notes/views/view_ecology.md\n"
            "7. files/{ticker}/notes/views/view_genesis.md\n\n"
            "交叉验证各来源的结论，识别共识和分歧。\n"
            "输出控制在 150 行以内，保存到 files/{ticker}/notes/investment_memo.md（中文）。"
        ),
        "ensure_notes_dir": True,
    },
    # ==================== Challenge Agent ====================
    "challenge": {
        "prompt_file": "challenge_agent.txt",
        "tools": ["Read", "Write", "Glob"],
        "task_template": (
            "**重要**：文件路径已明确指定，请直接使用 Read 工具读取 {ticker} 的投资备忘录 files/{ticker}/notes/investment_memo.md，无需使用 Glob 搜索。\n"
            "运用圆桌思想家框架对其核心结论发起深度挑战与讨论。\n"
            "重点审视：前提假设、逻辑链条、核心矛盾、潜在盲点。\n"
            "输出保存到 files/{ticker}/notes/investment_memo_challenge.md（中文）。"
        ),
        "ensure_notes_dir": True,
    },
}


def write_session_notes(
    base_dir: Path,
    agent_key: str,
    ticker: str,
    task_prompt: str,
    model: str,
    session_dir: Path,
    transcript_file: Path,
):
    """Persist a copy of the session transcript into files/{ticker}/logs."""
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    session_name = session_dir.name
    timestamp_label = (
        session_name.split("session_", 1)[1]
        if session_name.startswith("session_")
        else datetime.now().strftime("%Y%m%d_%H%M%S")
    )

    note_path = logs_dir / f"{agent_key}_{timestamp_label}.md"

    try:
        transcript_text = transcript_file.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        transcript_text = ""

    instruction_block = (
        "\n".join(f"> {line}" for line in task_prompt.strip().splitlines())
        or "> (none)"
    )

    content = (
        f"# {ticker} {agent_key} 会话记录\n\n"
        f"- Timestamp: {timestamp_label}\n"
        f"- Model: {model}\n"
        f"- Session logs: {session_dir}\n"
        f"- Instruction:\n\n"
        f"{instruction_block}\n\n"
        "## Transcript\n\n"
        f"{transcript_text.strip()}\n"
    )

    note_path.write_text(content, encoding="utf-8")
    print(f"Session log saved to {note_path.resolve()}")


def load_prompt(filename: str) -> str:
    prompt_path = PROMPTS_DIR / filename
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read().strip()


def get_stock_data(ticker: str) -> dict:
    """获取股票实时数据（价格、市值）。

    Returns:
        dict: {"price": float|None, "market_cap": float|None, "currency": str}
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        market_cap = info.get("marketCap")
        currency = info.get("currency", "USD")
        return {
            "price": price,
            "market_cap": market_cap,
            "currency": currency,
        }
    except Exception as e:
        print(f"⚠️ 获取 {ticker} 股票数据失败: {e}")
        return {"price": None, "market_cap": None, "currency": "USD"}


def format_market_cap(value: float | None) -> str:
    """格式化市值显示。"""
    if value is None:
        return "数据待更新"
    if value >= 1e12:
        return f"{value / 1e12:.2f}T"
    elif value >= 1e9:
        return f"{value / 1e9:.2f}B"
    elif value >= 1e6:
        return f"{value / 1e6:.2f}M"
    else:
        return f"{value:,.0f}"


def get_recent_news(ticker: str, max_items: int = 5) -> str:
    """获取最新新闻作为时间锚点。

    Args:
        ticker: 股票代码
        max_items: 最多返回的新闻条数

    Returns:
        格式化的新闻列表字符串
    """
    try:
        stock = yf.Ticker(ticker)
        news = stock.news[:max_items] if stock.news else []

        if not news:
            return "暂无最新新闻"

        lines = []
        for item in news:
            title = item.get("title", "")
            # yfinance 的时间戳是 Unix timestamp
            pub_time = item.get("providerPublishTime", 0)
            if pub_time:
                pub_date = datetime.fromtimestamp(pub_time).strftime("%Y-%m-%d %H:%M")
            else:
                pub_date = "未知日期"
            publisher = item.get("publisher", "")
            lines.append(f"- [{pub_date}] {title} ({publisher})")

        return "\n".join(lines)
    except Exception as e:
        print(f"⚠️ 获取 {ticker} 新闻失败: {e}")
        return "新闻获取失败"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a single Stock Research agent. "
            "Profile agents: history, deep-history, business, deep-business, organization, deep-industrial. "
            "View agents: view-order, view-7powers, view-ecology, view-genesis. "
            "Synthesis: report."
        )
    )
    parser.add_argument(
        "--agent",
        choices=list(AGENT_PRESETS.keys()),
        required=True,
        help="Which agent to run.",
    )
    parser.add_argument(
        "--ticker",
        help="Ticker symbol, e.g., NVDA. If omitted, you will be prompted.",
    )
    parser.add_argument(
        "--model",
        default="haiku",
        help="Claude model ID to use (default: haiku).",
    )
    parser.add_argument(
        "--instruction",
        help="Override the default task instruction sent to the agent.",
    )
    return parser.parse_args()


def ensure_directories(ticker: str, ensure_notes_dir: bool) -> Path:
    base_dir = Path("files") / ticker
    notes_dir = base_dir / "notes"
    base_dir.mkdir(parents=True, exist_ok=True)
    if ensure_notes_dir:
        notes_dir.mkdir(exist_ok=True)
    return base_dir


def ensure_preprocessing(ticker: str, base_dir: Path) -> bool:
    """
    检查并执行 SEC 文件预处理。

    Returns:
        True if preprocessing was run, False if already exists
    """
    index_file = base_dir / "_index.json"
    raw_dir = base_dir / "raw"

    # 检查是否已有预处理文件
    if index_file.exists() and raw_dir.exists() and any(raw_dir.iterdir()):
        print(f"✓ 预处理文件已存在: {base_dir}")
        return False

    print(f"\n📥 自动预处理 {ticker} 的 SEC 文件...")
    preprocess_ticker(ticker, filing_types=["10-K", "10-Q", "DEF 14A"], verbose=True)
    return True


async def run_agent(agent_key: str, ticker: str, model: str, instruction: str | None):
    config = AGENT_PRESETS[agent_key]
    prompt = load_prompt(config["prompt_file"])

    # 获取实时股票数据（价格、市值）
    print(f"📈 获取 {ticker} 实时数据...")
    stock_data = get_stock_data(ticker)
    price_str = f"{stock_data['price']:.2f}" if stock_data["price"] else "数据待更新"
    market_cap_str = format_market_cap(stock_data["market_cap"])
    current_date = datetime.now().strftime("%Y年%m月%d日")

    # 获取最新新闻作为时间锚点
    print(f"📰 获取 {ticker} 最新新闻...")
    recent_news = get_recent_news(ticker)

    # 替换所有占位符
    prompt = prompt.replace("{TICKER}", ticker)
    prompt = prompt.replace("{DATE}", current_date)
    prompt = prompt.replace("{PRICE}", price_str)
    prompt = prompt.replace("{MARKET_CAP}", market_cap_str)
    prompt = prompt.replace("{RECENT_NEWS}", recent_news)

    # For deep-industrial agent, don't replace {INDUSTRY} - let agent identify it
    if agent_key != "deep-industrial":
        prompt = prompt.replace("{INDUSTRY}", ticker)
    base_dir = ensure_directories(ticker, config["ensure_notes_dir"])

    # 自动预处理 SEC 文件（如果需要）
    if config.get("needs_preprocessing"):
        ensure_preprocessing(ticker, base_dir)

    transcript_file, session_dir = setup_session()
    transcript = TranscriptWriter(transcript_file)
    tracker = SubagentTracker(transcript_writer=transcript, session_dir=session_dir)

    hooks = {
        "PreToolUse": [
            HookMatcher(matcher=None, hooks=[tracker.pre_tool_use_hook]),
        ],
        "PostToolUse": [
            HookMatcher(matcher=None, hooks=[tracker.post_tool_use_hook]),
        ],
    }

    # Initialize SEC MCP server if agent uses SEC tools
    mcp_servers: dict[str, object] = {}
    if (
        "get_company_filings" in config["tools"]
        or "get_financial_snapshot" in config["tools"]
    ):
        sec_tool = SECAgentTool()
        mcp_servers["sec"] = build_sec_mcp_server(sec_tool)

    options = ClaudeAgentOptions(
        permission_mode="bypassPermissions",
        system_prompt=prompt,
        allowed_tools=config["tools"],
        hooks=hooks,
        mcp_servers=mcp_servers,
        model=model,
    )

    task_prompt = instruction or config["task_template"].format(ticker=ticker)

    print("\n" + "=" * 70)
    print(f"Running single agent: {agent_key} for {ticker}")
    print(f"Model: {model}")
    print(f"Session logs: {session_dir}")
    print(f"Instruction: {task_prompt}")
    print("=" * 70 + "\n")

    result_msg = None
    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt=task_prompt)
            transcript.write_to_file(f"\nUser: {task_prompt}\n")
            transcript.write("\nAgent: ", end="")

            async for msg in client.receive_response():
                msg_type = type(msg).__name__
                if msg_type == "AssistantMessage":
                    process_assistant_message(msg, tracker, transcript)
                elif isinstance(msg, ResultMessage):
                    result_msg = msg
                elif msg_type == "ContentBlockDelta":
                    # Streaming text delta
                    if hasattr(msg, "delta") and hasattr(msg.delta, "text"):
                        print(msg.delta.text, end="", flush=True)
                elif msg_type not in (
                    "ContentBlockStart",
                    "ContentBlockStop",
                    "MessageStart",
                    "MessageStop",
                ):
                    # Debug: show unknown message types
                    print(f"\n[DEBUG] Unknown msg type: {msg_type}", flush=True)

            transcript.write("\n")
    finally:
        transcript.write("\n\nSession complete.\n")
        transcript.close()
        tracker.close()
        print(f"\n{'='*70}")
        print("📊 Session Summary")
        print(f"{'='*70}")
        print(f"Session logs: {session_dir}")
        print(f"  - Transcript: {transcript_file}")
        print(f"  - Tool calls: {session_dir / 'tool_calls.jsonl'}")

        # Display token usage and cost
        if result_msg:
            print(f"\n💰 Cost & Usage:")
            if result_msg.total_cost_usd is not None:
                print(f"  - Total cost: ${result_msg.total_cost_usd:.4f}")
            if result_msg.usage:
                input_tokens = result_msg.usage.get("input_tokens", 0)
                output_tokens = result_msg.usage.get("output_tokens", 0)
                print(f"  - Input tokens: {input_tokens:,}")
                print(f"  - Output tokens: {output_tokens:,}")
                print(f"  - Total tokens: {input_tokens + output_tokens:,}")
            print(f"  - Turns: {result_msg.num_turns}")
            print(f"  - Duration: {result_msg.duration_ms / 1000:.1f}s")
        print("=" * 70 + "\n")
        write_session_notes(
            base_dir=base_dir,
            agent_key=agent_key,
            ticker=ticker,
            task_prompt=task_prompt,
            model=model,
            session_dir=session_dir,
            transcript_file=transcript_file,
        )


async def main():
    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit(
            "Error: ANTHROPIC_API_KEY not found. Set it in your environment or .env file."
        )

    args = parse_args()
    ticker = (
        (args.ticker or input("Enter ticker symbol (e.g., NVDA): ")).strip().upper()
    )
    if not ticker:
        raise SystemExit("Ticker symbol is required.")

    await run_agent(
        agent_key=args.agent,
        ticker=ticker,
        model=args.model,
        instruction=args.instruction,
    )


if __name__ == "__main__":
    asyncio.run(main())
