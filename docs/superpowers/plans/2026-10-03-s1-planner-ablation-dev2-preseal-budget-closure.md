# Planner-ablation `dev_2` preseal budget closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clear the remaining `inspect_limits` / resource-budget blockers that keep `study_s1_planner_ablation_dev_2` at `seal_ready=false`, so a later separate seal grant can bind a concrete candidate without inventing product caps or rewriting `dev_1`.

**Architecture:** Keep product constructors and public request path unchanged. Bind study-only observation (already landed under D038 telemetry) and admitted bound proofs into the seal-candidate path. Prefer proof-from-observation and operator-accepted route bindings over new product runtime limits. Leave formal `protocol_seal/` creation and RealLLM campaign to later grants.

**Tech Stack:** existing `evaluation/planner_ablation/v2` campaign/sealing/resource modules; optional study binding of `agent/telemetry.py` + `provider_telemetry.py`; pytest offline gates; unsealed evidence under `docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_2/`.

## Global Constraints

- Study id remains `study_s1_planner_ablation_dev_2`; scorer `signal_diag.planner_ablation_scoring` `2.0.0-dev.1`.
- Do not create `protocol_seal/` under the `dev_2` root in this plan.
- Do not run RealLLM study campaigns, provider `/models` probes, or warm-ups unless a later grant names them.
- Do not change `RealLLMPlanner` public product behavior, prompt, causal policy, DSP thresholds, or finish gates.
- Do not rewrite `study_s1_planner_ablation_dev_1` seal bytes or historical contextual baselines.
- Do not treat D039 `observed_facts` as a planner-ablation budget change; seal candidates must bind the post-D039 product tree when generated later.
- Demonstration thresholds (1% clipping, 5% THD, 5% even-harmonic growth) remain demonstration values, not SLAs.
- Definitions precede implementation inside each task. Offline tests may use pytest temp dirs only.

---

## Why this plan exists (OQ-019 / D038 status)

OQ-019 study-shape freeze (D038) and the `dev_2` protocol revision already landed offline harness, independent label approval, and default-off token/transport telemetry (PR #21). Path-C product `observed_facts` (D039 / PR #23) is on trunk tip `11d7dbe`.

`dev_1` Wave 5 did **not** accept formal dominance. The open engineering question remains: whether HEAD `RealLLMPlanner` earns its complexity versus truth-free `fixed_pipeline` under matched conditions.

On trunk tip `11d7dbe` (this plan's writing day), a fresh offline probe still reports:

```text
execution_blocked = true
seal_ready = false
blockers =
  unknown_max_tokens_bound
  unknown_provider_request_timeout
  unknown_transport_attempts_per_call_bound
  unavailable_retry_telemetry
  unknown_planner_calls_per_slot_bound
  agent_limits_do_not_prove_planner_call_bound:tool_count_is_not_planner_calls
  unknown_input_token_bound
  unknown_output_token_bound
  unknown_provider_sdk_identity
  worst_case_requests_uncomputable
```

Installed `openai` in the writing environment is `3.6.0` and matches `uv.lock`. Prior `RESOURCE_BOUNDS.md` recorded installed `3.20.0` vs lock `3.6.0`; Task 1 must re-bind the installed tuple before any seal candidate.

This plan does **not** authorize seal creation or RealLLM. It authorizes only documentation acceptance first, then a later offline implementation grant for Tasks 2–6 when the operator issues one.

## Current grant for this document

```text
授权 OQ-019 / study_s1_planner_ablation_dev_2 预封预算闭合 writing-plans only。
不 seal、不 RealLLM campaign、不改产品诊断门、不 commit 实现代码，除非后续另授。
```

---

## File map

| Path | Role |
|------|------|
| `docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_2/PRESEAL_BUDGET_STATUS.md` | Unsealed status board: blocker → evidence → clearance path |
| `docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_2/RESOURCE_BOUNDS.md` | Refresh installed SDK tuple and residual blockers after HEAD re-audit |
| `docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_2/OFFLINE_ACCEPTANCE.md` | Additive status note pointing at PRESEAL board; keep historical Task 7 record |
| `src/signal_diag/evaluation/planner_ablation/v2/campaign.py` | Only if later impl grant: bind observation-derived facts into `inspect_limits` / resource assessment without inventing product caps |
| `src/signal_diag/evaluation/planner_ablation/v2/resource_*.py` / `sealing.py` | Only if later impl grant: candidate proofs for admitted bounds |
| `tests/evaluation/planner_ablation/v2/test_resource_budget.py` (+ focused peers) | Offline clearance proofs; fail closed when observation unbound |
| `docs/CONTRACTS_V0_3_CONTEXTUAL.md` §21 / `docs/TEST_PLAN_V0_3_CONTEXTUAL.md` | Additive IDs only if a later definitions grant requires new observable obligations |

Out of scope files: product `composition.py` request caps, prompt files, DSP/rules, `dev_1` seal tree, UI/CLI product paths.

---

## Task 1: Preseal status board (docs only)

**Deliverable:** `PRESEAL_BUDGET_STATUS.md` that maps every current blocker to one clearance class.

Clearance classes (use exactly these labels):

1. `bind_study_observation` — already-landed telemetry can prove the fact when bound for the study candidate.
2. `operator_accept_route` — needs operator acceptance of live model/route mapping (no product rewrite).
3. `admitted_sdk_default_audit` — may use re-audited installed SDK defaults with explicit non-override flags.
4. `requires_product_cap_design` — cannot clear without a new product-behavior design + separate authorization (stop and open OQ/design; do not invent caps here).
5. `environment_rebind` — lockfile/install drift; seal candidate must re-hash installed tuple.

Steps:

- [ ] Create `PRESEAL_BUDGET_STATUS.md` under the `dev_2` study root with columns: blocker, class, evidence pointer, residual risk, clears `seal_ready` contribution (yes/no/partial).
- [ ] Record HEAD commit, `contextual_product_tree_sha256` tip (`4b7a5916…` at plan writing on `11d7dbe`), openai install vs `uv.lock`, and the fresh `inspect_limits` blocker list above.
- [ ] State that D039 is on HEAD and any later seal must bind that product tree; D039 is not a budget mutation.
- [ ] Explicitly forbid treating green offline harness tests as seal readiness.
- [ ] Commit docs only.

## Task 2: Re-audit installed SDK / transport tuple

**Deliverable:** refreshed facts in `RESOURCE_BOUNDS.md` (or an additive appendix section dated for this plan) for the writing/execution environment.

Steps:

- [ ] Hash the installed openai/`httpx`/`httpcore` identity that study observation can actually attach to.
- [ ] Recompute whether `DEFAULT_MAX_RETRIES` / timeout defaults still match the admitted audit table.
- [ ] Mark `unknown_provider_sdk_identity` clearance as `environment_rebind` once digests are recorded.
- [ ] Leave `unproved_http_send_bound` and failed-attempt token exposure as residual unless new admitted proofs exist.
- [ ] Do not call provider APIs.
- [ ] Commit docs only under the writing-plans grant; code changes wait for the offline impl grant.

## Task 3: Define observation-binding contract for seal candidates (definitions)

**Deliverable:** additive contract/test definitions (or a definitions subsection in this plan accepted by operator) stating when study observation may clear `unavailable_retry_telemetry` and planner-call/transport unknowns.

Steps:

- [ ] Specify that default product requests remain observation-off.
- [ ] Specify that a seal candidate / offline verified study may require a bound telemetry profile whose ledger closes before `seal_ready` can flip.
- [ ] Forbid mock SDK totals and approval booleans as substitutes for bound observation.
- [ ] Register new T-CX IDs only if CONTRACTS/TEST_PLAN need new observables; otherwise map to existing T-CX299/T-CX303–318 obligations.
- [ ] Stop for operator acceptance of these definitions before implementation.

## Task 4: Offline implementation — bind observation into budget assessment

**Gate:** requires a later grant naming Tasks 4–6 offline implementation.

Steps:

- [ ] Add failing tests: unbound observation keeps `unavailable_retry_telemetry` and related blockers; bound closed ledger clears only the blockers it truly proves.
- [ ] Implement the smallest binding in v2 campaign/resource/sealing helpers.
- [ ] Keep public `build_product_service` and default planner construction unchanged.
- [ ] Prove `worst_case_requests_uncomputable` clears only when planner-call and transport attempt bounds are both admitted.
- [ ] Run focused planner_ablation v2 resource/campaign/sealing tests.

## Task 5: Token bound honesty

**Gate:** same offline impl grant as Task 4.

Steps:

- [ ] Keep `unknown_input_token_bound` / `unknown_output_token_bound` blocked unless an admitted all-outcome or per-send proof exists.
- [ ] If no honest proof exists, document them as `requires_product_cap_design` or residual `admitted_sdk_default_audit` gaps; do not invent max_tokens in product settings.
- [ ] Add tests that reject fake token ceilings.

## Task 6: Operator route acceptance package (docs)

**Deliverable:** a short operator-facing package listing the exact model route string, prompt/causal identity, and whether the declared DeepSeek flash mapping is accepted for seal binding.

Steps:

- [ ] Record `deepseek-v4-flash` + prompt `v0.3-s1-planner-9.11` + policy `v9_11_mode_aware_no_fault_recovery` as the identity under test.
- [ ] Mark `unaccepted_provider_model_mapping` until the operator accepts the live route binding in writing.
- [ ] Do not call `/models` unless a later grant allows a connectivity probe.

## Task 7: Closeout checklist for the *next* seal grant (no seal)

**Deliverable:** checklist in `PRESEAL_BUDGET_STATUS.md` that a seal grant must name.

The seal grant (separate) must name at least:

- candidate manifest path and digest
- schedule digest (114 slots)
- decision bands
- resource/budget proofs that yield `seal_ready=true`
- product_tree / implementation digests including post-D039 tip
- explicit destination under `study_s1_planner_ablation_dev_2/protocol_seal/` (new only)

Steps:

- [ ] Write the checklist.
- [ ] State that RealLLM campaign requires a further grant after seal verify.
- [ ] Hand the package to independent review (Codex or equivalent). Do not seal.

---

## Proposed next grants (operator chooses)

1. **Accept this writing-plans document**, then:
   ```text
   授权 OQ-019/dev_2 预封预算闭合：按本计划 Tasks 1–3 文档与定义；不 seal、不 RealLLM、不改产品诊断门。
   ```
2. After definitions acceptance:
   ```text
   授权 OQ-019/dev_2 预封预算闭合 offline implementation：按本计划 Tasks 4–6；观测默认关闭；不 seal、不 RealLLM campaign。
   ```
3. Only when `seal_ready` can be honestly true:
   ```text
   授权创建 study_s1_planner_ablation_dev_2 protocol_seal，命名候选 manifest／schedule／bands／budgets；不 RealLLM。
   ```
4. Only after seal verify:
   ```text
   授权 RealLLM study campaign under sealed dev_2 identity + numerical budget；不改产品门。
   ```

---

## Verification (for this writing-plans PR)

- [ ] Plan exists under `docs/superpowers/plans/`.
- [ ] No `protocol_seal/` created for `dev_2`.
- [ ] No product code changed in the writing-plans-only wave.
- [ ] Fresh `inspect_limits` probe recorded as still blocked (honest baseline).
- [ ] Independent review invited before any offline impl grant.
