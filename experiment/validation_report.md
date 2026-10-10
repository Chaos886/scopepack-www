# 软件验证记录

日期：2026-10-10。以下为实际执行记录，不是模型实验结果。

## 本地执行与数据验收更新

仓库根目录运行 `python -m unittest discover -s experiment -p "test_*.py" -v`：**27 tests，OK，退出码 0**。本轮新增 9 项运行器检查与 5 项数据验收检查，保留此前 13 项检查。

- 运行器：严格 JSON、不修复输出；预检不生成；输入加输出预算的边界；坏输出/生成错误/加载失败仍保留；恢复不重复生成；中断请求计失败；防覆盖与锁；公开输入/预算校验；评分的请求哈希绑定。
- 数据：8 个样例的基本结构；软件样例不能冒充 web profile；异常文档/证据 ID/可回答性；簇/相同问题/相同文本跨 split；快照字节、时区与路径范围；重复 JSON 键和非有限数值拒绝。

运行器测试使用明确标为 `FAKE_SOFTWARE_TEST_NOT_MODEL_INFERENCE` 的假后端。快照检查测试使用 example.org 形式的虚构元数据与本地人工 HTML；没有抓取这些页面，也不代表真实网页数据验收。

**未验证：真实 Hugging Face 权重加载、GPU 推理、模型特定聊天模板/EOS、推理依赖版本组合。** 当前未安装 torch/transformers，没有真实模型输出、硬件性能或方法收益结果。

## 先前统计工具更新

仓库根目录运行 `python -m unittest discover -s experiment -p "test_*.py" -v`：13 tests，OK，退出码 0。包括下述 7 项原型检查与新增 6 项统计检查。

统计检查覆盖已知成对差值/转移计数、整簇重采样及固定种子、缺失分母、未配对/重复/簇不匹配拒绝、零分母/单簇、矛盾分数拒绝。使用人工夹具，未生成模型成绩。

`analyze.py` 已支持 JSON/Markdown 报告、差值区间、Damage/Rescue 点估计及输入/代码哈希。区间不含模型生成随机性、标注误差或多重比较校正。

## 初始原型检查

`python -m unittest -v test_prototype.py`：7 tests，OK，退出码 0。

| 检查 | 结果 |
|---|---|
| 循环及传递依赖闭包 | 通过 |
| 8 样例 × 4 方法 × 6 预算的渲染预算与闭包可行性 | 通过 |
| 修改 gold/task_type 不改变 public input 和选择 | 通过 |
| 错误引用不计联合成功、不可见引用无效 | 通过 |
| 正确拒答、坏 schema、空预测处理 | 通过 |
| 漏回预测不从分母删除 | 通过 |
| 重复 prediction ID 拒绝评分 | 通过 |

`prototype.py prepare`：实际生成 112 条请求，8 个人工构造样例。

`demo_run/manifest.json`：`PREPARED_NOT_EXECUTED`，计数单位 `regex_units_NOT_LLM_TOKENS`，未使用模型 tokenizer。

没有调用 LLM，没有生成真实 predictions、模型准确率、正式效率统计或置信区间。单元测试中的空预测/坏预测仅验证程序行为，不计入任何科研成绩。

早期两个测试曾因 Windows 环境的临时目录权限失败；改用普通工作区测试目录后全部通过。测试目录在 `work/unit-tests/`，不属于交付的研究数据。

独立 LaTeX 编译调用未成功：编辑器编译器报告 `Unable to find standard directories for platform`。未生成或验证可交付 PDF；源码和 Markdown 稿均保留。源文件后续的等价公式排版微调未重新获得成功编译验证。
