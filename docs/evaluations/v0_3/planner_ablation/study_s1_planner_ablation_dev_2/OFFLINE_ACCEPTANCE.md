# Offline acceptance: `study_s1_planner_ablation_dev_2`

**Status:** study-only offline harness acceptance recorded for Task 7 (gates/refusal tests; not seal or live-run readiness).
**Not a protocol seal.** No `protocol_seal/` directory exists under this study root.
**Not live-run readiness.** Green refusal / harness tests prove offline gates only.

Baseline commit (PR #17 merge / Task 7 starting point):

`8962747ade7052584f3ddcd25e50ad42992273cc`

## Offline execution identity

| Field | Value |
|-------|-------|
| study_id | `study_s1_planner_ablation_dev_2` |
| scoring_identity | `signal_diag.planner_ablation_scoring` |
| scoring_version | `2.0.0-dev.1` |
| execution_identity | `harness_only` |
| product planner under dry-run | `ScriptedFinishPlanner` (Scripted service path) |
| fixed arm | `PlannerAblationFixedPipelineBaseline` |
| schedule | 114 slots (57 product + 57 fixed); 9 single + 10 paired keys × 3 rounds |
| timing contract | `encoded_bytes_to_terminal_v1` |
| clock used in acceptance | `ControlledClock` with injected phase advances |
| latency claim | **None.** Synthetic clock values are harness metadata only and are **never** RealLLM latency evidence. |
| provider calls | **0** (fail-on-call spy at provider/client boundary) |
| RealLLM / network | **Not invoked** |
| formal seal | **Not created** |

## Label review state

| Field | Value |
|-------|-------|
| `design_inputs.md` review_status | `independent_offline_review_complete` |
| approved | `true` (independent offline reviewer, 2026-10-01) |
| evidence | `LABEL_REVIEW.md` + updated `design_inputs.md` review records |
| implementer self-check | superseded; does not substitute for seal grant |
| Codex / design-owner re-ack | recommended under current role split (design=Codex); not a seal |
| fabricated signoff | **none** |

Independent offline label review no longer blocks seal candidate readiness on label grounds.
Seal, RealLLM, and product changes remain separately gated.

## Configuration / budget blockers (Task 5 `inspect_limits`)

Observed from `snapshot_effective_configuration()` + `inspect_limits()` on default `AgentLimits` (offline):

| Field | Value |
|-------|-------|
| `execution_blocked` | `true` |
| `seal_ready` | `false` |

Blockers (exact):

- `unknown_max_tokens_bound`
- `unknown_provider_request_timeout`
- `unknown_transport_attempts_per_call_bound`
- `unavailable_retry_telemetry`
- `unknown_planner_calls_per_slot_bound`
- `agent_limits_do_not_prove_planner_call_bound:tool_count_is_not_planner_calls`
- `unknown_input_token_bound`
- `unknown_output_token_bound`
- `unknown_provider_sdk_identity`
- `worst_case_requests_uncomputable`

These unknown production request/token/transport bounds remain **seal and RealLLM execution blockers**. Green offline tests do not resolve them.

## Preservation hashes / notes

Relative to baseline `8962747ade7052584f3ddcd25e50ad42992273cc`:

| Path | SHA-256 |
|------|---------|
| `src/signal_diag/app/composition.py` | `578ced2aa3341a634ec6108a8a5c228623f4614610d154d3ace4cedb3b443fe3` |
| `src/signal_diag/evaluation/contextual/baseline.py` | `324af058471ecb89537ce6e1760fae7fecfdc259262e3e5834911f2b1a0edfd0` |
| `docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_1/protocol_seal/manifest.json` | `2c6e0914f72feffdd6a9bf0d854c83a73562d69d4d7be113e95df08fca1ca0dc` |
| `.../study_s1_planner_ablation_dev_1/protocol_seal/seal_meta.json` | `ac513bc99e71f8dfaa725d9bba2c93915f7bd934bb78ae49557d27c4935a3032` |
| `.../study_s1_planner_ablation_dev_1/protocol_seal/seal.sha256` | `2388b52db40d090f14c110f5ba74ec02aeb7fc0afff76524e8c5b58300e57de6` |

Notes:

- Public product builder (`build_product_service`) remains `RealLLMPlanner`; no Scripted silent fallback.
- Historical contextual baseline module bytes unchanged.
- `study_s1_planner_ablation_dev_1` seal files unchanged; no rewrite/migration.
- Additive append-only row `d038_planner_ablation_protocol_revision_dev_2` records the product-tree digest after adding `app/planner_ablation_v2_adapter.py` (`18221d0936e667e44c38275bdb0e36e54bf74e4b6c58d6dfc82b607299925de6`). Wave 2 `d038_planner_ablation_wave2_harness` row is preserved unchanged.
- Append-only row `d038_planner_ablation_dev_2_snapshot_failure_classification` records the live product-tree digest after P1 snapshot failure classification on `planner_ablation_v2_adapter.py` (`7b9299d22c1a0103f81731624cec9ccc0be05eac6370f5c24ae68f23b19d34b3`); historical `d038_planner_ablation_protocol_revision_dev_2` row remains at `18221d…`.

## T-CX289–T-CX302 → tests mapping

| ID | Obligation (short) | Owning tests |
|----|--------------------|--------------|
| T-CX289 | Request identity, equal-input oracle, aliases | `tests/evaluation/planner_ablation/v2/test_population.py` |
| T-CX290 | Unique schedule, source/master, 114 slots, order | `test_population.py` (`test_alias_collision_and_schedule`) |
| T-CX291 | Fixed U/C/G, truth-free `ByteRequest` | `test_population.py`; scoring U/C/G in `test_scoring.py` |
| T-CX292 | Shared timer decode/execute/guidance; exclude persistence | `test_timing.py`; `tests/app/test_planner_ablation_v2_adapter.py` |
| T-CX293 | D037 contextual entry; two-arm gate/guidance parity | `test_planner_ablation_v2_adapter.py` |
| T-CX294 | Actual provenance; relabeled offline rejected | `test_planner_ablation_v2_adapter.py`; `test_offline_acceptance.py::test_relabelled_harness_bundle_is_not_scored_product` |
| T-CX295 | Quality/usefulness/completion populations | `test_scoring.py` |
| T-CX296 | Semantic support; zero-claim / zero-eligibility | `test_scoring.py` |
| T-CX297 | Zero-loss decision; mode/round gates | `test_decision.py` |
| T-CX298 | Infrastructure stop vs behavioral continue | `test_campaign.py` |
| T-CX299 | Limits, budget blockers, resource telemetry | `test_campaign.py`; blockers re-asserted in `test_offline_acceptance.py` |
| T-CX300 | Seal binding; readonly verify; refuse existing | `test_sealing.py` |
| T-CX301 | Dev_1 preservation; evaluation ↛ app; product builder | `tests/test_architecture_boundaries.py` (`test_t_cx301_*`); `test_sealing.py` refuse-dev1 |
| T-CX302 | Full offline schedule; fail-on-call spy; review pending | `test_offline_acceptance.py` (`test_complete_harness_schedule_has_no_provider_calls`, `test_offline_acceptance_review_status_stays_pending`) |

## Verification commands and results

Environment: `export PATH="/home/ubuntu/.local/bin:$PATH"`.

```text
$ pytest tests/evaluation/planner_ablation tests/app/test_planner_ablation_adapter.py tests/app/test_planner_ablation_v2_adapter.py -q
143 passed in 33.98s

$ pytest -q
1662 passed, 1 warning in 78.62s

$ ruff check .
All checks passed!

$ mypy src
Success: no issues found in 127 source files

$ pytest tests/test_architecture_boundaries.py -q
62 passed in 6.14s

$ git diff --check
(exit 0; no whitespace errors)
```

Required skip/xfail: **none**. Live-model gate: **not invoked**. Wheel smoke: **not required** (no packaging change).

## Honest readiness statement

Green offline acceptance and green provenance **refusal** tests demonstrate that:

1. the 114-slot harness schedule runs through Scripted + fixed adapters with **zero** provider calls;
2. relabeled harness / fake-client RealLLMPlanner artifacts are rejected for scored product ingestion;
3. architecture and preservation gates hold for evaluation ↛ app, public product builder, contextual baseline, and `dev_1` seal bytes.

They do **not** prove:

- that production request/token/timeout/retry bounds are known;
- that a numerical worst-case budget for 57 product slots exists;
- that independent label review is complete;
- that a sealed `dev_2` protocol exists;
- that a RealLLM campaign may run;
- that any product planner change is authorized.

**Green refusal tests ≠ live-run readiness.**

## Exact future grant boundaries (still separately gated)

| Gate | Still required before… |
|------|-------------------------|
| Operator acceptance of label review + remaining budget closure | seal candidate readiness |
| Seal grant on concrete candidate manifest, schedule, bands, budgets | creating `protocol_seal/` under this study root |
| RealLLM grant with sealed identity + numerical request/token budget | any provider/network campaign |
| Separate product design + contracts + tests + operator auth | any product planner / composition change |

Offline implementation PR #18 merged to `codex/v0.2-real-world-validation` at `5d0a325` (tip `e118be5`). Label/budget follow-up lives on a separate preseal docs branch.

## Seal prerequisites (concrete checklist)

1. ~~Independent offline reviewer records approval for all ten oracle rows, alias, U/C/G, targets~~ — done in `LABEL_REVIEW.md` (`approved=true`). Optional Codex design-owner re-ack.
2. Resolve remaining `inspect_limits` blockers — see `BUDGET_BOUNDS.md`. Still open: `unknown_max_tokens_bound`, input/output token bounds, `unavailable_retry_telemetry`. Conditional SDK attempt ceiling `57×28×3=4788` is audit-derived only (not a proven HTTP send ceiling); `seal_ready` remains **false**.
3. Separate **seal grant** naming the concrete candidate manifest, schedule digest, decision bands, and budgets.
4. Separate **commit authorization** so the sealed implementation identity can bind an immutable commit.
5. Generate seal only into a **new** destination; never regenerate `dev_1`; never treat offline acceptance as the seal.
6. Only after seal verify: separate **RealLLM grant** with exact seal digest and budget — still no product-composition change without its own grant.

## Candidate manifest description (unsealed)

A future seal candidate must bind: unique-request schedule + aliases; scenario/source/master relations; every mode oracle + offline label-review record; U/C/G membership; timing/lifecycle/order/repetitions/limits/decision bands; original WAV and canonical request hashes; immutable implementation commit and product/prompt/profile/corpus/study-code hashes; dependency/runtime versions; operator authorization references. Construction path: `verify_manifest` / `generate_seal` under a seal grant only.

---

Task 7 offline implementation merged via PR #18. Post-merge label review + budget audit recorded under operator grant (2026-10-01). No real seal created. No RealLLM run.

## Token/transport telemetry offline implementation (Tasks 2–7)

**Status:** `offline_implementation_pending_revision` — Codex tip `218c2fa` P1/P2
recheck fixes applied in this revision (candidate validation enforcement, event-graph
recompute, fixed-arm digests, mount/proxy transport observation, unsupported profile
blocking, proof provenance authentication, token exposure). **Not** claiming
`offline_implementation_accepted` until independent recheck. Not
`resource_bounds_complete`, not `candidate_verified`, not seal, not RealLLM.

Honest external blockers remain open: HTTP/token bound admission, unaccepted provider
model mapping, lockfile↔install drift. Gates must not be loosened to clear them.

Observation defaults **off**. Public `RealLLMPlanner` constructors/payloads unchanged.
No commit/push/seal/RealLLM under this grant.

### Revision verification (this environment)

```text
$ export PATH="/home/ubuntu/.local/bin:$PATH"
$ pytest tests/agent/test_provider_telemetry.py tests/agent/test_telemetry.py \
    tests/agent/test_runtime_telemetry.py \
    tests/evaluation/planner_ablation/v2/test_resource_telemetry.py \
    tests/evaluation/planner_ablation/v2/test_resource_budget.py \
    tests/evaluation/planner_ablation/v2/test_resource_candidate.py \
    tests/evaluation/planner_ablation/v2/test_offline_acceptance.py \
    tests/app/test_planner_ablation_v2_adapter.py -q
52 passed

$ pytest tests/evaluation/planner_ablation tests/agent/test_real_llm_planner.py \
    tests/evaluation/test_recording.py tests/test_architecture_boundaries.py -q
(+ focused overlap) 326 passed total across required sets

$ ruff check --no-cache src tests scripts
All checks passed!

$ mypy --no-incremental src
Success: no issues found in 132 source files

$ git diff --check
(exit 0)
```

Installed observation profile here: `openai==3.20.0` matches reviewed
`RESOURCE_BOUNDS.md` digests (`ad8a3f77…`). CI may install a different
`openai>=1.0` resolution; audited support then latches unsupported, while
offline MockTransport fixture attach may still observe hooks without claiming
reviewed capability.

### Remaining seal / budget blockers (honest)

| Blocker | Status |
|---------|--------|
| `unproved_http_send_bound` | open — no admitted HTTP factor `H` |
| `unproven_failed_attempt_token_bound` | open — context capacity ≠ failed-attempt exposure |
| `unknown_input_token_bound` / `unknown_output_token_bound` | open |
| `unaccepted_provider_model_mapping` | open — legacy `deepseek-v4-flash` route unaccepted |
| Lockfile `openai==3.6.0` vs installed `3.20.0` | recorded drift; re-bind at seal time |
| Legacy `inspect_limits` explicit-flag path | still `execution_blocked=True` |

Conditional SDK ceiling `57×28×3=4788` remains documentation/admission arithmetic only.

### T-CX303–T-CX318 → tests mapping

| ID | Owning tests |
|----|--------------|
| T-CX303 | `tests/evaluation/planner_ablation/v2/test_resource_budget.py` |
| T-CX304 | `test_resource_budget.py`; `tests/agent/test_provider_telemetry.py` |
| T-CX305 | `test_resource_budget.py`; sealing resource validation |
| T-CX306 | `tests/agent/test_telemetry.py`; `test_provider_telemetry.py`; `test_real_llm_planner.py` |
| T-CX307 | `test_runtime_telemetry.py`; `test_telemetry.py`; adapter observer |
| T-CX308 | `test_runtime_telemetry.py` |
| T-CX309 | `test_provider_telemetry.py` (`test_retry_three_attempts_one_call`) |
| T-CX310 | `test_provider_telemetry.py` (`test_redirect_four_sends_one_sdk_attempt`) |
| T-CX311 | `test_provider_telemetry.py` (`test_lost_response_has_unknown_usage`) |
| T-CX312 | `test_resource_telemetry.py`; `test_provider_telemetry.py` |
| T-CX313 | `test_resource_telemetry.py`; campaign resource_stopped path |
| T-CX314 | adapter/campaign drain + observer isolation |
| T-CX315 | sealing/offline acceptance resource negative cases |
| T-CX316 | `test_resource_budget.py` |
| T-CX317 | `validate_resource_candidate` / sealing tests |
| T-CX318 | offline schedule paths; architecture whitelist includes `RESOURCE_BOUNDS.md` only |

### Full offline schedule paths

1. Existing 114-slot Scripted/fixed harness path — **unchanged**; product usage remains unknown; no resource-policy gate; zero real provider calls.
2. Resource-policy harness path (when enabled) — exact `RealLLMPlanner` + offline native MockTransport; audited SDK profile required; remains `harness_only` / non-scored; zero real provider calls.

No `protocol_seal/` under `study_s1_planner_ablation_dev_2`. Evidence docs: existing names plus `RESOURCE_BOUNDS.md` only.
