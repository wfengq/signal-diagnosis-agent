"""T-CX240: deterministic replay of the two preserved v9.9 failure shapes."""

from __future__ import annotations

from signal_diag.agent.diagnosis import validate_finish_decision
from signal_diag.agent.models import (
    DiagnosisClaim,
    DiagnosisValidationError,
    FinishDecision,
    TaskAssessment,
)
from signal_diag.rules.models import RuleEvaluation
from signal_diag.signal.context import StimulusContext
from signal_diag.tools.evidence import Evidence

ASSESSMENT = TaskAssessment(task_type="distortion_analysis", objective="S1")
CONTEXT = StimulusContext(
    mode="single_signal", test_signal_id="replay", assertion_source="evaluation_manifest"
)


def _ev(evidence_id: str, metric: str, value: object) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source_tool="analyze_contextual_distortion",
        call_id="call_replay_000001",
        metric=metric,
        value=value,  # type: ignore[arg-type]
        channel="mixdown",
    )


def _rv(evaluation_id: str, rule_id: str, judgment: str) -> RuleEvaluation:
    return RuleEvaluation(
        evaluation_id=evaluation_id,
        rule_id=rule_id,
        judgment=judgment,  # type: ignore[arg-type]
        observed_value=None,
        comparator="eq",
        threshold=True,
        profile_id="profile_s1_contextual_comparison_v9_10",
        profile_version="1.0.0",
        evidence_refs=("ev_mechanism",),
    )


def _finish(claims: tuple[DiagnosisClaim, ...]) -> FinishDecision:
    return FinishDecision(
        outcome="supported_fault",
        claims=claims,
        confidence_label="medium",
        task_assessment=ASSESSMENT,
    )


def _validate(decision: FinishDecision, evidence: tuple[Evidence, ...], rules: tuple[RuleEvaluation, ...]) -> None:
    validate_finish_decision(
        decision,
        known_evidence_ids=frozenset(item.evidence_id for item in evidence),
        known_rule_evaluation_ids=frozenset(item.evaluation_id for item in rules),
        task_assessment=ASSESSMENT,
        evidence=evidence,
        rule_evaluations=rules,
        stimulus_context=CONTEXT,
        causal_policy_version="v9_10_contextual_clipping_recovery",
    )


def test_t_cx240_7fd_replay_uses_contextual_clipping_family() -> None:
    evidence = (_ev("ev_mechanism", "test_clipping_mechanism", True),)
    rules = (_rv("ruleval_test_ratio", "rule_test_clipping_ratio_acceptable", "fail"),)
    claim = DiagnosisClaim(
        claim_id="claim_clipping",
        fault_type="clipping",
        statement="Clipping is supported by the test family.",
        evidence_refs=("ev_mechanism",),
        rule_refs=("ruleval_test_ratio",),
    )
    _validate(_finish((claim,)), evidence, rules)


def test_t_cx240_675_replay_rejects_combined_then_accepts_clipping_only() -> None:
    evidence = (_ev("ev_mechanism", "test_clipping_mechanism", True),)
    rules = (_rv("ruleval_test_ratio", "rule_test_clipping_ratio_acceptable", "fail"),)
    clipping = DiagnosisClaim(
        claim_id="claim_clipping",
        fault_type="clipping",
        statement="Clipping is supported.",
        evidence_refs=("ev_mechanism",),
        rule_refs=("ruleval_test_ratio",),
    )
    harmonic = clipping.model_copy(
        update={
            "claim_id": "claim_harmonic",
            "fault_type": "harmonic_distortion",
            "statement": "Unsupported harmonic sibling.",
        }
    )
    try:
        _validate(_finish((clipping, harmonic)), evidence, rules)
    except DiagnosisValidationError as error:
        assert "remove the unsupported harmonic_distortion sibling" in str(error)
    else:  # pragma: no cover - the first proposal must be rejected
        raise AssertionError("combined proposal unexpectedly accepted")
    _validate(_finish((clipping,)), evidence, rules)
