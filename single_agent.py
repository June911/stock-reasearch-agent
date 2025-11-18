"""Run a single specialized Stock Research agent without the lead coordinator."""

import argparse
import asyncio
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    HookMatcher,
)

from utils.message_handler import process_assistant_message
from utils.subagent_tracker import SubagentTracker
from utils.transcript import setup_session, TranscriptWriter
from tools.sec_agent_tool import SECAgentTool, build_sec_mcp_server

PROMPTS_DIR = Path(__file__).parent / "prompts"

AGENT_PRESETS = {
    "history": {
        "prompt_file": "history_researcher.txt",
        "tools": [
            "WebSearch",
            "Write",
            "get_company_filings",
            "get_financial_snapshot",
        ],
        "task_template": (
            "Research the full company history for {ticker} and save concise notes to "
            "files/{ticker}/notes/history.md following the required format."
        ),
        "ensure_notes_dir": True,
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
    """Persist a copy of the session transcript into files/{ticker}/notes."""
    notes_dir = base_dir / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)

    session_name = session_dir.name
    timestamp_label = (
        session_name.split("session_", 1)[1]
        if session_name.startswith("session_")
        else datetime.now().strftime("%Y%m%d_%H%M%S")
    )

    note_path = notes_dir / f"{agent_key}_{timestamp_label}.md"

    try:
        transcript_text = transcript_file.read_text(encoding="utf-8")
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
    print(f"Notes saved to {note_path.resolve()}")


def load_prompt(filename: str) -> str:
    prompt_path = PROMPTS_DIR / filename
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read().strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a single Stock Research agent (history, business, organization, or report)."
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


async def run_agent(agent_key: str, ticker: str, model: str, instruction: str | None):
    config = AGENT_PRESETS[agent_key]
    prompt = load_prompt(config["prompt_file"]).replace("{TICKER}", ticker)
    base_dir = ensure_directories(ticker, config["ensure_notes_dir"])

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

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt=task_prompt)
            transcript.write_to_file(f"\nUser: {task_prompt}\n")
            transcript.write("\nAgent: ", end="")

            async for msg in client.receive_response():
                if type(msg).__name__ == "AssistantMessage":
                    process_assistant_message(msg, tracker, transcript)

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
