"""Study scoring chain: grounding, safety, and dual-arm conclusion."""

from __future__ import annotations

import pytest

from signal_diag.evaluation.planner_ablation.decision import (
    StudyConclusion,
    StudyDecisionProtocol,
)
from signal_diag.evaluation.planner_ablation.identity import (
    PLANNER_ABLATION_SCORING_IDENTITY,
    PLANNER_ABLATION_STUDY_ID,
)
from signal_diag.evaluation.planner_ablation.scoring import (
    ScoringPopulationError,
    claim_population_denominator,
)
from signal_diag.evaluation.planner_ablation.study_score import (
    StudyOracleLabel,
    build_study_comparison_metrics,
    score_planner_ablation_study,
    unsupported_positive_claim_rate,
)
from signal_diag.tools.evidence import Evidence


def _protocol(**overrides: object) -> StudyDecisionProtocol:
    base = {
        "study_id": PLANNER_ABLATION_STUDY_ID,
        "scoring_identity": PLANNER_ABLATION_SCORING_IDENTITY,
        "non_inferiority_max_gap": 0.05,
        "material_improvement_ratio": 0.20,
        "n_unit": "scorable_slots",
        "advantage_endpoint": "quality",
    }
    base.update(overrides)
    return StudyDecisionProtocol(**base)  # type: ignore[arg-type]


def _product_slot(**fields: object) -> dict[str, object]:
    base: dict[str, object] = {
        "arm": "product_agent",
        "execution_identity": "product_campaign",
        "planner_class": "RealLLMPlanner",
        "study_id": PLANNER_ABLATION_STUDY_ID,
        "scoring_identity": PLANNER_ABLATION_SCORING_IDENTITY,
        "scheduled": True,
    }
    base.update(fields)
    return base


def _fixed_slot(**fields: object) -> dict[str, object]:
    base: dict[str, object] = {
        "arm": "fixed_pipeline",
        "execution_identity": "product_campaign",
        "planner_class": "PlannerAblationFixedPipelineBaseline",
        "study_id": PLANNER_ABLATION_STUDY_ID,
        "scoring_identity": PLANNER_ABLATION_SCORING_IDENTITY,
        "scheduled": True,
    }
    base.update(fields)
    return base


def test_multi_claim_grounding_counts_each_claim() -> None:
    evidence = (
        Evidence(
            evidence_id="ev_1",
            call_id="call_1",
            source_tool="detect_clipping",
            metric="clipping_ratio",
            value=0.02,
            validity="valid",
            channel="mixdown",
        ),
    )
    slots = (
        _product_slot(
            completed_diagnosis=True,
            evidence=evidence,
            claims=(
                {"claim_id": "c1", "fault_type": "clipping", "evidence_refs": ("ev_1",), "rule_refs": ()},
                {
                    "claim_id": "c2",
                    "fault_type": "harmonic_distortion",
                    "evidence_refs": ("ev_missing",),
                    "rule_refs": (),
                },
            ),
        ),
    )
    population = claim_population_denominator(slots)
    assert population.denominator == 2
    assert population.numerator == 1
    rate, safety_ok = unsupported_positive_claim_rate(slots)
    assert rate == 0.5
    assert safety_ok is False


def test_zero_claim_population_blocks_evaluable_population() -> None:
    product = (
        _product_slot(
            completed_diagnosis=True,
            claims=(),
            diagnosis_outcome="no_supported_fault",
        ),
    )
    fixed = (
        _fixed_slot(
            completed_diagnosis=True,
            claims=(),
            diagnosis_outcome="no_supported_fault",
        ),
    )
    with pytest.raises(ScoringPopulationError):
        claim_population_denominator(product)
    metrics = build_study_comparison_metrics(
        product_slots=product,
        fixed_slots=fixed,
        oracle=(
            StudyOracleLabel(
                case_id="c1",
                expected_outcome="no_supported_fault",
                expected_causal_faults=(),
            ),
        ),
    )
    assert metrics.evaluable_population is False
    assert metrics.product_safety_ok is False


def test_behavioral_failure_stays_in_completion_denominator() -> None:
    slots = (
        _product_slot(completed_diagnosis=False, terminal_reached=True),
        _product_slot(completed_diagnosis=True, diagnosis_outcome="no_supported_fault", claims=()),
    )
    from signal_diag.evaluation.planner_ablation.scoring import (
        diagnosis_completion_rate,
    )

    completion = diagnosis_completion_rate(slots)
    assert completion.denominator == 2
    assert completion.numerator == 1


def test_end_to_end_synthetic_dual_arm_conclusion() -> None:
    oracle = (
        StudyOracleLabel(
            case_id="clip_case",
            expected_outcome="supported_fault",
            expected_causal_faults=("clipping",),
        ),
    )
    evidence = (
        Evidence(
            evidence_id="ev_clip",
            call_id="call_1",
            source_tool="detect_clipping",
            metric="clipping_ratio",
            value=0.03,
            validity="valid",
            channel="mixdown",
        ),
    )
    grounded_claim = {
        "claim_id": "c_clip",
        "fault_type": "clipping",
        "evidence_refs": ("ev_clip",),
        "rule_refs": (),
    }
    product = (
        _product_slot(
            case_id="clip_case",
            completed_diagnosis=True,
            diagnosis_outcome="supported_fault",
            evidence=evidence,
            claims=(grounded_claim,),
        ),
    )
    fixed = (
        _fixed_slot(
            case_id="clip_case",
            completed_diagnosis=True,
            diagnosis_outcome="no_supported_fault",
            evidence=evidence,
            claims=(
                {
                    "claim_id": "c_nf",
                    "fault_type": "no_supported_fault",
                    "evidence_refs": ("ev_clip",),
                    "rule_refs": (),
                },
            ),
        ),
    )
    conclusion = score_planner_ablation_study(
        product_slots=product,
        fixed_slots=fixed,
        oracle=oracle,
        protocol=_protocol(),
        fixed_latency_improvement_ratio=0.0,
    )
    assert conclusion in {
        StudyConclusion.PLANNER_ADVANTAGE,
        StudyConclusion.INSUFFICIENT_EVIDENCE,
    }
