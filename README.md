<div align="center">

<img src="scopepack-banner.svg" width="100%" alt="ScopePack — Preserve the conditions. Pack the evidence. Dependency-closed context compression research." />

**面向网页问答的适用条件与证据依赖保留压缩**

*Preserving Applicability under Context Budgets: Dependency-Closed Compression for Web Question Answering*

[论文初稿](www_draft.md) · [研究方案](研究与实验方案.md) · [开始实验](EXPERIMENT_PLAYBOOK.md) · [演绎评测](experiment/DEDUCTION.md) · [路线图](ROADMAP.md) · [结果模板](RESULTS_TEMPLATE.md)

</div>

---

> [!IMPORTANT]
> **研究工作稿，真实模型结果待完成。** 当前交付了方法设计、离线原型、本地推理运行器与统计工具；没有声称优于现有方法。默认样例使用正则计数单元，不能用于模型 token 效率结论。

<table>
<tr><th align="center">验证</th><th align="center">样例</th><th align="center">评测</th><th align="center">阶段</th></tr>
<tr>
<td align="center"><b>46</b><br/>本地测试通过</td>
<td align="center"><b>8 + 60</b><br/>两类软件样例</td>
<td align="center"><b>2</b><br/>问答与演绎</td>
<td align="center"><b>准备阶段</b><br/>未运行模型</td>
</tr>
</table>

## 01 · 为什么要保留“适用条件”

网页上的结论往往不是无条件成立的。价格可能只适用于新用户，退款可能排除经销商订单，政策可能在某一天之后才生效。压缩若留下结论、删掉条件，就可能改变证据的含义。

| 原始材料 | 只保留相关句时的风险 | ScopePack 的处理目标 |
|---|---|---|
| “十四天内可退款。”<br/>“仅限直接购买，不含经销商订单。” | 问经销商订单时，只看到第一句可能得出相反答案。 | 将结论及其必要条件作为依赖闭包，共同计入预算。 |

*这是解释机制的虚构例子，不是已测得的真实模型失败案例。*

**核心研究问题：** 固定检索结果、相关性分数、答案模型和上下文预算后，显式依赖约束能否提供超出强上下文剪枝与邻句扩展的收益？

## 02 · 从网页证据到可核对的答案

```mermaid
flowchart TB
    subgraph PACK["01 · 证据选择 / 已实现"]
      direction LR
      A["问题与快照<br/>句子 + 来源 ID"] --> B["分数 + 依赖<br/>闭包预算选择"] --> C["压缩原文<br/>保留来源"]
    end
    subgraph EVAL["02 · 生成与评估"]
      direction LR
      D["本地模型<br/>适配器待实测"] -.-> E["答案与引用<br/>导入评分"] --> F["成对比较<br/>分簇统计"]
    end
    PACK --> EVAL
    classDef input fill:#edf4ff,stroke:#7aa0d2,color:#173354
    classDef method fill:#e4f7f1,stroke:#42a88a,color:#135d4b
    classDef pending fill:#fff5dd,stroke:#d5a64c,color:#70521c
    class A input
    class B,C,E,F method
    class D pending
```

| 已实现 | 还需验证 / 开发 |
|---|---|
| BM25 分数、英文规则依赖、闭包选择、来源保留 | 学习型依赖预测、真实网页解析和跨页指代 |
| full / none / head / bm25 / neighbors / closure | Provence、LongLLMLingua、LLMLingua-2 等强基线 |
| 本地 HF 运行器、窗口预检、原始输出与恢复 | 真实权重联调、模型兼容性、官方 benchmark 指标 |
| 受控演绎题、符号证明核验、压缩后证明保留诊断 | 真实 LLM 演绎表现、未见推理模板、自然网页有效性 |
| 输出保护、评分来源清单、运行身份与矩阵检查 | 实际推理与外部成绩的真实性核验 |
| 数据结构、快照哈希及切分重叠检查 | 真实网页采集、独立标注与近重复审查 |
| 成对差值、cluster bootstrap、Damage / Rescue | 语义引用审查、实际费用与端到端性能 |

> [!NOTE]
> 闭包可行性不等于语义充分性。当前图由规则预测；错误依赖可能遗漏条件或浪费预算。新颖性及真实数据有效性仍需实验证据。

### 现在是否测到了演绎能力？

原始问答的正确答案和引用集合只能间接反映推理。新增模块明确给出事实、方向性规则和查询，用独立符号检查核验结论：**能推出 / 能推出显式否定 / 信息不足**。当前包含 60 道受控开发题，覆盖直接读取和 1–4 步合取推导。

报告区分答案准确率、必要证明是否被压缩保留、引用是否足以推出答案，以及三种配对世界是否全部答对。它评估指定规则语义下的行为，不能证明模型的内部思考过程或通用逻辑能力。**还没有真实 LLM 演绎分数。**

入口：[演绎诊断与命令](experiment/DEDUCTION.md) · [英文实验设计补充](DEDUCTION_STUDY.md)

## 03 · 两分钟运行离线流程

**环境：Python 3.10+。** 默认流程只用标准库；在仓库根目录执行：

```bash
# 检查数据结构
python experiment/validate_data.py --data experiment/demo.jsonl

# 准备上下文与模型请求，不调用模型
python experiment/prototype.py prepare --data experiment/demo.jsonl --out work/demo_run

# 核对受控演绎题的规则、文本与金标
python experiment/deduction.py inspect --data experiment/deduction_demo.jsonl

# 验证预算、金标隔离、评分、逻辑求解和统计约束
python -m unittest discover -s experiment -p "test_*.py" -v
```

重复运行请使用新的输出目录；准备和评分会拒绝覆盖已有产物。详见 [运行记录与结果保护](experiment/RUN_INTEGRITY.md)。

生成目录中，`requests.jsonl` 是模型输入，`context_diagnostics.jsonl` 是评测侧诊断，`manifest.json` 记录准备状态。**仅将 requests 中的 messages 交给答案模型。**

<details>
<summary><b>有了真实模型输出后：评分 → 成对统计</b></summary>

先按 [本地模型运行指南](experiment/LOCAL_INFERENCE.md) 填写配置、预检并生成真实回复；也可按 [接口约定](experiment/README.md) 导入其他后端输出。下面的评分与统计命令只适用于已保存完整配对预测的运行，不能在预测文件缺失时运行。

```bash
python experiment/prototype.py evaluate --data experiment/demo.jsonl --requests work/inference_001/requests.jsonl --predictions work/inference_001/predictions.jsonl --out work/evaluation

python experiment/analyze.py --scores work/evaluation/scores.jsonl --candidate closure --baseline bm25 --budget 128 --resamples 10000 --seed 2026 --out work/analysis_001
```

`128` 仅匹配默认软件样例的正则预算。正式实验须用真实数据、目标 tokenizer 和预先选择的主预算。统计输出为 `paired_analysis.json` 与 `paired_analysis.md`，不会覆盖已有同名报告。

每份 scores 只对应一个数据版本、答案模型、提示配置和生成重复；保留 full 参照及所有预定请求。工具拒绝未成对样本和重复记录，漏回仍计入分母。详情见 [统计说明](experiment/ANALYSIS.md)。

</details>

## 04 · 下一轮实验怎么推进

| 阶段 | 做什么 | 通过条件 |
|---|---|---|
| **A · 联调** | 确定模型 / tokenizer / 后端，先跑 10 条真实请求 | 无金标泄漏、无静默截断，输出与日志可追溯 |
| **B · Pilot** | 收集与独立标注约 150 题，多来源分簇 | 现象在真实数据存在，标注与配对可靠 |
| **C · 机制检验** | 同分数去边、邻句、Provence、oracle 图 | 收益不能由强基线或多留几句完全解释 |
| **D · 正式评估** | 锁定测试集，测质量、统计区间和总成本 | 包含失败案例、未见来源和端到端开销 |
| **E · 成稿** | 根据真实结果改写论文，核验 CFP 与 ACM 模板 | 贡献有证据，投稿规则和匿名要求满足 |

直接开始：[本地模型运行指南](experiment/LOCAL_INFERENCE.md) · [可执行配置](experiment/local_config.template.json) · [数据验收](experiment/DATA_VALIDATION.md)

首轮先检查模板后的总输入长度，再生成 10 条请求并评分；每条保留原始回复和失败状态。**运行器测试使用假后端验证程序行为，真实 Hugging Face 模型适配器仍待联调。**

研究记录：[实验操作手册](EXPERIMENT_PLAYBOOK.md) · [实验记录模板](EXPERIMENT_CONFIG.template.json) · [结果记录模板](RESULTS_TEMPLATE.md)

根目录的 `EXPERIMENT_CONFIG.template.json` 是实验记录表，程序不会读取；`experiment/local_config.template.json` 则由本地运行器读取。未填写项为 `null`，不能当作已完成的配置。

## 05 · 证据状态

| 检查层 | 当前证据 | 结论范围 |
|---|---|---|
| 软件层 | 46 项本地检查通过 | 支持实现约束；不是模型能力分数 |
| 输入层 | 8 个原型样例 + 60 道合成演绎开发题 | 支持离线检查和受控任务设计；不是自然 Web 数据集 |
| 模型层 | **Pending** | 尚无真实准确率、语义引用分数或质量提升 |
| 效率层 | **Pending** | 尚无真实 token 节省、推理速度或总费用 |

关键是验证：**显式依赖是否带来可归因、可重复且值得付出成本的改进。** 若邻句扩展或强剪枝足以解释收益，应缩小或修改主张。

## 06 · 文档地图

| 你想做什么 | 从这里开始 |
|---|---|
| 和导师讨论问题与方法 | [英文初稿](www_draft.md) · [中文研究方案](研究与实验方案.md) |
| 修改论文排版与公式 | [LaTeX 源码](www_draft.tex) |
| 排查近邻与创新边界 | [文献核对与待办](文献核对与待办.md) |
| 收集数据、标注并联调模型 | [实验操作手册](EXPERIMENT_PLAYBOOK.md) |
| 接入本地模型并恢复运行 | [本地模型运行指南](experiment/LOCAL_INFERENCE.md) |
| 检查真实网页数据与切分 | [数据验收规范](experiment/DATA_VALIDATION.md) |
| 运行代码与理解数据格式 | [实验 README](experiment/README.md) |
| 核对是否覆盖演绎能力 | [演绎评测说明](experiment/DEDUCTION.md) · [英文实验补充](DEDUCTION_STUDY.md) |
| 避免覆盖或混用实验结果 | [运行记录与结果保护](experiment/RUN_INTEGRITY.md) |
| 分析实测结果 | [统计说明](experiment/ANALYSIS.md) · [结果模板](RESULTS_TEMPLATE.md) |
| 查看已做与未做的事情 | [验证记录](experiment/validation_report.md) · [路线图](ROADMAP.md) |
| 获取最初版本存档 | [初稿压缩包](WWW初稿包.zip)（不含后续更新） |

<details>
<summary><b>目录结构</b></summary>

```text
scopepack-www/
├── README.md                         项目首页
├── scopepack-banner.svg              本地矢量封面
├── www_draft.md / www_draft.tex       论文初稿
├── EXPERIMENT_PLAYBOOK.md             实验操作手册
├── EXPERIMENT_CONFIG.template.json    运行配置记录模板
├── DEDUCTION_STUDY.md                 演绎诊断的英文实验设计
├── RESULTS_TEMPLATE.md               结果与证据记录模板
├── ROADMAP.md                        阶段任务与退出条件
└── experiment/
    ├── prototype.py                  上下文选择与预测评分
    ├── deduction.py                  受控题生成、符号证明与诊断报告
    ├── deduction_demo.jsonl          60 道合成演绎开发题
    ├── DEDUCTION.md                  演绎能力测量范围与操作入口
    ├── test_deduction.py             逻辑正确性与端到端检查
    ├── analyze.py                    成对分析与分簇 bootstrap
    ├── run_local.py                  本地生成、窗口预检与运行恢复
    ├── validate_data.py              数据结构、快照与切分检查
    ├── local_config.template.json    本地运行器的可执行配置
    ├── LOCAL_INFERENCE.md            模型接入与首轮联调
    ├── DATA_VALIDATION.md            数据验收规范
    ├── RUN_INTEGRITY.md              输出保护、评分身份与成本缓存
    ├── test_artifacts.py             运行记录与矩阵约束测试
    ├── test_prototype.py             实现约束检查
    ├── test_analyze.py               统计约束检查
    ├── test_run_local.py             失败、中断恢复及请求绑定检查
    ├── test_validate_data.py         数据与切分异常检查
    ├── demo.jsonl                    软件样例
    ├── ANALYSIS.md                   统计口径说明
    └── demo_run/                     已准备但未执行的请求
```

</details>

---

<div align="center">

**Research first. Evidence before claims.**

研究工作稿 · 尚未选择开源许可证 · WWW 届次与 CFP 待核验<br/>
LaTeX 尚未成功编译验证；当前排版不是已核验的 ACM 投稿模板。

</div>
