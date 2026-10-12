# 从离线原型到真实实验

[返回首页](README.md) · [配置模板](EXPERIMENT_CONFIG.template.json) · [结果模板](RESULTS_TEMPLATE.md)

本手册将后续工作拆成可验收步骤。本地模型运行器已实现但待真实权重联调；真实网页数据和强基线仍需准备；本文不是已经执行的实验报告。

## 1. 固定实验身份

复制配置模板，为每个模型、数据版本和生成重复建立新目录。根目录模板是记录格式，不被程序自动加载；本地推理使用单独的 [可执行配置](experiment/local_config.template.json)，详见 [运行指南](experiment/LOCAL_INFERENCE.md)。数据/split、权重或服务版本、tokenizer/chat template、压缩配置、提示或生成参数变化时，使用新 run_id。

必要记录包括公开输入与金标哈希、代码版本、模型、依赖预测器、预算单位、输出预留、重试政策和环境。不要把密钥写入配置或仓库。

prepare/evaluate 已拒绝覆盖已有产物，评分输出 evaluation_manifest.json，记录输入/输出和代码哈希；重复矩阵、混合单位或不同 run_id 会报错。旧式无 run_id 预测仍兼容但无法自动排除跨运行混用，详见 [运行记录](experiment/RUN_INTEGRITY.md)。

请求 ID 不构成全局运行 ID：不同代码/模板/tokenizer 版本可能生成相同 ID。用 `run_id + request_id` 管理预测归属，将 requests、predictions、scores 和 manifest 一起归档。

```text
work/runs/<run_id>/
├── config.json             填写后的配置
├── requests.jsonl          prepare 生成的模型输入
├── context_diagnostics.jsonl
├── manifest.json
├── run_manifest.json       本地运行身份、配置和资产哈希
├── preflight.jsonl         完整输入窗口检查
├── journal.jsonl           本地运行器原始回复与开始/结果事件
├── predictions.jsonl       结构化输出 + 原始文本、用量、耗时与状态
├── evaluation/scores.jsonl
└── analysis/               成对报告，不覆盖已有文件
```

仓库忽略 work/。未来发布应选择性导出允许公开的证据和汇总，不直接上传密钥、缓存或全部网页快照。不要把多个模型或生成重复放进同一 scores 文件。

## 2. 采集与标注

每题需要 question、source snapshots、cluster_id、答案/别名、answerability 和充分证据集合。每个快照记录 URL、抓取时间、出版/更新时间（若存在）、文本声明的有效时间、内容哈希及再分发许可。缺失字段记未知，不从当前时间猜测。

标注顺序：

1. 阅读完整来源，独立作答，记录是否存在无法裁决的冲突。
2. 圈出答案句，再补齐决定范围的时间、对象、资格和例外。
3. 另一套独立充分证据另建 evidence set，不强制保留全部替代证据。
4. 使用 A 需要 B 时记 A→B；主题相关不等于必要依赖。
5. 标记困难：隐含条件、列表/表格作用域、跨段回指和多种解释。
6. 第二位标注员独立复核，记录分歧、裁决和最终版本。

依赖标注建议包含 `source_id / required_id / relation / rationale / adjudication_status`。rationale 是简短依据，不要求冗长推理过程。金标图只用于评测或 oracle，不能传给待评估预测器。

### 后续关系预测接口草案

```json
{
  "source_id": "D1:s1",
  "required_id": "D1:s2",
  "relation": "eligibility",
  "confidence": null,
  "evidence_span_ids": ["D1:s1", "D1:s2"]
}
```

这是待实现适配合同，当前规则没有该分类器接口。标签可为 `temporal_scope / eligibility / exception / antecedent / explicit_reference / none`。只接受已存在的 ID；置信度须定义并校准，不能把模型自报分数直接当概率。替代支持、争议和低置信关系不直接转换为硬边。

数据结构、快照字节哈希及明确的切分重叠检查已实现，命令和边界见 [数据验收](experiment/DATA_VALIDATION.md)。语义充分性、许可和近重复仍须人工复核。

### 数据切分

事件、文档版本、镜像、近重复和成对改写保持同 split。先用开发题定规则，再冻结诊断题；约 150 题只是 pilot 规模建议，不是显著性保证。正式规模根据独立簇数、方差与目标效果决定。

## 3. 十题联调验收

- [ ] 目标模型真实 tokenizer 计数，不使用正则单元做效率结论。
- [ ] 聊天模板后的完整输入加输出预留不超窗口，无静默截断。
- [ ] 模型仅接收 requests 中 messages，不接收 gold 或诊断文件。
- [ ] 每题独立会话，模型版本和生成设置固定。
- [ ] 保存原始回复、完成原因、用量、耗时和异常。
- [ ] 解析失败保存 output:null，不破坏 JSONL 格式。
- [ ] 引用只能指向模型实际可见的句子 ID。
- [ ] 请求无重复、无漏记；失败仍保留在分母。
- [ ] 基础设施重试政策固定并记录成本，不因答错而反复重问。本地运行器不自动重试；中断请求保留为失败。
- [ ] 手工复核正确、错误、拒答和格式失败的评分路径；某类未自然出现时，另建明确标为软件检查的样例，不混入模型成绩。

生成输出固定为 `{answer, citations, abstain}`。证据不足时 answer 为空、citations 为空列表、abstain 为 true。不同压缩方法不得使用不同答案提示。

原始不可回答题的正确拒答可算成功；原题可回答但压缩丢证据后拒答，仍未完成任务，不能混淆。

## 4. 最小实验矩阵

候选 pilot：full、none、同强分数 selection、neighbors、closure、Provence，三个实际 token 预算。150 题、一个模型、四种受预算方法的答案调用数为 `150 × (2 + 4 × 3) = 2,100`，另加预测、摘要或 judge 调用。

原型 BM25 不等于强分数 selection，强打分器和 Provence 尚需适配。先报告弱基线诊断，再完成决定性强对照，不能用名字替代实现。固定预算外报告原生质量—长度曲线；预算适配器在开发集确定。抽象摘要不机械套用原句 ID 的 CER。

下面假设真实数据和本地 tokenizer 已准备、可选依赖已安装；当前包不下载权重；本地适配器不提供托管推理服务：

```bash
python experiment/prototype.py prepare --data work/data/pilot.jsonl --out work/runs/pilot_modelA_v1 --budgets 512 1024 2048 --tokenizer /absolute/path/to/local-tokenizer
```

prepare 后先按 [本地模型指南](experiment/LOCAL_INFERENCE.md) 在新目录生成预测。十条 smoke run 使用运行器保存的请求子集评分；正式统计须显式计划完整矩阵，核对请求数，并把下方 requests/predictions 路径都替换为同次完整运行目录。

## 5. 从预测到统计

```bash
python experiment/prototype.py evaluate --data work/data/pilot.jsonl --requests work/runs/pilot_modelA_v1/requests.jsonl --predictions work/runs/pilot_modelA_v1/predictions.jsonl --out work/runs/pilot_modelA_v1/evaluation

python experiment/analyze.py --scores work/runs/pilot_modelA_v1/evaluation/scores.jsonl --candidate closure --baseline bm25 --budget 1024 --resamples 10000 --seed 2026 --out work/runs/pilot_modelA_v1/analysis
```

这只比较短答案 EM 与严格引用集合代理，公开 benchmark 仍需对应官方指标。统计要求 full/budget=0 参照及完全相同的问题集合，不能只取成功返回题目的交集。

cluster bootstrap 抽取文档/事件簇，簇内问题和变体一起抽样，报告问题加权差值区间。它不估计生成随机性、标注偏差或数据污染。两个簇只是程序能计算的下限，少量独立簇的区间不可靠。

当前工具不计算 CER 汇总、语义引用、费用、延迟或多重比较校正；这些需另补。多个模型或生成重复分别分析，不把同一道题复制成独立样本。

## 6. 错误归因与继续条件

抽样检查各方法成功与失败：检索原本缺证据；漏边；错误边使闭包过大；选对证据但模型忽略条件；格式/引用 ID 错误；金标/评分歧义。“答案正确但证据不足”也要保留，不把碰巧猜对当保真。

扩大前判断：强基线是否已覆盖收益；oracle 图是否显示依赖有价值；预测与选择成本是否值得。按证据调整主张，不在测试集挑最好看预算。

## 7. 受控演绎诊断

原始答案 EM 不能独立说明演绎能力。新增 [演绎模块](experiment/DEDUCTION.md) 用事实、合取规则和三种逻辑状态核验受控任务，保持金标图不进入模型输入。主方法依旧按公开文本构图。

当前 60 题全为开发样例，包含深度 0 对照和 1–4 步推导。分别报告 full 的准确率、压缩后的证明保留、证明完整时的任务表现、引用支持与配对世界一致性。未知题无正向证明，不放入 proof retention 分母。条件准确率的分母因方法而异，只作为诊断，不替代同题配对比较。

新增指标的正式置信区间仍需扩展；当前 analyze.py 仅分析原有答案 EM 和精确证据代理。四个开发题族不足以支撑稳定统计结论；随机换名不是独立模板。后续引入官方任务及真实网页，不能用受控题替代 WWW 所需的外部有效性。

## 8. 写入论文

填写结果模板，链接运行日志和预先确定的主比较。说明性数字与实测分开；CI 单位用 percentage points；零分母写 undefined。未知模型/tokenizer 或缺失日志时先补追溯，再下结论。

最后补齐 CFP、ACM 模板、文献元数据、匿名链接和允许公开的数据。研究状态框和 pending 只能在对应证据确实存在后修改。
