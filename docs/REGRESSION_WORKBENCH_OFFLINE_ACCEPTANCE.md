# Regression workbench offline acceptance (Phase A + Phase B)

Status: Phase A Tasks 1–4 + Phase B Tasks 5–6 + Task 9 closeout evidence.
Product comparison profiles enabled in production: **0**.
User-benefit and RealLLM retest claims: **unverified**.
Commit/push/draft PR authorized for Codex review. Merge/seal/RealLLM remain gated.
Tasks 7–8 (retest planner / offline contrast) **not authorized** in this stage.

## Baseline

- Plan read-only baseline: `4b45f73997a3da89b19eb00846231c6bc84a7709`
- Branch tip at handoff import: `1f42677` (docs-only)
- Phase A tip after Codex revise (overall-pass fix): `2885d4b` on `cursor/s1-regression-workbench-impl-8b52`
- Phase B Task 5: `9e3f6de`; Task 6: `1029268` (pre-closeout)
- Authority: `docs/CONTRACTS_V0_3_CONTEXTUAL.md` §22, D042, design/plan documents
- Spec SHA256: `536b71ddb6e5f3b3369fa49a1aa4e7ad5471497d88b89977822600fa9a990fe4`
- Plan SHA256: `225e0ddfbd49281a1dd210726985db773b1e503b5133de90cb9ec8128bbd1b84`

## Scope covered

| Layer | Covered | Notes |
|---|---|---|
| Definition (§22, T-CX329–348, D042) | Yes | Task 1 registration |
| Unit: `regression_measurement` | Yes | `tests/tools/test_regression_measurement.py` |
| Unit: `rules/regression` | Yes | `tests/rules/test_regression.py` + fixtures |
| Real-tool integration (PCM → load → measure → compare) | Yes | `tests/evaluation/test_regression_measurement_acceptance.py` |
| In-session service (Task 5) | Yes | `tests/app/test_regression_service.py` |
| Reporting / API / static UI (Task 6) | Yes | reporting/api/ui tests + HTTP proof |
| Architecture allowlist / identity tip | Yes | app/ exempt in T285; tip `d042_regression_workbench_phase_b` |
| Retest planner / offline contrast | **Not yet** | Tasks 7–8 |

## Product profile posture

- Approved product `ComparisonProfile` count under `src/signal_diag/rules/profiles`: **0**
- Fixture tolerances live only under `tests/rules/regression_fixtures.py`. These are **not** product tolerances.
- Product `build_regression_service()` defaults `profile=None` (descriptive-only).

## AC / T-CX mapping

| Design AC | T-CX (plan) | Evidence |
|---|---|---|
| AC01–AC08, AC10–AC12, AC16 | T-CX329–335, T-CX345–346 | Phase A (see prior table in git history / Phase A tip) |
| AC09 case lifecycle / idempotency | T-CX336 / T-CX337 | `tests/app/test_regression_service.py` |
| AC13 reporting integrity / escape | T-CX338 | `tests/app/test_regression_reporting.py` |
| AC14 Web dual-file / retest path | T-CX339 | API/UI tests + HTTP proof note |
| AC15 planner / benefit | T-CX340–344, T-CX348 | **Not covered** (Tasks 7–8) |

## Commands and results (measured)

| Command | Result |
|---|---|
| `pytest tests/app/test_regression_service.py tests/app/test_regression_reporting.py tests/app/test_regression_api.py tests/app/test_regression_ui.py -q` | **37 passed** |
| HTTP proof on `127.0.0.1:8765` (capabilities → case → compare → repeat → repair → report.json/html → static) | **PASS** (case `case_270fd72c28954b36af76a366ee592923`); evidence under `.cursor/skills/verify-signal-diagnosis-agent/evidence/task6-regression-ui-browser-2026-10-04.md` |
| Browser/computerUse GUI recording | **Not executed** (computerUse model spend limit); HTTP covers the same routes the UI calls |
| Identity + architecture focused | tip `d042_regression_workbench_phase_b`; T285 app/ exempt; T269 allowlists `regression_api.py` |
| `python -m ruff check .` / `python -m mypy src` | pass (139 mypy files) |
| `git diff --check 4b45f73997a3da89b19eb00846231c6bc84a7709` | clean |
| `python -m pytest -q` (full, after T269 allowlist) | **1885 passed**, 1 warning |
| `python -m build` + clean-venv wheel ASGI smoke for `/regression` + `regression.js` | **PASS** |
| CPython 3.11/3.12 clean-environment matrix | **not executed** (not a release gate this round) |

## Identity (append-only)

- Phase A amendment: `d042_regression_workbench_phase_a` (`product_tree` `d2ca91ba…816e`)
- Phase B tip amendment: `d042_regression_workbench_phase_b`
- `current_implementation_sha256` unchanged: `9939842ca31ce0638d3ad985f418dbce80b6065b63ebbdb6daba9515ca1d67e3`
- Tip `product_tree_sha256`: `cda690d560fa71da49ae2021fd0e666d84f026352f050deb066b38c23ac58c64`
- Prompt / causal policy unchanged (`v0.3-s1-planner-9.11` / `v9_11_mode_aware_no_fault_recovery`)
- `model_calls`: **0**
- New modules are **not** Phase 4.3.1-certified; additive identity accounting only.

## Allowlist / layering notes (T285)

- Exact paths (Phase A): `tools/regression_measurement.py`, `rules/regression.py`
- Phase B app modules live under `src/signal_diag/app/` (T285 exempts `app/`)
- Packaged static: `regression.html`, `regression.js` via existing `static/*` package-data patterns
- evaluation ↛ app and rules/tools ↛ agent/app remain enforced by existing architecture tests

## Data shapes (Phase B)

- **ComparisonUpload / RetestLink / RegressionCaseSnapshot**: in-session case store; append-only comparisons; request_id idempotency
- **RegressionCaseReport**: validated comparisons + escaped HTML / source-preserving JSON
- Engineering limits: 20 MiB/file, 8 cases, 16 submits/case, one concurrent measurement group

## Open / not verified / blocked gates

- Product tolerance calibration and approved comparison profiles
- Retest planner (`v0.3-s1-retest-1.0`) and RealLLM runs (Tasks 7–8)
- User time savings or planner benefit studies
- Interactive browser GUI recording this session (HTTP proof substituted)
- Merge, seal, RealLLM, product tolerances
