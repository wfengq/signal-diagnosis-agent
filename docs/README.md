# Documentation Index

This directory separates active V0.2 specifications from historical design and
project-background material.

## Active source of truth

Read these documents before changing implementation code:

1. [`ARCHITECTURE_V0_2.md`](ARCHITECTURE_V0_2.md) — approved system architecture,
   Scenario S1, phase boundaries, and Hybrid Agent design.
2. [`CONTRACTS_V0_2.md`](CONTRACTS_V0_2.md) — frozen Phase 1–2 public Python
   contracts, frozen Phase 3 §32–§40 rules/knowledge contracts, frozen
   Phase 4 §41–§49 evaluation contracts, additive Phase 4.1 §§50–§51
   behavior gates, the frozen Phase 4.2 §52 evaluation-integrity gate, and the
   frozen Phase 4.3 §53 planner-v8 behavior gate plus Phase 4.3.1 §54 v8.1
   compliance correction.
3. [`TEST_PLAN_V0_2.md`](TEST_PLAN_V0_2.md) — required T001–T092 Phase 1–2
   acceptance, required T093–T124 Phase 3 acceptance, required T125–T183 Phase 4
   acceptance, additive T184–T200 Phase 4.1 acceptance, Phase 4.2 T201–T208,
   Phase 4.3 T209–T215, Phase 4.3.1 T216–T223, and separate real-model
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
  — completed Task 2–8 TDD plan. v6 development gate2 is honest
  `completed/below_target` at `808f653`; official v1.1.0 held-out was not run.
- [`superpowers/specs/2026-08-30-phase4-2-prompt-v7-correction-design.md`](superpowers/specs/2026-08-30-phase4-2-prompt-v7-correction-design.md)
  — approved and frozen Phase 4.2 evaluation-integrity and planner v7
  calibration design under §52, T201–T208, D023, and resolved OQ-007. It adds
  a fresh v1.2.0 dataset and opaque Agent signal IDs rather than retrying v7 on
  the integrity-defective v1.1.0 evaluation inputs. Deterministic Tasks 2–7
  are complete; T208 is green. v7 development gate3 at `71293a3` is honest
  `completed/below_target`; official v1.2.0 held-out was not run.
- [`superpowers/plans/2026-08-30-phase4-2-prompt-v7-correction.md`](superpowers/plans/2026-08-30-phase4-2-prompt-v7-correction.md)
  — Task 1–10 TDD plan for dataset v1.2.0, outbound identity integrity,
  prompt v7, campaigns, and gated live evaluation. Tasks 2–7 deterministic
  implementation is complete. Task 8 v7 development gate3 at `71293a3`
  is honest `completed/below_target`. Task 9 official/held-out was not run.
  Task 10 records that honest stop. v1.1.0 held-out remains unexecuted;
  v1.2.0 held-out was not run under v7 (first executed under Phase 4.3.1 v8.1
  gate5). Phase 4.2 is not accepted.
- [`superpowers/specs/2026-08-30-phase4-3-planner-v8-behavior-calibration-design.md`](superpowers/specs/2026-08-30-phase4-3-planner-v8-behavior-calibration-design.md)
  — approved and frozen Phase 4.3 design under §53, T209–T215, D024, and
  resolved OQ-008. It permits one final prompt-only v8 candidate while keeping
  dataset 1.2.0, Runtime, PlannerContext, scoring, targets, provider, and model
  unchanged.
- [`superpowers/plans/2026-08-30-phase4-3-planner-v8-behavior-calibration.md`](superpowers/plans/2026-08-30-phase4-3-planner-v8-behavior-calibration.md)
  — approved task-level implementation plan. Deterministic Tasks 1–4 are
  implemented and T215 is green at `1c70568` (not a live-model pass). Task 5
  v8 development gate4 at `48dfb89` is honest `completed/below_target`.
  Task 6 official/held-out was not run. Task 7 records that honest stop.
  Phase 4.3 is not accepted. Phase 5 remains unauthorized.

- [`superpowers/specs/2026-08-30-phase4-3-1-v8-1-compliance-correction-design.md`](superpowers/specs/2026-08-30-phase4-3-1-v8-1-compliance-correction-design.md)
  — approved and frozen Phase 4.3.1 compliance correction under §54, T216–T223,
  D025, and OQ-009. It adds prompt `v0.2-s1-planner-8.1` and scoring policy
  `signal_diag.scoring=2.0.0` while preserving every v4–v8 asset.
- [`superpowers/plans/2026-08-30-phase4-3-1-v8-1-compliance-correction.md`](superpowers/plans/2026-08-30-phase4-3-1-v8-1-compliance-correction.md)
  — Tasks 2–7 committed at `083b6d9`. T001–T223, Ruff, mypy, architecture,
  and diff-check are green. v8.1 development gate5 is honest
  `completed/meets_target` on 40 unique Agent slots (all bands pass;
  development split; not official held-out evidence). Task 9 official held-out
  is honest `completed/meets_target` on 80 Agent held-out slots (all bands
  pass; 2/80 Agent slots carry non-blocking behavioral failure codes on
  `case_v12_held_noise_02` — slot 1: `redundant_rule;inappropriate_replan`,
  outcome correct; slot 5: `required_knowledge_omitted;outcome_mismatch`, sole
  wrong outcome at 1/80; aggregate remains `completed/meets_target`).
  Phase 4.3.1 is accepted at Task 10 (terminal evidence at `99e0bdc`).
  Phase 5 remains gated.

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
`completed/below_target`. Prompt v6 Task 2–8 completed under §51 and
T196–T200. The v1.1.0 held-out split remains sealed. The v6 deterministic gate
passed. Real-model development gate2 `bench_phase4_1_dev_v6_gate2` is honest
`completed/below_target`, so official v6 held-out stays sealed. Report
`harness_status=pending` is CLI semantics, not a harness failure. Independent
review rejected a prompt-only v7 retry because v1.1.0 leaks semantic signal IDs
and contains hidden first-Tool/causal-identifiability requirements. The revised
Phase 4.2 design is approved and frozen under §52, T201–T208, D023, and
resolved OQ-007. Deterministic Tasks 2–7 are complete and T208 is green.
Real-model Task 8 development gate3 at `71293a3` is honest
`completed/below_target` (40 unique Agent slots; missed first_tool 0.75,
replan 0.719, unnecessary_tool 0.405, required_knowledge 0.2; CLI
`harness_status=pending`). Task 9 official v1.2.0 held-out was not run;
`docs/evaluations/phase4_2/official/` does not exist. Task 10 records that
honest stop. Phase 4.1 is not accepted; Phase 4.2 is not accepted;
Phase 5 remains gated.

The Phase 4.3 written design is approved and frozen under §53, T209–T215,
D024, and OQ-008. Deterministic T001–T215 are green at `1c70568`; that is not
a live-model pass. Real-model development gate4
`bench_phase4_3_dev_v8_v12_gate4` at `48dfb89` is honest
`completed/below_target` (40 unique Agent slots; missed evidence_grounding
0.849, timely_stopping 0.75, unsupported_claim 0.211; CLI
`harness_status=pending`). Official v1.2.0 held-out was not run;
`docs/evaluations/phase4_3/official/` does not exist. No v9. Task 7 records
that honest stop. Phase 4.3 is not accepted. The next written choice is
model capability versus PlannerContext (option 2), not more prompts.
Phase 5 remains unauthorized.

The Phase 4.3.1 compliance correction is approved and frozen under §54,
T216–T223, D025, and OQ-009.
[`superpowers/specs/2026-08-30-phase4-3-1-v8-1-compliance-correction-design.md`](superpowers/specs/2026-08-30-phase4-3-1-v8-1-compliance-correction-design.md)
adds prompt `v0.2-s1-planner-8.1` and scoring policy `signal_diag.scoring=2.0.0`
while preserving every v4–v8 asset.
[`superpowers/plans/2026-08-30-phase4-3-1-v8-1-compliance-correction.md`](superpowers/plans/2026-08-30-phase4-3-1-v8-1-compliance-correction.md)
Tasks 2–7 are committed at `083b6d9`. T001–T223, Ruff, mypy, architecture,
and diff-check are green. Real-model development gate5
`bench_phase4_3_1_dev_v8_1_v12_gate5` is honest `completed/meets_target`
(40 unique Agent slots; all TargetBands pass; CLI `harness_status=pending`).
Task 9 official held-out `bench_official_s1_v12_planner8_1_gate5` is honest
`completed/meets_target` (80 Agent held-out slots; all TargetBands pass;
2/80 Agent slots carry non-blocking behavioral failure codes on
`case_v12_held_noise_02` — slot 1: `redundant_rule;inappropriate_replan`,
outcome correct; slot 5: `required_knowledge_omitted;outcome_mismatch`, sole
wrong outcome at 1/80; aggregate remains `completed/meets_target`). Bundle:
`docs/evaluations/phase4_3_1/official/bench_official_s1_v12_planner8_1_gate5/`.
Phase 4.3.1 is accepted at Task 10 (terminal evidence at `99e0bdc`).
Phase 5 remains gated.

Phase 3 passed final Codex acceptance at `a820b7f`. Phase 4 deterministic
status is `harness_accepted` on branch `phase4-evaluation-design`. Real-model
status is `benchmark_completed` with honest `below_target` after the official
live 80-slot DeepSeek run `bench_official_s1_20260829t162243z`, recorded at
`b68ec5e`. That first official benchmark is complete and honestly below
target; it is not a harness failure and is not accepted as product-quality
behavior. Do not convert a target miss into a failure or hide it. Phase 5
remains unauthorized until separately designed, frozen, and explicitly
authorized. Phase 4.3.1 acceptance is the final product-behavior gate.

Quality gate this session (Python
`C:\Users\wei\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`):

```text
python -m pytest -q -rxXs -p no:cacheprovider --basetemp .pytest_cache/phase4-3-1-final
825 passed in 37.61s

python -m ruff check --no-cache src tests scripts
All checks passed!

python -m mypy --no-incremental src
Success: no issues found in 46 source files

git diff --check 1b94194..HEAD
(exit 0, empty output)
```

Zero required skip/xfail were reported. `app/` remains absent. Phase 4.3.1 is
accepted at Task 10 (development and official both `completed/meets_target`;
terminal evidence at `99e0bdc`). Phase 5 remains gated.
