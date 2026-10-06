# S1 Agent 增量切片实施计划

日期：2026-10-06
设计：`docs/superpowers/specs/2026-10-06-s1-agent-increment-design.md`（方向、通过线、调用上限预算规则已于 2026-10-06 获操作员批准）
状态：计划，待操作员授权实施（Task 0–9）。真实模型运行（D1、H1）另行授权。

## 修正记录

设计 §1 写“v9.11 prompt 在验证后被改、版本号未变”。准确表述：该改动以追加式身份修正记录在案（`code_identity_amendment.json` 的 `oq014_option_c_single_signal_flat_top_clipping`，prompt 哈希 `b4c279df…`，`model_calls: 0`），即改动有记录、但从未经真实模型运行验证。本计划据此处理：不改动 v9.11 的规格与既有修正记录，新行为在新版本号下评测。

## 全局约束

- 不改 `CONTRACTS_V0_2.md`、V0.2 冻结资产、任何已封存的 evaluation 产物；不改 `src/signal_diag/evaluation/contextual/`（其 harness 身份被既有封存研究钉住）、`evaluation/planner_ablation/`。
- 新评测代码放在新包 `src/signal_diag/evaluation/agent_increment/`。
- 不改 `DiagnosisClaim`、`PlannerContext`、`FullScaleMethodFloor` 等既有模型的字段；定位信息从结论所引用 Evidence 的工具参数（`time_range`、`channel`）推出。
- LLM 不生成任何数值、阈值或标准。标称频率只能来自用户文本中逐字出现的数字，不得来自测量 F0（§17）。未经确认的上下文字段不得进入诊断。
- `RealLLMPlanner` 与新的接诊规划器都不得静默退回脚本替身；缺少凭据即报错。
- 产品默认 prompt 在 H1 通过安全硬条件、操作员另行批准之前保持 v9.11 不变；新 prompt 只在评测与显式选择的路径上使用。
- TDD；随机性只来自预注册种子；不新增依赖。

## 版本与编号

- 新 prompt：`v0.3-s1-planner-9.12` = 现行 v9.11 文本（哈希 `b4c279df…`）+ T2 的分段/声道下钻指引。接诊规划器单独版本：`v0.3-s1-intake-1.0`。
- 决策：D045。合同：`CONTRACTS_V0_3_CONTEXTUAL.md` 新增 §24。测试编号：T-CX387–T-CX398（T-CX381–T-CX386 已由 R4 使用）。

## Task 0：文档登记（仅定义）

- D045：本切片、两项预算决定（调用上限代替 token 证明；开发阶段 1,500 次、留出阶段 1,008 次、每例 21 次）、通过线（设计 §4.2）、产品默认 prompt 不随本切片自动切换。
- §24（追加）：
  - 24.1 自由文本接诊：`IntakeRequest`（文本 + 上传文件名列表）→ `ContextDraft`（`mode`、`nominal_fundamental_hz`、`reference_file`、`stimulus_kind`、`missing_fields`、`questions`）→ 用户确认后的 `ConfirmedContext` → 既有情境提交。草案中的数字必须能在原文中逐字找到；确认前不进入诊断。
  - 24.2 局部故障：结论可引用分段工具调用的 Evidence；定位由所引用 Evidence 的 `time_range`/`channel` 推出；分段证据如何构成支持的规则以版本化规则配置给出（Task 5）。
  - 24.3 评测研究 `study_s1_agent_increment_1`：三臂、指标、通过线、调用上限、只写一次。
- `TEST_PLAN_V0_3_CONTEXTUAL.md`：登记 T-CX387–T-CX398（定义见文末）。
- 提交：`docs: register S1 agent-increment slice (D045, §24, T-CX387–T-CX398)`

## Task 1：接诊规划器（agent/，T-CX387、T-CX388）

- 新文件 `src/signal_diag/agent/intake.py`：`ContextDraft` 等模型；`IntakePlanner` 协议；`RealLLMIntakePlanner`（复用 `retest_planner.py` 的 OpenAI 兼容客户端写法与 SDK 身份，`deepseek-v4-flash`）；只用于测试的 `ScriptedIntakePlanner`（不进产品构建器）。
- 确定性校验 `validate_context_draft(draft, request)`：
  - `nominal_fundamental_hz` 非空时，其数值必须与原文中某个数字（含 `kHz` 换算）相等，否则拒绝；
  - `reference_file` 只能是上传文件名之一，且不得等于测试文件；
  - `mode` 与文件数一致（`paired_reference` 需两文件）；
  - 草案不得包含阈值、百分比标准等字段（模型 `extra="forbid"`）。
- 发给模型的只有文本、文件名、文件数与采样率等元数据；不发送波形或测量结果。
- 提交：`feat(agent): intake planner with deterministic draft validation (T-CX387, T-CX388)`

## Task 2：接诊产品入口（app/，T-CX389）

- API：`POST /api/v1/intake/draft`（文本 + 文件名列表 → `ContextDraft`）。确认不新增服务端端点：客户端用确认后的字段调用既有情境提交端点；服务端照旧校验。
- CLI：`signal-diag intake draft --text ... --file ...`。
- 产品构建器只装配 `RealLLMIntakePlanner`；未配置凭据时端点返回明确错误。
- Web UI 改动放到 Task 9（可选）。
- 提交：`feat(app): intake draft endpoint and CLI (T-CX389)`

## Task 3：B1 正则接诊基线（evaluation/，T-CX390）

- `src/signal_diag/evaluation/agent_increment/intake_baseline.py`：确定性规则（“参考/旧/之前/原来”等词归属参考文件；`\d+(\.\d+)?\s*(k?Hz)` 取频率；“正弦/测试音/单音”判单音激励）。规则表在实现前写死并随清单冻结。
- 与 agent 共用同一个模拟用户与同一个校验函数。
- 提交：`feat(eval): deterministic intake baseline B1 (T-CX390)`

## Task 4：prompt v9.12（T-CX391）

- `prompts_v03.py` 新增 `_S1_PROMPT_V9_12` = v9.11 现行文本 + 分段/声道下钻指引（何时用 `time_range`、`channel`；结论须引用分段 Evidence；不得把分段结果外推到整文件）。v9.11 规格与既有修正记录不动。
- 测试钉住：v9.12 文本以 v9.11 现行文本为前缀；哈希登记；产品默认仍为 v9.11。
- 提交：`feat(agent): planner prompt v9.12 with segment/channel drill-down (T-CX391)`

## Task 5：分段证据规则（rules/，T-CX392）

- 先确认现有规则闭包对分段工具调用产生的观测能否给出规则判定、结论能否引用。若可以，只需新增版本化规则配置（`rules/profiles/` 下新 YAML）规定“任一分段的削波规则 FAIL 可支持削波结论”，阈值沿用 `profile_s1_distortion`，不新定数值。
- 若需要改动既有模型字段或 V0.2 冻结行为才能实现：停下报告。
- 提交：`feat(rules): segment evidence rule profile (T-CX392)`

## Task 6：B2 分段穷举基线（evaluation/，T-CX393）

- `agent_increment/segment_baseline.py`：窗长 0.25 s、50% 重叠、每个声道 + mixdown；每段调用削波与谐波工具并按 Task 5 规则判定；任一段 FAIL 即报出并给出段位置。窗长等参数随清单冻结。
- 记录工具调用次数。
- 提交：`feat(eval): deterministic segment-scan baseline B2 (T-CX393)`

## Task 7：评测包（evaluation/agent_increment/，T-CX394–T-CX396）

- 模型：`IncrementCase`（`family` ∈ {T1, T2}、`split` ∈ {dev, heldout}、文本、文件、真值：结论、因果集、上下文字段、故障段/声道）、`IncrementArm` ∈ {`agent`, `strong_fixed`, `weak_fixed`}。
- 模拟用户：只对 agent/B1 已提出的字段按真值确认或纠正；不主动补全缺失字段；对 `questions` 只回答被问到的字段。记录纠正次数。
- 计分：主指标“增量”（配对正确数之差）；安全硬条件；T1 字段正确率与纠正次数；T2 定位正确率与工具调用数；与设计 §4.2 的通过线一致。
- 运行器：沿用 `evaluation/contextual` 的 ledger/只写一次/身份记录写法（复制模式，不导入或修改该包）；调用计数器在每次 HTTP 发送前检查：每例 21、阶段总上限（开发 1,500、留出 1,008），超限即停并写停止记录。
- `--dry-run`：打印样例数、各臂、预计最大调用数，不调用模型。
- 提交：`feat(eval): agent-increment study harness with call caps (T-CX394–T-CX396)`

## Task 8：样例构建（T-CX397）

- 开发集 T1 12 + T2 12；留出集 T1 24 + T2 24；比例要求见设计 §4.1（无故障反例 ≥ 1/3、信息不足样例、对基线有利的样例）。
- 音频：T2 用 `signal/` 现有合成器生成分段削波、单声道削波、分段谐波，以及在既有 NSynth/ESC-10 研究 WAV（只读复用）上叠加局部故障；T1 复用既有开发/验证情境样例的 WAV（只读）。
- 文本：开发集文本手写；留出集文本由实现前冻结的模板语法 + 预注册种子展开，既包含直白句式（对 B1 有利）也包含改写、口语、无关信息句式。模板在任何开发集真实运行之前提交并写入清单哈希。
- 留出集生成后立即写 `SHA256SUMS` 与清单哈希；之后不得改动。
- 提交：`feat(eval): agent-increment dev and held-out case sets (T-CX397)`

## Task 9：离线验收与可选 UI（T-CX398）

- 端到端：脚本替身跑通开发集与留出集的全部三臂（不调用模型），计分产出完整报告；身份字段齐全；超限停止路径有测试。
- 可选：Web UI 接诊输入框（文本 + 草案确认表单），不改现有默认流程。
- 验收文档 `docs/AGENT_INCREMENT_OFFLINE_ACCEPTANCE.md`。
- 提交：`docs: agent-increment offline acceptance (T-CX398)`

## 复审补充（2026-10-06，设计 §4.2）

- T1 主增量改为第一版草案四字段全对，纠正次数单独报告。
- 下游指标是确认后诊断结论正确数之差。离线用脚本替身，live 用 T-CX399 运行器。
- T1 真值结论取自所复用情境 WAV 的清单标签。`ContextDraft.asked_fields` 是“被问到”的唯一名单。
- 留出集文本多样性与清单哈希的更新见实现提交，不在本计划里改种子。

## 运行阶段（各自单独授权）

| 步 | 内容 | 上限 |
|---|---|---|
| D1 | 开发集真实运行（可多轮迭代 prompt v9.12 与接诊 prompt；每轮记录） | 合计 1,500 次调用 |
| F | 冻结 v9.12 与接诊 prompt 的最终文本与哈希；之后不再改 | — |
| H1 | 留出集单次运行，三臂；不重试挑选 | 1,008 次调用 |
| R | 报告：增量、安全、各族指标；Claude Code 独立复审；操作员决定产品默认 prompt 是否切换 | — |

## 验证（Task 9 完成时，在最终 tip 上）

pytest 全量（零 required skip/xfail）、架构测试、ruff、mypy、wheel smoke、`git diff --check <基线>..HEAD`。

## T-CX 定义

| ID | 定义 |
|---|---|
| T-CX387 | 接诊草案校验：标称频率必须逐字来自原文（含 kHz 换算）；参考文件只能是上传文件之一；模式与文件数一致；额外字段被拒绝 |
| T-CX388 | 接诊规划器只发送文本与文件元数据；缺凭据报错且不退回脚本替身 |
| T-CX389 | 接诊入口：未确认字段不进入诊断；确认后经既有情境端点提交并照常校验 |
| T-CX390 | B1 正则基线确定、规则表冻结、与 agent 共用模拟用户与校验 |
| T-CX391 | v9.12 以 v9.11 现行文本为前缀并登记哈希；产品默认仍为 v9.11 |
| T-CX392 | 分段证据规则：分段 FAIL 可支持结论，阈值来自既有配置；定位由所引用 Evidence 推出 |
| T-CX393 | B2 分段扫描确定、参数冻结、记录调用次数 |
| T-CX394 | 模拟用户只确认或纠正已提出的字段，不主动补全 |
| T-CX395 | 计分：增量、安全硬条件、T1/T2 指标与设计 §4.2 一致 |
| T-CX396 | 调用上限：每例 21、阶段总上限，超限即停并写停止记录；只写一次 |
| T-CX397 | 样例集：比例满足设计 §4.1；留出集由冻结模板与种子确定生成，SHA256SUMS 与清单哈希固定 |
| T-CX398 | 离线端到端：脚本替身跑通三臂、报告完整、身份字段齐全 |
