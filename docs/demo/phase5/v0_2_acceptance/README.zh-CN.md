# Phase 5 真实产品 Demo（Task 14）

> 对照英文原件 [README.md](README.md)，以英文契约为准。

> **访客摘要（本目录是什么 / 不是什么）：** 本目录是保留的 Phase 5 产品 Demo
> 证据包——两次经授权的公开 `RealLLMPlanner` 运行、自包含报告、校验和，以及经净化的 UI 截图。
> 它是本地 CLI/Web 路径端到端可跑通的呈现集成证明。它**不是**官方留出行为基准
> （那仍是 Phase 4.3.1 / 79/80），不是为改进而重跑的门禁，也不是生产就绪声明。
> 仅在需要 run ID、claim 文本或文件摘要时，再阅读下方详细验收记录。

本目录保存两次经授权的真实模型产品运行。它是
P5-R001–P5-R003 的呈现集成证据，不是新的
行为质量门禁。Phase 4.3.1 官方仍是真实模型行为
记录（80 个 Agent slots 上 `completed/meets_target`，并披露 2/80 与 1/80）。

此处记录的状态：`real_demo_completed`。

## 运行（恰好两次；无重跑）

两次运行均使用公开 `RealLLMPlanner`，配合 `deepseek` /
`deepseek-v4-flash` / `v0.2-s1-planner-8.1`（`phase4_certified_default=true`）。
两次运行均未使用 `ScriptedPlanner`。两次运行均未为改变
诊断而重复。结果按产生时原样保留。

默认问题：`Why does this signal sound distorted?`
默认通道：`mixdown`。

本地 `DEEPSEEK_API_KEY` 已存在（值未记录）。产品绑定
默认 `127.0.0.1:8000` 返回 Windows `WinError 10013`（绑定权限 /
排除端口）。同一产品 CLI 以
`signal-diag serve --host 127.0.0.1 --port 8765` 启动一次。这是显式
受支持的 `--port`，不是产品回退。

| ID | Path | Source | App `run_id` | Agent result `run_id` | Result | Outcome | Claim |
|---|---|---|---|---|---|---|---|
| P5-R001 | Web UI, public preset `clipping` | `synthetic` / `clipping` | `run_02841350c97647f6953466efb22ead64` | `run_65f04c39aca2` | `success` / `planner_finished` | `supported_fault` / `high` | `claim_clip_odd_1` fault `clipping` |
| P5-R002 | CLI supported PCM WAV | `wav` / `input_clipping_16bit.wav` | `run_93042771d3204fb7813795a330ae40a7` | `run_2a9dd1cdb72c` | `success` / `planner_finished` | `supported_fault` / `high` | `claim_clip_odd_1` fault `clipping` |

诚实 claim 文本（不是正确性 SLA）：

- Synthetic：clipping 由同次运行 Evidence 肯定支持；奇次
  3 与 5 视为 clipping 产物；THD 规则 FAIL 在没有可报告的 order-2 Evidence 时，
  并不单独构成独立 `harmonic_distortion` 原因。
- WAV：结构相同；措辞在第一句省略 “by same-run Evidence”。

两次运行共享的诚实细节：

- 7 个严格 trace 事件：planner, observation, planner, observation, planner,
  rule, planner。
- 12 个 Evidence 项；在 `profile_s1_distortion`
  `1.0.0-demo` 上 5 次规则评估；0 次知识检索；0 错误；0 警告；空
  limitations。
- 波形预览为 `visualization_only`（从 48000 samples 取 1000 points）。
- JSON 解析为 `DiagnosisReport` schema `1.0.0`。Claim 与 trace 引用
  在同一报告中可解析。HTML 自包含（内联 style，无
  `http://` / `https://` / script）并对外部文本转义。

合成运行的 JSON 与 HTML 经由同一已完成
应用运行的 `/api/v1/runs/{run_id}/report.json` 与 `report.html` 下载。这两次
渲染的 `generated_at` 相差几毫秒，因为每个端点
独立盖戳报告。那不是第二次诊断。

WAV JSON 从 CLI stdout 捕获。捕获 shell 添加的 UTF-8 BOM
已剥离；JSON 对象未重写。

## P5-R003 UI

主 Web UI 为应用运行
`run_02841350c97647f6953466efb22ead64` 提交了一次 `clipping` preset。三张经净化的 PNG 记录
同一已完成页面。未提交新诊断；补充截图从原始 `:8765` serve
进程恢复仍可用的已完成运行（捕获前经 `/api/v1/runs/{run_id}` 校验运行状态）。

| File | Shows |
|---|---|
| `ui_completed.png` | Input form, download links, lifecycle `completed` |
| `ui_diagnosis_sections.png` | Lifecycle `completed`, diagnosis (`supported_fault` / clipping), waveform preview, trace (7 events), observations, evidence (12), rules (5), knowledge (0 retrievals) |
| `ui_evaluation_panel.png` | Accepted evaluation summary: `completed/meets_target`, 80 slots, 2/80 behavioral-failure slots, 1/80 outcome error, demonstration-target disclaimer |

`ui_completed.png` 仍是原始 Task 14 视口截图。两张
补充 PNG 的加入，是因为仅该视口不足以满足
对 diagnosis/trace/evidence/rules/knowledge 与
Evaluation 披露的独立 P5-R003 审查。

这些 PNG 均不含凭证、本地用户名路径、原始 provider 正文，
或未净化堆栈跟踪。

## 文件（已提交字节的 SHA-256）

| File | SHA-256 | Bytes |
|---|---|---:|
| `input_clipping_16bit.wav` | `970c37cc879b32fea80f66cdbc31305b45d04c654b53fbf0633e4ed4dcdf416e` | 96044 |
| `synthetic_report.json` | `824fce315601f3c6ecf050641dbd823cac2c4a5af56eeac1bb433dec95000895` | 89497 |
| `synthetic_report.html` | `f943f36643bfcad0a4712a434197ff523e8dc7776b770d9353a7569ce8f04bc0` | 9073 |
| `wav_report.json` | `4de2f827e0e073abb359a34bfcb45c6dba10ea653a0195fcd41a9746db292962` | 87664 |
| `wav_report.html` | `68f95681fa6ffc3556c2d4a8bcb5ab988714fbd23e598a528c7c262e0a06a8d4` | 9061 |
| `ui_completed.png` | `0bc394ac1eb08274bd015c7a3e94819ffc0de71443ab9ae65bd487bbb23e312d` | 87213 |
| `ui_diagnosis_sections.png` | `b450b4d84d93cffa7e5183351374697e5c60793940bda9c02ce4a558819e5acd` | 271574 |
| `ui_evaluation_panel.png` | `34d9997711d8c475ccdb8f01bc6c73d3cf8ac138b32210158211725906c658be` | 17372 |

WAV 元数据：48 kHz，mono，16-bit PCM，48,000 frames，1.0 s。该文件是
公开 Demo clipping encoder 输出；摘要与 Task 12 encoder
字节匹配。

## 这不是什么

- 不是为改进而重跑的门禁。
- 不是 `ScriptedPlanner` 回退。
- 不是 Phase 5 / V0.2 终端验收（Task 15）。
- 不是声称这两次诊断构成新的官方基准。
- 不是授权推送、合并、删除工作树，或清理 `build/`。
