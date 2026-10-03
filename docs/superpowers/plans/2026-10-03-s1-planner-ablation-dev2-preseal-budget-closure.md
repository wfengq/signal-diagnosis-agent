# Planner-ablation `dev_2` preseal budget closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce an honest preseal package for `study_s1_planner_ablation_dev_2` that records which source-aware resource-candidate blockers are closed and which remain blocked, so a later separate seal grant can bind a concrete candidate without inventing product caps or rewriting `dev_1`.

**Architecture:** Keep product constructors and public request path unchanged. Treat source-aware `assess_resource_budget` + `validate_resource_candidate` as the readiness authority for formal candidates. Keep legacy `inspect_limits` as diagnostics only (it remains hard-coded `seal_ready=False` and must not be retargeted by this plan). Bind study-only observation capability where it proves event completeness; keep planner/SDK/HTTP/token worst-case ceilings on independent admitted proofs. Leave formal `protocol_seal/` creation and RealLLM campaign to later grants.

**Tech Stack:** existing `evaluation/planner_ablation/v2` campaign/sealing/resource modules; optional study binding of `agent/telemetry.py` + `provider_telemetry.py`; pytest offline gates; unsealed evidence under `docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_2/`.

## Global Constraints

- Study id remains `study_s1_planner_ablation_dev_2`; scorer `signal_diag.planner_ablation_scoring` `2.0.0-dev.1`.
- Do not create `protocol_seal/` under the `dev_2` root in this plan.
- Do not run RealLLM study campaigns, provider `/models` probes, or warm-ups unless a later grant names them.
- Do not change `RealLLMPlanner` public product behavior, prompt, causal policy, DSP thresholds, or finish gates.
- Do not rewrite `study_s1_planner_ablation_dev_1` seal bytes or historical contextual baselines.
- Do not treat D039 `observed_facts` as a planner-ablation budget change; later seal candidates must bind the post-D039 product tree.
- Do not change legacy `inspect_limits` semantics or invent product explicit-flag overrides to appease it.
- Demonstration thresholds (1% clipping, 5% THD, 5% even-harmonic growth) remain demonstration values, not SLAs.
- Definitions precede implementation. Offline tests may use pytest temp dirs only.
- Commit, push, and merge are never auto-authorized by this plan; each wave needs an explicit commit/push grant when the operator wants those operations.

### Readiness authority

```text
Readiness authority:
本计划以 source-aware resource assessment 和 validate_resource_candidate
的完整候选校验为准。legacy inspect_limits 仅作诊断记录，保持原语义。

Evidence separation:
离线观测测试证明 capability 与事件完整性，不提供生产最坏预算上界。
planner、SDK、HTTP、token 上界分别需要独立适用的认证 proof。
预封阶段不要求先执行正式战役取得 ledger。

Honest completion:
本轮允许以部分阻断已闭合、其余仍 blocked 收口。
不得为完成计划而强制 seal_ready=true。

Authorization:
Tasks 1–3 为文档与定义；Tasks 4–6 实现另授。
commit/push/merge、seal、RealLLM 均不由本计划自动授权。
```

---

## Why this plan exists (OQ-019 / D038 status)

OQ-019 study-shape freeze (D038) and the `dev_2` protocol revision already landed offline harness, independent label approval, and default-off token/transport telemetry (PR #21). Path-C product `observed_facts` (D039 / PR #23) is on trunk tip `11d7dbe`.

`dev_1` Wave 5 did **not** accept formal dominance. The open engineering question remains: whether HEAD `RealLLMPlanner` earns its complexity versus truth-free `fixed_pipeline` under matched conditions.

Two readiness tracks exist and must stay separated:

1. **Legacy diagnostics.** `inspect_limits(snapshot_effective_configuration())` still reports `execution_blocked=true` and hard-codes `seal_ready=False`. On tip `11d7dbe` its blocker list remains:

```text
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

2. **Source-aware candidate path.** Formal resource candidates use `assess_resource_budget` proofs/capability and `validate_resource_candidate`. That path does **not** consult the legacy explicit-flag gate (`sealing.py`). Candidate `seal_ready` follows `validation.ready and not validation.fixture_only`.

Installed `openai` in the writing environment is `3.6.0` and matches `uv.lock`. Prior `RESOURCE_BOUNDS.md` recorded installed `3.20.0` vs lock `3.6.0`. Task 2 must re-bind the installed tuple **and** confirm supported profile, hook coverage, and capability/proof identity agreement.

This writing-plans document authorizes **plan text only**. It does not authorize Tasks 1–6 execution, commit/push, seal, or RealLLM.

## Current grant for this document

```text
授权 OQ-019/dev_2 预封预算闭合：按修订后计划 Tasks 1–3 文档与定义；
新增 observable 写入 additive CONTRACTS/TEST_PLAN；已有义务仅映射。
不改 legacy inspect_limits；不 seal；不 RealLLM；不改产品诊断门。
commit/push 另授。
```

---

## File map

| Path | Role |
|------|------|
| `docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_2/PRESEAL_BUDGET_STATUS.md` | Unsealed status board with **two tables**: legacy diagnostics vs source-aware candidate blockers |
| `docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_2/RESOURCE_BOUNDS.md` | Refresh installed SDK tuple, supported profile, hook coverage, residual blockers |
| `docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_2/OFFLINE_ACCEPTANCE.md` | Additive status note pointing at PRESEAL board; keep historical Task 7 record |
| `docs/CONTRACTS_V0_3_CONTEXTUAL.md` §21 / `docs/TEST_PLAN_V0_3_CONTEXTUAL.md` | **Required** for any new observable obligation; existing T-CX299 / T-CX303–318 may be mapped without new IDs |
| `src/signal_diag/evaluation/planner_ablation/v2/resource_budget.py` / `resource_*.py` / `sealing.py` | Only under Tasks 4–6 offline impl grant: candidate proofs/capability wiring |
| `src/signal_diag/evaluation/planner_ablation/v2/campaign.py` | Only under Tasks 4–6 if needed for study binding helpers; **do not** retarget legacy `inspect_limits` |
| `tests/evaluation/planner_ablation/v2/test_resource_budget.py` (+ focused peers) | Offline proofs that observation capability ≠ worst-case ceilings |

Out of scope files: product `composition.py` request caps, prompt files, DSP/rules, `dev_1` seal tree, UI/CLI product paths.

---

## Task 1: Preseal status board (docs)

**Deliverable:** `PRESEAL_BUDGET_STATUS.md`.

Clearance classes (use exactly these labels):

1. `bind_study_observation` — study observation capability / event-graph completeness when bound for the candidate.
2. `operator_accept_route` — needs operator acceptance of live model/route mapping (no product rewrite).
3. `admitted_independent_proof` — independent, applicable, authenticated proof for a named worst-case ceiling (planner turns, SDK attempts, HTTP sends, tokens, timeout).
4. `requires_product_cap_design` — cannot clear without a new product-behavior design + separate authorization.
5. `environment_rebind` — lockfile/install drift or unsupported profile; candidate must re-bind installed identity.

Steps:

- [x] Create `PRESEAL_BUDGET_STATUS.md` with two tables:
  - **Legacy diagnostics** (`inspect_limits` blockers). Column “affects formal candidate seal_ready?” is **no** for all rows unless a later design explicitly changes that policy.
  - **Source-aware candidate blockers** from `assess_resource_budget` / `validate_resource_candidate` (capability, proofs, HTTP factor, token ceilings, route acceptance, dependency identity).
- [x] For each source-aware blocker: class, evidence pointer, residual risk, closed/partial/blocked.
- [x] Record HEAD commit, `contextual_product_tree_sha256`, openai install vs `uv.lock`, and that D039 is on HEAD (not a budget mutation).
- [x] State honest completion: partial closure is allowed; never force candidate `seal_ready=true` to finish the plan.
- [x] Explicitly forbid treating green offline harness tests or a campaign ledger as worst-case budget proof.
- [x] Commit/push under separate docs commit grant for Tasks 1–3.

## Task 2: Re-audit installed SDK / transport tuple (docs)

**Deliverable:** refreshed facts in `RESOURCE_BOUNDS.md` (or an additive dated appendix).

Steps:

- [x] Hash the installed openai / `httpx` / `httpcore` identity that study observation can attach to.
- [x] Confirm the installed tuple yields a **supported** SDK profile under the same checks used by `assess_resource_budget` (supported flag, policy/schema match, hook coverage for planner turns / repairs / SDK attempts / HTTP sends / usage, and capability vs proof openai_version agreement).
- [x] Recording digests alone does **not** clear SDK gates; unsupported profile or incomplete hooks remain blockers.
- [x] Recompute whether admitted SDK default timeout/retry facts still match; keep non-override flags honest.
- [x] Leave `unproved_http_send_bound` and failed-attempt token exposure residual unless new independent proofs exist.
- [x] Do not call provider APIs.
- [x] Commit/push under separate docs commit grant.

## Task 3: Define observation vs bound-proof contracts (definitions)

**Deliverable:** additive CONTRACTS_V0_3 / TEST_PLAN_V0_3 text for any **new** observable. Existing obligations may be mapped to T-CX299 / T-CX303–318 without new IDs. Plan prose alone is **not** a substitute for new contract obligations.

Steps:

- [x] Specify that default product requests remain observation-off.
- [x] Specify that offline observation tests prove capability and event-graph integrity only.
- [x] Specify that planner-call, SDK-attempt, HTTP-send, and token worst-case ceilings each require independent admitted proofs; a closed per-run ledger does not prove future worst case.
- [x] Specify that preseal does **not** require executing a formal RealLLM campaign to obtain a ledger before seal.
- [x] Forbid mock SDK totals and approval booleans as substitutes for proofs/capability.
- [x] Draft additive contract/test IDs when new observables are introduced; stop for operator acceptance of those definitions before Tasks 4–6.
- [x] Commit/push under separate docs commit grant.

## Task 4: Offline implementation — observation capability binding

**Gate:** later grant naming Tasks 4–6 offline implementation **and** commit/push if artifacts should land.

Steps:

- [ ] Add failing tests: unbound / incomplete observation capability keeps source-aware blockers; bound capability clears only completeness-class blockers it truly proves.
- [ ] Implement the smallest study binding helpers needed for candidate validation.
- [ ] Keep public `build_product_service` unchanged.
- [ ] Do **not** modify legacy `inspect_limits` to return `seal_ready=True`.
- [ ] Run focused planner_ablation v2 resource/campaign/sealing tests.

## Task 5: Independent worst-case proofs (offline)

**Gate:** same offline impl grant as Task 4.

Steps:

- [ ] Wire or document independent proofs for planner-turn ceiling, SDK attempt factor, HTTP send factor, and timeout only when admissible evidence exists.
- [ ] Keep token input/output ceilings blocked unless an admitted all-outcome or per-send proof exists; otherwise classify as residual or `requires_product_cap_design`.
- [ ] Add tests that reject using a closed run ledger as a worst-case request/token ceiling.
- [ ] Do not invent product `max_tokens` / timeout overrides.

## Task 6: Operator route acceptance package (docs)

**Deliverable:** operator-facing package for live route binding.

Steps:

- [ ] Record `deepseek-v4-flash` + prompt `v0.3-s1-planner-9.11` + policy `v9_11_mode_aware_no_fault_recovery`.
- [ ] Mark provider/model mapping unaccepted until the operator accepts the live route binding in writing.
- [ ] Do not call `/models` unless a later grant allows a connectivity probe.

## Task 7: Closeout checklist for the *next* seal grant (no seal)

**Deliverable:** checklist in `PRESEAL_BUDGET_STATUS.md`.

The later seal grant must name at least:

- candidate manifest path and digest
- schedule digest (114 slots)
- decision bands
- source-aware resource proofs/capability that make `validate_resource_candidate` ready (not legacy `inspect_limits`)
- product_tree / implementation digests including post-D039 tip
- explicit new destination under `study_s1_planner_ablation_dev_2/protocol_seal/`

Steps:

- [ ] Write the checklist.
- [ ] State that RealLLM campaign requires a further grant after seal verify.
- [ ] Hand the package to independent review. Do not seal.

### Implementation-wave verification (Tasks 4–6, when granted)

Before claiming the offline impl wave complete:

- [ ] Focused planner_ablation v2 resource/budget/sealing tests pass.
- [ ] Full pytest with zero required skip/xfail.
- [ ] Ruff clean.
- [ ] `mypy src` clean.
- [ ] Architecture tests pass.
- [ ] `git diff --check` against the applicable baseline.

---

## Proposed next grants (operator chooses)

1. **Accept this revised writing-plans document**, then docs/definitions only:
   ```text
   授权 OQ-019/dev_2 预封预算闭合：按修订后计划 Tasks 1–3 文档与定义；
   新增 observable 写入 additive CONTRACTS/TEST_PLAN；已有义务仅映射。
   不改 legacy inspect_limits；不 seal；不 RealLLM；不改产品诊断门。
   commit/push 另授。
   ```
2. After definitions acceptance, offline implementation:
   ```text
   授权 OQ-019/dev_2 预封预算闭合 offline implementation：按计划 Tasks 4–6；
   观测默认关闭；不改 legacy inspect_limits；不 seal；不 RealLLM campaign。
   commit/push 另授。
   ```
3. Only when source-aware candidate validation can honestly be ready:
   ```text
   授权创建 study_s1_planner_ablation_dev_2 protocol_seal，命名候选
   manifest／schedule／bands／source-aware budgets；不 RealLLM。
   ```
4. Only after seal verify:
   ```text
   授权 RealLLM study campaign under sealed dev_2 identity + numerical budget；
   不改产品门。
   ```

---

## Verification (for this writing-plans revise PR)

- [ ] Plan text separates legacy diagnostics from source-aware candidate readiness.
- [ ] Plan text states observation/ledger ≠ worst-case ceilings; no campaign-before-seal requirement.
- [ ] Plan text requires supported SDK profile / hook / capability–proof identity checks in Task 2.
- [ ] Authorization stages are Tasks 1–3 docs/definitions, then separately granted Tasks 4–6 impl; commit/push/seal/RealLLM never auto-authorized.
- [ ] No `protocol_seal/` created; no product code changed in this revise wave.
