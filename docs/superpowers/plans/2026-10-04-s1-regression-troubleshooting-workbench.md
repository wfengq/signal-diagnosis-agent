# S1 音频排障与复测工作台 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task, only after operator authorization. Cursor implements; Codex designs and independently reviews. Steps use checkbox syntax. No task authorizes commit, push, merge, seal, or RealLLM execution.

**Goal:** 实现周期测试信号的确定性版本比较、当前会话内的复测案例，以及独立且受约束的复测建议接口。

**Architecture:** tools 生成独立测量记录，rules 负责比较准入与判定，app 组织案例。agent 只选择复测方案，不计算指标或改写判定。跨运行比较使用新对象，不改旧诊断的 same-run Evidence 语义。

**Tech Stack:** 现有 Python 3.11/3.12、NumPy、Pydantic 2、PyYAML、FastAPI、原生 HTML/JS。第三交付仅复用已锁定的 OpenAI-compatible SDK，离线验证不调用网络模型。不新增依赖。

**Spec:** `docs/superpowers/specs/2026-10-04-s1-regression-troubleshooting-workbench-design.md`。
Approved spec SHA256: `536b71ddb6e5f3b3369fa49a1aa4e7ad5471497d88b89977822600fa9a990fe4`，按原始 UTF-8/LF 字节计算。

**Status:** 计划待操作员审阅。任何 Task 尚未获实施授权。
**Read-only baseline:** `4b45f73997a3da89b19eb00846231c6bc84a7709` on `codex/v0.2-real-world-validation`，2026-10-04 读取远端并检出核对。
**Local authoring checkout:** `9931875`。只在该 checkout 落盘设计与计划，不作为实施基线。
所有命令中的 `<BASE>` 指执行时核定的完整基线 SHA；本计划核定值为上面的 `4b45f73997a3da89b19eb00846231c6bc84a7709`，不是名为 BASE 的 Git ref。

## Global Constraints

- 首期为周期测试信号，意图为“预期行为不变”，不覆盖任意语音、音乐或随机效果器。
- 旧版输出是基准，不能自动作为干净 reference。原始激励上传不证明执行来源。
- 不自动归一化、重采样、时间拉伸或对齐；不把不适用测量转成零。
- 所有数值来自 DSP；容差来自版本化配置；LLM 不能生成指标、阈值或通过结果。
- 没有已批准的产品比较规则时，只能展示描述性变化。演示诊断阈值不是比较容差。
- 保持 v9.11 诊断 prompt、causal policy、D037、D039 及既有入口语义。复测 planner 独立身份。
- 不修改 frozen V0.2 §§1–64、历史 bundle、Demo、seal 或既有 oracle。不续写 OQ-019 结论。
- 不静默回落 Scripted；离线 fake/mock 明确标记，不能计为产品模型运行。
- 不自动执行用户程序；无数据库、案例恢复导入、插件宿主、向量库或多 Agent 产品架构。
- 本计划内所有数值测试夹具仅验证实现逻辑，不是科学容差、质量承诺或正式研究协议。
- 不 commit/push/开 PR/merge，除非操作员另授。每个任务以保留可审阅 diff 结束。

## Review Focus

以下五类输入在任务中都有对应负向测试：

1. 两侧 Evidence ID 相同、调用计数重置或输入字节相同：必须按运行、侧和输入身份解析，不能串侧。Task 2/3/6。
2. 同为 float、指标同名但单位、工具配置或分析范围不同：不允许直接比较。Task 3。
3. 调用方自称 profile 已批准、或者上传夹具 profile：产品不能据此启用通过/失败。Task 3/5。
4. 重复提交、并发追加和旧页面返回的晚到响应：不得覆盖已完成记录或关联到错误父记录。Task 5/6。
5. 无 key、模型超时、取消后仍在执行及错误建议 ID：保持比较结果、停止建议流程，无假成功或自动重试。Task 7/8。

## 授权与交付分段

| 阶段 | Tasks | 可交付结果 | 必须停止的位置 |
|---|---|---|---|
| A 定义与确定性比较 | 1–4 | 合同、离线测量与比较、负向用例 | 复检通过后另授 B |
| B 案例与产品入口 | 5–6 | 当前会话案例、Web、导出、手动复测 | 复检通过后另授 C |
| C 复测 planner 的离线实现 | 7–8 | 独立协议、注入式 SDK 客户端、离线对照接口 | 不进行真实模型调用 |
| 收口 | 9 | 每个阶段结束均执行其适用检查 | 不因测试绿自动提交或启用新阶段 |

产品容差校准、复测电平参数批准、真实模型验证及用户收益研究均为外部后续授权。本计划不执行它们。可先只授权 Task 1 文档定义，不自动包含 Tasks 2–4。

## 基线核对与文件责任

当前基线合同止于 §21，测试编号止于 T-CX328。提议新增 §22 与 T-CX329–348；实施前再次检查冲突，若已占用则调整本计划映射并复检，不能覆盖他人定义。

已核对：`SignalToolService(repository)`、`detect_clipping(signal_id, ClippingInput)`、`analyze_harmonic_distortion(signal_id, HarmonicDistortionInput)`、`load_wav_bytes(data, filename=..., limits=...)`。测量 clipping_ratio 的 Evidence unit 为 None，thd_percent 的 unit 为 `%`。不要把 ratio 当百分数。

现有静态资源位于 `app/static/`，不是 `app/web/`。现有 `create_app(service=None)` 的签名保持不变。

| 新增文件 | 职责 |
|---|---|
| `src/signal_diag/tools/regression_measurement.py` | MeasurementSelection、InputIdentity、MeasurementBundle 和真实工具测量 |
| `src/signal_diag/rules/regression.py` | 条件、来源引用、规则、比较记录和纯比较函数 |
| `src/signal_diag/app/regression.py` | 上传适配、服务端配置、当前会话案例与资源释放 |
| `src/signal_diag/app/regression_reporting.py` | 案例 JSON 验证与 HTML 渲染 |
| `src/signal_diag/app/regression_api.py` | 新路由及新用途的有界 multipart 解析 |
| `src/signal_diag/app/static/regression.html`、`regression.js` | 新增工作台页面，复用现有样式 |
| `src/signal_diag/agent/retest_planner.py` | 建议目录、输入输出、资格校验、独立 prompt 和客户端适配 |
| `src/signal_diag/evaluation/regression.py` | 显式固定策略、离线用例及建议评分 |
| `docs/REGRESSION_WORKBENCH_OFFLINE_ACCEPTANCE.md` | 基线、AC/T-CX 映射、实测结果、未解除项 |

既有修改限定为 additive 合同/测试/决策记录，`app/api.py` 的新路由挂载与 lifespan 释放、`app/static/index.html` 的入口链接，以及确有必要的测试路径白名单、身份追加和文档索引。不改旧 CLI diagnose，不复制 planner-ablation baseline 到产品。

## Task 1: 注册合同、测试与身份要求

**Files:** Modify `docs/CONTRACTS_V0_3_CONTEXTUAL.md`, `docs/TEST_PLAN_V0_3_CONTEXTUAL.md`, `docs/DECISIONS.md`。

**Interfaces:** 产出 §22 的数据和行为定义及下表映射；不创建 Python 类、不改 allowlist 实现、不修改 runtime。

| 提议 ID | 定义 | 后续任务 |
|---|---|---|
| T-CX329 | 请求严格类型、对应范围、用户声明与观测分离 | 2/5 |
| T-CX330 | 真实工具测量、同字节双侧独立身份、无预处理 | 2 |
| T-CX331 | 逐指标准入、不同配置/单位/范围的拒绝 | 3 |
| T-CX332 | 规则差值方向、边界及相对差分母 | 3 |
| T-CX333 | 产品无 profile 只描述，夹具配置不得公开启用 | 3/5 |
| T-CX334 | 跨运行引用、内容与类型一致性、重建校验 | 3/6 |
| T-CX335 | 部分覆盖、已有异常、执行失败的汇总语义 | 3/4 |
| T-CX336 | 同会话追加、显式父关系与幂等提交 | 5 |
| T-CX337 | 文件/会话限额、并发和清理 | 5/6 |
| T-CX338 | JSON/HTML 完整性、转义、原始证据与差值区分 | 6 |
| T-CX339 | Web 双文件到手动复测、晚到响应与无 key | 6 |
| T-CX340 | 目录资格、没有合格方案及禁止越权参数 | 7 |
| T-CX341 | 独立 planner 身份、紧凑输入、严格输出 | 7 |
| T-CX342 | 预算、取消、失败和无静默回退 | 7 |
| T-CX343 | 同条件固定/模型策略对照、真值隔离、失败分母 | 8 |
| T-CX344 | real adapter + fake transport 离线接通，无网络 | 8 |
| T-CX345 | 旧诊断入口、D037/D039 与 sealed 资产保留 | 4/9 |
| T-CX346 | 分层、冻结白名单、append-only 身份 | 4/9 |
| T-CX347 | 修复复测消失/持续/不适用/失败均可区分 | 5/6 |
| T-CX348 | 无已批规则/收益证据不宣称产品或 planner 验收完成 | 8/9 |

- [ ] 核对实际 HEAD、git status、ID 及接口；确认 spec 原始字节 hash，与本计划基线差异单独记录。已有用户改动不覆盖。
- [ ] 在 §22 写入本计划接口、枚举语义、客户端不能提供 profile 和建议数值参数的边界。新增决策条目的编号从实际基线分配，不改 D037/D039。
- [ ] 写入 T-CX329–348 的可观察行为，标明“definition only”与实际覆盖分开登记。
- [ ] 运行 `git diff --check <BASE>`，核查 frozen V0.2 文本未动。文档阶段不以空测试冒充覆盖。
- [ ] Stop for recheck。没有 Tasks 2–4 授权则停在此处。

## Task 2: 独立测量记录，复用真实 DSP 工具

**Files:** Create `src/signal_diag/tools/regression_measurement.py`; test `tests/tools/test_regression_measurement.py`。

**Interfaces:**

- `InputIdentity`：run_id、side=`baseline|candidate`、wav_sha256、signal_id、采样率、源通道数、总帧数、已解析的起止样本索引、所选通道和不可变的工具参数快照。
- `MeasurementSelection`：ClippingInput 与 HarmonicDistortionInput。二者必须选择同一 time_range/channel；首期单个比较项只选 left 或 right，不使用 mixdown 掩盖通道变化。双通道需要分别检查并保留覆盖表。
- `MeasurementBundle`：identity、ToolResult[ClippingOutput]、ToolResult[HarmonicDistortionOutput]、measurement_version、内容 digest。工具失败仍保留其 status/error；不构造假 AgentRunResult。
- `measure_output(*, repository: SignalRepository, identity: InputIdentity, selection: MeasurementSelection) -> MeasurementBundle`。

身份中输入字节哈希由 app 从上传字节计算；工具层核对 repository 中信号元数据和解析范围。digest 采用 UTF-8 canonical JSON，sort_keys、compact separators、allow_nan=False，并排除 digest 字段本身；不能只对 Evidence ID 列表求 hash。

- [ ] 写红测 `test_real_pcm_measurements_keep_two_run_identities`：用内存 PCM WAV 经真实 load_wav_bytes 入仓；相同字节两侧 hash 相同而 run_id/side 不同，调用真实工具后双方 clipping_ratio 相等。无需恰好相同的 call_id。
- [ ] 写红测 `test_selection_and_sample_bytes_are_preserved`：调用前后原信号数组逐值相同且不可写；不新增归一化。分别测试右通道缺失、范围越界、NaN 参数和两工具范围不一致。
- [ ] 写红测 `test_invalid_harmonic_is_not_zero`：真实不适用工具输出保留状态，不产生数值为零的有效 THD。工具 error 与 not_applicable 分开。
- [ ] 运行 `python -m pytest tests/tools/test_regression_measurement.py -q`，先确认失败指向新增行为。
- [ ] 实现上述单一模块。每侧建立新的 SignalToolService；保留返回的完整工具结果。明确解析后的实际样本范围，不用文件名决定语义。
- [ ] 重跑同一命令，预期全部通过。保留 diff，Stop for recheck。

## Task 3: 纯比较规则、严格来源与描述性默认

**Files:** Create `src/signal_diag/rules/regression.py`; tests `tests/rules/test_regression.py`, `tests/rules/regression_fixtures.py`。

**Consumes:** Task 2 的 MeasurementBundle。
**Produces:**

- `ComparisonConditions`：intent=`preserve_behavior`、baseline_version、candidate_version、stimulus_key、parameters_key、same_input/parameters_unchanged/aligned_ranges 的 `yes|no|unknown` 声明、repeatability=`declared_deterministic|unknown|observed_variable`。可选 original_input_sha256 和显式 nominal Hz；声明不是测量证明。
- `SourceRef`：side、run_id、wav_sha256、bundle_digest、evidence_id。引用项附带 source_tool、call_id、metric、value、unit、validity、channel/time_range；要求类型和值逐项一致。
- `ComparisonRule`：rule_id、metric、source_tool、unit、difference=`signed_absolute|relative_increase`、allowed_min/max、相对差专用 denominator_floor、applicability_version。
- `ComparisonProfile`：profile_id、version、规则 tuple 和内容 digest。approved 标志不属于客户端可授信字段。
- `MetricComparison`：metric、双方 SourceRef、difference 或 None、difference_unit、status=`not_comparable|descriptive_only|regression_detected|no_regression_detected`、reason_codes、rule_ref 或 None。
- `ComparisonRecord`：comparison_id、双侧 bundle、conditions、profile 身份、不可变逐项结果、required_checks 与 coverage、内容 digest。缺失必要项时不得 overall pass。
- `compare_measurements(baseline: MeasurementBundle, candidate: MeasurementBundle, *, conditions: ComparisonConditions, profile: ComparisonProfile | None) -> ComparisonRecord`。
- `validate_comparison_record(record: ComparisonRecord) -> None`：在报告构建与解析边界重算引用、差值、结果和 digest。返回已篡改结果必须抛 ValueError；Pydantic 重建包装为 ValidationError。

首期数值比较表仅 `detect_clipping/clipping_ratio/None/float` 与 `analyze_harmonic_distortion/thd_percent/%/float`。其它 Evidence 保留为测量事实，不自动成为比较项目。严格拒绝 bool/int/str 代替 float、非有限数及工具结果与 Evidence 不一致。

clipping_ratio 差值为 ratio；thd_percent 的绝对差单位为 percentage_points。相对增量定义 `(candidate-baseline)/abs(baseline)`，仅 `abs(baseline)>denominator_floor` 时适用。floor 必须有限且正，边界包含关系固定为 allowed_min <= difference <= allowed_max。

双方同名指标只有方法参数、范围对应、源通道、单位和有效性均兼容才可比较。谐波还需双方有效测量及工具参数兼容；不从 THD 差产生 supported_fault。任何用户声明为 no 或相关 unknown 均阻断受影响判定，不能把未提供声明当 yes。

谐波的基频兼容要求属于 profile 的适用性配置，不让实现代理自行发明频率差阈值。没有经审阅的兼容性规则时，保留双方有效值，THD 差值判定保持受阻，不得仅凭两个 valid 标志放行。测试 profile 显式定义其兼容性夹具，并包含两个有效但基频不兼容的负例。

- [ ] 写 `test_fixture_profile_boundary`，使用仅位于 tests 的 profile：ratio 允许差值 [-0.001, 0.001]。在上下边界判未发现回归，越界判回归。这些数字只测比较器，产品不加载。
- [ ] 写 `test_no_profile_is_descriptive`：合格双侧非零变化、profile=None → descriptive_only、rule_ref=None，不能整体通过。equal 值也不能冒充已有验收规则。
- [ ] 写 `test_relative_difference_rejects_small_denominator`：baseline=0 与恰好 floor 时均 not_comparable；不得 NaN/Inf。另测相对差、百分点和 ratio 的单位不混淆。
- [ ] 参数化测试错单位、错工具、错配置、错范围、无效 harmonic、missing Evidence、交换 side/run、相同 ID 异运行、1.0 被替成 True/1、手改 difference 或 status，均按准入或完整性错误拒绝。
- [ ] 写 `test_existing_fault_and_partial_coverage_are_preserved`：双方原始 flat_top/clipping_mechanism 事实仍在；一个有效结果不隐藏另一个 required check 的阻断。工具执行 error 不映射为任何通过。
- [ ] 运行 `python -m pytest tests/rules/test_regression.py -q`，确认红测后实现纯比较及边界验证，再全部跑绿。
- [ ] Stop for recheck。不在 src/rules/profiles 写测试阈值，不启用产品 profile。

## Task 4: 交付 A 的离线真实输入验收

**Files:** Create `tests/evaluation/test_regression_measurement_acceptance.py`, `docs/REGRESSION_WORKBENCH_OFFLINE_ACCEPTANCE.md`; necessary identity/architecture updates follow Task 9。

**Interfaces:** 使用真实 load_wav_bytes、InMemorySignalRepository、Task 2/3；不得调用 planner-ablation baseline 或任何模型客户端。

- [ ] 写真实 PCM 样本测试：相同正弦、确定性新增削波、双方均削波、谐波不适用、左右声道不同、范围截断。随机样本若有则 seed 固定。
- [ ] 为同一组样本分别验证无 profile 的描述性结果与测试 profile 的判断逻辑。不得从合成样本表现直接批准产品容差。
- [ ] 运行 `python -m pytest tests/evaluation/test_regression_measurement_acceptance.py tests/tools/test_regression_measurement.py tests/rules/test_regression.py -q`。
- [ ] 写验收映射，区分定义、unit、真实工具集成和未实现 UI/planner。记录产品 profile 数量为零、未验证收益。
- [ ] 执行 Task 9 的阶段 A 收口，Stop for recheck，B 另授。

## Task 5: 同会话案例与有界应用服务

**Files:** Create `src/signal_diag/app/regression.py`; test `tests/app/test_regression_service.py`。

**Consumes:** MeasurementSelection、ComparisonConditions、compare_measurements。
**Produces:**

- `ComparisonUpload`：baseline_data/candidate_data bytes、显示文件名、双方版本、conditions、selection、可选 original_input_data。禁止客户端指定 hash、run_id、判定或 profile 对象。
- `RetestLink`：kind=`repeat|repair|recommendation`、parent_comparison_id、可选 recommendation_id。与建议关联时必须匹配其预期条件。
- `RegressionCaseSnapshot`：case_id、revision、goal、不可变比较记录 tuple、独立失败记录 tuple、建议记录 tuple。每项显式标识已有结果及最新提交状态。
- `RegressionWorkbenchService.create_case(goal: str) -> RegressionCaseSnapshot`。
- `async submit_comparison(case_id: str, upload: ComparisonUpload, *, request_id: str, link: RetestLink | None) -> RegressionCaseSnapshot`。
- `get_case(case_id: str) -> RegressionCaseSnapshot`、`delete_case(case_id: str) -> None`、`async aclose() -> None`。

服务负责字节 hash 和新 run/comparison ID，真实解码后调用工具；不借 DiagnosisApplicationService.submit_contextual_wav 把两侧变成 paired_reference。原始激励仅保存来源信息，不暗中注入诊断上下文。

产品构建函数 `build_regression_service() -> RegressionWorkbenchService` 位于同一模块，默认 profile=None。无公共 profile 上传/路径参数，无客户端 approved 字段。测试仅通过显式构造器注入夹具 profile；产品构建路径测试证明不会加载 tests 配置。将来启用容差须单独新增经审阅的服务端绑定，本计划不实现任意 profile 加载器。

本计划提出的工程资源限制需在 Task 1 中定义后实施：沿用 WavLoadLimits 每文件 20 MiB；一组最多 baseline/candidate/original 三文件。最多 8 个活动案例，每例最多 16 次已接收提交；单个服务同时测量一组，其余返回 busy，不建无界队列。它们不是研究预算或科学阈值。

goal 限 2000 字符，版本与条件 key 各限 256 字符，request_id 限 64 字符。所有外部新模型 extra=forbid。对上传流先占用有界操作槽，再读取字节；不能只限制测量并发而允许无限并行缓冲上传。断连时停止接收，已进入工作线程的测量确实结束后才释放该槽。

不长期保留上传字节和数组，测量后只保留身份、结构化工具结果及报告。执行完成、失败和 aclose 时释放临时 repository；会话清理不覆盖已导出的文件。

- [ ] 红测无 key 的真实 PCM 双侧提交仍产生描述性比较，recommendation 状态 unavailable；旧诊断接口仍 planner_not_configured。
- [ ] 红测相同 request_id+相同请求返回已有结果、不重新测量；相同 request_id+不同内容拒绝。父记录必须存在于同案例且已完成，repair/repeat 新建记录，不能就地覆盖。
- [ ] 红测运行失败保留原记录并追加失败条目；重复失败请求也不重复执行；尝试篡改返回快照不影响内部状态。
- [ ] 红测文件限额、会话限额、同时提交 busy、删除正在运行案例的冲突、关闭时等待真实工作结束。不能只 cancel asyncio waiter 就声称资源已释放。
- [ ] 运行 `python -m pytest tests/app/test_regression_service.py -q`，红测后实现。只用当前会话内存，不添加数据库。
- [ ] 全部通过后 Stop for recheck。

## Task 6: Web、报告与手动复测路径

**Files:** Create `src/signal_diag/app/regression_reporting.py`, `src/signal_diag/app/regression_api.py`, `src/signal_diag/app/static/regression.html`, `src/signal_diag/app/static/regression.js`; Modify `src/signal_diag/app/api.py`, `src/signal_diag/app/static/index.html`；tests `tests/app/test_regression_reporting.py`, `tests/app/test_regression_api.py`, `tests/app/test_regression_ui.py`。

**Interfaces:**

- `build_case_report(snapshot: RegressionCaseSnapshot) -> RegressionCaseReport` 和 `render_case_html(report: RegressionCaseReport) -> str`。RegressionCaseReport 在 reporting 模块定义，包含完整比较/来源对象，model_validate 和构建都调用 Task 3 完整性验证。
- `build_regression_router(service: RegressionWorkbenchService) -> APIRouter`。现有 create_app 签名不变，在 lifespan 中创建并关闭附属 service；测试在独立 FastAPI 上挂该 router，无需扩旧工厂签名。
- 新路由 `/regression`；API `/api/v1/regression/cases` 创建案例、`/{case_id}` 读取/删除、`/{case_id}/comparisons` multipart 提交、`/{case_id}/report.json`、`/{case_id}/report.html` 导出。请求成功返回当前 snapshot。
- 新能力状态 `/api/v1/regression/capabilities` 区分 measurement_available、recommendation_available、enabled_profile_ids。已有 `/api/v1/health` 不改含义。

在 `app/api.py` 的 `_STATIC_MEDIA_TYPES` 精确增加 regression.js，通过现有打包静态读取路径服务资源，不放开任意文件。JSON API 的 invalid 输入用 422、超限用 413/429、未知案例用 404、busy/关联冲突用 409；科学上的 not_comparable 返回成功响应内的明确结果，不伪装服务异常。

multipart 只收 baseline/candidate、可选 original 和单个 UTF-8 metadata JSON。逐文件按 20 MiB 截止，总请求按三文件上限加 64 KiB 元数据/编码开销截止；字段重复、未知字段及任意超限在完整缓冲前拒绝。不能对不受限的 request.form/read 调用完后才测大小。复用有界解析思路，不扩旧上传入口的允许字段。

界面顺序固定为目标与测试条件、两侧文件、逐项结果及覆盖范围、复测或修复后追加、导出。没有产品 profile 时显示“仅报告测量变化，尚无已批准的比较容差”；不显示通过绿标。服务重启丢失案例时明确提示，不假装恢复。

- [ ] 红测报告 build/model_validate 对跨案例引用、丢失证据、伪造 rule_ref、差值与原值不一致均拒绝。HTML 转义文件名、版本、goal 和模型文本，JSON 保留来源。
- [ ] 红测合法 multipart 实测可达真实 service，重复字段/超限拒绝；输入客户端 profile/approved/result 字段被拒绝；无需 key 的比较与旧诊断无 key 行为分离。
- [ ] 红测前端绑定唯一 case/request ID，晚到响应不覆盖当前案例；错误和部分覆盖不能显示“全部通过”。按钮 pending 状态和幂等键共同防止重复执行。
- [ ] 运行 `python -m pytest tests/app/test_regression_reporting.py tests/app/test_regression_api.py tests/app/test_regression_ui.py -q`，红测后实现。
- [ ] 通过浏览器驱动实际页面完成上传、描述性比较、repeat、repair 和两种导出；记录可复现动作及输出。静态源码字符串断言不能替代这一步。工具不可用时记录 UI 未验收，不伪报通过。
- [ ] 执行 Task 9 阶段 B 收口，Stop for recheck。不要自动进入 Task 7。

## Task 7: 独立复测协议及受约束模型适配

**Files:** Create `src/signal_diag/agent/retest_planner.py`; Modify `src/signal_diag/app/regression.py`, `src/signal_diag/app/regression_api.py`, `src/signal_diag/app/static/regression.js`; test `tests/agent/test_retest_planner.py`, `tests/app/test_regression_recommendations.py`。

**Interfaces:**

- `RetestContext`：comparison_id、comparison_digest、紧凑有效测量与阻断码、合格方案 tuple。不包含原始 WAV、数组、case goal 原文中的执行指令或 oracle。
- `RetestOption`：option_id、kind=`complete_conditions|repeat_conditions|lower_both_inputs`、所需输入、保持条件、确定性解释模板及经审核参数绑定。
- `RetestSelection`：仅 option_id 或 None、basis_refs、abstain_reason_code。extra=forbid；不允许输出阈值、增益数值、shell 命令或新 fault claim。
- `eligible_retests(record: ComparisonRecord) -> tuple[RetestOption, ...]`；缺具体信息才给 complete_conditions；重复性 unknown 才给 repeat_conditions；无已批电平参数时 lower_both_inputs 不可选。
- `RetestPlanner` Protocol：`async choose(context: RetestContext) -> RetestSelection`。
- `RealLLMRetestPlanner(*, client: RetestChatClient, model: str, limits: RetestCallLimits)` 实现协议。RetestChatClient 是本模块窄接口，由 `OpenAICompatibleRetestClient` 适配锁定 SDK，测试注入 fake transport。
- `RetestChatClient.complete(*, model: str, system_prompt: str, user_json: str, limits: RetestCallLimits) -> str` 为 async 方法，返回原始消息文本供严格解析；`async aclose() -> None` 关闭资源。SDK adapter 将 limits 显式传给请求，不隐式读取环境补值。
- `RetestCallLimits`：必须显式给出正整数 max_output_tokens 和有限正 timeout_s；一次建议至多一个 SDK 调用，SDK max_retries=0，不做应用重试。数值值域严格拒 bool。无完整已批准配置则产品建议 unavailable。
- `async RegressionWorkbenchService.request_recommendation(case_id: str, comparison_id: str, *, request_id: str) -> RegressionCaseSnapshot`。

新增 `POST /api/v1/regression/cases/{case_id}/comparisons/{comparison_id}/recommendations`，只接收 request_id。界面能力可用时才显示请求建议按钮，结果使用固定模板。方案资格与参数不接受客户端输入。SDK 调用一次的限制不等于 HTTP redirect 或供应商 token 最坏界的证明，本计划不拿它清除 OQ-019 资源门禁。

新身份建议为 `v0.3-s1-retest-1.0`，仅用于新协议；Task 1 注册并标未质量认证。构造默认产品 service 不自动启用该 planner。操作员启用模型参数与运行预算需另授；offline 实现可测整个真实适配路径。

输出 option_id 必须属于当次确定性目录，basis_refs 必须解析到该比较；不是靠 prompt 保证。用户可见建议使用方案模板与选择依据组合，不直接渲染模型自由诊断。无合格方案直接返回 unavailable，不必调用模型。

- [ ] 红测禁用方案、伪造引用、unknown option、额外 gain/fault 字段、一次返回多个方案均拒绝。上下文无波形、FFT 和真值标签。
- [ ] 红测 fake client 成功一次、超时、连接错误、非法 JSON 和取消。验证 max_retries=0、无第二请求，SDK 任务实际终止/关闭后才释放执行状态。
- [ ] 红测 no-key/未配置时返回 unavailable，比较记录字节不变；禁止转向 ScriptedPlanner 或固定策略伪造产品成功。
- [ ] 红测同一 request_id 不重复收费请求；比较 digest 变化、跨案例或正在执行时拒绝不合法关联。
- [ ] 运行 `python -m pytest tests/agent/test_retest_planner.py tests/app/test_regression_recommendations.py -q`，实现后全部通过。测试断言真正经 SDK adapter 的参数与调用次数，不只测宽松 fake planner。
- [ ] Stop for recheck，无网络模型调用。

## Task 8: 离线对照及完整案例链

**Files:** Create `src/signal_diag/evaluation/regression.py`, `tests/evaluation/test_regression_retests.py`; Modify `docs/REGRESSION_WORKBENCH_OFFLINE_ACCEPTANCE.md`。

**Interfaces:** `RetestEvaluationCase` 包含输入、允许揭示的复测结果及独立真值；只有 evaluator 可访问真值。`choose_fixed_retest(context: RetestContext) -> RetestSelection` 为显式对照，按 complete_conditions 优先、其次 repeat_conditions、其余按已注册目录次序；无合格项则 abstain。`score_retest_cases(cases: tuple[RetestEvaluationCase, ...], results: tuple[RetestEvaluationResult, ...]) -> RetestEvaluationSummary` 保留计划人口及失败。

`RetestEvaluationResult` 包含 case_id、arm、status=`completed|failed|missing`、selection 或 None、揭示的复测 outcome、耗时与调用计数。`RetestEvaluationSummary` 按 arm 返回 scheduled/completed/valid_selection/useful_retest/error 的计数及分母；空人口无比率，重复或计划外 case_id 拒绝，缺失结果计为 missing。useful_retest 由独立真值与所揭示结果判定，合法 abstain 单独计数，不伪装成功复测。没有正式收益阈值时不输出 advantage/dominance 类结论。

评价对象明确标 `fixed_strategy` 或 `real_adapter_fake_transport`。后者证明接口接通，不声称模型智能、准确率或延迟收益。不得把它写为已执行 product_agent/RealLLM。

- [ ] 写同一初始证据、同目录、同预算的对照，覆盖建议有效、错误选择、无建议、缺条件、复测仍未解决以及执行失败。
- [ ] 用两个已计划案例，一例成功、一例失败，断言完成分母为 2 而非 1；模拟时钟只验证计时定义，不能报告真实速度提升。
- [ ] 经真实 app service + RealLLMRetestPlanner + fake SDK transport 完成比较、建议、手动提交对应复测、报告导出。确保 oracle 未传给 planner。
- [ ] 运行 `python -m pytest tests/evaluation/test_regression_retests.py tests/app/test_regression_recommendations.py -q`。
- [ ] 验收报告写清“工程离线验证结果”“产品容差未启用”“真实模型与用户收益未验证”，不得从 offline green 推导产品收益已通过。
- [ ] 执行 Task 9 阶段 C 收口，Stop for independent recheck。

## Task 9: 每阶段身份与累计验证

**Files:** Modify only when needed `tests/test_architecture_boundaries.py`, `tests/agent/test_v03_prompt_v9_11.py`, `docs/evaluations/v0_3/contextual/development/study_v0_3_contextual_dev_1/code_identity_amendment.json`, `docs/REGRESSION_WORKBENCH_OFFLINE_ACCEPTANCE.md`, `docs/README.md`。

- [ ] 新文件路径白名单仅列授权的精确文件；禁止放开整个 dsp/rules/agent 或关闭 T285。新增架构断言覆盖 evaluation 不导入 app、rules/tools 不依赖 agent/app。
- [ ] 用现行 `src/signal_diag/evaluation/contextual/calibration.py` 的 product tree 计算逻辑核实摘要。若纳入身份的路径变化，追加新 amendment 行并更新 active-tip 断言，保留所有旧行及旧值。
- [ ] 不因旧身份覆盖范围未包含某些新文件而宣称新功能已认证；另在验收报告列新模块、规则、prompt 的真实身份。无模型调用时准确记录零。
- [ ] 运行本阶段聚焦测试，然后 `python -m pytest -q`、`python -m ruff check .`、`python -m mypy src`、`python -m pytest tests/test_architecture_boundaries.py -q`、`git diff --check <BASE>`。所列结果均须实测。
- [ ] Task 6 新增打包静态资源，执行 `python -m build` 和 `python -m pytest tests/app/test_packaging.py -q`，并在安装 wheel 的干净环境启动服务，实际取得 regression 页面及 JS；源码 checkout 的通过不能替代 wheel。
- [ ] 发布门另做 CPython 3.11/3.12 clean-environment matrix。不是本轮发布时，准确标记未执行，不能宣称 release-ready。
- [ ] 若历史身份/封存测试要求 clean git 而当前无 commit 授权，报告具体未完成检查，不能私自临时 commit/reset。继续完成其余可执行检查，不把 blocked 写成 passed。
- [ ] 验收表逐项记录实际基线、文件/命令、测试名、结果和未完成项；单独保留容差、电平参数、实时模型预算及收益评价的后续门禁。
- [ ] Stop for independent recheck。通过不授权 commit、push、merge、seal 或 RealLLM。

## Spec 覆盖与计划自查

| Spec 部分 | 任务 |
|---|---|
| §§1–3 范围、输入、声明 | 1/2/5/6 |
| §4 比较、部分覆盖和容差 | 3/4；生产容差校准另授 |
| §5 归因边界 | 2/3/9 |
| §6 案例、引用、导出、失败 | 3/5/6 |
| §7 方案、planner 和失败 | 7/8；真实预算值与调用另授 |
| §8 模块依赖 | 1/2/3/5/7/8/9 |
| §9 AC01–AC16 | AC01–08/10–12 在 2–4，AC09/13 在 5–6，AC14–15 在 7–8，AC16 在 9 |
| §9.2 收益验证 | 8 定义并验证离线机制，真实收益研究另授，不假称完成 |
| §§10–11 分段、身份和检查 | 全局约束及 9 |
| §12 外部研究边界 | 不引入新依赖，不以竞品 README 作为验收 |

本计划不给尚未验证的产品容差、真实模型预算和用户收益通过线填默认值。它们不是留给实现代理自由发挥的空白，而是本轮不得跨越的明确边界。

完整 spec 与本计划必须一同交给 Cursor；仅有聊天摘要或 SHA 前缀不够。若 GitHub 无法看到本机文件，应提供原文件或另授文档提交，不能假定云端可访问本机路径。
