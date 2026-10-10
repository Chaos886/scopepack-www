# ScopePack 离线评测原型

这是方法初稿的可执行起点。**已完成上下文选择及导入预测评分，没有模型推理后端，没有真实模型成绩。** `demo.jsonl` 的 8 题全部是人工构造的软件样例，不能用于证明论文方法有效。

## 1. 环境与已运行的结果

Python 3.10+，默认流程仅依赖标准库。在本文件所在的 `experiment` 目录执行；请使用你自己的 Python 解释器。

```bash
python prototype.py prepare --data demo.jsonl --out ../work/demo_run
python -m unittest discover -s . -p "test_*.py" -v
```

已实际验证：13 项测试通过（7 项原型约束 + 6 项统计约束）；生成 112 条请求。`demo_run/manifest.json` 状态为 `PREPARED_NOT_EXECUTED`。

默认预算 `[64,128,256]` 是正则计数单元，标记为 `regex_units_NOT_LLM_TOKENS`，**不是 LLM token**。这种模式只用于断言预算算法、数据流与评分行为，不用于论文效率曲线。

## 2. 文件如何流转

```text
data.jsonl（问题 + 文档 + 评测金标）
        │ prepare：仅 public_input 字段进入压缩器
        ├── requests.jsonl → 你的模型后端 → predictions.jsonl
        ├── context_diagnostics.jsonl（评测侧，含金标证据保留诊断）
        └── manifest.json

data.jsonl + requests.jsonl + predictions.jsonl
        │ evaluate
        ├── scores.jsonl
        └── summary.json
```

只把每条 request 的 `messages` 发给模型。不要把整个数据集、金标、诊断文件或其他题的答案发过去。每条请求独立会话。

## 3. 数据格式

每行一个 JSON 对象。示意如下，内容只是虚构格式例子：

```json
{
  "id": "policy_001",
  "cluster_id": "policy_event_001",
  "question": "Are reseller purchases refundable?",
  "documents": [{
    "doc_id": "D1",
    "title": "Example policy",
    "source": "synthetic://example",
    "snapshot": "synthetic-v1",
    "sentences": [
      {"sid": "s1", "paragraph": "p1", "text": "The annual plan allows a refund within fourteen days."},
      {"sid": "s2", "paragraph": "p1", "text": "This applies only to direct purchases, except reseller orders."}
    ]
  }],
  "gold": {
    "answers": ["No", "No, reseller purchases are excluded"],
    "evidence_sets": [["D1:s1", "D1:s2"]],
    "abstain": false
  }
}
```

实际 JSONL 必须把每个对象写在一行。句子 ID 由 `doc_id:sid` 组成，一题内不能重复。`paragraph` 用于依赖规则，不是可忽略的装饰字段。文档顺序等于序列化顺序。

`gold.evidence_sets` 可以有多个充分集合，保留任一个集合即可满足 CER。示例严格联合评分要求输出引用恰好等于某个集合。不可回答题设置 `gold.abstain=true`；正确输出必须为 `answer=""`、`citations=[]`、`abstain=true`。

代码的 `public_input()` 仅复制问题与文档必要字段。改变 gold 或 task_type 不影响选择；测试已经验证。新增训练/测试信息字段时应继续使用白名单，别把整个 sample 传给模型。

## 4. 已实现的选择方法

| 参数 | 实际行为 |
|---|---|
| `full` | 保留全部原句，作为参照，不受预算约束；记录 budget=0 表示不适用，并非空输入 |
| `none` | 空文档上下文，仍保留问题和系统指令；budget=0 |
| `head` | 按原顺序装入能容纳的完整句子；可能跳过过长句，不等于严格前缀截断 |
| `bm25` | BM25 相关性与新增渲染成本驱动的多起点选择 |
| `neighbors` | 同分数、同选择器，每个种子扩展同文档前后各一句；不沿邻句无限扩展 |
| `closure` | 同分数、同选择器，加入每句的预测依赖闭包 |

所有输出保留原文顺序和来源头。预算核算包含来源头、句子 ID 和分隔符。规则图包括同段条件绑定、有限回指与原文中的显式 ID 引用。

`head-tail`、dense/强重排、LongLLMLingua、LLMLingua-2、Provence、学习型关系分类器及其消融尚未接入。不要把 `bm25` 当作这些强基线的替代。

## 5. 正式 token 预算

需自行准备与目标模型一致且固定版本的本地 Hugging Face tokenizer，并在自己的实验环境安装匹配的 `transformers` 及该 tokenizer 所需依赖。当前未安装，也不自动下载任何权重。

```bash
python prototype.py prepare --data real_data.jsonl --out run_001 --budgets 512 1024 2048 --tokenizer 'D:/models/your-tokenizer'
```

代码以 `local_files_only=True`、`trust_remote_code=False` 载入；需要远程自定义代码的 tokenizer 不直接支持。此计数覆盖**序列化 context 部分**，不含聊天模板、问题、固定系统指令或生成预留。模型后端必须对完整请求另外检查窗口，禁止静默截断。

正式实验固定并额外保存 tokenizer 文件版本/哈希、模型版本和 chat template。现有 manifest 只记录数据/原型哈希、tokenizer 路径与请求数，尚不足以独立锁定全部外部环境。

不同运行请使用不同目录，避免覆盖。请求 ID 可在相同配置重跑时复用，但不能假设跨代码/模板/不同 tokenizer 版本唯一；预测必须与该次保存的 requests 和 manifest 一起归档，禁止混用。

## 6. 怎样接入大模型

当前没有推理 adapter。接入所选本地推理框架或模型服务时，最小循环如下；这是后端无关伪代码，`backend.generate` 需要按实际后端实现：

```python
for request in requests:
    # 检查完整聊天模板输入 + 输出预留不超模型窗口
    raw, usage, timing, finish_reason = backend.generate(
        messages=request["messages"],
        model=EXACT_MODEL_VERSION,
        decoding=FROZEN_DECODING_CONFIG,
    )
    # 原始回复与配置单独落盘；不要丢弃失败。
    parsed = strict_json_parse(raw)  # 失败时为 null
    append_prediction({"id": request["id"], "output": parsed})
```

`requests.jsonl` 每行包含 `id`、`sample_id`、`method`、`budget`、`budget_unit`、`input_hash`、`selected_ids`、`context_units`、`messages`、`selection_ms`。系统提示已要求模型仅根据文档输出 JSON，并将网页文本视为证据而非指令。

你需要固定：确切模型版本、推理框架/服务版本、聊天模板、温度、采样参数、reasoning 参数（如适用）、输出 token 上限、随机种子（如支持）、并发和重试政策。不要默认所有后端支持相同参数。第一次先联调 10 条，再启动正式网格。

模型应返回以下结构；此处只是格式说明，不能复制为真实预测：

```json
{"answer":"a short answer","citations":["D1:s1","D1:s2"],"abstain":false}
```

保存的 `predictions.jsonl` 每行结构为：

```json
{"id":"EXACT_ID_FROM_REQUEST_FILE","output":{"answer":"a short answer","citations":["D1:s1","D1:s2"],"abstain":false}}
```

发生格式错误可保存 `output:null`，并在另一个原始日志中保存失败原因。这里的预测 schema 仅供评分；完整原始日志还应包含原始响应、模型标识、请求配置、token 用量、延迟、完成原因、重试、错误状态。不要把访问密钥写进日志。

基础实验不能遇到答错就重问。基础设施重试应有固定上限并计费；若采用格式修复，事先规定所有方法一致的规则，保留首次失败并单列额外成本。

## 7. 评分命令与含义

只有真实预测文件存在后再执行：

```bash
python prototype.py evaluate --data real_data.jsonl --requests run_001/requests.jsonl --predictions run_001/predictions.jsonl --out run_001/evaluation
```

对于 demo 数据则把 `real_data.jsonl` 换为 `demo.jsonl`，requests/predictions 路径同步换为同次 demo 运行目录。没有预测时不要编造文件来填结果表。

输出 `scores.jsonl` 为逐请求结果；`summary.json` 按 method 和 budget 汇总，所有率为 0–100 百分数：

- `valid`：输出 schema 有效，引用 ID 全部在实际可见上下文中，且引用无重复。它不代表回答正确或语义一致。
- `answer_em`：大小写及空白规范化后等于显式别名；原始不可回答题要求严格正确拒答。
- `joint_exact_evidence`：答案正确且引用集合精确匹配一个金标集合；是严格代理，不是语义支撑率。
- `missing`：该预定请求没有预测的比例；缺失仍保留在总题数 n 中并计零分。

未知或重复 prediction ID、重复 request ID、请求与数据公共输入哈希不匹配会报错。单条坏输出计零，无法解析的 JSONL 文件会报错；接入器需把坏模型回复存为 null，而非破坏 JSONL 格式。

CER 在 `context_diagnostics.jsonl` 中以 `complete_evidence_set_retained` 逐条记录，未实现分组统计；不可回答或没有证据集标注的题为 null。文件状态是 `CONTEXT_ONLY_NO_MODEL_INFERENCE`。它反映选择结果，不代表模型答对。

成对差值、Damage/Rescue 和分簇 bootstrap 已在独立的 `analyze.py` 实现，见 [统计说明](ANALYSIS.md)。官方 LongBench 评分、语义引用审查和延迟曲线仍未实现。当前 EM 不能称作 LongBench 官方分数。

## 8. 检查范围与局限

7 项测试检查循环/传递闭包、渲染预算、金标隔离、错误与不可见引用、拒答/坏格式、漏回分母及重复预测。Windows 环境的临时目录权限曾导致测试准备失败，现改用工作区普通目录；测试产生的中间文件保留在 `work/unit-tests/`。

预算测试覆盖 8 个样例 × 4 个受约束方法 × 6 个预算；新增 6 项统计测试验证成对比较、整簇抽样、缺失分母与异常数据处理。这些检查不能证明真实语义保真。没有真实模型、真实网页、神经基线结果或实测统计区间与速度测量。当前版本可为接入与分析做准备，不能直接产出支撑投稿的实证结论。
