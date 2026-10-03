# S1 planner-ablation token and transport telemetry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. The operator's execution method takes precedence; this header does not authorize execution or delegation.

**Goal:** Add offline-verified observation and source-aware resource admission for dev_2 while preserving product requests and retaining every unresolved seal/execution blocker.

**Architecture:** An opt-in agent observer emits immutable events to an app-owned per-slot collector. Evaluation validates serialized observations and admitted bound proofs without importing app composition or the provider SDK. A versioned resource extension joins the existing dev_2 candidate and campaign; dev_1 and default product behavior remain unchanged.

**Tech Stack:** Existing Python >=3.11, Pydantic 2, pytest/pytest-asyncio, Ruff, mypy, and the executor's existing OpenAI-compatible SDK/native transport. No dependency installation, upgrade, new product caps, or live API probes are included.

**Spec:** `docs/superpowers/specs/2026-10-01-s1-planner-ablation-token-transport-telemetry-design.md`, approved on 2026-10-01. SHA-256 after approval metadata: `6a6652c0dc03cf454b22983772f34604ed6731fcc04e770578ae298f426571ef`. The reviewed pre-approval content had SHA-256 `e0fd80a48ed80cc33f184f43bc3e82b4e25488280ba760598eafb2e1265c8014`; only approval metadata changed.

**Status:** plan awaiting review. Current grant is `授权 token／transport telemetry writing-plans only`. No task below is authorized for execution by this document.

## Global constraints

- Source baseline is PR #19 merge `fb3a71b400bccd8891f89006e3b72f847b83d17d`. The writing checkout is older, `9931875`; execute only from a clean checkout containing that merge and both complete telemetry documents. Preserve unrelated user work.
- Keep `study_s1_planner_ablation_dev_2`, scorer `signal_diag.planner_ablation_scoring` version `2.0.0-dev.1`, 114 scheduled slots including 57 product slots, existing aliases/oracles/U/C/G, decision bands, and `encoded_bytes_to_terminal_v1` unchanged.
- Resource policy is `planner_ablation_resource_v1`; proposed telemetry schema is `planner_ablation_telemetry_v1`. These names require Task 1 registration before implementation. No numeric limit is frozen by this plan.
- Preserve exact `RealLLMPlanner`, public constructors/builders, prompt/settings, runtime budgets, fresh-client construction, and native timeout/retry/redirect/authentication/proxy/TLS/lifetime behavior. Observation defaults off.
- Preserve frozen V0.2 §§1–64, historical baselines, accepted bundles and dev_1 reproducer. Demonstration thresholds remain demonstration thresholds.
- `agent` must not import `evaluation` or `app`; `evaluation` must not import `app` or construct/call the provider SDK for this feature. SDK-dependent observation belongs at the agent provider boundary.
- Defaults never make existing `*_explicit` flags true. Unknown usage never becomes zero. Known usage, exact totals, and potential token exposure remain separate quantities.
- All offline sessions, Scripted paths, injected clients, mock native transports and synthetic fixtures remain `harness_only`. Caller booleans and class-name strings cannot elevate them.
- No formal seal, provider `/models` call, connectivity probe, warm-up, RealLLM campaign, product replacement, explicit product request cap, commit, push or merge is authorized. Existing synthetic seal tests may use pytest temporary directories under a later offline implementation grant; repository evidence roots remain unwritten.
- If observation or finite token-bound proof cannot preserve the approved semantics, record a blocker and stop that admission path. Do not switch to explicit product caps, package upgrades, or looser gates.

## Review focus

1. SDK versions can share a name while using different native HTTP implementations. Bind the installed dependency/source tuple and reject unsupported profiles (Tasks 2 and 4).
2. `RecordingPlanner` hides the executing planner from runtime. Forward the private observer without importing evaluation into agent or counting wrapper/factory events twice (Tasks 3 and 5).
3. A received completion can consume tokens and then fail JSON validation; a 500 or lost response can consume unknown tokens. Retain both cases without inventing totals (Tasks 4 and 5).
4. Terminal readiness can precede worker drain. Retain late events, keep the authoritative timer, and forbid the next slot when the ledger cannot close (Task 5).
5. A complete-looking budget object, mock SDK, or approval boolean can bypass an old gate. Verify proof/identity/review bindings independently at candidate, preflight, ingestion and decision boundaries (Tasks 2, 6 and 7).

## Baseline, authorization stages and file map

At the inspected baseline, CONTRACTS ends at §20 and test definitions at
T-CX302. Task 1 proposes §21 and T-CX303–318. Reconcile collisions against the
execution baseline before editing; do not overwrite an existing definition.

| Stage | Deliverable | Authority |
|---|---|---|
| Current | This plan plus design approval metadata | Writing-plans only |
| Definitions | Task 1, additive §21/test definitions | Separate grant after plan review |
| Offline implementation | Tasks 2–7, including private agent changes and wrapper forwarding | Separate grant explicitly naming that scope; may be combined with definitions only after plan acceptance |
| Independent review | Implementation, real evidence and remaining blockers | Does not authorize seal or execution |
| Later operations | Commit/push; concrete candidate acceptance; formal seal; RealLLM | Separate grants for each operation |

Tasks run in order. Task 2 may finish with documented unknown external bounds;
Tasks 3–7 can still prove observation offline. That outcome is a valid offline
deliverable, but cannot be reported as budget closure or seal readiness.

| Files to create or modify under a later grant | Responsibility |
|---|---|
| `docs/CONTRACTS_V0_3_CONTEXTUAL.md`; `docs/TEST_PLAN_V0_3_CONTEXTUAL.md` | §21 and T-CX303–318 definitions |
| `src/signal_diag/agent/telemetry.py` | New stdlib-only events, observer/binding protocols and safe emission |
| `src/signal_diag/agent/provider_telemetry.py` | New private version-bound SDK/native transport observation; SDK import remains lazy |
| `src/signal_diag/agent/planner.py`; `src/signal_diag/agent/runtime.py` | Default-off canonical binding, turns, calls, usage and repair events |
| `src/signal_diag/evaluation/recording.py` | Private transparent observer forwarding through the existing wrapper |
| `src/signal_diag/app/planner_ablation_v2_adapter.py` | Per-slot collector, executed-instance binding, run/lifecycle/provenance mapping |
| `src/signal_diag/evaluation/planner_ablation/v2/resource_models.py` | New strict source-bound facts, ledger, capability and extension types |
| `src/signal_diag/evaluation/planner_ablation/v2/resource_budget.py`; `resource_telemetry.py` | New pure bound derivation and event/usage aggregation |
| `src/signal_diag/evaluation/planner_ablation/v2/models.py`, `timing.py`, `campaign.py`, `scoring.py`, `decision.py`, `provenance.py`, `sealing.py`, `__init__.py` | Additive version dispatch, session capability, campaign integration, resource prerequisites and verification; quality arithmetic stays unchanged |
| `scripts/run_planner_ablation_v2.py`; `scripts/seal_planner_ablation_v2.py` | Resource-aware refusal/validation; online runner stays disabled; no automatic generation |
| `tests/agent/test_telemetry.py`; `test_provider_telemetry.py`; `test_runtime_telemetry.py`; existing `test_real_llm_planner.py` | Agent observation and semantic parity |
| `tests/evaluation/test_recording.py`; `tests/app/test_planner_ablation_v2_adapter.py` | Wrapper and real-service proof |
| `tests/evaluation/planner_ablation/v2/test_resource_budget.py`; `test_resource_telemetry.py`; existing campaign/decision/sealing/offline tests | Pure budget, ledger, candidate and end-to-end gates |
| `tests/test_architecture_boundaries.py` | Exact additive authorization paths, imports and historical preservation |
| `docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_2/RESOURCE_BOUNDS.md`; existing `OFFLINE_ACCEPTANCE.md` | Unsealed audit/acceptance evidence and unresolved blockers |

Names without a directory in a table cell use that cell's preceding directory.
All `resource_*` types are study-owned. Agent events use frozen dataclasses with
primitive fields, not study models. Avoid unrelated file splits or exports.

## Interfaces fixed by this plan

These interfaces are future additions. They do not change frozen public product
signatures. Study model types use strict validation, `extra="forbid"`, finite
numbers, and canonical JSON for digesting.

| Interface | Owner and contract |
|---|---|
| `TelemetryBinding` | `agent/telemetry.py`: slot-local identity, monotonic clock, bounded nonthrowing sink, current turn/call/attempt associations; no oracle fields |
| `TelemetryEvent` | Tagged frozen union of turn/call/repair/SDK/send/usage start/end observations; sequence and parent IDs; typed outcome; no raw content |
| `SdkObservationProfile` / `ClientObservationDescriptor` | Agent stdlib descriptors: exact SDK/native/source identity and hook/default audit fields; actual canonical/mock/injected origin and unsupported blockers |
| `emit_safely(binding: TelemetryBinding, event: TelemetryEvent) -> None` | Agent: callback errors latch invalidity in the binding and never change planner/runtime control flow |
| `bind_planner_telemetry(planner: RealLLMPlanner, *, binding: TelemetryBinding) -> None` | `agent/planner.py`: exact type, idle and not already bound; sets private `_planner_telemetry_binding`, leaves `_client` untouched |
| `get_planner_telemetry_binding(planner: object) -> TelemetryBinding \| None` | Agent: reads the private opt-in forwarding protocol only, with no wrapper-class import or arbitrary object traversal |
| `_create_async_openai_client(*, api_key: str, base_url: str, binding: TelemetryBinding \| None = None, profile: SdkObservationProfile \| None = None) -> _ChatClient` | Existing private factory gains opt-in parameters; unobserved callers keep exactly their old argument and construction path |
| `SdkProfileAudit` | Study: exact installed versions/source hashes, native family, proven hook points/defaults/resend paths, supported status and blockers |
| `BoundFact` / `ResourceProofBundle` | Study: strict value/unit/origin plus code/dependency/model/proof bindings and independent acceptance references |
| `assess_resource_budget(config: EffectiveConfiguration, proofs: ResourceProofBundle, capability: ObservationCapability \| None) -> ResourceAssessment` | `resource_budget.py`: pure derivation; absent capability/proof blocks; names logical/SDK/HTTP/token units separately |
| `attach_sdk_observation(client: object, *, binding: TelemetryBinding, profile: SdkObservationProfile) -> ClientObservationDescriptor` | Private agent provider module: validates the serialized profile's exact installed identity before attaching per-instance observation; no study imports |
| `StudyResourceObserver(binding: TelemetryBinding)` | App: thread-safe collector; factory diagnostics separate from turn/call counts |
| `StudyResourceObserver.resource_snapshot(*, worker_drained: bool) -> SlotResourceLedger` | App: closed ledger only when drained; otherwise explicit pending events and invalid/incomplete state |
| `ResourceObservedSession.resource_snapshot(*, worker_drained: bool) -> SlotResourceLedger` | New additive protocol in `v2/timing.py`, extending `ArmSession`; leave the original protocol unchanged |
| `aggregate_resource_ledger(ledger: SlotResourceLedger, *, assessment: ResourceAssessment) -> ResourceObservation` | `resource_telemetry.py`: pure validated counts, known usage subtotal, exact/unknown totals, conservative exposure and blockers |
| `evaluate_prerequisites(study: VerifiedStudyV2, records: Sequence[StudyTerminal], *, campaign: CampaignRecord \| None = None) -> PrerequisiteReport` | Existing `scoring.py` function with an additive optional campaign input; resource-policy studies require its bound slot ledgers, not just terminal records |
| `ResourceCandidateExtension` | Study: resource/schema versions, accepted proofs, capability, provider/dependency identity, label-review binding, derived assessment and digest |
| `SlotResourceLedger` / `ResourceObservation` / `ResourceCandidateValidation` | Study models: validated events and closure; counts/known subtotal/exact-or-unknown totals/exposure/blockers; recomputed candidate readiness/reasons |
| `validate_resource_candidate(candidate: CandidateManifestV2, *, repository_root: Path) -> ResourceCandidateValidation` | `sealing.py`: recomputes bytes and resource proofs; no SDK client or seal write |

`SdkProfileAudit` in the study has a primitive serialization. The agent consumes
an equivalent stdlib descriptor with the same fields, not that Pydantic class.
The agent type is named `SdkObservationProfile`; `attach_sdk_observation` takes
that descriptor at the agent boundary. App performs the checked conversion.
No cross-layer type alias
may import the study back into agent.

## Task 1: Register additive resource definitions and preservation scope

**Files:** Modify only `docs/CONTRACTS_V0_3_CONTEXTUAL.md` and
`docs/TEST_PLAN_V0_3_CONTEXTUAL.md` under a later definitions grant.

**Consumes:** Approved design, this plan, §20, current T-CX289–302.
**Produces:** §21, reconciled T-CX303–318, and the exact scope for later guard
updates. No test implementation changes or implementation semantics hidden
in a definitions-only stage.

- [ ] Re-read AGENTS and its required product documents, both complete telemetry documents, and the clean execution baseline. Hash both documents and record the exact baseline. A missing file/hash mismatch stops work; do not reconstruct text from a chat summary.
- [ ] Add §21 covering event units, unknown/partial usage, source-aware default admission, default-off agent/wrapper observation, resource failures, provider identity, proof/capability/candidate validation and separate authority.
- [ ] Register the proposed IDs using the mapping below. Keep T-CX299's requirement for actual telemetry; no ceiling-only exception.
- [ ] Record the later T285 additions as exactly `src/signal_diag/agent/telemetry.py`, `src/signal_diag/agent/provider_telemetry.py`, and `src/signal_diag/evaluation/recording.py`. Existing planner/runtime paths are already additive-authorized but still require this feature's grant. Do not authorize whole agent/evaluation directories.
- [ ] Record `RESOURCE_BOUNDS.md` as the only new dev_2 evidence document permitted in this scope. Retain the `protocol_seal/` prohibition and all preserved digests. The actual test allowlist changes occur in Tasks 2 and 3, not this definitions-only stage.
- [ ] Verify definition coverage, unchanged earlier sections/IDs, and `git diff --check`. Optionally run the unchanged architecture tests read-only; no implementation check is claimed for the new definitions. This stage changes no code or executable tests.

| ID | Owning tasks | Definition |
|---|---|---|
| T-CX303 | 2 | Honest origins/default flags; unknown and legacy gates remain blocked |
| T-CX304 | 2, 4 | Actual SDK/native transport/source identity; dependency drift rejected |
| T-CX305 | 2, 6 | Requested/declared/returned model policy and acceptance binding |
| T-CX306 | 3, 4, 5 | Observation on/off preserves payload, planner type, diagnosis and exception behavior |
| T-CX307 | 2, 3, 5 | Actual turns/calls, no factory/wrapper double counts; conditional control-flow ceiling |
| T-CX308 | 3 | All parse/reject budget-consumption events; SDK retries are separate |
| T-CX309 | 4 | 500/500/200 attempt trace and usage before planner parsing |
| T-CX310 | 4 | Redirect/send/authentication/lower-transport units and bounds |
| T-CX311 | 4, 5 | Failure/cancellation/lost-response observations and unknown tokens |
| T-CX312 | 4, 5 | Strict usage validation, subdivisions and missing data |
| T-CX313 | 5 | Incomplete/invalid ledger, partial totals and bound violations |
| T-CX314 | 5 | Slot isolation, late callbacks and real worker drain |
| T-CX315 | 6 | Fixture/Scripted/fake/native-mock/forged-context ingestion rejection |
| T-CX316 | 2, 5 | Derived SDK/HTTP/token budgets and fail-closed unknown factors |
| T-CX317 | 6 | Full candidate/review/proof/code/dependency binding; no synthetic shortcuts |
| T-CX318 | 7 | Offline schedule, zero live calls, historical/package preservation |

## Task 2: Model source-aware bounds and audit the actual environment

**Files:** Create `.../v2/resource_models.py`, `resource_budget.py`,
`tests/evaluation/planner_ablation/v2/test_resource_budget.py`, and
`.../study_s1_planner_ablation_dev_2/RESOURCE_BOUNDS.md`; modify the exact document
whitelist in `tests/test_architecture_boundaries.py`. The last document path expands
under `docs/evaluations/v0_3/planner_ablation/`.

**Consumes:** `EffectiveConfiguration`, existing budget audit, exact installed
environment/source files and approved provider documents.
**Produces:** `SdkProfileAudit`, `BoundFact`, `ResourceProofBundle`,
`ObservationCapability`, `ResourceAssessment`, `SlotResourceLedger`,
`ResourceObservation`, `ResourceCandidateExtension`, `ResourceCandidateValidation`,
and `assess_resource_budget`. Define their strict schemas here; later tasks
produce and validate instances without renaming them.

- [ ] Write `test_audited_defaults_do_not_set_explicit_flags`, `test_unknown_origin_or_scope_blocks_budget`, `test_sdk_ceiling_is_not_http_ceiling`, `test_context_capacity_does_not_prove_failed_attempt_exposure`, and `test_dependency_or_model_binding_drift_blocks_admission`.

  Core assertions are:

  ```python
  assert config.request_timeout_explicit is False
  assert config.transport_retry_override_explicit is False
  assert assessment.sdk_attempt_ceiling == 57 * 28 * 3
  assert assessment.http_send_ceiling is None  # no admitted H proof
  assert assessment.execution_blocked is True
  assert "unproven_failed_attempt_token_bound" in assessment.blockers
  ```

  Fixtures explicitly use synthetic reviewed facts and remain fixture-only;
  they do not make the real candidate ready.
- [ ] Run `python -m pytest tests/evaluation/planner_ablation/v2/test_resource_budget.py -q`; confirm missing source-aware validation fails before implementation.
- [ ] Implement the strict models and pure arithmetic `57 * P * A * H`, then HTTP ceiling times each admitted per-send input/output ceiling. Reject nonpositive count factors, booleans as integers, nonfinite values, unit mismatches, unsupported scope, missing proof acceptance and identities that disagree.
- [ ] Read the executor's actual distributions/source without requests or installation. Record SDK, native HTTP/core dependencies, authentication mode, effective timeout phases/retries/redirects, lower-level resend behavior, source hashes and candidate hook locations. The Cloud audit's `3.20.0` and lockfile's `3.6.0` are evidence, not interchangeable pins. An unaudited installed tuple is unsupported.
- [ ] Prove all current runtime continue paths for the conditional 28-turn ceiling. Bind default AgentLimits, v9.11 policy and source digest. A new uncovered branch invalidates the proof; do not repair it by adding a runtime cap.
- [ ] Record provider requested-name/declared-route and output-omission evidence. Keep concrete model acceptance pending until explicitly given. Either provide an applicable all-outcome token cap or a reviewed serializer/tokenizer/framing/reachable-context proof. If neither exists, retain input/failed-attempt blockers. Character ratios and context capacity alone cannot clear them.
- [ ] Write `RESOURCE_BOUNDS.md` with exact facts, units, source/proof hashes, derivation and remaining blockers. No production manifest, numeric protocol freeze or affirmative seal-readiness record is created. Verify the focused tests pass and the legacy `inspect_limits(snapshot_effective_configuration())` remains blocked.
- [ ] Add only that document name to the dev_2 whitelist under the offline grant, preserving the no-seal assertion. Run the architecture test and diff check; do not replace any historical hash to accommodate a change.

## Task 3: Observe canonical turns and runtime repair through the wrapper

**Files:** Create `src/signal_diag/agent/telemetry.py`,
`tests/agent/test_telemetry.py`, `test_runtime_telemetry.py`; modify agent
`planner.py`, `runtime.py`, evaluation `recording.py` and
`tests/evaluation/test_recording.py`, plus the exact T285 additions in
`tests/test_architecture_boundaries.py` registered by Task 1.

**Consumes:** Primitive observer/profile descriptors, existing runtime and wrapper.
**Produces:** Frozen `TelemetryEvent`, `TelemetryBinding`, `emit_safely`, binding
helper/getter, stdlib profile/client descriptors and the private wrapper forwarding property. SDK integration comes
in Task 4; default-off product construction remains identical now.

- [ ] Write `test_factory_probes_are_not_turns`, `test_recording_wrapper_forwards_binding_without_extra_turn`, `test_parse_and_reject_consumption_emit_repairs`, `test_exhausted_retry_does_not_emit_another_consumption`, `test_observer_failure_preserves_product_exception`, and `test_unbound_default_constructor_is_unchanged`.

  For a runtime path with two repair continues and a final budget exhaustion:

  ```python
  assert resource_counts.repair_attempt_count == 2
  assert resource_counts.planner_turn_count == 3
  assert result.termination_reason == "max_planner_retries"
  assert "planner_attempt_count" not in type(result).model_fields
  ```

- [ ] Run `python -m pytest tests/agent/test_telemetry.py tests/agent/test_runtime_telemetry.py tests/evaluation/test_recording.py -q`; confirm missing event/binding behavior fails.
- [ ] Add default-None `_planner_telemetry_binding` without changing `RealLLMPlanner.__init__`. Bind only an idle exact `RealLLMPlanner`; reject a second binding or subclass. Emit turn start/end from the actual `decide` entry including early configuration failure and cancellation.
- [ ] Define event variants `PlannerTurnEvent`, `LogicalCallEvent`, `RepairEvent`, `SdkAttemptEvent`, `HttpSendEvent`, and `UsageObservation`. Begin/end events share a correlation ID but have distinct sequence IDs and phases; only duplicate sequence IDs or duplicate phases are invalid. Define the primitive profile/client descriptors for Task 4. Runtime repair events refer to the binding's actual current/last turn, including parse failures.
- [ ] Add only Task 1's exact agent/wrapper paths to T285's additive authorization list. Add tests for stdlib-only event types and agent not importing app/evaluation. Keep historical asset digests and all existing checks intact.
- [ ] Add a private read-only forwarding property with the same name to `RecordingPlanner`, returning the inner planner's binding via the agent protocol. Keep wrapper records, provider-usage behavior, constructor and validation unchanged. Runtime reads only that lower-layer protocol; it never imports or inspects `RecordingPlanner` by name.
- [ ] Emit `RepairEvent` exactly when the parse-error branch decrements `planner_retries_remaining` and when `_reject_decision` returns a consuming continue. Keep state/result fields and rejection messages unchanged. Terminal exhaustion is a turn failure, not another consumed repair.
- [ ] Ensure callback errors and full buffers latch invalidity without throwing into product control flow. Test arbitrary callback failure on both success and product exception paths, with the same decision/exception before and after observation.
- [ ] Re-run the focused command plus `tests/agent/test_real_llm_planner.py` and `tests/test_architecture_boundaries.py`; expected no double counts or reverse imports.

## Task 4: Observe the real SDK path and native dispatch without changing it

**Files:** Create `src/signal_diag/agent/provider_telemetry.py` and
`tests/agent/test_provider_telemetry.py`; modify the private planner client factory
and request block in `agent/planner.py`, plus `test_real_llm_planner.py`.

**Consumes:** Task 2 exact audited profile, Task 3 binding/events.
**Produces:** `attach_sdk_observation(..., profile: SdkObservationProfile)` and
`ClientObservationDescriptor`; logical call, SDK attempt, HTTP dispatch and usage
events from the canonical SDK, with no `_client` fake injection.

- [ ] Write `test_retry_three_attempts_one_call`, `test_redirect_four_sends_one_sdk_attempt`, `test_usage_survives_invalid_planner_json`, `test_lost_response_has_unknown_usage`, `test_pre_dispatch_sdk_failure_is_not_zero_turns`, `test_observed_and_unobserved_sdk_requests_match`, and `test_unsupported_sdk_profile_latches_blocker`.

  With native offline transports and the audited default SDK retries:

  ```python
  assert retry_trace.logical_call_count == 1
  assert retry_trace.sdk_attempt_count == 3
  assert redirect_trace.sdk_attempt_count == 1
  assert redirect_trace.http_send_attempt_count == 4
  assert invalid_json_trace.reported_usage.total_tokens == 26
  assert lost_response_trace.exact_total_tokens is None
  assert lost_response_trace.http_send_attempt_count >= 1
  ```

  The fixtures provide prompt=16 and completion=10 for the invalid-JSON response.
  HTTP error responses without usage remain unknown; the 500/500/200 case does
  not imply exact usage for all three attempts.
- [ ] Run `python -m pytest tests/agent/test_provider_telemetry.py tests/agent/test_real_llm_planner.py -q`; verify missing capture fails.
- [ ] Extend only the private factory with an optional binding/profile. With observation off, execute the existing `AsyncOpenAI(api_key=..., base_url=...)` path unchanged. With it on, construct that same concrete SDK first and attach audited per-instance delegated callbacks to its existing native client. Do not replace the planner, SDK retry loop, native transport, or lifetime policy.
- [ ] Implement one explicitly audited profile, not a generic version guess. For the 3.20.0 candidate, audit per-loop `_prepare_options` entry, `_send_request` exit, and the native transport's single-dispatch hook. Confirm those points against installed source; preparation/build failures must close a zero-send SDK attempt. The retry header is only a cross-check. If no preserving callback/delegation can observe those points, retain `unavailable_retry_telemetry`; no class/global patch, SDK subclass or alternate client is the fallback.
- [ ] Emit logical-call start before `chat.completions.create`; end in `finally`. Extract allowlisted response usage/model/fingerprint metadata before empty-content and planner JSON validation. Do not read/consume HTTP bodies in an observation hook or alter SDK response parsing.
- [ ] Cover connect/send exceptions, cancellation, redirect exhaustion, retryable response, malformed usage, auth resend policy, and lower-transport request replay. Close the last dispatched send on error while retaining unknown receipt/usage. Connection-only retries are separate diagnostics. Unsupported replay paths invalidate the profile instead of being hidden.
- [ ] Compare observation on/off request bodies, settings, SDK headers excluding naturally generated opaque IDs, effective timeout/retry/redirect/proxy/TLS values, client lifetime and returned exceptions. Test the same empty/invalid content and typed transport errors. Observation may add elapsed overhead; it must not change request semantics. Re-run the focused command and archive the exact tested dependency/profile identity as offline capability evidence.

SDK private callbacks are version-sensitive. The source audit and profile tests
are a prerequisite for support, not permission to alter installed SDK source.
The 3.20.0 audit candidate uses the official
[SDK request implementation](https://github.com/openai/openai-python/blob/v3.20.0/src/openai/_base_client.py).
That source places preparation and sending inside its retry loop; it does not
prove the executor's installed native transport hooks or defaults.

## Task 5: Close per-slot ledgers and enforce resource failure accounting

**Files:** Modify app adapter and its test; create `.../v2/resource_telemetry.py`
and `tests/evaluation/planner_ablation/v2/test_resource_telemetry.py`; modify
v2 `models.py`, `timing.py`, `campaign.py`, `scoring.py`, `decision.py`, and related existing tests.

**Consumes:** Agent event stream, audited assessment/capability, full existing slot
schedule and contextual service entry.
**Produces:** `StudyResourceObserver.resource_snapshot`, `aggregate_resource_ledger`,
resource sidecars on slot records, explicit resource-stop reason and prerequisite.

- [ ] Write `test_real_service_wrapper_emits_turn_and_repair`, `test_slot_ledger_rejects_orphan_duplicate_and_missing_end`, `test_usage_totals_and_subdivisions_are_strict`, `test_partial_usage_is_not_exact_campaign_total`, `test_late_callback_prevents_next_slot`, `test_valid_diagnosis_survives_resource_stop`, and `test_fixed_arm_zero_requires_no_provider_path`.

  Required assertions include:

  ```python
  assert partial.reported_usage_subtotal.total_tokens == 26
  assert partial.exact_total_tokens is None
  assert partial.acceptance_blocked is True
  assert stopped.slot_records[0].terminal.outcome == original_outcome
  assert all(slot.status == "unstarted" for slot in stopped.slot_records[1:])
  assert prerequisites.resource_observation_ok is False
  ```

  `prerequisites` is the independently derived `PrerequisiteReport` from the
  resource-aware `evaluate_prerequisites`, not a caller-supplied acceptance flag.
- [ ] Run `python -m pytest tests/evaluation/planner_ablation/v2/test_resource_telemetry.py tests/evaluation/planner_ablation/v2/test_campaign.py tests/app/test_planner_ablation_v2_adapter.py -q`; confirm missing slot/resource enforcement fails.
- [ ] Create a thread-safe bounded collector for the slot before submission. In the executing tracking factory, bind the exact planner only while idle; leave construction probes unbound. Use one monotonic clock and checked primitive-to-study conversion. Preserve complete contextual kwargs and waiter, fresh repository and deterministic guidance.
- [ ] Associate the service run ID when actually available; keep slot-local IDs beforehand. A study-generated failure terminal ID must not masquerade as an observed service run ID. Proven pre-submission failure can be represented as `run_not_created`; otherwise an unknown/conflicting association blocks telemetry.
- [ ] Add `ResourceObservedSession` with the study-only `resource_snapshot` method; keep `ArmSession` unchanged. App sessions implement the added capability, consumed after `_dispatch_slot` drain/teardown. Keep missing capability unknown. Replace the campaign's current unconditional unknown collection only on the resource-policy path; retain legacy collection behavior and fixed zero-use proofs.
- [ ] Validate strict integer usage, total/subdivision arithmetic, event ordering/parents, dispatch/response correlation, pending calls, overflow/callback failures and ceiling violations. Compute exact totals only with complete usage or admitted zero-use proof; otherwise expose known subtotal and reserved ceilings independently. Never persist raw payloads/exception strings in the resource sidecar.
- [ ] Project proven turn count into existing `ResourceTelemetry.planner_call_count`, consumed repairs into `repair_attempt_count`, and exact-or-unknown token totals into the old token fields. Keep ambiguous nonzero `transport_attempt_count` unknown rather than silently redefining it; the new sidecar carries both `sdk_attempt_count` and `http_send_attempt_count`. Resource-policy prerequisites validate those named units; legacy consumers retain their old fail-closed path. Proven fixed-arm zeros may project as zero in both representations.
- [ ] Stop before the next slot on resource invalidity/incomplete usage or model-policy drift. Add typed `resource_stopped` campaign status and reason without relabeling a valid diagnosis as behavioral failure. Preserve full schedule, quality denominators, terminal outcome and late/pending ledger. Resource failure blocks accepted decision through a new derived prerequisite, including a last-slot failure that otherwise looks fully completed.
- [ ] Extend `evaluate_prerequisites` in `scoring.py` with the optional campaign input defined above. Add `PrerequisiteReport.resource_observation_ok: bool | None = None`; None denotes the legacy path and never satisfies a resource-policy study. A resource-policy `VerifiedStudyV2` requires the bound full campaign, one matching resource ledger per slot, matching terminal/run associations, recomputed aggregates and all closed resources. Missing campaign/ledger or terminal-only projection derives False; legacy studies keep their existing path. Include that derived result in `all_passed` and decision reason codes without changing quality/usefulness/population calculations.
- [ ] Exercise the real background service, wrapper and observer with offline SDK responses. Timeout tests hold a worker pending, cancel the waiter, release late callbacks, and verify drain/stop and no overlap. Observer errors do not escape into product logic. Retain 120-second outer deadline, authoritative shared interval and observation overhead; do not subtract late drain time from latency or add it to an already closed terminal interval.
- [ ] Re-run focused tests and existing v2 decision/timing/scoring tests. Expected unchanged quality/utility arithmetic, report matching and accepted outcomes on complete valid resources; negative resource cases yield `insufficient_evidence`.

## Task 6: Verify resource candidates and provenance without enabling execution

**Files:** Modify v2 `sealing.py`, `provenance.py`, `models.py`, `__init__.py`,
both v2 scripts and `test_sealing.py`; add resource/provenance cases to v2
`test_offline_acceptance.py` and the app adapter test.

**Consumes:** Admitted proofs, exact offline capability, current approved label
review, code/dependency snapshots and Task 5 resource observations.
**Produces:** `ResourceCandidateExtension`, `validate_resource_candidate`,
resource-version dispatch and stricter admission/preflight/readonly verification.
The online script remains a refusal entry point in this scope.

- [ ] Write `test_fixture_budget_cannot_make_production_candidate_ready`, `test_label_review_binds_exact_population`, `test_resource_source_or_dependency_tamper_rejected`, `test_native_mock_cannot_be_relabelled_online`, `test_class_name_and_booleans_do_not_authenticate_path`, and `test_readonly_verification_never_writes`.

  Required negative cases include changing any proof, label-review, oracle,
  input, SDK source, model mapping or observation profile digest; missing actual
  review acceptance; an arbitrary nonempty grant string; `_client` injection;
  and an exact `RealLLMPlanner` using a mock native transport.
- [ ] Run `python -m pytest tests/evaluation/planner_ablation/v2/test_sealing.py tests/evaluation/planner_ablation/v2/test_offline_acceptance.py tests/app/test_planner_ablation_v2_adapter.py -q`; confirm old boolean/fixture shortcuts fail the new cases.
- [ ] Add an explicit optional resource extension to unsealed dev_2 candidate/verified-study schemas. Canonical digest, generation validation and readonly verify bind every referenced resource file/value. No extension means legacy behavior for old fixture reproduction, never a ready production resource candidate. Dev_1 code/identity and its byte layout remain untouched.
- [ ] Dispatch candidate readiness by the extension's registered resource policy. New readiness derives from `ResourceCandidateValidation`, approved label/input/code identity and recomputed `ResourceAssessment`; it never calls the legacy explicit-flag gate and flips its result. Keep old `BudgetAssessment` semantics and flags intact. Production dev_2 generation/preflight must require the new validated extension, so omitting it cannot bypass resource checks.
- [ ] Bind actual SDK/native transport/core versions and source digests through read-only distribution metadata/audit facts; do not import SDK clients into evaluation. Bind source-aware limits, capability evidence, requested/declared model policy, timing/drain/usage completeness policy, and code identity including the new agent/wrapper files.
- [ ] Convert the existing approved `LABEL_REVIEW.md` into a checked binding to its source digest and exact oracle/alias/U/C/G/WAV population. Do not rerun label design or accept a caller's `approved=True`. Validate binding mismatch separately from structural label validity.
- [ ] Recompute assessments from approved facts. Keep `make_complete_budget_assessment` fixture-only; synthetic completeness flags or supplied green objects cannot satisfy production preflight/generation. A production candidate with unresolved identities or token bounds stays blocked. Dirty implementation identity cannot be promoted to an immutable candidate; commit authorization is a separate later gate.
- [ ] Add checked actual-class/module/tree and canonical transport descriptors to app provenance mapping. Keep fixture indicators immutable. New resource-policy scored ingestion requires the verified resource context and actual operator authorization evidence in addition to the existing checks. Descriptors and hashes bind managed facts; they do not authenticate arbitrary fabricated provider responses.
- [ ] Preserve public `--online` refusal before SDK construction. Update CLI diagnostics to name resource blockers and distinguish readonly verification from generation; do not add a runnable online entry or consume an environment flag as self-issued permission. Production generation still requires a later grant and refuses every existing destination, including an empty directory.
- [ ] Verify only synthetic test candidates in pytest temporary directories. Assert before/after hashes for readonly verification and historical evidence. No repo `protocol_seal/` directory or formal candidate is generated by this task.

## Task 7: Produce offline acceptance and an honest blocker handoff

**Files:** Existing v2 offline/campaign/decision tests, app integration tests,
`tests/test_architecture_boundaries.py`, `OFFLINE_ACCEPTANCE.md`, and
`RESOURCE_BOUNDS.md`.

**Consumes:** Tasks 1–6 and exact execution-environment evidence.
**Produces:** T-CX303–318 proof map, full offline acceptance, unresolved-blocker
report and a reviewable diff. No automatic post-acceptance operation.

- [ ] Retain the existing 114-slot Scripted/fixed acceptance path without the new resource-policy gate; its product usage remains unknown and never claims SDK capability. Add `test_full_schedule_resource_path_is_harness_only` as a second 114-slot path using the exact canonical planner, real service and controlled offline native SDK transport, with valid mock completion usage. Both paths keep the real-provider boundary fail-on-call and assert zero real calls; every artifact remains non-scored. The second path requires the audited SDK profile to pass, not a Scripted substitution or skip.
- [ ] Assert all scheduled slots and mode/round denominators remain unchanged. Preserve quality/usefulness/completion/guidance arithmetic. Assert a resource failure in the final slot blocks advantage/dominance even when completion remains 114/114.
- [ ] Run focused checks: `python -m pytest tests/agent/test_telemetry.py tests/agent/test_runtime_telemetry.py tests/agent/test_provider_telemetry.py tests/agent/test_real_llm_planner.py tests/evaluation/test_recording.py tests/evaluation/planner_ablation tests/app/test_planner_ablation_v2_adapter.py -q`. Expected all required cases pass without live requests.
- [ ] Run cumulative checks: `python -m pytest -q -rxXs -p no:cacheprovider`; `python -m ruff check --no-cache src tests scripts`; `python -m mypy --no-incremental src`; `python -m pytest tests/test_architecture_boundaries.py -q`; `git diff --check fb3a71b`. Expected zero required skip/xfail, no architecture/type/lint/whitespace failures. Record exact counts, versions and commands rather than borrowing earlier green CI.
- [ ] Confirm public builder/composition/service signatures, product payloads, default-off behavior, frozen V0.2 contract and historical assets remain preserved. Run `python scripts/verify_phase5_wheel.py` for the new packaged agent modules. A release gate additionally requires clean local CPython 3.11/3.12 checks under AGENTS; offline feature acceptance must not falsely claim that release matrix if it was not run.
- [ ] Document each ID's actual test path/name, tested SDK/native transport profile, exact proof sources, real-provider count zero, historical hashes and unresolved resource blockers. Unsupported target SDK or unknown input/output bounds are reported explicitly; no forced green budget or unavailable profile test is hidden behind a skip.
- [ ] Self-review every approved-design section against the coverage table below. Deliver the complete diff and documents to independent Codex review, preserving implementation ownership with the operator's chosen executor. Do not commit/push, generate a formal seal, clear pending model/budget acceptance or run RealLLM.

## Coverage and completion meanings

| Approved design sections | Tasks |
|---|---|
| §1–2 choice, baseline, provider/SDK drift | 1, 2, 4, 6 |
| §3 count hierarchy and usage | 3, 4, 5 |
| §4 private boundaries and worker binding | 1, 3, 4, 5 |
| §5 records, bounded collector, privacy and fixed zero proof | 2, 3, 5 |
| §6–7 origins, token scope and arithmetic | 1, 2, 5 |
| §8 capability, resource stop, drain and timing | 4, 5, 7 |
| §9 provenance, label-review binding and candidate verification | 6 |
| §10 tests and §11 remaining blockers | 1–7 |
| §12 staged authority and §13 source anchors | Current document, Tasks 1 and 7 |

`offline_implementation_accepted` means the observation and validation code is
proved under its named offline profile. `resource_bounds_complete` additionally
requires every admitted numeric/source/model fact. `candidate_verified` also
requires immutable implementation identity and the complete review bindings.
These are separate statuses. None is a seal or a RealLLM grant.

Completion may legitimately leave `unknown_input_token_bound`,
`unproven_failed_attempt_token_bound`, `unknown_output_token_bound`, or
`unaccepted_provider_model_mapping` active. Report that result instead of
claiming the budget is closed. If the implementation cannot preserve canonical
SDK/product semantics, the observation profile is unsupported and needs design
review before any alternative.

## Handoff boundary

Current work ends after this plan is reviewed. The proposed next grant, only
after plan acceptance, is:

`授权 token／transport telemetry definitions + offline implementation，按本计划 Tasks 1–7；包含默认关闭的私有 agent 观测及 RecordingPlanner 转发；不 seal、不 RealLLM、不 commit/push。`

That grant would make Task 1 definitions precede Task 2–7 implementation. If the
operator grants definitions only, stop after Task 1. Historical instruction to
use Cursor does not itself authorize this new scope. No frequent-commit workflow
overrides the separate commit/push requirement.
