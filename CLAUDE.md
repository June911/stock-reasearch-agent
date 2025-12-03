# CLAUDE.md

基于 Claude Agent SDK 的多层股票研究系统。详细文档见 [README.md](README.md)。

## 常用命令

```bash
# 完整 pipeline
uv run python run_pipeline.py --ticker NVDA --model sonnet

# 单 agent 测试
uv run python single_agent.py --agent deep-history --ticker NVDA --model sonnet

# 预处理 SEC 文件
uv run python preprocess_sec.py NVDA
```

## 代码修改约定

### 语言
- **研究输出 & prompts**: 中文
- **代码 & 注释**: English

### 文件路径
- 始终使用相对路径（从项目根目录）
- 禁止 `~` 或绝对路径
- 输出到 `files/{TICKER}/notes/`

### Agent 设计原则
- **Layer 1**: 产出事实（发生了什么、如何运作）
- **Layer 2**: 产出判断（所以呢）
- **Layer 3**: 综合 + 挑战

### Prompt 修改
- Prompt 定义严格的输出 schema，不要随意改格式
- 保留 `{TICKER}` 和 `{DATE}` 占位符
- 修改后先用 single_agent 测试，再跑 pipeline

### SEC 数据流
- Agent 优先读本地 `_index.json` + `raw/*.md`
- 不要直接调 SEC API 下载
- 用 `extract_sec_sections` 解析 HTML（节省 90%+ tokens）

## 常见修改

**添加新 view 框架:**
1. 创建 `prompts/view/观点_{name}.md`
2. 在 `single_agent.py` 的 `AGENT_PRESETS` 添加 `view-{name}`
3. 在 `run_pipeline.py` 的 `LAYER2_AGENTS` 添加
4. 更新 `summary_agent.txt` 读取新文件

**添加新 SEC 章节:**
1. 更新 `preprocess_sec.py` 的 `FILING_SECTIONS`
2. 添加 `SECTION_FILENAME_MAP` 映射
