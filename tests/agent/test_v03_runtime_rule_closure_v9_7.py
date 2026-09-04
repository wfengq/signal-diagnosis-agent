"""T-CX175–T-CX176: automatic v9.7 rule closure in DistortionDiagnosisRuntime."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from signal_diag.agent.models import (
    AnalyzeContextualDistortionCall,
    CallToolDecision,
    DetectClippingCall,
    FinishDecision,
    TaskAssessment,
)
from signal_diag.agent.planner import ScriptedPlanner, ScriptedStep
from signal_diag.agent.policies import AgentLimits
from signal_diag.agent.runtime import DistortionDiagnosisRuntime
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal.context import StimulusContext
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.signal.synthetic import generate_sine
from signal_diag.tools.contracts import ClippingInput, ContextualDistortionInput
from signal_diag.tools.results import ToolResult
from signal_diag.tools.service import SignalToolService
from tests.conftest import store_synthetic_case

REPO = Path(__file__).resolve().parents[2]
PROFILE_S1 = REPO / "src/signal_diag/rules/profiles/s1_distortion_v1.yaml"
PROFILE_CX = REPO / "src/signal_diag/rules/profiles/s1_contextual_comparison_v1.yaml"

ASSESSMENT = TaskAssessment(
    task_type="distortion_analysis",
    objective="diagnose S1 distortion",
)


class RecordingRuleEngine(RuleEngine):
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[str, ...], frozenset[str] | None]] = []

    def evaluate_profile(self, profile, evidence, *, evidence_filter=None):  # type: ignore[no-untyped-def]
        self.calls.append(
            (
                profile.profile_id,
                tuple(item.evidence_id for item in evidence),
                evidence_filter,
            )
        )
        return super().evaluate_profile(
            profile, evidence, evidence_filter=evidence_filter
        )


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
    return store_synthetic_case(repository, test), store_synthetic_case(repository, ref)


def _finish() -> FinishDecision:
    return FinishDecision(
        outcome="inconclusive",
        claims=(),
        confidence_label="low",
        limitations=("runtime closure test stop",),
    )


def _loader() -> YamlRuleProfileLoader:
    return YamlRuleProfileLoader(
        {
            "profile_s1_distortion": PROFILE_S1,
            "profile_s1_contextual_comparison": PROFILE_CX,
        }
    )


@pytest.mark.asyncio
async def test_t_cx175_automatic_clipping_closure_increments_once() -> None:
    repository = InMemorySignalRepository()
    test_id, ref_id = _store_pair(repository)
    engine = RecordingRuleEngine()
    contexts: list[Any] = []

    class CapturePlanner(ScriptedPlanner):
        async def decide(self, context):  # type: ignore[no-untyped-def]
            contexts.append(context)
            return await super().decide(context)

    steps = [
        ScriptedStep(
            expected_observation_count=0,
            decision=CallToolDecision(
                task_assessment=ASSESSMENT,
                call=DetectClippingCall(args=ClippingInput()),
                purpose="clipping measurement",
            ),
        ),
        ScriptedStep(
            expected_observation_count=1,
            decision=_finish(),
        ),
    ]
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=CapturePlanner(steps),
        rule_engine=engine,
        rule_profile_loader=_loader(),
        causal_policy_version="v9_7_deterministic_rule_closure",
        limits=AgentLimits(max_planner_retries=2, max_tool_calls=4, max_rule_evaluations=4),
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
    assert len(engine.calls) == 1
    profile_id, evidence_ids, evidence_filter = engine.calls[0]
    assert profile_id == "profile_s1_distortion"
    assert evidence_filter == frozenset(evidence_ids)
    assert len(result.rule_evaluation_batches) == 1
    assert result.rule_evaluation_batches[0].profile_id == "profile_s1_distortion"
    assert len(contexts) >= 2
    second = contexts[1]
    assert len(second.rule_evaluation_batches) == 1
    obs_refs = second.observations[0].evidence_refs
    assert evidence_ids == obs_refs
    assert evidence_filter == frozenset(obs_refs)


@pytest.mark.asyncio
async def test_t_cx175_automatic_contextual_closure_uses_contextual_profile() -> None:
    repository = InMemorySignalRepository()
    test_id, ref_id = _store_pair(repository)
    engine = RecordingRuleEngine()
    steps = [
        ScriptedStep(
            expected_observation_count=0,
            decision=CallToolDecision(
                task_assessment=ASSESSMENT,
                call=AnalyzeContextualDistortionCall(args=ContextualDistortionInput()),
                purpose="contextual measurement",
            ),
        ),
        ScriptedStep(
            expected_observation_count=1,
            decision=_finish(),
        ),
    ]
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=ScriptedPlanner(steps),
        rule_engine=engine,
        rule_profile_loader=_loader(),
        causal_policy_version="v9_7_deterministic_rule_closure",
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
    assert len(engine.calls) == 1
    assert engine.calls[0][0] == "profile_s1_contextual_comparison"
    assert result.rule_evaluation_batches[0].profile_id == (
        "profile_s1_contextual_comparison"
    )


@pytest.mark.asyncio
async def test_t_cx175_bound_stops_before_tool_when_no_rule_slots() -> None:
    repository = InMemorySignalRepository()
    test_id, ref_id = _store_pair(repository)

    class GuardedTools(SignalToolService):
        def __init__(self, repo: InMemorySignalRepository) -> None:
            super().__init__(repo)
            self.invoked = False

        def detect_clipping(self, signal_id, args):  # type: ignore[no-untyped-def]
            self.invoked = True
            return super().detect_clipping(signal_id, args)

    tools = GuardedTools(repository)
    steps = [
        ScriptedStep(
            expected_observation_count=0,
            decision=CallToolDecision(
                task_assessment=ASSESSMENT,
                call=DetectClippingCall(args=ClippingInput()),
                purpose="should not run",
            ),
        ),
    ]
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=tools,
        planner=ScriptedPlanner(steps),
        rule_engine=RecordingRuleEngine(),
        rule_profile_loader=_loader(),
        causal_policy_version="v9_7_deterministic_rule_closure",
        limits=AgentLimits(max_planner_retries=2, max_tool_calls=4, max_rule_evaluations=0),
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
    assert tools.invoked is False
    assert result.termination_reason == "max_rule_evaluations"
    assert result.observations == ()
    assert result.rule_evaluation_batches == ()


@pytest.mark.asyncio
async def test_t_cx176_dependency_missing_terminates_runtime_error() -> None:
    repository = InMemorySignalRepository()
    test_id, ref_id = _store_pair(repository)
    steps = [
        ScriptedStep(
            expected_observation_count=0,
            decision=CallToolDecision(
                task_assessment=ASSESSMENT,
                call=DetectClippingCall(args=ClippingInput()),
                purpose="clipping measurement",
            ),
        ),
    ]
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=ScriptedPlanner(steps),
        rule_engine=None,
        rule_profile_loader=None,
        causal_policy_version="v9_7_deterministic_rule_closure",
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
    assert result.termination_reason == "runtime_error"
    assert result.status == "error"
    assert any("rule" in message.lower() for message in result.errors)


@pytest.mark.asyncio
async def test_t_cx176_empty_non_error_evidence_terminates_runtime_error() -> None:
    repository = InMemorySignalRepository()
    test_id, ref_id = _store_pair(repository)

    class EmptyEvidenceTools(SignalToolService):
        def detect_clipping(self, signal_id, args):  # type: ignore[no-untyped-def]
            return ToolResult(
                call_id="call_empty_clip",
                tool_name="detect_clipping",
                status="invalid",
                result=None,
                evidence=(),
                warnings=("synthetic empty evidence for closure invariant",),
                error_message=None,
            )

    steps = [
        ScriptedStep(
            expected_observation_count=0,
            decision=CallToolDecision(
                task_assessment=ASSESSMENT,
                call=DetectClippingCall(args=ClippingInput()),
                purpose="empty evidence",
            ),
        ),
    ]
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=EmptyEvidenceTools(repository),
        planner=ScriptedPlanner(steps),
        rule_engine=RecordingRuleEngine(),
        rule_profile_loader=_loader(),
        causal_policy_version="v9_7_deterministic_rule_closure",
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
    assert result.termination_reason == "runtime_error"
    assert result.rule_evaluation_batches == ()


@pytest.mark.asyncio
async def test_t_cx176_errored_tool_appends_no_rule_batch() -> None:
    repository = InMemorySignalRepository()
    test_id, ref_id = _store_pair(repository)
    engine = RecordingRuleEngine()

    class ErrorTools(SignalToolService):
        def detect_clipping(self, signal_id, args):  # type: ignore[no-untyped-def]
            return ToolResult(
                call_id="call_err_clip",
                tool_name="detect_clipping",
                status="error",
                result=None,
                evidence=(),
                warnings=(),
                error_message="boom",
            )

    steps = [
        ScriptedStep(
            expected_observation_count=0,
            decision=CallToolDecision(
                task_assessment=ASSESSMENT,
                call=DetectClippingCall(args=ClippingInput()),
                purpose="errored tool",
            ),
        ),
        ScriptedStep(
            expected_observation_count=1,
            decision=_finish(),
        ),
    ]
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=ErrorTools(repository),
        planner=ScriptedPlanner(steps),
        rule_engine=engine,
        rule_profile_loader=_loader(),
        causal_policy_version="v9_7_deterministic_rule_closure",
        limits=AgentLimits(
            max_planner_retries=2,
            max_tool_calls=4,
            max_rule_evaluations=4,
            max_no_progress=5,
        ),
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
    assert engine.calls == []
    assert result.rule_evaluation_batches == ()
    assert len(result.observations) == 1
    assert result.observations[0].status == "error"
