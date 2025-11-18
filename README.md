# 🏦 Stock Research Agent

A multi-agent stock research system powered by Claude Agent SDK that generates comprehensive Investment Memos for any public company.

## 📋 Overview

This system orchestrates specialized AI agents to research public companies across three dimensions:

1. **Company History** - Founding story, product evolution, key milestones
2. **Business Model** - Revenue streams, competitive advantages, market position
3. **Organization** - Leadership team, board composition, ownership structure

The research is synthesized into a professional Investment Memo following standard institutional investor format.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Lead Agent (Coordinator)                  │
│  - Receives ticker symbol (e.g., "NVDA")                    │
│  - Spawns 3 researchers in parallel                         │
│  - Waits for completion                                     │
│  - Spawns report writer                                     │
└─────────────────────────────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐
│ History          │ │ Business     │ │ Organization     │
│ Researcher       │ │ Researcher   │ │ Researcher       │
│                  │ │              │ │                  │
│ - WebSearch      │ │ - WebSearch  │ │ - WebSearch      │
│ - Write          │ │ - Write      │ │ - Write          │
└──────────────────┘ └──────────────┘ └──────────────────┘
          │                │                │
          └────────────────┼────────────────┘
                           ▼
                  files/research_notes/
                  - TICKER_history.md
                  - TICKER_business.md
                  - TICKER_organization.md
                           │
                           ▼
                ┌──────────────────────┐
                │ Report Writer        │
                │                      │
                │ - Read research      │
                │ - Synthesize         │
                │ - Write memo         │
                └──────────────────────┘
                           │
                           ▼
                  files/reports/
                  - TICKER_memo.md
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Anthropic API key ([get one here](https://console.anthropic.com/settings/keys))

### Installation

1. **Install uv (if not already installed):**
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd stock-research-agent
   ```

3. **Install dependencies:**
   ```bash
   uv sync
   ```

   Or with pip (slower):
   ```bash
   pip install -e .
   ```

4. **Set up environment:**
   ```bash
   cp .env.example .env
   # Edit .env and add your ANTHROPIC_API_KEY
   ```

### Usage

**Option 1: Quick Start Script (Recommended)**

```bash
./run.sh
```

This script will:
- Check if uv is installed
- Set up .env file if needed
- Install dependencies
- Run the agent

**Option 2: Manual Run**

```bash
uv run python main.py
```

**Option 3: Activate Virtual Environment**

```bash
source .venv/bin/activate  # On Unix/macOS
# OR
.venv\Scripts\activate     # On Windows
python main.py
```

Enter a ticker symbol when prompted:
```
Enter ticker symbol (e.g., NVDA, AAPL): NVDA
```

The system will:
1. Spawn 3 researchers in parallel
2. Each researcher uses WebSearch 5-10 times to gather information
3. Save research notes to `files/research_notes/`
4. Spawn report writer to synthesize findings
5. Generate Investment Memo at `files/reports/NVDA_memo.md`

## 📁 Directory Structure

```
stock-research-agent/
├── main.py                  # Entry point
├── prompts/                 # Agent system prompts
│   ├── lead_agent.txt       # Coordinator logic
│   ├── history_researcher.txt
│   ├── business_researcher.txt
│   ├── org_researcher.txt
│   └── report_writer.txt
├── utils/                   # Utility modules
│   ├── subagent_tracker.py  # Tracks tool calls with hooks
│   ├── message_handler.py   # Processes agent messages
│   └── transcript.py        # Session logging
├── tools/                   # Additional tools
│   └── sec_tools.py         # SEC filing tools (mock)
├── files/                   # Output directories
│   ├── research_notes/      # Intermediate research
│   └── reports/             # Final Investment Memos
└── logs/                    # Session transcripts
    └── session_YYYYMMDD_HHMMSS/
        ├── transcript.txt   # Human-readable log
        └── tool_calls.jsonl # Structured tool call log
```

## 📊 Investment Memo Structure

Generated memos follow this format:

```markdown
# Investment Memo: COMPANY (TICKER)

## Executive Summary
[2-3 paragraph synthesis of key points]

## Investment Thesis
[Core bull case and opportunity]

## Company Overview
- Founding & Evolution
- Business Model
- Competitive Position

## Financial Analysis
- Revenue & Growth
- Profitability & Returns
- Business Quality

## Management & Governance
- Leadership Team
- Board & Governance
- Ownership & Alignment

## Investment Framework
- Bull Case (5 points)
- Bear Case (5 points)
- Key Risks (3-5 risks)

## Conclusion
- Investment Recommendation
- Key Monitoring Points

## Sources
[All sources from research notes]
```

## 🔧 Key Features

### 1. Parallel Execution
- All 3 researchers run simultaneously for speed
- Coordination handled by lead agent

### 2. Comprehensive Tracking
- `SubagentTracker` uses hooks to monitor all tool calls
- PreToolUse hook: Captures tool invocations
- PostToolUse hook: Captures tool results
- Logs saved to `logs/session_*/tool_calls.jsonl`

### 3. Research Quality Controls
- Each researcher must use WebSearch 5-10 times
- All claims must be sourced from WebSearch results
- No reliance on LLM training data
- Specific numbers, dates, and URLs required

### 4. File System as Memory
- `files/research_notes/` stores intermediate research
- `files/reports/` stores final Investment Memos
- Markdown format for easy reading and version control

## 🎯 Agent Responsibilities
···
| Agent | Tools | Purpose |
|-------|-------|---------|
| Lead Agent | Task | Orchestrates workflow, spawns subagents |
| History Researcher | WebSearch, Write | Company founding, product evolution, milestones |
| Business Researcher | WebSearch, Write | Revenue model, moats, competitive position |
| Org Researcher | WebSearch, Write | Leadership, board, ownership, compensation |
| Report Writer | Glob, Read, Write | Synthesizes research into Investment Memo |

## 🔍 Example Output

**Input:** `NVDA`

**Research Notes Generated:**
- `files/research_notes/NVDA_history.md` (4-5 paragraphs)
- `files/research_notes/NVDA_business.md` (4-5 paragraphs)
- `files/research_notes/NVDA_organization.md` (4-5 paragraphs)

**Investment Memo Generated:**
- `files/reports/NVDA_memo.md` (1500-2500 words)
  - Executive Summary
  - Investment Thesis
  - Company Overview (history, business, competitive position)
  - Financial Analysis (revenue, profitability, quality)
  - Management & Governance (leadership, board, ownership)
  - Investment Framework (bull case, bear case, risks)
  - Conclusion & Monitoring Points
  - Complete Source List

## 📈 Future Enhancements

### SEC Filing Integration
The `tools/sec_tools.py` module is currently a mock. Future versions could:
- Integrate with SEC Edgar API
- Parse 10-K, 10-Q, and proxy statements (DEF 14A)
- Extract financial tables from XBRL data
- Analyze MD&A sections with NLP

### Additional Researchers
Consider adding:
- **Valuation Researcher**: DCF models, comps, precedent transactions
- **Technical Researcher**: Chart patterns, momentum indicators
- **Sentiment Researcher**: News sentiment, social media, analyst ratings
- **ESG Researcher**: Environmental, Social, Governance factors

### Advanced Features
- Comparative analysis (multiple companies)
- Time-series analysis (tracking company changes over time)
- Portfolio-level analysis
- Alert system for monitoring points

## 💻 Development

### Why uv?

This project uses [uv](https://docs.astral.sh/uv/) for dependency management because it's:
- **10-100x faster** than pip
- **Deterministic** - generates `uv.lock` for reproducible installs
- **Compatible** - works with standard `pyproject.toml`
- **Modern** - built in Rust with best practices

### Development Workflow

Install dev dependencies:
```bash
uv sync --all-extras
```

Run tests:
```bash
uv run pytest
```

Format code:
```bash
uv run black .
uv run ruff check .
```

Add a new dependency:
```bash
uv add <package-name>
```

## 🛠️ Customization

### Modify Agent Behavior
Edit prompt files in `prompts/` directory:
- Change research focus areas
- Adjust output formats
- Modify quality standards
- Add new instructions

### Add New Agents
1. Create new prompt file: `prompts/new_agent.txt`
2. Add AgentDefinition in `main.py`:
   ```python
   agents = {
       "new-agent": AgentDefinition(
           description="...",
           tools=["WebSearch", "Write"],
           prompt=load_prompt("new_agent.txt"),
           model="haiku"
       )
   }
   ```
3. Update lead agent to spawn new agent

### Adjust Models
Change model in AgentDefinition:
- `"haiku"` - Fast, cost-effective (default)
- `"sonnet"` - Balanced performance
- `"opus"` - Highest quality

## 📝 Notes

- **Web Search Dependency**: Researchers require WebSearch for all information
- **Token Usage**: Haiku model keeps costs low (~$0.25-0.50 per full analysis)
- **Time**: Full analysis takes 2-5 minutes depending on parallel execution
- **Accuracy**: Quality depends on WebSearch results and source availability

## ⚠️ Disclaimer

This tool is for informational and educational purposes only. The generated Investment Memos do not constitute investment advice, financial advice, trading advice, or any other sort of advice. Always conduct your own due diligence and consult with qualified financial professionals before making investment decisions.

## 📄 License

MIT License - See LICENSE file for details

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## 📧 Contact

For questions or issues, please open a GitHub issue.

---

**Built with [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk) by Anthropic**
