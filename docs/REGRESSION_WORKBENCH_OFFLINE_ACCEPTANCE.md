# Regression workbench offline acceptance (Phase A + Phase B + Phase C Task 7)

Status: Phase A–B as before + **Phase C Task 7 offline + Task 9 closeout Codex accept** at code tip `7a2b0c8` / docs tip `9f0f74f` on branch `cursor/s1-regression-task7-offline-8b52` (baseline `41b0cba`). Merge/Task 8/seal/RealLLM/product tolerances still gated.
Product comparison profiles enabled in production: **0**.
User-benefit and RealLLM retest claims: **unverified**.
Independent Codex offline accept recorded for Phase B tip `6997400` and Phase C Task 7 tip `7a2b0c8`/`9f0f74f`. Merge/seal/RealLLM remain gated.
Phase C Task 7: closed abstain codes, service-boundary admission, T285-clean real SDK one-call evidence via `build_openai_retest_client(http_client=...)`.
Task 8 (offline contrast evaluation chain) **not authorized**.
Browser dual-file / retest / export path: **executed** (T-CX339). Design AC14 is scheme admission (Task 7 catalog/parse), not the browser path.

## Baseline

- Plan read-only baseline: `4b45f73997a3da89b19eb00846231c6bc84a7709`
- Merge baseline for Phase C Task 7: `41b0cba` (`codex/v0.2-real-world-validation` after PR #33)
- Phase A tip after Codex revise: `2885d4b`
- Phase B Task 5: `9e3f6de`; Task 6: `1029268`; closeout: `4b11fab`
- Phase B revise (cancel/fingerprint/hash): `f86f1ac`
- Phase B revise2 tip: `0e22c3d`
- Phase B revise3 tip: `74ae50a` / identity `d042_regression_workbench_phase_b_revise3` / product tree `572f039d7e962d9906e03a95eb92a4fba64f135cdc490af2acce71f7c6875735`
- Phase B revise4 tip: `d66f346` / docs tip `6997400` / identity `d042_regression_workbench_phase_b_revise4` / product tree `5f73c757dee9771d6499cd2413ff5751679250e332ffb31332eaca5c43a7208d`
- Codex independent offline accept: tip `6997400` (code `d66f346`); transplant/double-cancel/busy-HTTP/original-hash/link-fingerprint/Web-F0 spot checks closed; reviewer **114 passed** (regression app + v9.11 identity + architecture); CI 4/4 SUCCESS
- Authority: `docs/CONTRACTS_V0_3_CONTEXTUAL.md` §22, D042, design/plan documents

## Scope covered

| Layer | Covered | Notes |
|---|---|---|
| Definition (§22, T-CX329–348, D042) | Yes | Task 1 registration |
| Measurement + compare (Tasks 2–4) | Yes | tools/rules/evaluation acceptance tests |
| In-session service (Task 5) | Yes | `tests/app/test_regression_service.py` |
| Reporting / API / static UI (Task 6) | Yes | reporting/api/ui tests + HTTP + browser proof |
| Cancel/busy/link fingerprint revise | Yes | cancel waits for worker; fingerprint includes `RetestLink` |
| Report integrity + pre-parse slot + Web F0 revise3 | Yes | shared report validate; `hold_operation_slot` before multipart read; omit hardcoded Web F0 |
| Case ownership + double-cancel revise4 | Yes | `case_id` on case records; nested cancel wait until worker done |
| Browser dual-file / repeat / repair / export (T-CX339) | Yes | headed Playwright + screen recording; see browser proof doc |
| Design AC14 scheme admission (Task 7) | Yes (offline) | eligible catalog + strict parse + **service-boundary** `validate_selection_against_context`; closed abstain codes |
| Retest planner offline adapter (Task 7) | Yes (committed tip) | `tests/agent/test_retest_planner.py`, `tests/app/test_regression_recommendations.py`; real AsyncOpenAI MockTransport |
| Retest planner / offline contrast (Task 8) | **Not yet** | Task 8 evaluation chain |

## Product / UI posture

- Approved product `ComparisonProfile` count under `src/signal_diag/rules/profiles`: **0**
- Product `build_regression_service()` defaults `profile=None` (descriptive-only) and leaves `retest_planner=None` so `recommendation_available` is **false**
- Recommendation button stays hidden until capabilities report `recommendation_available`
- Web UI omits harmonic `fundamental_hz` in comparison metadata so the measurement tool auto-estimates F0 (not a nominal stimulus declaration). Clients may still POST an explicit `fundamental_hz` via API when needed.
- `conditions.original_input_sha256` without uploaded original bytes is a **user declaration**, not a verified hash. When original bytes are uploaded, the service requires an exact match or fills the digest itself.
- `regression.js` uses `textContent` / `createElement` only (no `innerHTML` sinks; static check).

## Idempotency fingerprint (request_id)

Covers: baseline/candidate/optional-original **bytes**, upload metadata JSON (versions, filenames, conditions including declared `original_input_sha256`, selection), and optional `RetestLink`. Same `request_id` with any differing fingerprint is rejected.

Recommendation `request_id` fingerprints `case_id` + `comparison_id` + comparison digest. Same id with a different digest is rejected. One SDK call per new recommendation id; repeats reuse stored outcome.

## Cancel / concurrency

Single `ThreadPoolExecutor(max_workers=1)`. HTTP comparison and recommendation routes acquire `hold_operation_slot()` before work so a busy service returns 409. On `CancelledError`, the service waits for in-flight recommendation/SDK work before clearing `_busy`. Cancelled submits do not store a completed/failed `request_id` outcome, so the same id may retry. Overlap while work is still running returns busy.

## AC / T-CX mapping

| Design AC | T-CX | Evidence |
|---|---|---|
| AC09 case lifecycle / idempotency | T-CX336 / T-CX337 | service tests incl. cancel/link fingerprint |
| AC13 reporting integrity / escape | T-CX338 | `tests/app/test_regression_reporting.py` + exported browser reports |
| *(no design AC number for Web path)* | **T-CX339** | Browser dual-file + manual retest + export: `docs/REGRESSION_WORKBENCH_BROWSER_PROOF_2026-10-04.md` (HTTP proof is complementary only) |
| AC14 方案准入 | T-CX340 | Task 7: `eligible_retests` + `parse_retest_selection` + recommendation service path (fake transport) |
| AC15 planner / benefit | T-CX340–344, T-CX348 | Task 7 offline wiring only; **not** product RealLLM or benefit claims |

## Phase C Task 7 revise1b (T285 + SDK evidence; baseline `41b0cba`)

Codex revise P1s addressed across revise1 / revise1b:
1. Closed `abstain_reason_code` enum + fixed user-facing templates.
2. Service-boundary `validate_selection_against_context`.
3. Real SDK one-call evidence **without** `pytest.importorskip` or test-file `import openai` (T285): `build_openai_retest_client(..., http_client=httpx.MockTransport)`.
4. Builder pins `base_url` and blank `organization`/`project` so ambient `OPENAI_*` cannot redirect/attach tenant headers.
5. Adapter requires `max_retries` to be exact `int` 0 (rejects missing / `0.0` / nonzero).

| Check | Result |
|---|---|
| Codex independent recheck | **accept** (Task 7 offline + Task 9 closeout only) |
| Focused Task 7 files | **27 passed** |
| Focused Task 7 + T-CX254 identity tip | **28 passed** (corrected; was mistyped as 29) |
| Architecture (incl. T285) | **62 passed** at tip `7a2b0c8` |
| Identity tip | `d042_regression_workbench_phase_c_task7_revise1b` / product tree `27849cc6…` |
| Full `pytest -q` (this Cloud Agent) | **1923 passed**, 1 warning at tip `7a2b0c8` |
| Codex reviewer full suite | **1922 passed**, 1 failed (`test_t133_*` needs `pip wheel`; same on baseline; env) |
| RealLLM network / product tolerances | **not verified** |
| Merge / Task 8 / seal | **blocked** (accept does not authorize) |

Remaining P2 (not blocking accept): acceptance count typo (fixed here); empty OpenAI org/project headers; duplicate JSON keys; selection shape at service boundary; recommendation overwrite history; missing `#recommendation-status`; button/UI and HTTP 409 recommendation tests; cancel-wait proof strength.

Commands (measured on clean tip `7a2b0c8`; Cursor Cloud Agent + Codex reviewer):

| Command | Result |
|---|---|
| `pytest tests/agent/test_retest_planner.py tests/app/test_regression_recommendations.py -q` | **27 passed** |
| `pytest … + test_t_cx254_v911_behavior_identity_is_preserved_and_active_bridge_matches -q` | **28 passed** |
| `pytest tests/test_architecture_boundaries.py -q` | **62 passed** (T285 green; no importorskip/openai imports) |
| Full `pytest -q` | **1923 passed** here / **1922** at Codex (t133 wheel env) |
| Wheel / CPython 3.11/3.12 matrix | **not executed** (not a release gate) |

Correction: earlier drafts wrongly mapped interactive browser GUI to design AC14. Spec AC14 is scheme admission (“不适用方案或未批准参数不能由模型输出绕过”). Task 6 Web dual-file/manual retest is **T-CX339**.

## Commands and results (measured on revise4 working tree)

| Command | Result |
|---|---|
| `pytest tests/app/test_regression_{reporting,api,service,ui}.py -q` | **48 passed** |
| HTTP proof (capabilities→compare→repeat→repair→reports→static) | **PASS**; tracked in `docs/REGRESSION_WORKBENCH_HTTP_PROOF_2026-10-04.md` |
| Browser GUI (T-CX339) dual-file / repeat / repair / export | **PASS** at tip `4972100`; evidence under `.cursor/skills/verify-signal-diagnosis-agent/evidence/regression-browser-tcx339/`; recording `/opt/cursor/artifacts/regression-browser-tcx339-task6.mp4`; see `docs/REGRESSION_WORKBENCH_BROWSER_PROOF_2026-10-04.md` |
| `python -m ruff check` / `python -m mypy` on touched app modules | pass (revise4) |
| `git diff --check 4b45f73997a3da89b19eb00846231c6bc84a7709` | clean (touched paths) |
| `python -m pytest -q` (full, tip `d66f346`) | **1896 passed**, 1 warning |
| Wheel ASGI smoke for `/regression` + `regression.js` | previously **PASS** at Task 6 closeout; not reclaimed as release matrix |
| CPython 3.11/3.12 clean-environment matrix | **not executed** |

## Identity (append-only)

- `code_identity_amendment.json` under the contextual development study is an **append-only identity bridge**, not a sealed Demo/official evaluation asset. Revise rows only append tip entries; prior rows retain prior digests.
- `tests/agent/test_v03_prompt_v9_11.py` tip assertions are updated so the active tip equals `contextual_product_tree_sha256()`; older tip rows stay pinned to historical digests. Prompt/causal identity remains `v0.3-s1-planner-9.11` / `v9_11_mode_aware_no_fault_recovery`.
- Phase B tips: `d042_regression_workbench_phase_b` → `…_revise` → `…_revise2` → `…_revise3` → `…_revise4`
- Phase C tips: `…_task7_offline` → `…_revise1` → `…_revise1b`
- Tip `product_tree_sha256`: `27849cc6f09d56d1d929d7dd0b83cd369b2ca6846db61788287bedc391626d2b`
- Prior tips retained: offline `29df07a0…`, revise1 `5f9c03ae…`
- `current_implementation_sha256` unchanged: `9939842ca31ce0638d3ad985f418dbce80b6065b63ebbdb6daba9515ca1d67e3`
- `model_calls`: **0**

## Allowlist / layering

- T285 exact paths (Phase A): `tools/regression_measurement.py`, `rules/regression.py`
- Phase C Task 7 exact path: `src/signal_diag/agent/retest_planner.py`
- Phase B/C app modules under `src/signal_diag/app/` (T285 exempts `app/`)
- T269 allows FastAPI only in `api.py`, `multipart.py`, `regression_api.py`
- Layer FORBIDDEN table already covers evaluation ↛ app and rules/tools ↛ agent/app
- HTTP status string-matching for regression `invalid_request` remains a known P2 (typed codes deferred; frozen `AppErrorCode` not expanded)

## Open / not verified / blocked gates

- Product tolerance calibration / approved profiles
- Task 8 offline contrast evaluation + useful_retest scoring
- Approved retest run config (model/limits) to enable product recommendations
- RealLLM retest quality / user-benefit claims
- Typed HTTP error codes (P2; string-matching deferred)
- Merge, seal

Commit/push of this Phase C Task 7 tip is for **Codex git fetch / independent recheck only**. It does **not** authorize Task 8, merge, seal, RealLLM, or product tolerances. Task 7 offline green proves adapter wiring and scheme admission under fake transport only.
