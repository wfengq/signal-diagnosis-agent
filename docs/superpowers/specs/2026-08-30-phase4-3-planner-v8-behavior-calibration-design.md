# Phase 4.3 Planner v8 Behavior Calibration Design

**Date:** 2026-08-30

**Status:** Approved in writing on 2026-08-30. §53, T209–T215, D024, and
OQ-008 are frozen as design/test authority. Implementation and every real-model
run remain gated pending a detailed plan and separate explicit instruction.

**Implementation baseline:** `eb47237` on `phase4-evaluation-design`

**Evidence baseline:**
`docs/evaluations/phase4_2/development/bench_phase4_2_dev_v7_v12_gate3/`

## 1. Decision summary

Phase 4.3 is one final controlled prompt-only calibration of the real-model
Planner. It keeps the integrity-corrected Phase 4.2 evaluation foundation and
adds one coherent Planner v8 identity. It does not redesign the Agent,
evaluation dataset, Runtime, or scoring system.

The selected approach is:

- keep dataset `s1-distortion-synthetic` `1.2.0` unchanged;
- keep the accepted Runtime, PlannerContext, DSP, Tool, Rule, Knowledge,
  scoring, reporting, provider, model, and target contracts unchanged;
- add one coherent prompt `v0.2-s1-planner-8`;
- add deterministic tests proving the intended v8 behavior through the real
  product boundary;
- add one new development campaign identity and a conditional one-shot
  official identity;
- stop the prompt-only route if the v8 development campaign remains below
  target.

Phase 4.2 remains immutable and honestly `completed/below_target`. Phase 4.3
does not rewrite that result or rerun its campaign.

## 2. Evidence and problem statement

The Phase 4.2 deterministic integrity gate passed. The v7 development campaign
then ran 40 unique Agent slots on eight development cases with five repetitions
per case. It completed without unscored slots and produced:

```text
benchmark_status=completed
target_status=below_target
harness_status=pending  # CLI report-model semantics, not a harness failure
```

The four missed frozen bands were:

```text
first_tool_selection_rate          0.750   target >= 0.800
observation_driven_replan_rate     0.719   target >= 0.800
unnecessary_tool_action_rate       0.405   target <= 0.200
required_knowledge_usage_rate      0.200   target >= 0.800
```

The failures were stable across repetitions rather than isolated stochastic
errors:

- both clean cases used the same four-Tool sequence in all ten runs:
  clipping, spectrum, fundamental, then harmonic analysis;
- both harmonic cases chose spectrum first in all ten runs, then usually added
  clipping and fundamental before harmonic analysis;
- the combined case stopped after clipping in all five runs and omitted the
  independent harmonic cause;
- the noise case chose a valid first Tool in all five runs but continued through
  unrelated Tools and retrieved required knowledge in only one run;
- every initial task assessment recorded an empty hypothesis list.

The same campaign also showed that the architecture and grounding path are not
the primary problem:

```text
causal_macro_f1                       0.900
outcome_accuracy                      1.000
evidence_grounding_rate               1.000
unsupported_claim_rate                0.000
timely_stopping_rate                  1.000
applicable_rule_usage_rate            0.929
knowledge_citation_utilization_rate   1.000 when knowledge was retrieved
```

The root cause is therefore scoped to Planner behavior: v7 does not reliably
use the shortest valid Tool path, does not maintain explicit viable hypotheses,
stops too early after finding clipping in a broad request, and does not follow
the required invalid-result knowledge path.

## 3. Scope

### 3.1 In scope

- one new complete prompt `v0.2-s1-planner-8`;
- a private exact-v8 planner binding while preserving private compatibility
  bindings for historical prompts;
- deterministic semantic tests for hypothesis maintenance, Tool efficiency,
  combined-cause coverage, and invalid-result knowledge use;
- deterministic fake-transport tests through active `RealLLMPlanner`, the real
  Runtime, DSP Tools, RuleEngine, and KnowledgeIndex;
- additive v8 development and official campaign routes;
- strict identity and provenance preflight using existing models;
- one development run and, only after a development pass, one official run;
- honest status and immutable evaluation bundles.

### 3.2 Frozen and unchanged

- dataset `s1-distortion-synthetic` `1.2.0`, including all cases, requests,
  seeds, parameters, conditions, policies, and split membership;
- `PlannerContext`, `AgentDecision`, `DistortionDiagnosisRuntime`, limits,
  retry, invalid-decision, no-progress, and termination semantics;
- public DSP, Tool, RuleEngine, RuleProfile, KnowledgeIndex, Evidence,
  Diagnosis, trace, score, report, and benchmark models;
- scoring functions, failure codes, denominators, and `TargetBands`;
- DeepSeek provider, `deepseek-v4-flash`, model parameters, profile identity,
  and repetition counts;
- all v4–v7 prompt bytes and hashes, private planners, campaign routes,
  configuration identities, and committed bundles;
- the sealed v1.2 official held-out split.

### 3.3 Non-goals

- no Runtime-forced Tool, rule, or knowledge action;
- no fixed clipping/FFT/F0/THD pipeline;
- no ScriptedPlanner or fake transport as a product fallback;
- no new DSP algorithm, Tool, rule threshold, knowledge backend, or retrieval
  corpus;
- no evaluation-label, case-ID, category, split, acceptable-Tool, sufficient
  set, causal-truth, or target leakage into Planner messages;
- no lowering or redefining a target after observing v7;
- no v7 rerun or mutation of the v7 development bundle;
- no Phase 5 adapter, API, UI, WAV, reporting, deployment, or infrastructure
  implementation.

## 4. Considered approaches

### 4.1 Coherent v8 prompt with deterministic product-boundary tests — selected

This is the narrowest change that addresses the observed Planner behavior
without moving decision authority into the controller. It preserves the real
LLM product path and allows the v1.2 evaluation to measure whether the model can
follow a clearer decision policy.

### 4.2 Add controller-maintained structured hypothesis state — rejected

Adding `open`, `resolved`, or `unobservable` hypothesis state to
PlannerContext could improve stability, but it changes a frozen public boundary
and transfers part of diagnosis policy from the model into deterministic
control. It is not authorized for Phase 4.3.

### 4.3 Runtime-enforced actions — rejected

Forcing harmonic analysis after clipping or forcing knowledge retrieval after
invalid Evidence would make the target easier to reach, but it would turn the
product path into a disguised fixed controller. This contradicts Scenario S1's
dynamic-selection objective.

## 5. Planner v8 decision policy

### 5.1 Hypothesis lifecycle

The Planner maintains an explicit set of still-viable S1 hypotheses in
`task_assessment.hypotheses`.

- A broad request to inspect plausible S1 distortion starts with both
  `clipping` and `harmonic_distortion` viable.
- A symptom-specific request may prioritize its indicated family.
- A later observation may reopen another family when that observation provides
  a concrete reason.
- A hypothesis closes only when supported, ruled out by sufficient Evidence,
  or explicitly unobservable with a traceable limitation.
- A positive result for one family does not close another still-viable family.
- Finish is permitted only after every still-viable requested hypothesis is
  closed.

The Runtime does not create or enforce this set. It remains a Planner decision
recorded in the existing `TaskAssessment` field.

### 5.2 Symptom-driven first Tool

The prompt describes these as decision guidance, not a universal routing
table:

```text
flattened peaks / amplitude ceiling       -> detect_clipping is informative
overtones / harmonic coloration           -> analyze_harmonic_distortion is informative
unstable pitch / non-periodic waveform    -> estimate_fundamental or harmonic analysis is informative
generic broad request                     -> clipping or harmonic may be first
```

The Planner must choose from user-visible symptoms, public metadata, current
hypotheses, and same-run observations. It must never choose from `signal_id` or
evaluation identity.

### 5.3 Minimal Tool use

`analyze_harmonic_distortion` accepts a missing `fundamental_hz` and can perform
the configured harmonic analysis directly. The Planner must not treat spectrum
or standalone F0 estimation as mandatory prerequisites.

- `analyze_spectrum` is used only when existing Evidence cannot locate relevant
  frequency structure.
- `estimate_fundamental` is used when pitch/voicing is itself diagnostic or
  when a prior harmonic result explicitly shows that an additional F0 estimate
  is needed.
- A Tool is not called merely to make a report appear more complete.
- A rule batch is not repeated over equivalent Evidence.

### 5.4 Required representative behavior

Clean broad request:

- acquire clipping and harmonic Evidence in either order;
- do not call spectrum or standalone F0 by default;
- evaluate the configured profile once over the relevant Evidence;
- finish `no_supported_fault` only after both viable families are ruled out.

Harmonic-specific request:

- call harmonic analysis first;
- evaluate the configured profile when relevant Evidence exists;
- finish when the requested harmonic hypothesis is supported or ruled out;
- do not add spectrum, clipping, or F0 without an observation-driven reason.

Combined broad request:

- clipping and harmonic analysis may occur in either order;
- a supported clipping observation does not permit early finish while the
  harmonic hypothesis remains viable;
- report independent harmonic distortion only with its own reportable order-2
  Evidence, separate from clipping Evidence;
- finish with both causes and resolvable same-run references.

Noise or invalid request:

- begin with fundamental or harmonic analysis based on the visible symptom;
- after unvoiced or invalid Evidence, acquire only the additional invalid
  harmonic Evidence needed for an applicable NOT_APPLICABLE rule path;
- evaluate the profile, retrieve explanatory knowledge, and finish with one
  traceable inconclusive claim and a non-empty limitation;
- do not detour through clipping or spectrum without new Evidence that makes
  those actions relevant.

### 5.5 Knowledge and stopping

- Invalid or not-applicable harmonic results with a material limitation require
  curated explanatory knowledge before finish.
- The final inconclusive claim cites same-run Evidence, applicable same-run
  NOT_APPLICABLE rule evaluations, and the used same-run knowledge retrieval.
- Straightforward supported-fault and no-fault results do not retrieve
  decorative knowledge.
- Once same-run Evidence is sufficient for every viable hypothesis, the next
  action is rule/knowledge work that is still required or `finish`, not another
  unrelated DSP Tool.

## 6. Prompt and campaign identities

The exact identities to freeze after written-spec approval are:

```text
prompt version:          v0.2-s1-planner-8
development campaign:   phase4.3-v8-development
development benchmark:  bench_phase4_3_dev_v8_v12_gate4
official campaign:      phase4.3-v8-official
official benchmark:     bench_official_s1_v12_planner8_gate4
dataset:                 s1-distortion-synthetic 1.2.0
provider/model:          deepseek / deepseek-v4-flash
rule profile:            profile_s1_distortion 1.0.0-demo
development slots:       8 cases x 5 = 40 Agent slots
official slots:          16 cases x 5 = 80 Agent slots
```

The v8 prompt is one complete byte-frozen prompt. It is not implemented by
appending a corrective suffix to v7.

Every v8 bundle uses existing six-file reporting and records identity-complete
provenance. `benchmark_manifest.json`, `metrics.json`, and valid checksums are
mandatory. Missing, unreadable, incomplete, non-canonical, or mismatched
development provenance is `invalid_configuration` before credentials or
official scheduling.

## 7. Proposed deterministic acceptance contract

After written-spec approval, the contract-freeze task will propose additive
`CONTRACTS_V0_2.md` §53, `TEST_PLAN_V0_2.md` §26 T209–T215, and D024.

```text
T209  legacy v4–v7 immutability and exact v8 prompt/planner identity
T210  v8 hypothesis lifecycle, symptom-driven first Tool, minimal Tool use,
      combined continuation, invalid-result knowledge, and stopping semantics
T211  outbound value-level non-leakage under v8
T212  clean, harmonic, combined, and noise fake-transport paths through active
      RealLLMPlanner plus real Runtime/DSP/Tools/RuleEngine/KnowledgeIndex
T213  no Runtime-forced action, fixed pipeline, or ScriptedPlanner product fallback
T214  canonical v8 campaigns, identities, strict provenance, and official preflight
T215  cumulative T001–T215, zero required skip/xfail, Ruff, mypy, architecture,
      and baseline diff-check gate
```

T212 does not make a scripted controller the product Agent. It supplies
deterministic model responses at the `RealLLMPlanner` transport boundary and
verifies the existing product Runtime and deterministic dependencies.

Existing malformed-decision retries, recoverable errors, no-progress limits,
max-Tool termination, reference validation, and no-fallback behavior remain
required and unchanged.

## 8. Real-model gates

### 8.1 Development

The development campaign may run only after:

- the v8 prompt bytes and SHA-256 are committed;
- T001–T215 pass with zero required skip/xfail;
- Ruff, mypy, architecture, and diff-check pass;
- the canonical destination does not exist;
- credentials are present without being exposed.

The exact v8 development identity runs once. All applicable frozen target bands
must pass simultaneously. Averages or selected headline metrics do not replace
the frozen acceptance calculation.

If development is `completed/below_target`:

- preserve and commit the honest bundle;
- do not rerun or alter the same identity;
- do not create a prompt-only v9;
- do not run official held-out;
- stop and open a new written decision between changing the model and changing
  PlannerContext.

### 8.2 Official

Official may run exactly once only when development is
`completed/meets_target` for the byte-identical v8 candidate and all identity
preflight checks pass.

The official result is preserved whether it meets target or not. An official
miss cannot be used for same-held-out prompt tuning or rerun.

## 9. Phase acceptance

Phase 4.3 is accepted only when all of the following are true:

- T001–T215 and all static gates pass;
- v8 development is `completed/meets_target`;
- v8 official is `completed/meets_target`;
- all 80 official Agent slots are scoreable;
- prompt, dataset, profile, provider/model, repetition, benchmark, and checksum
  identities are valid;
- no held-out rerun, leakage, forced controller action, target reduction, or
  historical identity drift occurred.

If development or official misses target, Phase 4.3 is not accepted and Phase 5
remains gated.

## 10. Execution workflow

Implementation remains assigned to Cursor after the written contract and plan
are separately approved. Every implementation task follows the user-approved
seven-step sequence:

1. Implementer performs TDD and leaves changes uncommitted.
2. A separate agent performs specification-compliance review.
3. Critical or Important findings are fixed and independently re-reviewed.
4. A separate agent performs code-quality review.
5. Critical or Important findings are fixed and independently re-reviewed.
6. The main Agent independently verifies tests, diff, scope, and gates.
7. The main Agent creates the local task commit.

Tasks do not modify the same worktree concurrently. Nothing is pushed, merged,
or advanced to Phase 5 during this phase.

## 11. Documentation sequence and authority

Approval of this written specification will authorize only the next design
step:

1. record OQ-008;
2. draft and freeze additive §53, §26 T209–T215, and D024 after explicit user
   approval;
3. create the detailed Cursor implementation plan using the Superpowers
   writing-plans workflow;
4. obtain a separate explicit implementation authorization.

Until those gates pass, this specification does not authorize code changes,
model execution, development reruns, official held-out access, Phase 5, push,
or merge.
