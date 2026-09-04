# V0.3 v9.7 Deterministic Rule Closure Code Acceptance Report

**Decision:** `v9_7_harness_complete`

**Not claimed:** `development_confirmed`, validation `meets_target`, product
performance improvement, or authorization to run a real-model confirmation.

**Recorded:** 2026-09-05 (local)

**Branch:** `codex/v0.2-real-world-validation`

**Commit note:** Gates below were executed against the Task 1–8 working tree on
top of Task 7 HEAD `e710c08bf77aecb75f7d0b98fbfb87446b64c0e6` (baseline start
`2f449646b90fc1d660147e1f17cc5df0a2cf4bf1`). No push was performed. No real
model was invoked. `docs/evaluations/v0_3/validation/` was not accessed for
product work.

## Identities

| Identity | Value |
|---|---|
| Starting HEAD (authorized baseline) | `2f449646b90fc1d660147e1f17cc5df0a2cf4bf1` |
| Task 7 HEAD (pre-acceptance commit) | `e710c08bf77aecb75f7d0b98fbfb87446b64c0e6` |
| Active prompt version | `v0.3-s1-planner-9.7` |
| Active causal policy | `v9_7_deterministic_rule_closure` |
| v9.7 system prompt UTF-8 SHA-256 | `fc50d82fc7b5701388f5d35c7f50a157ed1c88f050e6057cd8f11caf280b982a` |
| Frozen v9.6 system prompt UTF-8 SHA-256 | `b9ed17debf9bfd2f086ee0eaa178d83370630a0530ebd02336769e416be1b5eb` |
| Profile `s1_distortion` SHA-256 | `1e02d0dabe74ae1327fa3418d4ce546c53e8a8d06b175b5c508edb8b512f5ed1` |
| Profile `s1_contextual_comparison` SHA-256 | `c79865caf913b2a1a5f6f50fccd8c37d6f2828e72feb1f80d9c9c7b4b7d9eb58` |
| Growth threshold (unchanged) | `5.0` % |
| Active freeze code identity (via amendment) | `51b65779a0ef7797b512e527f2757edfd0fdb99f7dc3302786309d7d40fca470` |

## Preservation (T-CX001–T-CX003 / T-CX146–T-CX148 / T-CX166)

Preservation suite passed with frozen prompt/profile/tag identities unchanged.
v9.6 confirmation control artifacts remain at the pinned literals from T-CX166.
Working-tree and committed diffs against `2f44964…` contain **no** mutations
under historical official/Demo, v8.1, v9.4, v9.5 Task 13, or v9.6 confirmation
case traces. Shadow replay wrote only the append-only directory
`v9_7_rule_closure_shadow_replay_1/`.

## Shadow replay (T-CX184)

Offline command:

```text
python -m signal_diag.evaluation.contextual shadow-replay-rule-closure \
  --run-dir …/agent_v9_6_dev_confirmation_1 \
  --destination …/v9_7_rule_closure_shadow_replay_1
```

| Field | Value |
|---|---|
| Verdict | `shadow_replay_complete` |
| `source_case_count` | 20 |
| `label_independent_mapping` | true |
| Contextual positive-FAIL case IDs | `a4a0853be9983f8c`, `2be730b9113701de`, `6fb80bbda391c26c`, `aa9b4a91b0253c33`, `35967af7b71c5b75` |
| Contextual complete-PASS (subset asserted) | includes `825a759a0ea47bb7`, `393940e92c58cf0b`, `04f4068ec91d2621`, `ce8b413cf7382c3d` |

No model call, no audio access, no expected-label input, no v9.6 mutation.

## Step 1 — Focused v9.7 gate

```text
pytest tests/agent/test_v03_rule_closure_v9_7.py \
  tests/agent/test_v03_runtime_rule_closure_v9_7.py \
  tests/agent/test_v03_prompt_v9_7.py \
  tests/evaluation/contextual/test_shadow_replay.py \
  tests/evaluation/test_recording.py \
  tests/evaluation/external/test_v03_contextual_preservation.py -q -rxXs -p no:cacheprovider
```

**Result:** **83 passed**, 0 skip/xfail (T-CX166–T-CX185 registry + focused behavior)

## Step 2 — Cumulative quality gates (T-CX185)

| Gate | Command | Result |
|---|---|---|
| Contextual-related suite | `pytest tests/signal tests/dsp tests/tools tests/rules tests/agent tests/app tests/evaluation/contextual -q -rxXs -p no:cacheprovider` | **702 passed** |
| Full pytest | `python -m pytest -q -rxXs -p no:cacheprovider` | **1377 passed**, 1 warning, 0 required skip/xfail |
| Ruff | `python -m ruff check --no-cache .` | All checks passed |
| Mypy | `python -m mypy --no-incremental src` | Success: 97 source files |
| Architecture + preservation | `pytest tests/test_architecture_boundaries.py tests/evaluation/external/test_v03_contextual_preservation.py -q -p no:cacheprovider` | **66 passed** |
| Diff hygiene | `git diff --check 605c8a8` | Pass (`DIFF_CHECK=0`) |

**Warning (non-blocking):** Pydantic serializer warning in
`tests/evaluation/external/test_manifest.py::test_canonical_json_bytes_rejects_nan`.

## Step 3 — Packaging and clean-environment matrix

### Wheel smoke

```text
PIP_CONFIG_FILE=NUL
PIP_INDEX_URL=https://pypi.org/simple
python scripts/verify_phase5_wheel.py
```

- sdist `signal_diagnosis_agent-0.2.0.tar.gz` sha256=`7412a29342437ac971a2f3794f0b7d34d2502d4a9397f3d4259c5f86003c1e48`
- wheel `signal_diagnosis_agent-0.2.0-py3-none-any.whl` sha256=`b189ece862cf15a2dd114face62148ce3d35d2c690bc60fc4957442fe50afc01`

### Dual-version matrix

```text
PIP_CONFIG_FILE=NUL
PIP_INDEX_URL=https://pypi.org/simple
python scripts/verify_phase5_local_matrix.py \
  --python-3.11 C:\Users\wei\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\python.exe \
  --python-3.12 C:\Users\wei\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\python.exe
```

| Interpreter | pytest | ruff | mypy | wheel |
|---|---|---|---|---|
| CPython 3.11 (uv) | **1377 passed**, 1 warning | pass | pass | pass |
| CPython 3.12 (uv) | **1377 passed**, 1 warning | pass | pass | pass |

Matrix-final wheel artifacts (3.12 clean env wheel step):

- sdist sha256=`7ba0f33fd3cb64d3b2c7834194345f2bdbdcbdf189462469a6528c779cea13db`
- wheel sha256=`e9f17834e9b92ce3c0ee0f36a14dd1f89062d727bc1886ad6578e8d692d51945`

**Result:** `local 3.11/3.12 clean-environment verification passed` (`MATRIX_EXIT=0`)

## What changed (Tasks 1–8 summary)

1. Registered `v9_7_deterministic_rule_closure` and T-CX166–T-CX185.
2. Added pure Tool→profile closure mapping (`rule_closure.py`).
3. Runtime automatic RuleEngine batch after relevant Tool observations.
4. Rejected manual `evaluate_rules` under v9.7; legacy policies unchanged.
5. Chronological Observation→automatic-rule trace provenance.
6. Froze/wired `v0.3-s1-planner-9.7` and product composition to v9.7.
7. Offline shadow replay of preserved v9.6 Observation Evidence.
8. Cumulative gates + this acceptance report; provenance-only code-identity
   amendment; architecture allowlist for `rule_closure.py`; planner identity
   assertions aligned to 9.7.

## Explicit non-claims

- No real-model development confirmation was run under v9.7.
- Shadow replay is **not** performance proof and does **not** replace scoring.
- v9.6 confirmation remains the preserved failure evidence (`below_target`).
- This report does **not** authorize validation access or a remediation campaign.

## Authorization still required before claiming development success

A new explicit authorization is required for a v9.7 development confirmation that:

1. uses a new append-only run directory;
2. freezes the v9.7 prompt/policy/code identities in preflight;
3. runs one RealLLMPlanner attempt per authorized slot;
4. does not rewrite v9.6 confirmation evidence or claim performance uplift from
   harness-only work.
