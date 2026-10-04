# Regression workbench offline acceptance (Phase A + Phase B)

Status: Phase A Tasks 1–4 + Phase B Tasks 5–6 + Task 9 closeout + revise/revise2/revise3.
Product comparison profiles enabled in production: **0**.
User-benefit and RealLLM retest claims: **unverified**.
Commit/push/draft PR authorized for Codex review. Merge/seal/RealLLM remain gated.
Tasks 7–8 (retest planner / offline contrast) **not authorized**.

## Baseline

- Plan read-only baseline: `4b45f73997a3da89b19eb00846231c6bc84a7709`
- Phase A tip after Codex revise: `2885d4b`
- Phase B Task 5: `9e3f6de`; Task 6: `1029268`; closeout: `4b11fab`
- Phase B revise (cancel/fingerprint/hash): `f86f1ac`
- Phase B revise2 tip: `0e22c3d`
- Phase B revise3 tip: identity `d042_regression_workbench_phase_b_revise3` / product tree `572f039d7e962d9906e03a95eb92a4fba64f135cdc490af2acce71f7c6875735`
- Authority: `docs/CONTRACTS_V0_3_CONTEXTUAL.md` §22, D042, design/plan documents

## Scope covered

| Layer | Covered | Notes |
|---|---|---|
| Definition (§22, T-CX329–348, D042) | Yes | Task 1 registration |
| Measurement + compare (Tasks 2–4) | Yes | tools/rules/evaluation acceptance tests |
| In-session service (Task 5) | Yes | `tests/app/test_regression_service.py` |
| Reporting / API / static UI (Task 6) | Yes | reporting/api/ui tests + HTTP proof doc |
| Cancel/busy/link fingerprint revise | Yes | cancel waits for worker; fingerprint includes `RetestLink` |
| Report integrity + pre-parse slot + Web F0 revise3 | Yes | shared report validate; `hold_operation_slot` before multipart read; omit hardcoded Web F0 |
| Retest planner / offline contrast | **Not yet** | Tasks 7–8 |

## Product / UI posture

- Approved product `ComparisonProfile` count under `src/signal_diag/rules/profiles`: **0**
- Product `build_regression_service()` defaults `profile=None` (descriptive-only)
- Web UI omits harmonic `fundamental_hz` in comparison metadata so the measurement tool auto-estimates F0 (not a nominal stimulus declaration). Clients may still POST an explicit `fundamental_hz` via API when needed.
- `conditions.original_input_sha256` without uploaded original bytes is a **user declaration**, not a verified hash. When original bytes are uploaded, the service requires an exact match or fills the digest itself.
- `regression.js` uses `textContent` / `createElement` only (no `innerHTML` sinks; static check).

## Idempotency fingerprint (request_id)

Covers: baseline/candidate/optional-original **bytes**, upload metadata JSON (versions, filenames, conditions including declared `original_input_sha256`, selection), and optional `RetestLink`. Same `request_id` with any differing fingerprint is rejected.

## Cancel / concurrency

Single `ThreadPoolExecutor(max_workers=1)`. HTTP comparison routes acquire `hold_operation_slot()` before reading multipart bytes, so a busy service returns 409 without parsing the upload body. On `CancelledError`, the service waits for the worker future to finish before clearing `_busy` / `case.running`. Cancelled submits do not store a completed/failed `request_id` outcome, so the same id may retry. Overlap while the cancelled worker is still running returns busy.

## AC / T-CX mapping (Phase B)

| Design AC | T-CX | Evidence |
|---|---|---|
| AC09 case lifecycle / idempotency | T-CX336 / T-CX337 | service tests incl. cancel/link fingerprint |
| AC13 reporting integrity / escape | T-CX338 | `tests/app/test_regression_reporting.py` |
| AC14 Web dual-file / retest path | T-CX339 | **pending** interactive browser GUI; HTTP proof in `docs/REGRESSION_WORKBENCH_HTTP_PROOF_2026-10-04.md` does not substitute |
| AC15 planner / benefit | T-CX340–344, T-CX348 | **Not covered** (Tasks 7–8) |

## Commands and results (measured on revise3 working tree)

| Command | Result |
|---|---|
| `pytest tests/app/test_regression_{reporting,api,service,ui}.py -q` | **45 passed** |
| HTTP proof (capabilities→compare→repeat→repair→reports→static) | **PASS**; tracked in `docs/REGRESSION_WORKBENCH_HTTP_PROOF_2026-10-04.md` |
| Browser/computerUse GUI recording | **Not executed** (AC14 pending) |
| `python -m ruff check` / `python -m mypy` on touched app modules | pass (revise3) |
| `git diff --check 4b45f73997a3da89b19eb00846231c6bc84a7709` | clean (touched paths) |
| `python -m pytest -q` (full) | recorded after commit |
| Wheel ASGI smoke for `/regression` + `regression.js` | previously **PASS** at Task 6 closeout; not reclaimed as release matrix |
| CPython 3.11/3.12 clean-environment matrix | **not executed** |

## Identity (append-only)

- `code_identity_amendment.json` under the contextual development study is an **append-only identity bridge**, not a sealed Demo/official evaluation asset. Revise rows only append tip entries; prior rows retain prior digests.
- `tests/agent/test_v03_prompt_v9_11.py` tip assertions are updated so the active tip equals `contextual_product_tree_sha256()`; older tip rows stay pinned to historical digests. Prompt/causal identity remains `v0.3-s1-planner-9.11` / `v9_11_mode_aware_no_fault_recovery`.
- Phase B tips: `d042_regression_workbench_phase_b` → `…_revise` → `…_revise2` → `…_revise3`
- Tip `product_tree_sha256`: `572f039d7e962d9906e03a95eb92a4fba64f135cdc490af2acce71f7c6875735`
- `current_implementation_sha256` unchanged: `9939842ca31ce0638d3ad985f418dbce80b6065b63ebbdb6daba9515ca1d67e3`
- `model_calls`: **0**

## Allowlist / layering

- T285 exact paths (Phase A): `tools/regression_measurement.py`, `rules/regression.py`
- Phase B app modules under `src/signal_diag/app/` (T285 exempts `app/`)
- T269 allows FastAPI only in `api.py`, `multipart.py`, `regression_api.py`
- HTTP status string-matching for regression `invalid_request` remains a known P2 (typed codes deferred; frozen `AppErrorCode` not expanded)

## Open / not verified / blocked gates

- Product tolerance calibration / approved profiles
- Tasks 7–8 planner + RealLLM
- Interactive browser GUI recording
- Typed HTTP error codes (P2)
- Merge, seal, RealLLM, product tolerances
