# WWW 方法论文初稿包

更新：2026-10-10。方向已按你的选择确定为**方法论文**。

后续更新：仓库首页现位于 [README.md](README.md)，新增 [实验手册](EXPERIMENT_PLAYBOOK.md)、[运行配置模板](EXPERIMENT_CONFIG.template.json)、[结果模板](RESULTS_TEMPLATE.md) 和 [成对统计工具](experiment/ANALYSIS.md)。软件检查现为 13 项（原型 7 + 统计 6），真实模型实验仍未执行。压缩包保留最初版本，不包含这些后续更新。

工作名称：**ScopePack：面向网页问答的适用条件依赖闭包压缩**。

英文题目：*Preserving Applicability under Context Budgets: Dependency-Closed Compression for Web Question Answering*。

核心问题是：网页中“可退款”“价格为 129 元”等结论往往附带适用人群、时间和例外。压缩只留下结论，可能改变证据含义。我们提出把结论及其必要条件作为一个依赖闭包，在严格的上下文预算内共同保留。

## 已交付什么

| 文件 | 用途 |
|---|---|
| `www_draft.md` | 可直接阅读的英文论文初稿，含方法、公式、实验协议、局限和待填结果表 |
| `www_draft.tex` | 同一初稿的独立 LaTeX 源文件，后续修改以此为准 |
| `研究与实验方案.md` | 中文解释研究定位、数据标注、对照实验、统计、成本和推进顺序 |
| `文献核对与待办.md` | 已查阅的主要论文、与本方案的区别及尚未完成的查新 |
| `experiment/README.md` | 从输入数据、压缩请求到导入模型输出和计算分数的操作说明 |
| `experiment/prototype.py` | 可离线运行的选择与评分原型 |
| `experiment/test_prototype.py` | 7 项研究相关实现约束检查 |
| `experiment/demo.jsonl` | 8 个手写的软件检查样例；全部为虚构素材 |
| `experiment/demo_run/` | 已生成的 112 条待执行模型请求、上下文诊断和运行清单 |

## 当前证据边界

已经实际运行的是数据预处理、上下文选择和软件测试。13 项检查全部通过；112 条请求已经准备好，**没有发送给任何大模型**。因此目前没有模型准确率、吞吐率、真实 token 节省或相对基线提升。

原型默认按正则单元计数，不能把这些单元叫作模型 token。代码支持接入本地 Hugging Face tokenizer，但当前环境没有安装相关可选库，也没有提供模型 tokenizer。正式实验必须补齐这一项。

当前依赖识别只是英文规则：条件词绑定同段句子、显式 ID 引用和有限代词回指。学习型关系预测器、神经压缩基线、真实网页解析器和模型推理后端均尚未实现。论文明确区分了已实现原型与待验证方法。

LaTeX 源码已请求在内置编辑器打开；编译器返回 `Unable to find standard directories for platform`，这是环境层面的失败，**不能确认编译成功，也没有交付已验证 PDF**。Markdown 稿可直接阅读。当前排版是工作稿，不是核验过的 ACM 投稿模板。

## 建议如何使用

先读中文方案的“主张与停止条件”，确认导师认同这个问题值得做；再讨论英文初稿的 Introduction、Method 和 Evaluation。首次真实模型试验应先做 10 条数据的接口联调，再做约 150 题的真实数据 pilot，决定是否继续扩大。

最紧要的缺口是：可用模型/API 或 GPU、真实网页快照及标注、Provence 等强基线，以及目标 WWW 届次和 track。WWW 2026 已经举行；本包没有把未知的后续届次截止日期写成事实。论文目前是可继续研究与修改的初稿，尚不能直接投稿。
