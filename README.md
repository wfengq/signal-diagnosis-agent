# Signal Diagnosis Agent

[中文对照](README.zh-CN.md)

A reproducible, evaluated, and interactive narrow-domain Agent that answers:
**“Why does this periodic signal sound distorted?”**

The product path uses a real LLM to select DSP, rule, and knowledge actions
dynamically. Deterministic DSP owns every numeric result, versioned profiles own
thresholds, and every supported diagnosis must cite same-run evidence. A
scripted planner is injectable for state-machine and tool-execution tests; it is
never a silent product fallback.

> V0.2 is a resume-grade demonstrable vertical slice, not a production audio-QA,
> chip-validation, or standards-compliance product.

![Completed local Web UI run](docs/demo/phase5/v0_2_acceptance/ui_completed.png)

![Accepted evaluation with disclosed failures](docs/demo/phase5/v0_2_acceptance/ui_evaluation_panel.png)

<details>
<summary>Open the full diagnosis, trace, Evidence, rules, and knowledge screenshot</summary>

![Full diagnosis with trace, evidence, and rules](docs/demo/phase5/v0_2_acceptance/ui_diagnosis_sections.png)

</details>

## What is implemented

- Synthetic periodic signals and bounded integer-PCM WAV input.
- Deterministic clipping, spectrum, fundamental, and harmonic analysis.
- Compact Evidence adapters; raw waveforms and full FFT arrays never reach the
  LLM.
- Dynamic `RealLLMPlanner` decisions with observation-driven replanning and
  explicit stopping.
- Versioned PASS/FAIL/NOT_APPLICABLE rules and a curated local knowledge index.
- Scripted deterministic acceptance plus separate real-model behavior
  evaluation against an honest fixed pipeline.
- One shared application service exposed through argparse CLI, FastAPI, a native
  Web UI, JSON, and self-contained HTML reports.

## Architecture

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

The dependency direction is enforced by architecture tests. `signal`, `dsp`,
`tools`, `rules`, and `knowledge` do not depend on Agent or LLM frameworks.

## Verified result

V0.2 terminal state:

```text
presentation_harness_accepted
real_demo_completed
Phase 5 accepted; V0.2 complete resume-grade demonstrable vertical slice
```

Deterministic acceptance:

- T001–T285: **1006 passed**, zero required skip/xfail.
- Local clean-environment matrix: CPython **3.11** and **3.12**.
- Ruff, mypy, architecture checks, diff-check, and wheel smoke passed.
- Hosted GitHub Actions is optional and was not used as an acceptance input.

Official real-model behavior evaluation:

- DeepSeek `deepseek-v4-flash`, public `RealLLMPlanner`, prompt
  `v0.2-s1-planner-8.1`.
- Dataset `s1-distortion-synthetic` 1.2.0, scoring 2.0.0.
- Development gate: 40 Agent slots, 40/40 correct outcomes, all 11 target
  bands passed. This split was used for behavior development and is not
  held-out evidence.
- 80 held-out Agent slots: `completed/meets_target`.
- Causal macro F1 1.0; evidence grounding 1.0; first-tool selection 1.0;
  timely stopping 1.0; unnecessary Tool action rate 0.0; unsupported claim
  rate 0.0.
- Outcome accuracy 79/80. Two slots contain disclosed non-blocking behavior
  failure codes; one of them is the sole wrong outcome. These facts remain
  visible in the UI and committed evaluation bundle.

The first Phase 4 official benchmark and the v5–v8 development misses remain
committed. They are engineering evidence, not hidden or rewritten results.

## Incremental external/contextual validation

After V0.2 acceptance, a separate incremental study examined the main external
validity limitation: the accepted official dataset was synthetic. The first
V0.2 external-WAV campaign used public recordings and controlled distortions
but remained `below_target`, primarily because single-WAV THD evidence could
not reliably distinguish newly introduced harmonic distortion from harmonic
content already present in the recording. That result remains preserved.

V0.3 added explicit `paired_reference` and `nominal_single_tone` context without
expanding beyond Scenario S1. Its frozen v9.11 validation ran 20 cases across
three arms (60 total slots): contextual Agent, truth-free fixed pipeline, and
no-context ablation. After an append-only correction to two incorrectly
implemented claim-level scoring denominators, the contextual Agent met every
preregistered aggregate and role gate:

- planner completion 19/20;
- outcome and causal exact-set accuracy 16/17;
- causal macro-F1 0.955;
- harmonic recall 5/5 and clipping recall 5/6;
- evidence grounding 21/21 and unsupported positive claims 0/10;
- paired harmonic causal advantage over no-context ablation: +4 cases.

The original generated `below_target` files, the scorer defect, the corrected
implementation, and the append-only `meets_target` verdict are all retained.
This is a small external/contextual validation, not an official benchmark,
industrial validation, production certification, or a replacement for V0.2.
See the [v9.11 validation acceptance report](docs/evaluations/v0_3/contextual/V9_11_CONTEXTUAL_VALIDATION_ACCEPTANCE_REPORT.md).

## Install

Requires Python 3.11 or 3.12.

```text
python -m pip install --upgrade pip
python -m pip install ".[app,llm]"
```

For tests and packaging:

```text
python -m pip install ".[app,llm,dev]"
```

Core DSP/rules/knowledge/agent installation remains `pip install .` and does
not pull FastAPI.

## Run the local Demo

The product planner requires a local DeepSeek API key. Never commit it.

```text
set DEEPSEEK_API_KEY=<your-key>
signal-diag serve --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765`. Port 8765 is used in the retained Demo because
port 8000 was unavailable on the acceptance machine.

The health endpoint, presets, accepted evaluation summary, and static UI load
without credentials. Diagnosis submission without credentials returns a
configuration error; the product path does not fall back to `ScriptedPlanner`.

**This is a local, single-user, no-auth service. Do not expose it to an
untrusted network.**

## CLI

```text
signal-diag presets
signal-diag diagnose synthetic clipping
signal-diag diagnose wav path\to\file.wav
signal-diag diagnose wav path\to\file.wav --channel mixdown --output json --html-output report.html
```

Default question: “Why does this signal sound distorted?” Default channel:
mixdown. Exit 0 is a valid completed Agent result, including inconclusive or
no-supported-fault. Exit 1 is an Agent/runtime or application failure. Exit 2
is a usage, input, or configuration error.

## WAV boundary

- Little-endian RIFF/WAVE, integer PCM or extensible PCM with PCM subtype.
- 8/16/24/32 bit, mono or stereo, 8 kHz–192 kHz.
- Maximum 20 MiB, 2,000,000 frames, and 30 seconds.
- Exact full-scale `float32` conversion; no per-signal peak normalization.
- RIFX, RF64, IEEE float, compression, and more than two channels are rejected.

## Where to read the code

Follow one request vertically rather than reading every module:

1. `src/signal_diag/app/cli.py` and `app/composition.py` — product entry and
   dependency assembly.
2. `app/service.py` — WAV/preset request to one Agent run.
3. `agent/models.py`, `agent/planner.py`, and `agent/runtime.py` — decisions,
   model boundary, state machine, limits, and termination.
4. `tools/service.py` into `dsp/clipping.py` or `dsp/harmonics.py` — deterministic
   computation becoming Evidence.
5. `rules/engine.py` and `knowledge/index.py` — configured judgments and
   deterministic retrieval.
6. `evaluation/runner.py` and `evaluation/scoring.py` — deterministic and live
   evaluation.
7. `tests/agent/test_s1_acceptance.py` and
   `tests/test_architecture_boundaries.py` — end-to-end contract and dependency
   proof.

See the [documentation index](docs/README.md) for reviewer, developer, and
historical reading paths.

## Evidence and reports

- [Engineering case study](docs/PROJECT_CASE_STUDY.md)
- [Phase 5 real Demo artifacts](docs/demo/phase5/v0_2_acceptance/README.md)
- [Accepted official Phase 4.3.1 bundle](docs/evaluations/phase4_3_1/official/bench_official_s1_v12_planner8_1_gate5/)
- [Architecture](docs/ARCHITECTURE_V0_2.md)
- [Frozen contracts](docs/CONTRACTS_V0_2.md)
- [Acceptance plan T001–T285](docs/TEST_PLAN_V0_2.md)
- [Design decisions D001–D031](docs/DECISIONS.md)

## Honest limitations

- S1 distortion only; this is not a general audio or hardware-test platform.
- Synthetic cases and bounded PCM WAV are supported; arbitrary production
  captures are not a validated corpus.
- F0 is an autocorrelation baseline, not a universal pitch tracker.
- Rule profile `profile_s1_distortion` 1.0.0-demo uses 1% clipping and 5% THD
  demonstration settings, not industry standards or SLAs.
- Local-only, no authentication, no database, no Docker, no vector search, and
  no multi-agent runtime.
- The accepted official run still discloses two behavior-coded slots and one
  wrong outcome out of 80.
- The V0.2 external-WAV increment remained `below_target`; the later v9.11
  contextual result applies only to its frozen 20-case study and includes one
  retained behavioral failure.
