# 数据验收与标注交接

[首页](../README.md) · [模型运行](LOCAL_INFERENCE.md) · [标注流程](../EXPERIMENT_PLAYBOOK.md)

`validate_data.py` 检查结构和明确的切分重叠。**通过检查不表示答案正确、证据充分、数据许可合规或不存在近重复。** 当前仓库只有 8 个虚构软件样例，没有自然网页数据集。

## 两级检查

```bash
# 软件联调及通用数据结构
python experiment/validate_data.py --data experiment/demo.jsonl

# 真实网页候选集：还检查来源、抓取时间和快照字节哈希
python experiment/validate_data.py --data work/data/pilot.jsonl --profile web --snapshot-root work/data/snapshots
```

`prepare` 和 `evaluate` 自动执行 basic 检查；**正式网页实验前仍须显式运行 web 检查**。所有命令从仓库根目录执行。

| 检查项 | basic | web 额外要求 |
|---|---|---|
| 样本身份 | 非空 id / cluster_id / question / provenance；id 唯一 | 不接受仓库的软件夹具标记 |
| 文档与句子 | 非空 title / source / snapshot；唯一 doc_id 和 doc_id:sid；非空 paragraph/text | source 为无用户凭证的 HTTP(S) URL |
| 金标 | 显式 bool abstain；非重复答案别名；证据 ID 存在且集合无重复 | 语义正确性依然人工复核 |
| 可回答性 | answerable 需非空 answers 与 evidence_sets；不可回答则两者为空 | 不自行推断答案或来源权威性 |
| split | 全部指定或全部省略；只接受 train/dev/test | 每题都必须指定 |
| 切分重叠 | 同 cluster、规范化相同问题、相同文档文本不得跨 split | 相同 URL（忽略 fragment）或快照哈希也不得跨 split |
| 快照 | 无字节文件校验 | ISO 抓取时间含时区；本地文件存在且 SHA-256 一致；路径限制在快照根目录内 |

`doc_id` 和 `sid` 限 ASCII 字母、数字、下划线、连字符。`paragraph` 是非空字符串，确保条件段落边界可追溯。句子顺序、原文文本和来源元数据决定模型输入。

通用样本见 [experiment README](README.md)。真实网页文档在其基础上至少增加：

```json
{
  "source": "https://example.org/policy",
  "snapshot": "2026-10-10T12:00:00+08:00",
  "snapshot_path": "policy/raw.html",
  "content_sha256": "REPLACE_WITH_64_LOWERCASE_HEX_SHA256"
}
```

这段只是字段说明，不是通过验收的真实来源。`snapshot` 表示抓取时间，不是政策生效日期；内容中声明的 `effective_from`、`published_at`、更新时间及来源许可建议单列，缺失则记未知。SHA-256 对应保存快照文件的**原始字节**；HTML 到句子的提取程序、版本和行/段映射另行归档。验证器不证明提取忠实性。

## 首批约 150 题的人工交接

以事件/文档家族建 cluster，先分配开发与锁定测试范围，再制作问题和变体。涉及同一页面不同时间版本、镜像、改写的样本保持同簇同 split；当前自动检查不能完整识别这些近重复。跨站相似文本需另做去重审查。

每题保留：原始快照、提取文本、问题、短答案与允许别名、拒答标签、一个或多个充分证据集合，以及条件依赖关系。两位标注员独立复核；保存分歧、裁决人、时间和版本。不能由生成问题的同一模型独自认证答案。

覆盖时间条件、资格对象、例外、跨段/跨页引用、无依赖对照和原始不可回答情形；具体配额在看到开发数据后预先记录，不为某方法输赢挑题。150 题是试验建议，并不保证统计功效。

建议随数据保存一份数据卡：

| 字段 | 当前应填写 |
|---|---|
| 收集范围与日期 | 真实领域、来源筛选规则、抓取窗口 |
| 使用与发布范围 | 逐来源许可/条款依据及允许发布的内容 |
| 标注流程 | 标注员人数、独立性、培训与裁决规则 |
| 规模与簇 | 各 split 的问题数、簇数、来源域、类型分布 |
| 去重与泄漏检查 | 自动命令输出和人工近重复审查记录 |
| 限制 | 语言/领域偏差、冲突、无法判断的来源、可能的数据污染 |
| 冻结身份 | 数据文件 SHA-256、快照清单、提取程序版本、冻结日期 |

只有完成这些记录并核对内容后，才将候选数据用于论文结论。基本结构检查输出的 `STRUCTURE_VALID_NOT_SEMANTICALLY_CERTIFIED` 不应改写成“数据质量已认证”。
