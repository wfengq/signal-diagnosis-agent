# Documentation Index

V0.2 is complete and accepted as a reproducible, evaluated, interactive S1
distortion-diagnosis vertical slice. This index separates the short reviewer
path from implementation authority and historical evidence.

## Five-minute reviewer path

1. [Project README](../README.md) — product, screenshots, metrics, and quickstart.
2. [Engineering case study](PROJECT_CASE_STUDY.md) — difficult failures,
   decisions, corrections, and lessons.
3. [Phase 5 Demo evidence](demo/phase5/v0_2_acceptance/README.md) — two retained
   public `RealLLMPlanner` runs and sanitized artifacts.
4. [Accepted official evaluation](evaluations/phase4_3_1/official/bench_official_s1_v12_planner8_1_gate5/)
   — immutable 80-slot held-out bundle.
5. [V0.3 contextual validation acceptance](evaluations/v0_3/contextual/V9_11_CONTEXTUAL_VALIDATION_ACCEPTANCE_REPORT.md)
   — incremental 20-case/60-slot external-context study with preserved scorer
   correction history.

## Code-review path

1. `src/signal_diag/app/composition.py` and `app/service.py` — application
   assembly and request orchestration.
2. `src/signal_diag/agent/models.py`, `planner.py`, and `runtime.py` — explicit
   model boundary and deterministic Agent controller.
3. `src/signal_diag/tools/service.py` and `src/signal_diag/dsp/` — compact Tool
   results backed by deterministic numerical code.
4. `src/signal_diag/rules/engine.py` and `src/signal_diag/knowledge/index.py` —
   profile-owned thresholds and curated retrieval.
5. `src/signal_diag/evaluation/runner.py` and `scoring.py` — campaign execution,
   trace assembly, and target scoring.
6. `tests/agent/test_s1_acceptance.py` and
   `tests/test_architecture_boundaries.py` — end-to-end and dependency gates.

## Active source of truth

Read these before changing behavior or public interfaces:

1. [ARCHITECTURE_V0_2.md](ARCHITECTURE_V0_2.md) — Scenario S1, Hybrid Agent,
   phase boundaries, and dependency direction.
2. [CONTRACTS_V0_2.md](CONTRACTS_V0_2.md) — frozen Phase 1–5 contracts,
   §§1–§64.
3. [TEST_PLAN_V0_2.md](TEST_PLAN_V0_2.md) — deterministic T001–T285 and
   separately gated real-model evaluation/Demo requirements.
4. [DECISIONS.md](DECISIONS.md) — D001–D031 architectural and process choices.
5. [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) — OQ-001–OQ-011 disposition and
   historical contract concerns.
6. [Phase 5 design](superpowers/specs/2026-08-31-phase5-presentation-engineering-design.md)
   and [implementation plan](superpowers/plans/2026-08-31-phase5-presentation-engineering.md).

When active documents disagree, use this priority:

```text
explicit current user instruction
    -> AGENTS.md
    -> CONTRACTS_V0_2.md
    -> ARCHITECTURE_V0_2.md
    -> TEST_PLAN_V0_2.md
    -> approved implementation plan
```

A disagreement is a contract concern; do not resolve it silently.

## Engineering evolution

Formal designs and plans remain under `superpowers/specs/` and
`superpowers/plans/`. They preserve the complete reasoning trail without making
the root README read like a task ledger.

- Phase 1: deterministic signal foundation, T001–T063.
- Phase 2: minimal Agent runtime and real/scripted planner boundary, T064–T092.
- Phase 3: rules and curated knowledge actions, T093–T124.
- Phase 4: evaluation harness and first honest official `below_target` result,
  T125–T183.
- Phase 4.1: v5/v6 prompt behavior development misses, T184–T200.
- Phase 4.2: dataset 1.2.0, opaque Agent IDs, evaluation-integrity correction,
  and v7 development miss, T201–T208.
- Phase 4.3: final prompt-only v8 calibration and honest development miss,
  T209–T215.
- Phase 4.3.1: clipping-scope and invalid-Evidence scoring correction; v8.1
  development and official both `meets_target`, T216–T223.
- Phase 5: WAV, CLI/API/UI/reporting, packaging, dual Python verification, and
  real product Demo, T224–T285.

The [engineering case study](PROJECT_CASE_STUDY.md) is the concise narrative;
the specs, plans, Git history, and committed bundles are the detailed evidence.

## Evaluation and Demo evidence

- `evaluations/phase4/` — first 80-slot official run, immutable
  `completed/below_target`.
- `evaluations/phase4_1/` — v5 and v6 development-only misses; held-out stayed
  sealed.
- `evaluations/phase4_2/` — v7 development-only miss on corrected dataset 1.2.0.
- `evaluations/phase4_3/` — v8 development-only miss; no official run.
- `evaluations/phase4_3_1/development/` — v8.1 40-slot `meets_target` gate.
- `evaluations/phase4_3_1/official/` — v8.1 80-slot held-out
  `completed/meets_target` bundle.
- `demo/phase5/v0_2_acceptance/` — retained Web UI and WAV CLI real-model runs,
  reports, screenshots, and checksums.
- `reports/` — Phase 2 and Phase 3 real-model observations.
- `evaluations/v0_2_external_wav/` — incremental V0.2 external-WAV study,
  including the retained `below_target` result.
- `evaluations/v0_3/contextual/` — V0.3 contextual development history,
  sealed three-arm validation, independent audit, and corrected
  `meets_target` verdict.

Historical misses are intentionally retained. They are evidence of controlled
calibration and held-out discipline, not active product configurations.

## Historical and background documents

- [archive/v0.1/](archive/v0.1/) contains the original V0.1 project,
  contracts, and test plan. They are historical only.
- [context/](context/) contains non-normative project and career background.
  It cannot override active engineering contracts.

## Current terminal status

```text
presentation_harness_accepted
real_demo_completed
Phase 5 accepted; V0.2 complete resume-grade demonstrable vertical slice
```

The public product path is `RealLLMPlanner`; required tests do not call a live
model. The accepted Demo and official bundles must not be rewritten to improve
recorded outcomes.

The V0.3 contextual study is additive evidence only. It does not change the
V0.2 completion statement or convert either external study into an official
benchmark, industrial validation, or production-readiness claim.
