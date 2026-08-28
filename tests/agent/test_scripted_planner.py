"""Checkpoint D — ScriptedPlanner (T068–T070)."""

import pytest

from signal_diag.agent.models import (
    CallToolDecision,
    ClippingInput,
    DetectClippingCall,
    FinishDecision,
    Observation,
    PlannerContext,
    PlannerOutputError,
    ScriptExhaustedError,
    TaskAssessment,
)
from signal_diag.agent.planner import ScriptedPlanner, ScriptedStep
from signal_diag.signal.models import SignalMeta
from signal_diag.tools.registry import get_tool_descriptors


def _context(*, observation_count: int = 0) -> PlannerContext:
    observations = tuple(
        Observation(
            observation_id=f"obs_{index:03d}",
            call_id=f"call_test_{index:03d}",
            tool_name="detect_clipping",
            normalized_arguments={"channel": "mixdown"},
            purpose="prior step",
            status="success",
        )
        for index in range(observation_count)
    )
    return PlannerContext(
        run_id="run_script",
        user_request="Why distorted?",
        signal_meta=SignalMeta(
            signal_id="sig_script",
            source_type="generated",
            sample_rate_hz=48_000,
            channels=1,
            num_samples=96_000,
            duration_s=2.0,
            original_dtype="float32",
        ),
        task_assessment=None,
        observations=observations,
        evidence=(),
        tool_history=(),
        available_tools=get_tool_descriptors(),
        remaining_tool_calls=8,
        remaining_planner_retries=2,
        no_progress_count=0,
    )


def _call_decision(purpose: str) -> CallToolDecision:
    return CallToolDecision(
        task_assessment=TaskAssessment(
            task_type="distortion_analysis",
            objective="inspect clipping",
        ),
        call=DetectClippingCall(args=ClippingInput()),
        purpose=purpose,
    )


@pytest.mark.asyncio
async def test_t068_script_returns_decisions_in_order() -> None:
    steps = [
        ScriptedStep(expected_observation_count=0, decision=_call_decision("first")),
        ScriptedStep(expected_observation_count=1, decision=_call_decision("second")),
    ]
    planner = ScriptedPlanner(steps)
    first = await planner.decide(_context(observation_count=0))
    assert first.purpose == "first"
    second = await planner.decide(_context(observation_count=1))
    assert second.purpose == "second"


@pytest.mark.asyncio
async def test_t069_script_checks_observation_count_and_evidence_metrics() -> None:
    from signal_diag.tools.evidence import Evidence

    planner = ScriptedPlanner(
        [
            ScriptedStep(
                expected_observation_count=1,
                required_evidence_metrics=("clipping_detected",),
                decision=_call_decision("needs evidence"),
            )
        ]
    )
    with pytest.raises(PlannerOutputError):
        await planner.decide(_context(observation_count=0))

    context_with_evidence = PlannerContext(
        **{
            **_context(observation_count=1).model_dump(),
            "evidence": (
                Evidence(
                    evidence_id="ev_test_001",
                    source_tool="detect_clipping",
                    call_id="call_detect_clipping_000000",
                    metric="clipping_detected",
                    value=True,
                    channel="mixdown",
                ),
            ),
        }
    )
    decision = await planner.decide(context_with_evidence)
    assert decision.purpose == "needs evidence"


@pytest.mark.asyncio
async def test_t070_script_exhaustion_raises() -> None:
    planner = ScriptedPlanner(
        [
            ScriptedStep(
                expected_observation_count=0,
                decision=FinishDecision(
                    task_assessment=TaskAssessment(
                        task_type="unsupported",
                        objective="n/a",
                    ),
                    outcome="inconclusive",
                    claims=(),
                    confidence_label="low",
                    limitations=("done",),
                ),
            )
        ]
    )
    await planner.decide(_context())
    with pytest.raises(ScriptExhaustedError):
        await planner.decide(_context())
