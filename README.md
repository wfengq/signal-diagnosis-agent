# Signal Diagnosis Agent

V0.2 local Demo for Scenario **S1**: explain why a periodic audio-like signal
sounds distorted. The product path uses a Hybrid Agent over deterministic
signal analysis. It is a demonstration system, not a production audio-QA,
chip-validation, or standards-compliance tool.

## Scope

Supported public Demo inputs:

- five packaged synthetic presets (`clean_periodic`, `clipping`,
  `harmonic_distortion`, `combined_distortion`, `noise_inconclusive`);
- little-endian integer-PCM WAV uploads (see WAV limits below).

The Agent diagnoses clipping and/or harmonic distortion, or reports
inconclusive / no-supported-fault, using same-run Evidence, versioned rule
judgments, and curated knowledge citations. Raw waveforms and full FFT arrays
are never sent to an LLM.

## Architecture

```text
signal -> dsp -> tools -> rules/knowledge -> agent -> evaluation -> app
```

- `signal/` owns representation, repository, segmentation, synthetic cases, and
  WAV ingestion.
- `dsp/` owns deterministic numerical algorithms.
- `tools/` adapt DSP into compact Evidence.
- `rules/` apply versioned PASS/FAIL/NOT_APPLICABLE thresholds.
- `knowledge/` is a curated local Markdown corpus with keyword/tag retrieval.
- `agent/` owns `RealLLMPlanner` and deterministic runtime control.
  `ScriptedPlanner` is a test double only and is never a silent product fallback.
- `evaluation/` owns the Phase 4 harness and the packaged Phase 4.3.1 summary.
- `app/` is a thin presentation layer: one `DiagnosisApplicationService`, a
  FastAPI adapter, an argparse CLI (`signal-diag`), and a packaged native Web UI.

Core install does not require FastAPI. Web serving uses the `app` extra. The
OpenAI-compatible DeepSeek client uses the `llm` extra.

## Status (honest)

| Gate | Status |
|---|---|
| Phase 1–3 deterministic foundation | accepted |
| Phase 4.3.1 official held-out (80 Agent slots) | `completed/meets_target` with 2/80 and 1/80 disclosure below |
| Phase 5 presentation implementation | **accepted** on `phase5-presentation-engineering` |
| `presentation_harness_accepted` | **accepted** after local CPython 3.11/3.12 clean-environment verification |
| Real product Demo (`real_demo_completed`) | **completed** — two honest public `RealLLMPlanner` runs; see `docs/demo/phase5/v0_2_acceptance` |
| Terminal V0.2 status | `presentation_harness_accepted` / `real_demo_completed` / Phase 5 accepted; V0.2 complete resume-grade demonstrable vertical slice |

Do not treat this README as a production-readiness statement.

## Install

Requires **Python 3.11 or 3.12**.

From a clone:

```text
python -m pip install --upgrade pip
python -m pip install ".[app,llm]"
```

Optional development tools (pytest, Ruff, mypy, `build`):

```text
python -m pip install ".[app,llm,dev]"
```

Core DSP/rules/knowledge/agent install remains `pip install .` and does not
pull FastAPI.

## Configure and start the local Demo

The product planner is DeepSeek `deepseek-v4-flash` with prompt
`v0.2-s1-planner-8.1`. Set a local key; do not commit it.

```text
set DEEPSEEK_API_KEY=<your-key>
signal-diag serve
```

Default bind is `127.0.0.1:8000`. Open that localhost URL in a browser.

Optional:

```text
signal-diag serve --host 127.0.0.1 --port 8000
```

**Warning: local single-user/no-auth service. Do not expose this server to an
untrusted network.** There is no authentication, CORS is off by default, and
there is no public-network safety claim.

Health, presets, the accepted evaluation summary, and the static UI load
without credentials. Submitting a diagnosis requires `DEEPSEEK_API_KEY`.
Missing credentials return a configuration error; the product path never falls
back to `ScriptedPlanner`.

## CLI

```text
signal-diag presets
signal-diag diagnose synthetic clipping
signal-diag diagnose wav path\to\file.wav
signal-diag diagnose wav path\to\file.wav --channel mixdown --output json --html-output report.html
```

Default question: “Why does this signal sound distorted?” Default channel:
mixdown. Exit 0 is a valid completed Agent result (including inconclusive /
no-supported-fault). Exit 1 is an Agent/runtime or application failure. Exit 2
is usage, input, or configuration error.

## WAV support and limits

| Property | Value |
|---|---|
| Container | little-endian RIFF/WAVE |
| Encoding | integer PCM; extensible PCM with PCM subtype |
| Bit depth | 8, 16, 24, or 32 |
| Channels | 1 or 2 |
| Sample rate | 8 kHz–192 kHz |
| Max upload | 20 MiB |
| Max frames | 2,000,000 |
| Max duration | 30 s |
| Conversion | exact full-scale float32; **no peak normalization** |
| Rejected | RIFX, RF64, IEEE float, compressed, more than two channels |

Malformed containers raise invalid-WAV errors. Valid files outside rate/frame/
duration bounds raise signal-limit errors. The next byte above 20 MiB is
rejected as payload-too-large without retaining a run.

## Actual dynamic trace

The UI, JSON, and HTML reports show the **actual chronological Agent trace**
from the same run: planner decisions, observations/Evidence, rule evaluations,
and knowledge retrievals. Queued/running views show only real lifecycle state
and never simulate Tool progress. External strings are inserted as text, not
HTML.

## Reports

Canonical JSON and self-contained HTML reports are produced from the same
application models. Download them from the Web UI after a terminal run, or
write HTML from the CLI with `--html-output`.

## Phase 4.3.1 accepted evaluation (honest)

Packaged snapshot identity:
`bench_official_s1_v12_planner8_1_gate5` on dataset `s1-distortion-synthetic`
`1.2.0`, prompt `v0.2-s1-planner-8.1`, model `deepseek-v4-flash`, scoring
`2.0.0`.

- Official Agent path: 80 held-out slots, `benchmark_status=completed`,
  `target_status=meets_target`.
- **2/80** Agent slots carry non-blocking behavioral failure codes on
  `case_v12_held_noise_02` (slot 1: `redundant_rule;inappropriate_replan`,
  outcome correct; slot 5: `required_knowledge_omitted;outcome_mismatch`).
- **1/80** is the sole wrong outcome (slot 5 above). Aggregate remains
  `completed/meets_target`.
- Demonstration targets are not industry standards or SLAs.

The UI Evaluation panel is required to show these facts, including the 2/80
and 1/80 disclosures. It must not hide failures.

## Deterministic versus real Demo gates

- **Deterministic presentation harness** (`presentation_harness_accepted`)
  requires T001–T285, Ruff, mypy, architecture, wheel smoke, and Python
  3.11/3.12 local clean-environment verification. That state is **recorded**
  after both local clean environments passed. Hosted GitHub Actions is
  optional and is not required.
- **Real product Demo** (`real_demo_completed`) is a separate non-CI gate:
  one public synthetic preset and one supported PCM WAV, each once, through
  public `RealLLMPlanner`. That gate is **recorded** after the two honest
  Task 14 runs. Individual diagnoses are retained as produced and are not a
  new official benchmark.

Recorded artifacts:

```text
docs/demo/phase5/v0_2_acceptance
```

See [`docs/demo/phase5/v0_2_acceptance/README.md`](docs/demo/phase5/v0_2_acceptance/README.md)
for run identities, honest outcomes, sanitization notes, and file hashes.

## Demo thresholds disclaimer

Rule profile `profile_s1_distortion` `1.0.0-demo` uses demonstration settings
(1% clipping, 5% THD). These are **not** industry standards, product SLAs, or
chip-acceptance criteria.

## Limitations

- S1 distortion only; not a general audio or hardware test platform.
- Synthetic presets and bounded PCM WAV only; no arbitrary production captures
  as a validated corpus.
- F0 estimation is an autocorrelation baseline, not a universal pitch tracker.
- Local no-auth Demo; not multi-user, not networked, not authenticated.
- No Docker, no database, no vector search, no multi-agent runtime.
- Historical Phase 4 official v1.0.0 remains immutable `below_target`; Phase
  4.3.1 is the accepted product-behavior gate and still discloses 2/80 and 1/80.

## Resume bullets (truthful)

- Built a layered signal-diagnosis agent (DSP → tools → versioned rules →
  knowledge → planner runtime → evaluation → local app).
- Official Phase 4.3.1 held-out: 80 Agent slots `completed/meets_target`, with
  honest 2/80 behavioral-failure and 1/80 outcome-error disclosure.
- Added a local FastAPI + native Web UI + CLI presentation layer over one
  application service, with packaged wheel assets and secret-free CI.
- Recorded two honest real-model product Demo runs (Web UI `clipping` preset
  and one supported PCM WAV) under `docs/demo/phase5/v0_2_acceptance`.
- Recorded terminal V0.2 status: Phase 5 accepted as a resume-grade
  demonstrable vertical slice. Push and merge remain unauthorized.
- Did **not** claim production audio QA, chip validation, or standard-setting
  thresholds.
