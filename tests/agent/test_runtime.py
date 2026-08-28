"""Checkpoint E — Runtime core path (T071–T075)."""

from __future__ import annotations

import pytest

from signal_diag.agent.models import (
    AnalyzeHarmonicDistortionCall,
    CallToolDecision,
    ClippingInput,
    DetectClippingCall,
    DiagnosisClaim,
    FinishDecision,
    HarmonicDistortionInput,
    TaskAssessment,
)
from signal_diag.agent.planner import ScriptedPlanner, ScriptedStep
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


@pytest.mark.asyncio
async def test_t071_runtime_initial_context_is_compact(
    repository: InMemorySignalRepository,
    clipped_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, clipped_case)
    captured: list[object] = []

    class CapturePlanner(ScriptedPlanner):
        async def decide(self, context):  # type: ignore[no-untyped-def]
            captured.append(context)
            return await super().decide(context)

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
            decision=FinishDecision(
                outcome="supported_fault",
                claims=(
                    DiagnosisClaim(
                        claim_id="claim_clip",
                        fault_type="clipping",
                        statement="clipping found",
                        evidence_refs=("ev_placeholder",),
                    ),
                ),
                confidence_label="high",
            ),
        ),
    ]
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=CapturePlanner(steps),
    )
    await runtime.run(signal_id=signal_id, user_request="Why distorted?")
    first = captured[0]
    assert len(first.observations) == 0  # type: ignore[attr-defined]
    dumped = first.model_dump_json()  # type: ignore[attr-defined]
    assert "frequencies_hz" not in dumped


@pytest.mark.asyncio
async def test_t072_executes_named_tool_with_runtime_injected_signal_id(
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
            decision=FinishDecision(
                outcome="inconclusive",
                claims=(),
                confidence_label="low",
                limitations=("stop early for test",),
            ),
        ),
    ]
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=ScriptedPlanner(steps),
    )
    result = await runtime.run(signal_id=signal_id, user_request="Why distorted?")
    assert len(result.observations) == 1
    assert result.observations[0].tool_name == "detect_clipping"
    assert "signal_id" not in result.observations[0].normalized_arguments


@pytest.mark.asyncio
async def test_t073_observation_propagates_to_next_context(
    repository: InMemorySignalRepository,
    clipped_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, clipped_case)
    seen_counts: list[int] = []

    class CountPlanner(ScriptedPlanner):
        async def decide(self, context):  # type: ignore[no-untyped-def]
            seen_counts.append(len(context.observations))
            return await super().decide(context)

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
        ScriptedStep(
            expected_observation_count=2,
            decision=FinishDecision(
                outcome="inconclusive",
                claims=(),
                confidence_label="low",
                limitations=("done",),
            ),
        ),
    ]
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=CountPlanner(steps),
    )
    await runtime.run(signal_id=signal_id, user_request="Why distorted?")
    assert seen_counts == [0, 1, 2]
    assert seen_counts[-1] == 2


@pytest.mark.asyncio
async def test_t074_evidence_propagates_unchanged(
    repository: InMemorySignalRepository,
    clipped_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, clipped_case)
    evidence_snapshots: list[tuple[str, ...]] = []

    class EvidencePlanner(ScriptedPlanner):
        async def decide(self, context):  # type: ignore[no-untyped-def]
            evidence_snapshots.append(
                tuple(item.evidence_id for item in context.evidence)
            )
            return await super().decide(context)

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
            decision=FinishDecision(
                outcome="inconclusive",
                claims=(),
                confidence_label="low",
                limitations=("done",),
            ),
        ),
    ]
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=EvidencePlanner(steps),
    )
    result = await runtime.run(signal_id=signal_id, user_request="Why distorted?")
    assert evidence_snapshots[0] == ()
    assert len(evidence_snapshots[1]) > 0
    assert evidence_snapshots[1] == tuple(item.evidence_id for item in result.evidence)


@pytest.mark.asyncio
async def test_t075_invalid_observation_allows_replan(
    repository: InMemorySignalRepository,
    noise_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, noise_case)
    steps = [
        ScriptedStep(
            expected_observation_count=0,
            decision=CallToolDecision(
                task_assessment=_assessment(),
                call=AnalyzeHarmonicDistortionCall(
                    args=HarmonicDistortionInput()
                ),
                purpose="try harmonic on noise",
            ),
        ),
        ScriptedStep(
            expected_observation_count=1,
            decision=FinishDecision(
                outcome="inconclusive",
                claims=(),
                confidence_label="low",
                limitations=("invalid harmonic on noise",),
            ),
        ),
    ]
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=ScriptedPlanner(steps),
    )
    result = await runtime.run(signal_id=signal_id, user_request="Why distorted?")
    assert result.observations[0].status == "invalid"
    assert result.termination_reason == "planner_finished"
