# V0.3 v9.7 Deterministic Rule Closure Design

**Status:** proposed for written user review

**Date:** 2026-09-05

**Scope:** V0.3 Scenario S1 contextual-agent remediation after the preserved
v9.6 development-confirmation result

**Branch:** `codex/v0.2-real-world-validation`

## 1. Decision summary

V0.3 will add a new product prompt identity,
`v0.3-s1-planner-9.7`, and a new causal policy,
`v9_7_deterministic_rule_closure`.

Under the new policy, the Agent runtime will select and evaluate the required
rule profile automatically after each relevant non-error Tool observation. The
profile and Evidence scope will be determined by Tool name and diagnostic mode,
not by an LLM `evaluate_rules` decision. The LLM will continue to select
measurements, decide whether more measurements are necessary, construct final
claims, cite same-run Evidence and rule results, and write limitations.

The change addresses a demonstrated architectural failure without changing
WAV data, DSP, thresholds, rule profiles, labels, scorers, or historical
evidence. It preserves the v9.5 and v9.6 prompts, policies, runs, and
`below_target` conclusions as immutable evidence.

## 2. Evidence and root cause

The append-only v9.6 development confirmation completed 20 unique cases with
no infrastructure interruption. Its corrected score was:

- planner completion: 10/20;
- scoreable outcome accuracy: 7/17;
- scoreable causal exact-set accuracy: 7/17;
- scoreable evidence grounding: 7/17;
- unsupported claims: 0/17;
- inconclusive appropriateness: 6/6;
- descriptive harmonic recall: 0/5;
- descriptive clipping recall: 4/6.

The failed harmonic and combined cases were not missing deterministic signal
evidence. All five harmonic/combined positives had valid contextual comparison
Evidence and `even_harmonic_growth_percent` above the frozen five-percent
development threshold. Tool routing also worked: paired and nominal cases used
`analyze_contextual_distortion` and did not substitute the ordinary harmonic
Tool.

The failure occurred at rule closure. Across the run, all 36 planner-created
`evaluate_rules` decisions selected `profile_s1_distortion`; none selected
`profile_s1_contextual_comparison`. Consequently:

- paired and nominal harmonic positives could not cite the required contextual
  rule FAIL results;
- clean paired and natural-even controls could not cite the required contextual
  PASS results;
- combined cases could not close their independent contextual harmonic path;
- repeated finish validation errors exhausted planner retries.

The prompt contains a real conflict. The v9.6 contextual policy describes the
mode-specific contextual gates, while inherited output-contract text still
directs the planner to use `profile_s1_distortion` for S1 rule evaluation.
Merely restating the correct profile name would leave deterministic profile and
Evidence selection under probabilistic model control.

Root-cause classification: deterministic orchestration boundary defect. It is
not evidence of a DSP defect, threshold defect, source-data defect, or label
defect.

## 3. Goals

The remediation must:

- make rule-profile selection deterministic and mode-aware;
- evaluate rules over the complete Evidence suffix produced by the triggering
  Tool observation;
- prevent an LLM from omitting inconvenient Evidence or mixing Evidence from
  unrelated calls when rules are evaluated;
- make contextual PASS and FAIL results available to the next planner turn;
- preserve deterministic finish validation and same-run citation requirements;
- retain the LLM for measurement planning and final diagnostic synthesis;
- make automatic rule creation explicit and reconstructable in evaluation
  traces;
- fail closed when automatic rule closure cannot be completed;
- preserve all historical identities, behavior, and recorded runs;
- create an offline-verifiable harness before any new real-model run.

## 4. Non-goals

This remediation will not:

- change `profile_s1_distortion` or
  `profile_s1_contextual_comparison`;
- change the one-percent clipping, five-percent THD, or five-percent contextual
  growth demonstration thresholds;
- change contextual DSP, harmonic estimation, clipping detection, Evidence
  values, or Tool schemas;
- change development WAVs, manifests, labels, confidence tiers, source records,
  seals, or expected outcomes;
- change scoring formulas, denominators, or acceptance targets;
- auto-construct, rewrite, or auto-attach final claim Evidence and rule refs;
- convert the contextual Agent into the fixed pipeline;
- add a new fault domain, dependency, network lookup, or multi-agent product
  architecture;
- access validation data during implementation or use it for tuning;
- invoke a real model during code acceptance;
- retry, replace, or relabel a historical v9.5 or v9.6 attempt;
- claim performance improvement before a separately authorized real-model
  development confirmation.

## 5. Considered approaches

### 5.1 Prompt-only profile clarification

Create v9.7 by naming `profile_s1_contextual_comparison` more explicitly. This
has the smallest code surface, but the LLM would still choose the profile,
Evidence subset, and evaluation timing. The v9.6 result shows that textual
preferences are not a sufficient reliability boundary. This approach is
rejected.

### 5.2 Reject an incorrect planner-selected profile

Keep `evaluate_rules` as an LLM action and reject incompatible profile choices.
This is fail-closed, but each incorrect choice consumes a retry and asks the
same model to repair the orchestration decision. It preserves the failure mode
that caused v9.6 `max_planner_retries`. This approach is rejected as the primary
design.

### 5.3 Deterministic post-Tool rule closure

After a relevant Tool returns a non-error observation, the runtime evaluates a
fixed profile against exactly that observation's Evidence. The resulting rule
batch is visible on the next planner turn. This removes probabilistic choices
from deterministic orchestration while retaining the Agent's measurement and
reporting responsibilities. This is the selected approach.

## 6. Versioning and compatibility

Add the following causal policy without modifying existing literals:

```text
CausalPolicyVersion =
  "v9_4_legacy"
  | "v9_5_contextual"
  | "v9_6_contextual"
  | "v9_7_deterministic_rule_closure"
```

Policy behavior is cumulative only for the new identity:

- `v9_4_legacy`: unchanged legacy finish behavior and manual rule evaluation;
- `v9_5_contextual`: unchanged historical contextual finish gates and manual
  rule evaluation;
- `v9_6_contextual`: unchanged contextual finish gates, mode-aware harmonic
  Tool rejection, and manual rule evaluation;
- `v9_7_deterministic_rule_closure`: reuses the v9.6 Tool-routing guard and
  contextual finish gates, adds automatic rule closure, and rejects planner
  `evaluate_rules` actions.

The product composition root will switch to the v9.7 prompt and policy only
after their tests and identities are frozen. Tests and explicit dependency
injection may continue to construct every older identity. No historical prompt
constant will be edited.

## 7. Rule closure planner

Introduce one small Agent-layer unit responsible only for the deterministic
mapping. It exposes two pure operations:

```text
required_rule_profile(policy, stimulus_context, tool_name)
  -> RuleClosureProfileId | None

build_rule_closure_request(profile_id, observation)
  -> RuleClosureRequest | None
```

The first operation permits a bounded-resource precheck before Tool execution.
The second attaches the complete Evidence suffix only after an Observation
exists.

Conceptual immutable result:

```text
RuleClosureRequest
  profile_id: RuleClosureProfileId
  evidence_refs: tuple[str, ...]
```

`RuleClosureProfileId` is limited to the two existing profiles used by Scenario
S1. The request contains the observation's complete ordered
`evidence_refs`; callers cannot provide an arbitrary subset.

The v9.7 mapping is:

- `detect_clipping` in every diagnostic mode ->
  `profile_s1_distortion`;
- `analyze_harmonic_distortion` in `single_signal` ->
  `profile_s1_distortion`;
- `analyze_contextual_distortion` in `paired_reference` or
  `nominal_single_tone` -> `profile_s1_contextual_comparison`;
- `analyze_spectrum` and `estimate_fundamental` -> no closure;
- an Observation with Tool status `error` -> no closure.

Both `success` and `invalid` statuses trigger closure for a relevant Tool.
Invalid Evidence is deliberately evaluated so that the fixed RuleEngine can
produce auditable `not_applicable` results.

Both operations are pure mappings. They do not load profiles, execute rules,
mutate runtime state, inspect expected labels, or infer a diagnosis.

## 8. Runtime state transition

For `v9_7_deterministic_rule_closure`, a relevant Tool action follows this
order:

1. Apply the existing task-assessment, routing, Tool-budget, and equivalent-call
   checks.
2. Determine whether the requested Tool would require one automatic closure.
   If no rule-evaluation slot remains, terminate with
   `max_rule_evaluations` before executing the Tool.
3. Execute the Tool and append its Observation, Evidence, history, and warnings
   through the existing recording path.
4. If status is `error`, retain the Tool result and do not consume a
   rule-evaluation slot.
5. If status is `success` or `invalid`, derive the closure request from the
   recorded Observation.
6. Require a non-empty Evidence suffix for a relevant non-error Tool. An empty
   suffix is an internal contract violation and terminates as `runtime_error`.
7. Load the fixed profile, evaluate it with an Evidence filter equal to the
   exact suffix, append one `RuleEvaluationBatch`, and increment
   `rule_evaluation_count` once.
8. Build the next planner context with the new Observation, Evidence, and rule
   batch already present.

Automatic closure uses the existing `max_rule_evaluations` bound. It does not
add a second limit or an unbounded background action. The default capacity of
four supports the intended maximum of two required closures in current S1
paths while retaining a fail-closed upper bound.

The RuleEngine continues to evaluate the complete selected profile. Rules whose
source metric is absent from the exact Evidence suffix remain
`not_applicable`. The runtime must not introduce a profile-specific partial-rule
engine.

## 9. Planner `evaluate_rules` behavior

The typed historical decision union retains `EvaluateRulesDecision` for trace
compatibility and older policies. Under v9.7 only, a planner-created
`evaluate_rules` decision is rejected as a recoverable behavioral error after
the normal initial task-assessment requirement is applied.

The rejection:

- explains that rule batches are created automatically from Tool observations;
- tells the planner to use existing rule batches or obtain the missing Tool
  observation;
- consumes one planner retry;
- consumes zero Tool calls and zero rule evaluations;
- creates no Evidence or rule batch;
- is not an infrastructure error.

Repeated manual rule actions may still terminate at `max_planner_retries` and
must be preserved as behavioral failure evidence. Older policies retain their
current manual `evaluate_rules` behavior; any shared refactoring must be proven
equivalent by tests.

## 10. Trace and provenance contract

The current Agent trace assembler assumes that a `CallToolDecision` may append
an Observation and Evidence but not a rule batch. v9.7 extends this append-only
delta contract.

For a relevant non-error Tool decision, the trace will contain, in order:

1. its existing `PlannerDecisionEvent`;
2. one `ObservationEvent` containing the exact Evidence suffix;
3. one `RuleEvaluationEvent` containing the automatic batch.

The Observation and rule events use the same
`caused_by_decision_index`, which identifies the Tool decision that triggered
both. This makes automatic origin reconstructable without adding a new event
type or changing historical event fields.

For an irrelevant or errored Tool, the existing event shape remains unchanged
and no rule event is present. For a historical manual rule decision, the
existing `RuleEvaluationEvent` relationship remains unchanged.

The runtime must validate the automatic batch against the fixed closure request
before appending it. The trace assembler then enforces structural provenance
and must reject:

- more than one automatic rule batch from one Tool decision;
- a rule batch after an irrelevant or errored Tool;
- non-append-only Observation, Evidence, or rule deltas.

Semantic tests independently verify that the appended batch equals a direct
RuleEngine evaluation of the required profile and exact Observation Evidence.
The trace assembler does not load profiles or re-run rules.

Existing recorded traces require no migration and must round-trip unchanged.

## 11. v9.7 prompt contract

The v9.7 prompt will be created from frozen v9.6 source without mutating v9.6
bytes. It must remove, rather than merely contradict, inherited instructions
that tell the model to choose or emit rule-evaluation actions.

The final v9.7 prompt must:

- omit positive JSON examples with `decision_type="evaluate_rules"`;
- omit instructions to evaluate `profile_s1_distortion` manually;
- omit `evaluate_rules` from the advertised v9.7 decision choices;
- state that relevant Tool observations automatically produce rule batches;
- instruct the planner to cite the resulting same-run `ruleval_*` IDs;
- instruct the planner to call the required Tool when a needed rule family is
  absent, rather than requesting a profile directly;
- retain v9.6 mode routing, clipping independence, contextual harmonic gates,
  natural-even behavior, nominal limitation, combined behavior, and
  `no_supported_fault` requirements;
- contain no numerical threshold value;
- retain single-object JSON output and no-fallback requirements.

The runtime rejection in Section 9 remains necessary even though the prompt no
longer advertises the historical action. Prompt compliance is not treated as a
security or correctness boundary.

## 12. Finish semantics

v9.7 does not weaken or auto-satisfy any finish gate. It reuses the v9.6
contextual finish validator:

- clipping still requires `clipping_mechanism=true` plus a same-run substantial
  clipping rule FAIL;
- paired harmonic distortion still requires valid contextual analysis, F0
  compatibility, acceptable reference clipping, and harmonic-growth FAIL;
- nominal harmonic distortion still requires contextual validity, F0
  compatibility, `test_series_kind=even_order_present`, nominal THD FAIL, and
  the declaration limitation;
- `single_signal` harmonic structure remains descriptive and cannot become a
  causal harmonic-distortion claim;
- `no_supported_fault` still requires test clipping exclusion plus the
  mode-specific harmonic/contextual PASS family;
- combined still requires independently complete clipping and harmonic claims;
- invalid or insufficient context remains `inconclusive` with same-run
  grounding and a non-empty limitation;
- positive faults and sibling `no_supported_fault` remain mutually exclusive.

The LLM still selects the final Evidence and rule refs. Unknown, missing, or
semantically insufficient refs continue to produce a recoverable finish error.
The runtime must not silently add refs to make a proposed claim valid.

## 13. Failure handling

The following are runtime failures, not diagnoses:

- the rule engine or profile loader is absent when v9.7 requires closure;
- the fixed profile cannot be loaded;
- RuleEngine evaluation raises;
- a relevant non-error Tool produces no Evidence;
- the runtime produces a batch inconsistent with the closure request;
- trace assembly cannot prove the append-only Tool-to-rule relationship.

These terminate as `runtime_error`; none may become `inconclusive` and none may
fall back to `ScriptedPlanner`.

Planner schema errors, manual `evaluate_rules`, invalid finish refs, and missing
finish gates remain recoverable behavioral errors subject to the existing retry
limit. Provider errors retain their existing classification and campaign stop
policy.

## 14. Test contract

Allocate T-CX166 through T-CX185 without changing T-CX001 through T-CX165:

- T-CX166: v9.6 prompt SHA and preserved v9.6 run artifacts remain unchanged;
- T-CX167: causal-policy literal compatibility and v9.7 inheritance are exact;
- T-CX168: clipping maps to the distortion profile in every mode;
- T-CX169: paired contextual analysis maps to the contextual profile;
- T-CX170: nominal contextual analysis maps to the contextual profile;
- T-CX171: single-signal harmonic analysis maps to the distortion profile;
- T-CX172: spectrum, fundamental, and errored Tools create no closure;
- T-CX173: invalid relevant Tool Evidence creates `not_applicable` rules;
- T-CX174: closure uses the exact complete same-observation Evidence suffix;
- T-CX175: automatic closure increments and respects the existing rule bound;
- T-CX176: empty Evidence and dependency failures terminate fail-closed;
- T-CX177: v9.7 rejects manual rule decisions without consuming rule budget;
- T-CX178: v9.4, v9.5, and v9.6 manual-rule behavior remains unchanged;
- T-CX179: Tool trace emits Observation then RuleEvaluation with one cause;
- T-CX180: historical and v9.7 traces both round-trip and preserve deltas;
- T-CX181: v9.7 prompt removes positive manual-rule instructions and examples;
- T-CX182: v9.7 prompt retains mode, finish, and no-fallback semantics;
- T-CX183: composition selects v9.7 prompt and policy without thresholds;
- T-CX184: deterministic replay covers clean, natural-even, harmonic, combined,
  invalid, and clipping families;
- T-CX185: cumulative architecture, preservation, packaging, and registry gate.

T-CX184 uses deterministic fixtures or preserved observation-level Evidence.
It must not invoke a model, alter historical trace files, inspect validation
assets, or claim model-level success.

## 15. Offline shadow replay

Before any new model call, an offline audit will replay the preserved v9.6
observation Evidence through the proposed closure mapping without modifying the
v9.6 run. The audit must demonstrate:

- every completed clipping observation maps to the unchanged distortion
  profile;
- every paired/nominal contextual observation maps to the contextual profile;
- the five observed harmonic/combined positives produce the required
  contextual FAIL family from their existing Evidence;
- clean and natural-even observations produce the required contextual PASS
  family when their Evidence qualifies;
- invalid observations yield deterministic FAIL or `not_applicable` results
  consistent with the frozen profiles;
- no expected label is used as an input to mapping or rule evaluation.

This replay establishes harness correctness only. It is not a replacement for
a real-model development confirmation and does not repair or supersede the
v9.6 run.

## 16. Acceptance and stop gates

Implementation reaches `v9_7_harness_complete` only when:

- each new behavior is introduced by a failing test and made green by the
  smallest implementation;
- T-CX166 through T-CX185 pass;
- the complete contextual and full pytest suites pass with zero required
  skip/xfail;
- Ruff, `mypy src`, architecture, preservation, and
  `git diff --check 605c8a8` pass;
- wheel contents and smoke tests remain valid if packaged files change;
- the required CPython 3.11 and 3.12 clean-environment matrix passes for the
  release gate;
- v9.5/v9.6 prompt hashes and all preserved Task 13/v9.6 run assets remain
  unchanged;
- the v9.7 prompt version, prompt SHA, causal policy, and code identity are
  recorded;
- the offline shadow replay passes;
- no validation path is accessed and no real model is invoked.

`v9_7_harness_complete` is a code and offline-evidence conclusion only. It is
not `development_confirmed`, validation success, or demonstrated performance
improvement.

## 17. Real-model gate after code acceptance

A new v9.7 development confirmation requires separate authorization. It must:

- use a new append-only run directory;
- preflight the exact code, prompt, profile, manifest, and model identities;
- use `RealLLMPlanner` with `scripted_planner_fallback=false`;
- execute each of the 20 frozen development slots once;
- retain all behavioral and infrastructure failures;
- preserve the v9.5 and v9.6 directories unchanged;
- score behavioral failures as incorrect under the corrected scoring adapter;
- report the frozen development targets without changing their denominators.

The target can be claimed only if the newly recorded run satisfies all frozen
gates, including planner completion at least 0.95, outcome accuracy at least
0.80, causal exact-set accuracy at least 0.75, evidence grounding 1.00,
unsupported-claim rate zero, the inconclusive gate, and the natural-even false
positive gate.

Only a `meets_target` development result plus a new explicit authorization may
permit validation construction or execution. A `below_target` result is
preserved and returns to evidence-level diagnosis; validation remains closed.

## 18. Protected assets and workspace boundaries

The implementation and later campaign must not modify:

- V0.2 Phase 4.3.1 official bundles;
- the accepted V0.2 Demo;
- v8.1, v9.4, v9.5, or v9.6 prompt bytes and identities;
- v9.5 or v9.6 recorded run directories;
- `profile_s1_distortion` thresholds;
- `profile_s1_contextual_comparison` thresholds;
- the `v0.2.0` tag;
- scoring identities or historical Git commits.

The currently untracked V0.2 investigation report and V0.3 validation tree are
outside this design's write scope and remain untouched.
