"""Opt-in planner/runtime telemetry protocols (stdlib-only; no study/SDK imports)."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

EventPhase = Literal["start", "end"]
TurnOutcome = Literal[
    "success",
    "planner_output_error",
    "planner_error",
    "cancelled",
    "configuration_error",
    "unknown",
]
RepairReason = Literal["parse_error", "reject_decision"]
CallOutcome = Literal[
    "success",
    "empty_content",
    "invalid_json",
    "transport_error",
    "cancelled",
    "unknown",
]
SdkAttemptOutcome = Literal[
    "success",
    "retryable_response",
    "fatal_response",
    "transport_error",
    "cancelled",
    "pre_dispatch_failure",
    "unknown",
]
HttpSendOutcome = Literal[
    "success",
    "redirect",
    "http_error",
    "transport_error",
    "cancelled",
    "unknown",
]
UsageStatus = Literal["complete", "missing", "malformed", "unknown"]


@dataclass(frozen=True, slots=True)
class PlannerTurnEvent:
    kind: Literal["planner_turn"] = "planner_turn"
    sequence_id: str = ""
    correlation_id: str = ""
    phase: EventPhase = "start"
    turn_id: str = ""
    monotonic_s: float = 0.0
    outcome: TurnOutcome | None = None
    logical_completion_submitted: bool = False
    parent_id: str | None = None


@dataclass(frozen=True, slots=True)
class LogicalCallEvent:
    kind: Literal["logical_call"] = "logical_call"
    sequence_id: str = ""
    correlation_id: str = ""
    phase: EventPhase = "start"
    turn_id: str = ""
    call_id: str = ""
    monotonic_s: float = 0.0
    outcome: CallOutcome | None = None
    parent_id: str | None = None


@dataclass(frozen=True, slots=True)
class RepairEvent:
    kind: Literal["repair"] = "repair"
    sequence_id: str = ""
    correlation_id: str = ""
    phase: EventPhase = "end"
    turn_id: str = ""
    reason: RepairReason = "parse_error"
    retries_consumed: int = 1
    monotonic_s: float = 0.0
    parent_id: str | None = None


@dataclass(frozen=True, slots=True)
class SdkAttemptEvent:
    kind: Literal["sdk_attempt"] = "sdk_attempt"
    sequence_id: str = ""
    correlation_id: str = ""
    phase: EventPhase = "start"
    turn_id: str = ""
    call_id: str = ""
    attempt_id: str = ""
    retry_index: int = 0
    monotonic_s: float = 0.0
    outcome: SdkAttemptOutcome | None = None
    parent_id: str | None = None


@dataclass(frozen=True, slots=True)
class HttpSendEvent:
    kind: Literal["http_send"] = "http_send"
    sequence_id: str = ""
    correlation_id: str = ""
    phase: EventPhase = "start"
    turn_id: str = ""
    call_id: str = ""
    attempt_id: str = ""
    send_id: str = ""
    redirect_index: int = 0
    sanitized_endpoint: str = ""
    monotonic_s: float = 0.0
    status_code: int | None = None
    outcome: HttpSendOutcome | None = None
    parent_id: str | None = None


@dataclass(frozen=True, slots=True)
class UsageObservation:
    kind: Literal["usage"] = "usage"
    sequence_id: str = ""
    correlation_id: str = ""
    phase: EventPhase = "end"
    turn_id: str = ""
    call_id: str = ""
    attempt_id: str = ""
    send_id: str = ""
    status: UsageStatus = "unknown"
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cache_hit_tokens: int | None = None
    cache_miss_tokens: int | None = None
    reasoning_tokens: int | None = None
    response_model: str | None = None
    fingerprint: str | None = None
    monotonic_s: float = 0.0
    parent_id: str | None = None


TelemetryEvent = (
    PlannerTurnEvent
    | LogicalCallEvent
    | RepairEvent
    | SdkAttemptEvent
    | HttpSendEvent
    | UsageObservation
)


@dataclass(frozen=True, slots=True)
class SdkObservationProfile:
    """Primitive SDK observation profile consumed at the agent boundary."""

    openai_version: str
    openai_source_digest: str
    native_http_family: str
    native_http_version: str
    httpcore_version: str
    source_file_digests: tuple[tuple[str, str], ...]
    max_retries_default: int
    sdk_attempts_per_call: int
    prepare_options_hook: str
    send_request_hook: str
    native_dispatch_hook: str
    supported: bool
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ClientObservationDescriptor:
    """Actual constructed client observation identity (canonical/mock/injected)."""

    origin: Literal["canonical_sdk", "mock_native", "injected_client", "unsupported"]
    openai_version: str | None
    native_http_family: str | None
    profile_supported: bool
    blockers: tuple[str, ...] = ()
    fixture_only: bool = True


@runtime_checkable
class TelemetrySink(Protocol):
    def __call__(self, event: TelemetryEvent) -> None: ...


@dataclass
class TelemetryBinding:
    """Slot-local binding: monotonic clock, bounded sink, current associations."""

    slot_id: str
    sink: TelemetrySink
    max_events: int = 10_000
    clock: Callable[[], float] = time.monotonic
    invalid: bool = False
    invalid_reasons: list[str] = field(default_factory=list)
    event_count: int = 0
    _seen_sequences: set[str] = field(default_factory=set)
    current_turn_id: str | None = None
    current_call_id: str | None = None
    current_attempt_id: str | None = None
    last_turn_id: str | None = None

    def new_id(self, prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex}"

    def mark_invalid(self, reason: str) -> None:
        self.invalid = True
        if reason not in self.invalid_reasons:
            self.invalid_reasons.append(reason)


def emit_safely(binding: TelemetryBinding, event: TelemetryEvent) -> None:
    """Emit without throwing into planner/runtime control flow."""
    try:
        if binding.event_count >= binding.max_events:
            binding.mark_invalid("telemetry_buffer_overflow")
            return
        seq = event.sequence_id
        if seq in binding._seen_sequences:
            binding.mark_invalid(f"duplicate_sequence_id:{seq}")
            return
        binding._seen_sequences.add(seq)
        binding.event_count += 1
        if event.kind == "planner_turn":
            if event.phase == "start":
                binding.current_turn_id = event.turn_id
            else:
                binding.last_turn_id = event.turn_id
                if binding.current_turn_id == event.turn_id:
                    binding.current_turn_id = None
        elif event.kind == "logical_call":
            if event.phase == "start":
                binding.current_call_id = event.call_id
            elif binding.current_call_id == event.call_id:
                binding.current_call_id = None
        elif event.kind == "sdk_attempt":
            if event.phase == "start":
                binding.current_attempt_id = event.attempt_id
            elif binding.current_attempt_id == event.attempt_id:
                binding.current_attempt_id = None
        binding.sink(event)
    except Exception as error:  # noqa: BLE001 — observation must not escape
        binding.mark_invalid(f"sink_failure:{type(error).__name__}")


@runtime_checkable
class _PlannerTelemetryForwarding(Protocol):
    @property
    def _planner_telemetry_binding(self) -> TelemetryBinding | None: ...


def get_planner_telemetry_binding(planner: object) -> TelemetryBinding | None:
    """Read the private opt-in forwarding protocol only (no wrapper imports)."""
    if not isinstance(planner, _PlannerTelemetryForwarding):
        # Still allow objects that expose the attribute without the Protocol match.
        binding = getattr(planner, "_planner_telemetry_binding", None)
        if binding is None:
            return None
        if isinstance(binding, TelemetryBinding):
            return binding
        return None
    binding = planner._planner_telemetry_binding
    if binding is None or isinstance(binding, TelemetryBinding):
        return binding
    return None
