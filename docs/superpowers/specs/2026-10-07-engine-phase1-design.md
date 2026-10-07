# D052 第 1 阶段：确定性诊断引擎成为产品默认（设计）

日期：2026-10-07
状态：已批准（操作员 2026-10-07，§6 四项均选 A；D053）。授权按本设计实现；不授权任何真实模型运行。
上位依据：D052、`docs/superpowers/specs/2026-10-07-route-adjustment-device-testing-design.md` §5 阶段 1、AGENTS.md、D037、D039、D047、D050、D051。

## 1. 目标

情境诊断（产品默认路径）的结论改由确定性引擎给出。同一个输入每次得到同样的结论；不需要模型凭据就能诊断；不会因为模型反复出错而没有结论（`egfxset_live_1` 中有 9/26 次 `max_planner_retries`）。

**不在本阶段：** 扫频激励（阶段 2）、LLM 解释层（阶段 3）、测试向导（阶段 4）、V0.2 旧版单文件运行路径（保持原样）。

## 2. 现状与约束（读代码所得）

- **运行时：** 产品诊断由 `DistortionDiagnosisRuntime` 驱动。它反复调用 `PlannerModel.decide()`，执行工具、规则评估、知识检索，并在 `FinishDecision` 时按因果策略 `v9_11_mode_aware_no_fault_recovery` 校验 claims（`agent/diagnosis.py`）。证据追溯、追踪事件和报告都建立在它产出的 `AgentRunResult` 上。
- **已有的固定流程：** `evaluation/contextual/baseline.py` 的 `ContextualFixedPipelineBaseline` 用与产品相同的规则门给出 claims，但输出的是评测用的 `BaselineRunResult`，报告和页面不能直接使用。
- **冻结的 V0.2 测试：**
  - T251 要求 `build_product_service` 构建 `RealLLMPlanner`（prompt v9.11）；
  - T264 要求默认 `create_app()` 的健康检查返回 `planner_configured` 和 `planner_identity`；
  - T213 要求 `agent/runtime.py` 里不写死通用工具流水线、不构造被强制的动作；
  - T282 要求安装冒烟脚本使用 `build_product_service(environ={})`。

  这些测试都不改。
- **页面：** 现在没有模型凭据时，提交按钮被禁用（`plannerHealthAllowsSubmit`）。

## 3. 做法

### 3.1 引擎：一个确定性的决策器

新模块 `src/signal_diag/agent/engine.py`，版本号 `s1-engine-1.0`。它实现现有的 `PlannerModel` 接口，在同一个 `DistortionDiagnosisRuntime` 里运行。它按模式给出固定的决策序列，只读取运行时返回的观测和证据，不调用模型：

| 模式 | 工具（整文件，D049 防护后的工具服务） | 规则 | 结论 |
|---|---|---|---|
| `single_signal` | `detect_clipping`、`analyze_harmonic_distortion` | `profile_s1_distortion` | 削波按规则门可认定；谐波只作为观测事实（D037、D039 路径 C） |
| `nominal_single_tone` | `detect_clipping`、`analyze_contextual_distortion` | 上面两个 profile | 与 `ContextualFixedPipelineBaseline` 相同的规则门 |
| `paired_reference` | 同上 | 同上 | 同上 |

最后，对每个被认定的故障类型做确定性的知识检索（按标签），再给出 `FinishDecision`。claims 只引用同一次运行中的证据和规则判定，并且必须通过运行时现有的 v9.11 因果策略校验。如果被驳回，那是引擎的缺陷，由测试拦下，不靠重试掩盖。

**为什么不另起一个结果模型：** 走同一个运行时，证据校验、因果策略、追踪事件、报告、页面、D050/D051 定位和上下文升级建议都原样复用。引擎的输出天然受到和 LLM planner 一样严格的校验。

**与 T213 的关系：** 固定序列写在 `agent/engine.py`，不写进 `agent/runtime.py`。运行时不变，T213 仍然成立。

### 3.2 服务与入口

- 新增 `build_engine_service`（`app/composition.py`）：诊断默认走引擎，同时保留按需构建 `RealLLMPlanner` 的能力（D052 2A）。自由文字理解（D047）仍然需要 DeepSeek 凭据。
- `build_product_service` 保持原样，T251 和 T282 不变。
- CLI 和 API 的默认工厂改为 `build_engine_service`。
- 情境诊断新增可选参数 `diagnosis_path`：`engine`（默认）或 `planner`。选 `planner` 但没有凭据时，按现有方式报错，不退回引擎。
- V0.2 旧版 `diagnose wav` / `submit_wav` 路径不变。

### 3.3 身份与报告

- 快照和 `ContextualDiagnosisReport` 新增可选字段 `diagnosis_identity`：
  - 引擎运行：`{kind: "deterministic_engine", engine_version, rule_profiles}`；
  - planner 运行：`{kind: "llm_planner"}` 加上原来的 planner 信息。
- `planner_identity` 的处理见 §6 决策 2。
- 健康检查新增 `diagnosis_engine` 字段（引擎版本、是否可用），T264 要求的字段不变。
- HTML 报告、CLI 文本和页面显示“诊断由确定性引擎 s1-engine-1.0 给出”。

### 3.4 页面

- 诊断提交不再受模型凭据限制，只受引擎可用性限制。
- 自由文字起草（D047）仍然需要凭据；没有凭据时，页面提示改用“高级：手动设置上下文”。

## 4. 离线验收（不调用模型）

1. **不出错：** 在以下用例上，引擎运行全部以正常结论结束，没有 `max_planner_retries`，也没有校验驳回：
   - V0.2 合成清单的全部用例；
   - V0.2 外部 WAV 研究的用例；
   - 情境研究开发集和验证集的全部用例（三种模式）；
   - 智能体增量研究 H1 的 T2 用例，以及按真值上下文运行的 T1 用例。
2. **确定性：** 同一输入重复运行，除运行编号和时间外，结论、claims、证据和判定逐字节相同。
3. **结论对照：** 在有真值的集合上统计引擎的正确数，并与已记录的 v9.11 结果并列报告。预先登记的标准：引擎在每个集合上不低于已记录的 planner 结果；低于的地方逐例说明原因，并由操作员决定是否接受。
4. **EGFxSet：** 用 `egfxset_check_1` 的工具在本地运行（不进 CI），与 `egfxset_live_1` 并列报告：引擎 26/26 有结论，对比 planner 的 17/26。
5. **页面证明：** 没有凭据时可以完成诊断；报告显示引擎身份；定位和升级建议正常。

## 5. 合同与测试

- **合同：** `CONTRACTS_V0_3_CONTEXTUAL.md` 新增 §28。
- **决策：** D053。
- **测试：** T-CX448 起，全部离线：

| ID | 内容 |
|---|---|
| T-CX448 | 引擎决策序列按模式固定，只调用 §3.1 的工具和规则，不调用模型 |
| T-CX449 | §4.1 各集合全部正常结束，零校验驳回 |
| T-CX450 | 确定性：重复运行结果相同 |
| T-CX451 | D037：单文件模式从不认定谐波失真 |
| T-CX452 | 结论对照报告的生成与预先登记的标准 |
| T-CX453 | `build_engine_service` 默认走引擎，`diagnosis_path=planner` 走 `RealLLMPlanner`，没有凭据时报错且不回退；`build_product_service` 不变 |
| T-CX454 | 快照、报告 JSON 和 HTML、CLI、健康检查的身份字段；旧形状的报告保持不变 |
| T-CX455 | 页面在没有凭据时可以提交诊断，自由文字起草提示需要凭据 |
| T-CX456 | 浏览器证明（桩 planner，手工记录，不进 CI） |

## 6. 操作员决定（2026-10-07：1A、2A、3A、4A）

1. **引擎实现方式：**
   - A（推荐）：实现为确定性决策器，走现有运行时，复用全部校验和报告。
   - B：独立的引擎模块，产出新的结果模型，报告层适配两种结果。
2. **报告里的 `planner_identity`：**
   - A（推荐）：在情境快照和报告中改为可选。引擎运行时省略，改看 `diagnosis_identity`；planner 运行保持原样。这避免在引擎给出的报告上写一个模型身份。
   - B：保持必填，引擎运行时也填写配置的 planner 信息，再加 `diagnosis_identity` 说明实际由谁给出。
3. **默认入口：**
   - A（推荐）：CLI 和 API 默认改用 `build_engine_service`，planner 需要显式选择。
   - B：默认入口不变，引擎需要显式选择。等阶段 3 解释层就绪后再切换默认。
4. **结论对照不达标时：**
   - A（推荐）：逐例说明并暂停切换默认，由操作员决定。
   - B：只要不出错就切换，差异记录为已知问题。

## 7. 2026-10-07 调研的使用

**本阶段已经采用的（架构层面）：**
- **全量运行检测器、直接列出问题：** 借鉴 iZotope RX Repair Assistant、Pulsar、BATON 的做法，引擎不再由模型挑选检测项目。
- **LLM 放在人和机器之间：** 借鉴 Rohde & Schwarz CMX500 AI Scripting Assistant，LLM 只负责理解描述和解释结果，不参与判定。
- **数值和结论只来自确定性 DSP 与规则：** 有音频大模型在基础物理属性上接近随机的证据支持（SonicBench、AudioJudge）。

**本阶段不采用、另有安排的（具体技术）：**
- **Aleinik 幅度直方图削波检测（OQ-025）：** 紧接本阶段之后单独设计，加上新版本规则。本阶段的结论对照要求证据和规则不变，同时改削波证据会混淆差异来源。`egfxset_live_1` 中 planner 的 9 次报错，根源就是归一化录音被判为削波；引擎在这类录音上同样会判削波，只是不会报错。
- **Farina 指数扫频反卷积：** 阶段 2 的核心。届时先核实 pyfar、SuMPF 的许可证和维护情况，再决定是采用还是参照论文自行实现。
- **librosa pYIN：** 作为评测中的独立基频对照，用于发现八度错误（OQ-024），不进入产品。
- **harm_analysis、waveform-analyzer（MIT）：** 最多在测试中交叉验证 THD，不引入依赖。
- **Essentia（AGPL）：** 不进入产品；需要时只在离线评测中作为对照。

## 8. 实现后的修订（操作员 2026-10-07 选 A）

第一次对照（§4.3）发现两处不如 planner：

1. **长文件里的局部削波漏报 4 例：** 增量研究 T2 中，削波只出现在立体声的一个声道、一小段时间里，整文件比例低于阈值。
   - **修订：** 单文件模式下，整文件不支持削波时，引擎再按 D050 的窗口和声道逐段检查削波。结论引用出问题的那几个窗口的证据和规则判定。
   - **效果：** 4 例全部补回，其他用例不变。
2. **声明单音的纯削波用例多认定了谐波（1 例，`dff3ebd9dffee874`）：** 削波本身产生偶次谐波，现有规则无法区分。作为已知局限记录，等阶段 2 的扫频测试解决。

**修订后的结果**见 D053 和 `docs/evaluations/v0_3/engine/phase1_comparison/report.json`：零报错、零驳回；情境验证集 17/17；增量研究 T1、T2 与 agent 逐例相同。
