# Phase 5 real product Demo (Task 14)

This directory holds the two authorized real-model product runs. It is
presentation-integration evidence for P5-R001–P5-R003, not a new
behavior-quality gate. Phase 4.3.1 official remains the real-model behavior
record (`completed/meets_target` on 80 Agent slots, with 2/80 and 1/80
disclosed).

Status recorded here: `real_demo_completed`.

## Runs (exactly two; no rerun)

Both runs used public `RealLLMPlanner` with `deepseek` /
`deepseek-v4-flash` / `v0.2-s1-planner-8.1` (`phase4_certified_default=true`).
Neither run used `ScriptedPlanner`. Neither run was repeated to change the
diagnosis. Results are retained as produced.

Default question: `Why does this signal sound distorted?`
Default channel: `mixdown`.

Local `DEEPSEEK_API_KEY` was present (value not recorded). Product bind
default `127.0.0.1:8000` returned Windows `WinError 10013` (bind permission /
excluded port). The same product CLI was started once as
`signal-diag serve --host 127.0.0.1 --port 8765`. That is an explicit
supported `--port`, not a product fallback.

| ID | Path | Source | App `run_id` | Agent result `run_id` | Result | Outcome | Claim |
|---|---|---|---|---|---|---|---|
| P5-R001 | Web UI, public preset `clipping` | `synthetic` / `clipping` | `run_02841350c97647f6953466efb22ead64` | `run_65f04c39aca2` | `success` / `planner_finished` | `supported_fault` / `high` | `claim_clip_odd_1` fault `clipping` |
| P5-R002 | CLI supported PCM WAV | `wav` / `input_clipping_16bit.wav` | `run_93042771d3204fb7813795a330ae40a7` | `run_2a9dd1cdb72c` | `success` / `planner_finished` | `supported_fault` / `high` | `claim_clip_odd_1` fault `clipping` |

Honest claim text (not a correctness SLA):

- Synthetic: clipping affirmatively supported by same-run Evidence; odd-order
  3 and 5 treated as clipping products; THD rule FAIL does not create an
  independent `harmonic_distortion` cause without reportable order-2 Evidence.
- WAV: same structure; wording omits “by same-run Evidence” in the first
  sentence.

Shared honest details for both runs:

- 7 strict trace events: planner, observation, planner, observation, planner,
  rule, planner.
- 12 Evidence items; 5 rule evaluations on `profile_s1_distortion`
  `1.0.0-demo`; 0 knowledge retrievals; 0 errors; 0 warnings; empty
  limitations.
- Waveform preview is `visualization_only` (1000 points from 48000 samples).
- JSON parses as `DiagnosisReport` schema `1.0.0`. Claim and trace refs
  resolve in the same report. HTML is self-contained (inline style, no
  `http://` / `https://` / script) and escapes external text.

JSON and HTML for the synthetic run were downloaded from the same completed
app run via `/api/v1/runs/{run_id}/report.json` and `report.html`. Those two
renders have `generated_at` a few milliseconds apart because each endpoint
stamps the report independently. That is not a second diagnosis.

WAV JSON was captured from CLI stdout. A UTF-8 BOM added by the capture
shell was stripped; the JSON object was not rewritten.

## P5-R003 UI

The primary Web UI submitted the `clipping` preset once for app run
`run_02841350c97647f6953466efb22ead64`. Three sanitized PNGs document the
same completed page. No new diagnosis was submitted; supplemental captures
restored the still-available completed run from the original `:8765` serve
process (run state verified via `/api/v1/runs/{run_id}` before capture).

| File | Shows |
|---|---|
| `ui_completed.png` | Input form, download links, lifecycle `completed` |
| `ui_diagnosis_sections.png` | Lifecycle `completed`, diagnosis (`supported_fault` / clipping), waveform preview, trace (7 events), observations, evidence (12), rules (5), knowledge (0 retrievals) |
| `ui_evaluation_panel.png` | Accepted evaluation summary: `completed/meets_target`, 80 slots, 2/80 behavioral-failure slots, 1/80 outcome error, demonstration-target disclaimer |

`ui_completed.png` remains the original Task 14 viewport capture. The two
supplemental PNGs were added because that viewport alone did not satisfy
independent P5-R003 review of diagnosis/trace/evidence/rules/knowledge and
Evaluation disclosure.

None of the PNGs contain a credential, local username path, raw provider body,
or unsanitized stack trace.

## Files (SHA-256 of committed bytes)

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

WAV metadata: 48 kHz, mono, 16-bit PCM, 48,000 frames, 1.0 s. The file is the
public Demo clipping encoder output; the digest matches the Task 12 encoder
bytes.

## What this is not

- Not a rerun-to-improve gate.
- Not a `ScriptedPlanner` fallback.
- Not Phase 5 / V0.2 terminal acceptance (Task 15).
- Not a claim that these two diagnoses are a new official benchmark.
- Not authorization to push, merge, delete the worktree, or clean `build/`.
