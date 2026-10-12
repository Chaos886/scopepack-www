# 实验结果记录模板

> **TEMPLATE · 尚无实测结果。** 复制到具体运行归档后填写。占位内容、软件样例或预期效果不能作为论文证据。

## 运行身份

| 字段 | 待填写 |
|---|---|
| run_id / code commit | pending |
| 数据版本 / split / 数据哈希 | pending |
| 答案模型精确版本 / 生成重复 | pending |
| tokenizer / chat template / prompt | pending |
| 问题数 / 独立来源簇数 | pending |
| 原始上下文长度分布 | pending |
| 主预算 / 主对照 / 主指标 | pending |
| 预先确定分析的记录位置 | pending |
| 原始请求、响应及失败日志 | pending |

## 主结果

| Method | Actual tokens | Answer | Semantic joint | Exact-evidence proxy | CER | Missing % | Total latency | Total cost |
|---|---|---|---|---|---|---|---|---|
| Full context | pending | pending | pending | pending | pending | pending | pending | pending |
| Same-score selection | pending | pending | pending | pending | pending | pending | pending | pending |
| Neighbor expansion | pending | pending | pending | pending | pending | pending | pending | pending |
| Provence | pending | pending | pending | pending | pending | pending | pending | pending |
| ScopePack / predicted edges | pending | pending | pending | pending | pending | pending | pending | pending |
| ScopePack / oracle edges | pending | pending | pending | pending | pending | pending | pending | pending |

Full 是额外参照，不是同预算对手。Oracle 仅诊断，不是可部署方法或严格上界。写清指标定义，exact-evidence proxy 不等于语义支撑率；抽象压缩的 CER 需另行审查。

## 主比较与不确定性

- 候选 − 基线差值（percentage points）：pending
- 95% 成对分簇 bootstrap 区间：pending
- 簇数 / 重采样次数 / seed：pending
- 生成重复的独立波动：pending
- 多重比较政策与探索性标记：pending

区间不跨 0 不自动意味着实用价值或机制成立；须报告效果尺度与成本。

## 完整 → 压缩上下文

| | Compressed correct | Compressed wrong |
|---|---|---|
| Full correct | pending | pending |
| Full wrong | pending | pending |

Damage = 正确→错误 / Full 正确数；Rescue = 错误→正确 / Full 错误数。零分母记 undefined。漏回和格式失败不得从总数删除。

## 成本

- 依赖预测 / 选择 / 生成耗时：pending
- 首 token 和总延迟 / batch / 并发：pending
- GPU/显存/精度或 API 计价版本：pending
- 预测、摘要、judge 与重试的总费用：pending
- 冷/暖缓存、摊销工作与复用次数：pending

## 案例审查

| Case ID | Type | Original evidence | Retained spans | Raw answer | Adjudication | Error cause |
|---|---|---|---|---|---|---|
| pending | success / failure | pending | pending | pending | pending | pending |

至少包含失败，覆盖过大闭包、漏边、证据充分但生成失败；人工变体与自然网页分开报告。

## 受控演绎补充（独立报告，不与自然网页混合）

| Method / budget | 全部题数 | 三标签准确率 | 证明保留率 | 证明完整条件下准确率 | 充分引用且答对 | 三个配对世界全对 |
|---|---|---|---|---|---|---|
| pending | pending | pending | pending | pending | pending | pending |

- 每个比例的分母、原始未知题数与格式/运行错误数：pending
- 深度 0 对照与 1–4 步结果、标签混淆矩阵：pending
- 独立模板/题族数、未完整安排的配对三元组：pending
- 证明丢失但猜对、证明完整仍失败的人工归因：pending

当前 60 道合成开发题无真实 LLM 成绩。证明支持只适用于规定的形式片段；条件准确率不能用于不同方法的直接因果比较。新增诊断见 [说明](experiment/DEDUCTION.md)。

## 结论约束

- 本次直接支持的结论：pending
- 强基线或邻句是否足以解释收益：pending
- 未见来源是否保持效果：pending
- 仍不能声称什么：pending
- 继续扩大 / 修改假设 / 停止，以及依据：pending
