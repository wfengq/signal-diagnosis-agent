# Signal Diagnosis Agent

> 英文原件为 [README.md](README.md)，以英文版为准。

一个只回答一个窄问题、并为答案给出证据的 LLM agent：**“这个周期信号为什么听起来失真？”**

给它一个 WAV 文件，也可以附一句自然语言描述。它会决定要做哪些测量，用确定性 DSP 执行测量，再按版本化规则判断，最后给出诊断：削波、谐波失真、两者兼有、没有可支持的故障，或不确定。诊断里的每条结论都引用了支撑它的测量结果。

- **LLM 只做规划，从不自己计算数值。** 所有数值都来自确定性 DSP，所有阈值都来自版本化的规则 profile。原始波形和完整 FFT 数组永远不会发给模型。
- **结论受证据把关。** 结论必须引用同一次运行（same-run）的证据和规则判定，否则运行时直接拒绝。证据不足以下结论时，答案就是“不确定”（`inconclusive`）。
- **效果是和对照组正面比出来的。** 下面每一项行为结论都来自预先登记的评测，留出集只跑一次；没达标的结果和达标的结果一起留在仓库里。

> 这是一个可演示的垂直切片，不是生产级音频质检、芯片验证或标准符合性产品。规则阈值（削波 1%、THD 5%）是演示设置，不是行业标准。

## 结果一览

| 评测 | 测的是什么 | 结果 |
|---|---|---|
| **V0.2 官方留出集**（已验收的产品：commit `b48790c`，prompt `v0.2-s1-planner-8.1`） | 80 次留出集 agent 运行，样例为合成的 S1 信号 | 结论正确 **79/80**；因果 macro F1 1.0；证据引用率 1.0；无依据结论率 0.0 |
| **Agent 增量研究**（2026-10-06；研究用 prompt `v0.3-s1-planner-9.15` / `v0.3-s1-intake-1.1`，不是产品默认） | 每个任务族 24 个留出样例上，agent 比最强固定流程多做对几例 | **T1 自由文本接诊：+5**（22 比 17），达到可测增量。**T2 局部故障：0**（18 比 18），但工具调用 **96 次对 824 次**。agent 在 48 例里**没有一次**无依据的故障结论。 |
| **V0.3 情境验证** | 在外部 WAV 上提供参考文件或声明标称单音时的诊断 | 见[验收报告](docs/evaluations/v0_3/contextual/V9_11_CONTEXTUAL_VALIDATION_ACCEPTANCE_REPORT.md) |

每个数字只属于它所在行写明的版本，彼此不能互相替代：79/80 只属于 V0.2 产品版本；agent 增量研究的数字来自研究用 prompt，产品默认并不运行这些 prompt。完整报告：

- [Agent 增量研究结果报告](docs/evaluations/v0_3/agent_increment/STUDY_S1_AGENT_INCREMENT_1_REPORT.md)：结论、各组明细、限定这些数字的条件，以及开发集五轮迭代的过程。
- [工程案例](docs/PROJECT_CASE_STUDY.zh-CN.md)：项目中遇到的难点、纠错和关键决策。

## 为什么这些数字可信

- **严格区分开发集和留出集。** 开发集用来迭代。跑留出集之前先冻结 prompt 并记录哈希，留出集只跑一次。
- **对照组是能做到的最强固定流程。** T1 用正则规则解析描述，T2 用逐段穷举扫描。“固定流程已经够用”也被认可为有效结论。
- **失败结果不删。** 第一次官方运行（`below_target`）、开发阶段没达标的几轮，以及 agent 增量研究中有缺陷的几轮，都和验收通过的结果一起保留在仓库里。每一次纠正都记录在 [DECISIONS.md](docs/DECISIONS.md)。
- **不会悄悄降级。** 产品路径用的是真实 LLM 的 planner。脚本化 planner 只用于测试，缺少凭证时也不会拿它顶替。

## 快速上手

需要 Python 3.11 或 3.12，以及放在环境变量里的 DeepSeek API key。切勿把密钥提交进仓库。

```text
python -m pip install ".[app,llm]"
set DEEPSEEK_API_KEY=<your-key>        # macOS/Linux 用 export
signal-diag serve --host 127.0.0.1 --port 8765
```

打开 `http://127.0.0.1:8765`。健康检查、预设样例和静态页面不需要凭证就能加载。没有凭证时提交诊断，会返回配置错误，不会给出脚本化的答案。

**这是一个本地、单用户、没有鉴权的服务，切勿暴露到不可信的网络。**

命令行用法：

```text
signal-diag presets
signal-diag diagnose synthetic clipping
signal-diag diagnose wav path/to/file.wav --channel mixdown --output json --html-output report.html
signal-diag intake diagnose --text "新功放放 1 kHz 测试音，听着发毛" --test-file new.wav --file old.wav
```

退出码 0 表示 agent 正常给出了结果，包括“不确定”和“没有可支持的故障”。退出码 1 表示 agent、运行时或应用出错。退出码 2 表示用法、输入或配置有误。

### 默认路径会下什么结论、不会下什么结论

网页打开后首先是“描述问题”：写下你听到的情况，选一到两个 WAV 文件，逐项确认模型起草的上下文，然后诊断。界面是中文，关键英文术语并列保留；手动表单和示例信号收在“高级”区域里。命令行的 `intake diagnose` 会逐项询问保留、修改或跳过；脚本里用 `--yes` 或直接写字段参数（`--mode`、`--reference`、`--nominal-fundamental-hz`、`--stimulus-kind`）。

默认只处理单个文件，结论偏保守：可以确认削波，但在缺少上下文时不会把丰富的谐波说成“新增的失真”。如果能提供干净的参考 WAV，或声明单音的标称频率，就可以进一步认定谐波失真。这一步是可选的，并不假定每个用户都有未失真的原始录音。

自由文本接诊只负责起草这些上下文：模型只看到你的文字和文件名，看不到音频。起草的字段要经你确认才会使用；某个模式需要的字段没有全部确认时，按单文件诊断并说明原因。标称频率只来自你的文字或输入，绝不来自测量。上下文来自已确认草稿时，报告里会注明。

## 架构

```text
signal -> dsp -> tools -> rules/knowledge -> agent -> evaluation -> app
```

```text
CLI / Web UI / API
        |
DiagnosisApplicationService
        |
DistortionDiagnosisRuntime <-> RealLLMPlanner
        |
SignalToolService -> deterministic DSP -> Evidence
        |
RuleEngine / KnowledgeIndex
        |
StructuredDiagnosis -> JSON / HTML / UI
```

依赖方向由架构测试强制保证：`signal`、`dsp`、`tools`、`rules` 和 `knowledge` 都不依赖 agent 或任何 LLM 框架。

读代码时，建议顺着一次请求从上往下走：

1. `src/signal_diag/app/cli.py` 和 `app/composition.py`：程序入口与依赖组装。
2. `app/service.py`：从一个 WAV 或预设请求，到一次 agent 运行。
3. `agent/models.py`、`agent/planner.py` 和 `agent/runtime.py`：决策、模型边界、状态机、各项上限与终止条件。
4. 从 `tools/service.py` 进入 `dsp/clipping.py` 或 `dsp/harmonics.py`：确定性计算如何变成证据。
5. `rules/engine.py` 和 `knowledge/index.py`：按配置的规则判定，以及确定性的知识检索。
6. `evaluation/`：评测批次、计分，以及 agent 增量研究的运行框架。
7. `tests/agent/test_s1_acceptance.py` 和 `tests/test_architecture_boundaries.py`：端到端契约测试与依赖方向测试。

## 局限

- **范围：** 只做 S1 失真诊断，不是通用的音频或硬件测试平台。
- **输入：** 支持合成样例和有限制的整数 PCM WAV。任意的实际采集录音还没有经过验证。
- **基频估计：** 用的是自相关基线方法，不是通用的音高跟踪器。在 8 kHz 采样率下可能锁到次谐波上，agent 增量研究报告里写明了这带来的影响。
- **部署：** 只能本地运行。没有鉴权、数据库、Docker、向量检索，也没有多 agent 运行时。
- **已披露的未达标项：**
  - 已验收的官方运行里，80 次中有 2 次带行为问题标记，其中 1 次结论错误。
  - agent 增量研究每个任务族只有 24 个留出样例，只跑了一次，只用了一个模型。

## 版本说明

- **已验收的 V0.2 产品：** commit `b48790c`，prompt `v0.2-s1-planner-8.1`。上面的 79/80 和保留的 [Phase 5 演示](docs/demo/phase5/v0_2_acceptance/README.md)都属于这个版本。要重现那次演示，请检出 `b48790c`（有 tag 时也可以用 `v0.2.0`）。
- **当前默认分支：** 产品以情境模式运行附加的 V0.3 planner `v0.3-s1-planner-9.11`，它的报告没有经过 V0.2 评测认证。包元数据里的版本号仍是 `0.2.0`，这是为了保留 tag 和 wheel 的历史。
- **自由文本接诊：** 产品使用接诊 prompt `v0.3-s1-intake-1.1`（即增量研究里评测过的那一版），诊断仍用产品 planner `v0.3-s1-planner-9.11`。
- **Agent 增量研究用的 planner**（`v0.3-s1-planner-9.15`）：在研究里评测过，但不是产品默认。

## 输入与安装细节

WAV 输入限制：

- 小端 RIFF/WAVE，整数 PCM，或 subtype 为 PCM 的 extensible PCM。
- 8/16/24/32 位，单声道或立体声，采样率 8 kHz 到 192 kHz。
- 最大 20 MiB、2,000,000 帧、30 秒。
- 按满量程精确转换为 `float32`，不对单个信号做峰值归一化。
- 不支持 RIFX、RF64、IEEE 浮点、压缩格式，以及两个以上声道。

开发环境安装：`python -m pip install ".[app,llm,dev]"`。核心的 DSP/规则/知识/agent 只需 `pip install .`，不会引入 FastAPI。必跑测试从不调用真实模型。CI 在 Python 3.11 和 3.12 上运行全部测试。

## 文档

从[文档导航](docs/README.md)开始阅读。它提供简短的评审阅读路线、权威文档清单和全部评测的索引。

- [架构](docs/ARCHITECTURE_V0_2.md)
- [V0.2 冻结契约](docs/CONTRACTS_V0_2.md)
- [V0.3 情境契约](docs/CONTRACTS_V0_3_CONTEXTUAL.md)
- [设计决策](docs/DECISIONS.md)
- [工程案例](docs/PROJECT_CASE_STUDY.zh-CN.md)
