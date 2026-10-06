# Architecture and Development Decisions

**Status:** Active
**Current architecture version:** V0.2 accepted; HEAD may run V0.3 contextual product identity
**Last updated:** 2026-10-06

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

## D032 — Separate V0.2 acceptance anchor from HEAD live product identity

**Decision:** V0.2 completion remains the dual acceptance state at commit
`b48790c` (tag target `ff16e2a` / `v0.2.0` when present). That product identity
is DeepSeek `deepseek-v4-flash` with prompt `v0.2-s1-planner-8.1`.

HEAD on `codex/v0.2-real-world-validation` (and successors) may ship the V0.3
contextual product path as the default `RealLLMPlanner` /
`build_product_service` wiring (`v0.3-s1-planner-9.11`,
`v9_11_mode_aware_no_fault_recovery`). Reports must show
`phase4_certified_default=false` whenever the live prompt is not the Phase
4.3.1 certified identity `v0.2-s1-planner-8.1`.

The V0.3 contextual validation `meets_target` result is additive evidence. It
does not replace the official 79/80 held-out bundle and does not authorize
rewriting sealed assets.

**Authorization:** User-approved V0.3 contextual design
(`docs/superpowers/specs/2026-09-04-v0-3-contextual-reference-diagnosis-design.md`
and later v9.x amendments) plus hygiene clarification authorized 2026-09-29.
Where a chat approval was not committed as a decision at the time, this entry
records the lasting outcome; gaps in contemporaneous OQ linkage are noted as
“approval not fully recorded in-repo at land time.”

## D033 — V0.3 automatic rule closure for product policies ≥ v9.7

**Decision:** For causal policies `v9_7_deterministic_rule_closure` and later
product policies, the runtime performs deterministic Tool-to-profile rule
closure and rejects planner `EvaluateRulesDecision`. This supersedes the
Phase 3 planner-owned rule-evaluation flow **for those product policies only**.
`CONTRACTS_V0_2.md` §38.3 remains frozen historical text for the V0.2 slice.
Scripted and historical campaign paths that still use manual `evaluate_rules`
keep that behavior under older policy identities.

Recorded under design
`docs/superpowers/specs/2026-09-05-v0-3-v9-7-deterministic-rule-closure-design.md`.
Related contract mapping: OQ-015 (resolved — hygiene 2026-09-29).

## D034 — Phase 4.3.1 certification marker names only v8.1

**Decision:** `_CERTIFIED_PROMPT_VERSION` in `app/composition.py` must equal
`v0.2-s1-planner-8.1`. It must not be set to any v0.3 prompt identity.
`phase4_certified_default` compares the live prompt string to that marker and
must stay false while HEAD defaults to v9.11.

## D035 — External WAV re-execution pins v8.1 planner subclass

**Decision:** `evaluation/external/runner.py` `_build_production_planner` must
construct `_Phase4V8_1RealLLMPlanner`, not the public `RealLLMPlanner` default,
so recorded external campaign identity (`v0.2-s1-planner-8.1`) matches the
system prompt actually sent on re-runs. Official Phase 4.3.1 runners already
follow this pattern.

## D036 — OQ-014 Option C single_signal flat-top clipping finish gate

**Decision:** Keep the strict DSP `clipping_mechanism` label unchanged. For
`single_signal` supported_fault clipping under policies that use
`_validate_clipping_supported` or `_validate_v910_clipping_supported`, accept
valid `flat_top_detected=true` Evidence plus a same-run substantial legacy
clipping-rule FAIL (`rule_clipping_ratio_acceptable` or `rule_flat_top_absent`)
when `clipping_mechanism` is false. `paired_reference` and
`nominal_single_tone` continue to require `test_clipping_mechanism` for clipping
claims. Sealed evaluation bundles and Workstream C mechanism gold labels remain
unchanged.

## D037 — Product definition: single-file default, context optional

**Decision (operator answers 2026-09-29):**

1. **Default experience:** single-file (`single_signal`) conservative diagnosis.
   Reference WAV (`paired_reference`) and declared single-tone stimulus
   (`nominal_single_tone`) are **optional upgrades**, not the only legitimate
   product mode. Rephrase V0.3 docs that called `single_signal` merely a
   “compatibility path”: it is the default user path; paired reference remains
   the strongest evidence mode when available.
2. **Built-in presets:** keep “unknown signal” semantics (option A). The
   `harmonic_distortion` preset may end `inconclusive` under HEAD single-file
   gates by design; do not inject generator-known stimulus into presets to make
   Demo look stronger than a real one-file user. Guidance after inconclusive is
   the remediation (shipped; see Implementation status below).
3. **Public quality claims:** until a separate held-out design is authorized,
   HEAD default-path quality numbers are not cited. The official **79/80**
   remains attached only to V0.2 acceptance at `b48790c` /
   `v0.2-s1-planner-8.1`. V0.3 contextual validation remains additive evidence.

**One-line product:** A hybrid diagnosis Agent for periodic-signal distortion:
deterministic DSP measures, versioned rules judge, a real LLM plans; with only
one file it can confirm clipping and must stay conservative on harmonic
attribution; with a clean reference or declared single-tone stimulus it can
support evidence-backed “added vs inherent” judgments.

**Not:** general audio QA / pass-fail production metrology / industry SLAs.

**Long-term vision:** D016 remains open (extensible signal test & fault
diagnosis). Noise/SNR, drift, sensors, CSV, etc. are not shipped.

**Implementation status (merged):**

1. Deterministic `context_guidance` on single-file `inconclusive` (CONTRACTS
   V0.3 §17; T-CX264–T-CX268; PR #10 / #11 evidence trail). Spec:
   `docs/superpowers/specs/2026-09-29-single-file-context-guidance-design.md`.
2. Web UI upgrade loop (CONTRACTS V0.3 §18; T-CX269–T-CX275; PR #12): Demo
   presets materialize as PCM WAV and submit via contextual `single_signal`;
   the UI holds test bytes and re-submits as `paired_reference` /
   `nominal_single_tone` from the guidance panel. Frozen V0.2
   `POST /api/v1/runs/synthetic` remains for compatibility; the Web UI product
   path no longer posts it. Spec:
   `docs/superpowers/specs/2026-09-30-d037-upgrade-loop-ui-design.md`.

Further product-behavior changes still require a new written design, contract
additions, test IDs, and explicit authorization.

## D038 — OQ-019 S1 planner-ablation study-shape freeze

**Decision (operator 2026-09-30):** Approve the revised study shape in
`docs/superpowers/specs/2026-09-30-s1-planner-ablation-utility-study-design.md`
for `study_s1_planner_ablation_dev_1`.

Frozen by this decision:

1. Research question: whether HEAD `RealLLMPlanner` earns its complexity versus
   a truth-free `fixed_pipeline` under matched conditions on fresh development
   cases.
2. Scored arms: `product_agent` and `fixed_pipeline` only.
   `scripted_agent` may appear later for harness acceptance and never enters the
   scored comparison.
3. Modes for the first freeze: `single_signal` on the D037 contextual entry
   path, plus `paired_reference` as the required upgrade arm.
4. Evidence root: additive `docs/evaluations/v0_3/planner_ablation/`.
5. Historical `ContextualFixedPipelineBaseline` and the contextual campaign
   adapter are reuse candidates. Matching of claim gates, D037 entry,
   deterministic report processing, and an independent scoring identity remains
   a prerequisite for attributable planner conclusions.
6. Study results do not authorize product planner replacement, gate softening,
   or sealed-bundle rewrites.

Not authorized by this decision:

- writing-plans (needs a separate documentation-only grant);
- additive CONTRACTS / TEST_PLAN IDs, harness code, or Scripted dry-run;
- RealLLM / campaign execution;
- executable protocol seal (case list, numeric bands, retries) before the later
  plan and preregistration.

Related: OQ-019 resolved as study-shape approved 2026-09-30.

## D039 — OQ-013 product-behavior path C (single-file observed facts)

**Decision (operator 2026-10-03):** Resolve the deferred OQ-013
**product-behavior** fork as path C. Do not restore v8.1 harmonic
`supported_fault` on `single_signal`. Keep prompt
`v0.3-s1-planner-9.11` and causal policy
`v9_11_mode_aware_no_fault_recovery`.

Approve the design in
`docs/superpowers/specs/2026-10-03-single-file-observed-facts-design.md`:

1. Extend contextual `context_guidance` with deterministic
   `observed_facts` copied from same-run valid Evidence.
2. Use a display whitelist independent of the §17 reason-selection metric
   set. First phase: `thd_percent` from `analyze_harmonic_distortion` only.
3. Empty `observed_facts` is valid. No zero-fill, no derived metrics, no
   soft diagnosis copy.
4. Frozen V0.2 DTOs and `diagnose wav` stay unchanged.
5. Implementation (later grant) must amend CONTRACTS_V0_3 §17, register
   tests from T-CX319 if still free, and append a new code-identity row
   when the live product-tree digest changes. Preserve prior identity rows
   (including D038 / PR #21). Digest change is not prompt/policy identity
   change and not quality certification.

**Not authorized by this decision:** product or contract implementation,
seal, RealLLM campaign, HEAD quality claims, planner-ablation budget or
ledger changes, or merge of an implementation PR.

Related: OQ-013 hygiene remains D032/D034/D035; product-behavior → D039.

## D040 — OQ-019/dev_2 reviewed SDK capability rebind to lock `openai==3.6.0`

**Decision (operator authorize-execute 2026-10-03):** Rebind the reviewed
observation capability identity in `provider_telemetry` from the prior
`openai==3.20.0` audit tuple to the lock-aligned installed
`openai==3.6.0` digests recorded in `RESOURCE_BOUNDS.md` §7, so
`build_audited_sdk_observation_profile().supported` is true when install
matches `uv.lock`.

Append-only product-tree bridge:
`d040_preseal_sdk_capability_rebind` in
`study_v0_3_contextual_dev_1/code_identity_amendment.json`. Prompt, causal
policy, DSP thresholds, and product diagnosis gates are unchanged.

**Not authorized by this decision:** inventing HTTP send factor `H` or token
ceilings; setting `model_mapping_accepted=true`; creating `protocol_seal/`;
RealLLM campaign; retargeting legacy `inspect_limits`.

Related: OQ-019 / D038 preseal residual `environment_rebind`.

## D041 — OQ-019/dev_2 residual preseal route acceptance and HTTP send factor `H`

**Decision (operator authorize-execute 2026-10-03, post-D040):** Close two
source-aware preseal blockers for `study_s1_planner_ablation_dev_2` without
changing product model strings, prompts, causal policy, or request payloads.

1. **Operator route acceptance (Task 6):** Written acceptance of the live route
   package already recorded in `PRESEAL_BUDGET_STATUS.md`: requested model
   `deepseek-v4-flash`, planner prompt `v0.3-s1-planner-9.11`, causal policy
   `v9_11_mode_aware_no_fault_recovery`, declared V4.1-Flash legacy mapping
   (`deepseek-v4.1-flash`). Study `ProviderLimitsBinding` may set
   `model_mapping_accepted=true` when bound to that identity. No `/models`
   probe and no product composition change.

2. **HTTP send factor admission:** Admit `H=21` (`http_sends_per_sdk_attempt`)
   from audited defaults on the reviewed lock-aligned install: OpenAI Async
   client enables redirect following; httpx `DEFAULT_MAX_REDIRECTS=20` →
   worst-case sends per SDK attempt `1+20`. Origin `sdk_default_audit`, scope
   `admitted`, `dependency_identity` `openai==3.6.0;httpx==0.28.1`. Updates
   `RESOURCE_BOUNDS.md` arithmetic and bound-fact JSON; closes
   `unproved_http_send_bound` on the source-aware board when proofs bind `H`.

**Still blocked (explicit):** all-outcome and per-send input/output token
ceilings; failed-attempt token exposure; formal `seal_ready=true` without token
proofs. Legacy `inspect_limits` unchanged.

**Not authorized by this decision:** creating `protocol_seal/`; RealLLM
campaign; retargeting legacy `inspect_limits`; inventing `max_tokens` or
product caps.

Related: D040 SDK rebind; OQ-019 preseal residual gates.

## D042 — S1 regression troubleshooting workbench (additive definitions)

**Decision (operator authorize-execute 2026-10-04, Phase A grant):** Register
additive V0.3 §22 and T-CX329–348 for a periodic-test-signal regression
troubleshooting workbench: independent bilateral measurement bundles, pure
comparison rules with descriptive-only product default, in-session cases, and
an independent uncqualified retest planner identity. Implementation proceeds
only under staged grants (Phase A Tasks 1–4; later B/C separately).

**Constraints preserved:** frozen V0.2 §§1–64; RealLLMPlanner product diagnosis
path and Scripted non-fallback; D037 single-file default; D039 observed facts;
v9.11 prompt/causal policy; demo diagnosis thresholds are not comparison
tolerances; baseline WAV is not automatic clean `paired_reference`.

**Not authorized by this decision:** product comparison tolerance enablement;
retest level-parameter approval; RealLLM retest quality claims; Tasks 5–8
unless separately granted; commit/push/PR/merge/seal; rewriting sealed
evaluation or Demo assets.

Related: design
`docs/superpowers/specs/2026-10-04-s1-regression-troubleshooting-workbench-design.md`;
plan
`docs/superpowers/plans/2026-10-04-s1-regression-troubleshooting-workbench.md`.

## D043 — Regression full-scale check as a separate judged record (OQ-020)

**Decision (operator approval 2026-10-05, definitions only):** Register V0.3 §23 and
T-CX349–T-CX370. Regression comparison judges a comparison-specific
full-scale sample count and state in a separate immutable record, gated by
user declarations and a reviewed floor record. `clipping_ratio` is
permanently descriptive in comparison and no product profile may carry a
rule for it.

**This is an explicit amendment.** It narrows the reading of §22.2 "only"
and of the §22.3 rule shape; withdraws the possibility of a `clipping_ratio`
rule, which leaves `ComparisonRecord` overall pass permanently not true on
the product path; partly supersedes the D042 / §22.6 statement that product
tolerances and pass/fail are not authorized, by fixing what a floor record
tolerates and defining a judgment path, while authorizing no value; and
extends the §22.4 submit fingerprint, upload and snapshot shapes.

**Constraints preserved:** frozen V0.2 §§1–64; `ComparisonRecord` and its
validation; `MeasurementBundle` and `measurement_version`; `RetestLink`;
product `profile=None`; the single-file clipping detector, thresholds, v9.11
prompt and causal policy; D037/D039; the §22 block on `observed_variable`.

**Not authorized by this decision:** any floor, critical-zone or
approved-domain value; a characterization run; a judged product status;
sub-full-scale flat-top judgment; THD judgment; RealLLM; seal; merge.

**Known limits recorded with the decision:** the fact counts samples at the
threshold and does not tell a flattened waveform from a high unclipped level;
sub-full-scale clipping is invisible to it; all gating declarations are
unverifiable; 8-bit files and chains with any render-to-render variation get
no judgment; sample counts cannot be recomputed at validation.

Related: OQ-020; design
`docs/superpowers/specs/2026-10-05-s1-regression-clipping-comparison-semantics-design.md`
§12–§13 and
`docs/superpowers/specs/2026-10-05-s1-regression-layer1-characterization-materials-scoring-design.md`
§10–§11; amendment record
`docs/superpowers/specs/2026-10-05-s1-regression-full-scale-check-contract-amendment-draft.md`.

**Implementation status (merged 2026-10-05):** §23 stage 2 is implemented
under the operator's implementation grant: PR #41, squash commit `0770514` on
`codex/v0.2-real-world-validation` (independently reviewed, Accept at
`31ba78a`; implementation branch `cursor/s1-full-scale-check` retained for the
SHAs cited in the acceptance record). Plan:
`docs/superpowers/plans/2026-10-05-s1-regression-full-scale-check.md`
(revision 4); offline record:
`docs/REGRESSION_FULL_SCALE_CHECK_OFFLINE_ACCEPTANCE.md`. The product ships no
floor record (`PRODUCT_APPROVED_FULL_SCALE_FLOORS` is empty), so product checks
are `descriptive_only` or `not_comparable` only. Still not authorized at the
time of that merge: the layer-1 characterization run, any floor, critical-zone
or approved-domain value, floor approval, a judged product status, and every
item listed above as not authorized. Open follow-up at that time: OQ-021.
Product floor status is superseded by D044 (round_1 YAML registration).

## D044 — Approve round_1 full-scale method floor (OQ-021 A, OQ-022 B)

**Decision (operator approval 2026-10-06):** Close OQ-021 with Option A and
OQ-022 with Option B. Register the reviewed round_1 layer-1 freeze as the
product `FullScaleMethodFloor`, with the values below taken at full precision
from `docs/evaluations/v0_3/full_scale_characterization/round_1/freeze_record.json`
(digest `447751cee16da908ec179ab8966b3342ef273fc2a71028fb1ba01d07e585af06`).
Register T-CX381–T-CX386.

**Approved floor values (full precision; do not round):**

| Field | Value | Freeze source |
|-------|-------|---------------|
| `facts_version` | `v0.3-full-scale-facts-1` | product facts identity |
| `full_scale_threshold` | `0.99` | facts / characterization |
| `min_consecutive_samples` | `2` | facts / characterization |
| `min_samples_per_period` | `5.5125` | stage1 `domain.n_min` |
| `min_periods_in_range` | `1.0` | stage1 `domain.p_min` |
| `zone_below_threshold` | `0.0` | stage1 K2 `zone_below` |
| `zone_above_threshold` | `0.002004394531250009` | stage1 K2 `zone_above` |
| `zone_min_counted_samples` | `null` | stage1 K2 `min_counted` |
| `count_floor_samples` | `1280` | stage2 F2 `floor_params.value` |
| `count_floor_ratio` | `null` | F2 form |
| `tolerated_difference` | `one_step_of_coarser_depth_one_sided_plus_depth_conversion` | §23.4 fixed id |
| zone form / floor form | K2 / F2 | freeze `zone_form` / `floor_form` |
| stage1 row | `n=5.5125;p=1;K2` | freeze `zone_row_id` |

**OQ-021 Option A:** a floor applies only when both anchor sides have facts and
the three identity fields match. Missing facts on either side means the floor
is not applicable (`floor_missing`). Change only `_floor_identity_ok`.

**OQ-022 Option B:** keep the fixed minimum at one coarser-depth step. Append
to §23.4 that any approved floor record must have `zone_above` of at least one
16-bit step (`2^-15`). No change to `_in_critical_zone` or judgment logic.

**Mandatory disclosures (must accompany any product use of this floor):**

1. **Low sensitivity.** Freeze rationale: the 10% aggravation tier remains
   masked in 663/1728 pairs. Validation `rel_peak=0.1` tier:
   masked 684 of 1248 judged pairs (disclosures in
   `validation_report.json` / `.md`).
2. **Near-threshold clipping is not separable.** Validation M11 note: the
   existing outputs cannot distinguish a flattened from an unflattened sine at
   the threshold (characterization design §10.4).
3. **k=1 / k=2 flip counts.** Validation fixed-minimum totals: flips 4809,
   outside k=1: 0, outside k=2: 0
   (`disclosures.fixed_minimum_flip_totals`).
4. **Fundamental source.** Characterization uses the generated fundamental; the
   product uses the user-declared fundamental and does not check it (§10.6).
5. **Not an industry standard.** These floor, zone, and domain limits are
   demonstration / reviewed characterization values, not industry standards or
   SLAs.

**Constraints preserved:** frozen V0.2 §§1–64; `FullScaleMethodFloor` model
fields; critical-zone and judgment logic (except OQ-021 identity applicability);
no silent rewrite of sealed evaluation/Demo digests or T285 allowlists. Adding
a versioned floor YAML under `rules/profiles/` changes
`contextual_product_tree_sha256`; if V0.2 protection, T285, or sealed-identity
tests fail, stop and report without updating sealed hashes or allowlists.

**Tests:** T-CX381 (OQ-021 A), T-CX382 (OQ-022 B contract pin), T-CX383 (YAML
load + digest check), T-CX384 (YAML equals freeze values at full precision),
T-CX385 (product builder wires the floor; eligible checks judged with the
registered product floor), T-CX386 (registry equals loaded
YAML; supersedes empty-registry assertions of T-CX363/T-CX371 where they
conflict).

Related: OQ-021; OQ-022; freeze
`docs/evaluations/v0_3/full_scale_characterization/round_1/freeze_record.json`;
validation
`docs/evaluations/v0_3/full_scale_characterization/round_1/validation_report.md`.

## D045 — S1 agent-increment slice (definitions and offline implementation)

**Decision (operator 2026-10-06):** Approve the T1 free-text intake and T2
localized-fault slice, the three-arm increment as the primary metric, and the
§4.2 pass line from
`docs/superpowers/specs/2026-10-06-s1-agent-increment-design.md`. Budget control
is a call cap instead of a per-token proof. Caps are 1,500 HTTP calls for the
development stage, 1,008 for the held-out stage, and 21 per case (D041 `H`).
Crossing a cap stops the run and writes a stop record.

**Registered with this decision:** V0.3 §24 and T-CX387–T-CX398. Prompt
`v0.3-s1-planner-9.12` is the current v9.11 text plus segment and channel
drill-down guidance. Intake planner identity is `v0.3-s1-intake-1.0`. The
product default prompt stays `v0.3-s1-planner-9.11`. This slice does not switch
it.

**Constraints preserved:** frozen V0.2 §§1–64; v9.11 prompt text and its
existing code-identity rows; `DiagnosisClaim`, `PlannerContext`, and
`FullScaleMethodFloor` fields; Scripted non-fallback on every product planner;
nominal Hz only from verbatim user text, never from measured F0.

**Not authorized by this decision:** real-model development or held-out runs
(D1, H1); sealing the study; merging the implementation PR; treating offline
scripted-arm output as a RealLLM quality number.

Related: plan
`docs/superpowers/plans/2026-10-06-s1-agent-increment.md`.

**Supplement (2026-10-06, design §4.2):** T1 increment counts a case only when the first draft matches all four context fields before the simulated user corrects anything. Correction count stays a separate report. A downstream increment is the paired difference in diagnosis conclusions after confirmation. Offline diagnosis uses a scripted stand-in. The live runner uses the real planners. T1 ground-truth conclusions come from the reused contextual manifest (`expected_outcome`, `expected_causal_set`), including a real `inconclusive` only when that manifest says so. `ContextDraft.asked_fields` is the only list the simulated user treats as asked. A question string that merely contains a field name is not asked.

**Batch driver (2026-10-06, T-CX400–T-CX404):** `evaluation/agent_increment/live_campaign.py` runs a live stage (D1 dev, H1 held-out): fixed arms reuse the offline implementation, the agent arm uses the live runner under one stage ledger, and all three arms are scored by one definition per family. A cap stop or a transport failure ends the stage and keeps completed cases (report marked incomplete); an invalid intake draft is scored as wrong. A held-out run needs a matching prompt freeze record (stage F), writes to `<study>/runs/heldout_*` and runs once. The driver is ready; no live stage has been run, and D1, F and H1 each still need operator authorization. Fixed in the same change: the call guard now reaches the SDK at `chat.completions.create` (it previously called a root `create` that real SDK clients do not have).

**Batch driver review follow-ups (2026-10-06, independent read-only review of PR #54):**
- Diagnosis request: case texts correlate with the label in both families (every held-out T2 no-fault case reads "整段听着平稳", every T2 inconclusive case "我不确定这是不是故障"; T1 no-fault texts say the tone sounds clean). Every live diagnosis run therefore receives one neutral request (`DIAGNOSIS_REQUEST`, which asks for type, time segment and channel); fixed arms never read text. The T1 intake alone reads the case text, because reading it is the T1 task. The request's sha256 is part of the prompt freeze record, so H1 refuses if it changes after stage F.
- Localization: whole-file analysis never counts as localized, for every arm (the weak arm, and agent Evidence with no range or a range spanning the file).
- T1 downstream: in live stages the fixed arms' downstream conclusion is still the scripted stand-in judge, not the live planner. The downstream increment mixes intake context with diagnosis engine and is reported as secondary, not as a paired comparison. The primary T1 metric (first draft, before correction) is unaffected.
- Setup: preconditions, every case's decoded audio and fixed-arm rows, identity and the SDK client are settled before the output directory exists, so a setup failure (including an unreadable WAV) leaves nothing behind and cannot use up the single held-out run. Once the directory exists, the ledger, a report and (on abort) a stop record are always written, a write problem never replaces the original error, and a cap stop arriving wrapped in any exception type is still recorded as a cap stop. A dev run may not use a `heldout_` output name. Intake errors are scored as the model's answer only when the draft does not parse, fails validation or is empty; a malformed response or a harness-side error stops the stage.

**D1 round 1 intake fix (2026-10-06, T-CX405):** D1 round 1 (`runs/dev_r1`, PR #55, 49 HTTP calls) is kept as recorded, but its T1 numbers measure a harness defect, not the agent. Ten of twelve intake calls returned empty content and two returned unparseable drafts. The intake request omitted the settings the diagnosis planner sends: reasoning disabled, a JSON object response and temperature 0. With reasoning on, deepseek-v4-flash can spend the 800-token output budget before writing a draft. The intake request now sends the same three settings; the intake prompt text and identity `v0.3-s1-intake-1.0` are unchanged. Empty intake content now stops a live stage as an infrastructure error instead of being scored as a wrong answer, so a request defect cannot turn into a score again. The product intake path shares this client and receives the same fix. The T2 numbers of round 1 are valid development observations. D1 rounds share the 1,500-call development cap cumulatively; round 1 used 49.

**D1 round 2 and fixes before round 3 (2026-10-06, T-CX406, T-CX407):** Round 2 (`runs/dev_r2`, PR #57, 50 HTTP calls; D1 total 99) is kept as recorded. The request fix worked, but all 12 intake drafts failed schema validation. Prompt `v0.3-s1-intake-1.0` named the draft keys without their allowed values or types, so the T1 numbers of round 2 again measure the harness, not the agent. The intake prompt is now `v0.3-s1-intake-1.1`: it names every allowed `mode` and `stimulus_kind` value, gives the mode precedence the labels use (a named reference file, then a written test-tone frequency, then `single_signal`), and includes a JSON example that validates. A draft that fails validation now records the failing field locations and error types in the case file, without the model's values. T2 in both rounds was consistent: the planner made two whole-file calls and finished, so localization was 0. Planner `signal_meta` already carries `duration_s` and `channels`, so the gap is the guidance. The study planner is now `v0.3-s1-planner-9.13`: the v9.11 text plus a call plan (whole-file mixdown, each channel when there are two, then equal windows that cover the file, citing the window Evidence). It fits the runtime's default 8 tool calls. v9.11 and v9.12 texts and hashes are unchanged, and the product default stays v9.11. Two case-set limits found in review are recorded, not fixed here: (1) dev clean controls `dev-t1-00` to `dev-t1-03` state a tone frequency in the text but are labelled `single_signal` with no frequency, which the held-out labels never do, so a consistent intake cannot match them; (2) at 8 kHz, automatic F0 estimation picks a subharmonic (about 87.9 Hz) for the 440 Hz T2 tone, over the whole file and over the 1.0–1.25 s fault window, so `analyze_harmonic_distortion` without a stated fundamental returns invalid, and the 2 dev and 6 held-out harmonic T2 cases cannot be answered by any arm. The same tone at 48 kHz, or 400 Hz and 500 Hz at 8 kHz, is estimated correctly.

**D1 round 3 and the fix before round 4 (2026-10-06, T-CX408):** Round 3 (`runs/dev_r3`, PR #59, 130 HTTP calls; D1 total 229) is kept as recorded. Intake 1.1 worked: every draft validated, first-draft field accuracy was 0.71 and the T1 increment +1. Diagnosis did not finish in 23 of 24 runs: each rule-backed tool call spends one automatic rule evaluation, `AgentLimits.max_rule_evaluations` is 4, and a fifth such call ends the run with no diagnosis. The v9.13 plan needed 5 to 7 calls; its design checked `max_tool_calls` (8) and missed this limit. The study planner is now `v0.3-s1-planner-9.14`. It keeps the runtime limits, which are the product's, and sizes each path to them: contextual runs (reference or nominal frequency) follow the v9.11 procedure without window scans; single-file mono runs check four equal windows; single-file stereo runs check left and right over the whole file, then two halves of the channel that clipped. The budget figures in the text are derived from `AgentLimits`, and a test fails if any plan exceeds it. Executed deterministically, the single-file plan flags and localizes every dev clipping case and flags no clean case; the same check over the held-out audio was used to confirm feasibility only, without a model.

**D1 round 4, scoring correction and the fix before round 5 (2026-10-06, T-CX409, T-CX410):** Round 4 (`runs/dev_r4`, PR #61, 139 HTTP calls; D1 total 368) is kept as recorded. All five dev T2 clipping cases were correct and localized with four tool calls each (strong fixed arm: 14 to 90). Every no-fault case ended at `max_planner_retries`: in `single_signal` mode a `no_supported_fault` claim must cite harmonic-analysis and THD PASS results, v9.14 forbids collecting them and left the outcome unnamed, and the model sent `no_supported_fault` with no claims three times. An offline reproduction with a fake SDK showed the same seven sends and rejection. The study planner is now `v0.3-s1-planner-9.15`, which names `inconclusive` with no claims as the single-file outcome when no window shows clipping; a test drives the real runtime through each prescribed finish. **Scoring correction (operator-approved 2026-10-06, before any held-out run):** the T2 no-fault rule (correct when no fault is claimed) also counted five crashed runs as correct in round 4. An agent run that ends without a diagnosis is now never a correct conclusion; the fixed arms always finish, so they are unaffected. Earlier rounds' reports are kept as recorded and are not rescored. Case files now record the runtime's rejection messages (`run_errors`).

**D1 round 5 and stage F (2026-10-06):** Round 5 (`runs/dev_r5`, PR #63, 112 HTTP calls; D1 total 480 of 1,500) completed every run (`planner_finished` on all 24, no `run_errors`). Under the corrected scoring: T1 first-draft increment +1 (6 vs 5), T1 downstream 6 vs 11 (secondary; fixed arms use the scripted judge), T2 10 vs 10 with every dev clipping case localized and 47 agent tool calls against 464. The remaining agent errors are the dev clean-control label conflict (`dev-t1-00` to `dev-t1-03`), two combined cases where an invalid contextual analysis keeps the agent from claiming harmonic distortion (product policy), and the two harmonic T2 cases no arm can answer. D1 ends here. **Stage F (operator-authorized 2026-10-06, `approved_by` wfengq):** `prompt_freeze_record.json` freezes planner `v0.3-s1-planner-9.15`, intake `v0.3-s1-intake-1.1` and the diagnosis request; its hashes equal round 5's `identity.json`. H1 runs once on the 48 held-out cases under this record, after F merges, with the 1,008-call stage cap.

**H1 result and safety reading (2026-10-06):** H1 (`runs/heldout_h1`, PR #65, 217 HTTP calls; study total 697) ran once under the frozen identity; all 48 runs finished with no `run_errors`. T1 first-draft increment **+5** (agent 22/24, strong fixed 17/24): measurable increment. T2 increment **0** (18/24 each): no significant increment; agent and B2 both localized 6/6 clipping cases, with 96 against 824 tool calls. **Safety reading (operator decision 2026-10-06):** the hard conditions (zero unsupported positive conclusions, traceability 1.0) apply to the agent arm, which met both on all 48 cases. `report.json` aggregates all arms and shows T1 `safety_hard_pass: false` because the strong fixed arm's scripted judge claimed faults on four clean cases; the file is kept as recorded and both readings are reported. Held-out case-set limits are recorded in the report: the six segment-harmonic T2 cases no arm can answer, and the eight clean T1 cases whose stated frequency (440 or 1000 Hz) does not match their 220 Hz audio, which affects the secondary downstream metric only. Full results: `docs/evaluations/v0_3/agent_increment/STUDY_S1_AGENT_INCREMENT_1_REPORT.md`. The product default prompt is unchanged.

## D046 — Stop OQ-019 planner-ablation `dev_2` before sealing

**Decision (operator 2026-10-06):** `study_s1_planner_ablation_dev_2` stops at
its partial preseal state and will not be sealed or run. No live model call was
made for it, so it has no results and no conclusion may be cited from it.

**Why:** the remaining preseal blockers (all-outcome and per-send token
ceilings, failed-attempt token exposure; see D041 and
`PRESEAL_BUDGET_STATUS.md`) had no practical route to closure. The question
dev_2 was set up to answer, whether the RealLLM planner earns its complexity
over a truth-free fixed pipeline, is now measured by the agent-increment study
(D045), which budgets by HTTP call caps instead of token proofs. D045 is a
separate study, not a continuation of dev_2.

**Kept as historical record, unchanged:** every file under
`docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_2/`,
D038–D041, and the `planner_ablation` code and tests. `dev_1` and its
`fixed_pipeline_dominance` conclusion are unaffected.

**Reusable:** the scenarios and oracles approved in `LABEL_REVIEW.md` (an
independent review that did not use arm outputs as truth, with separate
single-file and paired-reference oracles for each scenario) may seed a later
study, for example on the value of context upgrades. Reuse needs its own
design and authorization.

**Housekeeping:** PR #28 (D041 proof-binding revision) and PR #20 (telemetry
design docs, already on trunk byte-identical) were closed without merge.

## D047 — Free-text intake product flow (confirm, then diagnose)

**Decision (operator 2026-10-06):** productize the T1 intake as a
confirm-then-diagnose flow in the Web UI and CLI, per
`docs/superpowers/specs/2026-10-06-s1-free-text-intake-product-design.md`
(approved with options 1A, 2A, 3A, and a small live acceptance run).
Contract: `CONTRACTS_V0_3_CONTEXTUAL.md` §25. Tests: T-CX411–T-CX419.

**Why:** the agent-increment held-out run measured T1 at +5 (22 vs 17 of 24),
above the pre-registered +3 line, but the product stopped at a raw draft that
the user had to copy into the form by hand.

**Choices:** the diagnosis planner gets the neutral question, not the user's
description (1A); reports show the context came from a confirmed draft, while
`assertion_source` stays `user_supplied` (2A); the CLI prompts on a terminal
and accepts `--yes` or explicit flags for scripts (3A).

**Unchanged:** product default prompt `v0.3-s1-planner-9.11`, intake prompt
`v0.3-s1-intake-1.1`, causal policy, rules, DSP, and the contextual endpoint's
validation. T2 localization and the study planner v9.15 stay out of the
product. The live acceptance run uses development T1 cases only, needs its own
handoff with a call cap, and produces no quality number; it is not compared
with H1 and does not replace the V0.2 79/80.

## D048 — SDK observation identity names the dispatching client (OQ-023 A)

**Decision (operator 2026-10-06):** adopt OQ-023 Option A. The SDK observation
profile records the HTTP client that actually dispatches requests for the
locked `openai==3.6.0`, its vendored `httpx2`, and the audit pins `httpx2`
2.12.0 alongside the existing pins. Design:
`docs/superpowers/specs/2026-10-06-oq023-sdk-dispatch-identity-design.md`.
Contract: `CONTRACTS_V0_3_CONTEXTUAL.md` §21.10. Tests: T-CX425–T-CX427.

The `llm` extra pins `httpx2==2.12.0` next to `openai==3.6.0`, so installs
without the lock file get the audited dispatch client; CI found 2.13.1 otherwise.

**Why:** the profile said `httpx` 0.28.1 and `httpx.AsyncClient.send`, so an
`httpx2` upgrade would have passed the audit unnoticed. Send counting was never
affected: observation wraps the client instance's own transport, verified
against a closed local port with no model call.

**Unchanged:** every recorded artifact, including the stopped `dev_2` study's
files and the D041 send-factor identity string, which keep the old labels as
history; product prompts and diagnosis behavior.
