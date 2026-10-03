# Resource bounds audit: `study_s1_planner_ablation_dev_2`

**Scope:** Task 2 source-aware resource policy `planner_ablation_resource_v1` —
offline environment audit and bound derivation only.
**Not a protocol seal.** No `protocol_seal/` created under this study root.
**Not a RealLLM grant.** No provider/network calls. No product request caps.
**Explicit:** green offline tests ≠ budget closure or seal readiness.

Companion to `BUDGET_BOUNDS.md` (legacy `inspect_limits` explicit-flag path).
Audited SDK defaults **must not** flip `request_timeout_explicit`,
`transport_retry_override_explicit`, or `max_tokens_explicit`.

**Authoritative reviewed capability identity:** §7 below (lock-aligned `openai==3.6.0`,
rebound 2026-10-03 SDK environment grant). §1 is a superseded 2026-10-01 audit only.

Audit environment (writing workspace, post-rebind):

| Fact | Value |
|------|-------|
| Branch | `cursor/oq019-dev2-residual-gates-8b52` |
| Trunk tip referenced | `0b2cc5d` (post D040 rebind; D041 residual gates) |
| Installed `openai` | `3.6.0` (`importlib.metadata`) |
| `uv.lock` `openai` | `3.6.0` (**matches installed**) |
| `httpx` | `0.28.1` |
| `httpcore` | `1.0.9` |
| Native HTTP family | `httpx` (OpenAI Python AsyncOpenAI default) |
| `build_audited_sdk_observation_profile().supported` | **true** (matches §7 digests) |

## 1. Installed SDK / source identity (superseded historical audit, 2026-10-01)

| Path | SHA-256 |
|------|---------|
| `openai/__init__.py` | `df04adb6b7a4481956342b4dbadeb9b8555e789e2efd1f8469fa6ddb4d22f7a8` |
| `openai/_base_client.py` | `7a0a173edf3fadb6b310895d5db6fa0b14264bdaa25b33dd4eb29d860a82639b` |
| `openai/_client.py` | `0e2ab3a8fd22a55c9312cd712c9b38948566121a6384a0b29ed55b7f3390de26` |
| `openai/_constants.py` | `eeccbc82822f0e4372f42f666afd1d1e1fe80cb2ef71357018a0170ac6b9ce32` |
| Aggregate (ordered concat of the four digests) | `ad8a3f7783180a170f5fd054998e0add17351411ca9705b4fcde767ee02f0765` |

Audited defaults (not product overrides):

| Setting | Value | Origin |
|---------|-------|--------|
| `DEFAULT_MAX_RETRIES` | `2` → **3** SDK attempts/call | `sdk_default_audit` |
| `DEFAULT_TIMEOUT` | connect=5s, read/write/pool=600s | `sdk_default_audit` |
| Redirects | Async client follows redirects; httpx `DEFAULT_MAX_REDIRECTS=20` | **admitted** `H=21` (D041; §3) |
| Auth | bearer API key; product does not pass custom http client | `bearer_api_key` |

Candidate observation hooks (3.20.0 source audit; support gated by Task 4 offline tests):

- `AsyncAPIClient._prepare_options` (retry-loop entry)
- `AsyncAPIClient._send_request` (retry-loop exit)
- `httpx.AsyncClient.send` (single HTTP dispatch)

An unaudited installed tuple, lockfile-only identity (`3.6.0`), or drifted
source digest is **unsupported**.

## 2. Control-flow planner-turn ceiling

Under `AgentLimits()` defaults and causal policy `v9_11_mode_aware_no_fault_recovery`:

```text
P = (T + K) + (T + K + 1)*(N - 1) + R + 1
  = 12 + 13 + 2 + 1
  = 28 planner turns / product slot
```

Bound code digests at audit time (invalidate on uncovered continue path):

| Path | SHA-256 |
|------|---------|
| `src/signal_diag/agent/policies.py` | `635aa378de66224c25fceb2e3f8cefb77d7b385e8faf181958d11f361ec03726` |
| `src/signal_diag/agent/runtime.py` | `e98e175e6b779fa43a063a484e2c885a7dbc948f96e1ba4573142b8d14f7323c` |
| `src/signal_diag/agent/planner.py` | `2f8829bd36eeb8f8cc0f0e6a7bee8895e8a24500cd186a2756af8d95541d9121` |
| `src/signal_diag/app/composition.py` | `578ced2aa3341a634ec6108a8a5c228623f4614610d154d3ace4cedb3b443fe3` |

Do **not** equate `max_tool_calls=8` with planner turns. A new uncovered continue
path invalidates `P`; do not repair by adding a product runtime cap.

## 3. Named-unit arithmetic

```text
S = 57 product slots
P = 28 (control_flow_proof, conditional)
A = 3  (sdk_default_audit retry loop)
H = 21 (sdk_default_audit, admitted D041)

logical_call_ceiling = S * P           = 1596
sdk_attempt_ceiling  = S * P * A       = 4788
http_send_ceiling    = S * P * A * H   = 100548
http_send_per_slot   = P * A * H       = 1764
input_token_ceiling  = http_send_ceiling * I = UNKNOWN (no admitted I)
output_token_ceiling = http_send_ceiling * O = UNKNOWN (no admitted O)
```

**HTTP send factor audit (D041, no network):** On the reviewed lock-aligned
install (`openai==3.6.0`, native dispatch `httpx.AsyncClient.send`), the OpenAI
Async client enables redirect following. httpx `DEFAULT_MAX_REDIRECTS` is `20`
(`httpx==0.28.1`). Worst-case HTTP dispatches per SDK attempt is therefore
`1 + 20 = 21` (`http_sends_per_sdk_attempt`). Origin `sdk_default_audit`,
scope `admitted`, `dependency_identity` `openai==3.6.0;httpx==0.28.1`. This
admits redirect-chain replay only; auth resend and lower-transport replay remain
outside the proof.

`4788` is a **conditional SDK-attempt ceiling**. `100548` is a **conditional
HTTP-send ceiling** when `H` is bound; it is not an accepted live campaign
budget without token proofs and non-fixture capability.

## 4. Provider model / token evidence

| Fact | Status |
|------|--------|
| Requested model | `deepseek-v4-flash` (product string unchanged) |
| Declared route (docs 2026-10-01) | V4.1-Flash legacy name → `deepseek-v4.1-flash` — **accepted** on study binding (D041) |
| Operator route package (Task 6) | `PRESEAL_BUDGET_STATUS.md` — `deepseek-v4-flash` + `v0.3-s1-planner-9.11` + `v9_11_mode_aware_no_fault_recovery`; mapping **accepted** (`model_mapping_accepted=true`) |
| `max_tokens` / `max_completion_tokens` on product create | **omitted** |
| Provider context-window capacity | does **not** prove failed-attempt token exposure |
| Serializer / tokenizer / framing / reachable-context proof | **absent** |
| All-outcome token cap | **absent** |

## 5. Remaining blockers (honest)

| Blocker | Status |
|---------|--------|
| `unproved_http_send_bound` | **cleared** when proofs bind admitted `H=21` (D041) |
| `unproven_failed_attempt_token_bound` | remains — context capacity ≠ failed-attempt exposure |
| `unknown_input_token_bound` / `unknown_output_token_bound` | remains without all-outcome or admitted per-send proofs |
| `unaccepted_provider_model_mapping` | **cleared** on study binding after D041 operator acceptance |
| `unavailable_retry_telemetry` (legacy `inspect_limits`) | remains until Task 3–5 observation is bound |
| Lockfile vs installed SDK drift | **cleared** on lock-aligned `3.6.0` (§7); superseded §1 drift retained for history |

Legacy `inspect_limits(snapshot_effective_configuration())` stays
`execution_blocked=True`. Source-aware `assess_resource_budget` can compute
`sdk_attempt_ceiling=4788` from fixture-reviewed facts while remaining
`execution_blocked=True` and `seal_ready=False`.

## 6. Code change in this document's audit

Task 2 adds pure study models and `assess_resource_budget`. It does **not**
change product constructors, request payloads, or explicit-flag semantics.

**No formal seal. No RealLLM. No commit/push authorized by this document.**

## 7. Current reviewed capability identity (lock-aligned `openai==3.6.0`)

**Scope:** authoritative SDK / transport identity for `provider_telemetry` and
admitted bound-fact `dependency_identity` on this study path. Rebound from
superseded §1 (`3.20.0` Cloud audit) under OQ-019/dev_2 offline SDK rebind
grant (2026-10-03). Companion status board: `PRESEAL_BUDGET_STATUS.md`.

| Fact | Value |
|------|-------|
| Writing branch | `cursor/oq019-dev2-residual-gates-8b52` |
| Trunk tip referenced | `0b2cc5d` (post D040; D041 residual gates) |
| Installed `openai` | `3.6.0` |
| `uv.lock` `openai` | `3.6.0` (**matches installed**) |
| `httpx` | `0.28.1` |
| `httpcore` | `1.0.9` |
| Native HTTP family | `httpx` |
| `DEFAULT_MAX_RETRIES` | `2` → **3** SDK attempts/call |
| `DEFAULT_TIMEOUT` | connect=5s, read/write/pool=600s |
| Candidate hooks | `AsyncAPIClient._prepare_options`, `AsyncAPIClient._send_request`, `httpx.AsyncClient.send` |
| `build_audited_sdk_observation_profile().supported` | **true** |

Reviewed source digests (`sha256` of file bytes; baked into `provider_telemetry`):

| Path | SHA-256 |
|------|---------|
| `openai/__init__.py` | `2c6e2a8d358b4bd705fa019a0d5b10d5b457591cf699e53b8aff36d9ba30fb1d` |
| `openai/_base_client.py` | `53dc8c82344056600a08f51df158956827bdcc1a15cd4d3e1ce905a22663bd4c` |
| `openai/_client.py` | `e2421659ea3ebd4ede9c940ae449e3cea65c096f21d97a1ece44f194aeda85ae` |
| `openai/_constants.py` | `eeccbc82822f0e4372f42f666afd1d1e1fe80cb2ef71357018a0170ac6b9ce32` |
| Aggregate (`aggregate_openai_source_digest`) | `a4a2193775e68b1497d61c84ad851e785597db0f0a2a443856d3b890fa412e47` |

What offline rebind **clears** (this grant only):

- `environment_rebind` reviewed SDK identity / digest agreement on lock-aligned
  `3.6.0`; `build_audited_sdk_observation_profile().supported=true` when the
  installed tuple matches this table.
- Lockfile↔install drift for `openai` on this environment.

What rebind does **not** clear (D040 alone):

- Input/output token ceilings or failed-attempt token exposure (still
  **unknown** / unproved).

Closed in **D041** residual gates (study proofs; product unchanged):

- HTTP send factor `H=21` (`unproved_http_send_bound` when bound).
- Operator route acceptance (`model_mapping_accepted=true` on study binding).

Still not cleared by D040/D041:

- Legacy `inspect_limits` explicit-flag blockers.
- Formal `protocol_seal/` or RealLLM campaign readiness.
- Formal candidate `seal_ready=true` without token proofs and non-fixture bind.

**No formal seal. No RealLLM authorized by this section.**

## Structured bound-fact records (machine-readable)

```json
{
  "schema": "planner_ablation_bound_facts_v1",
  "facts": [
    {
      "name": "planner_turn_ceiling",
      "status": "approved",
      "value": 28,
      "unit": "planner_turns_per_slot",
      "origin": "control_flow_proof",
      "scope": "admitted",
      "applicable_path": "runtime",
      "code_identity": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "dependency_identity": "openai==3.6.0",
      "model_identity": null
    },
    {
      "name": "sdk_attempt_factor",
      "status": "approved",
      "value": 3,
      "unit": "sdk_attempts_per_logical_call",
      "origin": "sdk_default_audit",
      "scope": "admitted",
      "applicable_path": "product_deepseek_chat",
      "code_identity": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "dependency_identity": "openai==3.6.0",
      "model_identity": "deepseek-v4-flash"
    },
    {
      "name": "http_send_factor",
      "status": "approved",
      "value": 21,
      "unit": "http_sends_per_sdk_attempt",
      "origin": "sdk_default_audit",
      "scope": "admitted",
      "applicable_path": "openai_async_follow_redirects_plus_httpx_default_max_redirects_20",
      "code_identity": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "dependency_identity": "openai==3.6.0;httpx==0.28.1",
      "model_identity": "deepseek-v4-flash",
      "acceptance_reference": "docs/DECISIONS.md#d041--oq-019dev_2-residual-preseal-route-acceptance-and-http-send-factor-h"
    },
    {
      "name": "input_token_ceiling",
      "status": "unknown"
    },
    {
      "name": "output_token_ceiling",
      "status": "unknown"
    },
    {
      "name": "all_outcome_token_ceiling",
      "status": "unknown"
    },
    {
      "name": "request_timeout",
      "status": "unknown"
    }
  ]
}
```
