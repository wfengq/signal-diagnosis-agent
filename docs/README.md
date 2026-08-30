# Documentation Index

This directory separates active V0.2 specifications from historical design and
project-background material.

## Active source of truth

Read these documents before changing implementation code:

1. [`ARCHITECTURE_V0_2.md`](ARCHITECTURE_V0_2.md) — approved system architecture,
   Scenario S1, phase boundaries, and Hybrid Agent design.
2. [`CONTRACTS_V0_2.md`](CONTRACTS_V0_2.md) — frozen Phase 1–2 public Python
   contracts, frozen Phase 3 §32–§40 rules/knowledge contracts, frozen
   Phase 4 §41–§49 evaluation contracts, and additive Phase 4.1 §§50–§51
   behavior gates.
3. [`TEST_PLAN_V0_2.md`](TEST_PLAN_V0_2.md) — required T001–T092 Phase 1–2
   acceptance, required T093–T124 Phase 3 acceptance, required T125–T183 Phase 4
   acceptance, additive T184–T200 Phase 4.1 acceptance, and separate real-model
   evaluation.
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
  `benchmark_completed` with honest `below_target`.
- [`superpowers/specs/2026-08-29-phase4-evaluation-design.md`](superpowers/specs/2026-08-29-phase4-evaluation-design.md)
  — written Phase 4 evaluation design approved on 2026-08-29; §41–§49 and
  T125–T183 are frozen.
- [`superpowers/plans/2026-08-29-phase4-evaluation.md`](superpowers/plans/2026-08-29-phase4-evaluation.md)
  — task-level TDD implementation plan for Phase 4 covering T125–T183.
  Deterministic harness is `harness_accepted` after T001–T183, Ruff, mypy,
  and `git diff --check`. Official live DeepSeek benchmark
  `bench_official_s1_20260829t162243z` produced the six-file bundle under
  [`evaluations/phase4/bench_official_s1_20260829t162243z/`](evaluations/phase4/bench_official_s1_20260829t162243z/):
  80 scoreable held-out Agent slots, `benchmark_status=completed`,
  `target_status=below_target`.
- [`superpowers/specs/2026-08-30-phase4-1-agent-behavior-improvement-design.md`](superpowers/specs/2026-08-30-phase4-1-agent-behavior-improvement-design.md)
  — written Phase 4.1 agent-behavior-improvement design approved on 2026-08-30;
  additive §50 and T184–T195. Deterministic implementation complete at
  `cadc15d`; real-model gates not done; Phase 4.1 not accepted.
- [`superpowers/plans/2026-08-30-phase4-1-agent-behavior-improvement.md`](superpowers/plans/2026-08-30-phase4-1-agent-behavior-improvement.md)
  — task-level TDD implementation plan for the v5 Phase 4.1 attempt covering
  T184–T195. Its 40-slot development gate1 is immutable
  `completed/below_target` at `f9392c2`; official v1.1.0 held-out was not run.
- [`superpowers/specs/2026-08-30-phase4-1-prompt-v6-correction-design.md`](superpowers/specs/2026-08-30-phase4-1-prompt-v6-correction-design.md)
  — approved additive prompt v6 correction design; §51, T196–T200, and D022
  preserve v4/v5 evidence while authorizing a coherent v6 product prompt.
- [`superpowers/plans/2026-08-30-phase4-1-prompt-v6-correction.md`](superpowers/plans/2026-08-30-phase4-1-prompt-v6-correction.md)
  — active Task 2–8 TDD implementation plan. v6 development gate2 must meet
  target before the one-shot official held-out campaign is permitted.

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

Phase 4 accepted at `b68ec5e` (`completed/below_target` official v1.0.0
benchmark remains immutable). Phase 4.1 v5 deterministic implementation is
complete at `cadc15d`; its development gate1 at `f9392c2` is honest
`completed/below_target`. Prompt v6 Task 2–8 implementation is authorized under
§51 and T196–T200. The v1.1.0 held-out split remains sealed until v6
development gate2 reaches `completed/meets_target`. The v6 deterministic gate
passed; the real development gate2 is pending. Phase 4.1 is not accepted;
Phase 5 remains gated.

Phase 3 passed final Codex acceptance at `a820b7f`. Phase 4 deterministic
status is `harness_accepted` on branch `phase4-evaluation-design`. Real-model
status is `benchmark_completed` with honest `below_target` after the official
live 80-slot DeepSeek run `bench_official_s1_20260829t162243z`, recorded at
`b68ec5e`. That first official benchmark is complete and honestly below
target; it is not a harness failure and is not accepted as product-quality
behavior. Do not convert a target miss into a failure or hide it. Do not
start Phase 5 until Phase 4.1 is accepted and Phase 5 is explicitly
authorized.

Quality gate this session (Python
`C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`):

```text
python -m pytest -q -rxXs -p no:cacheprovider --basetemp <temporary-directory> tests/evaluation/test_runner.py::test_official_trace_keeps_empty_delta_planner_decisions tests/evaluation/test_scoring.py::test_t162_unnecessary_tool_scoring
2 passed in 1.50s

python -m pytest -q -rxXs -p no:cacheprovider --basetemp <temporary-directory>
451 passed in 20.64s

python -m ruff check --no-cache src tests scripts
All checks passed!

python -m mypy --no-incremental src
Success: no issues found in 45 source files

git diff --check 9bd01f2..HEAD
(exit 0, empty output)
```

Zero required skip/xfail were reported. The former deferred-package failure
`test_deferred_packages_are_not_present[evaluation]` is gone. `app/` remains
absent. Phase 2 was implemented directly from its accepted architecture,
contracts, and test plan and has no separate plan document.
