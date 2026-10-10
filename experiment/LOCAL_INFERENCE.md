# 本地模型：从请求到可评分输出

[项目首页](../README.md) · [数据验收](DATA_VALIDATION.md) · [实验手册](../EXPERIMENT_PLAYBOOK.md)

`run_local.py` 已实现本地 Hugging Face 因果语言模型适配器，以及可独立测试的执行、记录和恢复流程。**当前只通过软件测试，尚未用真实模型权重联调。** 此环境没有 `torch`、`transformers` 或已配置模型；不要把“代码已实现”理解成“真实实验已通过”。

## 1. 适用范围与环境

- Python 3.10+；本地安装与硬件匹配的 PyTorch、Transformers、safetensors，以及所选 tokenizer 的依赖。先用模型官方支持的版本建立独立环境，联调通过后冻结依赖版本。当前仓库不声称验证过某个推理依赖组合。
- 已下载的 decoder-only instruct/chat 模型与 tokenizer，必须有聊天模板和 safetensors 权重。记录上游精确 revision。路径不存在会报错，不自动下载、不调用外部 API。
- CPU 使用 `float32`；单张 CUDA GPU 可选择 `float32`、`float16` 或 `bfloat16`。显存/内存需求由具体模型决定；尚未测量。
- 暂不支持量化、多卡、vLLM、Ollama、付费 API、自定义远程代码或 reasoning 模式开关。聊天模板若不接受 system 消息会显式失败，不暗中改写提示。

适配器使用 `local_files_only=True`、`trust_remote_code=False`、`use_safetensors=True`。加载权重前逐条处理聊天模板，检查**完整输入 tokens + 最大输出预留 ≤ 配置窗口**；超过窗口则保留失败行，不截断全文参照或压缩上下文。配置窗口还不能大于模型/tokenizer 声明的有限上限；特殊 RoPE 扩展模型须另做适配核验。

## 2. 填写可执行配置

复制 [local_config.template.json](local_config.template.json) 到仓库 `work/local-config.json`，填入以下三个必填项：

| 项 | 填什么 |
|---|---|
| `model_path` | 已存在的模型目录，例如 `D:/models/your-instruct-model` |
| `tokenizer_path` | 与 prepare 使用的 tokenizer 相同的本地目录 |
| `model_revision` | 上游权重的精确 commit/revision；另对本地实际文件计算哈希 |

其他项：`device`、`dtype`、`max_context_tokens`、`max_new_tokens`、`seed`。相对路径以**配置文件所在目录**为基准。4096/256 是待核对的模板值，不能假设适合所有模型。模板中的 `null` 会被拒绝。

此配置会被运行器读取；根目录 `EXPERIMENT_CONFIG.template.json` 仍是研究记录表，二者用途不同。模型路径、实际日志和回复保存在被忽略的 `work/`，无需上传整个模型目录。

解码固定为单请求、greedy、`do_sample=False`、`num_beams=1`、无自动重试。只继承权重配置的 EOS 等特殊 token，不继承隐藏的采样/惩罚/强制输出设置。固定种子不保证跨设备逐字节确定性；实际版本、参数和 GPU 名称会记录。

## 3. 准备 → 预检 → 首次生成

以下命令都从**仓库根目录**执行。先将路径换成你实际使用的本地 tokenizer。

```bash
python experiment/validate_data.py --data experiment/demo.jsonl

python experiment/prototype.py prepare --data experiment/demo.jsonl --out work/prepared_demo_tokens --tokenizer D:/models/your-instruct-model

# 仅预检，不加载模型权重，不生成答案
python experiment/run_local.py --config work/local-config.json --data experiment/demo.jsonl --requests work/prepared_demo_tokens/requests.jsonl --out work/preflight_001 --max-requests 10 --preflight

# 第一次真实联调，只执行文件中的前 10 条请求
python experiment/run_local.py --config work/local-config.json --data experiment/demo.jsonl --requests work/prepared_demo_tokens/requests.jsonl --out work/smoke_001 --max-requests 10

python experiment/prototype.py evaluate --data experiment/demo.jsonl --requests work/smoke_001/requests.jsonl --predictions work/smoke_001/predictions.jsonl --out work/smoke_001/evaluation
```

`--max-requests` 默认 10，是前 N 条请求，不是 N 道问题。运行器把这个子集另存为 `work/smoke_001/requests.jsonl`，**评分必须使用这个文件**。其余预备请求未计划执行，不应误计为本次漏回。10 条通常不是完整配对矩阵，不要对其直接运行成对统计。

预检仍需安装 tokenizer 依赖、读取模型配置及对权重文件计算哈希，可能产生明显磁盘 I/O；“不加载权重”指不构造模型/占用权重显存。预检目录和生成目录分别建立，不复用。

若只想检查历史 `experiment/demo_run/requests.jsonl` 的连接流程，可显式添加 `--allow-fixture-units`。该开关只接受明确标为软件夹具的数据，完整模型窗口仍按真实 tokenizer 检查。此模式不能提供 token 压缩效率结论。正常实验必须重新 prepare，使用目标 tokenizer。

## 4. 输出与失败口径

```text
work/smoke_001/
├── run_manifest.json       run_id、实际配置、资产/代码/输入哈希、环境和状态
├── requests.jsonl          本次计划执行的完整请求子集
├── preflight.jsonl         模板后输入 tokens、token ID 哈希和窗口判断
├── journal.jsonl           先记开始，再追加结果；每条刷新到磁盘
└── predictions.jsonl       每个计划请求一行，含原始文本和可评分 output
```

每条预测包含 `run_id`、`request_sha256`、状态、原始解码文本、结构化 `output`；实际生成还记录生成 token IDs、输入/输出 token 数、完成原因及生成耗时。原始 token IDs 保留特殊 token，`raw_text` 解码时去除特殊 token。输出 token 计数包含实际生成的终止 token。

只接受单个完整 JSON 对象 `{answer, citations, abstain}`；不剥代码围栏、不从解释或思考中抽取 JSON、不修复答案。格式失败保存 `output:null` 和原始文本。引用是否可见、是否支持答案由评分/人工审核另行处理；`completed` 仅表示结构化输出可解析，不表示答对。

| 状态 | 处理 |
|---|---|
| `completed` | 保留原始回复并进入评分 |
| `invalid_output` | 保留原始回复，output 为 null，计零 |
| `context_overflow` / `template_error` | 不生成，仍保留本次计划请求，计零 |
| `backend_load_error` / `generation_error` | 保存异常，计零，不自动重试 |
| `interrupted_not_retried` | 上次已开始但没有可靠结果，不重复调用，计零 |

运行完成但含以上失败时标为 `FINISHED_WITH_FAILURES`。查看 manifest 的各状态计数，不能只看进程正常退出。已保存的失败行在评分中 `missing=0`，但答案/联合分数为 0；`missing` 专指根本没有预测记录。失败率须结合 manifest 报告。

`generation_ms` 只测生成及设备同步，不含权重加载、tokenizer、资产哈希、压缩和文件写入；模型加载耗时单列。不能用它声称端到端加速，也不等于云服务账单。

## 5. 恢复与可追溯性

新运行拒绝覆盖已有目录。相同参数追加 `--resume` 可恢复**生成目录**：

```bash
python experiment/run_local.py --config work/local-config.json --data experiment/demo.jsonl --requests work/prepared_demo_tokens/requests.jsonl --out work/smoke_001 --max-requests 10 --resume
```

已完成或失败的请求不会再次生成；只执行尚未开始的请求。中断前已记 started、但未记结果的请求直接保留为 `interrupted_not_retried`。若需要重新尝试失败，建立**新的运行目录与 run_id**，保留首次失败，不能挑选成功重试混入原成绩。

模型/tokenizer 文件、代码、数据、请求、配置或环境指纹改变时拒绝恢复。`journal.jsonl` 是恢复依据；损坏或半写入 JSON 行会使恢复停止，保留原文件人工审查，不静默丢行。异常断电可能遗留 `.running.lock`：只有确认旧进程已停止后，手动移除该锁文件再恢复；不删除日志或结果。

请求 ID 仍不是全局唯一实验身份。归档 `run_id + request_id + request_sha256` 及整个 manifest。新运行器的预测在评分时会校验请求哈希；旧式外部预测仍可导入，但没有这个额外绑定保证。

## 6. 从联调到论文实验

1. 人工查看首轮原始回复，确认模板、EOS、JSON 输出和引用符合选定模型；再冻结依赖版本。
2. 按 [数据验收规范](DATA_VALIDATION.md) 准备真实网页与独立标注。软件样例只做联调。
3. 按预先记录的样本数和方法矩阵显式提高 `--max-requests`，检查 saved request_count 与预期一致。正式统计需完整的 full/bm25/closure 等配对组。
4. 运行评分和成对分析，再加入强基线、语义引用审查、成本统计及失败案例。真实模型表现和方法优势目前仍为待验证。

实现依据：[Transformers 生成教程](https://huggingface.co/docs/transformers/main/en/llm_tutorial)、[聊天模板文档](https://huggingface.co/docs/transformers/main/en/chat_templating)。查阅日期：2026-10-10；实际兼容性仍需在所选模型环境联调。
