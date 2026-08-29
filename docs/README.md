# Documentation Index

This directory separates active V0.2 specifications from historical design and
project-background material.

## Active source of truth

Read these documents before changing implementation code:

1. [`ARCHITECTURE_V0_2.md`](ARCHITECTURE_V0_2.md) — approved system architecture,
   Scenario S1, phase boundaries, and Hybrid Agent design.
2. [`CONTRACTS_V0_2.md`](CONTRACTS_V0_2.md) — frozen Phase 1–2 public Python
   contracts, frozen Phase 3 §32–§40 rules/knowledge contracts, and frozen
   Phase 4 §41–§49 evaluation contracts.
3. [`TEST_PLAN_V0_2.md`](TEST_PLAN_V0_2.md) — required T001–T092 Phase 1–2
   acceptance, required T093–T124 Phase 3 acceptance, required T125–T183 Phase 4
   acceptance, and separate real-model evaluation.
4. [`DECISIONS.md`](DECISIONS.md) — approved architectural and process decisions.
5. [`superpowers/plans/2026-08-28-phase1-deterministic-foundation.md`](superpowers/plans/2026-08-28-phase1-deterministic-foundation.md)
   — task-level Phase 1 TDD implementation plan covering T001–T063.

## Acceptance reports and active implementation plan

- [`reports/PHASE2_R001_R006_ACCEPTANCE_REPORT.md`](reports/PHASE2_R001_R006_ACCEPTANCE_REPORT.md)
  — retained Phase 2 real-model R001–R006 review, explicitly separate from CI.
- [`reports/PHASE3_REAL_MODEL_BEHAVIOR_REPORT.md`](reports/PHASE3_REAL_MODEL_BEHAVIOR_REPORT.md)
  — Phase 3 product-path observation with injected rules and knowledge;
  the recorded status is **RAN** once (honest DeepSeek run) with 0 rule
  and 0 knowledge actions. This is not a CI gate and is not Phase 3
  product-path acceptance.
- [`superpowers/plans/2026-08-29-phase3-rules-knowledge.md`](superpowers/plans/2026-08-29-phase3-rules-knowledge.md)
  — completed Phase 3 TDD plan covering T093–T124; OQ-003 is resolved and the
  implementation plus final fix wave passed Codex acceptance at `a820b7f`.
  Phase 4 deterministic status is `harness_accepted`; real-model status is
  `benchmark_pending`.
- [`superpowers/specs/2026-08-29-phase4-evaluation-design.md`](superpowers/specs/2026-08-29-phase4-evaluation-design.md)
  — written Phase 4 evaluation design approved on 2026-08-29; §41–§49 and
  T125–T183 are frozen.
- [`superpowers/plans/2026-08-29-phase4-evaluation.md`](superpowers/plans/2026-08-29-phase4-evaluation.md)
  — task-level TDD implementation plan for Phase 4 covering T125–T183.
  Deterministic harness is `harness_accepted` after T001–T183, Ruff, mypy,
  and `git diff --check`. This branch has not run a live 80-slot DeepSeek
  benchmark and has no official credentialed six-file bundle, so real-model
  status remains `benchmark_pending`. Do not claim `benchmark_completed`.

Potential contract defects are recorded in
[`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md). An open entry does not override a
frozen contract.

When active documents disagree, the priority is:

```text
explicit current user instruction
    ↓
AGENTS.md
    ↓
CONTRACTS_V0_2.md
    ↓
ARCHITECTURE_V0_2.md
    ↓
TEST_PLAN_V0_2.md
    ↓
approved implementation plan
```

A disagreement between active documents is a contract concern and must be
reported rather than resolved silently.

## Historical V0.1 documents

The original reviewed specifications are preserved in [`archive/v0.1/`](archive/v0.1/):

- [`PROJECT_SPEC_V0_1.md`](archive/v0.1/PROJECT_SPEC_V0_1.md)
- [`CONTRACTS_V0_1.md`](archive/v0.1/CONTRACTS_V0_1.md)
- [`TEST_PLAN_V0_1.md`](archive/v0.1/TEST_PLAN_V0_1.md)

They explain the project's evolution but are not implementation authority for
V0.2. Do not add compatibility layers solely to preserve unreleased V0.1 names.

## Background context

Non-normative project and career context is stored in [`context/`](context/):

- [`project_origin.md`](context/project_origin.md)
- [`job_search_master_context_v2.md`](context/job_search_master_context_v2.md)

These files explain project motivation and truthfulness constraints. They do not
override active engineering contracts.

## Future documents

Phase 3 passed final Codex acceptance at `a820b7f`. Phase 4 deterministic
status is `harness_accepted` on branch `phase4-evaluation-design` after the
quality gate below (pre-commit HEAD `a5ebd0987752f1234e803e762a2c78196b4738a0`).
Real-model status is `benchmark_pending`: no live 80-slot DeepSeek run and no
official credentialed six-file bundle exist on this branch. Phase 5 remains
gated until both `harness_accepted` and `benchmark_completed` are satisfied.
Do not convert a target miss into a failure or hide it.

Quality gate this session (Python
`C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`):

```text
python -m pytest tests/evaluation tests/test_architecture_boundaries.py -q -rxXs --basetemp .pytest_cache/phase4-task11-basetemp
159 passed in 15.14s

python -m pytest -q -rxXs --basetemp .pytest_cache/phase4-task11-basetemp
434 passed in 17.89s

python -m ruff check .
All checks passed!

python -m mypy src
Success: no issues found in 45 source files

git diff --check
(exit 0, empty output)
```

Zero required skip/xfail were reported. The former deferred-package failure
`test_deferred_packages_are_not_present[evaluation]` is gone. `app/` remains
absent. Phase 2 was implemented directly from its accepted architecture,
contracts, and test plan and has no separate plan document.
