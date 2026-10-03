# Preseal budget status: `study_s1_planner_ablation_dev_2`

**Status:** partial preseal (Tasks 1–6 offline impl + SDK rebind + D041 residual
gates). Not a protocol seal.
**Readiness authority:** source-aware `assess_resource_budget` +
`validate_resource_candidate`. Legacy `inspect_limits` is diagnostics only.
**Honest completion:** Token ceilings and failed-attempt exposure remain
`blocked`. Operator route acceptance is **closed** (D041). HTTP send factor
`H` redirect admission is **partial** — arithmetic may use admitted `H=21`;
auth / lower-transport applicability is incomplete (§21.3). This board does
**not** force candidate `seal_ready=true`.
**Not authorized here:** `protocol_seal/`, RealLLM campaign, product
diagnosis-gate changes, legacy `inspect_limits` retargeting.

Companion docs: `RESOURCE_BOUNDS.md` §7 (current reviewed identity),
`BUDGET_BOUNDS.md` (legacy path), `OFFLINE_ACCEPTANCE.md`,
`CONTRACTS_V0_3_CONTEXTUAL.md` §21.9 / T-CX324–T-CX325, `docs/DECISIONS.md`
D041.

## Identity snapshot (this writing environment)

| Fact | Value |
|------|-------|
| Writing branch | `cursor/oq019-dev2-residual-gates-8b52` |
| Trunk tip referenced | `0b2cc5d` |
| `contextual_product_tree_sha256()` | `8d35581d9a5217e66ce9734687a533ef72df9a0e597f340ffd4bd57cce8058d0` (post D040 rebind) |
| Installed `openai` | `3.6.0` (`importlib.metadata` via `uv run`) |
| `uv.lock` `openai` | `3.6.0` (matches installed) |
| Reviewed capability identity | `openai==3.6.0` (`provider_telemetry` / `RESOURCE_BOUNDS.md` §7) |
| Audited profile `supported` | **true** (lock-aligned digests + hooks identity) |
| D039 on HEAD lineage | yes; not a planner-ablation budget mutation |
| D041 residual gates | route accepted + `H=21` admitted (study proofs only) |

## Clearance classes

Use exactly these labels on source-aware rows:

1. `bind_study_observation`
2. `operator_accept_route`
3. `admitted_independent_proof`
4. `requires_product_cap_design`
5. `environment_rebind`

## Table A — Legacy diagnostics (`inspect_limits`)

Probe: `inspect_limits(snapshot_effective_configuration())` on this environment.
Result: `execution_blocked=true`, hard-coded `seal_ready=false`.

| Blocker | Affects formal candidate `seal_ready`? | Notes |
|---------|----------------------------------------|-------|
| `unknown_max_tokens_bound` | **no** | Legacy explicit-flag path only |
| `unknown_provider_request_timeout` | **no** | Same |
| `unknown_transport_attempts_per_call_bound` | **no** | Same |
| `unavailable_retry_telemetry` | **no** | Same; observation binding is source-aware |
| `unknown_planner_calls_per_slot_bound` | **no** | Same |
| `agent_limits_do_not_prove_planner_call_bound:tool_count_is_not_planner_calls` | **no** | Same |
| `unknown_input_token_bound` | **no** | Same |
| `unknown_output_token_bound` | **no** | Same |
| `unknown_provider_sdk_identity` | **no** | Same |
| `worst_case_requests_uncomputable` | **no** | Same |

This plan wave does **not** change `inspect_limits` semantics or invent product
explicit-flag overrides to clear this table.

## Table B — Source-aware candidate blockers

Authority: `assess_resource_budget` proofs/capability and
`validate_resource_candidate` (`sealing.py` does not consult the legacy
explicit-flag gate). Candidate readiness is
`validation.ready and not validation.fixture_only`.

| Blocker / residual | Class | Status | Evidence | Residual risk |
|--------------------|-------|--------|----------|---------------|
| Reviewed SDK profile on lock-aligned `3.6.0` (digests/hooks identity) | `environment_rebind` | **closed** (partial wave) | `RESOURCE_BOUNDS.md` §7; `build_audited_sdk_observation_profile().supported is True` when install matches; `pyproject` llm extra pins `openai==3.6.0` | Foreign installs / digest drift still latch unsupported |
| Missing / incomplete production observation capability (turns, repairs, SDK attempts, HTTP sends, usage) | `bind_study_observation` | **partial** | `resource_capability.bind_observation_capability` (Tasks 4–6); offline harness T-CX306–315; production non-fixture bind still required | Helper maps installed/agent profile; offline green ≠ production capability bind |
| `unproved_http_send_bound` (factor `H`) | `admitted_independent_proof` | **partial** (D041) | `RESOURCE_BOUNDS.md` §3; admitted redirect `H=21` (`sdk_default_audit`, scope `admitted`, `openai==3.6.0`; httpx `0.28.1` in applicable_path prose) | Auth replay / lower-transport paths beyond redirect chain still unbounded; not seal-cleared |
| `unknown_input_token_bound` / `unknown_output_token_bound` / failed-attempt token exposure | `admitted_independent_proof` or `requires_product_cap_design` | **blocked** | `RESOURCE_BOUNDS.md` §4–5 | Context-window capacity ≠ failed-attempt exposure; no all-outcome proof |
| `request_timeout` unknown as admitted product-bound fact | `admitted_independent_proof` | **blocked** | SDK default timeout audited; must not flip `request_timeout_explicit` | Legacy path still unknown; source-aware needs admitted applicable proof |
| Planner-turn ceiling `P=28` / SDK attempt factor `A=3` (conditional arithmetic) | `admitted_independent_proof` | **partial** | Control-flow / SDK-default audits in `RESOURCE_BOUNDS.md` | Conditional; invalidated by uncovered continue paths |
| `unaccepted_provider_model_mapping` (`deepseek-v4-flash` live route) | `operator_accept_route` | **closed** (D041) | `docs/DECISIONS.md` D041; **Operator route package** below | Product strings unchanged; acceptance is study binding only |
| Closed per-run ledger / offline schedule totals as worst-case ceiling | *(forbidden substitute)* | **blocked** (must not clear) | §21.9 / T-CX324 | Observation integrity ≠ future worst-case requests/tokens |

## Evidence separation (normative pointer)

Offline observation tests prove capability and event-graph integrity only.
They do **not** provide production worst-case request or token ceilings.
Planner-turn, SDK-attempt, HTTP-send, and token ceilings each need independent,
applicable, authenticated proofs. Preseal does **not** require executing a
formal RealLLM campaign to obtain a ledger before seal (§21.9 / T-CX324–325).

Green offline harness tests and a closed campaign ledger are **forbidden** as
sole worst-case budget proof.

## Operator route acceptance package (Task 6)

**Operator written acceptance recorded (D041, 2026-10-03).** No `/models` probe
in this wave.

| Binding | Value | Accepted |
|---------|-------|----------|
| Requested / product model string | `deepseek-v4-flash` | n/a (product unchanged) |
| Planner prompt identity | `v0.3-s1-planner-9.11` | study pin matches HEAD wiring |
| Causal policy | `v9_11_mode_aware_no_fault_recovery` | study pin matches HEAD wiring |
| Declared provider route vs requested name | V4.1-Flash legacy mapping (`deepseek-v4.1-flash`) per `RESOURCE_BOUNDS.md` §4 | **yes** (`model_mapping_accepted=true` on study binding) |
| Provider/model mapping for seal | D041 + this table | **accepted** for study `ProviderLimitsBinding` |

## Mapping to existing T-CX obligations

| Topic | IDs (existing unless noted) |
|-------|-----------------------------|
| Actual resource telemetry vs ceiling-only | T-CX299, T-CX303, T-CX316 |
| SDK/native identity and drift | T-CX304 |
| Model mapping acceptance | T-CX305 |
| Default-off observation; on/off behavior | T-CX306 |
| Turns/repairs/attempts/sends/usage graph | T-CX307–T-CX315 |
| Candidate/proof/code/dependency binding | T-CX317 |
| Offline schedule; no live calls; preservation | T-CX318 |
| Observation ≠ worst-case; no campaign-before-seal; PRESEAL board | **T-CX324**, **T-CX325** (additive §21.9) |

## Checklist for a *later* seal grant (no seal in this wave)

A future seal grant must name at least:

- [ ] candidate manifest path and digest
- [ ] schedule digest (114 slots)
- [ ] decision bands
- [ ] source-aware resource proofs/capability that make `validate_resource_candidate` ready (**not** legacy `inspect_limits`)
- [ ] product_tree / implementation digests including post-D039 tip
- [ ] explicit new destination under `study_s1_planner_ablation_dev_2/protocol_seal/`
- [ ] admitted all-outcome or per-send token ceilings (still absent after D041)

RealLLM campaign requires a further grant after seal verify.

## Honest readiness statement

Closed in SDK rebind wave: reviewed capability identity rebound to lock-aligned
`openai==3.6.0`; `build_audited_sdk_observation_profile().supported=true` on
matching installs; lockfile↔install drift cleared for `openai` here.

D041 residual gates wave: redirect-chain `H=21` is **admitted** for conditional
arithmetic when study proofs bind the fact (`assess_resource_budget`); total
HTTP factor applicability stays **partial** on this board until auth /
lower-transport write-up is complete — do not claim `unproved_http_send_bound`
fully cleared for seal. Operator route acceptance clears
`unaccepted_provider_model_mapping` on study `ProviderLimitsBinding`.
Conditional `http_send_ceiling=100548` is derivable from `RESOURCE_BOUNDS.md`
§3 when redirect proofs bind; seal still blocked on tokens and partial `H`.

Still blocked for formal candidate `seal_ready`: input/output token ceilings,
failed-attempt token exposure, production non-fixture observation bind, and
remaining `admitted_independent_proof` rows above. Partial closure is the
intended honest outcome. Do not force `seal_ready=true` to finish the plan.
