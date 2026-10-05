# Regression workbench offline acceptance (Phase A + Phase B + Phase C Task 7–8)

Status: Phase A–B as before + **Phase C Task 7 offline** (PR #34 at `3684c20`) + **Phase C Task 8 offline + Task 9 closeout ready for Codex recheck** on branch `cursor/s1-regression-task8-offline-8b52`. Merge/seal/RealLLM/product tolerances **still gated** — this tip is for independent engineering recheck only.

Product comparison profiles enabled in production: **0**.

User-benefit and RealLLM retest claims: **unverified**. Do **not** derive product benefit from offline green tests.

Engineering offline verification only: fake SDK transport proves adapter wiring and scheme admission; **product tolerances are not enabled**; real-model quality and user benefit were **not** verified on this path.

Phase C Task 8: offline contrast evaluation in `src/signal_diag/evaluation/regression.py` with arms **`fixed_strategy`** (deterministic catalog priority) vs **`real_adapter_fake_transport`** (RealLLMRetestPlanner + fake transport — proves interface plumbing, **not** model intelligence, accuracy, or latency benefit). Recommendation history is **append-only** (distinct `recommendation_id` per successful `request_id`; same `request_id` remains idempotent).

Browser dual-file / retest / export path: **executed** (T-CX339). Design AC14 is scheme admission (Task 7 catalog/parse), not the browser path.

## Baseline

- Plan read-only baseline: `4b45f73997a3da89b19eb00846231c6bc84a7709`
- Merge baseline for Phase C Task 8 work: `3684c20` (`codex/v0.2-real-world-validation` after PR #34)
- Phase C Task 7 tip (merged): `3684c20`
- Phase C Task 8 branch: `cursor/s1-regression-task8-offline-8b52` (commits through Task 8 closeout on push)
- Authority: `docs/CONTRACTS_V0_3_CONTEXTUAL.md` §22, D042, design/plan documents

## Scope covered

| Layer | Covered | Notes |
|---|---|---|
| Definition (§22, T-CX329–348, D042) | Yes | Task 1 registration |
| Measurement + compare (Tasks 2–4) | Yes | tools/rules/evaluation acceptance tests |
| In-session service (Task 5) | Yes | `tests/app/test_regression_service.py` |
| Reporting / API / static UI (Task 6) | Yes | reporting/api/ui tests + HTTP + browser proof |
| Design AC14 scheme admission (Task 7) | Yes (offline) | eligible catalog + strict parse + service-boundary admission |
| Retest planner offline adapter (Task 7) | Yes | fake transport; real SDK MockTransport evidence (T285-clean) |
| Offline retest contrast evaluation (Task 8) | Yes (offline) | `evaluation/regression.py` + `tests/evaluation/test_regression_retests.py` |
| Retest planner / product RealLLM benefit | **Not verified** | Task 8 does not certify model quality or user benefit |

## Product / UI posture

- Approved product `ComparisonProfile` count under `src/signal_diag/rules/profiles`: **0**
- Product `build_regression_service()` defaults leave `retest_planner=None` so `recommendation_available` is **false**
- Recommendation button hidden until capabilities report `recommendation_available`

## Idempotency fingerprint (request_id)

Comparison and recommendation `request_id` fingerprints unchanged from Task 7. Recommendation rows **append** on each new `request_id`; retries with the same `request_id` reuse stored outcome and do not append or re-call the SDK.

## Phase C Task 8 offline (baseline `3684c20`)

| Check | Result (Cursor Cloud Agent) |
|---|---|
| Focused Task 8 + recommendations | `pytest tests/evaluation/test_regression_retests.py tests/app/test_regression_recommendations.py -q` → **23 passed** |
| Architecture (incl. T285 allowlist) | `pytest tests/test_architecture_boundaries.py -q` → run at closeout |
| Identity active tip | `d042_regression_workbench_phase_c_task8_offline` / product tree `e45c301db1944c425eaae0ab0671ea1bfa100b4b3d6f4ca51c5073e2af1dbcf3` |
| RealLLM network / product tolerances | **not verified** |
| Merge / seal | **blocked** (recheck does not authorize) |

Contrast arms (Task 8):

- `fixed_strategy`: `choose_fixed_retest` — complete_conditions → repeat_conditions → catalog order; not product wiring.
- `real_adapter_fake_transport`: service + `RealLLMRetestPlanner` + fake SDK; labels transport only.

Service-chain test asserts oracle/truth never appears in planner `user_json` (only `RetestContext` fields).

## Identity (append-only)

- `code_identity_amendment.json` remains append-only; prior rows unchanged.
- Active tip: `d042_regression_workbench_phase_c_task8_offline`
- `product_tree_sha256`: `e45c301db1944c425eaae0ab0671ea1bfa100b4b3d6f4ca51c5073e2af1dbcf3`
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

Commit/push of this Task 8 tip is for **Codex git fetch / independent recheck only**. It does **not** authorize merge, seal, RealLLM network runs, or product tolerances.

## Remaining P2 (not blocking recheck)

Empty OpenAI org/project headers; duplicate JSON keys; `#recommendation-status` UI; button/HTTP 409 recommendation tests; cancel-wait proof strength; typed HTTP error codes; wheel/CPython matrix not reclaimed as release gate.
