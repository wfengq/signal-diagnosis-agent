"""T-CX163–T-CX165: deterministic regressions for recorded v9.5 failure families."""

from __future__ import annotations

import pytest

from signal_diag.agent.diagnosis import validate_finish_decision
from signal_diag.agent.models import (
    AnalyzeContextualDistortionCall,
    AnalyzeHarmonicDistortionCall,
    CallToolDecision,
    DetectClippingCall,
    DiagnosisClaim,
    DiagnosisValidationError,
    FinishDecision,
    HarmonicDistortionInput,
    TaskAssessment,
)
from signal_diag.agent.planner import ScriptedPlanner, ScriptedStep
from signal_diag.agent.policies import AgentLimits
from signal_diag.agent.runtime import DistortionDiagnosisRuntime
from signal_diag.rules.models import RuleEvaluation
from signal_diag.signal.context import StimulusContext
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.signal.synthetic import generate_sine
from signal_diag.tools.contracts import ClippingInput, ContextualDistortionInput
from signal_diag.tools.evidence import Evidence
from signal_diag.tools.service import SignalToolService
from tests.conftest import store_synthetic_case

ASSESSMENT = TaskAssessment(
    task_type="distortion_analysis",
    objective="diagnose S1 distortion",
)


def _ev(
    evidence_id: str,
    metric: str,
    value: object,
    *,
    source_tool: str = "detect_clipping",
    unit: str | None = None,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source_tool=source_tool,  # type: ignore[arg-type]
        call_id=f"call_{source_tool}_000000",
        metric=metric,
        value=value,  # type: ignore[arg-type]
        unit=unit,
        channel="mixdown",
    )


def _rule(
    evaluation_id: str,
    rule_id: str,
    judgment: str,
    *,
    profile_id: str = "profile_s1_contextual_comparison",
) -> RuleEvaluation:
    return RuleEvaluation(
        evaluation_id=evaluation_id,
        rule_id=rule_id,
        judgment=judgment,  # type: ignore[arg-type]
        observed_value=None,
        comparator="eq",
        threshold=True,
        profile_id=profile_id,
        profile_version="1.0.0",
        evidence_refs=(),
    )


def _paired_no_fault_pack() -> tuple[tuple[Evidence, ...], tuple[RuleEvaluation, ...]]:
    evidence = (
        _ev("ev_mech", "clipping_mechanism", False),
        _ev("ev_detected", "clipping_detected", False),
        _ev(
            "ev_series",
            "test_series_kind",
            "even_order_present",
            source_tool="analyze_contextual_distortion",
        ),
        _ev(
            "ev_growth",
            "even_harmonic_growth_percent",
            0.1,
            source_tool="analyze_contextual_distortion",
            unit="%",
        ),
    )
    rules = (
        _rule(
            "ruleval_ratio",
            "rule_clipping_ratio_acceptable",
            "pass",
            profile_id="profile_s1_distortion",
        ),
        _rule(
            "ruleval_flat",
            "rule_flat_top_absent",
            "pass",
            profile_id="profile_s1_distortion",
        ),
        _rule("ruleval_valid", "rule_contextual_analysis_valid", "pass"),
        _rule("ruleval_f0", "rule_contextual_f0_compatible", "pass"),
        _rule("ruleval_ref_ratio", "rule_reference_clipping_ratio_acceptable", "pass"),
        _rule("ruleval_ref_flat", "rule_reference_flat_top_absent", "pass"),
        _rule("ruleval_growth", "rule_even_harmonic_growth_acceptable", "pass"),
    )
    return evidence, rules


def _paired_ctx() -> StimulusContext:
    return StimulusContext(
        mode="paired_reference",
        test_signal_id="sig_test",
        reference_signal_id="sig_ref",
        assertion_source="user_supplied",
    )


def test_t_cx163_no_fault_citation_replay() -> None:
    evidence, rules = _paired_no_fault_pack()
    known_evidence = frozenset(item.evidence_id for item in evidence)
    known_rules = frozenset(item.evaluation_id for item in rules)
    wrong = FinishDecision(
        outcome="no_supported_fault",
        claims=(
            DiagnosisClaim(
                claim_id="claim_clean_wrong",
                fault_type="no_supported_fault",
                statement="Cites clipping_detected only.",
                evidence_refs=("ev_detected",),
                rule_refs=tuple(item.evaluation_id for item in rules),
            ),
        ),
        confidence_label="medium",
        limitations=("relative to reference",),
    )
    with pytest.raises(DiagnosisValidationError, match="clipping_mechanism=false"):
        validate_finish_decision(
            wrong,
            known_evidence_ids=known_evidence,
            known_rule_evaluation_ids=known_rules,
            task_assessment=ASSESSMENT,
            evidence=evidence,
            rule_evaluations=rules,
            stimulus_context=_paired_ctx(),
            causal_policy_version="v9_6_contextual",
        )

    correct = FinishDecision(
        outcome="no_supported_fault",
        claims=(
            DiagnosisClaim(
                claim_id="claim_clean",
                fault_type="no_supported_fault",
                statement="No supported fault relative to the reference.",
                evidence_refs=("ev_mech",),
                rule_refs=tuple(item.evaluation_id for item in rules),
            ),
        ),
        confidence_label="medium",
        limitations=("Finding is relative to the supplied reference.",),
    )
    validate_finish_decision(
        correct,
        known_evidence_ids=known_evidence,
        known_rule_evaluation_ids=known_rules,
        task_assessment=ASSESSMENT,
        evidence=evidence,
        rule_evaluations=rules,
        stimulus_context=_paired_ctx(),
        causal_policy_version="v9_6_contextual",
    )


@pytest.mark.asyncio
async def test_t_cx164_combined_routing_and_causal_closure_replay() -> None:
    repository = InMemorySignalRepository()
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
    invoked: list[str] = []

    class RecordingService(SignalToolService):
        def analyze_harmonic_distortion(self, signal_id, args):  # type: ignore[no-untyped-def]
            invoked.append("analyze_harmonic_distortion")
            return super().analyze_harmonic_distortion(signal_id, args)

        def analyze_contextual_distortion(self, context, args):  # type: ignore[no-untyped-def]
            invoked.append("analyze_contextual_distortion")
            return super().analyze_contextual_distortion(context, args)

        def detect_clipping(self, signal_id, args):  # type: ignore[no-untyped-def]
            invoked.append("detect_clipping")
            return super().detect_clipping(signal_id, args)

    tools = RecordingService(repository)
    steps = [
        ScriptedStep(
            expected_observation_count=0,
            decision=CallToolDecision(
                task_assessment=ASSESSMENT,
                call=DetectClippingCall(args=ClippingInput()),
                purpose="clipping path",
            ),
        ),
        ScriptedStep(
            expected_observation_count=1,
            decision=CallToolDecision(
                call=AnalyzeHarmonicDistortionCall(args=HarmonicDistortionInput()),
                purpose="wrong ordinary harmonic",
            ),
        ),
        ScriptedStep(
            expected_observation_count=1,
            decision=CallToolDecision(
                call=AnalyzeContextualDistortionCall(args=ContextualDistortionInput()),
                purpose="correct contextual harmonic",
            ),
        ),
        ScriptedStep(
            expected_observation_count=2,
            decision=FinishDecision(
                outcome="inconclusive",
                claims=(),
                confidence_label="low",
                limitations=("routing replay stop",),
            ),
        ),
    ]
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=tools,
        planner=ScriptedPlanner(steps),
        causal_policy_version="v9_6_contextual",
        limits=AgentLimits(max_planner_retries=3, max_tool_calls=8),
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
    assert "analyze_harmonic_distortion" not in invoked
    assert invoked.count("detect_clipping") == 1
    assert invoked.count("analyze_contextual_distortion") == 1
    assert any("analyze_contextual_distortion" in message for message in result.errors)

    clip_rules = (
        _rule(
            "ruleval_ratio",
            "rule_clipping_ratio_acceptable",
            "fail",
            profile_id="profile_s1_distortion",
        ),
    )
    harm_rules = (
        _rule("ruleval_valid", "rule_contextual_analysis_valid", "pass"),
        _rule("ruleval_f0", "rule_contextual_f0_compatible", "pass"),
        _rule("ruleval_ref_ratio", "rule_reference_clipping_ratio_acceptable", "pass"),
        _rule("ruleval_ref_flat", "rule_reference_flat_top_absent", "pass"),
        _rule("ruleval_growth", "rule_even_harmonic_growth_acceptable", "fail"),
    )
    evidence = (
        _ev("ev_mech", "clipping_mechanism", True),
        _ev(
            "ev_series",
            "test_series_kind",
            "even_order_present",
            source_tool="analyze_contextual_distortion",
        ),
        _ev(
            "ev_growth",
            "even_harmonic_growth_percent",
            3.0,
            source_tool="analyze_contextual_distortion",
            unit="%",
        ),
    )
    incomplete = FinishDecision(
        outcome="supported_fault",
        claims=(
            DiagnosisClaim(
                claim_id="claim_clip",
                fault_type="clipping",
                statement="Clipping independently supported.",
                evidence_refs=("ev_mech",),
                rule_refs=("ruleval_ratio",),
            ),
            DiagnosisClaim(
                claim_id="claim_harm_incomplete",
                fault_type="harmonic_distortion",
                statement="Missing growth FAIL citation.",
                evidence_refs=("ev_series", "ev_growth"),
                rule_refs=(
                    "ruleval_valid",
                    "ruleval_f0",
                    "ruleval_ref_ratio",
                    "ruleval_ref_flat",
                ),
            ),
        ),
        confidence_label="medium",
        limitations=(),
    )
    with pytest.raises(DiagnosisValidationError, match="harmonic growth"):
        validate_finish_decision(
            incomplete,
            known_evidence_ids=frozenset(item.evidence_id for item in evidence),
            known_rule_evaluation_ids=frozenset(
                item.evaluation_id for item in (*clip_rules, *harm_rules)
            ),
            task_assessment=ASSESSMENT,
            evidence=evidence,
            rule_evaluations=(*clip_rules, *harm_rules),
            stimulus_context=_paired_ctx(),
            causal_policy_version="v9_6_contextual",
        )

    complete = FinishDecision(
        outcome="supported_fault",
        claims=(
            DiagnosisClaim(
                claim_id="claim_clip",
                fault_type="clipping",
                statement="Clipping independently supported.",
                evidence_refs=("ev_mech",),
                rule_refs=("ruleval_ratio",),
            ),
            DiagnosisClaim(
                claim_id="claim_harm",
                fault_type="harmonic_distortion",
                statement="Contextual harmonic growth independently supported.",
                evidence_refs=("ev_series", "ev_growth"),
                rule_refs=tuple(item.evaluation_id for item in harm_rules),
            ),
        ),
        confidence_label="high",
        limitations=(),
    )
    validate_finish_decision(
        complete,
        known_evidence_ids=frozenset(item.evidence_id for item in evidence),
        known_rule_evaluation_ids=frozenset(
            item.evaluation_id for item in (*clip_rules, *harm_rules)
        ),
        task_assessment=ASSESSMENT,
        evidence=evidence,
        rule_evaluations=(*clip_rules, *harm_rules),
        stimulus_context=_paired_ctx(),
        causal_policy_version="v9_6_contextual",
    )


@pytest.mark.parametrize(
    ("branch",),
    [("natural_even_no_fault",), ("clipping_with_invalid_contextual",)],
)
def test_t_cx165_natural_even_and_clipping_preservation(branch: str) -> None:
    if branch == "natural_even_no_fault":
        evidence, rules = _paired_no_fault_pack()
        decision = FinishDecision(
            outcome="no_supported_fault",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_clean",
                    fault_type="no_supported_fault",
                    statement="No growth relative to reference.",
                    evidence_refs=("ev_mech",),
                    rule_refs=tuple(item.evaluation_id for item in rules),
                ),
            ),
            confidence_label="medium",
            limitations=("Relative to the supplied reference.",),
        )
        validate_finish_decision(
            decision,
            known_evidence_ids=frozenset(item.evidence_id for item in evidence),
            known_rule_evaluation_ids=frozenset(item.evaluation_id for item in rules),
            task_assessment=ASSESSMENT,
            evidence=evidence,
            rule_evaluations=rules,
            stimulus_context=_paired_ctx(),
            causal_policy_version="v9_6_contextual",
        )
        return

    evidence = (
        _ev("ev_mech", "clipping_mechanism", True),
        _ev(
            "ev_valid",
            "comparison_valid",
            False,
            source_tool="analyze_contextual_distortion",
        ),
    )
    rules = (
        _rule(
            "ruleval_ratio",
            "rule_clipping_ratio_acceptable",
            "fail",
            profile_id="profile_s1_distortion",
        ),
        _rule("ruleval_valid", "rule_contextual_analysis_valid", "fail"),
    )
    decision = FinishDecision(
        outcome="supported_fault",
        claims=(
            DiagnosisClaim(
                claim_id="claim_clip",
                fault_type="clipping",
                statement="Clipping remains independently supported.",
                evidence_refs=("ev_mech",),
                rule_refs=("ruleval_ratio",),
            ),
        ),
        confidence_label="high",
        limitations=("Contextual harmonic comparison remains invalid.",),
    )
    validate_finish_decision(
        decision,
        known_evidence_ids=frozenset(item.evidence_id for item in evidence),
        known_rule_evaluation_ids=frozenset(item.evaluation_id for item in rules),
        task_assessment=ASSESSMENT,
        evidence=evidence,
        rule_evaluations=rules,
        stimulus_context=_paired_ctx(),
        causal_policy_version="v9_6_contextual",
    )
