# Engineering Case Study: Signal Diagnosis Agent V0.2

## The problem

Scenario S1 asks a narrow but nontrivial question: “Why does this periodic
signal sound distorted?” The goal was not to hard-code a pipeline that always
runs clipping, FFT, F0, and THD. The product had to let a real LLM choose the
next justified action, inspect structured observations, replan, and stop when
the evidence was sufficient.

The accepted diagnosis space is deliberately narrow: clipping, harmonic
distortion, and basic frequency/fundamental evidence when needed. Synthetic
signals provide known ground truth; bounded PCM WAV makes the vertical slice
interactive.

## Why the architecture is hybrid

A real LLM is necessary to demonstrate dynamic Tool selection. It is not a
reliable CI oracle. The design therefore separates the model boundary from the
controller:

```text
PlannerModel
    |- RealLLMPlanner      product path
    `- ScriptedPlanner     deterministic test double
```

`DistortionDiagnosisRuntime` owns state transitions, Tool execution, observation
propagation, retries, invalid-action handling, no-progress detection, call
limits, and termination. It does not force a fixed Tool sequence. DSP owns
numeric calculations, rule profiles own thresholds, and the LLM sees compact
structured Evidence rather than raw arrays.

This split produced two distinct validation layers:

1. deterministic system acceptance for routing, state, Tool execution,
   propagation, errors, and termination;
2. real-model behavior evaluation for first Tool, replanning, unnecessary
   actions, stopping, grounding, and diagnosis quality.

## End-to-end design

```text
signal -> dsp -> tools -> rules/knowledge -> agent -> evaluation -> app
```

- Signal repositories are immutable and store full-scale `float32` waveforms.
- DSP implements explainable clipping, spectrum, autocorrelation F0, and
  harmonic analysis.
- Tools convert DSP results into compact Evidence with stable IDs.
- Rules evaluate Evidence against a versioned demonstration profile.
- Knowledge retrieval is deterministic over a curated local Markdown corpus.
- The Agent chooses actions and must cite same-run Evidence/rules/knowledge.
- Evaluation compares the Agent with an honest fixed pipeline.
- The application layer exposes the same service through CLI, API, Web UI,
  JSON, and HTML.

## The failures that improved the system

The project retained every material target miss rather than optimizing the
story after the fact.

### 1. The first official run showed that “callable” is not “used”

**Symptom.** The first 80-slot official Phase 4 run was
`completed/below_target`. Causal macro F1 was 0.840, but applicable-rule usage
was 0.513, required-knowledge usage was 0, and evidence grounding was 0.895.

**Root cause.** Phase 3 had implemented correct rule and knowledge actions, but
the real planner did not consistently choose them. Deterministic availability
did not prove product-path behavior.

**Decision.** Keep the official bundle immutable, separate harness completion
from target achievement, and add behavior-development gates before a new
held-out run.

**Lesson.** Tool existence, controller correctness, and model behavior are
different claims and need different evidence.

### 2. Prompt additions fixed usage but created contradictory behavior

**Symptom.** v5 raised rule usage to 0.854 and required-knowledge usage to 1.0,
yet causal F1 fell to 0.75, grounding to 0.789, and knowledge-citation
utilization to 0.2. v6 improved causal F1 to 0.969 and citation utilization to
1.0, but grounding remained 0.857 and unsupported claims reached 0.0625.

**Root cause.** Additive prompt text competed with older examples. A 5% THD
boundary could be treated as “no fault” even when harmonic evidence existed;
combined distortion could stop after clipping; inconclusive examples could
finish with empty claims and uncited knowledge.

**Decision.** Replace append-only patches with coherent versioned prompts,
freeze every prior prompt identity, and stop each campaign honestly when its
development gate missed.

**Lesson.** Prompt text is executable policy. Examples and prose must express
one consistent state machine.

### 3. Evaluation integrity had to be repaired before more prompt tuning

**Symptom.** Review found that semantic signal IDs could expose labels such as
`clipping_strong`, visible request metadata did not fully justify different
first-Tool expectations, and combined cases relied on hidden matched controls.

**Root cause.** The evaluator knew distinctions that the planner could not
legitimately observe. A better score under those conditions would not establish
better reasoning.

**Decision.** Dataset 1.2.0 introduced opaque outbound IDs, first-Tool fairness
based only on visible context, fresh cases/seeds, and single-signal combined
distortion with visible generation parameters. Official gates also require a
complete, identity-matched development bundle before loading held-out inputs or
creating the SDK client.

**Verification.** v7 used the repaired dataset but still missed first-Tool
selection (0.75), observation-driven replanning (0.719), unnecessary Tool rate
(0.405), and required-knowledge usage (0.2). Because evaluation integrity was
now credible, those failures could be attributed to behavior rather than label
leakage.

**Lesson.** A held-out score is meaningful only when the model cannot infer the
answer from identifiers or invisible evaluator assumptions.

### 4. A failed v8 run exposed a contract/scoring mismatch, not just a model miss

**Symptom.** v8 achieved first-Tool selection 1.0 and knowledge usage 1.0 but
missed evidence grounding (0.849), timely stopping (0.75), and unsupported
claim rate (0.211).

**Root cause.** T210 globally prohibited a clipping-specific finish that was
legal under the scenario, while the legacy scoring proxy mishandled the
required invalid-Evidence -> NOT_APPLICABLE rule transition.

**Decision.** Do not stack another prompt. Freeze a narrow Phase 4.3.1
compliance correction: v8.1 clarified the legal finish scope, and scoring 2.0.0
recognized the frozen invalid-Evidence semantics. Runtime, PlannerContext,
dataset, target bands, provider, and model stayed unchanged.

**Lesson.** When evaluation disagrees with a frozen contract, fix the evaluator
or written policy explicitly; do not train the model to game a faulty proxy.

### 5. The accepted gate remained honest about residual failures

**Development.** v8.1 passed all 11 target bands on 40 development Agent slots.

**Official.** The one-time 80-slot held-out run was
`completed/meets_target`:

- causal macro F1: 1.0;
- evidence grounding: 1.0;
- first-Tool selection: 1.0;
- observation-driven replanning: 0.995;
- timely stopping: 1.0;
- unnecessary Tool action rate: 0.0;
- unsupported claim rate: 0.0;
- outcome accuracy: 79/80.

Two slots retain behavior failure codes. One of them is the single wrong
outcome. The aggregate meets the frozen target bands, but the UI, README, and
bundle continue to disclose both numbers.

## Why the fixed pipeline still matters

The fixed pipeline is not the product Agent. It is an honest baseline that runs
the predetermined analysis sequence. It provides a reproducible comparison for
Tool count, diagnosis quality, and stopping behavior. The Agent must justify
its dynamic choices rather than win because the baseline was intentionally
weakened.

## Turning the core into a demonstrable product

Phase 5 added presentation without moving domain logic into adapters:

- strict, bounded PCM WAV decoding;
- five public synthetic presets;
- one `DiagnosisApplicationService` shared by CLI and FastAPI;
- a native Web UI with real queued/running/completed lifecycle state;
- actual chronological Agent trace, Evidence, rule, and knowledge sections;
- canonical JSON and self-contained HTML reports;
- packaged static/evaluation assets and clean wheel installation;
- local CPython 3.11/3.12 clean-environment acceptance;
- two retained real-model product Demo runs, one Web preset and one WAV CLI.

The final deterministic suite contains 1006 passing tests. The real Demo is a
separate product-path check and never becomes a stochastic CI requirement.

## What this project demonstrates

- Contract-first boundaries around an LLM without turning the controller into
  the product Agent.
- Numerical and threshold provenance: DSP calculates; profiles judge; the LLM
  explains and plans.
- Traceability across Evidence, rules, knowledge, decisions, and final claims.
- Held-out discipline, immutable benchmark assets, and explicit stop gates.
- Willingness to treat evaluator defects as first-class engineering defects.
- Thin presentation adapters over one tested service rather than duplicated
  business logic.

## Limits and next version boundary

V0.2 remains narrow. It does not claim general audio diagnosis, hardware
qualification, production capture coverage, universal pitch tracking,
industry-standard thresholds, authentication, persistence, vector retrieval,
or deployment hardening. Expanding those areas would require new contracts,
datasets, test IDs, and evaluation gates rather than an informal extension of
the accepted result.

## Evidence map

- [Frozen architecture](ARCHITECTURE_V0_2.md)
- [Frozen contracts](CONTRACTS_V0_2.md)
- [T001–T285 acceptance plan](TEST_PLAN_V0_2.md)
- [D001–D031 decisions](DECISIONS.md)
- [Historical and accepted evaluation bundles](evaluations/)
- [Accepted official v8.1 bundle](evaluations/phase4_3_1/official/bench_official_s1_v12_planner8_1_gate5/)
- [Real product Demo](demo/phase5/v0_2_acceptance/README.md)
- [Formal specs and implementation plans](superpowers/)
