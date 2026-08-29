# Documentation Index

This directory separates active V0.2 specifications from historical design and
project-background material.

## Active source of truth

Read these documents before changing implementation code:

1. [`ARCHITECTURE_V0_2.md`](ARCHITECTURE_V0_2.md) — approved system architecture,
   Scenario S1, phase boundaries, and Hybrid Agent design.
2. [`CONTRACTS_V0_2.md`](CONTRACTS_V0_2.md) — frozen Phase 1–2 public Python
   contracts and frozen Phase 3 §32–§40 rules/knowledge contracts.
3. [`TEST_PLAN_V0_2.md`](TEST_PLAN_V0_2.md) — required T001–T092 Phase 1–2
   acceptance, required T093–T124 Phase 3 acceptance, and separate R001–R006
   real-model evaluation.
4. [`DECISIONS.md`](DECISIONS.md) — approved architectural and process decisions.
5. [`superpowers/plans/2026-08-28-phase1-deterministic-foundation.md`](superpowers/plans/2026-08-28-phase1-deterministic-foundation.md)
   — task-level Phase 1 TDD implementation plan covering T001–T063.

## Acceptance reports and active implementation plan

- [`reports/PHASE2_R001_R006_ACCEPTANCE_REPORT.md`](reports/PHASE2_R001_R006_ACCEPTANCE_REPORT.md)
  — retained Phase 2 real-model R001–R006 review, explicitly separate from CI.
- [`reports/PHASE3_REAL_MODEL_BEHAVIOR_REPORT.md`](reports/PHASE3_REAL_MODEL_BEHAVIOR_REPORT.md)
  — Phase 3 product-path observation with injected rules and knowledge;
  the recorded status is **NOT RUN** because credentials were unavailable.
  This is not a CI gate and is not a fabricated pass.
- [`superpowers/plans/2026-08-29-phase3-rules-knowledge.md`](superpowers/plans/2026-08-29-phase3-rules-knowledge.md)
  — completed Phase 3 TDD plan covering T093–T124; OQ-003 is resolved and
  Phase 3 is deterministically accepted. Independent Task 9 review is still
  required before merge.

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

Phase 3 is accepted. Phase 4 evaluation contracts remain unfrozen. Later
implementation plans are created only when the preceding contract and
completion gates permit them. Phase 2 was implemented directly from its accepted
architecture, contracts, and test plan and has no separate plan document. Future
contracts are frozen immediately before their implementation phase, as defined
by `ARCHITECTURE_V0_2.md`. Do not implement Phase 4 or Phase 5 until that phase
is explicitly authorized.
