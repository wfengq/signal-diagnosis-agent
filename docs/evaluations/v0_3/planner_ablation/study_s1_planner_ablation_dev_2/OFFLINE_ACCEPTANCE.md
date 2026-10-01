# Offline acceptance: `study_s1_planner_ablation_dev_2`

**Status:** study-only offline acceptance complete for Task 7.  
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
| `design_inputs.md` review_status | `pending` |
| approved | `false` |
| implementer self-check | construction/gates consistency recorded in `design_inputs.md` |
| independent / operator review | **pending** — required before any seal |
| fabricated signoff | **none** |

Unresolved disagreement or pending independent review **blocks seal**. This offline acceptance does not expand into a new campaign.

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
| Independent label review + operator approval of `design_inputs.md` | seal candidate readiness |
| Seal grant on concrete candidate manifest, schedule, bands, budgets | creating `protocol_seal/` under this study root |
| Commit / push / merge authorization | publishing this offline diff |
| RealLLM grant with sealed identity + numerical request/token budget | any provider/network campaign |
| Separate product design + contracts + tests + operator auth | any product planner / composition change |

## Seal prerequisites (concrete checklist)

1. Independent offline reviewer records approval (or revises proposal) for all ten oracle rows, alias, U/C/G, targets — no threshold relaxation.
2. Resolve every `inspect_limits` blocker above; publish numerical worst-case request/token budget for 57 product slots.
3. Separate **seal grant** naming the concrete candidate manifest, schedule digest, decision bands, and budgets.
4. Separate **commit authorization** so the sealed implementation identity can bind an immutable commit.
5. Generate seal only into a **new** destination; never regenerate `dev_1`; never treat this offline acceptance as the seal.
6. Only after seal verify: separate **RealLLM grant** with exact seal digest and budget — still no product-composition change without its own grant.

## Candidate manifest description (unsealed)

A future seal candidate must bind: unique-request schedule + aliases; scenario/source/master relations; every mode oracle + offline label-review record; U/C/G membership; timing/lifecycle/order/repetitions/limits/decision bands; original WAV and canonical request hashes; immutable implementation commit and product/prompt/profile/corpus/study-code hashes; dependency/runtime versions; operator authorization references. Construction path: `verify_manifest` / `generate_seal` under a seal grant only.

---

Prepared under Task 7 offline implementation grant. Changes intentionally left **uncommitted**. No real seal created. No RealLLM run.
