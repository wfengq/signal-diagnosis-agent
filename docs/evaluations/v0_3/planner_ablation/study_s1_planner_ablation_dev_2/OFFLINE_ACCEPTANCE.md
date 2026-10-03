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

## Preseal budget status (Tasks 1–3 docs / definitions)

Additive pointer only. Historical Task 7 / telemetry offline-acceptance text
above remains the harness record.

| Field | Value |
|-------|-------|
| Status board | `PRESEAL_BUDGET_STATUS.md` |
| SDK re-audit | `RESOURCE_BOUNDS.md` §7 (2026-10-03) |
| Contract | `CONTRACTS_V0_3_CONTEXTUAL.md` §21.9 |
| Test IDs | T-CX324–T-CX325 (new); T-CX299 / T-CX303–318 mapped for existing telemetry obligations |
| Readiness authority | source-aware `assess_resource_budget` / `validate_resource_candidate` |
| Legacy `inspect_limits` | diagnostics only; still `execution_blocked=true` / `seal_ready=false` |
| Installed `openai` vs lock | `3.6.0` / `3.6.0` (match) |
| Reviewed capability identity | `openai==3.6.0` (§7); audited profile **supported** on lock-aligned install |
| Formal candidate `seal_ready` | **false** (honest partial closure) |
| `protocol_seal/` | **absent** |
| RealLLM / product gates | **not** authorized by Tasks 1–3 |

Green offline harness and a closed ledger do **not** admit worst-case ceilings
and do **not** require a campaign before seal (§21.9).

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

**Status:** `offline_implementation_accepted` at tip
`d152489abd649cc29ae0cf386ad46f56bc8f5276` on
`cursor/s1-dev2-telemetry-impl-0d26` (PR #21). Codex re-review accepted the
offline Tasks 1–7 gate scope (event graph, proof/label binding, usage, BoundFact).
CI green on that tip (Python 3.11/3.12).

**Not** `resource_bounds_complete`. **Not** `candidate_verified`. **Not** a
protocol seal. **Not** RealLLM / online execution readiness. Honest external
blockers below remain open.

Historical revise notes under this heading keep the pending-revision trail that
led to the tip accept. The current status is this paragraph, not the older
`offline_implementation_pending_revision` lines.

This revise closes the confirmed P1 gaps without clearing external blockers:

- P1A. `reject_online_preflight` rejects `make_complete_budget_assessment` plus arbitrary seal/grant strings. Online mode and the resource-policy path refuse before `session_factory` when the policy, a non-blocked assessment, or a `VerifiedResourceAdmission` is missing. `legacy_fixture_seal` survives `generate_seal` → `verify_manifest` as `construction_path=legacy_fixture_seal`.
- P1B. `aggregate_resource_ledger` pairs `planner_turn`, `logical_call`, `sdk_attempt`, and `http_send`. Unpaired events and claimed closure that does not match the graph are blockers. Exact zero on an empty graph is accepted only when the caller passes `fixed_zero_use` (fixed-pipeline slots). An empty product ledger with exact 0 is blocked.
- P1C. A redirect without a `reviewed:` zero-use proof sets `exact_total_tokens` to null, keeps the usage subtotal and potential exposure, and sets `acceptance_blocked`.
- P1D. Bound-fact files must be `RESOURCE_BOUNDS.md`, `BUDGET_BOUNDS.md`, `LABEL_REVIEW.md`, `OFFLINE_ACCEPTANCE.md`, or `design_inputs.md` under this study. Anything else, including `docs/README.md`, is `proof_acceptance_inapplicable_file`. Non-fixture readiness binds the on-disk `LABEL_REVIEW.md`; `approved=True` on the caller object is not that binding. `MockTransport` and the fixture offline boundary stay `mock_native`. `validate_resource_candidate` takes optional `installed_sdk_identity` and does not import the SDK.
- P1E. `run_schedule` does not overwrite a slot digest. A mismatch with `{request_key}:{arm}:{round_index}` is `slot_digest_mismatch` and stops the resource path. Scoring requires that same digest, not uniqueness alone.
- P1F. `test_full_schedule_resource_path_is_harness_only` runs all 114 slots through exact `RealLLMPlanner`, `RecordingPlanner`, the real service, and `MockTransport`, with `allow_fixture_offline_boundary`. Hosts stay `example.test`. Provenance stays `harness_only`. A final-slot resource failure blocks `planner_advantage` and `fixed_pipeline_dominance`.
- P2. `ReportedUsage` rejects booleans and negative subdivisions before coercion. Transport observation wraps each transport object once. Resource `seal_ready` follows the resource assessment, not the legacy explicit-flag gate. Legacy `inspect_limits` stays blocked.

Honest external blockers remain open: HTTP/token bound admission, unaccepted provider
model mapping, lockfile↔install drift. Gates must not be loosened to clear them.

Observation defaults **off**. Public `RealLLMPlanner` constructors/payloads unchanged.
No commit/push/seal/RealLLM under this grant.

### P1C/P1E/P2 follow-up verification (this environment)

```text
$ python3 -m pytest tests/evaluation/planner_ablation/v2/test_resource_candidate.py \
    tests/evaluation/planner_ablation/v2/test_resource_telemetry.py \
    tests/evaluation/planner_ablation/v2/test_campaign.py \
    tests/evaluation/planner_ablation/v2/test_resource_budget.py \
    tests/evaluation/planner_ablation/v2/test_offline_acceptance.py \
    tests/app/test_planner_ablation_v2_adapter.py \
    tests/evaluation/planner_ablation/v2/test_sealing.py -q
77 passed

$ python3 -m ruff check src/signal_diag/evaluation/planner_ablation/v2/campaign.py \
    src/signal_diag/evaluation/planner_ablation/v2/sealing.py \
    src/signal_diag/evaluation/planner_ablation/v2/resource_telemetry.py \
    src/signal_diag/evaluation/planner_ablation/v2/resource_models.py \
    tests/evaluation/planner_ablation/v2/test_campaign.py \
    tests/evaluation/planner_ablation/v2/test_resource_candidate.py \
    tests/evaluation/planner_ablation/v2/test_resource_telemetry.py
All checks passed

$ python3 -m mypy --no-incremental src/signal_diag/evaluation/planner_ablation/v2/campaign.py \
    src/signal_diag/evaluation/planner_ablation/v2/sealing.py \
    src/signal_diag/evaluation/planner_ablation/v2/resource_telemetry.py \
    src/signal_diag/evaluation/planner_ablation/v2/resource_models.py
Success: no issues found in 4 source files

$ git diff --check origin/cursor/s1-dev2-telemetry-impl-0d26...HEAD
(exit 0)
```

Still `offline_implementation_pending_revision`. Codex recheck is still required.

### Codex P1/P2 revise verification (this environment, openai 3.20.0)

```text
$ python3 -m pytest tests/evaluation/planner_ablation/v2 \
    tests/app/test_planner_ablation_v2_adapter.py \
    tests/agent/test_provider_telemetry.py \
    tests/agent/test_telemetry.py \
    tests/agent/test_runtime_telemetry.py -q
158 passed in 48.61s

$ python3 -m ruff check src/signal_diag/evaluation/planner_ablation/v2 \
    src/signal_diag/agent/provider_telemetry.py \
    src/signal_diag/app/planner_ablation_v2_adapter.py \
    tests/evaluation/planner_ablation/v2 \
    tests/agent/test_provider_telemetry.py
All checks passed

$ python3 -m mypy --no-incremental \
    src/signal_diag/evaluation/planner_ablation/v2/campaign.py \
    src/signal_diag/evaluation/planner_ablation/v2/sealing.py \
    src/signal_diag/evaluation/planner_ablation/v2/resource_telemetry.py \
    src/signal_diag/evaluation/planner_ablation/v2/resource_models.py \
    src/signal_diag/evaluation/planner_ablation/v2/resource_budget.py \
    src/signal_diag/evaluation/planner_ablation/v2/scoring.py \
    src/signal_diag/agent/provider_telemetry.py \
    src/signal_diag/app/planner_ablation_v2_adapter.py
Success: no issues found in 8 source files

$ git diff --check f590efc...HEAD
(exit 0)
```

Still `offline_implementation_pending_revision`. No seal. No live provider call.

### Revision verification (this environment)

```text
$ export PATH="/home/ubuntu/.local/bin:$PATH"
$ PYTHONPATH=/tmp/openai322pkg:$PYTHONPATH python3 -c "import openai; print(openai.__version__)"
3.22.1
$ PYTHONPATH=/tmp/openai322pkg:$PYTHONPATH python3 -m pytest tests/agent/test_provider_telemetry.py -q
12 passed

$ python3 -m pytest tests/agent/test_provider_telemetry.py \
    tests/evaluation/planner_ablation/v2/test_resource_telemetry.py \
    tests/evaluation/planner_ablation/v2/test_resource_candidate.py \
    tests/evaluation/planner_ablation/v2/test_offline_acceptance.py \
    tests/evaluation/planner_ablation/v2/test_campaign.py \
    tests/app/test_planner_ablation_v2_adapter.py -q
75 passed

$ git diff --check
(exit 0)
```

Installed observation profile here: lock-aligned `openai==3.6.0` matches reviewed
`RESOURCE_BOUNDS.md` §7 digests (`build_audited_sdk_observation_profile().supported`
is **true** on this tuple). CI may resolve `openai>=1.0` outside `3.6.0`; audited
support then latches unsupported. Offline MockTransport tests attach via
`build_fixture_sdk_observation_profile()` plus `allow_fixture_offline_boundary=True`
and never claim canonical SDK on mock transports.

### Remaining seal / budget blockers (honest)

| Blocker | Status |
|---------|--------|
| `unproved_http_send_bound` | open — no admitted HTTP factor `H` |
| `unproven_failed_attempt_token_bound` | open — context capacity ≠ failed-attempt exposure |
| `unknown_input_token_bound` / `unknown_output_token_bound` | open |
| `unaccepted_provider_model_mapping` | open — legacy `deepseek-v4-flash` route unaccepted |
| Lockfile `openai==3.6.0` vs installed | **cleared** on lock-aligned `3.6.0` (SDK rebind grant) |
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
| T-CX318 | offline schedule paths; architecture whitelist includes `RESOURCE_BOUNDS.md`, `PRESEAL_BUDGET_STATUS.md` |

### Full offline schedule paths

1. Existing 114-slot Scripted/fixed harness path — **unchanged**; product usage remains unknown; no resource-policy gate; zero real provider calls.
2. Resource-policy harness path — exact `RealLLMPlanner` wrapped by
   `RecordingPlanner`, real service, `MockTransport` on `example.test`, all 114
   slots attempted. Provenance stays `harness_only`. The fixture offline boundary
   is not an audited production profile and is not a scored conclusion.

No `protocol_seal/` under `study_s1_planner_ablation_dev_2`. Evidence docs: existing
whitelist names plus `RESOURCE_BOUNDS.md` and `PRESEAL_BUDGET_STATUS.md` (status board).

## Codex revise round 2 (superseded by tip accept)

**Historical status at this revise:** `offline_implementation_pending_revision`.
Superseded by `offline_implementation_accepted` at tip `d152489` (see status
under Tasks 2–7). Still no seal. Still no RealLLM. Still no live provider call.

This round keeps online execution refused. `reject_online_preflight` always raises `online_path_not_authorized_in_offline_scope`. A constructed `VerifiedResourceAdmission`, a synthetic budget, and strings such as `not-a-verified-seal` do not open `run_schedule(execution_mode="online")`. `make_verified_resource_admission` is the only producer and does not return an admission under this grant.

Event graphs now require a unique `sequence_id`, a start before its end, an `http_send.attempt_id` that matches an `sdk_attempt`, an `sdk_attempt.call_id` that matches a `logical_call`, and usage that cites an `http_send`. A `zero_use_proof` string, including a `reviewed:` prefix, does not make a redirect exact. Reviewed zero-use proof is not a product path yet.

Numeric bound facts, capability `offline_evidence_reference`, and provider `source_reference` may cite only `RESOURCE_BOUNDS.md` or `BUDGET_BOUNDS.md`. `LABEL_REVIEW.md` is the label-review binding. Non-fixture label review also requires the on-disk file to contain `approved=true`. Caller `approved=True` does not replace that marker.

`build_candidate_manifest`, `generate_seal`, and `verify_manifest` take optional `installed_sdk_identity`. `read_installed_sdk_identity()` in `app/sdk_identity.py` collects it. Evaluation still does not import the SDK. Profile attach compares `native_http_family`, `native_http_version`, `httpcore_version`, `source_file_digests`, `max_retries_default`, and `sdk_attempts_per_call`. Campaign totals compare summed `logical_call_count` with `logical_call_ceiling`.

The 114-slot harness stays on the fixture offline boundary because its transport is `MockTransport`. When the installed profile is the reviewed one, a non-mock client can attach as `canonical_sdk` without that boundary.
