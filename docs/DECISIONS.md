# Architecture and Development Decisions

**Status:** Active  
**Current architecture version:** V0.2  
**Last updated:** 2026-08-31

This file records approved decisions that affect implementation. Historical V0.1
documents are preserved under `docs/archive/v0.1/`.

## D001 — Use a modular monolith

**Decision:** Organize the project as one Python package with strict dependency
boundaries rather than graph-first scaffolding or separate services.

**Direction:**

```text
signal → dsp → tools → rules/knowledge → agent → evaluation → app
```

Only modules required by the current phase are created.

## D002 — Implement the project in five gated phases

**Decision:** Deliver in this order:

1. deterministic signal-analysis foundation;
2. minimal end-to-end distortion-diagnosis Agent;
3. deterministic rules and small knowledge/RAG;
4. evaluation and Agent-versus-fixed-pipeline comparison;
5. API, UI, and reporting.

Later phases do not begin before the previous phase passes its required tests.

## D003 — Freeze S1 as the first end-to-end scenario

**Decision:** Scenario S1 asks why a synthetic periodic signal, and later a WAV
file, sounds distorted.

The initial supported diagnosis space is clipping, harmonic distortion, combined
distortion, no supported fault, and inconclusive. Fundamental evidence is
collected only when it supports the diagnosis.

## D004 — Dynamic tool selection is required

**Decision:** S1 does not require a fixed clipping → FFT → F0 → THD pipeline. The
product Agent selects the first Tool, inspects structured observations, replans
when justified, and stops when evidence is sufficient.

A fixed pipeline exists only as the Phase 4 comparison baseline.

## D005 — Use a Hybrid planner boundary

**Decision:** `PlannerModel` is the explicit model boundary.

- `RealLLMPlanner` is the product Agent path.
- `ScriptedPlanner` is a deterministic test double for runtime acceptance.
- Product failure never silently falls back to `ScriptedPlanner`.
- Required CI does not depend on stochastic LLM behavior.

## D006 — Keep numerical computation deterministic

**Decision:** Raw waveform and full FFT arrays never enter model context. DSP
code alone calculates clipping, spectrum, fundamental, harmonic, and THD
metrics. LLM output cannot create numerical Evidence or invent thresholds.

## D007 — Make Evidence traceability a Phase 1 capability

**Decision:** Tool adapters create compact deterministic Evidence with source
Tool and call IDs. Every supported diagnosis claim must cite Evidence from the
same run.

## D008 — Add harmonic distortion to Phase 1

**Decision:** V0.2 Phase 1 includes harmonic and combined synthetic generators,
harmonic association, THD measurement, and an Agent-facing harmonic-distortion
Tool. Clipping, FFT, and F0 alone cannot accept S1.

## D009 — Separate deterministic acceptance from real-model evaluation

**Decision:**

- T001–T092 are deterministic required acceptance tests.
- T001–T063 define Phase 1 completion.
- T064–T092 define Phase 2 runtime/S1 deterministic completion.
- R001–R006 measure real-model behavior outside CI.

## D010 — V0.2 supersedes unreleased V0.1 public names

**Decision:** Preserve V0.1 documents as history, but implement only approved
V0.2 contracts. Do not add compatibility aliases for unreleased V0.1 Tool names
or the single-value `fault_type` model.

## D011 — Start knowledge retrieval small and deterministic

**Decision:** Phase 3 begins with curated local Markdown plus deterministic
keyword/tag retrieval. Embeddings and vector databases are optional later
changes, not initial requirements.

## D012 — Presentation engineering comes last

**Decision:** WAV upload, API, UI, and HTML reporting are Phase 5 adapters over
the validated core. They must not duplicate DSP, rules, or Agent runtime logic.

## D013 — Preserve truthfulness of project claims

**Decision:** The project remains planned or partially implemented until its
actual code, tests, evaluation, and Demo exist. Synthetic signals are described
as synthetic and must not be presented as real chip or production test data.

## D014 — Freeze Phase 3 rules and knowledge contracts

**Decision:** OQ-001 is approved. `CONTRACTS_V0_2.md` §32–§40 and
`TEST_PLAN_V0_2.md` T093–T124 are the frozen Phase 3 implementation and
acceptance authority.

Phase 3 uses deterministic rule profiles, keyword/tag knowledge retrieval,
optional injected runtime dependencies, and independent limits of four rule
evaluations and four knowledge retrievals per run. Phase 2-only runtime
construction remains compatible. The separate OQ-003 profile decision is
recorded in D015.

## D015 — Approve the S1 demonstration rule profile

**Decision:** OQ-003 is approved. The first profile is
`profile_s1_distortion`, version `1.0.0-demo`, with comparator expressions
interpreted as PASS conditions:

- `clipping_detected eq false`;
- `clipping_ratio lte 0.01`;
- `flat_top_detected eq false`;
- harmonic-analysis `valid eq true`;
- `thd_percent lte 5.0`, unit `%`.

These values separate the accepted synthetic S1 fixtures and are explicitly
demonstration limits, not industry standards. Changing any comparator or
threshold requires a new profile version. Boundary tests cover values below,
equal to, and above the 1% and 5% thresholds.

## D016 — Define V0.2 as the first demonstrable vertical slice

**Decision:** The long-term project vision remains an extensible Signal Test and
Fault Diagnosis Agent for audio, sensor, and generic sampled waveforms. V0.2 is
the first complete, demonstrable vertical slice of that platform; it does not
redefine the whole project as S1-only.

V0.2 completion includes the full S1 distortion-diagnosis path: Phase 3
deterministic rules and knowledge, Phase 4 versioned evaluation plus an
Agent-versus-fixed-pipeline comparison, and Phase 5 WAV/API/UI/reporting
adapters. The product path uses a real LLM; deterministic acceptance uses an
injected scripted/fake planner.

Within V0.2, supported diagnosis remains explicitly limited to clipping,
harmonic distortion, basic supporting frequency/fundamental evidence, no
supported fault, and inconclusive outcomes. Later versioned scenarios may add
noise/SNR, frequency drift, amplitude abnormalities, PCM/CSV inputs, and sensor
waveforms. Those later capabilities receive their own contracts and tests and
must not cause speculative compatibility code in V0.2.

## D017 — Isolate Phase 4 as a manifest-driven evaluation subsystem

**Decision:** Phase 4 adds `signal_diag.evaluation` above the accepted Phase 1–3
layers. It does not modify `PlannerModel`, `DistortionDiagnosisRuntime`, or
`AgentRunResult`.

An external `RecordingPlanner` wraps real or scripted planners and captures
pre-decision contexts. A trace assembler aligns those records with real
Observations, Evidence, rule batches, and knowledge retrievals. Ambiguous
chronology is an evaluator error; grouped summaries are not accepted as a
substitute.

The dataset manifest declares acceptable first Tools and alternative sufficient
Evidence sets, never one mandatory full Tool sequence.

## D018 — Use dual Phase 4 acceptance states

**Decision:** Phase 4 separates deterministic `harness_accepted` from real-model
`benchmark_completed`.

The deterministic harness uses ScriptedPlanner and required T001–T183. The
official product benchmark uses DeepSeek `deepseek-v4-flash`, 16 held-out cases,
and five fixed slots per case. Real-model target misses are recorded as
`below_target` but do not fail CI. Missing credentials leave `pending`; exhausted
infrastructure/evaluator failures leave `incomplete`.

Phase 5 remains gated until both states are satisfied.

## D019 — Keep causal truth separate from observations and require identifiable combined cases

**Decision:** Phase 4 cases store generator-injected `causal_faults` separately
from DSP-observable conditions. Diagnosis metrics use causal truth; DSP,
Evidence, and RuleEngine checks use observable truth.

Because clipping itself creates harmonics, every combined case must pass a
matched clipping-only control check using existing harmonic-component Evidence.
The control and separation tolerance validate dataset fairness only and are
never shown to the Agent or baseline.

## D020 — Compare against an honest fixed pipeline and publish immutable results

**Decision:** The fixed baseline always executes clipping analysis, harmonic
distortion analysis, and the same S1 profile. It does not use knowledge, FFT,
F0, manifest truth, or matched controls, and it is not patched to hide expected
clipping/THD ambiguity.

The baseline uses dedicated Phase 4 result models rather than representing a
non-Agent run with the Agent-only `planner_finished` termination reason.

Primary metrics are deterministic scorer outputs. Human review cannot edit
them. Official report bundles are append-only, retain all failures and
repeated-run variation, and describe V0.2 targets as demonstration targets
rather than standards or SLAs.

## D021 — Correct Phase 4.1 behavior by prompt only, on a fresh held-out set

**Decision:** Phase 4.1 is an additive behavior-calibration gate. The first
correction is prompt-only. Frozen Phase 1–4 public Planner, Runtime,
evaluation, scoring, and report interfaces remain unchanged.

The official v1.0.0 DeepSeek benchmark at `b68ec5e` remains an immutable
diagnostic baseline. Its honest `completed/below_target` result is not a
harness failure and is not accepted as product-quality behavior. Observed
failures may motivate general prompt policy, but that bundle is never reused
as proof that an improved prompt generalizes.

Phase 4.1 adds dataset `s1-distortion-synthetic` `1.1.0` with new case IDs,
signal parameters, random seeds, and request assignments. It does not copy
v1.0.0 held-out fixtures. Development uses 8 cases × 5 slots; the official
held-out run uses 16 × 5 slots once, after the candidate prompt is frozen.
Do not tune against or rerun the same held-out set after inspecting results.
A subsequent formal attempt requires a new semantic dataset version, fresh
held-out cases, a new prompt identity where applicable, and a new benchmark
ID.

The runtime does not force rule evaluation, knowledge retrieval, or a fixed
DSP sequence before `finish`. Causal distortion presence and configured rule
acceptance remain independent facts; rule PASS never erases supported causal
Evidence. Knowledge is required by observable invalid/not-applicable state,
never by planner-visible evaluation labels.

Phase 4.1 acceptance requires `completed/meets_target` on the new official
bundle and T001–T195 green. Phase 5 remains gated until that gate is
independently verified.

## D022 — Preserve v5 evidence and add one coherent prompt v6 campaign

**Decision:** The completed v5 development result at `f9392c2` is immutable
`completed/below_target` evidence. Do not rewrite v5, append another policy
block to it, redirect its campaign choices, or overwrite its gate1 report.

Phase 4.1 adds prompt `v0.2-s1-planner-6` as one complete coherent instruction.
It corrects the repeatable prompt contradictions around dual truth, unresolved
combined hypotheses, inconclusive knowledge citation, and no-fault semantics.
The correction remains prompt-only: public Planner, Runtime, DSP, Tool, rule,
knowledge, evaluation, scoring, target, and report contracts do not change, and
the runtime does not force an analysis action.

Private legacy planners preserve exact v4/v5 reproducibility. The existing
`phase4.1-development` and `phase4.1-official` routes remain v5. Additive
`phase4.1-v6-development` and `phase4.1-v6-official` routes carry distinct v6
prompt, hash, configuration, and benchmark identities.

The v1.1.0 development split may be reused because it is already tuning data;
the v1.1.0 held-out split remains sealed. The 40-slot v6 development gate2 must
reach `completed/meets_target` before the byte-identical candidate may run the
80-slot official held-out gate once. A development miss stops before held-out.
An official miss is retained honestly and is neither tuned against nor rerun.

T196–T200 enforce legacy identity, v6 semantic coherence, product-boundary
traceability and no leakage, additive campaign scheduling, and the cumulative
quality gate. Phase 5 remains gated until independent Phase 4.1 acceptance.

## D023 — Repair evaluation integrity before planner v7 calibration

**Decision:** The v6 development result remains immutable
`completed/below_target`, but its remaining misses are not treated as a purely
prompt-level defect. The first v7 draft was rejected because semantic case
labels reached PlannerContext through `signal_id`, some first-Tool expectations
depended on hidden case truth, and the Agent could not observe the matched
control used to prove a third-harmonic combined cause.

Phase 4.2 adds dataset `s1-distortion-synthetic` `1.2.0` with fresh case IDs,
signal parameter combinations, seeds, request assignments, and held-out cases.
For v1.2 Agent runs, deterministic opaque signal IDs contain no category or
split semantics. Identical initial Planner-visible inputs cannot carry
different acceptable-first-Tool requirements. Natural symptom cues may guide
selection without naming Tools or answers.

Combined v1.2 cases use symmetric synthetic clipping plus a reportable injected
even-order harmonic. This makes the separate harmonic cause observable in the
signal's own structured Evidence. The matched clipping-only control remains
dataset-quality metadata outside PlannerContext. For v1.2 only, an absent
filtered order-2 component in an otherwise valid control is zero; invalid
analysis is not. Historical dataset validation semantics remain unchanged.

After these integrity corrections, Phase 4.2 adds one coherent prompt
`v0.2-s1-planner-7`, canonical development/official campaigns, and a strict
identity-complete provenance gate. Existing targets, public Agent/Runtime/DSP/
Tool/rule/knowledge/evaluation/scoring/report contracts, provider, and model do
not change. v4/v5/v6 identities and bundles remain reproducible, and v1.1.0
held-out remains unexecuted.

The v1.2 development gate is tuning evidence; only a byte-identical
`completed/meets_target` candidate may run the v1.2 held-out gate once. Phase 5
remains gated until independent product-quality acceptance. This decision
authorizes the written Task 1 contract freeze only. Tasks 2–10, code changes,
real-model execution, and all held-out runs require a later explicit user
instruction.

Recorded Task 10 outcome (2026-08-30, bundle commit `71293a3`): Tasks 2–7 and
T208 are complete. Development gate3 is honest `completed/below_target`.
Official v1.2.0 held-out was not run. Phase 4.2 is not accepted. Phase 5
remains gated.

## D024 — Make planner v8 the final prompt-only calibration attempt

**Decision:** Phase 4.3 preserves the integrity-corrected v1.2 dataset,
PlannerContext, Runtime, DSP, Tools, rules, knowledge, scoring, targets,
provider, and model. It adds one coherent `v0.2-s1-planner-8` prompt and new
canonical development/official identities to correct the stable v7 behavior
misses in Tool efficiency, viable-hypothesis maintenance, combined-cause
coverage, and required invalid-result knowledge retrieval.

The controller does not force actions and ScriptedPlanner does not become a
product fallback. v4–v7 identities and bundles remain immutable. The v8
development identity runs once after deterministic gates. A development miss
stops before held-out and closes the prompt-only route; further work requires a
new written choice between changing the model and changing PlannerContext. A
passing candidate may run official once, and an official miss is not tuned
against or rerun. Phase 5 remains gated until product-quality acceptance and
separate authorization.

This decision freezes the written design only. Implementation and all model
runs require a detailed plan and separate explicit user authorization.

## D025 — Permit one v8.1 compliance correction with versioned scoring

**Decision:** The immutable v8 development result remains honest
`completed/below_target`, but it is not sufficient evidence that the approved
§53 product behavior exhausted the prompt-only route. T210 implemented a
global prohibition on clipping-only finish that contradicts §53's permitted
symptom-specific request scope. The legacy scoring proxy also excludes
structured invalid Evidence when judging whether a following NOT_APPLICABLE
rule action is timely.

Phase 4.3.1 is a one-time compliance exception to D024, not another open-ended
prompt iteration. It adds one complete `v0.2-s1-planner-8.1` prompt that uses
the existing TaskAssessment hypotheses to distinguish clipping-specific,
harmonic-specific, and broad requests. Causal fault types are affirmative only.
Clipping-generated odd harmonics and a THD rule failure do not establish an
independent harmonic cause; reportable order-2 Evidence remains required.

The correction also adds internal scoring policy `signal_diag.scoring 2.0.0`
through existing `BenchmarkConfig.sdk_versions`. It recognizes valid or
invalid/not-applicable structured Evidence as RuleEngine input when scoring
rule timing and replanning. Public scoring signatures, score/report models,
all other formulas and failure codes, and TargetBands remain unchanged.
Historical configurations use legacy scoring, so v4–v8 fingerprints, trace
scores, and bundles remain reproducible.

Canonical identities are `phase4.3.1-v8.1-development` /
`bench_phase4_3_1_dev_v8_1_v12_gate5` and
`phase4.3.1-v8.1-official` /
`bench_official_s1_v12_planner8_1_gate5`. Dataset 1.2.0, provider, model,
profile, parameters, and repetitions do not change. Development may run once
after T001–T223 and all static gates. A development miss ends the prompt route
and leaves official sealed. A passing byte-identical candidate may run official
once. An official miss is retained and not tuned against or rerun.

This decision freezes design and tests only. Implementation and every model
run require a detailed plan and separate explicit authorization. Passing Phase
4.3.1 authorizes Phase 5 design only, not implementation.

## D026 — Make a thin shared application service the Phase 5 product boundary

**Decision:** The Web UI is the primary V0.2 live Demo, with a versioned
FastAPI backend and an argparse CLI. All three converge on one
`DiagnosisApplicationService`; adapters do not independently compose or
reimplement Signal registration, Runtime execution, diagnosis, trace, or
reports.

The UI uses native packaged HTML/CSS/JavaScript and same-origin fetch. There is
no Node build or frontend framework. CLI calls the application service directly
and does not require the HTTP server. Product composition uses public
RealLLMPlanner. ScriptedPlanner is test/development injection only and never a
fallback.

This preserves the modular-monolith dependency direction and keeps Phase 5 a
presentation layer rather than a second diagnostic implementation.

## D027 — Use bounded in-process jobs and polling instead of streaming

**Decision:** Real-model diagnoses run through a bounded in-process FIFO
executor. The default permits one running and four queued jobs and retains the
latest twenty terminal runs. Lifecycle is
queued→running→completed/failed, state is monotonic, active jobs are never
evicted, and process restart clears all records.

The Web UI polls HTTP status. While a run is active it displays only its actual
lifecycle state; after completion it shows the verified chronological trace.
SSE/WebSocket semantics, cancellation, persistence, database, Redis, and task
queues are deferred. This gives responsive local Demo behavior without
changing the accepted Runtime into a streaming controller.

## D028 — Support a strict bounded PCM WAV subset

**Decision:** Phase 5 supports little-endian RIFF/WAVE integer PCM with mono or
stereo 8-, 16-, 24-, or 32-bit samples, including extensible PCM whose subtype
and valid/container bit widths are unambiguous. Conversion uses exact
full-scale scaling into canonical float32 and never peak-normalizes, truncates,
resamples, or repairs.

Inputs must be no more than 20 MiB, 2,000,000 frames, and 30 seconds, with
sample rate from 8 kHz through 192 kHz inclusive. Compressed, IEEE-float, RIFX,
RF64, malformed, over-channel, or over-limit input is rejected explicitly.
These are local Demo resource constraints, not industry quality limits.

Five deterministic public synthetic presets remain separate from evaluation
manifests. WAV and synthetic use the same application/runtime path after
canonical registration and requested whole-file channel selection.

## D029 — Reuse strict evaluation chronology for canonical product reports

**Decision:** Phase 5 exposes the accepted Agent branch of evaluation trace
assembly as additive public `assemble_agent_events(records, result)`.
`assemble_evaluation_trace` delegates to it, preserving all historical Phase
4 behavior. The product projects those events into a compact timeline rather
than inventing a fixed pipeline or creating a fake EvaluationCase.

One validated `DiagnosisReport` is the source for canonical JSON and
self-contained escaped HTML. Same-run Evidence/Rule/Knowledge references are
mandatory; unresolved refs fail report generation. Reports exclude secrets,
raw provider responses, full waveform, and full FFT data. Preview data is
bounded and marked visualization-only.

The UI also shows a packageable checksum-linked snapshot of the accepted Phase
4.3.1 official benchmark, including the two behavioral-failure slots and sole
wrong outcome. It never rescores or selectively hides failures.

## D030 — Require deterministic presentation and a separate real product Demo

**Decision:** Phase 5 acceptance has two states.
`presentation_harness_accepted` requires deterministic T001–T285, static
quality gates, wheel/clean-install smoke, and Python 3.11/3.12 secret-free CI.
`real_demo_completed` requires one public synthetic and one supported WAV run
through public RealLLMPlanner plus an actual Web UI presentation, with sanitized
strict Trace and JSON/HTML artifacts.

The real Demo is an integration check, not another small stochastic quality
benchmark; Phase 4.3.1 official remains behavior evidence. Individual Demo
outcomes are retained honestly, no fake fallback is permitted, and missing
credentials leave real Demo pending.

V0.2 may be called a complete demonstrable vertical slice only after both
states pass. D026–D030 and the complete written contract were approved under
OQ-010 on 2026-08-31. That approval authorizes implementation planning only;
source/test implementation, model runs, push, and merge still require the
completed detailed plan and a separate explicit execution choice.

## D031 — Accept local dual-version clean environments instead of hosted CI

**Decision:** D030's dual-interpreter requirement is satisfied by reproducible
local clean-environment full verification on CPython 3.11 and CPython 3.12.
Hosted GitHub Actions is optional automation and is **not** an input to
`presentation_harness_accepted`.

The committed verifier must, for each labeled interpreter:

1. prove `sys.version_info[:2]` is exactly `(3, 11)` or `(3, 12)`;
2. create a fresh virtual environment in system Temp;
3. install the project extras `[app,llm,dev]` with no provider secret;
4. from the repository working tree, run the same commands previously required
   of CI: `pytest -q -rxXs -p no:cacheprovider`, `ruff check --no-cache src
   tests scripts`, `mypy --no-incremental src`, and
   `scripts/verify_phase5_wheel.py`;
5. require zero failed, skipped, and xfailed tests.

`git diff --check 36ae7c9..HEAD` runs once against the repository. The
verifier never uses repository `build/` and never calls a real model.
No other D026–D030, T001–T283, wheel, architecture, or honesty requirement
is reduced.

Approved under OQ-011 on 2026-08-31.
