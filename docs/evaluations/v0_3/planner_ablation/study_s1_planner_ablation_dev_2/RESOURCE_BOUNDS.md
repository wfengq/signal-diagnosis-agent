# Resource bounds audit: `study_s1_planner_ablation_dev_2`

**Scope:** Task 2 source-aware resource policy `planner_ablation_resource_v1` —
offline environment audit and bound derivation only.
**Not a protocol seal.** No `protocol_seal/` created under this study root.
**Not a RealLLM grant.** No provider/network calls. No product request caps.
**Explicit:** green offline tests ≠ budget closure or seal readiness.

Companion to `BUDGET_BOUNDS.md` (legacy `inspect_limits` explicit-flag path).
Audited SDK defaults **must not** flip `request_timeout_explicit`,
`transport_retry_override_explicit`, or `max_tokens_explicit`.

Audit environment (this workspace, 2026-10-01):

| Fact | Value |
|------|-------|
| Branch | `cursor/s1-dev2-telemetry-impl-0d26` |
| Baseline merge | `fb3a71b400bccd8891f89006e3b72f847b83d17d` |
| Installed `openai` | `3.20.0` (`importlib.metadata`) |
| `uv.lock` `openai` | `3.6.0` (**not interchangeable** with installed) |
| `httpx` | `0.28.1` |
| `httpcore` | `1.0.9` |
| Native HTTP family | `httpx` (OpenAI Python AsyncOpenAI default) |

## 1. Installed SDK / source identity

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
| Redirects | enabled by default on native httpx client | **unproved** HTTP send factor `H` |
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
H = UNKNOWN (redirects / auth resend / lower-transport replay unbound)

logical_call_ceiling = S * P           = 1596
sdk_attempt_ceiling  = S * P * A       = 4788
http_send_ceiling    = S * P * A * H   = UNKNOWN
input_token_ceiling  = http_send_ceiling * I = UNKNOWN
output_token_ceiling = http_send_ceiling * O = UNKNOWN
```

`4788` is a **conditional SDK-attempt ceiling**, not an HTTP-send ceiling and
not an accepted live budget.

## 4. Provider model / token evidence

| Fact | Status |
|------|--------|
| Requested model | `deepseek-v4-flash` (product string unchanged) |
| Declared route (docs 2026-10-01) | V4.1-Flash for legacy flash name — **unaccepted** for seal |
| `max_tokens` / `max_completion_tokens` on product create | **omitted** |
| Provider context-window capacity | does **not** prove failed-attempt token exposure |
| Serializer / tokenizer / framing / reachable-context proof | **absent** |
| All-outcome token cap | **absent** |

## 5. Remaining blockers (honest)

| Blocker | Status |
|---------|--------|
| `unproved_http_send_bound` | remains — no admitted `H` |
| `unproven_failed_attempt_token_bound` | remains — context capacity ≠ failed-attempt exposure |
| `unknown_input_token_bound` / `unknown_output_token_bound` | remains without all-outcome or admitted per-send proofs |
| `unaccepted_provider_model_mapping` | remains until operator accepts live route binding |
| `unavailable_retry_telemetry` (legacy `inspect_limits`) | remains until Task 3–5 observation is bound |
| Lockfile vs installed SDK drift | recorded; seal must re-bind installed tuple |

Legacy `inspect_limits(snapshot_effective_configuration())` stays
`execution_blocked=True`. Source-aware `assess_resource_budget` can compute
`sdk_attempt_ceiling=4788` from fixture-reviewed facts while remaining
`execution_blocked=True` and `seal_ready=False`.

## 6. Code change in this document's audit

Task 2 adds pure study models and `assess_resource_budget`. It does **not**
change product constructors, request payloads, or explicit-flag semantics.

**No formal seal. No RealLLM. No commit/push authorized by this document.**
