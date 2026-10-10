# ScopePack — WWW research draft

**Preserving Applicability under Context Budgets: Dependency-Closed Compression for Web Question Answering**

面向网页问答的上下文压缩方法初稿：在上下文预算内共同保留陈述及其适用时间、资格条件、例外、回指和来源依赖。

## Research status / 当前状态

This repository contains a research proposal, an offline prototype, and an evaluation protocol. It does **not** contain real LLM experiment results or evidence of superiority over existing methods.

- 已完成：英文方法稿、中文实验方案、文献核对、上下文选择与导入预测评分原型。
- 软件验证：7 项检查通过；8 个虚构软件样例；112 条模型请求已准备，未发送给模型。
- 默认长度单位是 `regex_units_NOT_LLM_TOKENS`，不能用于正式 token 效率结论。
- 待完成：真实网页数据、目标 tokenizer、模型推理后端、Provence 等强基线、正式统计与成本分析。
- 所有论文结果仍为 `pending`。目标 WWW 届次及 CFP 未核验；当前不是可直接投稿的终稿。

## Read the draft / 阅读入口

| 内容 | 文件 |
|---|---|
| 英文初稿 | [www_draft.md](www_draft.md) |
| LaTeX 源文件 | [www_draft.tex](www_draft.tex) |
| 中文研究与实验方案 | [研究与实验方案.md](研究与实验方案.md) |
| 近邻文献与查新待办 | [文献核对与待办.md](文献核对与待办.md) |
| 实验原型说明 | [experiment/README.md](experiment/README.md) |
| 实际软件检查记录 | [experiment/validation_report.md](experiment/validation_report.md) |
| 下一阶段任务 | [ROADMAP.md](ROADMAP.md) |
| 原始完整初稿包 | [WWW初稿包.zip](WWW初稿包.zip) |

## Run the offline prototype

Python 3.10+; standard library only for the default fixture run. Run from the repository root:

```bash
python experiment/prototype.py prepare --data experiment/demo.jsonl --out work/demo_run
python -m unittest discover -s experiment -p "test_*.py" -v
```

`prepare` creates requests and context diagnostics. It does not invoke a model. The checked-in `experiment/demo_run/` is a prepared fixture run, not a measured model run.

After connecting a model backend and saving real predictions:

```bash
python experiment/prototype.py evaluate --data experiment/demo.jsonl --requests work/demo_run/requests.jsonl --predictions work/demo_run/predictions.jsonl --out work/evaluation
```

The scoring command above requires a real prediction file from that same run; no such file is included. Formal datasets should replace the fixtures and use their appropriate official metrics.

## Method and scope

The current implementation uses BM25 scores and deterministic English dependency rules. A selected sentence is packed with its transitive dependency closure; all serialized source headers and sentence IDs count toward the context budget. Neural relation prediction and strong compressor adapters are proposed extensions, not implemented capabilities.

The main scientific comparison is **same scorer, same budget and optimizer, with versus without explicit dependencies**, alongside Provence and neighbor expansion. Novelty and empirical value remain unproven.

## Manuscript and publication

The Markdown and LaTeX files are working drafts. The native LaTeX compiler previously failed due to an environment directory error, so no verified PDF is included. The layout is not a verified ACM submission template. Preserve pending-result labels until measured evidence exists.

This repository is private during research preparation. No open-source license has been selected. Source data permissions and the eventual release license require a separate decision before public release.
