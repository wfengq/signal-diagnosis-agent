"""T-CX280, T-CX286: decision language and identity guards."""

from __future__ import annotations

import inspect

import pytest

from signal_diag.evaluation.planner_ablation.decision import (
    StudyComparisonMetrics,
    StudyConclusion,
    StudyDecisionProtocol,
    decide_study_conclusion,
)
from signal_diag.evaluation.planner_ablation.identity import (
    PLANNER_ABLATION_STUDY_ID,
    validate_scoring_identity_derivation,
    validate_study_identity,
)


def _protocol(**overrides: object) -> StudyDecisionProtocol:
    base = {
        "study_id": PLANNER_ABLATION_STUDY_ID,
        "scoring_identity": "signal_diag.planner_ablation_scoring",
        "non_inferiority_max_gap": 0.05,
        "material_improvement_ratio": 0.20,
        "n_unit": "scorable_slots",
    }
    base.update(overrides)
    return StudyDecisionProtocol(**base)  # type: ignore[arg-type]


def _metrics(**overrides: object) -> StudyComparisonMetrics:
    base = {
        "product_primary_quality": 0.9,
        "fixed_primary_quality": 0.88,
        "product_usefulness": 0.9,
        "fixed_usefulness": 0.88,
        "product_completion": 1.0,
        "fixed_completion": 1.0,
        "product_safety_ok": True,
        "fixed_safety_ok": True,
        "fixed_latency_improvement_ratio": 0.25,
        "constrained_metric_regression": False,
        "matched_comparison": True,
        "evaluable_population": True,
        "protocol_complete": True,
        "unmatched_comparison": False,
    }
    base.update(overrides)
    return StudyComparisonMetrics(**base)  # type: ignore[arg-type]


def test_t_cx286_fixed_dominance_at_equal_completion() -> None:
    conclusion = decide_study_conclusion(_protocol(), _metrics())
    assert conclusion == StudyConclusion.FIXED_PIPELINE_DOMINANCE


def test_t_cx286_fixed_dominance_with_non_hundred_percent_completion() -> None:
    conclusion = decide_study_conclusion(
        _protocol(),
        _metrics(
            product_completion=0.92,
            fixed_completion=0.90,
            product_primary_quality=0.88,
            fixed_primary_quality=0.87,
            product_usefulness=0.86,
            fixed_usefulness=0.85,
        ),
    )
    assert conclusion == StudyConclusion.FIXED_PIPELINE_DOMINANCE


def test_t_cx286_planner_advantage_when_quality_gap_exceeds_band() -> None:
    conclusion = decide_study_conclusion(
        _protocol(),
        _metrics(product_primary_quality=0.95, fixed_primary_quality=0.80),
    )
    assert conclusion == StudyConclusion.PLANNER_ADVANTAGE


def test_t_cx286_insufficient_on_safety_failure() -> None:
    conclusion = decide_study_conclusion(
        _protocol(),
        _metrics(product_safety_ok=False),
    )
    assert conclusion == StudyConclusion.INSUFFICIENT_EVIDENCE


def test_t_cx286_insufficient_on_regression_and_unmatched() -> None:
    assert (
        decide_study_conclusion(_protocol(), _metrics(constrained_metric_regression=True))
        == StudyConclusion.INSUFFICIENT_EVIDENCE
    )
    assert (
        decide_study_conclusion(_protocol(), _metrics(unmatched_comparison=True))
        == StudyConclusion.INSUFFICIENT_EVIDENCE
    )
    assert (
        decide_study_conclusion(_protocol(), _metrics(evaluable_population=False))
        == StudyConclusion.INSUFFICIENT_EVIDENCE
    )
    assert (
        decide_study_conclusion(_protocol(), _metrics(protocol_complete=False))
        == StudyConclusion.INSUFFICIENT_EVIDENCE
    )
    assert (
        decide_study_conclusion(_protocol(), _metrics(matched_comparison=False))
        == StudyConclusion.INSUFFICIENT_EVIDENCE
    )


def test_t_cx286_dominance_blocked_without_material_improvement() -> None:
    conclusion = decide_study_conclusion(
        _protocol(),
        _metrics(fixed_latency_improvement_ratio=0.05),
    )
    assert conclusion == StudyConclusion.INSUFFICIENT_EVIDENCE


def test_t_cx286_dominance_blocked_when_completion_regresses() -> None:
    conclusion = decide_study_conclusion(
        _protocol(),
        _metrics(product_completion=0.90, fixed_completion=0.70),
    )
    assert conclusion == StudyConclusion.INSUFFICIENT_EVIDENCE


def test_t_cx280_rejects_foreign_study_and_derivation() -> None:
    with pytest.raises(ValueError, match="foreign study"):
        validate_study_identity("study_other")
    with pytest.raises(ValueError, match="derivation"):
        validate_scoring_identity_derivation(
            study_id=PLANNER_ABLATION_STUDY_ID,
            scoring_identity="signal_diag.planner_ablation_scoring",
            derivation="historical_17_of_6",
        )


def test_t_cx286_planner_advantage_on_usefulness_endpoint_counterexample() -> None:
    protocol = _protocol(advantage_endpoint="usefulness")
    metrics = _metrics(
        product_primary_quality=0.9,
        fixed_primary_quality=0.9,
        product_usefulness=0.9,
        fixed_usefulness=0.6,
        product_completion=1.0,
        fixed_completion=1.0,
        fixed_latency_improvement_ratio=0.05,
    )
    assert decide_study_conclusion(protocol, metrics) == StudyConclusion.PLANNER_ADVANTAGE

    quality_protocol = _protocol(advantage_endpoint="quality")
    assert (
        decide_study_conclusion(quality_protocol, metrics)
        == StudyConclusion.INSUFFICIENT_EVIDENCE
    )


def test_decision_module_has_no_hardcoded_live_n_defaults() -> None:
    import signal_diag.evaluation.planner_ablation.decision as decision_module

    module_source = inspect.getsource(decision_module)
    assert "1/17" not in module_source
    assert "1/6" not in module_source
    assert not hasattr(decision_module, "DEFAULT_NON_INFERIORITY_N")
    assert not hasattr(decision_module, "DEFAULT_MATERIAL_IMPROVEMENT_RATIO")
