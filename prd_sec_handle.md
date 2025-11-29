# SEC 财报处理方案

## 一、目标

将 SEC 原始财报文件（10-K、10-Q、S-1、DEF 14A 等）转化为结构化知识库，实现：

1. **降低 Token 成本**：从 100K+ tokens 降至按需加载的 5-10K tokens
2. **提高分析效率**：Agent 可直接定位所需信息，无需每次全文解析
3. **支持增量更新**：新季报发布后，只更新变化部分
4. **标准化输出**：所有公司的知识库结构一致，便于横向对比

---

## 二、核心原则

### 2.1 脚本 vs Skill 分工

| 层级 | 执行者 | 职责 | 特点 |
|------|--------|------|------|
| **脚本层** | Python | 清洗、切分、结构化 | 零Token成本、100%确定性、可复用 |
| **Skill层** | Agent/LLM | 分析、判断、输出 | 需要理解、灵活处理、消耗Token |

**判断标准**：任务是否需要"理解"？
- 不需要理解 → 脚本
- 需要理解/判断 → Skill/Agent

### 2.2 SEC 文件价值密度

| 文件类型 | 核心价值 | 优先级 | 处理建议 |
|----------|----------|--------|----------|
| **S-1/招股书** | 历史、商业模式、风险（最完整） | ⭐⭐⭐ | 详细拆分，作为基础 |
| **10-K** | 年度全貌 | ⭐⭐⭐ | 必须拆分，保留详细版 |
| **10-Q** | 季度更新，增量信息 | ⭐⭐ | 提取变化部分，与10-K diff |
| **DEF 14A** | 高管薪酬、股权结构、治理 | ⭐⭐ | 对应"组织架构"模块 |
| **8-K** | 重大事件 | ⭐ | 事件驱动，按时间线索引 |
| **Form 4** | 内部人交易 | ⭐ | 结构化存储，监控用 |

### 2.3 10-K/10-Q 内部价值分布

```
高价值（必须精读提取）
├── Item 1: Business（商业模式）
├── Item 1A: Risk Factors（风险清单）
├── Item 7: MD&A（管理层讨论）
└── Financial Statements + Notes（财务数据）

中等价值（按需加载）
├── Item 2: Properties
├── Item 5: Market for Common Equity
└── Item 8: 审计报告

低价值（可忽略）
├── 封面、目录、签名页
├── 法律声明模板
└── XBRL 元数据
```

---

## 三、系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                     原始文件层                               │
│   SEC EDGAR 下载的 HTML/XBRL 文件（10-K, 10-Q, S-1 等）       │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   脚本处理层（零Token成本）                   │
│                                                             │
│  sec_parser.py                                              │
│  ├── 清洗：去除HTML样式、XBRL标签、模板内容                   │
│  ├── 切分：按Item/Section拆分成独立文件                      │
│  ├── 提取：财务数据 → JSON，叙述内容 → Markdown              │
│  └── 索引：生成元数据和摘要                                  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                     结构化知识库                             │
│                                                             │
│  /知识库/{Ticker}/                                          │
│  ├── _index.json          # 元数据、文件索引                 │
│  ├── raw/                 # 按章节切分的原始内容              │
│  ├── structured/          # 结构化数据（JSON）               │
│  └── processed/           # Agent分析产物                    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   Skill 指导层（消耗Token）                   │
│                                                             │
│  SKILL.md                                                   │
│  ├── 数据位置：哪个分析任务读哪个文件                         │
│  ├── 分析框架：判断标准、异常信号识别                         │
│  └── 输出模板：最终报告格式                                  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      Agent 分析层                            │
│                                                             │
│  按需加载知识库文件，执行：                                   │
│  ├── 财务分析                                               │
│  ├── 商业模式分析                                           │
│  ├── 风险评估                                               │
│  └── ...                                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 四、知识库目录结构

### 4.1 原始方案（按季度组织）

```
/知识库/{Ticker}/
│
├── _index.json                 # 元数据（公司信息、文件清单、最后更新时间）
│
├── raw/                        # 按章节切分的原始内容（Markdown）
│   ├── item1_business.md       # 业务描述
│   ├── item1a_risks.md         # 风险因素
│   ├── item7_mda.md            # 管理层讨论与分析
│   ├── item7a_market_risk.md   # 市场风险披露
│   └── notes/                  # 财报注释（重要！）
│       ├── note_revenue.md     # 收入确认政策
│       ├── note_segments.md    # 业务分部
│       └── ...
│
├── structured/                 # 结构化数据（JSON，可计算）
│   ├── financials.json         # 三大报表数据
│   ├── metrics.json            # 关键指标（预计算YoY、QoQ）
│   ├── segments.json           # 业务分部数据
│   └── shareholders.json       # 股权结构
│
├── history/                    # 历史版本（支持diff比较）
│   ├── 2024Q4/
│   ├── 2025Q1/
│   ├── 2025Q2/
│   └── 2025Q3/
│
├── events/                     # 8-K重大事件
│   └── events.json             # 时间线索引
│
└── processed/                  # Agent分析产物
    ├── business_model.md       # 商业模式分析
    ├── financial_analysis.md   # 财务分析
    └── risk_assessment.md      # 风险评估
```

### 4.2 采用方案（按日期组织） ✅

**决策理由**：
- 直接用 report_date，不需要额外推算季度
- 避免财年混乱（不同公司财年结束月份不同）
- 与 filings 目录命名一致，结构清晰

```
/files/{Ticker}/
│
├── _index.json                       # 元数据索引
│
├── filings/                          # 原始 HTML（已有，自动下载）
│   ├── 2025-09-30_10-Q_000187604225000047/
│   │   ├── crcl-20250930.htm
│   │   └── metadata.json
│   └── 2024-12-31_10-K_000187604225000012/
│       └── ...
│
├── raw/                              # 提取后的 Markdown（按 filing 分组）
│   ├── 2025-09-30_10-Q/
│   │   ├── item1.md
│   │   ├── item1a_risks.md
│   │   └── item7_mda.md
│   └── 2024-12-31_10-K/
│       ├── item1_business.md
│       ├── item1a_risks.md
│       └── item7_mda.md
│
└── notes/                            # 研究笔记（已有）
    └── ...
```

### 4.3 _index.json 结构

```json
{
  "ticker": "CRCL",
  "company_name": "Circle Internet Group",
  "updated_at": "2025-11-28T10:00:00",
  "filings": [
    {
      "report_date": "2025-09-30",
      "filing_type": "10-Q",
      "filing_date": "2025-11-06",
      "fiscal_quarter": "Q3",
      "fiscal_year": "2025",
      "source_file": "filings/2025-09-30_10-Q_000187604225000047/crcl-20250930.htm",
      "raw_dir": "raw/2025-09-30_10-Q/",
      "sections": ["item1", "item1a_risks", "item7_mda"],
      "processed_at": "2025-11-28T10:00:00"
    },
    {
      "report_date": "2024-12-31",
      "filing_type": "10-K",
      "filing_date": "2025-03-15",
      "fiscal_quarter": "Q4",
      "fiscal_year": "2024",
      "source_file": "filings/2024-12-31_10-K_.../...",
      "raw_dir": "raw/2024-12-31_10-K/",
      "sections": ["item1_business", "item1a_risks", "item7_mda"],
      "processed_at": "2025-11-28T10:00:00"
    }
  ]
}
```

### 4.4 方案对比

| 维度 | 原方案（按季度） | 采用方案（按日期） |
|------|-----------------|-------------------|
| 目录命名 | `history/2025Q3/` | `raw/2025-09-30_10-Q/` |
| 财年处理 | 需要推算 | 无需处理 |
| 与 filings 一致性 | 需要映射 | 直接对应 |
| 同期多 filing | 不易处理 | 自然支持（不同 accession） |
| 直观性 | 季度直观 | 日期精确 |

---

## 五、脚本设计

### 5.1 核心脚本：sec_parser.py

```python
"""
SEC 财报解析脚本

功能：
1. 清洗 HTML/XBRL 文件
2. 按 Item 切分章节
3. 提取结构化数据
4. 生成索引文件

输入：SEC 原始文件（HTML/XBRL）
输出：结构化知识库目录
"""

class SECParser:
    
    def __init__(self, ticker: str, file_path: str):
        self.ticker = ticker
        self.file_path = file_path
        self.file_type = self._detect_file_type()  # 10-K, 10-Q, S-1, etc.
    
    def parse(self) -> dict:
        """主解析流程"""
        # Step 1: 清洗
        clean_text = self._clean_html()
        
        # Step 2: 切分
        sections = self._split_sections(clean_text)
        
        # Step 3: 提取财务数据
        financials = self._extract_financials()
        
        # Step 4: 生成索引
        index = self._generate_index(sections, financials)
        
        return {
            'sections': sections,
            'financials': financials,
            'index': index
        }
    
    def _clean_html(self) -> str:
        """清洗 HTML/XBRL 标签"""
        # - 移除 style 标签
        # - 移除 XBRL 元数据（<ix:header>, context definitions）
        # - 移除表格样式，保留表格内容
        # - 处理特殊字符
        pass
    
    def _split_sections(self, text: str) -> dict:
        """按 Item 切分章节"""
        # 识别标准 Item 标题：
        # - "Item 1. Business"
        # - "Item 1A. Risk Factors"
        # - "Item 7. Management's Discussion..."
        # 返回 {item_id: content} 字典
        pass
    
    def _extract_financials(self) -> dict:
        """提取三大报表数据"""
        # - 资产负债表
        # - 利润表
        # - 现金流量表
        # 返回结构化 JSON
        pass
    
    def _generate_index(self, sections, financials) -> dict:
        """生成索引文件"""
        return {
            'ticker': self.ticker,
            'file_type': self.file_type,
            'period': self._extract_period(),
            'sections': list(sections.keys()),
            'financials_available': list(financials.keys()),
            'processed_at': datetime.now().isoformat()
        }

    def save(self, output_dir: str):
        """保存到知识库目录"""
        pass
```

### 5.2 Item 切分规则

| Item | 标题关键词 | 输出文件 |
|------|-----------|----------|
| Item 1 | "Business" | item1_business.md |
| Item 1A | "Risk Factors" | item1a_risks.md |
| Item 1B | "Unresolved Staff Comments" | item1b_comments.md |
| Item 2 | "Properties" | item2_properties.md |
| Item 3 | "Legal Proceedings" | item3_legal.md |
| Item 4 | "Mine Safety" | （跳过） |
| Item 5 | "Market for Registrant" | item5_market.md |
| Item 6 | "Selected Financial Data" | item6_selected.md |
| Item 7 | "Management's Discussion" | item7_mda.md |
| Item 7A | "Quantitative and Qualitative" | item7a_market_risk.md |
| Item 8 | "Financial Statements" | item8_financials.md |

### 5.3 财务数据提取格式

```json
{
  "balance_sheet": {
    "period": "2025-09-30",
    "assets": {
      "total_assets": 12345678000,
      "current_assets": 5678900000,
      "cash_and_equivalents": 1234567000,
      // ...
    },
    "liabilities": {
      // ...
    },
    "equity": {
      // ...
    }
  },
  "income_statement": {
    "period": "Q3 2025",
    "revenue": 456789000,
    "cost_of_revenue": 123456000,
    "gross_profit": 333333000,
    // ...
  },
  "cash_flow": {
    // ...
  },
  "metrics": {
    "gross_margin": 0.73,
    "net_margin": 0.15,
    "revenue_yoy": 0.25,
    "revenue_qoq": 0.08,
    // 预计算的关键指标
  }
}
```

---

## 六、Skill 设计

### 6.1 SKILL.md 结构

```markdown
# SEC 知识库分析 Skill

## 数据位置指南

| 分析任务 | 主要数据源 | 补充数据源 |
|----------|-----------|-----------|
| 商业模式分析 | raw/item1_business.md | raw/notes/note_revenue.md |
| 财务分析 | structured/financials.json | raw/item7_mda.md |
| 风险评估 | raw/item1a_risks.md | events/events.json |
| 组织架构分析 | structured/shareholders.json | （需要 DEF 14A） |

## 分析流程

1. **先读 _index.json**：了解有哪些文件可用
2. **按任务选择性加载**：不要一次读取全部文件
3. **优先读结构化数据**：JSON 比 Markdown 更节省 Token
4. **需要深入时再读原文**：如发现异常，再读相关 Markdown

## 异常信号识别

### 财务异常
- 收入增长 vs 现金流背离
- 毛利率突变（±5%以上）
- 应收账款增速 > 收入增速

### 风险信号
- Risk Factors 新增条目
- 措辞从 "may" 变为 "likely"
- 诉讼、监管相关新增内容

### 治理信号
- 高管突然离职
- 审计师变更
- 内部控制缺陷披露

## 输出模板

（链接到现有的分析模板：知识库_财务分析.md 等）
```

### 6.2 与现有分析框架的对接

| 现有框架 | 数据来源 |
|----------|----------|
| 知识库_公司历史.md | S-1 + 历史 10-K + 8-K 事件 |
| 知识库_商业模式.md | Item 1 Business + Notes |
| 知识库_财务分析.md | structured/financials.json + Item 7 MD&A |
| 知识库_组织架构.md | DEF 14A + Item 10-14 |
| 知识库_赛道分析.md | Item 1 市场描述 + 外部来源 |
| 知识库_企业文化.md | DEF 14A + Glassdoor + 新闻 |

---

## 七、处理流程

### 7.1 首次建库（新公司）

```
1. 下载 SEC 文件
   └── S-1（如有）、最近 10-K、最近 4 个 10-Q、DEF 14A

2. 运行脚本
   └── python sec_parser.py --ticker CRCL --files ./raw_files/

3. 检查输出
   └── 确认 _index.json、raw/、structured/ 生成正确

4. Agent 分析
   └── 按分析框架执行，输出存入 processed/
```

### 7.2 增量更新（新季报）

```
1. 下载新 10-Q

2. 运行脚本（增量模式）
   └── python sec_parser.py --ticker CRCL --file new_10q.htm --incremental

3. 自动生成
   ├── 新季度数据存入 history/2025Q3/
   ├── 更新 structured/financials.json
   └── 生成 diff 报告（与上季度对比）

4. Agent 更新分析
   └── 重点关注变化部分
```

### 7.3 跨公司对比

```
1. 确保目标公司知识库结构一致

2. Agent 读取多个 structured/financials.json

3. 执行对比分析
   └── 同行业指标对比、估值对比等
```

---

## 八、容易忽略的重要事项

| 事项 | 为什么重要 | 处理建议 |
|------|-----------|----------|
| **财报注释（Notes）** | 真正的细节藏在这里：收入确认、客户集中度、诉讼 | 单独提取关键 Notes |
| **YoY/QoQ 变化** | 趋势比绝对值重要 | 脚本预计算变化率 |
| **管理层措辞变化** | 信号价值高 | 保留历史版本，支持 diff |
| **非 GAAP 指标** | 公司自定义，需理解计算方式 | 提取定义，标注来源 |
| **Earnings Call** | 不在 SEC 文件里，但有最真实信息 | 作为补充数据源 |
| **Proxy (DEF 14A)** | 组织/治理分析必需 | 单独处理流程 |

---

## 九、预期收益

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| 单次分析 Token 消耗 | ~100K | ~10-20K（按需加载） |
| 文件定位时间 | 每次全文搜索 | 直接读取目标文件 |
| 跨季度对比 | 手动对比 | 结构化 diff |
| 新公司建库 | 每次重新解析 | 脚本一键生成 |
| 分析一致性 | 依赖 Agent 记忆 | 标准化知识库结构 |

---

## 十、下一步行动

1. **[ ] 开发 sec_parser.py 核心脚本**
   - 支持 10-K、10-Q 解析
   - 输出标准目录结构

2. **[ ] 编写 SKILL.md**
   - 指导 Agent 使用知识库
   - 与现有分析框架对接

3. **[ ] 测试：以 Circle (CRCL) 为例**
   - 处理已上传的 10-Q
   - 验证输出质量

4. **[ ] 扩展支持**
   - S-1 招股书解析
   - DEF 14A 代理声明解析
   - 8-K 事件索引

---

*文档版本：v1.0*  
*创建日期：2025-11-28*