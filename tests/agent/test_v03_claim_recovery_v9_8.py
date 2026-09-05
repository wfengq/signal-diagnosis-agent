"""T-CX187–T-CX188 / T-CX190: v9.8 claim-reference recovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from signal_diag.agent.diagnosis import validate_finish_decision
from signal_diag.agent.models import (
    CallToolDecision,
    DetectClippingCall,
    DiagnosisClaim,
    DiagnosisValidationError,
    EvaluateRulesDecision,
    FinishDecision,
    TaskAssessment,
)
from signal_diag.agent.planner import ScriptedPlanner, ScriptedStep
from signal_diag.agent.policies import AgentLimits
from signal_diag.agent.rule_closure import required_rule_profile
from signal_diag.agent.runtime import DistortionDiagnosisRuntime
from signal_diag.knowledge.index import KnowledgeIndex
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.rules.models import RuleEvaluation
from signal_diag.signal.context import StimulusContext
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.signal.synthetic import generate_sine
from signal_diag.tools.contracts import ClippingInput
from signal_diag.tools.evidence import Evidence
from signal_diag.tools.service import SignalToolService
from tests.conftest import store_synthetic_case

ASSESSMENT = TaskAssessment(
    task_type="distortion_analysis",
    objective="diagnose S1 distortion",
)
REPO = Path(__file__).resolve().parents[2]
PROFILE_S1 = REPO / "src/signal_diag/rules/profiles/s1_distortion_v1.yaml"
PROFILE_CX = REPO / "src/signal_diag/rules/profiles/s1_contextual_comparison_v1.yaml"
CORPUS = REPO / "src/signal_diag/knowledge/corpus"


def _ev(
    evidence_id: str,
    metric: str,
    value: object,
    *,
    source_tool: str = "analyze_contextual_distortion",
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source_tool=source_tool,  # type: ignore[arg-type]
        call_id=f"call_{source_tool}_000001",
        metric=metric,
        value=value,  # type: ignore[arg-type]
        unit="%" if "percent" in metric else None,
        channel="mixdown",
    )


def _rule(
    evaluation_id: str,
    rule_id: str,
    judgment: str,
    *,
    evidence_refs: tuple[str, ...] = (),
) -> RuleEvaluation:
    return RuleEvaluation(
        evaluation_id=evaluation_id,
        rule_id=rule_id,
        judgment=judgment,  # type: ignore[arg-type]
        observed_value=None,
        comparator="eq",
        threshold=True,
        profile_id="profile_s1_contextual_comparison",
        profile_version="1.0.0",
        evidence_refs=evidence_refs,
    )


def _nominal_pack() -> tuple[tuple[Evidence, ...], tuple[RuleEvaluation, ...]]:
    evidence = (
        _ev("ev_ctx_valid", "context_valid", True),
        _ev("ev_f0_ok", "f0_compatible", True),
        _ev("ev_series", "test_series_kind", "even_order_present"),
        _ev("ev_thd", "test_thd_percent", 10.3),
        _ev("ev_mech", "clipping_mechanism", False, source_tool="detect_clipping"),
    )
    rules = (
        _rule(
            "ruleval_analysis",
            "rule_contextual_analysis_valid",
            "pass",
            evidence_refs=("ev_ctx_valid",),
        ),
        _rule(
            "ruleval_f0",
            "rule_contextual_f0_compatible",
            "pass",
            evidence_refs=("ev_f0_ok",),
        ),
        _rule(
            "ruleval_thd_fail",
            "rule_nominal_thd_acceptable",
            "fail",
            evidence_refs=("ev_thd",),
        ),
    )
    return evidence, rules


def _nominal_context(signal_id: str = "sig_test") -> StimulusContext:
    return StimulusContext(
        mode="nominal_single_tone",
        test_signal_id=signal_id,
        nominal_fundamental_hz=440.0,
        stimulus_kind="single_tone",
        assertion_source="user_supplied",
    )


def _finish(
    *,
    evidence_refs: tuple[str, ...],
    rule_refs: tuple[str, ...],
) -> FinishDecision:
    return FinishDecision(
        outcome="supported_fault",
        claims=(
            DiagnosisClaim(
                claim_id="claim_harm",
                fault_type="harmonic_distortion",
                statement="Nominal even-order harmonic distortion is supported.",
                evidence_refs=evidence_refs,
                rule_refs=rule_refs,
            ),
        ),
        confidence_label="medium",
        limitations=(),
        task_assessment=ASSESSMENT,
    )


def test_t_cx187_nominal_harmonic_requires_all_five_citations_together() -> None:
    evidence, rules = _nominal_pack()
    known_e = frozenset(item.evidence_id for item in evidence)
    known_r = frozenset(item.evaluation_id for item in rules)
    validate_finish_decision(
        _finish(
            evidence_refs=("ev_series", "ev_thd"),
            rule_refs=("ruleval_analysis", "ruleval_f0", "ruleval_thd_fail"),
        ),
        known_evidence_ids=known_e,
        known_rule_evaluation_ids=known_r,
        task_assessment=ASSESSMENT,
        evidence=evidence,
        rule_evaluations=rules,
        stimulus_context=_nominal_context(),
        causal_policy_version="v9_8_claim_reference_recovery",
    )
    with pytest.raises(DiagnosisValidationError, match="together"):
        validate_finish_decision(
            _finish(
                evidence_refs=("ev_series",),
                rule_refs=("ruleval_analysis", "ruleval_f0"),
            ),
            known_evidence_ids=known_e,
            known_rule_evaluation_ids=known_r,
            task_assessment=ASSESSMENT,
            evidence=evidence,
            rule_evaluations=rules,
            stimulus_context=_nominal_context(),
            causal_policy_version="v9_8_claim_reference_recovery",
        )


def test_t_cx188_rejection_lists_all_deficits_with_same_run_ids() -> None:
    evidence, rules = _nominal_pack()
    known_e = frozenset(item.evidence_id for item in evidence)
    known_r = frozenset(item.evaluation_id for item in rules)
    with pytest.raises(DiagnosisValidationError) as caught:
        validate_finish_decision(
            _finish(evidence_refs=("ev_ctx_valid",), rule_refs=()),
            known_evidence_ids=known_e,
            known_rule_evaluation_ids=known_r,
            task_assessment=ASSESSMENT,
            evidence=evidence,
            rule_evaluations=rules,
            stimulus_context=_nominal_context(),
            causal_policy_version="v9_8_claim_reference_recovery",
        )
    message = str(caught.value)
    assert "ev_series" in message
    assert "ruleval_thd_fail" in message
    assert "ev_thd" in message
    assert "ruleval_analysis" in message
    assert "ruleval_f0" in message
    assert "together" in message.lower()


def test_t_cx188_empty_claim_refs_still_report_all_five_deficits() -> None:
    evidence, rules = _nominal_pack()
    with pytest.raises(DiagnosisValidationError) as caught:
        validate_finish_decision(
            _finish(evidence_refs=(), rule_refs=()),
            known_evidence_ids=frozenset(item.evidence_id for item in evidence),
            known_rule_evaluation_ids=frozenset(
                item.evaluation_id for item in rules
            ),
            task_assessment=ASSESSMENT,
            evidence=evidence,
            rule_evaluations=rules,
            stimulus_context=_nominal_context(),
            causal_policy_version="v9_8_claim_reference_recovery",
        )
    message = str(caught.value)
    for live_id in (
        "ruleval_analysis",
        "ruleval_f0",
        "ev_series",
        "ruleval_thd_fail",
        "ev_thd",
    ):
        assert live_id in message
    assert "together" in message.lower()


def test_t_cx188_missing_run_inventory_cannot_bypass_evidence_requirement() -> None:
    with pytest.raises(DiagnosisValidationError, match="requires evidence"):
        validate_finish_decision(
            _finish(evidence_refs=(), rule_refs=()),
            known_evidence_ids=frozenset(),
            known_rule_evaluation_ids=frozenset(),
            task_assessment=ASSESSMENT,
            evidence=None,
            rule_evaluations=None,
            stimulus_context=_nominal_context(),
            causal_policy_version="v9_8_claim_reference_recovery",
        )


def test_t_cx190_v98_inherits_mapping_and_rejects_manual_rules() -> None:
    assert (
        required_rule_profile(
            causal_policy_version="v9_8_claim_reference_recovery",
            stimulus_context=_nominal_context(),
            tool_name="analyze_contextual_distortion",
        )
        == "profile_s1_contextual_comparison"
    )


@pytest.mark.asyncio
async def test_t_cx190_v98_runtime_rejects_manual_evaluate_rules() -> None:
    repository = InMemorySignalRepository()
    signal_id = store_synthetic_case(
        repository,
        generate_sine(
            frequency_hz=200.0,
            sample_rate_hz=48_000,
            duration_s=1.0,
            amplitude=0.5,
        ),
    )
    steps = (
        ScriptedStep(
            expected_observation_count=0,
            decision=CallToolDecision(
                task_assessment=ASSESSMENT,
                call=DetectClippingCall(args=ClippingInput()),
                purpose="obtain clipping Evidence",
            ),
        ),
        ScriptedStep(
            expected_observation_count=1,
            decision=EvaluateRulesDecision(
                profile_id="profile_s1_distortion",
                evidence_refs=(),
                purpose="attempt manual rule evaluation",
            ),
        ),
        ScriptedStep(
            expected_observation_count=1,
            decision=FinishDecision(
                outcome="inconclusive",
                claims=(),
                confidence_label="low",
                limitations=("stop after rule-policy test",),
                task_assessment=ASSESSMENT,
            ),
        ),
    )
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=ScriptedPlanner(steps),
        rule_engine=RuleEngine(),
        rule_profile_loader=YamlRuleProfileLoader(
            {
                "profile_s1_distortion": PROFILE_S1,
                "profile_s1_contextual_comparison": PROFILE_CX,
            }
        ),
        knowledge_index=KnowledgeIndex(CORPUS),
        causal_policy_version="v9_8_claim_reference_recovery",
        limits=AgentLimits(max_planner_retries=2),
    )
    result = await runtime.run(
        signal_id=signal_id,
        user_request="Why distorted?",
        stimulus_context=_nominal_context(signal_id),
    )
    assert any("automatic" in message for message in result.errors)
    assert any("Tool observation" in message for message in result.errors)
