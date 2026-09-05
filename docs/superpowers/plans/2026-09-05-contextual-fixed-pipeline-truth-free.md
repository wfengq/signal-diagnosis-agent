# Contextual Fixed-Pipeline Truth-Free Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Replace the contextual label-oracle baseline with a deterministic DSP/rule baseline and reseal the still-unexecuted validation study.

**Architecture:** A truth-free request carries only signal identities and stimulus context. A repository-backed baseline runs existing Tools and frozen profiles, maps same-run Evidence/rules to diagnoses, and produces auditable fixed-pipeline artifacts without reading manifest truth.

**Tech Stack:** Python 3.11/3.12, Pydantic, pytest, existing signal_diag Tool/Rule/Evidence services.

---

### Task 1: Freeze the truth-free interface with RED tests

**Files:**
- Modify: `tests/evaluation/contextual/test_runner.py`
- Modify: `src/signal_diag/evaluation/contextual/models.py`

- [x] Add tests for a frozen `ContextualBaselineRequest(case_id, signal_id, stimulus_context)` whose schema contains no truth/provenance fields.
- [x] Add a test proving `run_fixed_pipeline_case(ContextualCase)` is rejected instead of reading labels.
- [x] Run the focused tests and confirm failure because the request and executable baseline do not yet exist.

### Task 2: Implement the deterministic contextual baseline

**Files:**
- Create: `src/signal_diag/evaluation/contextual/baseline.py`
- Modify: `src/signal_diag/evaluation/contextual/runner.py`
- Modify: `src/signal_diag/evaluation/contextual/__init__.py`
- Modify: `tests/evaluation/contextual/test_runner.py`

- [x] Add real WAV/repository tests for clean, clipping, paired harmonic, combined, natural-even, nominal harmonic, and invalid/inconclusive paths.
- [x] Confirm the new behavior tests fail before implementation.
- [x] Run `detect_clipping` plus mode-appropriate harmonic/contextual Tool calls.
- [x] Evaluate only frozen `profile_s1_distortion` and `profile_s1_contextual_comparison` rules.
- [x] Map claims using same-run causal requirements and preserve Evidence/rule references.
- [x] Run focused tests until green.

### Task 3: Add explicit anti-leakage regression gates

**Files:**
- Modify: `tests/evaluation/contextual/test_runner.py`
- Modify: `tests/test_architecture_boundaries.py`

- [x] Add a metamorphic test showing external expected-label changes cannot affect a request/result.
- [x] Add a source guard forbidding `expected_outcome`, `expected_causal_set`, `role`, `confidence_tier`, and `transform_identity` in the baseline module.
- [x] Confirm each test fails for the old oracle and passes for the new baseline.

### Task 4: Supersede and reseal without rewriting history

**Files:**
- Create: `docs/evaluations/v0_3/contextual/validation/study_v0_3_contextual_validation_1/VALIDATION_SEAL_SUPERSESSION.json`
- Create: `docs/evaluations/v0_3/contextual/validation/study_v0_3_contextual_validation_1/validation_seal_v2/`
- Modify: `docs/evaluations/v0_3/contextual/validation/study_v0_3_contextual_validation_1/SEAL_STATUS.md`
- Modify: `tests/evaluation/contextual/test_sealing.py`

- [x] Record the original seal checksum, zero executed arms, leakage reason, and replacement seal identity without editing `validation_seal/`.
- [x] Create `validation_seal_v2/` from unchanged study inputs and the repaired implementation SHA with zero execution counters.
- [x] Verify both the historical seal and replacement seal.
- [x] Assert manifest/WAV/prompt/profile/scoring identities are unchanged and only implementation identity differs.

### Task 5: Run cumulative verification and stop

- [x] Run focused contextual baseline and sealing tests.
- [x] Run all contextual tests.
- [x] Run full pytest, Ruff, mypy, architecture/preservation, and `git diff --check 605c8a8`.
- [x] Scan changed artifacts for credentials and confirm no model run directory or final-test artifact exists.
- [x] Report results and stop without committing, pushing, or running a model.
