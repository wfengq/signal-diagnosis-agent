# Phase 4.1 Agent Behavior Improvement Design

**Date:** 2026-08-30

**Status:** Draft for written-spec review

**Baseline:** `b68ec5e` (`phase4-evaluation-design`)

**Scope:** V0.2 Phase 4.1 only

## 1. Purpose

Phase 4 produced an accepted deterministic evaluation harness and a complete,
honestly reported 80-slot DeepSeek benchmark. The official bundle at
`b68ec5e` is `completed/below_target`: causal diagnosis, first-Tool selection,
replanning, stopping, unnecessary Tool use, and unsupported-claim behavior met
their target bands, while applicable-rule use, required-knowledge use, and
Evidence grounding did not.

Phase 4.1 improves the real product Agent's behavior before Phase 5. It does
not rewrite the evaluator, weaken target bands, hide the original result, or
turn the runtime into a deterministic rules controller.

Phase 4.1 is complete only after a new, no-tuning held-out benchmark reaches
`completed/meets_target` and the complete deterministic suite remains green.

## 2. Root-cause finding

The original prompt describes the available rule and knowledge actions but
does not give the planner a sufficiently explicit policy for using them. In
the first official benchmark this produced:

- no rule evaluations on many clean and invalid cases;
- no knowledge retrievals on any case;
- repeated misclassification of injected harmonic cases whose THD still
  passed the 5% demonstration rule.

The last behavior is not a frozen-contract contradiction. D019 intentionally
separates generator-injected causal truth from configured acceptance
judgments. A signal may contain observable 4% harmonic distortion while also
passing the `thd_percent lte 5.0` demonstration rule. The diagnosis must report
both facts instead of treating rule PASS as proof that no distortion exists.

The first correction therefore belongs at the real planner's prompt boundary,
not in DSP, rules, scoring, or runtime control.

## 3. Approved strategy and boundaries

Phase 4.1 first uses prompt-only behavior guidance.

- The product path remains `RealLLMPlanner` with DeepSeek
  `deepseek-v4-flash`.
- The candidate prompt version is `v0.2-s1-planner-5` and is identified by its
  exact SHA-256 in every real-model artifact.
- `PlannerModel`, `AgentDecision`, `PlannerContext`,
  `DistortionDiagnosisRuntime`, public evaluation models, scoring formulas,
  target bands, and termination semantics remain unchanged.
- The S1 rule profile remains `profile_s1_distortion` `1.0.0-demo`.
- `ScriptedPlanner` and fake model transports remain deterministic test
  doubles. Product failure never falls back to either one.
- The runtime does not force rule evaluation, knowledge retrieval, or a fixed
  DSP sequence before accepting `finish`.
- The planner never receives waveform samples, full FFT arrays, evaluation
  labels, causal truth, split identity, knowledge policy, sufficient-Evidence
  sets, or scoring conditions.
- Numerical metrics remain DSP-owned, and thresholds remain profile-owned.

If prompt-only development evaluation cannot meet the existing target bands,
the work stops. A PlannerContext presentation change or model change requires
a separate design decision; neither may be introduced silently.

## 4. Planner decision policy

Each `RealLLMPlanner.decide` call still returns exactly one of:

```text
call_tool | evaluate_rules | retrieve_knowledge | finish
```

The prompt provides a general observation-driven policy rather than a
prescribed pipeline.

### 4.1 Hypothesis and DSP selection

The planner uses the user's question, compact signal metadata, and current
observations to maintain viable clipping, harmonic-distortion, and
inconclusive hypotheses. It selects the DSP Tool expected to reduce the most
relevant uncertainty. The prompt does not require one universal first Tool or
complete Tool sequence.

After each Observation, the planner decides whether the current Evidence is
sufficient, another DSP result is justified, a configured rule is applicable,
an explanatory knowledge action is useful, or the run should finish.

### 4.2 Causal observation versus configured acceptance

DSP Evidence answers whether a distortion characteristic is present. A rule
evaluation answers whether an observed value satisfies the configured
demonstration profile. Neither answer overwrites the other.

The prompt explicitly permits a supported causal claim together with a PASS
rule judgment, for example:

> Harmonic distortion is present at the observed THD, while that value still
> satisfies the configured 5% demonstration limit.

Conversely, a rule failure must cite the deterministic rule result; the model
must not invent or restate the threshold as its own calculation.

### 4.3 Rule actions

When relevant numeric Evidence exists, has not been evaluated under the
current S1 profile, and the configured judgment will inform the final
diagnosis, the planner should select `evaluate_rules`. The final claim cites
the applicable `ruleval_*` IDs as well as supporting Evidence.

Rule use remains observation-driven. Duplicate evaluations and evaluations
before applicable Evidence exists remain invalid or unnecessary under the
existing runtime and scorer semantics.

### 4.4 Knowledge actions

The planner should select `retrieve_knowledge` when invalid or not-applicable
DSP output needs an explanation, or when a material limitation cannot be
clearly explained from numeric Evidence alone. Straightforward clean and
supported-fault results do not require retrieval merely for completeness.

For an invalid/noise path, the expected general pattern is:

1. cite the invalid deterministic Evidence;
2. retrieve relevant curated knowledge;
3. finish with an `inconclusive` claim that cites both the Evidence and the
   `know_*` retrieval ID;
4. include at least one explicit limitation.

Knowledge explains a conclusion; it never substitutes for numeric Evidence.

### 4.5 Stopping

The planner finishes when the viable requested hypotheses have sufficient
Evidence, applicable configured judgments have been obtained, and any
necessary explanatory limitation is supported. It must not call additional
DSP Tools, repeat rule evaluations, or repeat knowledge retrievals merely to
make the trace look complete.

## 5. Dataset v1.1.0

Phase 4.1 adds, rather than overwrites, the following manifest identity:

```text
dataset_id: s1-distortion-synthetic
version: 1.1.0
rule_profile_id: profile_s1_distortion
rule_profile_version: 1.0.0-demo
```

The dataset remains deliberately narrow: clean, clipping, harmonic,
combined, and invalid/noise cases. It retains the exact Phase 4 allocation:

- development: 2 clean, 2 clipping, 2 harmonic, 1 combined, and 1
  invalid/noise case, for 8 total;
- held-out: 3 clean, 4 clipping, 4 harmonic, 3 combined, and 2 invalid/noise
  cases, for 16 total.

All v1.1.0 case IDs, signal parameters, random seeds, and request assignments
are new. They do not copy v1.0.0 held-out fixtures. The cases still cover
below-boundary, boundary, and above-boundary behavior, including the D019
distinction between injected harmonic distortion and the 5% profile judgment.

User requests use natural S1 wording and do not name Tools or prescribe a
pipeline. Development and held-out cases use different, semantically
equivalent request phrasings. The primary intent remains the original user
question: why the signal sounds distorted.

The Agent cannot see generator parameters, matched controls, causal labels,
knowledge policy, or evaluation metadata.

## 6. No-tuning protocol

The committed v1.0.0 benchmark at `b68ec5e` remains an immutable diagnostic
baseline. Its observed failures may motivate general behavior improvements,
but it is not reused as proof that the improved prompt generalizes.

The v1.1.0 protocol is:

1. create and deterministically validate the complete versioned manifest;
2. use only the 8 development cases for prompt development;
3. run five fixed development slots per case, for 40 product-path runs;
4. require the candidate prompt to meet the existing target bands on the
   development report;
5. freeze the prompt version, prompt SHA-256, dataset version, provider, model,
   model parameters, SDK versions, profile version, and runner settings;
6. only then execute the 16 held-out cases five times each, for 80 official
   product runs;
7. do not tune against or rerun the same held-out set after inspecting its
   results.

If the official v1.1.0 benchmark is below target, its complete report is
retained. A subsequent formal attempt requires a new semantic dataset version,
fresh held-out cases, a new prompt identity where applicable, and a new
benchmark ID.

The held-out manifest remains committed for reproducibility. As in Phase 4,
`held_out` means a procedural no-tuning split rather than a secret dataset.

## 7. Error handling and honest degradation

Phase 4.1 preserves existing runtime and evaluation error semantics.

- Invalid or schema-incompatible model output follows the current recoverable
  planner retry path. The same real planner repairs its output within budget.
- A `finish` with unresolved references or invalid diagnosis semantics is
  rejected by the runtime and may be repaired within the existing retry
  budget.
- Invalid or not-applicable DSP results are never replaced with model-generated
  numbers. The planner may gather justified alternative Evidence or finish
  inconclusively with knowledge and limitations.
- A `not_applicable` rule evaluation is not PASS.
- An empty or irrelevant knowledge result never authorizes a fabricated
  citation. The run may finish with a limitation and honestly miss a behavior
  target.
- Existing no-progress and action-budget terminations remain authoritative.
- The real runner retries only the already-frozen infrastructure classes.
  Exhausted infrastructure retries remain unscored/incomplete rather than
  being replaced with fake or scripted behavior.
- A completed benchmark that misses a target is recorded as
  `completed/below_target` with its full six-file bundle.

These rules keep model behavior failures, runtime failures, evaluator failures,
and provider infrastructure failures distinguishable.

## 8. Deterministic test allocation

Phase 4.1 extends the required test plan with T184-T195:

- **T184 — Prompt identity:** prompt version, exact content hash, and benchmark
  configuration agree.
- **T185 — No evaluation leakage:** prompt and serialized PlannerContext omit
  causal truth, split, knowledge policy, sufficient-Evidence sets, and scoring
  conditions.
- **T186 — Dual-truth expression:** deterministic examples support a causal
  distortion claim and an independent PASS/FAIL configured judgment in the
  same final diagnosis.
- **T187 — Rule action propagation:** applicable Evidence can drive a fake
  model rule decision through the real runtime, and the resulting batch reaches
  the next planner context and final claim.
- **T188 — Invalid knowledge path:** invalid Evidence can drive knowledge
  retrieval, an inconclusive claim with valid references, and a non-empty
  limitation.
- **T189 — Same-run traceability:** every final Evidence, rule, and knowledge
  reference resolves within the same run.
- **T190 — Dynamic route preservation:** the prompt does not prescribe a fixed
  Tool order, and multiple scripted/fake S1 routes remain valid.
- **T191 — v1.1.0 manifest:** identity, category allocation, unique IDs,
  deterministic parameters, seeds, and reconstruction validate.
- **T192 — Natural requests:** v1.1.0 request text contains no Tool names,
  required order, or answer-bearing evaluation labels.
- **T193 — Split isolation:** development and held-out IDs, signal parameter
  combinations, random seeds, and request assignments do not overlap.
- **T194 — Official runner freeze:** the real runner binds the frozen prompt
  hash, v1.1.0 dataset, new benchmark ID, and exactly 16 x 5 held-out slots.
- **T195 — Cumulative gate:** T001-T195 pass with zero required skip/xfail;
  Ruff, mypy, architecture boundaries, and
  `git diff --check b68ec5e..HEAD` remain green.

Deterministic tests may use `ScriptedPlanner` or a fake provider transport, but
they must exercise the real runtime, Tools, RuleEngine, KnowledgeIndex, and
trace assembly where those components are in scope. Stochastic model behavior
does not enter ordinary CI.

## 9. Real-model gates

### 9.1 Development gate

Only v1.1.0 development cases may be used for prompt iteration. Before the
prompt is frozen, the 40-slot development report must be scoreable and meet
the existing Phase 4 `TargetBands`. This report is developmental evidence, not
the official generalization result.

### 9.2 Official completion gate

Phase 4.1 is accepted only when all of the following hold:

- the new held-out benchmark has `benchmark_status=completed`;
- it has `target_status=meets_target`;
- every existing target with a non-zero denominator passes;
- all 80 held-out Agent slots are scoreable;
- the append-only six-file official bundle validates and its checksums match;
- failures and five-run variation remain visible;
- the `b68ec5e` v1.0.0 `below_target` baseline remains present and traceable;
- T001-T195 have no required skip/xfail or regression;
- Ruff, mypy, architecture tests, and `git diff --check` pass.

The real-model gate is not a normal CI test. Phase 5 remains gated until this
gate is independently verified.

## 10. Reporting and provenance

The new development and official reports use the existing six-file bundle
format and append-only writer. Each report identifies the dataset, prompt,
provider, model, parameters, profile, run slots, attempts, scoreability, target
status, and checksums.

Reports must not claim that the 1% clipping or 5% THD limits are industry
standards, and must not generalize synthetic S1 results to production audio or
sensor diagnosis.

## 11. Non-goals

- changing DSP algorithms or Evidence values;
- changing the S1 rule profile or target bands;
- changing frozen Phase 1-4 public models or scorer semantics;
- forcing rules or knowledge in the runtime controller;
- changing the model provider or model in the first correction wave;
- fine-tuning, model training, embeddings, vector search, or network search;
- repeatedly optimizing against one held-out set;
- WAV, API, UI, HTML/PDF presentation, or any other Phase 5 work;
- expanding beyond the accepted S1 diagnosis space.

## 12. Contract treatment and implementation gate

Phase 4.1 is an additive behavior-calibration gate. It does not reopen
`CONTRACTS_V0_2.md` sections 41-49 or T125-T183. After written-spec approval,
the task-level implementation plan may add an additive Phase 4.1 normative
section and T184-T195 without changing prior public interfaces or test
semantics.

Approval of this design does not itself authorize implementation. Code changes
remain gated on a Superpowers task-level plan and an explicit execution choice.
