# AGENTS.md

## Project

This repository implements a Signal Test and Fault Diagnosis Agent.

The current development phase is V0.2 Phase 4 gated: evaluation, including
Agent versus a fixed pipeline, is not authorized.

Phase 1 (T001–T063), Phase 2 (T064–T092), and Phase 3 (T093–T124) are complete
and accepted. Phase 3 is accepted on branch `phase3-rules-knowledge`. Do not
implement Phase 4 evaluation or Phase 5 presentation adapters until that phase
is explicitly authorized.

## Required reading

Before modifying code, read:

- `docs/README.md`
- `docs/ARCHITECTURE_V0_2.md` (especially §13)
- `docs/CONTRACTS_V0_2.md` (Phase 1–3 frozen)
- `docs/TEST_PLAN_V0_2.md` (Phase 1–3 required; T093–T124 in §21)
- `docs/DECISIONS.md`
- `docs/superpowers/plans/2026-08-28-phase1-deterministic-foundation.md`
- `docs/superpowers/plans/2026-08-29-phase3-rules-knowledge.md`

Phase 2 has no separate implementation plan under `docs/superpowers/plans/`.
Use `ARCHITECTURE_V0_2.md` §12 and the accepted Phase 2 contracts as the
implementation authority for Agent runtime work.

Phase 3 implementation authority remains `ARCHITECTURE_V0_2.md` §13, revised
`CONTRACTS_V0_2.md` §32–§40, and `TEST_PLAN_V0_2.md` §21 (T093–T124).
OQ-001 and OQ-003 were approved; Phase 3 is accepted. Do not start Phase 4
from this authorization.

These documents describe approved architecture and frozen interfaces.

Files under `docs/archive/v0.1/` are historical references only. Files under
`docs/context/` are non-normative background context.

## Source of truth

The Phase 1–3 interfaces in `docs/CONTRACTS_V0_2.md` are frozen. Phase 3
implementation must conform to §32–§40 and the T093–T124 acceptance gate.

Do not redesign or rename public models, functions, modules, arguments, return
values, or package boundaries unless the user explicitly requests a contract
change.

If you discover a problem with a frozen contract:

1. Do not silently change it.
2. Explain the problem.
3. Record the proposed change in `docs/OPEN_QUESTIONS.md`.
4. Continue only when the existing contract still permits a correct implementation.

## Architectural boundaries

The complete V0.2 dependency direction is:

`signal -> dsp -> tools -> rules/knowledge -> agent -> evaluation -> app`

Rules:

- `signal/` owns signal representation, repositories, segmentation, and synthetic generation.
- `dsp/` owns deterministic numerical algorithms.
- `tools/` adapts DSP functions into compact structured tool results.
- `rules/` owns versioned deterministic thresholds and PASS/FAIL/NOT_APPLICABLE
  judgments over Evidence.
- `knowledge/` owns curated corpus storage and deterministic keyword/tag retrieval.
- `agent/` owns Planner integration and deterministic runtime control.
- `evaluation/` will later own deterministic and real-model evaluation.
- `app/` will later own CLI/API/UI/report adapters.
- `signal/`, `dsp/`, `tools/`, `rules/`, and `knowledge/` must not depend on
  Agent or LLM frameworks.
- `rules/` and `knowledge/` must not depend on `agent/`.
- Raw waveform arrays must never be passed to an LLM.
- Full FFT arrays must never be passed to an LLM.
- Repository waveforms use `float32` with shape `(num_samples, channels)`.
- Repository data is immutable.
- DSP algorithms receive one-dimensional numeric arrays.
- Integer PCM is converted to full-scale floating point.
- Do not peak-normalize individual signals.
- Numerical metrics are produced only by deterministic DSP code.
- Pass/fail thresholds are not invented by an LLM; they come from versioned rule
  profiles in `rules/`.
- Tool adapters create compact deterministic Evidence.
- Every supported diagnosis claim must cite valid Evidence from the same run.
- Rule conclusions must cite valid rule-evaluation IDs from the same run.
- Knowledge citations explain claims; they do not substitute for signal Evidence.
- The product Agent will use `RealLLMPlanner`; `ScriptedPlanner` is only a test
  double and is never a silent product fallback.

## Gated next phases

Do not add:

- Phase 4 evaluation datasets, fixed-pipeline baseline, or report schemas
- Phase 5 WAV loader, FastAPI, web frontend, or HTML/PDF reporting
- LangGraph (unless explicitly requested and contract-approved)
- vector databases or embedding retrieval (initial Phase 3 uses keyword/tag only;
  see D011)
- large-scale knowledge ingestion or network search
- multi-agent architecture
- database persistence
- Docker infrastructure
- LLM-generated thresholds or standards

unless that later phase is explicitly authorized.

The complete project architecture is approved, but that approval does not waive
the Phase 4 gate.

## Completed phases (reference)

### Phase 1 — deterministic signal-analysis foundation (accepted)

Signal models, repository, segmentation, synthetic generators, DSP algorithms,
Tool contracts, Evidence, and tests T001–T063.

### Phase 2 — minimal end-to-end distortion-diagnosis Agent (accepted)

`PlannerModel`, `ScriptedPlanner`, `RealLLMPlanner`, `DistortionDiagnosisRuntime`,
S1 deterministic acceptance T064–T092, and separate R001–R006 real-model checks.

### Phase 3 — deterministic rules and knowledge retrieval (accepted)

Versioned `profile_s1_distortion` `1.0.0-demo` rule profiles, `RuleEngine`,
curated local Markdown corpus, keyword/tag `KnowledgeIndex`, runtime rule and
knowledge actions, and T093–T124. Demo thresholds are not industry standards.
The product-path runner is `scripts/run_phase3_real_model_eval.py`; the
real-model observation in `docs/reports/PHASE3_REAL_MODEL_BEHAVIOR_REPORT.md`
is **NOT RUN** because credentials were unavailable and is not a CI gate.

## Development workflow

Use test-driven development.

For each behavior:

1. Add or confirm the relevant test.
2. Run the test and confirm the expected failure when appropriate.
3. Implement the smallest correct solution.
4. Run the focused test.
5. Run the complete test suite after the logical unit is complete.
6. Refactor only while tests remain green.

Do not weaken tests merely to make an implementation pass.

Tests must be deterministic. Random test data must use an explicit seed.

## Numerical correctness

Prefer simple, explainable DSP implementations over unnecessary abstractions.

Do not claim precision unsupported by the algorithm.

F0 V0.2 is explicitly an autocorrelation baseline and is not expected to solve
every pitch-tracking problem.

A metric may return an invalid/not-applicable result instead of fabricating a numeric answer.

Invalid Evidence must produce `not_applicable` rule judgments, not PASS.

## Change discipline

Keep changes narrowly scoped to the current task.

Do not perform unrelated refactors.

Do not add dependencies without a concrete need.

Do not add compatibility layers for hypothetical future requirements.

Do not commit or push unless explicitly requested.

## Verification

Before declaring a task complete:

- run the relevant focused tests;
- run the full pytest suite (Phase 1–2 tests must remain green);
- report exactly which tests were run;
- report any remaining warnings, failures, TODOs, or contract concerns.

Phase 3 deterministic acceptance is T001–T124 with zero required skip/xfail,
the OQ-003-approved `profile_s1_distortion` `1.0.0-demo` profile, and an
honest real-model report (run or not-run). Do not treat a missing-credential
NOT RUN report as a fabricated real-model pass.

Never say that a later phase is complete if its required tests are failing.
