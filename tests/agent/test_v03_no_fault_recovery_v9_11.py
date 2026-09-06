"""T-CX250–T-CX253: v9.11 mode-aware no-fault recovery."""

from __future__ import annotations

import pytest

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
V911 = "v9_11_mode_aware_no_fault_recovery"


def _evidence(evidence_id: str, metric: str, value: object) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source_tool="detect_clipping",
        call_id="call_no_fault_000001",
        metric=metric,
        value=value,  # type: ignore[arg-type]
        channel="mixdown",
    )


def _rule(evaluation_id: str, rule_id: str) -> RuleEvaluation:
    return RuleEvaluation(
        evaluation_id=evaluation_id,
        rule_id=rule_id,
        judgment="pass",
        observed_value=None,
        comparator="eq",
        threshold=True,
        profile_id="profile_s1_contextual_comparison_v9_10",
        profile_version="1.0.0",
        evidence_refs=(),
    )


def _claim(
    evidence_refs: tuple[str, ...],
    rule_refs: tuple[str, ...],
) -> DiagnosisClaim:
    return DiagnosisClaim(
        claim_id="claim_no_fault",
        fault_type="no_supported_fault",
        statement="No supported S1 fault is established.",
        evidence_refs=evidence_refs,
        rule_refs=rule_refs,
    )


def _validate(
    claim: DiagnosisClaim,
    *,
    context: StimulusContext,
    evidence: tuple[Evidence, ...],
    rules: tuple[RuleEvaluation, ...],
    policy: str = V911,
) -> None:
    decision = FinishDecision(
        outcome="no_supported_fault",
        claims=(claim,),
        confidence_label="medium",
        task_assessment=ASSESSMENT,
    )
    validate_finish_decision(
        decision,
        known_evidence_ids=frozenset(item.evidence_id for item in evidence),
        known_rule_evaluation_ids=frozenset(item.evaluation_id for item in rules),
        task_assessment=ASSESSMENT,
        evidence=evidence,
        rule_evaluations=rules,
        stimulus_context=context,
        causal_policy_version=policy,  # type: ignore[arg-type]
    )


def _single_context() -> StimulusContext:
    return StimulusContext(
        mode="single_signal",
        test_signal_id="sig_single",
        assertion_source="evaluation_manifest",
    )


def _paired_context() -> StimulusContext:
    return StimulusContext(
        mode="paired_reference",
        test_signal_id="sig_test",
        reference_signal_id="sig_reference",
        assertion_source="evaluation_manifest",
    )


def _single_rules() -> tuple[RuleEvaluation, ...]:
    return (
        _rule("ruleval_clip_ratio", "rule_clipping_ratio_acceptable"),
        _rule("ruleval_flat", "rule_flat_top_absent"),
        _rule("ruleval_harmonic_valid", "rule_harmonic_analysis_valid"),
        _rule("ruleval_thd", "rule_thd_acceptable"),
    )


def _paired_rules() -> tuple[RuleEvaluation, ...]:
    return (
        _rule("ruleval_test_ratio", "rule_test_clipping_ratio_acceptable"),
        _rule("ruleval_test_flat", "rule_test_flat_top_absent"),
        _rule("ruleval_context_valid", "rule_contextual_analysis_valid"),
        _rule("ruleval_f0", "rule_contextual_f0_compatible"),
        _rule("ruleval_ref_ratio", "rule_reference_clipping_ratio_acceptable"),
        _rule("ruleval_ref_flat", "rule_reference_flat_top_absent"),
        _rule("ruleval_growth", "rule_even_harmonic_growth_acceptable"),
    )


def test_t_cx251_v911_single_signal_requires_legacy_clean_family() -> None:
    legacy = (_evidence("ev_legacy_false", "clipping_mechanism", False),)
    legacy_rules = _single_rules()
    _validate(
        _claim(
            ("ev_legacy_false",),
            tuple(item.evaluation_id for item in legacy_rules),
        ),
        context=_single_context(),
        evidence=legacy,
        rules=legacy_rules,
    )

    contextual = (
        _evidence("ev_test_false", "test_clipping_mechanism", False),
    )
    contextual_rules = (
        _rule("ruleval_test_ratio", "rule_test_clipping_ratio_acceptable"),
        _rule("ruleval_test_flat", "rule_test_flat_top_absent"),
        *_single_rules()[2:],
    )
    with pytest.raises(DiagnosisValidationError, match="clipping_mechanism=false"):
        _validate(
            _claim(
                ("ev_test_false",),
                tuple(item.evaluation_id for item in contextual_rules),
            ),
            context=_single_context(),
            evidence=contextual,
            rules=contextual_rules,
        )


def test_t_cx252_v911_paired_requires_contextual_clean_family() -> None:
    evidence = (_evidence("ev_test_false", "test_clipping_mechanism", False),)
    rules = _paired_rules()
    _validate(
        _claim(
            ("ev_test_false",),
            tuple(item.evaluation_id for item in rules),
        ),
        context=_paired_context(),
        evidence=evidence,
        rules=rules,
    )

    with pytest.raises(DiagnosisValidationError, match="harmonic growth PASS"):
        _validate(
            _claim(
                ("ev_test_false",),
                tuple(item.evaluation_id for item in rules[:-1]),
            ),
            context=_paired_context(),
            evidence=evidence,
            rules=rules,
        )


def test_t_cx253_v911_reports_all_available_ids_in_one_error() -> None:
    evidence = (
        _evidence("ev_unrelated", "clipping_mechanism", False),
        _evidence("ev_test_false", "test_clipping_mechanism", False),
    )
    rules = _paired_rules()
    with pytest.raises(DiagnosisValidationError) as caught:
        _validate(
            _claim(("ev_unrelated",), ()),
            context=_paired_context(),
            evidence=evidence,
            rules=rules,
        )

    message = str(caught.value)
    for expected_id in (
        "ev_test_false",
        "ruleval_test_ratio",
        "ruleval_test_flat",
        "ruleval_context_valid",
        "ruleval_f0",
        "ruleval_ref_ratio",
        "ruleval_ref_flat",
        "ruleval_growth",
    ):
        assert expected_id in message
    assert "cite ALL" in message


def test_t_cx253_v911_rejects_no_fault_outcome_with_non_no_fault_claim() -> None:
    claim = DiagnosisClaim(
        claim_id="claim_incoherent",
        fault_type="inconclusive",
        statement="The evidence is inconclusive.",
        evidence_refs=(),
        rule_refs=(),
    )
    decision = FinishDecision(
        outcome="no_supported_fault",
        claims=(claim,),
        confidence_label="low",
        task_assessment=ASSESSMENT,
    )

    with pytest.raises(
        DiagnosisValidationError,
        match="no_supported_fault outcome requires only no_supported_fault claims",
    ):
        validate_finish_decision(
            decision,
            known_evidence_ids=frozenset(),
            task_assessment=ASSESSMENT,
            evidence=(),
            rule_evaluations=(),
            stimulus_context=_single_context(),
            causal_policy_version=V911,
        )


def test_t_cx253_v911_empty_refs_report_all_available_ids() -> None:
    evidence = (_evidence("ev_test_false", "test_clipping_mechanism", False),)
    rules = _paired_rules()

    with pytest.raises(DiagnosisValidationError) as caught:
        _validate(
            _claim((), ()),
            context=_paired_context(),
            evidence=evidence,
            rules=rules,
        )

    message = str(caught.value)
    for expected_id in (
        "ev_test_false",
        "ruleval_test_ratio",
        "ruleval_test_flat",
        "ruleval_context_valid",
        "ruleval_f0",
        "ruleval_ref_ratio",
        "ruleval_ref_flat",
        "ruleval_growth",
    ):
        assert expected_id in message
    assert "cite ALL" in message


def test_t_cx250_v910_contextual_no_fault_behavior_is_preserved() -> None:
    evidence = (_evidence("ev_test_false", "test_clipping_mechanism", False),)
    rules = _paired_rules()
    _validate(
        _claim(
            ("ev_test_false",),
            tuple(item.evaluation_id for item in rules),
        ),
        context=_paired_context(),
        evidence=evidence,
        rules=rules,
        policy="v9_10_contextual_clipping_recovery",
    )
