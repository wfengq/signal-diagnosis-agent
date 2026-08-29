"""Checkpoint J — RecordingPlanner (T141–T142)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from signal_diag.agent.models import (
    AgentDecision,
    CallToolDecision,
    ClippingInput,
    DetectClippingCall,
    PlannerContext,
    PlannerOutputError,
    ScriptExhaustedError,
    TaskAssessment,
)
from signal_diag.agent.planner import ScriptedPlanner, ScriptedStep
from signal_diag.evaluation.recording import RecordingPlanner
from signal_diag.signal.models import SignalMeta
from signal_diag.tools.registry import get_tool_descriptors


def _planner_context() -> PlannerContext:
    return PlannerContext(
        run_id="run_recording",
        user_request="Why distorted?",
        signal_meta=SignalMeta(
            signal_id="sig_recording",
            source_type="generated",
            sample_rate_hz=48_000,
            channels=1,
            num_samples=96_000,
            duration_s=2.0,
            original_dtype="float32",
        ),
        task_assessment=None,
        observations=(),
        evidence=(),
        tool_history=(),
        available_tools=get_tool_descriptors(),
        remaining_tool_calls=8,
        remaining_planner_retries=2,
        no_progress_count=0,
    )


def _call_decision(purpose: str = "inspect clipping") -> CallToolDecision:
    return CallToolDecision(
        task_assessment=TaskAssessment(
            task_type="distortion_analysis",
            objective="inspect clipping",
        ),
        call=DetectClippingCall(args=ClippingInput()),
        purpose=purpose,
    )


class _IdentityPlanner:
    def __init__(self, decision: AgentDecision) -> None:
        self.decision = decision
        self.received: list[PlannerContext] = []

    async def decide(self, context: PlannerContext) -> AgentDecision:
        self.received.append(context)
        return self.decision


class _RaisePlanner:
    def __init__(self, error: BaseException) -> None:
        self.error = error

    async def decide(self, context: PlannerContext) -> AgentDecision:
        raise self.error


@pytest.mark.asyncio
async def test_t141_transparent_planner_delegation() -> None:
    context = _planner_context()
    decision = _call_decision()
    inner = _IdentityPlanner(decision)
    planner = RecordingPlanner(inner)

    returned = await planner.decide(context)

    assert inner.received == [context]
    assert inner.received[0] is context
    assert returned is decision
    records = planner.records
    assert len(records) == 1
    assert records[0].decision_index == 0
    assert records[0].status == "decision"
    assert records[0].decision is decision
    assert records[0].context is context
    assert records[0].provider_usage is None

    scripted_decision = _call_decision("scripted")
    scripted = ScriptedPlanner(
        [ScriptedStep(expected_observation_count=0, decision=scripted_decision)]
    )
    wrapped_scripted = RecordingPlanner(scripted)
    scripted_returned = await wrapped_scripted.decide(context)
    assert scripted_returned is scripted_decision
    assert wrapped_scripted.records[0].decision is scripted_decision


@pytest.mark.asyncio
async def test_t142_planner_call_snapshot_order() -> None:
    context = _planner_context()
    success_decision = _call_decision("first")
    output_error = PlannerOutputError("delegate output error")
    runtime_error = RuntimeError("delegate boom")

    class _SequencePlanner:
        def __init__(self) -> None:
            self.calls = 0

        async def decide(self, context: PlannerContext) -> AgentDecision:
            self.calls += 1
            if self.calls == 1:
                return success_decision
            if self.calls == 2:
                return {"not": "an AgentDecision"}  # type: ignore[return-value]
            if self.calls == 3:
                raise output_error
            raise runtime_error

    planner = RecordingPlanner(_SequencePlanner())

    first = await planner.decide(context)
    assert first is success_decision
    snapshot_after_success = planner.records
    assert isinstance(snapshot_after_success, tuple)
    assert len(snapshot_after_success) == 1

    with pytest.raises(PlannerOutputError) as invalid_info:
        await planner.decide(context)
    invalid_error = invalid_info.value
    assert invalid_error is not output_error
    assert "invalid AgentDecision" in str(invalid_error)

    with pytest.raises(PlannerOutputError) as raised_output_info:
        await planner.decide(context)
    assert raised_output_info.value is output_error

    with pytest.raises(RuntimeError) as raised_runtime_info:
        await planner.decide(context)
    assert raised_runtime_info.value is runtime_error

    records = planner.records
    assert records is not snapshot_after_success
    assert len(snapshot_after_success) == 1
    assert [item.decision_index for item in records] == [0, 1, 2, 3]
    assert [item.record_id for item in records] == [
        "decision_000000",
        "decision_000001",
        "decision_000002",
        "decision_000003",
    ]
    assert [item.status for item in records] == [
        "decision",
        "planner_output_error",
        "planner_output_error",
        "planner_error",
    ]
    assert records[0].decision is success_decision
    assert records[1].decision is None
    assert records[1].error_type == "PlannerOutputError"
    assert records[1].error_message
    assert records[2].error_type == "PlannerOutputError"
    assert records[2].error_message == "delegate output error"
    assert records[3].error_type == "RuntimeError"
    assert records[3].error_message == "delegate boom"
    assert all(item.context is context for item in records)
    assert all(item.provider_usage is None for item in records)
    assert all(item.latency_ms is not None and item.latency_ms >= 0.0 for item in records)

    with pytest.raises(ValidationError):
        records[0].decision_index = 99  # type: ignore[misc]

    exhausted = ScriptExhaustedError("scripted planner has no remaining steps")
    exhausted_planner = RecordingPlanner(_RaisePlanner(exhausted))
    with pytest.raises(ScriptExhaustedError) as exhausted_info:
        await exhausted_planner.decide(context)
    assert exhausted_info.value is exhausted
    exhausted_record = exhausted_planner.records[0]
    assert exhausted_record.decision_index == 0
    assert exhausted_record.status == "planner_error"
    assert exhausted_record.error_type == "ScriptExhaustedError"
