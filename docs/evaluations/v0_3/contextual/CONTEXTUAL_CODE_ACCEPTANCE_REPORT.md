# V0.3 Contextual Code Acceptance Report (Task 12)

**Decision:** `harness_complete`

**Not claimed:** experimental success, development confirmation, validation
`meets_target`, or Task 13 real-model authorization.

**Recorded:** 2026-09-04 (local)

**Branch:** `codex/v0.2-real-world-validation`

**Acceptance tree note:** gates below were executed with working-tree fixes that
are included in the Task 12 commits: growth FAIL fixture aligned to frozen 5.0%
profile; EV-T044/T045 set a dummy `DEEPSEEK_API_KEY` so the secret-free 3.11/3.12
matrix does not depend on ambient credentials. No WAV rematerialization, no
threshold reselection, no real-model run.

## Identities

| Identity | Value |
|---|---|
| Pre-report HEAD (Task 11 tip) | `745674cddd67a8914daf32570ddf841aa824f979` |
| Gate tree commit | `41c9489cf92132dc0407f40f7ae08ae396706f78` |
| Prompt version | `v0.3-s1-planner-9.5` |
| Prompt system UTF-8 SHA-256 | `a4f4d260adb45a2af088961c77586b08d8279cd1bc4f3780474c3b0a6bd7cb02` |
| `prompts_v03.py` file SHA-256 | `d97524eeb91d9f8c58569ab742da5e4b5274632771779ffefa357115d1481a90` |
| Profile `s1_distortion` SHA-256 | `1e02d0dabe74ae1327fa3418d4ce546c53e8a8d06b175b5c508edb8b512f5ed1` |
| Profile `s1_contextual_comparison` 1.0.0 SHA-256 | `c79865caf913b2a1a5f6f50fccd8c37d6f2828e72feb1f80d9c9c7b4b7d9eb58` |
| Growth threshold (frozen) | `5.0` % |
| Freeze-record `code_sha256` | `da72a8e856712af019a4bdd8fbdf7c3c20be59d6593793fb3e91f0f49b2a5ea9` |
| Amendment current implementation SHA-256 | `5e3dc82dd443f84b400c683d40012ba31e8ff2a2833e7a5e71286f4ca035c694` |
| Development manifest SHA-256 | `cca0ee24d8574435761d2d057fd4341c5e015ee7d5337826f796ea832cf047dd` |

Freeze identity resolves via `profile_freeze_record.json` or append-only
`code_identity_amendment.json` (T-CX138d).

## Step 1 — Focused contextual suite

```text
python -m pytest tests/signal/test_context.py tests/dsp/test_contextual.py \
  tests/tools/test_contextual_tools.py tests/rules/test_contextual_profile.py \
  tests/agent/test_v03_contextual_runtime.py tests/agent/test_v03_prompt_v9_5.py \
  tests/app/test_contextual_models.py tests/app/test_contextual_reporting.py \
  tests/app/test_contextual_runs.py tests/app/test_contextual_service.py \
  tests/evaluation/contextual -v
```

**Result:** **116 passed**, 0 skipped, 0 xfailed
**Interpreter:** CPython 3.11.15 (`.venv`)

Note: plan path `tests/tools/test_contextual.py` maps to repository file
`tests/tools/test_contextual_tools.py`.

## Step 2 — Cumulative quality gates (T-CX141–T-CX145)

| Gate | Command | Result |
|---|---|---|
| Full pytest | `python -m pytest -v` (reported `-q`) | **1321 passed**, 1 warning, 0 skip/xfail |
| Ruff | `python -m ruff check .` | All checks passed |
| Mypy | `python -m mypy src` | Success: 95 source files |
| Architecture + preservation | `pytest tests/test_architecture_boundaries.py tests/evaluation/external/test_v03_contextual_preservation.py` | **62 passed** |
| Diff hygiene | `git diff --check 605c8a8` | Pass (no trailing-whitespace errors) |

**Warning (non-blocking):** Pydantic serializer warning in
`tests/evaluation/external/test_manifest.py::test_canonical_json_bytes_rejects_nan`.

**Gate fixes applied before green full suite / matrix:**

1. `tests/rules/test_engine.py` — growth FAIL sample `1.5` → `6.5` (threshold frozen at 5.0%).
2. `tests/evaluation/external/test_runner.py` — EV-T044/T045 set `DEEPSEEK_API_KEY=test-key` for secret-free matrix compatibility.

## Step 3 — Packaging and clean-environment matrix

### Wheel content inspection (local build)

Required contextual/static assets present:

- `signal_diag/rules/profiles/s1_contextual_comparison_v1.yaml`
- `signal_diag/rules/profiles/s1_distortion_v1.yaml`
- `signal_diag/app/static/{index.html,app.js,styles.css}`

Forbidden content absent: no `.wav`/`.flac`/`.mp3`, no `private/` or `acquired/` paths
(member_count=112).

### Dual-version matrix

```text
PIP_CONFIG_FILE=NUL PIP_INDEX_URL=https://pypi.org/simple \
  python scripts/verify_phase5_local_matrix.py \
    --python-3.11 <uv cpython-3.11.15> \
    --python-3.12 <uv cpython-3.12.13>
```

| Version | Interpreter | pytest | ruff | mypy | wheel smoke |
|---|---|---|---|---|---|
| 3.11.15 | `...\uv\python\cpython-3.11-windows-x86_64-none\python.exe` | 1321 passed | pass | pass | pass |
| 3.12.13 | `...\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe` | 1321 passed | pass | pass | pass |

**Matrix result:** `local 3.11/3.12 clean-environment verification passed`

Representative wheel/sdist digests from matrix wheel verifier:

| Phase | Artifact | SHA-256 |
|---|---|---|
| 3.11 wheel verify | `signal_diagnosis_agent-0.2.0-py3-none-any.whl` | `85cc839c6414f6352123ce3bd7a7a897ce5c48704863bf8f101338be3762ecf1` |
| 3.11 wheel verify | `signal_diagnosis_agent-0.2.0.tar.gz` | `961c605bc45bd88e5e382a036428addd503fe845c1194869b8aa55eb9e152b77` |
| 3.12 wheel verify | `signal_diagnosis_agent-0.2.0-py3-none-any.whl` | `0cfa7cb31a28fc9aabd83cb15ccefe63336cf2d516b636390b80e8ac0dbefb08` |
| 3.12 wheel verify | `signal_diagnosis_agent-0.2.0.tar.gz` | `24722eea828aca027179ae8bd0d308cfcea7d2d884f6ab045b8c85c106167e65` |

### Matrix notes / warnings

- User `pip` config pointed at Aliyun; hash mismatch aborted the first matrix
  attempt. Re-run forced official PyPI via `PIP_CONFIG_FILE=NUL` and
  `PIP_INDEX_URL=https://pypi.org/simple`.
- CPython 3.12.13 was installed via `uv python install 3.12.13` for this gate
  (missing interpreter is a release-gate failure, not a skip).
- Matrix intentionally strips `DEEPSEEK_API_KEY`; no real provider calls.

## Preservation

Protected V0.2 acceptance / evaluation assets were not rewritten. Untracked
local paths remaining outside this acceptance commit:

- `docs/evaluations/v0_2_external_wav/investigation_report_2026-09-02.md`
- `docs/evaluations/v0_3/validation/`

## Explicit non-authorization

Task 12 does **not** authorize:

- Task 13 one-shot real-model development confirmation
- validation construction, seal, or real-model validation
- ScriptedPlanner product fallback
- any claim that development or validation experimental targets are met

## Verdict

```text
harness_complete
```

Code, packaging, and dual-version clean-environment gates for the V0.3
contextual harness are accepted. Stop here pending separate Task 13
authorization.
