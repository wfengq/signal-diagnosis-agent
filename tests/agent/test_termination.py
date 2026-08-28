"""Checkpoint E — Runtime termination and policy (T076–T085)."""

from __future__ import annotations

import pytest

from signal_diag.agent.models import (
    CallToolDecision,
    ClippingInput,
    DetectClippingCall,
    DiagnosisClaim,
    FinishDecision,
    PlannerOutputError,
    TaskAssessment,
)
from signal_diag.agent.planner import RealLLMPlanner, ScriptedPlanner, ScriptedStep
from signal_diag.agent.policies import AgentLimits
from signal_diag.agent.runtime import DistortionDiagnosisRuntime
from signal_diag.signal import SyntheticCase
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.tools.service import SignalToolService
from tests.conftest import store_synthetic_case


def _assessment() -> TaskAssessment:
    return TaskAssessment(
        task_type="distortion_analysis",
        objective="determine distortion cause",
    )


def _clipping_finish(evidence_id: str) -> FinishDecision:
    return FinishDecision(
        outcome="supported_fault",
        claims=(
            DiagnosisClaim(
                claim_id="claim_clip",
                fault_type="clipping",
                statement="clipping detected",
                evidence_refs=(evidence_id,),
            ),
        ),
        confidence_label="high",
    )


@pytest.mark.asyncio
async def test_t076_tool_error_observation_has_no_evidence(
    repository: InMemorySignalRepository,
    clipped_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, clipped_case)

    class ErrorToolService(SignalToolService):
        def detect_clipping(self, signal_id: str, args):  # type: ignore[no-untyped-def]
            from signal_diag.tools.results import ToolResult

            return ToolResult(
                call_id="call_detect_clipping_000000",
                tool_name="detect_clipping",
                status="error",
                error_message="simulated tool failure",
            )

    steps = [
        ScriptedStep(
            expected_observation_count=0,
            decision=CallToolDecision(
                task_assessment=_assessment(),
                call=DetectClippingCall(args=ClippingInput()),
                purpose="trigger error",
            ),
        ),
        ScriptedStep(
            expected_observation_count=1,
            decision=FinishDecision(
                outcome="inconclusive",
                claims=(),
                confidence_label="low",
                limitations=("tool error observed",),
            ),
        ),
    ]
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=ErrorToolService(repository),
        planner=ScriptedPlanner(steps),
    )
    result = await runtime.run(signal_id=signal_id, user_request="Why distorted?")
    assert result.observations[0].status == "error"
    assert result.observations[0].evidence_refs == ()
    assert result.evidence == ()


class _RetryThenSucceedPlanner:
    def __init__(self, succeed_on: int, decision: CallToolDecision) -> None:
        self._attempts = 0
        self._succeed_on = succeed_on
        self._decision = decision

    async def decide(self, context):  # type: ignore[no-untyped-def]
        self._attempts += 1
        if self._attempts < self._succeed_on:
            raise PlannerOutputError("malformed planner output")
        return self._decision


@pytest.mark.asyncio
async def test_t077_planner_output_error_is_retried_within_budget(
    repository: InMemorySignalRepository,
    clipped_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, clipped_case)
    decision = CallToolDecision(
        task_assessment=_assessment(),
        call=DetectClippingCall(args=ClippingInput()),
        purpose="recover after retry",
    )
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=_RetryThenSucceedPlanner(succeed_on=2, decision=decision),
        limits=AgentLimits(max_planner_retries=2, max_tool_calls=1),
    )
    result = await runtime.run(signal_id=signal_id, user_request="Why distorted?")
    assert result.tool_history
    assert result.termination_reason != "max_planner_retries"


@pytest.mark.asyncio
async def test_t078_planner_retry_exhaustion_terminates(
    repository: InMemorySignalRepository,
    clipped_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, clipped_case)

    class AlwaysFailPlanner:
        async def decide(self, context):  # type: ignore[no-untyped-def]
            raise PlannerOutputError("always malformed")

    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=AlwaysFailPlanner(),
        limits=AgentLimits(max_planner_retries=1),
    )
    result = await runtime.run(signal_id=signal_id, user_request="Why distorted?")
    assert result.termination_reason == "max_planner_retries"
    assert result.status == "error"
    assert len(result.tool_history) == 0


@pytest.mark.asyncio
async def test_t079_tool_call_limit_is_enforced(
    repository: InMemorySignalRepository,
    clipped_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, clipped_case)
    steps = [
        ScriptedStep(
            expected_observation_count=0,
            decision=CallToolDecision(
                task_assessment=_assessment(),
                call=DetectClippingCall(args=ClippingInput()),
                purpose="first",
            ),
        ),
        ScriptedStep(
            expected_observation_count=1,
            decision=CallToolDecision(
                call=DetectClippingCall(
                    args=ClippingInput(full_scale_threshold=0.95)
                ),
                purpose="second",
            ),
        ),
    ]
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=ScriptedPlanner(steps),
        limits=AgentLimits(max_tool_calls=1),
    )
    result = await runtime.run(signal_id=signal_id, user_request="Why distorted?")
    assert result.termination_reason == "max_tool_calls"
    assert len(result.tool_history) == 1


@pytest.mark.asyncio
async def test_t080_equivalent_call_is_rejected_and_counts_no_progress(
    repository: InMemorySignalRepository,
    clipped_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, clipped_case)
    same_call = DetectClippingCall(args=ClippingInput())
    steps = [
        ScriptedStep(
            expected_observation_count=0,
            decision=CallToolDecision(
                task_assessment=_assessment(),
                call=same_call,
                purpose="first purpose",
            ),
        ),
        ScriptedStep(
            expected_observation_count=1,
            decision=CallToolDecision(
                call=same_call,
                purpose="different prose only",
            ),
        ),
        ScriptedStep(
            expected_observation_count=1,
            decision=FinishDecision(
                outcome="inconclusive",
                claims=(),
                confidence_label="low",
                limitations=("stopped after duplicate",),
            ),
        ),
    ]
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=ScriptedPlanner(steps),
        limits=AgentLimits(max_no_progress=2),
    )
    result = await runtime.run(signal_id=signal_id, user_request="Why distorted?")
    assert len(result.tool_history) == 1
    assert any("equivalent tool call rejected" in item for item in result.errors)


@pytest.mark.asyncio
async def test_t081_no_progress_termination(
    repository: InMemorySignalRepository,
    clipped_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, clipped_case)
    same_call = DetectClippingCall(args=ClippingInput())
    steps = [
        ScriptedStep(
            expected_observation_count=0,
            decision=CallToolDecision(
                task_assessment=_assessment(),
                call=same_call,
                purpose="initial",
            ),
        ),
        ScriptedStep(
            expected_observation_count=1,
            decision=CallToolDecision(call=same_call, purpose="duplicate one"),
        ),
        ScriptedStep(
            expected_observation_count=1,
            decision=CallToolDecision(call=same_call, purpose="duplicate two"),
        ),
    ]
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=ScriptedPlanner(steps),
        limits=AgentLimits(max_no_progress=2),
    )
    result = await runtime.run(signal_id=signal_id, user_request="Why distorted?")
    assert result.termination_reason == "no_progress"
    assert result.status == "error"


@pytest.mark.asyncio
async def test_t082_valid_finish_with_evidence_succeeds(
    repository: InMemorySignalRepository,
    clipped_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, clipped_case)
    evidence_id = "ev_detect_clipping_detect_clipping_000000_000"
    steps = [
        ScriptedStep(
            expected_observation_count=0,
            decision=CallToolDecision(
                task_assessment=_assessment(),
                call=DetectClippingCall(args=ClippingInput()),
                purpose="check clipping",
            ),
        ),
        ScriptedStep(
            expected_observation_count=1,
            required_evidence_metrics=("clipping_detected",),
            decision=_clipping_finish(evidence_id),
        ),
    ]
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=ScriptedPlanner(steps),
    )
    result = await runtime.run(signal_id=signal_id, user_request="Why distorted?")
    assert result.status == "success"
    assert result.termination_reason == "planner_finished"
    assert result.diagnosis is not None
    assert result.diagnosis.claims[0].evidence_refs == (evidence_id,)


@pytest.mark.asyncio
async def test_t083_unknown_evidence_reference_follows_retry_policy(
    repository: InMemorySignalRepository,
    clipped_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, clipped_case)
    steps = [
        ScriptedStep(
            expected_observation_count=0,
            decision=CallToolDecision(
                task_assessment=_assessment(),
                call=DetectClippingCall(args=ClippingInput()),
                purpose="check clipping",
            ),
        ),
        ScriptedStep(
            expected_observation_count=1,
            decision=_clipping_finish("ev_unknown_000"),
        ),
        ScriptedStep(
            expected_observation_count=1,
            decision=FinishDecision(
                outcome="inconclusive",
                claims=(),
                confidence_label="low",
                limitations=("could not validate diagnosis",),
            ),
        ),
    ]
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=ScriptedPlanner(steps),
        limits=AgentLimits(max_planner_retries=1),
    )
    result = await runtime.run(signal_id=signal_id, user_request="Why distorted?")
    assert any("unknown evidence reference" in item for item in result.errors)
    assert result.termination_reason == "planner_finished"


@pytest.mark.asyncio
async def test_t084_unsupported_task_finishes_without_tool_calls(
    repository: InMemorySignalRepository,
    clipped_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, clipped_case)
    steps = [
        ScriptedStep(
            expected_observation_count=0,
            decision=FinishDecision(
                task_assessment=TaskAssessment(
                    task_type="unsupported",
                    objective="out of scope request",
                ),
                outcome="inconclusive",
                claims=(),
                confidence_label="low",
                limitations=("task unsupported",),
            ),
        ),
    ]
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=ScriptedPlanner(steps),
    )
    result = await runtime.run(signal_id=signal_id, user_request="Weather forecast?")
    assert len(result.tool_history) == 0
    assert result.termination_reason == "unsupported_task"


@pytest.mark.asyncio
async def test_t085_real_planner_failure_never_invokes_scripted_planner(
    repository: InMemorySignalRepository,
    clipped_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, clipped_case)

    class FailFastScriptedPlanner(ScriptedPlanner):
        async def decide(self, context):  # type: ignore[no-untyped-def]
            raise AssertionError("ScriptedPlanner must not be invoked")

    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=RealLLMPlanner(),
        limits=AgentLimits(max_planner_retries=0),
    )
    result = await runtime.run(signal_id=signal_id, user_request="Why distorted?")
    assert result.termination_reason == "max_planner_retries"
    sentinel = FailFastScriptedPlanner([])
    with pytest.raises(AssertionError):
        await sentinel.decide(result.observations)  # type: ignore[arg-type]
