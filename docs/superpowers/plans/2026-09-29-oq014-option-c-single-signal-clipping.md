# OQ-014 Option C — Single-signal flat-top clipping finish gate

**Status:** draft plan — **do not execute** until the operator replies
`OQ-014: Option C` against
`docs/superpowers/specs/2026-09-29-oq014-clipping-mechanism-semantics-design.md`.

**Date:** 2026-09-29

**Goal:** On `single_signal` only, allow `supported_fault/clipping` when valid
`flat_top_detected=true` Evidence is cited with a substantial clipping-rule
FAIL, without requiring `clipping_mechanism=true`. Keep DSP
`clipping_mechanism` strict. Keep contextual modes on `test_clipping_mechanism`.

## File map

| File | Responsibility |
|------|----------------|
| `src/signal_diag/agent/diagnosis.py` | Extend single_signal clipping supported-fault predicate |
| `src/signal_diag/agent/prompts_v03.py` (or new v9.12 spec) | Planner citation note for flat-top path |
| `tests/agent/test_s1_acceptance.py` / new `tests/agent/test_oq014_*.py` | Failing then green T087-strength / T-CX tests |
| `docs/CONTRACTS_V0_3_CONTEXTUAL.md` | Additive finish-gate clause |
| `docs/OPEN_QUESTIONS.md` / `docs/DECISIONS.md` | Resolve OQ-014; add D036 |
| `docs/TEST_PLAN_V0_3_CONTEXTUAL.md` | Register new T-CX ids |

Do **not** edit `dsp/clipping.py` under Option C. Do **not** rewrite sealed
bundles. Do **not** bump live RealLLM campaign without separate auth.

## Tasks

### Task 1: Failing acceptance test

- [ ] Write a scripted `single_signal` case for sub-full-scale flat-top (reuse
  synthetic clipped fixture / Demo-like peak 0.65).
- [ ] Assert finish outcome `supported_fault` with a clipping claim that cites
  `flat_top_detected` (and a substantial rule FAIL id).
- [ ] Run test; confirm it fails on current HEAD gates.
- [ ] Commit: `test: OQ-014 single_signal flat-top clipping must support fault`

### Task 2: Diagnosis predicate

- [ ] Implement Option C alternate predicate in `diagnosis.py` for policies that
  currently call `_validate_clipping_supported` on `single_signal`.
- [ ] Leave `_has_clipping_mechanism` / contextual validators unchanged.
- [ ] Run Task 1 test green; run Workstream C mechanism gold labels green.
- [ ] Commit: `fix: allow single_signal clipping via flat_top Evidence`

### Task 3: Prompt / contract / decisions

- [ ] Add planner guidance (prefer additive v9.12 identity if v9.11 bytes are
  frozen; otherwise a minimal v9.11 clarification only if already mutable).
- [ ] Append CONTRACTS_V0_3 clause; resolve OQ-014; add D036.
- [ ] Register T-CX ids in TEST_PLAN_V0_3_CONTEXTUAL.md.
- [ ] Commit: `docs: resolve OQ-014 Option C`

### Task 4: Verification

- [ ] `pytest` focused agent/dsp/app tests listed above.
- [ ] `ruff` / `mypy` on touched paths.
- [ ] Optional: ScriptedPlanner verify skill on clipping preset (no RealLLM).
- [ ] Open PR; do not merge without operator review.

## How to read

Execution playbook after approval: poteto-mode **feature** (not overnight).
One PR. No autopilot merge. Operator merges.
