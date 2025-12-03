# Stock Research Agent

基于 Claude Agent SDK 的多层股票研究系统，通过专业化 AI agents 协作生成深度投资备忘录。

## 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                     Layer 0: 数据预处理                          │
│                 SEC filings → 结构化 raw/*.md                    │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                     Layer 1: 知识构建                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ deep-history │  │ deep-business│  │deep-industrial│          │
│  │   演进分析    │  │   商业模式   │  │   行业判断    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                     Layer 2: 观点生成                            │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐       │
│  │view-7powers│ │view-order │ │view-ecology│ │view-genesis│      │
│  │   护城河   │ │    秩序   │ │   生态位   │ │  创生公式  │       │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘       │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                     Layer 3: 综合输出                            │
│            ┌──────────┐           ┌───────────┐                 │
│            │ summary  │     →     │ challenge │                 │
│            │ 投资备忘录│           │  挑战分析  │                 │
│            └──────────┘           └───────────┘                 │
└─────────────────────────────────────────────────────────────────┘
```

## 快速开始

### 环境配置

```bash
# 安装依赖
uv sync

# 配置环境变量
cp .env.example .env
# 编辑 .env 添加 ANTHROPIC_API_KEY 和 SEC_CONTACT
```

### 运行完整流程（推荐）

```bash
# 一键运行全部 9 个 agents
uv run python run_pipeline.py --ticker NVDA --model sonnet

# 跳过 Layer 1（使用已有的知识文件）
uv run python run_pipeline.py --ticker NVDA --model sonnet --skip-layer1

# 只重新生成备忘录
uv run python run_pipeline.py --ticker NVDA --model sonnet --skip-layer1 --skip-layer2
```

### 运行单个 Agent

```bash
# 运行单个 agent
uv run python single_agent.py --agent <agent-name> --ticker <TICKER> --model <model>

# 示例：运行深度商业模式分析
uv run python single_agent.py --agent deep-business --ticker NVDA --model sonnet
```

## Agent 清单

### Layer 1: 知识构建 Agents

| Agent | 说明 | 输入 | 输出 |
|-------|------|------|------|
| `deep-history` | 深度历史研究 | SEC raw + WebSearch | `notes/deep-history/evolution_analysis.md` |
| `deep-business` | 商业模式分析 | SEC raw + WebSearch | `notes/business-model/business_model.md` |
| `deep-industrial` | 行业深度研究 | WebSearch | `notes/industry/layer3_judgment.md` |

### Layer 2: 观点生成 Agents

| Agent | 框架 | 输入文件 | 输出 |
|-------|------|----------|------|
| `view-7powers` | Hamilton Helmer 7 Powers | business_model + layer3 | `notes/views/view_7powers.md` |
| `view-genesis` | 创生公式 | business_model + layer3 | `notes/views/view_genesis.md` |
| `view-order` | 秩序分析 | business_model + evolution + layer3 | `notes/views/view_order.md` |
| `view-ecology` | 生态位猎手 | business_model + evolution + layer3 | `notes/views/view_ecology.md` |

### Layer 3: 综合输出 Agents

| Agent | 说明 | 输入 | 输出 |
|-------|------|------|------|
| `summary` | 投资备忘录生成 | 全部 7 个知识/观点文件 | `notes/investment_memo.md` |
| `challenge` | 圆桌思想家挑战 | investment_memo | `notes/investment_memo_challenge.md` |

## 数据流

### 依赖关系

```
SEC filings (10-K, 10-Q, DEF 14A, S-1)
        │
        ↓ 自动预处理
    _index.json + raw/*.md
        │
        ├──────────────────────────────────┐
        ↓                                  ↓
   deep-history                      deep-business
   → evolution_analysis.md           → business_model.md
        │                                  │
        │      deep-industrial             │
        │      → layer3_judgment.md        │
        │              │                   │
        ↓              ↓                   ↓
   ┌─────────────────────────────────────────────┐
   │              View Agents                     │
   │  view-7powers  ← business_model + layer3    │
   │  view-genesis  ← business_model + layer3    │
   │  view-order    ← all three                  │
   │  view-ecology  ← all three                  │
   └─────────────────────────────────────────────┘
                       │
                       ↓
                   summary
               → investment_memo.md
                       │
                       ↓
                   challenge
            → investment_memo_challenge.md
```

## 目录结构

```
stock-research-agent/
├── run_pipeline.py          # 完整流程运行入口（推荐）
├── single_agent.py          # 单 agent 运行入口
├── preprocess_sec.py        # SEC 文件预处理
├── prompts/                 # Agent 系统提示词
│   ├── deep_history_researcher.txt
│   ├── deep_business_researcher.txt
│   ├── deep_industrial_researcher.txt
│   ├── summary_agent.txt
│   ├── challenge_agent.txt
│   └── view/                # 观点框架提示词
│       ├── 观点_7powers.md
│       ├── 观点_秩序.md
│       ├── 观点_生态猎手.md
│       └── 观点_创生公式.md
├── tools/                   # 工具模块
│   └── sec_agent_tool.py    # SEC Edgar API 集成
├── utils/                   # 工具函数
│   ├── subagent_tracker.py
│   ├── message_handler.py
│   └── transcript.py
├── files/                   # 研究输出（按 ticker 组织）
│   └── <TICKER>/
│       ├── _index.json      # SEC 文件索引
│       ├── raw/             # 预处理后的 SEC 内容
│       ├── filings/         # 原始 SEC 文件
│       ├── notes/           # 研究笔记
│       │   ├── deep-history/
│       │   ├── business-model/
│       │   ├── industry/
│       │   ├── views/
│       │   ├── investment_memo.md
│       │   └── investment_memo_challenge.md
│       └── logs/            # 会话记录
└── logs/                    # 全局会话日志
```

## 设计理念

### 1. 知识与观点分离

- **Layer 1** 只产出事实（发生了什么、如何运作）
- **Layer 2** 基于事实生成判断（所以呢）

### 2. 多视角交叉验证

- 4 个 View agents 从不同投资框架分析同一家公司
- Summary 识别多源共识（≥3 源一致）和分歧点

### 3. 批判性闭环

- Challenge agent 对最终结论发起系统性挑战
- 暴露隐性假设、逻辑漏洞和认知盲点

## SEC Edgar 集成

系统自动从 SEC Edgar 获取并预处理公司文件：

- **10-K**: 年度报告（业务描述、风险因素、财务数据）
- **10-Q**: 季度报告（最新财务状况）
- **DEF 14A**: 代理声明（高管薪酬、股权结构）
- **S-1 / S-1/A**: IPO 注册声明（适用于新上市公司，作为 10-K 的替代）
- **424B1-424B4**: 招股说明书（IPO 定价和发行详情）

### 配置

```bash
# .env 文件
SEC_CONTACT=your-email@example.com
SEC_APP_NAME=StockResearchAgent
SEC_REQUEST_DELAY=0.2  # 请求间隔（秒）
```

## 成本参考

| Agent 类型 | 模型 | 典型耗时 | 典型成本 |
|-----------|------|---------|---------|
| Layer 1 (知识) | sonnet | 10-25 min/agent | $1-4/agent |
| Layer 2 (观点) | sonnet | 2-5 min/agent | $0.1-0.3/agent |
| Summary | sonnet | 3-5 min | $0.2-0.4 |
| Challenge | sonnet | 3-5 min | $0.2-0.3 |
| **完整流程** | sonnet | **2-4 小时** | **$8-12** |

> 注：Layer 1 agents 使用 WebSearch 较多，成本波动较大。实测 MELI 完整流程耗时 ~3.5 小时，成本 ~$9。

## 免责声明

本工具仅供信息和教育目的。生成的投资备忘录不构成投资建议。投资决策前请进行独立研究并咨询专业人士。

## License

MIT License

---

**Built with [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk)**
