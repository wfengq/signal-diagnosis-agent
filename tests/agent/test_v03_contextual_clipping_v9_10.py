"""T-CX236–T-CX237: v9.10 coherent clipping evidence families."""

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
CONTEXT = StimulusContext(
    mode="single_signal",
    test_signal_id="sig_test",
    assertion_source="evaluation_manifest",
)


def _evidence(evidence_id: str, metric: str, value: object) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source_tool="analyze_contextual_distortion",
        call_id="call_contextual_000001",
        metric=metric,
        value=value,  # type: ignore[arg-type]
        channel="mixdown",
    )


def _rule(evaluation_id: str, rule_id: str, judgment: str) -> RuleEvaluation:
    return RuleEvaluation(
        evaluation_id=evaluation_id,
        rule_id=rule_id,
        judgment=judgment,  # type: ignore[arg-type]
        observed_value=None,
        comparator="eq",
        threshold=True,
        profile_id="profile_s1_contextual_comparison_v9_10",
        profile_version="1.0.0",
        evidence_refs=("ev_metric",),
    )


def _validate(
    claim: DiagnosisClaim,
    *,
    evidence: tuple[Evidence, ...],
    rules: tuple[RuleEvaluation, ...],
    outcome: str = "supported_fault",
    policy: str = "v9_10_contextual_clipping_recovery",
    context: StimulusContext = CONTEXT,
) -> None:
    decision = FinishDecision(
        outcome=outcome,  # type: ignore[arg-type]
        claims=(claim,),
        confidence_label="medium",
        limitations=("bounded test",) if outcome == "inconclusive" else (),
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


def _clipping_claim(evidence_refs: tuple[str, ...], rule_refs: tuple[str, ...]) -> DiagnosisClaim:
    return DiagnosisClaim(
        claim_id="claim_clipping",
        fault_type="clipping",
        statement="Clipping is supported.",
        evidence_refs=evidence_refs,
        rule_refs=rule_refs,
    )


def test_t_cx236_v910_accepts_only_coherent_clipping_family() -> None:
    evidence = (_evidence("ev_mechanism", "test_clipping_mechanism", True),)
    contextual_fail = _rule(
        "ruleval_test_ratio", "rule_test_clipping_ratio_acceptable", "fail"
    )
    contextual_flat_fail = _rule(
        "ruleval_test_flat", "rule_test_flat_top_absent", "fail"
    )
    legacy_fail = _rule("ruleval_ratio", "rule_clipping_ratio_acceptable", "fail")

    _validate(
        _clipping_claim(("ev_mechanism",), ("ruleval_test_ratio",)),
        evidence=evidence,
        rules=(contextual_fail,),
    )
    _validate(
        _clipping_claim(("ev_mechanism",), ("ruleval_test_flat",)),
        evidence=evidence,
        rules=(contextual_flat_fail,),
    )
    for rules in ((legacy_fail,), (contextual_fail, legacy_fail)):
        with pytest.raises(DiagnosisValidationError, match="coherent"):
            _validate(
                _clipping_claim(("ev_mechanism",), tuple(item.evaluation_id for item in rules)),
                evidence=evidence,
                rules=rules,
            )


def test_t_cx237_v910_no_fault_requires_contextual_clean_passes() -> None:
    evidence = (_evidence("ev_mechanism", "test_clipping_mechanism", False),)
    ratio = _rule("ruleval_test_ratio", "rule_test_clipping_ratio_acceptable", "pass")
    flat = _rule("ruleval_test_flat", "rule_test_flat_top_absent", "pass")
    harmonic_valid = _rule(
        "ruleval_harmonic_valid", "rule_harmonic_analysis_valid", "pass"
    )
    thd = _rule("ruleval_thd", "rule_thd_acceptable", "pass")
    claim = DiagnosisClaim(
        claim_id="claim_no_fault",
        fault_type="no_supported_fault",
        statement="No supported fault.",
        evidence_refs=("ev_mechanism",),
        rule_refs=(
            "ruleval_test_ratio",
            "ruleval_test_flat",
            "ruleval_harmonic_valid",
            "ruleval_thd",
        ),
    )
    _validate(
        claim,
        evidence=evidence,
        rules=(ratio, flat, harmonic_valid, thd),
        outcome="no_supported_fault",
    )
    incomplete = claim.model_copy(update={"rule_refs": ("ruleval_test_flat",)})
    with pytest.raises(DiagnosisValidationError, match="test clipping ratio PASS"):
        _validate(
            incomplete,
            evidence=evidence,
            rules=(flat, harmonic_valid, thd),
            outcome="no_supported_fault",
        )


@pytest.mark.parametrize(
    ("context", "mode_rules", "missing_message"),
    (
        (
            StimulusContext(
                mode="paired_reference",
                test_signal_id="sig_test",
                reference_signal_id="sig_reference",
                assertion_source="evaluation_manifest",
            ),
            (
                ("rule_contextual_analysis_valid", "contextual analysis PASS"),
                ("rule_contextual_f0_compatible", "contextual F0 compatibility PASS"),
                ("rule_reference_clipping_ratio_acceptable", "reference clipping ratio PASS"),
                ("rule_reference_flat_top_absent", "reference flat-top PASS"),
                ("rule_even_harmonic_growth_acceptable", "harmonic growth PASS"),
            ),
            "harmonic growth PASS",
        ),
        (
            StimulusContext(
                mode="nominal_single_tone",
                test_signal_id="sig_test",
                nominal_fundamental_hz=440.0,
                stimulus_kind="single_tone",
                assertion_source="evaluation_manifest",
            ),
            (
                ("rule_contextual_analysis_valid", "contextual analysis PASS"),
                ("rule_contextual_f0_compatible", "contextual F0 compatibility PASS"),
                ("rule_nominal_thd_acceptable", "nominal THD PASS"),
            ),
            "nominal THD PASS",
        ),
    ),
)
def test_t_cx237_v910_no_fault_retains_mode_specific_gates(
    context: StimulusContext,
    mode_rules: tuple[tuple[str, str], ...],
    missing_message: str,
) -> None:
    evidence = (_evidence("ev_mechanism", "test_clipping_mechanism", False),)
    clean_rules = (
        _rule("ruleval_test_ratio", "rule_test_clipping_ratio_acceptable", "pass"),
        _rule("ruleval_test_flat", "rule_test_flat_top_absent", "pass"),
    )
    extra_rules = tuple(
        _rule(f"ruleval_mode_{index}", rule_id, "pass")
        for index, (rule_id, _gate) in enumerate(mode_rules)
    )
    claim = DiagnosisClaim(
        claim_id="claim_no_fault",
        fault_type="no_supported_fault",
        statement="No supported fault.",
        evidence_refs=("ev_mechanism",),
        rule_refs=tuple(
            item.evaluation_id for item in (*clean_rules, *extra_rules)
        ),
    )
    _validate(
        claim,
        evidence=evidence,
        rules=(*clean_rules, *extra_rules),
        outcome="no_supported_fault",
        context=context,
    )
    with pytest.raises(DiagnosisValidationError, match=missing_message):
        _validate(
            claim.model_copy(
                update={"rule_refs": claim.rule_refs[:-1]}
            ),
            evidence=evidence,
            rules=(*clean_rules, *extra_rules[:-1]),
            outcome="no_supported_fault",
            context=context,
        )


def test_t_cx237_v99_keeps_legacy_family_and_rejects_contextual_family() -> None:
    evidence = (_evidence("ev_mechanism", "clipping_mechanism", True),)
    legacy = _rule("ruleval_ratio", "rule_clipping_ratio_acceptable", "fail")
    claim = _clipping_claim(("ev_mechanism",), ("ruleval_ratio",))
    _validate(claim, evidence=evidence, rules=(legacy,), policy="v9_9_paired_reference_recovery")
    contextual = _rule("ruleval_test_ratio", "rule_test_clipping_ratio_acceptable", "fail")
    with pytest.raises(DiagnosisValidationError):
        _validate(
            _clipping_claim(("ev_mechanism",), ("ruleval_test_ratio",)),
            evidence=evidence,
            rules=(contextual,),
            policy="v9_9_paired_reference_recovery",
        )
