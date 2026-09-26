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

The product claim specifically requires a real LLM to demonstrate dynamic Tool
selection on the public path. A real LLM is not a reliable CI oracle, so the
design separates the model boundary from the controller:

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

**Phenomenon.** The first official Agent could diagnose several cases while
rarely choosing the newly implemented rule and knowledge actions.

**Evidence.** The immutable
[80-slot Phase 4 bundle](evaluations/phase4/bench_official_s1_20260829t162243z/)
was `completed/below_target`: causal macro F1 0.840, applicable-rule usage
0.513, required-knowledge usage 0, and evidence grounding 0.895.

**Root cause.** Phase 3 proved that rule and knowledge actions were callable and
correct, but the real planner did not consistently choose them. Deterministic
availability did not prove product-path behavior.

**Decision.** Keep the official bundle immutable, separate harness completion
from target achievement, and add behavior-development gates before a new
held-out run.

**Fix.** Freeze an additive Phase 4.1 behavior gate with explicit rule,
knowledge, grounding, replanning, and stopping metrics; tune only on a
development split.

**Verification.** The original bundle stayed byte-for-byte historical evidence.
Later campaigns report separate development/official identities instead of
overwriting this run.

**Lesson.** Tool existence, controller correctness, and model behavior are
different claims and need different evidence.

### 2. Prompt additions fixed usage but created contradictory behavior

**Phenomenon.** The planner began using rules and knowledge, but boundary,
combined, and inconclusive cases became internally inconsistent.

**Evidence.** The
[v5 development bundle](evaluations/phase4_1/development/bench_phase4_1_dev_v5_gate1/)
raised rule usage to 0.854 and required-knowledge usage to 1.0, yet causal F1
fell to 0.75, grounding to 0.789, and knowledge-citation utilization to 0.2.
The
[v6 development bundle](evaluations/phase4_1/development/bench_phase4_1_dev_v6_gate2/)
improved causal F1 to 0.969 and citation utilization to 1.0, but grounding
remained 0.857 and unsupported claims reached 0.0625.

**Root cause.** Additive prompt text competed with older examples. A 5% THD
boundary could be treated as “no fault” even when harmonic evidence existed;
combined distortion could stop after clipping; inconclusive examples could
finish with empty claims and uncited knowledge.

**Decision.** Replace append-only patches with coherent versioned prompts,
freeze every prior prompt identity, and stop each campaign honestly when its
development gate missed.

**Fix.** v6 became one coherent prompt rather than a v4/v5 appendix, with
explicit boundary, combined-hypothesis, and inconclusive-citation policy.

**Verification.** v6 improved the targeted metrics but still missed the frozen
grounding and unsupported-claim bands, so official v1.1.0 held-out was not run
and the `below_target` development bundle was retained.

**Lesson.** Prompt text is executable policy. Examples and prose must express
one consistent state machine.

### 3. Evaluation integrity had to be repaired before more prompt tuning

**Phenomenon.** A prompt-only v7 could appear to improve behavior while using
information that was unavailable in a genuine user request.

**Evidence.** Independent review found semantic IDs such as
`clipping_strong`, different first-Tool expectations for otherwise equivalent
visible contexts, and combined cases whose causal distinction depended on a
hidden matched control.

**Root cause.** The evaluator knew distinctions that the planner could not
legitimately observe. A better score under those conditions would not establish
better reasoning.

**Decision.** Dataset 1.2.0 introduced opaque outbound IDs, first-Tool fairness
based only on visible context, fresh cases/seeds, and single-signal combined
distortion with visible generation parameters. Official gates also require a
complete, identity-matched development bundle before loading held-out inputs or
creating the SDK client.

**Fix.** Implement Dataset 1.2.0 and the v7 campaigns under the frozen
[Phase 4.2 design](superpowers/specs/2026-08-30-phase4-2-prompt-v7-correction-design.md),
including preflight identity validation before any official model/client work.

**Verification.** The
[v7 development bundle](evaluations/phase4_2/development/bench_phase4_2_dev_v7_v12_gate3/)
still missed first-Tool selection (0.75), observation-driven replanning
(0.719), unnecessary Tool rate (0.405), and required-knowledge usage (0.2).
Official held-out remained unopened. Because evaluation integrity was now
credible, these failures could be attributed to behavior rather than label
leakage.

**Lesson.** A held-out score is meaningful only when the model cannot infer the
answer from identifiers or invisible evaluator assumptions.

### 4. A failed v8 run exposed a contract/scoring mismatch, not just a model miss

**Phenomenon.** v8 selected the first Tool and knowledge correctly but still
received systematic grounding, stopping, and unsupported-claim failures.

**Evidence.** The
[v8 development bundle](evaluations/phase4_3/development/bench_phase4_3_dev_v8_v12_gate4/)
recorded first-Tool selection 1.0 and knowledge usage 1.0 but evidence grounding
0.849, timely stopping 0.75, and unsupported claim rate 0.211.

**Root cause.** T210 globally prohibited a clipping-specific finish that was
legal under the scenario, while the legacy scoring proxy mishandled the
required invalid-Evidence -> NOT_APPLICABLE rule transition.

**Decision.** Do not stack another prompt. Freeze a narrow Phase 4.3.1
compliance correction: v8.1 clarified the legal finish scope, and scoring 2.0.0
recognized the frozen invalid-Evidence semantics. Runtime, PlannerContext,
dataset, target bands, provider, and model stayed unchanged.

**Fix.** Implement the frozen
[Phase 4.3.1 correction](superpowers/specs/2026-08-30-phase4-3-1-v8-1-compliance-correction-design.md):
the coherent v8.1 policy plus versioned scoring 2.0.0, with historical v4–v8
identities unchanged.

**Verification.** v8.1 passed all 11 target bands on 40 development slots before
the one-time 80-slot official run was authorized. Both accepted bundles remain
separate from every failed predecessor.

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

## Incremental external validity: from single-WAV ambiguity to context

The accepted V0.2 official benchmark primarily used synthetic signals. A later
incremental external-WAV study therefore tested public recordings, controlled
distortions on real-recording masters, and domain-out audio. It completed
honestly as `below_target`: the system could process real WAV inputs, but
single-WAV harmonic measurements did not consistently establish whether
harmonics were newly introduced or already present in the source.

The response was not to relabel those failures or lower the frozen 1% clipping
and 5% THD demonstration thresholds. V0.3 introduced two explicit observation
modes inside the same Scenario S1 boundary:

- `paired_reference` compares a test recording with its clean reference;
- `nominal_single_tone` uses a declared single-tone stimulus contract.

Development runs retained successive failures while the implementation added
deterministic contextual DSP, mode-aware causal gates, automatic rule closure,
and conservative recovery guidance. The v9.11 development confirmation met its
frozen gate before validation was resealed.

The final contextual validation froze 20 cases and ran three arms once in a
fixed 60-slot order: the contextual Agent, a truth-free deterministic fixed
pipeline, and a no-context ablation. The contextual Agent completed 19/20
slots, reached 16/17 outcome and causal exact-set accuracy, harmonic recall 5/5,
clipping recall 5/6, and a +4 paired-harmonic causal advantage over ablation.

Independent review then found an evaluator defect: two claim-level metrics used
the 17-case outcome denominator instead of their preregistered dynamic
populations. The raw `below_target` output was preserved. A TDD correction added
claim-level same-run reference accounting and deterministic replay from the
immutable result files. Correct scoring produced 21/21 grounded claims and
0/10 unsupported positive claims; all aggregate and role gates passed, yielding
the append-only verdict `meets_target`.

This result is deliberately narrow. It shows that declared reference or
stimulus context materially improved harmonic attribution on one small,
license-traceable external/contextual study. It is not an official benchmark,
industrial validation, production certification, general audio diagnosis, or
a contextual final external test. The earlier V0.2 external-WAV
`below_target` result remains part of the evidence trail.

### Honest public positioning

A concise, supportable description is:

> Built and evaluated a hybrid signal-diagnosis Agent combining deterministic
> DSP, versioned causal rules, and LLM planning; designed a sealed three-arm
> external/contextual WAV study where v9.11 achieved 16/17 outcome and causal
> exact-set accuracy, 21/21 grounded claims, and 0/10 unsupported positive
> claims, while preserving failed runs and an append-only scorer correction.

Avoid claims of industrial validation, production readiness, industry-standard
thresholds, a general-purpose audio diagnostician, or an official external
benchmark.

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
- [V0.3 contextual validation acceptance](evaluations/v0_3/contextual/V9_11_CONTEXTUAL_VALIDATION_ACCEPTANCE_REPORT.md)
- [Formal specs and implementation plans](superpowers/)

### Demo checksum portability note

The retained Demo README records JSON/HTML hashes from the Windows acceptance
worktree. Git stores those text blobs with LF line endings while a Windows
checkout may materialize CRLF, so raw text-file hashes can differ by checkout.
The WAV and PNG hashes are byte-stable. Official evaluation-bundle validation
uses its frozen LF-normalized checksum policy and is unaffected. The accepted
Demo files and their original table remain unchanged.
