"""App-owned v2 study adapters: encoded bytes → StudyTerminal (dev_2 only)."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Literal

from signal_diag.agent.models import (
    AgentRunResult,
    StructuredDiagnosis,
    TaskAssessment,
)
from signal_diag.agent.planner import (
    PlannerModel,
    RealLLMPlanner,
    bind_planner_telemetry,
)
from signal_diag.agent.telemetry import TelemetryBinding, TelemetryEvent
from signal_diag.app.context_guidance import ContextGuidance, build_context_guidance
from signal_diag.app.contextual_models import ContextualAppRunSnapshot
from signal_diag.app.guarded_tools import GuardedSignalToolService
from signal_diag.app.service import (
    ApplicationDependencies,
    DiagnosisApplicationService,
)
from signal_diag.evaluation.models import BaselineRunResult
from signal_diag.evaluation.planner_ablation.baseline import (
    PlannerAblationFixedPipelineBaseline,
)
from signal_diag.evaluation.planner_ablation.models import (
    PlannerAblationBaselineRequest,
    StudyContextGuidanceView,
    StudyObservedFactView,
)
from signal_diag.evaluation.planner_ablation.v2.campaign import (
    _BEHAVIORAL_TERMINATION_MARKERS,
    collect_resource_telemetry,
)
from signal_diag.evaluation.planner_ablation.v2.models import (
    TIMING_CONTRACT_V1,
    ByteRequest,
    ExecutionProvenance,
    FailureCause,
    PhaseMarker,
    PhaseName,
    RequestTiming,
    ResourceTelemetry,
    ScoredArm,
    StudyTerminal,
)
from signal_diag.evaluation.planner_ablation.v2.timing import apply_phase_advance
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.models import RuleProfileLoader
from signal_diag.signal import (
    InMemorySignalRepository,
    build_signal_record,
    extract_segment,
    load_wav_bytes,
)
from signal_diag.signal.context import StimulusContext
from signal_diag.signal.repository import SignalRepository
from signal_diag.tools.service import SignalToolService

_APPROVED_PRODUCT_PLANNER_CLASS = "RealLLMPlanner"
_PRODUCT_RESIDUAL_NOTES = (
    "product_path_includes_preview_and_event_projection_overhead",
    "request_level_system_comparison_not_pure_planner_attribution",
)
_NEUTRAL_TEST_FILENAME = "analysis.wav"
_NEUTRAL_REFERENCE_FILENAME = "reference.wav"
_DEFAULT_ASSESSMENT = TaskAssessment(
    task_type="distortion_analysis",
    objective="determine why the signal sounds distorted",
    hypotheses=("clipping", "harmonic_distortion"),
)
_ExecuteFailureKind = Literal["infrastructure", "behavioral", "unknown"]
_BEHAVIORAL_TERMINATION_REASONS = frozenset(
    {
        "max_tool_calls",
        "max_planner_retries",
        "max_rule_evaluations",
        "max_knowledge_retrievals",
        "no_progress",
    }
)
_INFRASTRUCTURE_APPLICATION_ERROR_CODES = frozenset(
    {"internal_error", "runtime_error", "provider_error"}
)


def _failure_cause_from_product_snapshot(
    snapshot: ContextualAppRunSnapshot,
    result: AgentRunResult | None,
) -> tuple[Literal["completed", "failed"], FailureCause | None]:
    diagnosis = result.diagnosis if result is not None else None
    if snapshot.status == "completed" and result is not None and diagnosis is not None:
        return "completed", None

    app_err = snapshot.application_error
    if app_err is not None:
        detail = f"{app_err.code}:{app_err.message}"
        if app_err.code in _INFRASTRUCTURE_APPLICATION_ERROR_CODES:
            return "failed", FailureCause(kind="infrastructure", detail=detail)
        if app_err.code == "trace_integrity_error":
            return "failed", FailureCause(kind="unknown", detail=detail)
        lowered = app_err.message.lower()
        if any(marker in lowered for marker in _BEHAVIORAL_TERMINATION_MARKERS):
            return "failed", FailureCause(kind="behavioral", detail=detail)
        return "failed", FailureCause(kind="unknown", detail=detail)

    if result is not None:
        reason = result.termination_reason
        if reason in _BEHAVIORAL_TERMINATION_REASONS:
            return "failed", FailureCause(kind="behavioral", detail=reason)
        if reason == "runtime_error":
            return "failed", FailureCause(kind="infrastructure", detail=reason)
        if reason == "unsupported_task":
            return "failed", FailureCause(kind="behavioral", detail=reason)
        if diagnosis is None:
            detail = reason or "diagnosis missing"
            return "failed", FailureCause(kind="unknown", detail=detail)
        return "completed", None

    return "failed", FailureCause(kind="unknown", detail=snapshot.status)


def _failure_kind_for_execute_error(error: BaseException) -> _ExecuteFailureKind:
    if isinstance(error, (OSError, TimeoutError, ConnectionError)):
        return "infrastructure"
    detail = str(error).lower()
    if any(marker in detail for marker in _BEHAVIORAL_TERMINATION_MARKERS):
        return "behavioral"
    return "unknown"


@dataclass
class StudyResourceObserver:
    """Per-slot collector. Factory diagnostics stay separate from turn/call counts."""

    slot_id: str = "slot"
    allow_fixture_offline_boundary: bool = False
    max_events: int = 10_000
    records: list[ResourceTelemetry] = field(default_factory=list)
    planner_factory_calls: int = 0
    admitted_per_send_input_tokens: int | None = None
    admitted_per_send_output_tokens: int | None = None
    observation_descriptor: object | None = None
    _events: list[object] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _invalid: bool = False
    _invalid_reasons: list[str] = field(default_factory=list)
    _run_id: str | None = None
    _binding: TelemetryBinding | None = None

    def note_planner_factory_call(self) -> None:
        self.planner_factory_calls += 1

    def attach_observation_descriptor(self, descriptor: object) -> None:
        """Retain client observation identity for ledger gates."""
        self.observation_descriptor = descriptor
        blockers = tuple(getattr(descriptor, "blockers", ()) or ())
        supported = bool(getattr(descriptor, "profile_supported", False))
        origin = getattr(descriptor, "origin", None)
        if origin == "unsupported" or (
            not supported and origin != "mock_native"
        ):
            self._invalid = True
            reason = "unsupported_observation_descriptor"
            if reason not in self._invalid_reasons:
                self._invalid_reasons.append(reason)
            for blocker in blockers:
                text = str(blocker)
                if text not in self._invalid_reasons:
                    self._invalid_reasons.append(text)
        elif bool(getattr(descriptor, "fixture_only", True)) and origin != "mock_native":
            marker = "fixture_only_observation_descriptor"
            if marker not in self._invalid_reasons:
                self._invalid_reasons.append(marker)

    def make_binding(self) -> TelemetryBinding:
        def sink(event: TelemetryEvent) -> None:
            with self._lock:
                if len(self._events) >= self.max_events:
                    self._invalid = True
                    if "telemetry_buffer_overflow" not in self._invalid_reasons:
                        self._invalid_reasons.append("telemetry_buffer_overflow")
                    return
                self._events.append(event)

        binding = TelemetryBinding(
            slot_id=self.slot_id,
            sink=sink,
            max_events=self.max_events,
        )
        binding.allow_fixture_offline_boundary = self.allow_fixture_offline_boundary
        self._binding = binding
        return binding

    def associate_run_id(self, run_id: str | None) -> None:
        if run_id is None:
            return
        if self._run_id is not None and self._run_id != run_id:
            self._invalid = True
            self._invalid_reasons.append("conflicting_run_id")
            return
        self._run_id = run_id

    def observe_terminal(self, terminal: StudyTerminal) -> ResourceTelemetry:
        telemetry = collect_resource_telemetry(terminal)
        if self.planner_factory_calls and telemetry.planner_call_count is None:
            pass
        self.records.append(telemetry)
        return telemetry

    def resource_snapshot(self, *, worker_drained: bool) -> object:
        from signal_diag.agent.telemetry import (
            HttpSendEvent,
            LogicalCallEvent,
            PlannerTurnEvent,
            RepairEvent,
            SdkAttemptEvent,
            UsageObservation,
        )
        from signal_diag.evaluation.planner_ablation.v2.resource_models import (
            ReportedUsage,
            SlotResourceLedger,
        )
        from signal_diag.evaluation.planner_ablation.v2.resource_telemetry import (
            sum_reported_usage,
        )

        with self._lock:
            events = list(self._events)
            invalid = self._invalid
            reasons = list(self._invalid_reasons)
            run_id = self._run_id
            binding = self._binding

        if binding is not None and getattr(binding, "invalid", False):
            invalid = True
            reasons.extend(getattr(binding, "invalid_reasons", []))
        descriptor = getattr(binding, "observation_descriptor", None) if binding else None
        if descriptor is not None:
            self.observation_descriptor = descriptor
            if getattr(descriptor, "origin", None) == "unsupported":
                invalid = True
                reasons.append("unsupported_observation_descriptor")
            for item in getattr(descriptor, "blockers", ()) or ():
                text = str(item)
                if text.startswith("fixture_only"):
                    continue
                reasons.append(text)

        # Lifecycle endpoints: pair/dedupe by event kind + correlation + phase.
        # Usage and repair are independent observation records (not lifecycle ends).
        lifecycle_kinds = frozenset(
            {"planner_turn", "logical_call", "sdk_attempt", "http_send"}
        )
        pending: list[str] = []
        starts: dict[tuple[str, str], str] = {}
        ends: set[tuple[str, str]] = set()
        for event in events:
            kind = str(getattr(event, "kind", None) or "")
            phase = getattr(event, "phase", None)
            corr = str(
                getattr(event, "correlation_id", None)
                or getattr(event, "sequence_id", "")
                or ""
            )
            if kind not in lifecycle_kinds or not phase:
                continue
            key = (kind, corr)
            if phase == "start":
                starts[key] = kind
            elif phase == "end":
                ends.add(key)

        for key, kind in starts.items():
            if key not in ends:
                pending.append(f"{key[0]}:{key[1]}")
                invalid = True
                reasons.append(f"missing_end:{kind}:{key[1]}")

        seen_phase: set[tuple[str, str, str]] = set()
        for event in events:
            kind = str(getattr(event, "kind", None) or "")
            phase = getattr(event, "phase", None)
            corr_raw = getattr(event, "correlation_id", None)
            if not phase or not corr_raw:
                continue
            corr = str(corr_raw)
            # Observation records may share a parent ID with lifecycle ends; key by kind.
            phase_key = (kind, corr, str(phase))
            if phase_key in seen_phase:
                invalid = True
                reasons.append(f"duplicate_phase:{kind}:{corr}:{phase}")
            seen_phase.add(phase_key)

        turn_count = sum(
            1 for e in events if isinstance(e, PlannerTurnEvent) and e.phase == "start"
        )
        repair_count = sum(1 for e in events if isinstance(e, RepairEvent))
        logical_count = sum(
            1 for e in events if isinstance(e, LogicalCallEvent) and e.phase == "start"
        )
        sdk_count = sum(
            1 for e in events if isinstance(e, SdkAttemptEvent) and e.phase == "start"
        )
        http_count = sum(
            1 for e in events if isinstance(e, HttpSendEvent) and e.phase == "start"
        )

        # Map complete usage to send_id (or call_id fallback) for coverage checks.
        usages: list[ReportedUsage] = []
        usage_complete_objects = True
        usage_by_send: dict[str, UsageObservation] = {}
        usage_events = [e for e in events if isinstance(e, UsageObservation)]
        if not usage_events and logical_count > 0:
            usage_complete_objects = False
            reasons.append("missing_usage_observations")
        for usage in usage_events:
            if usage.status != "complete":
                usage_complete_objects = False
                reasons.append(f"usage_{usage.status}")
                continue
            if (
                usage.prompt_tokens is None
                or usage.completion_tokens is None
                or usage.total_tokens is None
            ):
                usage_complete_objects = False
                reasons.append("usage_incomplete_fields")
                continue
            try:
                reported = ReportedUsage(
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    total_tokens=usage.total_tokens,
                    cache_hit_tokens=usage.cache_hit_tokens,
                    cache_miss_tokens=usage.cache_miss_tokens,
                    reasoning_tokens=usage.reasoning_tokens,
                )
                usages.append(reported)
            except Exception:  # noqa: BLE001
                invalid = True
                usage_complete_objects = False
                reasons.append("usage_validation_failed")
                continue
            link = usage.send_id or usage.call_id
            if link:
                if link in usage_by_send:
                    invalid = True
                    reasons.append(f"duplicate_usage_for_send:{link}")
                usage_by_send[link] = usage

        http_ends = [
            e for e in events if isinstance(e, HttpSendEvent) and e.phase == "end"
        ]
        # Non-redirect dispatched sends need complete usage for exact reported
        # totals. Redirect hops are not approved zero-use proofs; they reserve
        # potential_token_exposure when ceilings are admitted.
        send_coverage_complete = True
        for send in http_ends:
            if send.outcome == "redirect":
                # Reviewed zero-use proof is not implemented. A string prefix cannot
                # make a redirect an exact-zero send.
                send_coverage_complete = False
                reasons.append(
                    f"redirect_without_zero_use_proof:{send.send_id or send.correlation_id}"
                )
                continue
            link = send.send_id or send.correlation_id
            matched = usage_by_send.get(link)
            if matched is None or matched.status != "complete":
                send_coverage_complete = False
                reasons.append(f"incomplete_send_usage_coverage:{link}")

        # Logical calls without any HTTP (pre-dispatch failure) need explicit
        # zero-use proof; absence keeps exact total unknown.
        if logical_count > 0 and http_count == 0 and not usage_events:
            send_coverage_complete = False
            if "missing_usage_observations" not in reasons:
                reasons.append("logical_call_without_send_or_usage_proof")
        if logical_count > 0 and http_count == 0 and usage_events:
            # Usage without HTTP observation (mounted/proxy miss) is invalid.
            invalid = True
            send_coverage_complete = False
            reasons.append("usage_without_http_dispatch_observation")

        # Potential token exposure: reserve for sends lacking complete usage
        # when per-send ceilings were provided on the binding/assessment.
        potential_token_exposure: int | None = None
        admitted_input = getattr(self, "admitted_per_send_input_tokens", None)
        admitted_output = getattr(self, "admitted_per_send_output_tokens", None)
        if isinstance(admitted_input, int) or isinstance(admitted_output, int):
            exposure = 0
            any_reserved = False
            for send in http_ends:
                link = send.send_id or send.correlation_id
                matched = usage_by_send.get(link) if link else None
                if matched is not None and matched.status == "complete":
                    continue
                # Redirect or incomplete/missing usage → reserve, never invent zero.
                if isinstance(admitted_input, int):
                    exposure += admitted_input
                if isinstance(admitted_output, int):
                    exposure += admitted_output
                any_reserved = True
            potential_token_exposure = exposure if any_reserved else 0

        subtotal = sum_reported_usage(usages)
        exact_total = (
            subtotal.total_tokens
            if (
                usage_complete_objects
                and send_coverage_complete
                and subtotal is not None
                and not pending
                and worker_drained
                and not invalid
            )
            else None
        )
        if (
            logical_count == 0
            and http_count == 0
            and turn_count == 0
            and worker_drained
            and not pending
            and not usage_events
            and not invalid
        ):
            # Fixed / no-provider path may have zero usage with complete ledger.
            exact_total = 0

        incomplete = (
            (not worker_drained)
            or bool(pending)
            or (not usage_complete_objects and logical_count > 0)
            or (not send_coverage_complete and http_count > 0)
        )
        closed = (
            worker_drained
            and not pending
            and not incomplete
            and not invalid
            and (exact_total is not None or (logical_count == 0 and http_count == 0))
        )
        unique_reasons = tuple(dict.fromkeys(reasons))
        serialized_events = tuple(
            {
                "kind": getattr(e, "kind", None),
                "phase": getattr(e, "phase", None),
                "sequence_id": getattr(e, "sequence_id", None),
                "monotonic_s": getattr(e, "monotonic_s", None),
                "correlation_id": getattr(e, "correlation_id", None),
                "turn_id": getattr(e, "turn_id", None),
                "call_id": getattr(e, "call_id", None),
                "attempt_id": getattr(e, "attempt_id", None),
                "send_id": getattr(e, "send_id", None),
                "status": getattr(e, "status", None),
                "outcome": getattr(e, "outcome", None),
                "prompt_tokens": getattr(e, "prompt_tokens", None),
                "completion_tokens": getattr(e, "completion_tokens", None),
                "total_tokens": getattr(e, "total_tokens", None),
                "cache_hit_tokens": getattr(e, "cache_hit_tokens", None),
                "cache_miss_tokens": getattr(e, "cache_miss_tokens", None),
                "reasoning_tokens": getattr(e, "reasoning_tokens", None),
                "response_model": getattr(e, "response_model", None),
                "fingerprint": getattr(e, "fingerprint", None),
            }
            for e in events
        )
        return SlotResourceLedger(
            slot_key_digest=self.slot_id,
            run_id=run_id,
            events=serialized_events,
            planner_turn_count=turn_count,
            repair_attempt_count=repair_count,
            logical_call_count=logical_count,
            sdk_attempt_count=sdk_count,
            http_send_attempt_count=http_count,
            reported_usage_subtotal=subtotal,
            exact_total_tokens=exact_total,
            potential_token_exposure=potential_token_exposure,
            pending_event_ids=tuple(pending),
            worker_drained=worker_drained,
            telemetry_invalid=invalid,
            incomplete=incomplete,
            blockers=unique_reasons,
            closed=closed,
        )

def _study_guidance_from_context_guidance(
    guidance: ContextGuidance,
) -> StudyContextGuidanceView:
    return StudyContextGuidanceView(
        reason_codes=guidance.reason_codes,
        unlockable_modes=guidance.unlockable_modes,
        required_inputs={
            key: tuple(value) for key, value in guidance.required_inputs.items()
        },
        summary=guidance.summary,
        observed_facts=tuple(
            StudyObservedFactView(
                evidence_id=f.evidence_id,
                source_tool=f.source_tool,
                call_id=f.call_id,
                metric=f.metric,
                value=f.value,
                unit=f.unit,
                validity=f.validity,
                time_range=f.time_range,
                channel=f.channel,
            )
            for f in guidance.observed_facts
        ),
    )


def _baseline_to_agent_result(baseline: BaselineRunResult) -> AgentRunResult:
    if baseline.diagnosis is None:
        raise ValueError("baseline diagnosis required for guidance derivation")
    return AgentRunResult(
        run_id=baseline.run_id,
        status=baseline.status,
        diagnosis=StructuredDiagnosis(
            run_id=baseline.diagnosis.run_id,
            task_type="distortion_analysis",
            outcome=baseline.diagnosis.outcome,
            claims=baseline.diagnosis.claims,
            confidence_label=baseline.diagnosis.confidence_label,
            limitations=baseline.diagnosis.limitations,
            termination_reason="planner_finished",
            tool_call_count=baseline.diagnosis.tool_call_count,
            rule_evaluation_batches=baseline.diagnosis.rule_evaluation_batches,
        ),
        observations=baseline.observations,
        evidence=baseline.evidence,
        tool_history=baseline.tool_history,
        termination_reason="planner_finished",
        warnings=baseline.warnings,
        errors=baseline.errors,
        rule_evaluation_batches=baseline.rule_evaluation_batches,
    )


def _study_guidance_from_agent_result(
    *,
    mode: str,
    result: AgentRunResult | None,
) -> StudyContextGuidanceView | None:
    built = build_context_guidance(mode=mode, result=result)  # type: ignore[arg-type]
    if built is None:
        return None
    return _study_guidance_from_context_guidance(built)


def _map_guidance(guidance: object | None) -> StudyContextGuidanceView | None:
    if guidance is None:
        return None
    if isinstance(guidance, StudyContextGuidanceView):
        return guidance
    if isinstance(guidance, ContextGuidance):
        return _study_guidance_from_context_guidance(guidance)
    return StudyContextGuidanceView(
        reason_codes=tuple(guidance.reason_codes),  # type: ignore[attr-defined]
        unlockable_modes=tuple(guidance.unlockable_modes),  # type: ignore[attr-defined]
        required_inputs={
            key: tuple(value)
            for key, value in guidance.required_inputs.items()  # type: ignore[attr-defined]
        },
        summary=guidance.summary,  # type: ignore[attr-defined]
        observed_facts=tuple(
            StudyObservedFactView(
                evidence_id=f.evidence_id,  # type: ignore[attr-defined]
                source_tool=f.source_tool,  # type: ignore[attr-defined]
                call_id=f.call_id,  # type: ignore[attr-defined]
                metric=f.metric,  # type: ignore[attr-defined]
                value=f.value,  # type: ignore[attr-defined]
                unit=f.unit,  # type: ignore[attr-defined]
                validity=f.validity,  # type: ignore[attr-defined]
                time_range=f.time_range,  # type: ignore[attr-defined]
                channel=f.channel,  # type: ignore[attr-defined]
            )
            for f in guidance.observed_facts  # type: ignore[attr-defined]
        ),
    )


def _phase_marker(
    clock: Callable[[], float],
    phase: PhaseName,
    advances: dict[str, float] | None,
) -> PhaseMarker:
    started = float(clock())
    apply_phase_advance(clock, phase, advances)
    ended = float(clock())
    return PhaseMarker(phase=phase, started_at=started, ended_at=ended)


def _placeholder_timing(
    markers: tuple[PhaseMarker, ...],
    *,
    residual: tuple[str, ...] = (),
) -> RequestTiming:
    return RequestTiming(
        timing_contract=TIMING_CONTRACT_V1,
        request_start=0.0,
        terminal_result_ready=0.0,
        elapsed_s=0.0,
        phase_markers=markers,
        residual_overhead_notes=residual,
    )


def _resolve_product_provenance(
    *,
    planner_class: str,
    provider_client_bound: bool,
    offline_session: bool,
) -> ExecutionProvenance:
    # Offline / scripted / fake-client sessions are immutable harness_only.
    # A class-name string alone never elevates to product_campaign.
    if (
        offline_session
        or planner_class != _APPROVED_PRODUCT_PLANNER_CLASS
        or provider_client_bound
    ):
        identity: Literal["product_campaign", "harness_only"] = "harness_only"
    else:
        # Future online scored path would still require verified prompt/context.
        identity = "harness_only"
    return ExecutionProvenance(
        planner_class=planner_class or "unknown",
        execution_identity=identity,
        provider_client_bound=provider_client_bound,
        offline_session=offline_session,
    )


class ProductArmSession:
    """Product study session: contextual submit/wait only; no labels."""

    def __init__(
        self,
        service: DiagnosisApplicationService,
        *,
        clock: Callable[[], float],
        phase_advances: dict[str, float] | None = None,
        offline_session: bool = True,
        owns_service_lifecycle: bool = False,
        arm: ScoredArm = "product_agent",
        observer: StudyResourceObserver | None = None,
    ) -> None:
        self._service = service
        self._clock = clock
        self._phase_advances = phase_advances
        self._offline_session = offline_session
        self._owns_service_lifecycle = owns_service_lifecycle
        self._arm = arm
        self._observer = observer
        # Fresh empty repository prepared outside the request timer.
        dependencies = service._dependencies
        service._dependencies = replace(
            dependencies,
            repository=InMemorySignalRepository(),
        )
        if self._observer is not None:
            self._observer.note_planner_factory_call()
        self._construction_planner_class = type(dependencies.planner_factory()).__name__
        probe = dependencies.planner_factory()
        if self._observer is not None:
            self._observer.note_planner_factory_call()
        self._construction_client_bound = (
            self._construction_planner_class == _APPROVED_PRODUCT_PLANNER_CLASS
            and getattr(probe, "_client", None) is not None
        )

    def provenance_preview(self) -> ExecutionProvenance:
        return _resolve_product_provenance(
            planner_class=self._construction_planner_class,
            provider_client_bound=self._construction_client_bound,
            offline_session=self._offline_session,
        )

    @property
    def background_worker_alive(self) -> bool:
        # Store status is authoritative for in-flight work (queue may be empty
        # while the executor is awaiting item.execute()). Idle worker tasks that
        # only wait on an empty queue are not "leaked" background work.
        store = self._service._contextual_store
        return any(
            snapshot.status in ("queued", "running")
            for snapshot in store._snapshots.values()
        )

    async def execute(self, request: ByteRequest) -> StudyTerminal:
        if not isinstance(request, ByteRequest):
            raise TypeError("product arm session requires ByteRequest encoded bytes")
        if request.channel != "mixdown":
            raise ValueError("study product session requires channel='mixdown'")
        if request.segment_policy != "full_signal":
            raise ValueError("study product session requires segment_policy='full_signal'")

        markers: list[PhaseMarker] = []
        dependencies: ApplicationDependencies = self._service._dependencies
        executed_planner_class = self._construction_planner_class
        provider_client_bound = self._construction_client_bound

        def tracking_factory() -> PlannerModel:
            nonlocal executed_planner_class, provider_client_bound
            if self._observer is not None:
                self._observer.note_planner_factory_call()
            planner = dependencies.planner_factory()
            executed_planner_class = type(planner).__name__
            provider_client_bound = (
                executed_planner_class == _APPROVED_PRODUCT_PLANNER_CLASS
                and getattr(planner, "_client", None) is not None
            )
            if self._observer is not None:
                target: object = planner
                # RecordingPlanner forwards via property; bind the inner exact planner.
                inner = getattr(planner, "_planner", None)
                if type(inner) is RealLLMPlanner:
                    target = inner
                    executed_planner_class = "RealLLMPlanner"
                if type(target) is RealLLMPlanner and getattr(
                    target, "_planner_telemetry_binding", None
                ) is None:
                    binding = self._observer.make_binding()
                    bind_planner_telemetry(target, binding=binding)
                    if binding.allow_fixture_offline_boundary:
                        client = getattr(target, "_client", None)
                        if client is not None and not getattr(
                            client, "_signal_diag_observation_attached", False
                        ):
                            from signal_diag.agent.provider_telemetry import (
                                attach_sdk_observation,
                                build_fixture_sdk_observation_profile,
                            )

                            descriptor = attach_sdk_observation(
                                client,
                                binding=binding,
                                profile=build_fixture_sdk_observation_profile(),
                                allow_fixture_offline_boundary=True,
                            )
                            self._observer.attach_observation_descriptor(descriptor)
            return planner

        self._service._dependencies = replace(
            dependencies,
            planner_factory=tracking_factory,  # type: ignore[arg-type]
        )
        try:
            markers.append(_phase_marker(self._clock, "decode", self._phase_advances))
            # Decode + segment + context construction happen inside submit_contextual_wav.
            submission = await self._service.submit_contextual_wav(
                request.test_wav_bytes,
                test_filename=_NEUTRAL_TEST_FILENAME,
                mode=request.mode,
                reference_data=request.reference_wav_bytes,
                reference_filename=(
                    _NEUTRAL_REFERENCE_FILENAME
                    if request.reference_wav_bytes is not None
                    else None
                ),
                nominal_fundamental_hz=None,
                stimulus_kind=None,
                user_request=request.question,
                channel="mixdown",
            )
            markers[-1] = PhaseMarker(
                phase="decode",
                started_at=markers[-1].started_at,
                ended_at=float(self._clock()),
            )
            markers.append(_phase_marker(self._clock, "execution", self._phase_advances))
            snapshot = await self._service.wait_for_contextual_terminal(submission.run_id)
            if self._observer is not None:
                self._observer.associate_run_id(submission.run_id)
            markers[-1] = PhaseMarker(
                phase="execution",
                started_at=markers[-1].started_at,
                ended_at=float(self._clock()),
            )

            markers.append(_phase_marker(self._clock, "guidance", self._phase_advances))
            result = snapshot.result
            guidance = _map_guidance(snapshot.context_guidance)
            if guidance is None and result is not None:
                guidance = _study_guidance_from_agent_result(
                    mode=request.mode,
                    result=result,
                )
            markers[-1] = PhaseMarker(
                phase="guidance",
                started_at=markers[-1].started_at,
                ended_at=float(self._clock()),
            )
        except Exception as error:  # noqa: BLE001 — study terminal must classify failures
            provenance = _resolve_product_provenance(
                planner_class=executed_planner_class,
                provider_client_bound=provider_client_bound,
                offline_session=self._offline_session,
            )
            while len(markers) < 3:
                missing: PhaseName = ("decode", "execution", "guidance")[len(markers)]
                markers.append(_phase_marker(self._clock, missing, self._phase_advances))
            failed_terminal = StudyTerminal(
                run_id=f"run_failed_{uuid.uuid4().hex[:12]}",
                arm=self._arm,
                mode=request.mode,
                status="failed",
                failure_cause=FailureCause(
                    kind=_failure_kind_for_execute_error(error),
                    detail=str(error),
                ),
                task_assessment=_DEFAULT_ASSESSMENT,
                provenance=provenance,
                timing=_placeholder_timing(
                    tuple(markers),
                    residual=_PRODUCT_RESIDUAL_NOTES,
                ),
            )
            if self._observer is not None:
                self._observer.observe_terminal(failed_terminal)
            return failed_terminal
        finally:
            self._service._dependencies = dependencies

        provenance = _resolve_product_provenance(
            planner_class=executed_planner_class,
            provider_client_bound=provider_client_bound,
            offline_session=self._offline_session,
        )
        diagnosis = result.diagnosis if result is not None else None
        status, failure = _failure_cause_from_product_snapshot(snapshot, result)

        terminal = StudyTerminal(
            run_id=snapshot.run_id,
            arm=self._arm,
            mode=request.mode,
            status=status,
            failure_cause=failure,
            outcome=diagnosis.outcome if diagnosis is not None else None,
            claims=diagnosis.claims if diagnosis is not None else (),
            evidence=result.evidence if result is not None else (),
            rule_evaluation_batches=(
                result.rule_evaluation_batches if result is not None else ()
            ),
            task_assessment=_task_assessment_from_diagnosis(diagnosis),
            stimulus_context=snapshot.stimulus_context,
            guidance=guidance,
            limitations=diagnosis.limitations if diagnosis is not None else (),
            observations=result.observations if result is not None else (),
            tool_history=result.tool_history if result is not None else (),
            provenance=provenance,
            timing=_placeholder_timing(
                tuple(markers),
                residual=_PRODUCT_RESIDUAL_NOTES,
            ),
        )
        if self._observer is not None:
            self._observer.observe_terminal(terminal)
        return terminal

    async def aclose(self) -> None:
        if self._owns_service_lifecycle:
            await self._service.aclose()

    def resource_snapshot(self, *, worker_drained: bool) -> object:
        if self._observer is None:
            raise AttributeError("resource_snapshot unavailable without observer")
        return self._observer.resource_snapshot(worker_drained=worker_drained)


def _task_assessment_from_diagnosis(
    diagnosis: StructuredDiagnosis | None,
) -> TaskAssessment:
    if diagnosis is None:
        return _DEFAULT_ASSESSMENT
    return TaskAssessment(
        task_type=diagnosis.task_type,
        objective=_DEFAULT_ASSESSMENT.objective,
        hypotheses=_DEFAULT_ASSESSMENT.hypotheses,
    )


class FixedArmSession:
    """Fixed study session: decode bytes inside execute, then unchanged baseline."""

    def __init__(
        self,
        *,
        profile_loader: RuleProfileLoader,
        rule_engine: RuleEngine | None = None,
        repository: SignalRepository | None = None,
        tool_service: SignalToolService | None = None,
        clock: Callable[[], float],
        phase_advances: dict[str, float] | None = None,
        offline_session: bool = True,
        arm: ScoredArm = "fixed_pipeline",
        observer: StudyResourceObserver | None = None,
    ) -> None:
        self._profile_loader = profile_loader
        self._rule_engine = rule_engine or RuleEngine()
        # Fresh empty container prepared outside the timer.
        self._repository = repository or InMemorySignalRepository()
        # D049: same tool settings as the product arm, so only the planner differs.
        self._tools = tool_service or GuardedSignalToolService(self._repository)
        self._clock = clock
        self._phase_advances = phase_advances
        self._offline_session = offline_session
        self._arm = arm
        self._observer = observer
        self._baseline = PlannerAblationFixedPipelineBaseline(
            repository=self._repository,
            tool_service=self._tools,
            rule_engine=self._rule_engine,
            profile_loader=self._profile_loader,
        )

    async def execute(self, request: object) -> StudyTerminal:
        if not isinstance(request, ByteRequest):
            raise TypeError("fixed arm session requires ByteRequest encoded bytes")
        if request.channel != "mixdown":
            raise ValueError("study fixed session requires channel='mixdown'")
        if request.segment_policy != "full_signal":
            raise ValueError("study fixed session requires segment_policy='full_signal'")

        markers: list[PhaseMarker] = []
        provenance = ExecutionProvenance(
            planner_class=type(self._baseline).__name__,
            execution_identity="harness_only",
            provider_client_bound=False,
            offline_session=self._offline_session,
        )

        try:
            markers.append(_phase_marker(self._clock, "decode", self._phase_advances))
            test_loaded = load_wav_bytes(
                request.test_wav_bytes, filename=_NEUTRAL_TEST_FILENAME
            )
            test_selected = extract_segment(test_loaded.record, channel="mixdown")
            test_analysis = build_signal_record(
                test_selected,
                sample_rate_hz=test_loaded.record.meta.sample_rate_hz,
                source_type=test_loaded.record.meta.source_type,
                filename=test_loaded.record.meta.filename,
            )
            self._repository.put(test_analysis)

            reference_analysis_id: str | None = None
            if request.mode == "paired_reference":
                assert request.reference_wav_bytes is not None
                ref_loaded = load_wav_bytes(
                    request.reference_wav_bytes, filename=_NEUTRAL_REFERENCE_FILENAME
                )
                ref_selected = extract_segment(ref_loaded.record, channel="mixdown")
                ref_analysis = build_signal_record(
                    ref_selected,
                    sample_rate_hz=ref_loaded.record.meta.sample_rate_hz,
                    source_type=ref_loaded.record.meta.source_type,
                    filename=ref_loaded.record.meta.filename,
                )
                self._repository.put(ref_analysis)
                reference_analysis_id = ref_analysis.meta.signal_id

            stimulus = StimulusContext(
                mode=request.mode,
                test_signal_id=test_analysis.meta.signal_id,
                reference_signal_id=reference_analysis_id,
                assertion_source="evaluation_manifest",
            )
            markers[-1] = PhaseMarker(
                phase="decode",
                started_at=markers[-1].started_at,
                ended_at=float(self._clock()),
            )

            markers.append(_phase_marker(self._clock, "execution", self._phase_advances))
            baseline_request = PlannerAblationBaselineRequest(
                case_id=f"study_{uuid.uuid4().hex[:12]}",
                signal_id=test_analysis.meta.signal_id,
                stimulus_context=stimulus,
            )
            baseline: BaselineRunResult = await self._baseline.run(baseline_request)
            markers[-1] = PhaseMarker(
                phase="execution",
                started_at=markers[-1].started_at,
                ended_at=float(self._clock()),
            )

            markers.append(_phase_marker(self._clock, "guidance", self._phase_advances))
            guidance = _study_guidance_from_agent_result(
                mode=request.mode,
                result=_baseline_to_agent_result(baseline),
            )
            markers[-1] = PhaseMarker(
                phase="guidance",
                started_at=markers[-1].started_at,
                ended_at=float(self._clock()),
            )
        except Exception as error:  # noqa: BLE001
            while len(markers) < 3:
                missing = ("decode", "execution", "guidance")[len(markers)]
                markers.append(
                    _phase_marker(self._clock, missing, self._phase_advances)  # type: ignore[arg-type]
                )
            failed_terminal = StudyTerminal(
                run_id=f"baseline_failed_{uuid.uuid4().hex[:12]}",
                arm=self._arm,
                mode=request.mode if isinstance(request, ByteRequest) else "single_signal",
                status="failed",
                failure_cause=FailureCause(
                    kind=_failure_kind_for_execute_error(error),
                    detail=str(error),
                ),
                task_assessment=_DEFAULT_ASSESSMENT,
                provenance=provenance,
                timing=_placeholder_timing(tuple(markers)),
            )
            if self._observer is not None:
                self._observer.associate_run_id(failed_terminal.run_id)
                self._observer.observe_terminal(failed_terminal)
            return failed_terminal

        diagnosis = baseline.diagnosis
        if diagnosis is None:
            missing_terminal = StudyTerminal(
                run_id=baseline.run_id,
                arm=self._arm,
                mode=request.mode,
                status="failed",
                failure_cause=FailureCause(kind="behavioral", detail="diagnosis missing"),
                evidence=baseline.evidence,
                rule_evaluation_batches=baseline.rule_evaluation_batches,
                task_assessment=_DEFAULT_ASSESSMENT,
                stimulus_context=stimulus,
                observations=baseline.observations,
                tool_history=baseline.tool_history,
                provenance=provenance,
                timing=_placeholder_timing(tuple(markers)),
            )
            if self._observer is not None:
                self._observer.associate_run_id(missing_terminal.run_id)
                self._observer.observe_terminal(missing_terminal)
            return missing_terminal

        terminal = StudyTerminal(
            run_id=baseline.run_id,
            arm=self._arm,
            mode=request.mode,
            status="completed",
            outcome=diagnosis.outcome,
            claims=diagnosis.claims,
            evidence=baseline.evidence,
            rule_evaluation_batches=baseline.rule_evaluation_batches,
            task_assessment=TaskAssessment(
                task_type=diagnosis.task_type,
                objective=_DEFAULT_ASSESSMENT.objective,
                hypotheses=_DEFAULT_ASSESSMENT.hypotheses,
            ),
            stimulus_context=stimulus,
            guidance=guidance,
            observations=baseline.observations,
            tool_history=baseline.tool_history,
            limitations=diagnosis.limitations,
            provenance=provenance,
            timing=_placeholder_timing(tuple(markers)),
        )
        if self._observer is not None:
            self._observer.associate_run_id(terminal.run_id)
            self._observer.observe_terminal(terminal)
        return terminal

    async def aclose(self) -> None:
        return None

    def resource_snapshot(self, *, worker_drained: bool) -> object:
        from signal_diag.evaluation.planner_ablation.v2.resource_models import (
            ReportedUsage,
            SlotResourceLedger,
        )

        if self._observer is not None:
            # Prefer observer digest/run association so fixed slots never collide.
            snapshot = self._observer.resource_snapshot(worker_drained=worker_drained)
            # Observer may have no provider events; force audited zero-use fields.
            return SlotResourceLedger(
                slot_key_digest=self._observer.slot_id,
                run_id=getattr(snapshot, "run_id", None),
                events=getattr(snapshot, "events", ()),
                planner_turn_count=0,
                repair_attempt_count=0,
                logical_call_count=0,
                sdk_attempt_count=0,
                http_send_attempt_count=0,
                reported_usage_subtotal=ReportedUsage(
                    prompt_tokens=0, completion_tokens=0, total_tokens=0
                ),
                exact_total_tokens=0,
                potential_token_exposure=0,
                pending_event_ids=getattr(snapshot, "pending_event_ids", ()),
                worker_drained=worker_drained,
                telemetry_invalid=bool(getattr(snapshot, "telemetry_invalid", False)),
                incomplete=not worker_drained,
                blockers=() if worker_drained else ("worker_not_drained",),
                closed=worker_drained and bool(getattr(snapshot, "run_id", None)),
            )

        raise AttributeError(
            "fixed arm resource_snapshot requires a StudyResourceObserver "
            "bound to the schedule slot digest"
        )


def build_product_arm_session(
    service: DiagnosisApplicationService,
    *,
    clock: Callable[[], float] | None = None,
    phase_advances: dict[str, float] | None = None,
    offline_session: bool = True,
    observer: StudyResourceObserver | None = None,
) -> ProductArmSession:
    """Build a product ArmSession. Does not receive oracle/population labels."""
    import time

    return ProductArmSession(
        service,
        clock=clock if clock is not None else time.perf_counter,
        phase_advances=phase_advances,
        offline_session=offline_session,
        observer=observer,
    )


def build_fixed_arm_session(
    *,
    profile_loader: RuleProfileLoader,
    rule_engine: RuleEngine | None = None,
    repository: SignalRepository | None = None,
    tool_service: SignalToolService | None = None,
    clock: Callable[[], float] | None = None,
    phase_advances: dict[str, float] | None = None,
    offline_session: bool = True,
    observer: StudyResourceObserver | None = None,
) -> FixedArmSession:
    """Build a fixed ArmSession. Does not receive oracle/population labels."""
    import time

    return FixedArmSession(
        profile_loader=profile_loader,
        rule_engine=rule_engine,
        repository=repository,
        tool_service=tool_service,
        clock=clock if clock is not None else time.perf_counter,
        phase_advances=phase_advances,
        offline_session=offline_session,
        observer=observer,
    )
