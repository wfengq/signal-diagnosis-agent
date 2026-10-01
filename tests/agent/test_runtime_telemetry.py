"""Runtime repair telemetry through opt-in binding (T-CX307/308)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from signal_diag.agent.models import (
    CallToolDecision,
    ClippingInput,
    DetectClippingCall,
    PlannerOutputError,
    TaskAssessment,
)
from signal_diag.agent.planner import (
    RealLLMPlanner,
    ScriptedPlanner,
    ScriptedStep,
    bind_planner_telemetry,
)
from signal_diag.agent.runtime import DistortionDiagnosisRuntime
from signal_diag.agent.telemetry import (
    PlannerTurnEvent,
    RepairEvent,
    TelemetryBinding,
    TelemetryEvent,
    get_planner_telemetry_binding,
)
from signal_diag.evaluation.recording import RecordingPlanner
from signal_diag.signal import SyntheticCase
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.tools.service import SignalToolService
from tests.conftest import store_synthetic_case


def _assessment() -> TaskAssessment:
    return TaskAssessment(
        task_type="distortion_analysis",
        objective="determine distortion cause",
    )


@dataclass
class _CountingSink:
    events: list[TelemetryEvent]

    def __call__(self, event: TelemetryEvent) -> None:
        self.events.append(event)


@pytest.mark.asyncio
async def test_parse_and_reject_consumption_emit_repairs(
    repository: InMemorySignalRepository,
    clipped_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, clipped_case)
    events: list[TelemetryEvent] = []
    binding = TelemetryBinding(slot_id="slot_runtime", sink=_CountingSink(events))

    class FlakyPlanner(RealLLMPlanner):
        def __init__(self) -> None:
            super().__init__(provider="deepseek", api_key="k", base_url="http://x")
            self._n = 0

        async def decide(self, context):  # type: ignore[no-untyped-def]
            # Emit turn events via binding manually to simulate RealLLM path counts
            # while driving parse/reject through a controlled subclass used only here.
            # Exact-type bind is required; use a Scripted path wrapped after binding
            # a genuine RealLLMPlanner for forwarding, and a scripted inner for logic.
            raise AssertionError("unused")

    # Drive repairs with ScriptedPlanner; bind telemetry on a RealLLMPlanner that
    # RecordingPlanner forwards, while runtime uses the recording wrapper around
    # a scripted planner that also exposes the forwarded binding via composition.
    # Simpler approach: monkeypatch-free ScriptedPlanner and emit via runtime's
    # get_planner_telemetry_binding on a RecordingPlanner wrapping RealLLM that
    # we replace decide on... Use ScriptedPlanner directly and attach binding
    # attribute for protocol forwarding.
    steps = [
        ScriptedStep(
            expected_observation_count=0,
            decision=CallToolDecision(
                task_assessment=None,  # reject: missing assessment
                call=DetectClippingCall(args=ClippingInput()),
                purpose="bad",
            ),
        ),
        ScriptedStep(
            expected_observation_count=0,
            decision=CallToolDecision(
                task_assessment=None,
                call=DetectClippingCall(args=ClippingInput()),
                purpose="bad2",
            ),
        ),
        ScriptedStep(
            expected_observation_count=0,
            decision=CallToolDecision(
                task_assessment=None,
                call=DetectClippingCall(args=ClippingInput()),
                purpose="bad3",
            ),
        ),
    ]
    scripted = ScriptedPlanner(steps)
    # Attach binding so runtime repair emission can find it.
    scripted._planner_telemetry_binding = binding  # type: ignore[attr-defined]
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=scripted,
    )
    result = await runtime.run(signal_id=signal_id, user_request="Why distorted?")
    repairs = [e for e in events if isinstance(e, RepairEvent)]
    assert len(repairs) == 2
    assert result.termination_reason == "max_planner_retries"
    assert "planner_attempt_count" not in type(result).model_fields


@pytest.mark.asyncio
async def test_exhausted_retry_does_not_emit_another_consumption(
    repository: InMemorySignalRepository,
    clipped_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, clipped_case)
    events: list[TelemetryEvent] = []
    binding = TelemetryBinding(slot_id="slot_ex", sink=events.append)

    class AlwaysParseError:
        _planner_telemetry_binding = binding

        async def decide(self, context):  # type: ignore[no-untyped-def]
            raise PlannerOutputError("bad json")

    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=AlwaysParseError(),  # type: ignore[arg-type]
    )
    result = await runtime.run(signal_id=signal_id, user_request="Why distorted?")
    repairs = [e for e in events if isinstance(e, RepairEvent)]
    # max_planner_retries default 2 → two consuming continues, third exhausts.
    assert len(repairs) == 2
    assert result.termination_reason == "max_planner_retries"


@pytest.mark.asyncio
async def test_recording_wrapper_forwards_binding_without_extra_turn() -> None:
    events: list[TelemetryEvent] = []
    binding = TelemetryBinding(slot_id="slot_wrap", sink=events.append)
    inner = RealLLMPlanner(client=object())  # type: ignore[arg-type]
    bind_planner_telemetry(inner, binding=binding)
    wrapper = RecordingPlanner(inner)
    assert get_planner_telemetry_binding(wrapper) is binding
    # Wrapper construction / property access is not a planner turn.
    assert [e for e in events if isinstance(e, PlannerTurnEvent)] == []


@pytest.mark.asyncio
async def test_observer_failure_preserves_product_exception_on_runtime(
    repository: InMemorySignalRepository,
    clipped_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, clipped_case)

    def boom(_event: TelemetryEvent) -> None:
        raise RuntimeError("sink fail")

    binding = TelemetryBinding(slot_id="slot_fail", sink=boom)

    class AlwaysParseError:
        _planner_telemetry_binding = binding

        async def decide(self, context):  # type: ignore[no-untyped-def]
            raise PlannerOutputError("bad json")

    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=AlwaysParseError(),  # type: ignore[arg-type]
    )
    result = await runtime.run(signal_id=signal_id, user_request="Why distorted?")
    assert result.termination_reason == "max_planner_retries"
    assert binding.invalid is True
