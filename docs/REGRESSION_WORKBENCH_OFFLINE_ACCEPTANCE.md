# Regression workbench offline acceptance (Phase A + Phase B + Phase C Task 7–8)

Status: Phase A–B as before + **Phase C Task 7 offline** (PR #34 at `3684c20`) + **Phase C Task 8 offline revise1** on branch `cursor/s1-regression-task8-offline-8b52`. Claude Code revise **P1s fixed** at tip `revise1` (see measured checks below). Merge/seal/RealLLM/product tolerances **still gated**.

Product comparison profiles enabled in production: **0**.

User-benefit and RealLLM retest claims: **unverified**. Do **not** derive product benefit from offline green tests.

Engineering offline verification only: fake SDK transport proves adapter wiring and scheme admission; **product tolerances are not enabled**; real-model quality and user benefit were **not** verified on this path.

Phase C Task 8: offline contrast evaluation in `src/signal_diag/evaluation/regression.py` with arms **`fixed_strategy`** (deterministic catalog priority) vs **`real_adapter_fake_transport`** (RealLLMRetestPlanner + fake transport — proves interface plumbing, **not** model intelligence, accuracy, or latency benefit). Recommendation history is **append-only** (distinct `recommendation_id` per successful `request_id`; same `request_id` remains idempotent).

Browser dual-file / retest / export path: **executed** (T-CX339). Design AC14 is scheme admission (Task 7 catalog/parse), not the browser path.

Historical Phase B command tables and closeout tips remain documented at Task 7 branch tip `3684c20` / merged PR #34 acceptance snapshot; this file retains the AC mapping below and adds Task 8 revise measurements.

## Baseline

- Plan read-only baseline: `4b45f73997a3da89b19eb00846231c6bc84a7709`
- Merge baseline for Phase C Task 8 work: `3684c20` (`codex/v0.2-real-world-validation` after PR #34)
- Phase C Task 7 tip (merged): `3684c20`
- Phase C Task 8 branch: `cursor/s1-regression-task8-offline-8b52` (commits through Task 8 revise1 on push)
- Authority: `docs/CONTRACTS_V0_3_CONTEXTUAL.md` §22, D042, design/plan documents

## Scope covered

| Layer | Covered | Notes |
|---|---|---|
| Definition (§22, T-CX329–348, D042) | Yes | Task 1 registration |
| Measurement + compare (Tasks 2–4) | Yes | tools/rules/evaluation acceptance tests |
| In-session service (Task 5) | Yes | `tests/app/test_regression_service.py` |
| Reporting / API / static UI (Task 6) | Yes | reporting/api/ui tests + HTTP + browser proof |
| Cancel/busy/link fingerprint revise (Phase B) | Yes | cancel waits for worker; fingerprint includes `RetestLink` |
| Browser dual-file / repeat / repair / export (T-CX339) | Yes | headed Playwright + screen recording; see browser proof doc |
| Design AC14 scheme admission (Task 7) | Yes (offline) | eligible catalog + strict parse + service-boundary admission |
| Retest planner offline adapter (Task 7) | Yes | fake transport; real SDK MockTransport evidence (T285-clean) |
| Offline retest contrast evaluation (Task 8) | Yes (offline) | `evaluation/regression.py` + `tests/evaluation/test_regression_retests.py` |
| Retest planner / product RealLLM benefit | **Not verified** | Task 8 does not certify model quality or user benefit |

## Product / UI posture

- Approved product `ComparisonProfile` count under `src/signal_diag/rules/profiles`: **0**
- Product `build_regression_service()` defaults leave `retest_planner=None` so `recommendation_available` is **false**
- Recommendation button hidden until capabilities report `recommendation_available`
- `conditions.original_input_sha256` without uploaded original bytes is a **user declaration**, not a verified hash.
- `regression.js` uses `textContent` / `createElement` only (no `innerHTML` sinks; static check).

## Idempotency fingerprint (request_id)

Comparison and recommendation `request_id` fingerprints unchanged from Task 7. Recommendation rows **append** on each new `request_id`; retries with the same `request_id` reuse stored outcome and do not append or re-call the SDK. Phase B revise history: fingerprint covers baseline/candidate bytes, upload metadata JSON, and optional `RetestLink`.

## AC / T-CX mapping

| Design AC | T-CX | Evidence |
|---|---|---|
| AC09 case lifecycle / idempotency | T-CX336 / T-CX337 | service tests incl. cancel/link fingerprint |
| AC13 reporting integrity / escape | T-CX338 | `tests/app/test_regression_reporting.py` + exported browser reports |
| *(no design AC number for Web path)* | **T-CX339** | Browser dual-file + manual retest + export: `docs/REGRESSION_WORKBENCH_BROWSER_PROOF_2026-10-04.md` |
| AC14 方案准入 | T-CX340 | Task 7: eligible catalog + parse + `validate_selection_against_context` |
| AC15 planner / benefit | T-CX340–344, T-CX348 | Task 7 offline wiring; Task 8 contrast scoring offline only; **not** product benefit |

Correction: interactive browser GUI is **T-CX339**, not design AC14. Spec AC14 is scheme admission.

## Phase C Task 8 offline revise1 (baseline `3684c20`; Claude Code P1s)

P1 fixes at revise1:

1. `score_retest_cases` validates selections with `validate_selection_against_context` (forged option/basis → not valid).
2. `useful_retest` uses case `revealed_outcomes` via `reveal_outcome_for_selection`; mismatched `result.revealed` raises `ValueError`.
3. `scheduled_arms` default emits both contrast arms with `scheduled=len(cases)` even when results absent.

| Check | Result (Cursor Cloud Agent, revise1) |
|---|---|
| Focused Task 8 + recommendations | `pytest tests/evaluation/test_regression_retests.py tests/app/test_regression_recommendations.py -q` → **29 passed** |
| Architecture (incl. T285 allowlist) | `pytest tests/test_architecture_boundaries.py -q` → **62 passed** |
| Identity T-CX254 | `pytest tests/agent/test_v03_prompt_v9_11.py -k t_cx254 -q` → **3 passed** |
| Full `pytest -q` | **1943 passed**, 1 warning |
| `ruff check src/signal_diag/evaluation/regression.py` | pass |
| `mypy src/signal_diag/evaluation/regression.py` | pass |
| `git diff --check 3684c20` | clean |
| RealLLM network / product tolerances | **not verified** |
| Merge / seal | **blocked** (revise does not authorize) |

Contrast arms (Task 8):

- `fixed_strategy`: `choose_fixed_retest` — complete_conditions → repeat_conditions → catalog order; not product wiring.
- `real_adapter_fake_transport`: service + `RealLLMRetestPlanner` + fake SDK; labels transport only.

Service-chain test asserts oracle/truth never appears in planner `user_json` (only `RetestContext` fields).

## Identity (append-only)

- `code_identity_amendment.json` remains append-only; prior rows unchanged.
- Pinned tip: `d042_regression_workbench_phase_c_task8_offline` / product tree `e45c301db1944c425eaae0ab0671ea1bfa100b4b3d6f4ca51c5073e2af1dbcf3`
- Active tip: `d042_regression_workbench_phase_c_task8_revise1` / product tree `e45c301db1944c425eaae0ab0671ea1bfa100b4b3d6f4ca51c5073e2af1dbcf3` (live `contextual_product_tree_sha256()` after revise1)
- Prior active tip retained: `d042_regression_workbench_phase_c_task7_revise1b` / `27849cc6…`
- `current_implementation_sha256` unchanged: `9939842ca31ce0638d3ad985f418dbce80b6065b63ebbdb6daba9515ca1d67e3`
- `model_calls`: **0**

## Allowlist / layering

- T285 exact paths include Phase C Task 7 `src/signal_diag/agent/retest_planner.py` and Task 8 `src/signal_diag/evaluation/regression.py`
- Phase B/C app modules under `src/signal_diag/app/` (T285 exempts `app/`)
- Layer FORBIDDEN: evaluation must not import app (enforced by architecture tests)

## Open / not verified / blocked gates

- Product tolerance calibration / approved profiles
- Approved retest run config on product path
- RealLLM retest quality / user-benefit claims
- Merge, seal

Commit/push of this Task 8 revise1 tip is for **independent recheck only**. It does **not** authorize merge, seal, RealLLM network runs, or product tolerances.

## Remaining P2 (not blocking recheck)

Empty OpenAI org/project headers; duplicate JSON keys; `#recommendation-status` UI; button/HTTP 409 recommendation tests; cancel-wait proof strength; typed HTTP error codes; wheel/CPython matrix not reclaimed as release gate.
