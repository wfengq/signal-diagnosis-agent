# Budget bounds audit: `study_s1_planner_ablation_dev_2`

**Scope:** Task 5 `inspect_limits` preseal readiness — offline source/SDK audit only.  
**Not a protocol seal.** No `protocol_seal/` created.  
**Not a RealLLM grant.** No provider/network calls. No product planner/composition patches.  
**Explicit:** green offline tests ≠ live-run readiness; no RealLLM grant implied.

Audit environment (this workspace, 2026-10-01):

| Fact | Value |
|------|-------|
| Branch | `cursor/s1-dev2-label-budget-0d26` |
| Installed `openai` | `3.20.0` (`importlib.metadata`) |
| `uv.lock` `openai` | `3.6.0` (differs from installed) |
| `pyproject.toml` LLM extra | `openai>=1.0` (no exact pin) |
| Separate DeepSeek SDK | **none** — product uses OpenAI-compatible `AsyncOpenAI` |

---

## 1. Audited source facts

### 1.1 `inspect_limits` / `EffectiveConfiguration`

- Defaults snapshot leaves request/token/transport fields unknown; AgentLimits merge defaults alone do not prove request/token bounds:

```131:231:src/signal_diag/evaluation/planner_ablation/v2/campaign.py
def inspect_limits(config: EffectiveConfiguration) -> BudgetAssessment:
    """Audit AgentLimits/transport facts and emit explicit unknown-bound blockers.
    ...
    no explicit max_tokens/timeout/retry override) do **not** prove an effective
    request or token bound. Missing production limits remain seal/execution blockers.
    """
    ...
    if not config.max_tokens_explicit or config.max_tokens is None:
        blockers.append("unknown_max_tokens_bound")
    if not config.request_timeout_explicit or config.request_timeout_s is None:
        blockers.append("unknown_provider_request_timeout")
    if (
        not config.transport_retry_override_explicit
        or config.transport_attempts_per_call_bound is None
    ):
        blockers.append("unknown_transport_attempts_per_call_bound")
    if not config.retry_telemetry_available:
        blockers.append("unavailable_retry_telemetry")
    if config.planner_calls_per_slot_bound is None:
        blockers.append("unknown_planner_calls_per_slot_bound")
        blockers.append(
            "agent_limits_do_not_prove_planner_call_bound:"
            "tool_count_is_not_planner_calls"
        )
    ...
        else:
            worst_case_requests = (
                PRODUCT_SLOT_COUNT_V2 * planner_bound * transport_bound
            )
    ...
        seal_ready=False,
```

- Product slot count is fixed at 57 (`PRODUCT_SLOT_COUNT_V2` in `models.py`).
- Study resource telemetry deliberately leaves planner/transport/token counts unknown:

```234:251:src/signal_diag/evaluation/planner_ablation/v2/campaign.py
def collect_resource_telemetry(terminal: StudyTerminal) -> ResourceTelemetry:
    ...
    unknown: list[str] = [
        "planner_call_count",
        "repair_attempt_count",
        "transport_attempt_count",
        "input_tokens",
        "output_tokens",
        "total_tokens",
    ]
    return ResourceTelemetry(
        planner_call_count=None,
        ...
        transport_attempt_count=None,
```

### 1.2 `AgentLimits` defaults (product runtime)

```15:22:src/signal_diag/agent/policies.py
class AgentLimits(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_tool_calls: int = Field(default=8, ge=1)
    max_planner_retries: int = Field(default=2, ge=0)
    max_no_progress: int = Field(default=2, ge=1)
    max_rule_evaluations: int = Field(default=4, ge=0)
    max_knowledge_retrievals: int = Field(default=4, ge=0)
```

`DistortionDiagnosisRuntime` defaults to these limits (`runtime.py` `_DEFAULT_LIMITS = AgentLimits()`, ctor `limits: AgentLimits = _DEFAULT_LIMITS`).  
`DiagnosisApplicationService` constructs the runtime **without** overriding `limits` (e.g. `service.py` ~373–381 and ~540–548), so product path uses defaults.

Audited AgentLimits defaults match `AUDITED_AGENT_LIMIT_DEFAULTS` (tool=8, planner_retries=2, no_progress=2, rules=4, knowledge=4). These are **not** a planner-call bound by themselves (tool count ≠ planner calls).

### 1.3 Runtime control flow (planner calls)

Main loop: each iteration calls `await self._planner.decide(context)` once (`runtime.py` ~171–179), then dispatches:

| Path | Effect on budgets | Lines (approx.) |
|------|-------------------|-----------------|
| `PlannerOutputError` | consumes planner retry; terminate at 0 | 180–190 |
| `CallToolDecision` success/error | increments `tool_call_count`; success resets no-progress; error/equivalent increments no-progress | 379–482, 847 |
| tool budget exhausted | terminate `max_tool_calls` | 426–428 |
| `EvaluateRulesDecision` under v9_11 | always `_reject_decision` (retry consume) | 522–538 |
| `RetrieveKnowledgeDecision` | increments knowledge count / no-progress / terminate | 608–673 |
| `FinishDecision` validation failure | retry consume | 711–738 |
| successful finish | terminate | 740–758 |

Product composition pins causal policy `v9_11_mode_aware_no_fault_recovery` (`composition.py` ~102). Under that policy, manual `evaluate_rules` cannot open an unbounded progress path.

`planner_attempt_count` is initialized to `0` in `_initial_state` and is **never incremented** — there is no separate hard `max_planner_attempts` field. Finiteness must come from the budgets above.

### 1.4 Product planner client construction

```430:485:src/signal_diag/agent/planner.py
        response = await client.chat.completions.create(
            model=model,
            messages=[...],
            response_format=_deepseek_response_format(),
            temperature=0.0,
            extra_body={"thinking": {"type": "disabled"}},
        )
...
def _create_async_openai_client(*, api_key: str, base_url: str) -> _ChatClient:
    ...
    return AsyncOpenAI(api_key=api_key, base_url=base_url)
```

Observed product call facts:

| Setting | Product value |
|---------|---------------|
| `temperature` | `0.0` (explicit) |
| `thinking` | `{"type": "disabled"}` via `extra_body` |
| `max_tokens` / `max_completion_tokens` | **omitted** |
| client `timeout` | **not passed** → SDK default |
| client `max_retries` | **not passed** → SDK default |

No connectivity test was performed.

### 1.5 Pinned installed OpenAI SDK (offline)

Installed package `openai==3.20.0`:

| Constant / behavior | Value | Source |
|---------------------|-------|--------|
| `DEFAULT_MAX_RETRIES` | `2` | `openai/_constants.py` |
| `DEFAULT_TIMEOUT` | `Timeout(timeout=600, connect=5.0)` → effective connect=5s, read/write/pool=600s | same |
| Retry loop | `for retries_taken in range(max_retries + 1)` | `openai/_base_client.py` sync ~1123, async ~1749 |
| Transport attempts per `create` | **3** (= 1 initial + 2 retries) when `max_retries=2` | derived from loop |

`AsyncOpenAI(api_key=..., base_url=...)` as constructed by product therefore inherits timeout=600s / max_retries=2 / up to 3 HTTP attempts per logical chat completion.

**Caveat:** `uv.lock` records `openai==3.6.0` while this environment has `3.20.0`. Seal must re-bind the **actual** seal-time installed version; this audit records the environment under test.

---

## 2. Derived planner-calls-per-slot bound

**Never equate** `max_tool_calls` (8) with planner calls.

Under product defaults (`AgentLimits()` + policy `v9_11`), every non-terminating `decide()` iteration consumes one of a finite set of continue tokens:

- at most `T=8` tool executions (success or error still increments `tool_call_count`);
- at most `K=4` knowledge retrievals;
- at most `R=2` reject/parse **continues** (then a further reject/parse terminates);
- at most `(T+K+1)*(N-1)` non-terminating no-progress continues with `N=2` (progress resets only on successful tool/knowledge; reject does not reset).

Conservative analytical upper bound on logical `planner.decide()` calls per product slot:

```text
bound = (T + K) + (T + K + 1)*(N - 1) + R + 1
      = 12 + 13*1 + 2 + 1
      = 28
```

A small state-machine search over the same action set also yields **28**.

Assumptions (must hold for this number):

1. `AgentLimits` remain the audited defaults.
2. Causal policy remains v9_11 (manual rule batches rejected into the retry budget).
3. No product change adds another continue path that avoids tool/knowledge/retry/no-progress accounting.
4. Bound counts **logical planner turns**, not HTTP transport attempts.

Campaign-level slot retry is separately `forbidden` (`campaign_retry_policy="forbidden"`).

---

## 3. Blocker resolution status

| Blocker | Status | Numeric / reason |
|---------|--------|------------------|
| `unknown_max_tokens_bound` | **BLOCKER remains** | Product `chat.completions.create` omits `max_tokens` / `max_completion_tokens`. No in-repo verified provider max-output pin. Resolving requires separate product design + authorization to set an explicit bound (or a verified provider-spec pin accepted into EffectiveConfiguration). |
| `unknown_provider_request_timeout` | **Audit-resolved (SDK default)** | Client effective timeout **600 s** read (connect **5 s**) from `openai.DEFAULT_TIMEOUT` when product does not pass `timeout`. Not a product-coded constant; seal must snapshot `request_timeout_explicit=True`, `request_timeout_s=600.0` (or tighter product override under a separate grant). |
| `unknown_transport_attempts_per_call_bound` | **Audit-resolved (SDK default)** | **`3`** attempts per logical `create` = `DEFAULT_MAX_RETRIES(2)+1`. Product does not override `max_retries`. |
| `unavailable_retry_telemetry` | **BLOCKER remains** | Study `collect_resource_telemetry` leaves `transport_attempt_count=None`. Product path does not expose SDK `retries_taken` / actual retry counts into study telemetry. Knowing the **max** attempts ≠ available **actual** retry telemetry. |
| `unknown_planner_calls_per_slot_bound` | **Audit-resolved (control-flow)** | **`28`** logical planner calls/slot under §2 assumptions. Still not equal to tool count 8. Companion note `agent_limits_do_not_prove_planner_call_bound:tool_count_is_not_planner_calls` remains correct as a warning against naive tool→planner equating; the 28 figure is a derived control-flow ceiling, not `max_tool_calls`. |
| `unknown_input_token_bound` | **BLOCKER remains** | No product max input tokens; prompt/context size not reduced to a sealed token ceiling. Growing planner context with tools/knowledge has no explicit token cap. |
| `unknown_output_token_bound` | **BLOCKER remains** | No `max_tokens` on the request; output length not product-bounded. |
| `unknown_provider_sdk_identity` | **Audit-resolved for this env (with drift caveat)** | Identity: OpenAI Python SDK **`openai==3.20.0`** installed; no DeepSeek-native SDK. `uv.lock` has `3.6.0`; `pyproject` only `>=1.0`. Seal must re-record exact seal-time version — do not treat lockfile and install as interchangeable. |
| `worst_case_requests_uncomputable` | **Conditionally computable; inspect still blocked** | If planner bound **28** and transport bound **3** are accepted: `57 * 28 * 3 = 4788` worst-case HTTP attempts across product slots. Default `snapshot_effective_configuration()` still omits those fields, so `inspect_limits` still emits this blocker until config is populated. Worst-case **tokens** remain uncomputable while input/output token bounds are unknown. |

### Temperature / thinking (already non-blocking when snapped)

Product sets `temperature=0.0` and thinking disabled. Default `snapshot_effective_configuration()` already records these; they are not among the listed blockers when defaults are used.

---

## 4. Worst-case request arithmetic (conditional)

Only if both factors are accepted as sealed EffectiveConfiguration facts:

```text
worst_case_requests = PRODUCT_SLOT_COUNT_V2
                    * planner_calls_per_slot_bound
                    * transport_attempts_per_call_bound
                    = 57 * 28 * 3
                    = 4788
```

Token ceilings:

```text
worst_case_input_tokens  = worst_case_requests * input_token_bound_per_call   # UNKNOWN
worst_case_output_tokens = worst_case_requests * output_token_bound_per_call  # UNKNOWN
```

Do **not** treat 4788 as an authorized live-run budget until EffectiveConfiguration carries the bounds, retry telemetry policy is addressed, and token bounds exist under an explicit grant.

---

## 5. `seal_ready` / `execution_blocked` flip assessment

On default offline snapshot (`snapshot_effective_configuration()` + `inspect_limits()`):

| Field | Current | Can flip from this audit alone? |
|-------|---------|----------------------------------|
| `execution_blocked` | `true` | **No** — `unknown_max_tokens_bound`, `unavailable_retry_telemetry`, `unknown_input_token_bound`, `unknown_output_token_bound` remain. |
| `seal_ready` | `false` (hardcoded in `inspect_limits`; also requires complete token worst-case via `compute_seal_readiness`) | **No** — token bounds and retry telemetry still missing; label review also still pending per `OFFLINE_ACCEPTANCE.md`. |

Optional study-side population of SDK timeout / transport / planner-call / SDK-version fields into `EffectiveConfiguration` would clear **some** blockers without product behavior change, but **cannot** clear token or retry-telemetry blockers without either:

1. product changes (explicit `max_tokens`, timeout/retry overrides, retry observation) under separate design/authorization; or  
2. an authorized, verified provider-spec binding accepted as configuration facts (still not a silent product invent-limits patch).

**No product composition/planner patch was made in this audit.** Prefer documentation over inventing limits in code.

---

## 6. Separate design / authorization needs (if limits must become product facts)

To clear remaining blockers for a future RealLLM grant, operators need an explicit grant covering at least:

1. Explicit `max_tokens` (or equivalent) on the product DeepSeek chat path — or a verified provider max-output identity bound into the seal.
2. Explicit input/output token ceilings usable as `input_token_bound_per_call` / `output_token_bound_per_call` (including maximal prompts under AgentLimits growth).
3. Study-visible retry/transport telemetry (`retries_taken` / attempt counts) **or** an accepted policy that max-bound alone satisfies “retry telemetry” (current `inspect_limits` requires `retry_telemetry_available=True` — that is a contract/design decision, not something this offline audit may redefine).
4. Re-bind exact `openai` version at seal time (lockfile vs environment drift).

None of the above is authorized by this document.

---

## 7. Code change

**None.** Documentation-only deliverable. `inspect_limits` left unchanged so default offline tests and “unknown until configured” semantics stay intact; inventing product limits in composition/planner is out of scope.

---

## 8. Readiness one-liner

Offline audit **derives** planner-call ceiling **28**, transport attempts/call **3**, client timeout **600 s**, and SDK identity **`openai==3.20.0` (this env)**; request ceiling **4788** is arithmetically available from those factors.  
**`execution_blocked` / `seal_ready` do not flip:** max tokens, input/output token bounds, and retry telemetry remain blockers.  
**Green offline tests ≠ live-run readiness; no RealLLM grant implied.**
