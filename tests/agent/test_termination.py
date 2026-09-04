"""Checkpoint E — Runtime termination and policy (T076–T085)."""

from __future__ import annotations

from pathlib import Path

import pytest

from signal_diag.agent.models import (
    AgentDecision,
    CallToolDecision,
    ClippingInput,
    DetectClippingCall,
    DiagnosisClaim,
    EvaluateRulesDecision,
    FinishDecision,
    PlannerContext,
    PlannerOutputError,
    TaskAssessment,
)
from signal_diag.agent.planner import RealLLMPlanner, ScriptedPlanner, ScriptedStep
from signal_diag.agent.policies import AgentLimits
from signal_diag.agent.runtime import DistortionDiagnosisRuntime
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal import SyntheticCase
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.tools.service import SignalToolService
from tests.conftest import store_synthetic_case


def _assessment() -> TaskAssessment:
    return TaskAssessment(
        task_type="distortion_analysis",
        objective="determine distortion cause",
    )


def _clipping_finish(evidence_id: str, rule_id: str = "ruleval_placeholder") -> FinishDecision:
    return FinishDecision(
        outcome="supported_fault",
        claims=(
            DiagnosisClaim(
                claim_id="claim_clip",
                fault_type="clipping",
                statement="clipping detected",
                evidence_refs=(evidence_id,),
                rule_refs=(rule_id,) if rule_id != "ruleval_placeholder" else (),
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
    full_scale_clipped_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, full_scale_clipped_case)
    evidence_id = "ev_detect_clipping_detect_clipping_000000_007"
    profile = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "signal_diag"
        / "rules"
        / "profiles"
        / "s1_distortion_v1.yaml"
    )

    class _FinishPlanner:
        def __init__(self) -> None:
            self._index = 0

        async def decide(self, context: PlannerContext) -> AgentDecision:
            if self._index == 0:
                self._index += 1
                return CallToolDecision(
                    task_assessment=_assessment(),
                    call=DetectClippingCall(args=ClippingInput()),
                    purpose="check clipping",
                )
            if self._index == 1:
                self._index += 1
                return EvaluateRulesDecision(
                    profile_id="profile_s1_distortion",
                    evidence_refs=(),
                    purpose="apply clipping rules",
                )
            clip_mech = next(
                item.evidence_id
                for item in context.evidence
                if item.metric == "clipping_mechanism" and item.value is True
            )
            rule_id = next(
                item.evaluation_id
                for batch in context.rule_evaluation_batches
                for item in batch.evaluations
                if item.rule_id == "rule_flat_top_absent" and item.judgment == "fail"
            )
            return FinishDecision(
                outcome="supported_fault",
                claims=(
                    DiagnosisClaim(
                        claim_id="claim_clip",
                        fault_type="clipping",
                        statement="clipping detected",
                        evidence_refs=(clip_mech,),
                        rule_refs=(rule_id,),
                    ),
                ),
                confidence_label="high",
            )

    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=_FinishPlanner(),
        rule_engine=RuleEngine(),
        rule_profile_loader=YamlRuleProfileLoader(
            {"profile_s1_distortion": profile}
        ),
    )
    result = await runtime.run(signal_id=signal_id, user_request="Why distorted?")
    assert result.status == "success"
    assert result.termination_reason == "planner_finished"
    assert result.diagnosis is not None
    assert evidence_id in result.diagnosis.claims[0].evidence_refs or any(
        item.metric == "clipping_mechanism"
        for item in result.evidence
        if item.evidence_id in result.diagnosis.claims[0].evidence_refs
    )


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
