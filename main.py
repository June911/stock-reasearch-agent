"""Entry point for stock research agent using AgentDefinition for subagents."""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AgentDefinition,
    HookMatcher,
)

from utils.subagent_tracker import SubagentTracker
from utils.transcript import setup_session, TranscriptWriter
from utils.message_handler import process_assistant_message
from tools.sec_agent_tool import SECAgentTool, build_sec_mcp_server

# Load environment variables
load_dotenv()

# Paths to prompt files
PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(filename: str) -> str:
    """Load a prompt from the prompts directory."""
    prompt_path = PROMPTS_DIR / filename
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read().strip()


async def chat():
    """Start interactive chat with the stock research agent."""

    # Check API key first, before creating any files
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\nError: ANTHROPIC_API_KEY not found.")
        print("Set it in a .env file or export it in your shell.")
        print("Get your key at: https://console.anthropic.com/settings/keys\n")
        return

    # Setup session directory and transcript
    transcript_file, session_dir = setup_session()

    # Create transcript writer
    transcript = TranscriptWriter(transcript_file)

    # Load prompts
    lead_agent_prompt = load_prompt("lead_agent.txt")
    history_researcher_prompt = load_prompt("history_researcher.txt")
    business_researcher_prompt = load_prompt("business_researcher.txt")
    org_researcher_prompt = load_prompt("org_researcher.txt")
    report_writer_prompt = load_prompt("report_writer.txt")

    # Initialize subagent tracker with transcript writer and session directory
    tracker = SubagentTracker(transcript_writer=transcript, session_dir=session_dir)

    # Initialize SEC tools via MCP server
    sec_tool = SECAgentTool()
    sec_mcp_server = build_sec_mcp_server(sec_tool)

    # Define specialized subagents
    agents = {
        "history-researcher": AgentDefinition(
            description=(
                "Use this agent to research company founding history, product evolution, "
                "key milestones, and historical stock performance. The history researcher uses "
                "SEC Edgar API for exact dates/financials and web search for narrative context. "
                "It can fetch 10-K/10-Q filings and extract financial metrics. Writes findings to "
                "files/{TICKER}/notes/history.md for later use by report writers."
            ),
            tools=[
                "WebSearch",
                "Write",
                "get_company_filings",
                "get_financial_snapshot",
            ],
            prompt=history_researcher_prompt,
            model="haiku",
        ),
        "business-researcher": AgentDefinition(
            description=(
                "Use this agent to research business models, revenue streams, competitive advantages, "
                "market positioning, and financial metrics. The business researcher uses web search "
                "to find revenue breakdowns, profit margins, competitive moats, TAM analysis, and "
                "competitive landscape information. Writes findings to "
                "files/{TICKER}/notes/business.md for later use by report writers."
            ),
            tools=["WebSearch", "Write"],
            prompt=business_researcher_prompt,
            model="haiku",
        ),
        "org-researcher": AgentDefinition(
            description=(
                "Use this agent to research organizational structure, leadership team, board composition, "
                "ownership structure, and executive compensation. The org researcher uses web search "
                "to find CEO background, executive team details, board members, insider ownership, "
                "institutional holders, and compensation alignment. Writes findings to "
                "files/{TICKER}/notes/organization.md for later use by report writers."
            ),
            tools=["WebSearch", "Write"],
            prompt=org_researcher_prompt,
            model="haiku",
        ),
        "report-writer": AgentDefinition(
            description=(
                "Use this agent to create a comprehensive Investment Memo document. "
                "The report-writer reads research findings from files/{TICKER}/notes/ "
                "(history, business, organization files) and synthesizes them into a structured "
                "Investment Memo saved to files/{TICKER}/report.md. "
                "Follows standard investment memo format with executive summary, investment thesis, "
                "company overview, financial analysis, management assessment, bull/bear cases, and risks. "
                "Does NOT conduct web searches - only reads existing research notes and creates memos."
            ),
            tools=["Glob", "Read", "Write"],
            prompt=report_writer_prompt,
            model="haiku",
        ),
    }

    # Set up hooks for tracking
    hooks = {
        "PreToolUse": [
            HookMatcher(
                matcher=None, hooks=[tracker.pre_tool_use_hook]  # Match all tools
            )
        ],
        "PostToolUse": [
            HookMatcher(
                matcher=None, hooks=[tracker.post_tool_use_hook]  # Match all tools
            )
        ],
    }

    options = ClaudeAgentOptions(
        permission_mode="bypassPermissions",
        system_prompt=lead_agent_prompt,
        allowed_tools=["Task"],
        agents=agents,
        hooks=hooks,
        mcp_servers={"sec": sec_mcp_server},
        model="haiku",
    )

    print("\n" + "=" * 70)
    print("🏦 STOCK RESEARCH AGENT")
    print("=" * 70)
    print("\nAnalyze any public company by providing its ticker symbol.")
    print("I'll research the company across 3 dimensions:")
    print("  1. Company History (founding, evolution, milestones)")
    print("  2. Business Model (revenue, moats, competitive position)")
    print("  3. Organization (leadership, board, ownership)")
    print("\nThen I'll synthesize findings into a comprehensive Investment Memo.")
    print(f"\nSession logs: {session_dir}")
    print(f"Research notes: files/<TICKER>/notes/")
    print(f"Investment memos: files/<TICKER>/report.md")
    print("\nType 'exit' or 'quit' to end.\n")
    print("=" * 70 + "\n")

    try:
        async with ClaudeSDKClient(options=options) as client:
            while True:
                # Get input
                try:
                    user_input = input(
                        "Enter ticker symbol (e.g., NVDA, AAPL): "
                    ).strip()
                except (EOFError, KeyboardInterrupt):
                    break

                if not user_input or user_input.lower() in ["exit", "quit", "q"]:
                    break

                # Write user input to transcript (file only, not console)
                transcript.write_to_file(f"\nUser: {user_input}\n")

                # Send to agent
                await client.query(prompt=f"Analyze {user_input}")

                transcript.write("\nAgent: ", end="")

                # Stream and process response
                async for msg in client.receive_response():
                    if type(msg).__name__ == "AssistantMessage":
                        process_assistant_message(msg, tracker, transcript)

                transcript.write("\n")
    finally:
        transcript.write("\n\nGoodbye!\n")
        transcript.close()
        tracker.close()
        print(f"\n{'='*70}")
        print("📊 Session Summary")
        print(f"{'='*70}")
        print(f"Session logs: {session_dir}")
        print(f"  - Transcript: {transcript_file}")
        print(f"  - Tool calls: {session_dir / 'tool_calls.jsonl'}")
        print(f"\nResearch notes: files/<TICKER>/notes/")
        print(f"Investment memos: files/<TICKER>/report.md")
        print(f"{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(chat())
