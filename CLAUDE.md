# CLAUDE.md - Stock Research Agent

## Project Overview

This is a **multi-agent stock research system** built with the [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk). The system uses specialized AI agents that collaborate in a layered pipeline to generate comprehensive investment memos for publicly traded companies.

**Primary Language**: Python 3.10+
**Framework**: Claude Agent SDK
**Output Language**: Chinese (中文)

## Tech Stack

- **Runtime**: Python 3.10+
- **Package Manager**: uv (Astral)
- **AI Framework**: claude-agent-sdk
- **Environment**: python-dotenv
- **Data Source**: SEC Edgar API (XBRL data)
- **Dev Tools**: pytest, black, ruff

## Quick Start

```bash
# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Add ANTHROPIC_API_KEY and SEC_CONTACT to .env

# Run full pipeline for a ticker
uv run python run_pipeline.py --ticker NVDA --model sonnet

# Run single agent
uv run python single_agent.py --agent deep-history --ticker NVDA --model sonnet
```

## Directory Structure

```
stock-research-agent/
├── main.py                 # Interactive chat entry (deprecated)
├── single_agent.py         # Single agent runner (primary entry)
├── run_pipeline.py         # Full pipeline orchestrator
├── preprocess_sec.py       # SEC file preprocessor
├── prompts/                # Agent system prompts
│   ├── deep_history_researcher.txt
│   ├── deep_business_researcher.txt
│   ├── deep_industrial_researcher.txt
│   ├── summary_agent.txt
│   ├── challenge_agent.txt
│   └── view/               # View analysis prompts (Chinese)
│       ├── 观点_7powers.md
│       ├── 观点_秩序.md
│       ├── 观点_生态猎手.md
│       └── 观点_创生公式.md
├── tools/                  # Custom tool implementations
│   ├── sec_agent_tool.py   # MCP server for SEC tools
│   ├── sec_tools.py        # SEC Edgar API client
│   └── sec_parser.py       # HTML/XBRL parsing
├── utils/                  # Utility modules
│   ├── subagent_tracker.py # Tool call tracking & logging
│   ├── message_handler.py  # Message stream processing
│   └── transcript.py       # Session transcript management
├── files/                  # Research outputs (per ticker)
│   └── {TICKER}/
│       ├── _index.json     # SEC filings index
│       ├── filings/        # Raw SEC HTML files
│       ├── raw/            # Preprocessed markdown sections
│       └── notes/          # Agent-generated research
└── logs/                   # Session logs (gitignored)
```

## Architecture: Layered Agent Pipeline

The system uses a 4-layer architecture where each layer's output feeds the next:

```
Layer 0: Data Preprocessing
    SEC filings → _index.json + raw/*.md

Layer 1: Knowledge Building (parallel)
    ├── deep-history    → notes/deep-history/evolution_analysis.md
    ├── deep-business   → notes/business-model/business_model.md
    └── deep-industrial → notes/industry/layer3_judgment.md

Layer 2: View Generation (parallel)
    ├── view-7powers    → notes/views/view_7powers.md
    ├── view-genesis    → notes/views/view_genesis.md
    ├── view-order      → notes/views/view_order.md
    └── view-ecology    → notes/views/view_ecology.md

Layer 3: Synthesis (sequential)
    └── summary         → notes/investment_memo.md
        └── challenge   → notes/investment_memo_challenge.md
```

## Agent Registry

All agents are defined in `single_agent.py` under `AGENT_PRESETS`:

| Agent | Layer | Tools | Output |
|-------|-------|-------|--------|
| `deep-history` | 1 | WebSearch, Write, Read, Glob, get_financial_snapshot, extract_sec_sections | `notes/deep-history/` |
| `deep-business` | 1 | WebSearch, Write, Read, Glob, get_financial_snapshot, extract_sec_sections | `notes/business-model/business_model.md` |
| `deep-industrial` | 1 | WebSearch, Write, Read, Glob | `notes/industry/layer[1-3]*.md` |
| `view-7powers` | 2 | Read, Write, Glob | `notes/views/view_7powers.md` |
| `view-genesis` | 2 | Read, Write | `notes/views/view_genesis.md` |
| `view-order` | 2 | Read, Write | `notes/views/view_order.md` |
| `view-ecology` | 2 | Read, Write | `notes/views/view_ecology.md` |
| `summary` | 3 | Read, Write, Glob | `notes/investment_memo.md` |
| `challenge` | 3 | Read, Write, Glob | `notes/investment_memo_challenge.md` |

## Key Files

### Entry Points
- **`run_pipeline.py`**: Main entry for full research pipeline. Runs all 9 agents in proper dependency order.
- **`single_agent.py`**: Run individual agents for testing or partial regeneration.
- **`preprocess_sec.py`**: Standalone SEC file preprocessing.

### Core Modules
- **`tools/sec_agent_tool.py`**: Exposes SEC tools as an MCP server for agent use.
- **`tools/sec_tools.py`**: SEC Edgar API client with caching.
- **`utils/subagent_tracker.py`**: Tracks all tool calls with hooks, writes to JSONL logs.

### Prompts
- All prompts support `{TICKER}` and `{DATE}` placeholders.
- View prompts are in Chinese (`prompts/view/*.md`).
- Prompts define strict output file paths and format requirements.

## Custom Tools (MCP Server)

The following tools are exposed via `tools/sec_agent_tool.py`:

| Tool | Description |
|------|-------------|
| `get_company_filings` | Fetch latest 10-K, 10-Q, DEF 14A metadata |
| `get_financial_snapshot` | Extract financial metrics from XBRL data |
| `extract_sec_sections` | Parse specific sections from SEC HTML files |

## Development Workflow

### Adding a New Agent

1. Create prompt file in `prompts/` (follow existing patterns)
2. Add entry to `AGENT_PRESETS` in `single_agent.py`
3. Define tools, output paths, and dependencies
4. If Layer 2+, update `run_pipeline.py` layer lists

### Modifying Prompts

- Prompts control agent behavior completely
- Key constraints are defined in prompts (file paths, output format, language)
- Test with single agent before full pipeline run

### Output File Conventions

- All research outputs go to `files/{TICKER}/notes/`
- Use relative paths from project root
- Chinese language for all generated content
- No timestamped filenames (except in `logs/`)

## Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...

# SEC Edgar (required for SEC tools)
SEC_CONTACT=your.email@example.com
SEC_APP_NAME=StockResearchAgent  # optional
SEC_REQUEST_DELAY=0.2            # optional, throttle requests
```

## Commands Reference

```bash
# Full pipeline
uv run python run_pipeline.py --ticker NVDA --model sonnet

# Skip layers (use existing files)
uv run python run_pipeline.py --ticker NVDA --model sonnet --skip-layer1
uv run python run_pipeline.py --ticker NVDA --model sonnet --skip-layer1 --skip-layer2

# Force re-download SEC files
uv run python run_pipeline.py --ticker NVDA --model sonnet --force-preprocess

# Single agent
uv run python single_agent.py --agent deep-history --ticker NVDA --model sonnet
uv run python single_agent.py --agent view-7powers --ticker NVDA --model haiku

# Preprocess SEC files only
uv run python preprocess_sec.py NVDA --filings 10-K,10-Q,DEF\ 14A
```

## Model Selection

| Use Case | Recommended Model |
|----------|-------------------|
| Full pipeline | `sonnet` |
| Layer 1 (deep research) | `sonnet` |
| Layer 2 (view generation) | `sonnet` or `haiku` |
| Layer 3 (summary) | `sonnet` |
| Testing/development | `haiku` |

## Cost Estimation

| Phase | Model | Time | Cost |
|-------|-------|------|------|
| Layer 1 | sonnet | 5-10 min/agent | $0.3-0.8 |
| Layer 2 | sonnet | 2-5 min/agent | $0.1-0.3 |
| Layer 3 | sonnet | 3-5 min/agent | $0.2-0.4 |
| **Full pipeline** | sonnet | **30-60 min** | **$2-5** |

## Conventions for AI Assistants

### When Working on This Codebase

1. **Language**: All research outputs and prompts use Chinese. Code and comments in English.

2. **File Paths**: Always use relative paths from project root. Never use `~` or absolute paths in prompts/outputs.

3. **Agent Design Principles**:
   - Layer 1 agents produce facts (what happened, how it works)
   - Layer 2 agents produce judgments (so what?)
   - Layer 3 synthesizes and challenges

4. **Prompt Modifications**:
   - Prompts define strict output schemas - don't change formats casually
   - Test with single agent before pipeline changes
   - Keep `{TICKER}` and `{DATE}` placeholders

5. **SEC Data Flow**:
   - Preprocessing creates `_index.json` and `raw/*.md`
   - Agents should read local files first, not call SEC API directly
   - Use `extract_sec_sections` for HTML parsing (90%+ token savings)

6. **Tool Access**:
   - Each agent has restricted tool access defined in `AGENT_PRESETS`
   - SEC tools require MCP server setup in agent options
   - View agents only need Read/Write (no WebSearch)

7. **Error Handling**:
   - Pipeline continues even if some agents fail
   - Check layer output files before running next layer
   - Session logs in `logs/` contain full transcripts

### Common Modifications

**To add a new view framework:**
1. Create `prompts/view/观点_{name}.md`
2. Add `view-{name}` to `AGENT_PRESETS`
3. Add to `LAYER2_AGENTS` in `run_pipeline.py`
4. Update `summary_agent.txt` to read new view file

**To change output format:**
1. Modify the relevant prompt template
2. Update any downstream agents that consume the output

**To add new SEC sections:**
1. Update `FILING_SECTIONS` in `preprocess_sec.py`
2. Add filename mapping in `SECTION_FILENAME_MAP`

## Testing

```bash
# Run tests
uv run pytest

# Format code
uv run black .

# Lint
uv run ruff check .
```

## Important Notes

- **Disclaimer**: This tool is for educational purposes only. Generated investment memos are not investment advice.
- **Rate Limits**: SEC Edgar requires identifying headers. Set `SEC_CONTACT` in `.env`.
- **Caching**: SEC files are cached in `files/{TICKER}/filings/`. Delete to re-download.
- **Logs**: Session logs are gitignored but useful for debugging agent behavior.
