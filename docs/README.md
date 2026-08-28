# Documentation Index

This directory separates active V0.2 specifications from historical design and
project-background material.

## Active source of truth

Read these documents before changing implementation code:

1. [`ARCHITECTURE_V0_2.md`](ARCHITECTURE_V0_2.md) — approved system architecture,
   Scenario S1, phase boundaries, and Hybrid Agent design.
2. [`CONTRACTS_V0_2.md`](CONTRACTS_V0_2.md) — frozen Phase 1–2 public Python
   contracts.
3. [`TEST_PLAN_V0_2.md`](TEST_PLAN_V0_2.md) — required T001–T092 deterministic
   acceptance and separate R001–R006 real-model evaluation.
4. [`DECISIONS.md`](DECISIONS.md) — approved architectural and process decisions.
5. [`superpowers/plans/2026-08-28-phase1-deterministic-foundation.md`](superpowers/plans/2026-08-28-phase1-deterministic-foundation.md)
   — task-level Phase 1 TDD implementation plan covering T001–T063.

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

Phase 2–5 implementation plans are created only when the previous phase satisfies
its approved completion gate. Future contracts are frozen immediately before
their implementation phase, as defined by `ARCHITECTURE_V0_2.md`.
