# S1 planner-ablation token and transport telemetry design

Status: design approved by the operator on 2026-10-01; implementation not authorized.
Date: 2026-10-01.
Source baseline: PR #19 merge `fb3a71b400bccd8891f89006e3b72f847b83d17d`.
Study: `study_s1_planner_ablation_dev_2`.

Approval: "审阅通过 `授权 token／transport telemetry writing-plans only`。"
This approval authorizes the companion implementation plan only. It does not
accept concrete runtime/provider bindings, numeric budgets, or a seal candidate.

The operator authorized only a reviewable token/transport telemetry design.
This document does not authorize implementation, CONTRACTS/TEST_PLAN edits,
seal generation, provider calls, commits, push, merge, or a product change.
The local checkout is `9931875`; source findings below refer to the merged
baseline above, read without switching or modifying the checkout.

## 1. Decision proposed for review

Keep the current product request semantics. Add opt-in observation for the
study, and admit resource bounds only with a reviewed source and exact runtime
identity. Count planner turns, runtime repairs, SDK attempts, HTTP send attempts,
and provider-reported tokens separately.

This closes a specific gap in §20.6 and T-CX299: the study currently has
conditional ceilings but cannot observe actual calls, retries, or tokens.
Knowing a ceiling does not prove observation. A successful mock run does not
prove the live model identity or authorize a campaign.

The recommended design permits audited defaults to supply effective bounds
under a new additive resource policy. It preserves the meaning of existing
`*_explicit` flags. It does not make SDK defaults into explicit product
overrides, and it does not weaken the old `inspect_limits` path.

Three choices were considered:

| Choice | Consequence | Decision |
|---|---|---|
| A. Passive observation plus source-bound effective limits | Preserves product settings; requires version-specific SDK observation, token-bound proof, and additive contracts | Recommend |
| B. Add explicit token, timeout, retry, and redirect caps to the product | Changes requests or failure behavior and potentially diagnosis quality | Requires a separate product design; excluded here |
| C. Record ceilings or token estimates without actual telemetry | Cannot meet §20.5, §20.6, or T-CX299 | Reject |

Choice A is conditional on proof. If an unchanged product request cannot be
given finite token/transport bounds, execution stays blocked. The implementer
must not silently switch to B to make the gates green.

## 2. Current facts and unresolved identities

These are baseline facts, not new grants:

| Finding | Evidence at the source baseline | Design consequence |
|---|---|---|
| `RealLLMPlanner` omits `max_tokens`, client timeout, and `max_retries`; it discards response usage | `src/signal_diag/agent/planner.py:420`, `:430`, `:477` | Observe the existing request and retain usage before output validation |
| Each `decide` constructs a fresh SDK client when `_client` is absent | `src/signal_diag/agent/planner.py:420–428` | Observation must preserve client construction and lifetime; no new pooling |
| Runtime calls `decide` once per loop; `planner_attempt_count` stays zero | `src/signal_diag/agent/runtime.py:179`, `:305` | Count actual entry events; do not use that field or factory calls as telemetry |
| Study telemetry leaves planner, repair, transport, and token values unknown | `src/signal_diag/evaluation/planner_ablation/v2/campaign.py:234` | Replace unknowns only through validated observations |
| Existing bounds gate requires explicit flags | `src/signal_diag/evaluation/planner_ablation/v2/models.py:519`; `campaign.py:131` | Add versioned source-aware validation; retain legacy rejection |
| Product provenance currently remains `harness_only` | `src/signal_diag/app/planner_ablation_v2_adapter.py:196` | Future online admission needs an explicit verified path, not a flipped label |
| Seal dependency binding omits the SDK and its full transport family | `src/signal_diag/evaluation/planner_ablation/v2/sealing.py:74` | Bind actual SDK and transport dependencies before accepting bounds |
| Candidate creation does not yet bind independent label approval into its machine validation | `src/signal_diag/evaluation/planner_ablation/v2/sealing.py:466` | Include the accepted review record in the candidate verification chain |

The merged `BUDGET_BOUNDS.md` records a Cloud audit of `openai==3.20.0`.
`uv.lock` records `3.6.0`; this Codex environment has `3.5.0`. These are distinct
identities. No observation or bound may substitute one environment for another.
The exact implementation environment is bound later; this design does not
install or upgrade packages.

There is also provider-side model routing drift. On 2026-10-01, DeepSeek's
official pricing documentation states that the legacy name
`deepseek-v4-flash` is now served by V4.1-Flash. The product still requests the
legacy name. Record requested name and provider-declared route separately.
The operator must accept this live identity before seal; do not change the
product model string under this design. Today's route does not establish the
backend used in a historical campaign.

The relevant official sources are:

- [DeepSeek model pricing and legacy-name routing](https://api-docs.deepseek.com/quick_start/pricing/).
- [DeepSeek chat completion limits and usage fields](https://api-docs.deepseek.com/api/create-chat-completion/).
- [DeepSeek token usage](https://api-docs.deepseek.com/quick_start/token_usage/).
- [OpenAI Python 3.20.0 transport documentation](https://github.com/openai/openai-python/blob/v3.20.0/httpx2.md).
- [OpenAI Python 3.20.0 request/retry implementation](https://github.com/openai/openai-python/blob/v3.20.0/src/openai/_base_client.py).
- [OpenAI Python 3.20.0 authentication/client implementation](https://github.com/openai/openai-python/blob/v3.20.0/src/openai/_client.py).

Provider pages are mutable. A later accepted binding records the reviewed date,
applicable model/path, relevant values, and source snapshot digest. Documentation
is evidence for declared limits, not proof of immutable model weights. No
provider `/models` request or connectivity probe is authorized by this design.

## 3. What counts as a call or a token

The observation hierarchy is:

```text
study slot
  planner turn: one entry to RealLLMPlanner.decide
    logical completion call: one SDK chat.completions.create invocation
      SDK attempt: one iteration of the SDK request/retry loop
        HTTP send attempt: one underlying HTTP request dispatch
```

A turn can fail before a logical completion call. SDK retries do not create new
planner turns. Redirects can create extra HTTP send attempts without another SDK
attempt. Runtime repair consumes the runtime's rejection/parse budget and creates
a subsequent turn; it is counted separately from SDK retries.

The selected profile covers the current non-streaming completion path only.
Adding streaming or a different provider API requires a separately reviewed
profile. Connection-establishment retries are diagnostic connection events unless
they replay an HTTP request; they must not be mislabeled as additional completions.

An HTTP send attempt proves local dispatch, not provider receipt, execution, or
billing. Connection failure after dispatch still counts as an attempt. A transport
with internal resend behavior needs its own audited dispatch observation; a hook
around `client.send` alone must not claim it sees those resends.

Two token quantities remain separate:

1. `reported_usage` sums valid provider-reported usage on received completion
   responses. It includes responses whose content later fails planner parsing.
2. `potential_token_exposure` uses approved per-send ceilings for attempts whose
   usage is unavailable. It is a conservative bound, not an observed token count
   or a monetary bill.

No response means usage is unknown unless a validated trace proves the call was
never dispatched. A missing usage object on a completion is unknown, not zero.
HTTP error responses without usage do not automatically prove zero token use.

For a complete, validated usage object, require nonnegative integer prompt,
completion, and total tokens, with total equal to prompt plus completion. Reject
booleans, malformed fields, and inconsistent totals. Cache-hit/cache-miss counts
and reasoning details are subdivisions; do not add them again to total tokens.
Missing subdivisions may remain absent when the required totals are complete.
Preserve the provider's field meanings in the binding.

When subdivisions are present, validate their types and arithmetic too. In
particular, supplied cache-hit plus cache-miss must equal prompt tokens, and
reasoning tokens cannot exceed completion tokens. Contradictory details invalidate
the observation instead of being discarded to preserve a passing total.

## 4. Observation belongs to the executing slot

The app adapter owns one collector for each fresh, non-overlapping slot. Its
tracking factory binds that collector to the concrete product planner created
for execution. Construction probes produce no planner-turn or provider-call
events. This binding is explicit; a `ContextVar` around submission is insufficient
for the service's persistent background worker.

The agent owns small observation protocols and immutable events. They depend
only on lower-level types or the standard library. They do not import the study,
`evaluation`, or `app`. The product's public constructor, builder, decision types,
run-result fields, and report JSON stay unchanged.

The proposed additive seam is private, opt-in observation on the canonical
`RealLLMPlanner`, disabled by default. A study binding helper installs the
observer on the exact planner instance. The canonical SDK construction path
then attaches observation using the audited native transport for that SDK
version. No subclass, alternate planner, injected fake completion client,
global patch, new request header, retry wrapper, or prompt rewrite is admitted.

Binding is supported only while that slot's service is idle, before submission.
The collector must safely accept callbacks from the executing worker, keep one
monotonic clock, and freeze only after that worker and its requests are drained.
Closing the study terminal timer does not close a still-active resource ledger.

The exact native hook/transport integration must be demonstrated in offline
tests for the selected SDK version. It must preserve timeout, redirect, retry,
proxy, TLS, connection-pool, authentication, and client-lifetime behavior.
If a hook cannot expose every relevant dispatch while preserving those
behaviors, that SDK observation profile remains unsupported.

Private planner/runtime changes are still changes to product internals.
They require a later additive contract, test definitions, and explicit
implementation authorization even though their default is off. Calling them
"study-only" does not bypass the scope gate.

The proposed file ownership is:

| Location | Responsibility |
|---|---|
| New `src/signal_diag/agent/telemetry.py` | Observation protocols, typed events, no study/SDK imports |
| `src/signal_diag/agent/planner.py` | Opt-in canonical binding, logical call/SDK observation, usage before parsing |
| `src/signal_diag/agent/runtime.py` | Actual repair-budget-consumption events at all relevant branches |
| `src/signal_diag/app/planner_ablation_v2_adapter.py` | Per-slot collector, runtime-to-slot association, lifecycle and provenance mapping |
| `src/signal_diag/evaluation/planner_ablation/v2/` | Pure event validation, aggregation, source-aware bounds, admission and seal binding |

SDK-dependent observation stays at the existing agent provider boundary. The
evaluation package consumes serialized facts; it must not construct a service,
import app composition, or call the SDK.

## 5. Minimal records and aggregation rules

These are proposed study-side schemas, not edits to existing product models:

| Record | Required facts |
|---|---|
| `BoundFact` | Value, unit, origin, applicable path, proof digest, exact code/dependency/model identity, and whether it is an actual explicit override |
| `ProviderLimitsBinding` | Endpoint origin, requested model, declared route, allowed response model metadata, source date/digest, token-limit scope, authentication and transport configuration |
| `PlannerTurnEvent` | Slot-local turn ID, monotonic start/end, typed outcome, whether a logical completion was submitted |
| `RepairEvent` | Turn ID, typed rejection/parse reason, actual retry budget consumed; not inferred from error text |
| `SdkAttemptEvent` | Logical call ID, attempt ID, retry index, start/end, typed outcome; optional SDK retry header used only as a cross-check |
| `HttpSendEvent` | Parent attempt ID, send ID, redirect/resend relation, sanitized endpoint, start/end, response status or typed failure/cancellation |
| `UsageObservation` | Parent send/response ID, validated usage totals/details or an explicit missing/malformed status |
| `SlotResourceLedger` | Event sequence, slot and eventual run-ID binding, derived totals, known subtotals, unknowns, bound violations, pending events and drain status |

The collector uses a bounded buffer sized from accepted event ceilings. Buffer
overflow, callback failure, duplicate IDs, orphan events, or missing end events
latch `telemetry_invalid`. Observation callbacks must not throw into product
decision logic. They must not silently drop data or invent replacement events.

No raw prompt, response text, waveform, FFT, API key, authorization header,
credential-bearing URL, or exception string is persisted in these records.
Allowlisted numbers, enums, hashes, lengths, sanitized endpoint identity, and
opaque IDs are sufficient. Prompt hashes and byte lengths are measured on the
exact submitted serialization; no second serialization may alter the request.

Associate slot-local IDs with the service run ID once available. Verify one
executing run per slot. A missing or conflicting association invalidates
telemetry; it does not receive a fabricated run ID.

Counts derive from unique validated entry/dispatch events. Failed calls and
received-but-unparseable completions stay in the totals. `input_tokens`,
`output_tokens`, and `total_tokens` are exact sums only when all potentially
token-consuming attempts have complete usage or a reviewed zero-use proof.
Otherwise keep the aggregate unknown and report the known subtotal and
unobserved exposure bound separately.

The fixed arm records zero planner/SDK/HTTP/token activity only when its audited
path and slot ledger establish that it has no provider path. It retains the same
decode/terminal/guidance timing obligations. No fake client is used to fabricate
zero product usage.

## 6. Bounds retain their source

Proposed `BoundFact.origin` values are `request_override`, `sdk_default_audit`,
`provider_spec`, `control_flow_proof`, and `unknown`. Each accepted fact binds the
code/path and environment that make it true. A number without that proof is
unknown for admission purposes.

Add a resource policy version, proposed `planner_ablation_resource_v1`, to the
unsealed dev_2 candidate. The existing quality scorer, schedule, populations,
decision bands, and timing contract remain unchanged. A future definitions phase
adds source-aware validation; old configs retain their existing fail-closed
semantics. Never set `max_tokens_explicit`, `request_timeout_explicit`, or
`transport_retry_override_explicit` to true because a default was audited.

The new policy permits these sources subject to review:

| Bound | Acceptable proof |
|---|---|
| Planner turns | Control-flow proof for the exact runtime, policy and AgentLimits; all continue paths accounted for |
| SDK attempts | Exact installed SDK retry loop, effective retry configuration, authentication behavior and relevant environment |
| HTTP send attempts | Redirect and lower-transport resend limits, observation depth, and any authentication resend paths |
| Timeout | Exact phase timeout/defaults plus authoritative outer slot deadline and verified background-worker lifecycle |
| Output tokens | Applicable provider hard/default output limit or actual explicit request cap, with omission semantics established |
| Input tokens | A proved bound on exact reachable serialized messages and provider framing, or a provider cap proved applicable to every budgeted request outcome |

The existing 120-second outer deadline remains the request deadline. An audited
SDK phase timeout, such as 600 seconds, is not a total request/campaign duration
bound. Timeout cancellation must not pretend a still-running worker is drained.

Input-token proof must cover system/user messages, growing evidence and knowledge
context, and error/repair text reachable under the runtime budgets. A byte count,
character/token ratio, demo tokenizer, or tokenizer for an unverified model
revision does not establish this bound. A tokenizer-based proof must bind the
correct vocabulary, framing overhead, serializer, and a finite reachable-context
size bound. No input truncation is introduced by this design.

A provider context-window limit describes accepted input capacity. It does not
alone prove the tokens exposed or charged by oversized/rejected/ambiguous attempts.
Accepting a provider cap as a universal exposure bound requires evidence for that
scope. If that proof is unavailable, emit `unproven_failed_attempt_token_bound`.
Do not claim the token budget is closed just because successful responses fit.

## 7. Arithmetic uses named units

The merged audit derives a conservative planner-turn ceiling of 28 under the
current v9.11 policy and defaults. It is conditional on every continue path
remaining covered. Do not equate eight tool calls with eight planner calls.

For the current 57 product slots, let:

```text
S = 57 product slots
P = accepted planner-turn ceiling per slot
A = accepted SDK attempts per logical completion
H = accepted HTTP send attempts per SDK attempt
I = accepted input-token exposure ceiling per HTTP send
O = accepted output-token exposure ceiling per HTTP send

logical_call_ceiling <= S * P
sdk_attempt_ceiling   = S * P * A
http_send_ceiling     = S * P * A * H
input_token_ceiling   = http_send_ceiling * I
output_token_ceiling  = http_send_ceiling * O
```

An audited `P=28`, `A=3` gives 4,788 SDK attempts, not HTTP sends. Derive `H`
from the selected transport's control flow, including redirects, authentication
resends, and lower-transport retries. Independent factors may be multiplied only
when their nesting and units are proved. Avoid double-counting the same loop.

For illustration only, if a reviewed transport allows twenty redirects per SDK
attempt and no other resend path, `H=21` and the HTTP ceiling is 100,548. That
number is not a selected bound or a RealLLM budget. The exact transport is not yet
bound. Finiteness alone is not operator acceptance of that exposure.

Token ceilings conservatively reserve exposure for ambiguous sends. Known usage
must never be reported as the entire campaign's actual usage when another attempt
is unknown. A financial charge requires provider billing evidence and rates;
this design does not turn token exposure into an invoice.

## 8. Offline capability and live completeness are different gates

Before seal, demonstrate that the selected observation profile can capture
turns, repairs, SDK attempts, HTTP sends, and usage under offline controlled
success/failure cases. Derive a capability result from those tests and exact
code/dependency hashes. A caller cannot pass `retry_telemetry_available=True`
without this binding. No live calibration request is required or authorized.

Before a later RealLLM grant, the candidate must have finite, reviewed numeric
bounds, exact installed dependencies, the accepted provider model mapping,
complete label-review bindings, verified inputs/code, and a separate operator
execution authorization. Mock capability evidence never makes mock output
scored evidence.

During a future campaign, close the ledger before accepting the slot's resource
metrics. On telemetry invalidity, usage absence without a zero-use proof, model
metadata outside the approved policy, or a bound violation, preserve the product
terminal outcome and stop before starting another slot. A typed resource failure
blocks an accepted positive study conclusion. It is not automatically a planner
behavioral failure and must not remove a slot from the frozen denominators.

An infrastructure deadline keeps its existing stop classification. Cancellation
of the waiter alone is not worker completion. Record late events until actual
drain; if drain fails, retain pending/unknown exposure, stop, and do not retry or
overlap slots. Observation must not introduce new product retries or alter the
product's diagnosis to repair study bookkeeping.

All observation work needed before terminal readiness is inside
`encoded_bytes_to_terminal_v1`. Artifact writing stays outside. Report that the
product arm includes the selected observation profile's overhead; do not subtract
it or claim unobserved planner-only latency. Offline on/off tests establish
semantic parity, not zero timing overhead.

## 9. Provenance and seal verification remain independent

Keep the scored product arm as the exact approved `RealLLMPlanner` with its
canonical SDK path. A concrete class object/module and code hash are stronger
evidence than a class-name string. The observation descriptor records the real
SDK, native transport family, settings and code identity; it is not an execution
authorization token or proof of provider receipt.

The existing `_client` fake-injection path remains `harness_only`. An offline
SDK using `MockTransport` also remains `harness_only`, even if `_client` is absent
and the planner class is correct. The approved internal observer transport must
be a real native transport created by the canonical factory, with its origin
verified. Do not redefine `provider_client_bound=False` to conceal an injected
fake or admit an arbitrary caller-supplied client.

Online admission derives from all of: verified manifest context, separate live
execution grant, exact approved planner path, verified real transport binding,
and offline/fixture indicators being false. No individual boolean, descriptor,
or arm label can turn a fixture into `product_campaign`.

The resource extension binds:

- Resource-policy and telemetry-schema versions, event/aggregation rules, and
  the chosen observation profile with its offline capability evidence.
- Exact implementation commit/tree, actual SDK and transport dependency
  versions/source identities, effective defaults, and applicable proof records.
- Endpoint/authentication mode and behavior-relevant proxy/transport settings,
  with credentials removed; requested and provider-declared model identities,
  response metadata policy, and reviewed source digests.
- Finite planner, SDK, HTTP and token ceilings with units; timeout/drain policy;
  applicable tokenizer/framing proof when used.
- Independent label-review approval and its exact oracle/alias/U/C/G/input
  bindings. A structural label validator does not replace independent approval.

This binding consumes the existing approved label review. It does not reopen
oracle design, change U/C/G membership, or authorize another label population.

`make_complete_budget_assessment` is not production proof. Synthetic complete
budget objects remain fixture-only. Production candidate validation recomputes
bounds from admitted facts and rejects inconsistent values, missing proof,
environment drift, and label-review mismatch.

Manifest verification must recompute these bindings before any future request.
Returned model/fingerprint metadata is checked when available against the
accepted policy, but cannot prove frozen weights. If the provider only echoes
the alias or has no fingerprint, record that limitation. Accepting such a
provider identity is an explicit operator decision, not a fabricated guarantee.
Detectable drift stops execution; it does not regenerate a seal.

This extension applies only to unsealed dev_2 through explicit version dispatch.
Dev_1 identities, seal, reproducer and campaign remain unchanged. No historical
campaign is rescored to validate the new telemetry.

## 10. Required acceptance evidence for a later implementation

The next definitions phase must reconcile the next free IDs. At the source
baseline, T-CX302 is the highest registered contextual ID. The following
T-CX303–T-CX318 names are proposed allocations, not registered definitions or
claims of passing tests:

| Proposed ID | Evidence required |
|---|---|
| T-CX303 | Defaults retain false explicit flags; unknown/unproved/legacy facts stay blocked; admitted sources require exact proof |
| T-CX304 | Installed SDK/transport versions and source hashes bind actual behavior; lockfile-only or changed-dependency identity fails |
| T-CX305 | Requested name and declared served route differ explicitly; unaccepted mapping or observable response drift blocks admission |
| T-CX306 | Observation on/off produces identical serialized provider payload/settings, concrete planner type, decisions, evidence, guidance, and exception behavior |
| T-CX307 | Count actual turns/calls, not factory probes or frozen attempt fields; exercise the control-flow-bound assumptions and reject an uncovered continue path |
| T-CX308 | All runtime parse/reject repair branches consume and emit the right repair count; SDK retries do not count as repairs |
| T-CX309 | Controlled 500/500/200 path records one logical call and three SDK attempts; successful usage is retained even when planner JSON is invalid |
| T-CX310 | Three redirects yield four observed HTTP sends and one SDK attempt; auth/lower-transport resend paths match their admitted ceilings |
| T-CX311 | Connect failure, send failure, cancellation, and lost response preserve dispatched counts and unknown usage; never fabricate zero |
| T-CX312 | Usage totals are typed/nonnegative/consistent; cache and reasoning details are not double-counted; missing/malformed usage is explicit |
| T-CX313 | Partial known usage stays separate from total and reserved exposure; missing events, overflow, callback failure, and cap violations block acceptance |
| T-CX314 | Fresh per-slot binding has no cross-slot events; timed-out worker cannot fake drain; late events persist and prevent another slot |
| T-CX315 | Relabeled Scripted, injected fake, mock native SDK, and caller-forged capability/online flags remain inadmissible for scored product |
| T-CX316 | SDK and HTTP units remain distinct; derived numeric budgets include every resend path and token-bound scope; unknown factors fail closed |
| T-CX317 | Candidate binds real independent review, model, proof, code/dependencies and resource versions; tampering and fixture-only budget helpers fail production validation |
| T-CX318 | Full offline schedule retains timing/matching/quality/denominators, zero real provider calls, historical preservation and package boundaries |

SDK-specific tests use controlled offline transports and credentials that cannot
reach a provider. A fail-on-call provider spy covers the study schedule itself.
Testing the canonical real-SDK observer through mocks is capability evidence
only; those artifacts never enter scored product ingestion.

Implementation acceptance later requires focused and cumulative pytest, Ruff,
mypy, architecture checks, and diff checks under AGENTS.md. A passing suite
cannot substitute for provider/token proof, identity acceptance, or a grant.
This design-only deliverable does not claim those implementation checks ran.

## 11. Concrete remaining blockers

This design resolves how facts and observations are admitted. It does not claim
that the required external facts or implementation already exist. Seal/execution
remain blocked until all applicable items below are closed:

| Blocker | Closure evidence |
|---|---|
| `unaccepted_provider_model_mapping` | Operator accepts the current requested-name/declared-route binding and stated identity limitations |
| `unbound_sdk_transport_identity` | Exact target environment and audited native transport dependency/source identity |
| `unproved_http_send_bound` | Complete redirect/authentication/lower-transport proof and corresponding observed dispatch tests |
| `unknown_input_token_bound` / `unproven_failed_attempt_token_bound` | Finite reachable-message/framing proof or an applicable all-outcome provider exposure cap |
| `unknown_output_token_bound` | Applicable output/omission bound for the accepted provider path |
| `unavailable_retry_telemetry` | Canonical opt-in observer implemented and independently validated offline, with all count layers |
| `unbound_label_review` | Accepted independent review linked to the exact candidate label/input population |
| `unverified_resource_candidate` | Source-aware arithmetic, evidence and identity verification passes without fixture shortcuts |

The numerical budget may remain operationally unattractive even after it is
finite. Accepting it is a separate operator decision. If proof cannot close
without changing product request semantics, return for a separate product
design rather than loosening a resource gate.

## 12. Authorization boundaries

The proposed sequence is:

1. Review this design, including source-aware defaults and the provider identity
   decision. Approval does not clear current gates.
2. Separately authorize an implementation plan for additive definitions,
   observation, budget/admission validation, and offline acceptance.
3. Separately authorize the named definitions and offline implementation scope.
   Register additive CONTRACTS/TEST_PLAN text before behavior changes. This
   scope must explicitly cover private agent observation changes.
4. Independently review implementation and a fully bound unsealed candidate.
   Commit/push, formal seal, and RealLLM each require their own grants.

The next recommended authorization after design acceptance is
`授权 token／transport telemetry writing-plans only`.

No step authorizes a fixed product route, planner replacement, explicit product
request caps, threshold changes, or modification of frozen V0.2 §§1–64. The
1% clipping and 5% THD values remain demonstration thresholds. Dev_1 formal
dominance remains unaccepted; its machine enum and evidence remain archival.

## 13. Source anchors

All source paths and line numbers in this document use the merged baseline
`fb3a71b400bccd8891f89006e3b72f847b83d17d`, not the older local checkout.
Representative immutable links are:

- [§20.5–20.7: resource metrics, bounds and authority](https://github.com/wfengq/signal-diagnosis-agent/blob/fb3a71b400bccd8891f89006e3b72f847b83d17d/docs/CONTRACTS_V0_3_CONTEXTUAL.md#L885).
- [T-CX299–302](https://github.com/wfengq/signal-diagnosis-agent/blob/fb3a71b400bccd8891f89006e3b72f847b83d17d/docs/TEST_PLAN_V0_3_CONTEXTUAL.md#L230).
- [Merged budget audit](https://github.com/wfengq/signal-diagnosis-agent/blob/fb3a71b400bccd8891f89006e3b72f847b83d17d/docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_2/BUDGET_BOUNDS.md).
- [Planner request construction](https://github.com/wfengq/signal-diagnosis-agent/blob/fb3a71b400bccd8891f89006e3b72f847b83d17d/src/signal_diag/agent/planner.py#L420).
- [Runtime turn boundary](https://github.com/wfengq/signal-diagnosis-agent/blob/fb3a71b400bccd8891f89006e3b72f847b83d17d/src/signal_diag/agent/runtime.py#L179).
- [Adapter provenance boundary](https://github.com/wfengq/signal-diagnosis-agent/blob/fb3a71b400bccd8891f89006e3b72f847b83d17d/src/signal_diag/app/planner_ablation_v2_adapter.py#L196).
- [Current limits gate](https://github.com/wfengq/signal-diagnosis-agent/blob/fb3a71b400bccd8891f89006e3b72f847b83d17d/src/signal_diag/evaluation/planner_ablation/v2/campaign.py#L131).
- [Seal readiness and fixture helper](https://github.com/wfengq/signal-diagnosis-agent/blob/fb3a71b400bccd8891f89006e3b72f847b83d17d/src/signal_diag/evaluation/planner_ablation/v2/sealing.py#L404).
