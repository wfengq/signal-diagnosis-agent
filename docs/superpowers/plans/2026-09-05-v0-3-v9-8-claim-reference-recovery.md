# V0.3 v9.8 Claim-Reference Recovery Implementation Plan

> **For agentic workers:** Use TDD. Each behavior change: RED → minimal GREEN →
> focused regression. Do not commit or push unless separately authorized.

**Goal:** Reduce alternating citation omissions on nominal harmonic finishes by
accumulating ID-bearing recoverable errors and freezing a v9.8 prompt/policy
that inherits all v9.7 deterministic closure behavior.

**Spec:** `docs/superpowers/specs/2026-09-05-v0-3-v9-8-claim-reference-recovery-design.md`

## Global constraints

- Start from HEAD `da3d4eca3be83a57381936b2121d27d42353fda8`.
- Do not modify DSP, Tools, profiles, thresholds, data, labels, scoring, retry
  budgets, v9.7 prompt bytes, or historical run artifacts.
- Do not access `docs/evaluations/v0_3/validation/` or run a real model.
- Keep untracked investigation_report and validation/ untouched.
- Strongest harness conclusion: `v9_8_harness_complete`.

## Task checklist

### Task 1 — Contracts and registry

- Update `docs/CONTRACTS_V0_3_CONTEXTUAL.md` with
  `v9_8_claim_reference_recovery` and §10.3.
- Update `docs/TEST_PLAN_V0_3_CONTEXTUAL.md` with T-CX186–T-CX190.
- Add T-CX186 preservation assertion (v9.7 SHA + registry uniqueness).

### Task 2 — Finish validator (T-CX187 / T-CX188)

- Extend `CausalPolicyVersion` and contextual policy set.
- Under v9.8 only, collect nominal-harmonic deficits with same-run IDs and
  require `test_thd_percent` Evidence tied to the THD FAIL rule.
- Do not auto-mutate claims.

### Task 3 — Inheritance wiring

- `rule_closure.py`, runtime routing, and manual-rule rejection accept v9.8.
- Legacy policies unchanged.

### Task 4 — Prompt and composition (T-CX189 / T-CX190)

- Build `_S1_PROMPT_V9_8` from frozen v9.7 via `_replace_once`.
- Wire planner + composition to v9.8.
- Assert v9.7 SHA unchanged.

### Task 5 — Gates and harness report

- Focused v9.8 + v9.7 regression suites.
- Full pytest, Ruff, mypy, architecture, preservation, `git diff --check`.
- Write `docs/evaluations/v0_3/contextual/V9_8_CODE_ACCEPTANCE_REPORT.md`.
- Stop for review; no commit/push.
