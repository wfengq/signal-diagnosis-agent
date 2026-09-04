# V0.3 v9.6 Contextual Code Acceptance Report

**Decision:** `v9_6_harness_complete`

**Not claimed:** `development_confirmed`, validation `meets_target`, product
performance improvement, or authorization to run a real-model remediation
campaign.

**Recorded:** 2026-09-04 (local)

**Branch:** `codex/v0.2-real-world-validation`

**Commit note:** Gates below were executed against the uncommitted working tree
on top of starting HEAD `acca1ef4e9444cfcae40b22d32f80fd8cc5b056c`. No commit
and no push were performed in this acceptance step. No real model was invoked.
`docs/evaluations/v0_3/validation/` was not accessed for product work.

## Identities

| Identity | Value |
|---|---|
| Starting HEAD (authorized baseline) | `acca1ef4e9444cfcae40b22d32f80fd8cc5b056c` |
| Active prompt version | `v0.3-s1-planner-9.6` |
| Active causal policy | `v9_6_contextual` |
| v9.6 system prompt UTF-8 SHA-256 | `b9ed17debf9bfd2f086ee0eaa178d83370630a0530ebd02336769e416be1b5eb` |
| Frozen v9.5 system prompt UTF-8 SHA-256 | `a4f4d260adb45a2af088961c77586b08d8279cd1bc4f3780474c3b0a6bd7cb02` |
| Working-tree `prompts_v03.py` SHA-256 | `7a00f54d2c9f2faa5e4e9f3d449ac12d049c17c5d5f398d4bbef419c648230e1` |
| Profile `s1_distortion` SHA-256 | `1e02d0dabe74ae1327fa3418d4ce546c53e8a8d06b175b5c508edb8b512f5ed1` |
| Profile `s1_contextual_comparison` SHA-256 | `c79865caf913b2a1a5f6f50fccd8c37d6f2828e72feb1f80d9c9c7b4b7d9eb58` |
| Growth threshold (unchanged) | `5.0` % |

## Preservation (T-CX146 / T-CX147)

v9.5 prompt bytes remain frozen at the SHA above. Selected Task 13 control
artifacts match the pinned literals:

| Relative path under `study_v0_3_contextual_dev_1/` | SHA-256 |
|---|---|
| `agent_v9_5_dev_run/AUDIT_CORRECTION.md` | `5423259dcd0ec44a94cbc44de8d98f49932fcf925fa812c30122f12166ff5b47` |
| `agent_v9_5_dev_run/STATUS.md` | `516d50d67e68c8689ca55f46969c6dec206a0a7325e234186e5860190037dabd` |
| `agent_v9_5_dev_diagnostic_continuation_1/STATUS.md` | `d08e3e282a339e7c3a7f9b9a2a6661d8173cbd9c0acc29723668cdee5ac6fbfb` |
| `agent_v9_5_dev_diagnostic_continuation_1/preflight.json` | `3b5ecc5b37e3c51c9d14a56e5bc12d7d21a9751f627a9d0bb31f1f95fe53f5ca` |
| `agent_v9_5_dev_diagnostic_continuation_1/disposition.json` | `7458f46e6cba03d3d8928a4643f06a58f2cd33a0640a06dbe2a0ee58e98176c1` |
| `agent_v9_5_dev_diagnostic_continuation_1/run_summary.json` | `9a2992a53f6a11a2a2e85a79036bcbc35923e184aa53e4330bced170f3c70a2f` |

Working-tree diff against HEAD contains **no** files under any Task 13 run
directory. Historical note: committed range `95bb191..acca1ef` only contains the
authorized trailing-whitespace cleanup of two Task 13 markdown files.

## Step 1 — Focused v9.6 / contextual suites

T-CX146–T-CX165 focused recheck:

```text
pytest tests/evaluation/external/test_v03_contextual_preservation.py \
  tests/agent/test_v03_contextual_routing_v9_6.py \
  tests/agent/test_v03_prompt_v9_6.py \
  tests/agent/test_v03_v9_6_regressions.py -q
```

**Result:** **24 passed**, 0 skip/xfail

**Recheck (T-CX148 table-row uniqueness):** After tightening
`test_t_cx148_v9_6_ids_are_registered_once` to extract only Markdown table ID
cells via `^\| (T-CX\d+) \|` and assert each of T-CX146–T-CX165 appears
**exactly once**, the same focused command was re-run with **24 passed**. No
product, prompt, contract, or TEST_PLAN content changes. Cumulative counts below
were also re-verified unchanged.

Broader contextual focused suite (signal/DSP/tools/rules/agent/app/evaluation)
was previously green during implementation; cumulative full suite below covers
the same tree.

## Step 2 — Cumulative quality gates

| Gate | Command | Result |
|---|---|---|
| Full pytest | `python -m pytest -q -rxXs -p no:cacheprovider` | **1342 passed**, 1 warning, 0 required skip/xfail |
| Ruff | `python -m ruff check --no-cache .` | All checks passed |
| Mypy | `python -m mypy --no-incremental src` | Success: 95 source files |
| Architecture + preservation | `pytest tests/test_architecture_boundaries.py tests/evaluation/external/test_v03_contextual_preservation.py -q -p no:cacheprovider` | **65 passed** |
| Diff hygiene | `git diff --check 605c8a8` | Pass |

**Warning (non-blocking):** Pydantic serializer warning in
`tests/evaluation/external/test_manifest.py::test_canonical_json_bytes_rejects_nan`.

## Step 3 — Packaging and clean-environment matrix

### Wheel smoke (inside matrix / prior local smoke)

Matrix-final wheel artifacts (3.12 clean env wheel step):

- sdist `signal_diagnosis_agent-0.2.0.tar.gz` sha256=`c2964ff3fce55100f1b002736d2205b2d3654cf841367e04d43881ce93b305f3`
- wheel `signal_diagnosis_agent-0.2.0-py3-none-any.whl` sha256=`e46f89f03b49af1694385654a7f16581a036e4bd47609d8b2a56d575f4932df2`

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
| CPython 3.11 (uv) | **1342 passed**, 1 warning | pass | pass | pass |
| CPython 3.12 (uv) | **1342 passed**, 1 warning | pass | pass | pass |

**Result:** `local 3.11/3.12 clean-environment verification passed` (`MATRIX_EXIT=0`)

## What changed (Tasks 1–4 summary)

1. Registered `v9_6_contextual` contract and T-CX146–T-CX165.
2. Added fail-closed mode-aware Tool routing under `v9_6_contextual` only.
3. Froze/wired `v0.3-s1-planner-9.6` and product composition to `v9_6_contextual`.
4. Added deterministic regressions for no-fault citation, combined routing/closure,
   natural-even no-growth, and clipping independence.

## Explicit non-claims

- No real-model development confirmation was run.
- Original Task 13 remains `below_target` with `protocol_deviation=true` and
  `development_confirmation_valid=false`.
- Diagnostic continuation remains `diagnostic_only=true`.
- This report does **not** authorize validation access or a remediation campaign.

## Authorization still required before claiming development success

A new explicit authorization is required for a v9.6 remediation development
confirmation that:

1. uses a new append-only run directory;
2. freezes the v9.6 prompt/policy/code identities in preflight;
3. runs one RealLLMPlanner attempt per remaining or rematerialized slot under the
   authorized protocol;
4. does not rewrite Task 13 evidence or claim to repair the invalid one-shot run.
