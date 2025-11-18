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
                 files/TICKER/
                 - notes/history.md
                 - notes/business.md
                 - notes/organization.md
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
                 files/TICKER/
                 - report.md
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
3. Save research notes to `files/NVDA/notes/`
4. Spawn report writer to synthesize findings
5. Generate Investment Memo at `files/NVDA/report.md`

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
│   └── sec_tools.py         # SEC Edgar integration helpers
├── files/                   # Output directories (one subfolder per ticker)
│   └── <TICKER>/            # e.g., files/NVDA/
│       ├── report.md        # Final Investment Memo
│       └── notes/           # Intermediate research
│           ├── history.md
│           ├── business.md
│           └── organization.md
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
- `files/<TICKER>/notes/` stores intermediate research
- `files/<TICKER>/report.md` stores final Investment Memos
- Markdown format for easy reading and version control

## 🎯 Agent Responsibilities
···
| Agent | Tools | Purpose |
|-------|-------|---------|
| Lead Agent | Task | Orchestrates workflow, spawns subagents |
| History Researcher | WebSearch, Write, SEC Tools | Company founding, product evolution, milestones, IPO details (uses SEC API for exact dates/financials) |
| Business Researcher | WebSearch, Write | Revenue model, moats, competitive position |
| Org Researcher | WebSearch, Write | Leadership, board, ownership, compensation |
| Report Writer | Glob, Read, Write | Synthesizes research into Investment Memo |

**Note:** History Researcher now integrates with SEC Edgar API to fetch exact IPO dates, filing URLs, and financial metrics directly from 10-K/10-Q filings, complementing WebSearch results with authoritative data.

## 🔍 Example Output

**Input:** `NVDA`

**Research Notes Generated:**
- `files/NVDA/notes/history.md` (4-5 paragraphs)
- `files/NVDA/notes/business.md` (4-5 paragraphs)
- `files/NVDA/notes/organization.md` (4-5 paragraphs)

**Investment Memo Generated:**
- `files/NVDA/report.md` (1500-2500 words)
  - Executive Summary
  - Investment Thesis
  - Company Overview (history, business, competitive position)
  - Financial Analysis (revenue, profitability, quality)
  - Management & Governance (leadership, board, ownership)
  - Investment Framework (bull case, bear case, risks)
  - Conclusion & Monitoring Points
  - Complete Source List

## 🧾 SEC Edgar Integration

The `tools/sec_tools.py` module now calls the official Edgar data endpoints to
retrieve the latest 10-K, 10-Q, and DEF 14A filings plus core XBRL metrics.

### Required Environment

Per SEC fair access policy you must identify yourself with a descriptive
User-Agent and contact email:

```bash
export SEC_USER_AGENT="StockResearchAgent/0.1 (research@example.com)"
# or set a contact and optional app name:
export SEC_CONTACT="research@example.com"
export SEC_APP_NAME="StockResearchAgent"
```

Optional knobs:

- `SEC_REQUEST_DELAY` (default `0.2` seconds) throttles requests.

### Example Usage

```python
from tools.sec_tools import SECTools

sec = SECTools()
ten_k = sec.get_latest_10k("NVDA")
financials = sec.extract_financial_tables(ten_k["url"])
print(ten_k["url"])
print(financials["income_statement"]["total_revenue"])
```

The helper automatically:

- Maps tickers → CIKs via SEC reference data (cached for 24h under `tools/.sec_cache`)
- Calls `data.sec.gov/submissions` for filing metadata
- Calls `data.sec.gov/api/xbrl/companyfacts` for normalized metrics
- Saves each downloaded filing to `files/<TICKER>/filings/<ACCESSION>/` with metadata for reuse
- Returns structured snapshots ready for downstream analysis

### Integrated into History Researcher

**The History Researcher agent now automatically uses SEC tools!**

When researching company history, it:
1. **First** calls `get_company_filings(ticker)` to get exact filing dates and URLs
2. **Optionally** calls `get_financial_snapshot(ticker)` for revenue/profitability history
3. **Then** uses WebSearch for narrative context and founder stories
4. **Combines** SEC hard data (dates, numbers) with WebSearch narratives

This ensures:
- **Exact IPO dates** from actual S-1 filings
- **Precise financial milestones** from 10-K/10-Q reports
- **Official business descriptions** from SEC filings
- **Authoritative sources** cited in research notes

No additional configuration needed - just set `SEC_CONTACT` in your `.env` file!

## 📈 Future Enhancements

### SEC Filing Enhancements
Future iterations can build on the live Edgar integration to:
- Parse MD&A sections with NLP
- Extract detailed tables (segment revenue, compensation, proposals)
- Support additional forms (8-K, S-1) and historical ranges

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

### Testing Individual Agents

The `single_agent.py` script allows you to run individual researchers without the lead coordinator for testing:

```bash
# Test history researcher
python single_agent.py --agent history --ticker NVDA

# Test business researcher
python single_agent.py --agent business --ticker AAPL

# Test organization researcher
python single_agent.py --agent organization --ticker TSLA

# Test report writer (requires research notes already exist)
python single_agent.py --agent report --ticker NVDA

# Use different model
python single_agent.py --agent history --ticker NVDA --model sonnet

# Custom instruction
python single_agent.py --agent history --ticker NVDA --instruction "Focus only on the founding story"
```

This is useful for:
- Debugging individual agent prompts
- Testing changes without running the full pipeline
- Generating partial research for specific companies
- Experimenting with different models

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
