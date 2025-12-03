# CLAUDE.md

多层股票研究系统。详细文档见 README.md。

## 常用命令

```bash
uv run python run_pipeline.py --ticker NVDA --model sonnet  # 完整流程
uv run python single_agent.py --agent deep-history --ticker NVDA --model sonnet  # 单 agent
uv run python preprocess_sec.py NVDA  # 预处理 SEC
```

## 约定

- **语言**: prompts/输出用中文，代码/注释用 English
- **路径**: 相对路径，输出到 `files/{TICKER}/notes/`
- **SEC 数据**: 读本地 `_index.json` + `raw/*.md`，不要直接调 API
- **Prompt**: 保留 `{TICKER}` `{DATE}` 占位符，改后先用 single_agent 测试
