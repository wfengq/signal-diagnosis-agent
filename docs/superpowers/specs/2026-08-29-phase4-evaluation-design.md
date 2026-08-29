# Phase 4 Evaluation Design

**Date:** 2026-08-29
**Status:** Approved section-by-section; pending written-spec review
**Baseline:** `3eaf662` (`phase3-rules-knowledge`)
**Scope:** V0.2 Phase 4 only

## 1. Purpose

Phase 4 turns Scenario S1 into a reproducible evaluation campaign. It measures
deterministic system correctness, real-model behavior, and an honest fixed
pipeline on the same versioned synthetic cases.

This phase does not redefine the long-term project as S1-only. It validates the
first resume-grade vertical slice of the extensible Signal Test and Fault
Diagnosis Agent described by D016.

## 2. Approved constraints

- `RealLLMPlanner` remains the product path.
- `ScriptedPlanner` remains a deterministic test double.
- Required CI never depends on stochastic LLM behavior.
- Phase 1–3 public interfaces remain unchanged.
- Raw waveforms and full FFT arrays never enter planner context or evaluation
  artifacts intended for model consumption.
- DSP code alone produces numerical signal metrics.
- Pass/fail thresholds come only from versioned rule profiles.
- The S1 demonstration profile remains `profile_s1_distortion`
  `1.0.0-demo`; its 1% clipping-ratio and 5% THD limits are demonstration
  limits, not industry standards.
- Phase 4 does not add WAV, API, UI, model training, a new fault type, or a new
  DSP algorithm.

## 3. Architecture

Phase 4 adds an independent `signal_diag.evaluation` package. Its dependency
direction is:

```text
evaluation -> signal / dsp / tools / rules / knowledge / agent
```

No Phase 1–3 package may import `evaluation`.

The package has seven responsibilities:

1. load and validate a versioned synthetic dataset manifest;
2. wrap a planner with `RecordingPlanner` without changing the runtime;
3. execute the existing Agent runtime on evaluation cases;
4. execute an honest fixed-pipeline baseline through the same Tools and rules;
5. assemble planner snapshots and run artifacts into one chronological trace;
6. calculate deterministic per-run and aggregate scores;
7. write JSON, CSV, and Markdown evaluation reports.

The data flow is:

```text
manifest case
  -> existing synthetic generator
  -> repository
  -> Agent or fixed baseline
  -> unified EvaluationTrace
  -> deterministic scorers
  -> versioned comparison report
```

## 4. Dataset

### 4.1 Identity and reconstruction

The first manifest is:

```text
dataset_id: s1-distortion-synthetic
version: 1.0.0
rule_profile_id: profile_s1_distortion
rule_profile_version: 1.0.0-demo
```

Every case records the generator and every input parameter required to
reconstruct the signal. Random inputs include an explicit seed. The loader
uses typed generator specifications rather than arbitrary dictionaries.

Because existing synthetic generators allocate fresh Signal IDs, the
evaluation adapter rewraps their unchanged samples through the existing signal
factory with a stable case-derived ID. It does not normalize or modify the
waveform.

### 4.2 Case allocation

The manifest contains exactly 24 cases:

| Split | Clean | Clipping | Harmonic | Combined | Invalid/noise | Total |
|---|---:|---:|---:|---:|---:|---:|
| Development | 2 | 2 | 2 | 1 | 1 | 8 |
| Held-out | 3 | 4 | 4 | 3 | 2 | 16 |

Severity and boundary coverage are cross-cutting tags, not additional outcome
classes. The cases collectively cover values below, at the tested numerical
tolerance around, and above the 1% clipping-ratio and 5% THD profile limits.

### 4.3 Dual ground truth

Each case separates:

- `causal_faults`: generator-injected clipping and/or harmonic fault labels;
- `observable_conditions`: facts that existing DSP and Tool Evidence must
  expose, including validity and profile-boundary behavior.

Final diagnosis accuracy uses `causal_faults`. DSP, Evidence, and RuleEngine
correctness use `observable_conditions`.

A rule judgment does not overwrite causal truth. An injected harmonic case may
have THD at or below the 5% demonstration limit; the report must distinguish
the observed cause from the configured acceptance judgment.

### 4.4 Dynamic-path expectations

Each case declares:

- a set of acceptable first DSP Tools;
- observable Evidence conditions;
- one or more alternative sufficient Evidence sets;
- acceptable final outcomes and causal claims;
- whether a limitation is required;
- a knowledge policy: `required`, `optional`, or `not_needed`;
- normalized knowledge tags used to score retrieval relevance.

The manifest never declares one required complete Tool sequence. A legal
dynamic route may use any declared sufficient Evidence set.

The official V0.2 knowledge policy is:

- clean: `not_needed`;
- clipping, harmonic, and combined: `optional`;
- invalid/noise: `required`.

### 4.5 Combined-case identifiability

Clipping itself creates harmonic energy, so `clipping detected` plus elevated
THD does not prove a separately injected harmonic fault.

Every combined case therefore has a matched clipping-only control used only by
dataset validation. The control has the same base frequency, amplitude,
sampling parameters, and clipping setting. Existing DSP must expose a
harmonic-component signature for the combined case outside the matched-control
envelope by the manifest's validation tolerance. Cases that fail this test are
rejected before dataset freeze.

The Agent cannot see the matched control, generation parameters, validation
tolerance, or ground truth. The tolerance proves that a case is observable; it
is not a product pass/fail threshold and is never sent to the LLM.

## 5. Planner recording and unified trace

`RecordingPlanner` implements the existing `PlannerModel` protocol and wraps
either a real or scripted planner. For each `decide(context)` call, including
invalid-output and raised-error attempts, it records:

- a monotonic decision index;
- the compact immutable `PlannerContext` seen by the delegate;
- the validated `AgentDecision` or a sanitized error classification;
- decision latency and provider usage when actually available.

It does not reinterpret the decision. Successful decisions are returned
unchanged; exceptions are recorded and re-raised unchanged so the existing
Runtime retains retry and termination control.

After the run, `TraceAssembler` compares successive context snapshots and the
final Agent or baseline run result. It aligns decisions with new Observations,
Evidence, rule-evaluation batches, and knowledge retrievals. The result is a
monotonic `EvaluationTrace`.

If artifacts cannot be matched without ambiguity, assembly fails. It must not
guess an order or fall back to the grouped action summary in the existing
Phase 3 runner.

Evaluation traces and committed reports must not contain raw waveforms, full
FFT arrays, credentials, or unredacted provider responses.

## 6. Fixed-pipeline baseline

The baseline is not an Agent and does not use a planner. It always performs:

1. `detect_clipping`;
2. `analyze_harmonic_distortion`;
3. evaluation of `profile_s1_distortion`;
4. deterministic diagnosis mapping.

The mapping is:

- any applicable clipping rule failure indicates clipping;
- valid harmonic analysis plus THD-rule failure indicates harmonic
  distortion;
- both indicators produce both claims;
- neither indicator with sufficient valid Evidence produces no supported
  fault;
- invalid harmonic Evidence with positive clipping Evidence still produces a
  clipping claim plus a limitation;
- invalid harmonic Evidence without another supported fault produces
  inconclusive plus a limitation.

It does not call FFT or F0 redundantly, retrieve knowledge, inspect manifest
truth, or use matched controls. It may overclaim combined distortion when
clipping alone produces high THD. That limitation is retained and reported so
the comparison remains honest.

It returns dedicated baseline diagnosis/run models rather than assigning the
Agent-only `planner_finished` completion reason to a non-Agent path.

The baseline and Agent use the same repository, `SignalToolService`,
`RuleEngine`, rule profile loader, and cases.

## 7. Scoring

All primary metrics are calculated by deterministic pure scorers from the
manifest and unified trace. Human review may add a qualitative appendix but
cannot alter primary scores.

### 7.1 Diagnosis and grounding

- `causal_exact_set_accuracy`: predicted clipping/harmonic set exactly equals
  `causal_faults`.
- `causal_macro_f1`: multilabel macro-F1 over clipping and harmonic distortion.
- `outcome_accuracy`: final outcome matches an allowed case outcome, including
  clean and inconclusive.
- `evidence_grounding_rate`: each scored claim resolves all cited Evidence IDs
  and at least one cited Evidence satisfies a semantic support condition for
  that claim.
- `unsupported_claim_rate`: predicted causal fault claims absent from
  `causal_faults`, divided by predicted causal fault claims. An empty
  denominator yields `0.0` and is reported with denominator zero.

### 7.2 Dynamic behavior

- `first_tool_selection_rate`: the first DSP Tool is in the case's acceptable
  set.
- `observation_driven_replan_rate`: after new Observation, rule, or knowledge
  state, the next decision advances a still-viable sufficient Evidence set,
  validly applies rules/knowledge, correctly finishes, or handles an
  invalid/error state according to frozen runtime policy.
- `unnecessary_tool_action_rate`: an executed Tool action advances no
  still-viable sufficient Evidence set and is not justified error recovery.
- `timely_stopping_rate`: after the first point at which a sufficient Evidence
  set is satisfied, no additional DSP Tool is executed.
- `applicable_rule_usage_rate`: rules are evaluated when applicable Evidence is
  available and evaluation has not already been completed for the same state.

This is explicitly a measure of observable context-sensitive behavior. It does
not claim to prove the model's private chain of thought.

### 7.3 Knowledge, efficiency, and failures

Knowledge scoring reports:

- required-policy usage rate;
- retrievals made in `not_needed` cases;
- retrieval citation utilization.

The report also includes Tool count, rule/knowledge action count, termination
reason, invalid/retry counts, latency, provider tokens, and cost when available.
Unavailable provider usage is `null`, never fabricated.

### 7.4 V0.2 target bands

| Metric | Target |
|---|---:|
| causal macro-F1 | at least 0.80 |
| first-tool selection | at least 0.80 |
| observation-driven replan | at least 0.80 |
| Evidence grounding | 1.00 |
| unsupported claims | at most 0.05 |
| unnecessary Tool actions | at most 0.20 |
| timely stopping | at least 0.80 |
| applicable rule usage | at least 0.80 |
| required knowledge usage | at least 0.80 |
| knowledge citation utilization | 1.00 |
| unnecessary knowledge retrieval | at most 0.20 |

These are V0.2 demonstration targets. They are not CI gates, industry
standards, production claims, or SLAs.

## 8. Real-model benchmark protocol

The official V0.2 product benchmark is provider-neutral in schema and pinned in
execution to the current DeepSeek `deepseek-v4-flash` product configuration.
It records the provider, model, prompt version and SHA-256, model parameters,
SDK/version metadata, dataset version, profile version, and timezone-aware run
timestamp. The official prompt version is `v0.2-s1-planner-4`; its exact content
is recorded by SHA-256.

The eight development cases may be used for prompt and evaluator debugging.
After the manifest and prompt are frozen, each of the 16 held-out cases receives
five fixed run slots, for 80 product runs.

The official run is sequential in five rounds, visiting held-out cases in
manifest order once per round. This avoids concurrency-dependent rate-limit and
latency effects while distributing time drift across cases.

Looking at held-out results ends tuning for that benchmark ID. A later prompt,
model, or rerun creates a new benchmark ID and cannot overwrite the original.
The held-out manifest is committed for reproducibility rather than kept secret;
the split denotes a no-tuning protocol, not hidden test data.

Only transport timeouts, rate limits, and provider 5xx failures receive up to
two infrastructure retries for the same slot. All attempts are retained.
Authentication/configuration errors are not retried. Invalid model output,
planner retries, no-progress, budget exhaustion, and runtime termination are
behavioral outcomes and are not replaced by a fresh slot.

## 9. Acceptance states

Phase 4 has two independent acceptance states.

`harness_accepted` requires the deterministic dataset, scripted Agent path,
baseline, trace assembly, scorers, reports, architecture boundaries, and
T001-T183 to pass in CI with no required skip or xfail.

`benchmark_completed` requires all 80 held-out slots to reach a scoreable
terminal behavior result and an immutable official report bundle to be saved.
Scores below target produce `below_target`; they do not fail CI and must not be
hidden.

Missing credentials or service access permits deterministic implementation to
finish but leaves `benchmark_pending`. Exhausted infrastructure retries leave
the benchmark `incomplete`. Neither state unlocks Phase 5.

Phase 4 is fully accepted only when both acceptance states are satisfied.

## 10. Reports

Local raw provider output remains under a gitignored evaluation-output
directory. A validated, redacted official bundle is append-only under:

```text
docs/evaluations/phase4/<benchmark_id>/
```

It contains:

```text
benchmark_manifest.json
runs.jsonl
metrics.json
case_summary.csv
report.md
checksums.sha256
```

The three report representations must agree on run counts and aggregate
metrics. Reports retain failures and five-run variation and display Agent and
baseline results side by side. Writing to an existing benchmark directory is an
error.

## 11. Public contract boundary

The public package exports immutable Pydantic models for manifest cases,
synthetic specifications, Evidence conditions, sufficient Evidence sets,
planner records, trace events, traces, validation reports, run scores,
aggregate metrics, target bands, benchmark configuration, and benchmark
reports.

It also exports:

```python
load_dataset_manifest
validate_dataset
RecordingPlanner
assemble_evaluation_trace
FixedPipelineBaseline
score_evaluation_trace
aggregate_benchmark
write_benchmark_bundle
```

Written self-review clarified four details that the in-chat interface sketch did
not carry but the approved model semantics require:

- `validate_dataset` receives the repository in which generated records are
  stored, in addition to its `SignalToolService`;
- `assemble_evaluation_trace` receives `run_slot` and `execution_path`;
- `aggregate_benchmark` receives traces, attempt records, and deterministic
  harness status as well as scores.
- the fixed pipeline returns `BaselineRunResult`/`BaselineDiagnosis`, so a
  non-Agent path never fabricates the Agent-only `planner_finished` reason.

Without these explicit inputs, the functions could not construct their frozen
return models without hidden global state. The clarification does not change a
Phase 1–3 interface.

The operational module exposes:

```text
python -m signal_diag.evaluation validate-dataset
python -m signal_diag.evaluation run-deterministic
python -m signal_diag.evaluation run-real
python -m signal_diag.evaluation render-report
```

Provider SDK adapters, concurrency, temporary layouts, scorer file splits, and
formatting helpers remain private.

## 12. Test allocation

- T125-T132: manifest and public model contracts;
- T133-T140: dataset generation, reconstruction, coverage, and identifiability;
- T141-T148: planner recording and chronological trace assembly;
- T149-T154: honest fixed baseline;
- T155-T166: deterministic scorers;
- T167-T174: scripted end-to-end evaluation and reports;
- T175-T181: official benchmark runner and status/error behavior;
- T182: Phase 4 dependency boundary;
- T183: full Phase 1-3 regression and required-test gate.

## 13. Non-goals

- WAV ingestion;
- CLI/API/UI product adapters;
- HTML or PDF presentation reports;
- new DSP or fault-diagnosis capabilities;
- vector retrieval or network knowledge search;
- multi-model leaderboards;
- training, fine-tuning, or repeated held-out optimization;
- a requirement that the Agent beat the baseline;
- claims of real-world or production accuracy from synthetic cases.

## 14. Written-spec review gate

The user approved each design section in conversation on 2026-08-29. This file
and the synchronized contract/test-plan changes require one written-spec review
before implementation planning. No Phase 4 code is authorized by this design
commit alone.
