# Contextual Validation Campaign Runner Implementation Plan

**Status:** Implemented and verified as `validation_runner_harness_complete`.
The authoritative execution evidence is
`docs/evaluations/v0_3/contextual/VALIDATION_RUNNER_CODE_ACCEPTANCE_REPORT.md`;
the original task checklist below is retained as the approved plan record.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a sealed, truth-free, append-only runner for the frozen 20-case contextual validation without running a model.

**Architecture:** A sealed execution-input projection carries only the fields needed to load WAVs and build `StimulusContext`. A campaign state machine consumes that projection in fixed arm-major order through injected Agent/fixed executors, writes append-only artifacts, stops on infrastructure failure, and hands completed results to the existing frozen scorer.

**Tech Stack:** Python 3.11/3.12, Pydantic v2, asyncio, pathlib, existing App service, contextual baseline, sealing and scoring modules, pytest.

---

### Task 1: Freeze execution-only inputs

**Files:**
- Modify: `src/signal_diag/evaluation/contextual/models.py`
- Create: `tests/evaluation/contextual/test_campaign.py`

- [ ] Add RED tests for immutable `ContextualExecutionInput` and `ContextualExecutionPlan` models containing only case/arm identity, diagnostic mode, relative WAV paths, and stimulus fields.
- [ ] Assert their schemas and serialized values exclude role, expected outcome/causal set, confidence, scoreability, source/license, transform, waveform samples, and FFT arrays.
- [ ] Assert nominal mode requires a finite positive nominal Hz and `single_tone`; paired mode requires a reference path; ablation is always `single_signal`.
- [ ] Run the focused tests and observe failure because the models do not exist.
- [ ] Implement the smallest models and rerun to green.

### Task 2: Add v3 seal support for execution inputs

**Files:**
- Modify: `src/signal_diag/evaluation/contextual/sealing.py`
- Modify: `src/signal_diag/evaluation/contextual/__main__.py`
- Modify: `tests/evaluation/contextual/test_sealing.py`

- [ ] Add RED tests proving a replacement seal can bind `execution_inputs.json`, verify its checksum, and reject tampering while legacy v1/v2 seals remain valid.
- [ ] Run the sealing tests and observe the missing argument/artifact failure.
- [ ] Add optional execution-input sealing and CLI metadata routing without changing legacy bundle verification.
- [ ] Rerun focused sealing tests to green.

### Task 3: Implement preflight and append-only campaign state

**Files:**
- Create: `src/signal_diag/evaluation/contextual/campaign.py`
- Modify: `tests/evaluation/contextual/test_campaign.py`

- [ ] Add RED tests that preflight verifies the seal, exact 20/60 arm-major plan, execution-input coverage, WAV hashes, empty source ledger, absent output, frozen provider/model/prompt/policy identities, and credential presence before constructing an executor.
- [ ] Add RED tests that existing output, historical seal status, non-empty ledger, path escape, SHA mismatch, or missing credentials fail without executing a slot.
- [ ] Implement `preflight_contextual_validation` returning a frozen truth-free execution plan and sanitized identity record.
- [ ] Add an append-only writer using create-new semantics and atomic replacement only for the live ledger.
- [ ] Rerun focused tests to green.

### Task 4: Implement exact execution and stop semantics

**Files:**
- Modify: `src/signal_diag/evaluation/contextual/campaign.py`
- Modify: `tests/evaluation/contextual/test_campaign.py`

- [ ] Add RED tests for exact contextual-agent → fixed-pipeline → ablation ordering and manifest case order within each arm.
- [ ] Add RED tests proving one campaign attempt per slot, behavioral failures continue, and the first infrastructure failure stops before the next slot.
- [ ] Add RED tests proving every terminal slot writes attempt/trace/result/summary artifacts once and no subsequent call overwrites them.
- [ ] Implement dependency-injected `run_contextual_validation_campaign` with a single sequential loop and sanitized failure records.
- [ ] Rerun focused tests to green.

### Task 5: Wire real product and deterministic executors

**Files:**
- Modify: `src/signal_diag/evaluation/contextual/campaign.py`
- Modify: `src/signal_diag/evaluation/contextual/__init__.py`
- Modify: `tests/evaluation/contextual/test_campaign.py`

- [ ] Add RED tests that the production Agent executor is backed by `RealLLMPlanner`, rejects `ScriptedPlanner`, sends no raw WAV/truth fields to the planner payload, and maps App snapshots to campaign artifacts.
- [ ] Add RED tests that the fixed executor uses `ContextualBaselineRequest`, local WAV decoding, deterministic Tools, and frozen profiles only.
- [ ] Implement both executors using existing product composition/runtime and truth-free baseline boundaries.
- [ ] Rerun focused tests to green without provider network access.

### Task 6: Finalize frozen scoring and CLI gates

**Files:**
- Modify: `src/signal_diag/evaluation/contextual/campaign.py`
- Modify: `src/signal_diag/evaluation/contextual/__main__.py`
- Modify: `src/signal_diag/evaluation/contextual/__init__.py`
- Modify: `tests/evaluation/contextual/test_campaign.py`
- Modify: `tests/evaluation/contextual/test_cli.py`

- [ ] Add RED tests that only 60 terminal results can be scored and partial infrastructure-stopped runs remain not evaluated.
- [ ] Add RED tests for frozen aggregate/role/ablation target gates and append-only summary/audit/status output.
- [ ] Add RED CLI tests for separate preflight/run commands, mandatory real-model authorization, active v3 seal, and refusal to run against v2.
- [ ] Implement finalization and CLI wiring; tests inject fakes and never call a provider.
- [ ] Rerun focused tests to green.

### Task 7: Register additive contracts and test IDs

**Files:**
- Modify: `docs/CONTRACTS_V0_3_CONTEXTUAL.md`
- Modify: `docs/TEST_PLAN_V0_3_CONTEXTUAL.md`
- Modify: `tests/evaluation/contextual/test_campaign.py`

- [ ] Register T-CX208 onward for execution inputs, preflight, ordering, failure policy, persistence, scoring, CLI authorization, and v3 reseal.
- [ ] Add source-level preservation assertions for product prompt/rules/thresholds and prior test-ID uniqueness.
- [ ] Run focused contract/preservation tests.

### Task 8: Supersede v2 and create zero-execution v3

**Files:**
- Modify: `docs/evaluations/v0_3/contextual/development/study_v0_3_contextual_dev_1/code_identity_amendment.json`
- Modify: `docs/evaluations/v0_3/contextual/validation/study_v0_3_contextual_validation_1/VALIDATION_SEAL_SUPERSESSION.json`
- Modify: `docs/evaluations/v0_3/contextual/validation/study_v0_3_contextual_validation_1/SEAL_STATUS.md`
- Create: `docs/evaluations/v0_3/contextual/validation/study_v0_3_contextual_validation_1/execution_inputs.json`
- Create: `docs/evaluations/v0_3/contextual/validation/study_v0_3_contextual_validation_1/validation_seal_v3/`
- Modify: `tests/evaluation/contextual/test_sealing.py`

- [ ] Generate the truth-free execution-input projection and validate its paths/checksums without opening final-test data.
- [ ] Record v2 as byte-identical, unexecuted historical seal with zero model calls.
- [ ] Append the new evaluation-harness identity and create v3 from unchanged study/product/prompt/profile/scoring/label identities plus execution inputs.
- [ ] Verify v1, v2, and v3; assert v3 has 20 planned cases, 60 planned arms, and zero executions/model calls.

### Task 9: Cumulative verification and stop

- [ ] Run campaign/sealing/CLI focused tests.
- [ ] Run all contextual tests and full pytest.
- [ ] Run Ruff, mypy, architecture/preservation, and `git diff --check 605c8a8`.
- [ ] Scan changed artifacts for credentials, raw audio, provider payloads, validation run directories, and final-test access.
- [ ] Report `validation_runner_harness_complete` only if every gate passes; stop without model execution, commit, or push.
