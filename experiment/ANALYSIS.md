# 成对分析与分簇 bootstrap

[项目首页](../README.md) · [实验手册](../EXPERIMENT_PLAYBOOK.md)

`analyze.py` 读取 `prototype.py evaluate` 的 scores.jsonl，不调用模型、不生成预测，也不验证记录是否真的来自模型。人工软件测试记录不可用于报告模型成绩。

## 输入

每份文件仅对应同一数据/split、答案模型、提示/生成配置及生成重复。保留候选和基线在目标预算的全部题，以及 full/budget=0 参照。三组 sample_id 集合与 cluster_id 必须一致。缺失预测在上游是 missing=1、valid=0、得分=0 的记录，必须保留。

拒绝重复请求、同 method/budget 重复 sample、非 0/1 分数、联合分数高于答案分数、缺失却成功等状态。文件不能自证模型/tokenizer 版本，需运行配置和原始日志。

## 运行

```bash
python experiment/analyze.py --scores work/evaluation/scores.jsonl --candidate closure --baseline bm25 --budget 128 --resamples 10000 --seed 2026 --out work/analysis_001
```

128 是默认软件样例预算，正式实验按目标 tokenizer 主预算设置。只有真实预测已评分后才能用其结果形成研究结论。

输出 paired_analysis.json 和 paired_analysis.md，含输入分数及分析代码 SHA-256；使用新目录，同名报告存在则拒绝覆盖。

## 定义

每题二元分数平均乘 100；候选减基线的单位是 percentage points，不是相对提升百分比。

每次从 K 个独立文档/事件簇中有放回抽 K 次，保留簇内所有问题和变体。簇重复被抽中，其成员也重复计入。最终差值按问题加权，分母是此次抽中的问题数，**不是等权平均各簇分数**。

95% 区间为差值分布的 2.5% 和 97.5% 线性插值分位数。这是 percentile cluster bootstrap，不是 p 值、BCa 或多重比较校正。候选与基线共享同一次簇抽样。

少于两个簇时不输出区间；少于 20 簇提示可能不稳定。20 是诊断提醒，不是普适充分性标准；多抽几万次不能弥补独立样本不足。

## Damage / Rescue

按答案 EM 计算 full 与 candidate 的四格转移。漏回/坏格式为失败。Damage 分母为 full 正确数；Rescue 分母为 full 错误数。零分母返回 JSON null、Markdown undefined。当前只输出这两个比例的点估计与计数，没有其置信区间。

## 限制

- 指标为 answer_em 和 joint_exact_evidence；后者仅是严格引用集合代理。
- 区间反映数据簇采样变化，不包含生成随机性、标注分歧或来源选择偏差。
- 多模型与多种子不合并成独立题目。
- 不计算语义支撑、CER 汇总、官方 LongBench 指标、费用/延迟或多重性校正。
- 测试集选预算、阈值或对照造成的偏差，不能靠置信区间修复。

6 项新增统计测试用人工分数夹具检查差值、簇重采样、确定性、缺失分母、坏数据拒绝及零分母，不产生论文模型成绩。
