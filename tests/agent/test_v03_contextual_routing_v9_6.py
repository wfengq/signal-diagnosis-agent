"""T-CX149–T-CX154: v9.6 mode-aware contextual Tool routing."""

from __future__ import annotations

import pytest

from signal_diag.agent.models import (
    AnalyzeContextualDistortionCall,
    AnalyzeHarmonicDistortionCall,
    CallToolDecision,
    FinishDecision,
    HarmonicDistortionInput,
    TaskAssessment,
)
from signal_diag.agent.planner import ScriptedPlanner, ScriptedStep
from signal_diag.agent.policies import AgentLimits
from signal_diag.agent.runtime import DistortionDiagnosisRuntime
from signal_diag.signal.context import StimulusContext
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.signal.synthetic import generate_sine
from signal_diag.tools.contracts import ContextualDistortionInput
from signal_diag.tools.service import SignalToolService
from tests.conftest import store_synthetic_case

ASSESSMENT = TaskAssessment(
    task_type="distortion_analysis",
    objective="diagnose S1 distortion",
)


class RecordingToolService(SignalToolService):
    def __init__(self, repository: InMemorySignalRepository) -> None:
        super().__init__(repository)
        self.invoked_tools: list[str] = []

    def analyze_harmonic_distortion(self, signal_id, args):  # type: ignore[no-untyped-def]
        self.invoked_tools.append("analyze_harmonic_distortion")
        return super().analyze_harmonic_distortion(signal_id, args)

    def analyze_contextual_distortion(self, context, args):  # type: ignore[no-untyped-def]
        self.invoked_tools.append("analyze_contextual_distortion")
        return super().analyze_contextual_distortion(context, args)


def _store_pair(
    repository: InMemorySignalRepository,
) -> tuple[str, str]:
    test = generate_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=1.0,
        amplitude=0.5,
    )
    ref = generate_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=1.0,
        amplitude=0.4,
    )
    test_id = store_synthetic_case(repository, test)
    ref_id = store_synthetic_case(repository, ref)
    return test_id, ref_id


def _finish_inconclusive() -> FinishDecision:
    return FinishDecision(
        outcome="inconclusive",
        claims=(),
        confidence_label="low",
        limitations=("routing test stop",),
    )


@pytest.mark.asyncio
async def test_t_cx149_v96_rejects_plain_harmonic_tool_in_paired_mode() -> None:
    repository = InMemorySignalRepository()
    test_id, ref_id = _store_pair(repository)
    tools = RecordingToolService(repository)
    captured: list[object] = []

    class CapturePlanner(ScriptedPlanner):
        async def decide(self, context):  # type: ignore[no-untyped-def]
            captured.append(context)
            return await super().decide(context)

    steps = [
        ScriptedStep(
            expected_observation_count=0,
            decision=CallToolDecision(
                task_assessment=ASSESSMENT,
                call=AnalyzeHarmonicDistortionCall(args=HarmonicDistortionInput()),
                purpose="wrong ordinary harmonic route",
            ),
        ),
        ScriptedStep(
            expected_observation_count=0,
            decision=_finish_inconclusive(),
        ),
    ]
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=tools,
        planner=CapturePlanner(steps),
        causal_policy_version="v9_6_contextual",
        limits=AgentLimits(max_planner_retries=2, max_tool_calls=4),
    )
    result = await runtime.run(
        signal_id=test_id,
        user_request="Why distorted?",
        stimulus_context=StimulusContext(
            mode="paired_reference",
            test_signal_id=test_id,
            reference_signal_id=ref_id,
            assertion_source="user_supplied",
        ),
    )
    assert "analyze_harmonic_distortion" not in tools.invoked_tools
    assert any(
        "analyze_contextual_distortion" in message
        and "paired_reference" in message
        for message in result.errors
    )
    assert len(captured) >= 2
    second = captured[1]
    assert any(
        "analyze_contextual_distortion" in item for item in second.recoverable_errors
    )


@pytest.mark.asyncio
async def test_t_cx150_v96_rejects_plain_harmonic_tool_in_nominal_mode() -> None:
    repository = InMemorySignalRepository()
    case = generate_sine(
        frequency_hz=440.0,
        sample_rate_hz=48_000,
        duration_s=1.0,
        amplitude=0.5,
    )
    signal_id = store_synthetic_case(repository, case)
    tools = RecordingToolService(repository)
    steps = [
        ScriptedStep(
            expected_observation_count=0,
            decision=CallToolDecision(
                task_assessment=ASSESSMENT,
                call=AnalyzeHarmonicDistortionCall(args=HarmonicDistortionInput()),
                purpose="wrong ordinary harmonic route",
            ),
        ),
        ScriptedStep(
            expected_observation_count=0,
            decision=_finish_inconclusive(),
        ),
    ]
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=tools,
        planner=ScriptedPlanner(steps),
        causal_policy_version="v9_6_contextual",
    )
    result = await runtime.run(
        signal_id=signal_id,
        user_request="Why distorted?",
        stimulus_context=StimulusContext(
            mode="nominal_single_tone",
            test_signal_id=signal_id,
            nominal_fundamental_hz=440.0,
            stimulus_kind="single_tone",
            assertion_source="user_supplied",
        ),
    )
    assert "analyze_harmonic_distortion" not in tools.invoked_tools
    assert any(
        "analyze_contextual_distortion" in message
        and "nominal_single_tone" in message
        for message in result.errors
    )


@pytest.mark.asyncio
async def test_t_cx151_v96_allows_contextual_tool_in_paired_mode() -> None:
    repository = InMemorySignalRepository()
    test_id, ref_id = _store_pair(repository)
    tools = RecordingToolService(repository)
    steps = [
        ScriptedStep(
            expected_observation_count=0,
            decision=CallToolDecision(
                task_assessment=ASSESSMENT,
                call=AnalyzeContextualDistortionCall(args=ContextualDistortionInput()),
                purpose="correct contextual harmonic route",
            ),
        ),
        ScriptedStep(
            expected_observation_count=1,
            decision=_finish_inconclusive(),
        ),
    ]
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=tools,
        planner=ScriptedPlanner(steps),
        causal_policy_version="v9_6_contextual",
    )
    result = await runtime.run(
        signal_id=test_id,
        user_request="Why distorted?",
        stimulus_context=StimulusContext(
            mode="paired_reference",
            test_signal_id=test_id,
            reference_signal_id=ref_id,
            assertion_source="user_supplied",
        ),
    )
    assert tools.invoked_tools == ["analyze_contextual_distortion"]
    assert len(result.observations) == 1
    assert result.observations[0].tool_name == "analyze_contextual_distortion"


@pytest.mark.asyncio
async def test_t_cx152_v96_allows_plain_harmonic_tool_in_single_mode() -> None:
    repository = InMemorySignalRepository()
    case = generate_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=1.0,
        amplitude=0.5,
    )
    signal_id = store_synthetic_case(repository, case)
    tools = RecordingToolService(repository)
    steps = [
        ScriptedStep(
            expected_observation_count=0,
            decision=CallToolDecision(
                task_assessment=ASSESSMENT,
                call=AnalyzeHarmonicDistortionCall(args=HarmonicDistortionInput()),
                purpose="descriptive single_signal harmonic",
            ),
        ),
        ScriptedStep(
            expected_observation_count=1,
            decision=_finish_inconclusive(),
        ),
    ]
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=tools,
        planner=ScriptedPlanner(steps),
        causal_policy_version="v9_6_contextual",
    )
    result = await runtime.run(
        signal_id=signal_id,
        user_request="Why distorted?",
        stimulus_context=StimulusContext(
            mode="single_signal",
            test_signal_id=signal_id,
            assertion_source="user_supplied",
        ),
    )
    assert tools.invoked_tools == ["analyze_harmonic_distortion"]
    assert len(result.observations) == 1


@pytest.mark.asyncio
async def test_t_cx153_rejected_route_consumes_retry_not_tool_budget() -> None:
    repository = InMemorySignalRepository()
    test_id, ref_id = _store_pair(repository)
    tools = RecordingToolService(repository)
    captured: list[object] = []

    class CapturePlanner(ScriptedPlanner):
        async def decide(self, context):  # type: ignore[no-untyped-def]
            captured.append(context)
            return await super().decide(context)

    steps = [
        ScriptedStep(
            expected_observation_count=0,
            decision=CallToolDecision(
                task_assessment=ASSESSMENT,
                call=AnalyzeHarmonicDistortionCall(args=HarmonicDistortionInput()),
                purpose="rejected route",
            ),
        ),
        ScriptedStep(
            expected_observation_count=0,
            decision=_finish_inconclusive(),
        ),
    ]
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=tools,
        planner=CapturePlanner(steps),
        causal_policy_version="v9_6_contextual",
        limits=AgentLimits(max_planner_retries=2, max_tool_calls=4),
    )
    await runtime.run(
        signal_id=test_id,
        user_request="Why distorted?",
        stimulus_context=StimulusContext(
            mode="paired_reference",
            test_signal_id=test_id,
            reference_signal_id=ref_id,
            assertion_source="user_supplied",
        ),
    )
    assert "analyze_harmonic_distortion" not in tools.invoked_tools
    assert len(captured) >= 2
    first = captured[0]
    second = captured[1]
    assert first.remaining_tool_calls == second.remaining_tool_calls == 4
    assert second.remaining_planner_retries == first.remaining_planner_retries - 1


@pytest.mark.asyncio
async def test_t_cx154_v95_routing_behavior_is_unchanged() -> None:
    repository = InMemorySignalRepository()
    test_id, ref_id = _store_pair(repository)
    tools = RecordingToolService(repository)
    steps = [
        ScriptedStep(
            expected_observation_count=0,
            decision=CallToolDecision(
                task_assessment=ASSESSMENT,
                call=AnalyzeHarmonicDistortionCall(args=HarmonicDistortionInput()),
                purpose="historical v9.5 still executes ordinary harmonic",
            ),
        ),
        ScriptedStep(
            expected_observation_count=1,
            decision=_finish_inconclusive(),
        ),
    ]
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=tools,
        planner=ScriptedPlanner(steps),
        causal_policy_version="v9_5_contextual",
    )
    result = await runtime.run(
        signal_id=test_id,
        user_request="Why distorted?",
        stimulus_context=StimulusContext(
            mode="paired_reference",
            test_signal_id=test_id,
            reference_signal_id=ref_id,
            assertion_source="user_supplied",
        ),
    )
    assert tools.invoked_tools == ["analyze_harmonic_distortion"]
    assert len(result.observations) == 1
