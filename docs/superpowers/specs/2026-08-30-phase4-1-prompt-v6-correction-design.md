# Phase 4.1 Prompt v6 Correction Design

**Date:** 2026-08-30

**Status:** Approved on 2026-08-30; Task 2–8 implementation authorized;
real-model held-out remains development-gated

**Baseline:** `f9392c2` (`phase4-evaluation-design`)

**Scope:** Phase 4.1 prompt-only remediation after the v5 development gate

## 1. Purpose

The first Phase 4.1 development campaign is valid, complete, and below target.
The immutable bundle at
`docs/evaluations/phase4_1/development/bench_phase4_1_dev_v5_gate1/` contains
40 scoreable DeepSeek Agent slots over the eight v1.1.0 development cases and
eight deterministic baseline slots. It records:

```text
benchmark_status = completed
target_status = below_target
causal_macro_f1 = 0.75
evidence_grounding_rate = 30 / 38
knowledge_citation_utilization_rate = 1 / 5
```

Applicable-rule use reached 35/41 and required-knowledge use reached 5/5, so
v5 improved action selection without meeting the complete behavior gate. The
remaining failures are concentrated and reproducible. Phase 4.1 prompt v6
corrects those prompt semantics before any v1.1.0 held-out run.

This design does not weaken targets, change evaluation truth, modify DSP or
rule calculations, force actions in the Runtime, or hide the v5 result.

## 2. Verified root cause

`v0.2-s1-planner-5` was constructed by appending a short Phase 4.1 policy to
the complete v4 prompt. The resulting system prompt contains competing
instructions and examples:

- the v4 supported-fault example describes fault support as exceeding a
  threshold, while the v5 policy says causal distortion and configured rule
  acceptance are independent facts;
- the v4 inconclusive example explicitly permits and demonstrates an empty
  `claims` array, while the v5 policy requires an inconclusive claim that cites
  invalid Evidence and retrieved knowledge;
- the v4 stopping rule says to stop once supported Evidence is sufficient,
  without explicitly requiring resolution of every still-viable requested S1
  hypothesis;
- the v4 no-fault language does not distinguish a negative observation about
  one fault family from the final diagnosis `no_supported_fault`.

The v5 development traces follow the older examples consistently:

1. `case_v11_dev_harmonic_boundary` finished `no_supported_fault` in all five
   slots even though deterministic Evidence supported injected harmonic
   distortion and the independent rule result passed the 5% demonstration
   limit.
2. `case_v11_dev_combined_01` finished after clipping Evidence in all five
   slots without testing the still-viable harmonic hypothesis.
3. `case_v11_dev_invalid_noise_01` retrieved required knowledge in all five
   slots, but four finishes used empty claims and therefore did not cite the
   retrieval. The remaining finish formed an ungrounded no-fault claim.
4. Two `case_v11_dev_harmonic_strong` slots added a separate
   `no_supported_fault` claim for absent clipping alongside a supported
   harmonic fault.

The correction belongs at the prompt boundary. No evidence indicates a DSP,
RuleEngine, KnowledgeIndex, Runtime, trace-assembly, or scorer defect.

## 3. Approaches considered

### 3.1 Rewrite v5 in place — rejected

The v5 prompt version and SHA-256 are embedded in the committed gate1 bundle.
Changing its bytes would make the recorded behavioral configuration
unreproducible and violate append-only evaluation provenance.

### 3.2 Append another policy block to v5 — rejected

This would retain the contradictory v4 examples that dominated gate1 behavior
and would create a third layer of precedence for the model to infer.

### 3.3 Add a coherent v6 prompt and additive campaigns — approved design

Create `v0.2-s1-planner-6` as one self-contained system prompt. Preserve v4,
v5, their exact SHA-256 values, their planner builders, their CLI campaign
routes, and all existing report bundles. Add separate v6 development and
official campaign identities over the existing v1.1.0 manifest.

PlannerContext presentation and the DeepSeek model remain unchanged. If this
second prompt-only development candidate is below target, work stops for a new
design decision; it does not silently expand into a context or model change.

## 4. Prompt identity and composition

The new prompt specification is:

```text
version: v0.2-s1-planner-6
composition: one complete prompt, not v4 + appendix and not v5 + appendix
provider: deepseek
model: deepseek-v4-flash
dataset: s1-distortion-synthetic 1.1.0
profile: profile_s1_distortion 1.0.0-demo
```

The exact prompt bytes and SHA-256 are frozen during implementation before a
real development slot runs. The hash is stored in every v6 configuration and
report artifact.

`RealLLMPlanner` remains the product planner and makes v6 the active product
prompt only after deterministic tests pass. Private prompt-bound planner
subclasses preserve exact v4 and v5 campaign execution. Product failure never
falls back to ScriptedPlanner or a fake transport.

## 5. Coherent v6 decision policy

The prompt continues to return exactly one existing `AgentDecision` variant:

```text
call_tool | evaluate_rules | retrieve_knowledge | finish
```

No public model, field, action, or Runtime transition changes.

### 5.1 Maintain hypotheses until they are resolved

The planner starts with the supported S1 hypotheses that remain plausible from
the request, metadata, and current structured observations. A positive result
for one fault family does not eliminate another viable family. The planner may
finish only when every still-viable requested hypothesis is either supported,
ruled out by sufficient Evidence, or explicitly left unresolved in an
inconclusive result.

This is not a fixed pipeline. A clipping-only case may stop after clipping when
the observations make a separate harmonic cause non-viable. A combined case
requires separate harmonic Evidence because clipping Evidence alone cannot
establish the complete causal set. Tool order remains dynamic.

### 5.2 Separate observed distortion from configured acceptance

DSP Evidence answers whether an observable distortion characteristic is
present. A rule evaluation answers whether Evidence satisfies the configured
demonstration profile. The final diagnosis may and sometimes must report both:

> Harmonic distortion is present in the deterministic Evidence, while the
> observed THD still satisfies the configured 5% demonstration limit.

A PASS rule result cannot turn supported harmonic Evidence into
`no_supported_fault`. A FAIL rule result cannot create a fault without
supporting Evidence. Threshold values are cited from live rule evaluations,
not calculated or invented by the model.

### 5.3 Use no-fault claims only as a final set conclusion

`fault_type="no_supported_fault"` is valid only when the complete supported S1
diagnosis set is empty after sufficient investigation. Negative clipping
Evidence inside a harmonic fault run is supporting context, not a separate
no-fault diagnosis claim. A `supported_fault` diagnosis must not contain a
`no_supported_fault` claim.

### 5.4 Make inconclusive results traceable

When invalid or not-applicable deterministic output prevents a supported or
no-fault conclusion, the planner:

1. evaluates the applicable S1 Evidence under the configured profile once;
2. retrieves curated explanatory knowledge when no relevant retrieval exists;
3. produces at least one `fault_type="inconclusive"` claim;
4. cites the invalid/not-applicable Evidence ID, applicable `ruleval_*` IDs,
   and the used `know_*` retrieval ID in that claim;
5. includes a non-empty limitation describing what could not be established.

The prompt contains no empty-claim inconclusive example. An empty or irrelevant
knowledge result is never cited and never authorizes fabricated explanation.

### 5.5 Rule and knowledge actions remain selective

The planner evaluates rules only after relevant Evidence exists and only once
for the same applicable Evidence/profile state. It retrieves knowledge for an
invalid/not-applicable explanation or material limitation, not to decorate a
straightforward supported or clean result. The Runtime retains the frozen
budgets and no-progress behavior.

### 5.6 Same-run references remain mandatory

Every diagnosis claim cites only IDs present in the current PlannerContext.
Evidence, rule-evaluation, and knowledge IDs must resolve in the same run.
Waveform samples, full FFT arrays, causal labels, split identity, knowledge
policy, sufficient-Evidence sets, and scoring conditions remain absent from
the model context.

## 6. Examples in the v6 prompt

Examples teach output shape without encoding one mandatory Tool sequence. The
complete prompt includes exactly these semantic examples:

- a supported clipping claim with live Evidence and rule references;
- a harmonic-boundary claim where distortion is present and the configured
  rule is PASS;
- a combined diagnosis containing clipping and harmonic-distortion claims with
  their separate Evidence;
- an inconclusive claim with invalid Evidence, NOT_APPLICABLE rule references,
  a knowledge reference, and a non-empty limitation;
- a clean final-set conclusion using `no_supported_fault` only after both
  supported families are sufficiently ruled out.

Example IDs are visibly illustrative placeholders and are never presented as
current-context IDs. The prompt continues to require live IDs from the actual
PlannerContext before `finish`.

## 7. Backward-compatible runner identities

The existing choices remain unchanged and continue to select v5:

```text
phase4.1-development
phase4.1-official
```

The correction adds:

```text
phase4.1-v6-development
phase4.1-v6-official
```

The v6 campaigns reuse the validated v1.1.0 manifest because none of its
held-out cases has been executed. Development continues to use only the eight
development IDs. Existing v4 and v5 configuration builders, fingerprints, and
campaign routes remain reproducible.

The second development bundle identity is fixed as:

```text
docs/evaluations/phase4_1/development/bench_phase4_1_dev_v6_gate2/
```

Only after that bundle reaches `completed/meets_target` may the official v6
campaign run once as:

```text
docs/evaluations/phase4_1/official/bench_official_s1_v11_planner6_gate2/
```

Both writers retain append-only refusal. Neither destination may exist before
execution.

## 8. Deterministic acceptance extension

The frozen T184–T195 tests remain unchanged as evidence for the v5 correction
wave. The v6 design adds, rather than renumbers or rewrites, these tests:

```text
T196  v4/v5 prompt and campaign immutability; exact v6 prompt identity/hash
T197  coherent v6 dual-truth, combined-hypothesis, no-fault, and inconclusive policy
T198  v6 no-leakage, same-run refs, rule/knowledge propagation, and dynamic routes
T199  additive v6 development/official campaign identity and split scheduling
T200  cumulative T001–T200 gate, Ruff, mypy, architecture, and diff-check
```

Deterministic tests use fake model transports or ScriptedPlanner only where the
existing test boundary permits them. They exercise the real Runtime, Tools,
RuleEngine, KnowledgeIndex, trace assembly, and scorers. No real LLM call enters
pytest.

## 9. Real-model gate protocol

### 9.1 Development gate2

Run exactly five slots for each of the eight v1.1.0 development cases. Verify
the six-file bundle independently, recompute all scores/aggregates, and require:

```text
benchmark_status = completed
target_status = meets_target
all 40 Agent slots scoreable
every non-zero-denominator target passes
```

The v5 gate1 bundle remains present and byte-identical. A gate2 result below
target is committed honestly and stops the correction before held-out.

### 9.2 Official gate2

The official run is authorized only after independent verification of the
development result and exact configuration identity apart from benchmark ID,
timestamp, and selected split. It runs 16 v1.1.0 held-out cases five times each
and requires the existing Phase 4.1 acceptance bands without modification.

If official gate2 is below target, retain it, leave Phase 4.1 unaccepted, keep
Phase 5 gated, and do not tune against or rerun those held-out cases.

## 10. Error handling and stopping conditions

Existing planner-output repair, infrastructure retry, no-progress, Tool, rule,
and knowledge budgets remain authoritative. Invalid output is a behavioral
result after the frozen repair budget; it is not replaced by scripted output.

The correction stops for a new user-approved design decision when:

- v6 development gate2 is below target;
- a correct prompt-only implementation requires changing PlannerContext;
- DeepSeek/model configuration must change;
- a frozen public Runtime, evaluation, scoring, or report interface appears
  unable to represent correct behavior.

No v7 prompt, context presentation change, model change, target change, or new
held-out dataset is introduced automatically.

## 11. Contract treatment

Frozen §50 and T184–T195 describe the completed v5 correction wave and remain
unchanged. Because §50 normatively names v5 and T194 freezes its campaign, v6
implementation requires an additive contract decision rather than a silent
replacement.

Before code changes, written approval adds:

- `CONTRACTS_V0_2.md` §51 for the v6 correction wave;
- `TEST_PLAN_V0_2.md` §24 for T196–T200;
- `DECISIONS.md` D022 for immutable v5 and additive v6 campaign identities;
- closure of OQ-006 in `OPEN_QUESTIONS.md`.

These additions change no Phase 1–4 public Python interface. Until approved,
this design and its implementation plan are design assets only.

## 12. Non-goals

- editing or deleting v4, v5, `b68ec5e`, or `f9392c2` artifacts;
- changing v1.1.0 signal cases, causal truth, matched controls, or targets;
- running or inspecting v1.1.0 held-out behavior before gate2 passes;
- changing DSP algorithms, Evidence values, RuleEngine, rule thresholds,
  KnowledgeIndex, Runtime control, scoring, or report schemas;
- forcing rule, knowledge, or Tool actions in the controller;
- prescribing a universal Tool order;
- changing provider, model, PlannerContext presentation, or model parameters;
- adding WAV, API, UI, HTML/PDF reporting, or other Phase 5 work;
- expanding beyond the accepted S1 diagnosis space.

## 13. Definition of done

The v6 correction is accepted only when:

- §51, §24/T196–T200, and D022 are approved and frozen;
- T001–T200 pass with zero required skip/xfail;
- Ruff, mypy, architecture tests, and `git diff --check f9392c2..HEAD` pass;
- v4 and v5 prompt bytes, hashes, runner paths, and committed bundles remain
  unchanged;
- v6 development gate2 is `completed/meets_target`;
- the one-shot v6 official gate2 is `completed/meets_target` with all 80 Agent
  slots scoreable;
- both v6 bundles validate and their checksums match;
- the v1.0.0 official and v5 development below-target evidence remains visible;
- an independent final review confirms no Phase 5 implementation exists.

Completion authorizes Phase 5 design only. It does not authorize Phase 5 code,
merge, or push.
