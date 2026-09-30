"""Parameterized study conclusion language (§19.5 / T-CX286)."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class StudyConclusion(str, Enum):
    PLANNER_ADVANTAGE = "planner_advantage"
    FIXED_PIPELINE_DOMINANCE = "fixed_pipeline_dominance"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class StudyDecisionProtocol(BaseModel):
    """Sealed protocol object; library code must not hard-code live 1/N gates."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    study_id: str = Field(min_length=1)
    scoring_identity: str = Field(min_length=1)
    non_inferiority_max_gap: float = Field(gt=0.0, lt=1.0)
    material_improvement_ratio: float = Field(gt=0.0, lt=1.0)
    n_unit: str = Field(min_length=1)
    require_matched_comparison: bool = True
    require_evaluable_population: bool = True
    require_complete_protocol: bool = True


class StudyComparisonMetrics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    product_primary_quality: float = Field(ge=0.0, le=1.0)
    fixed_primary_quality: float = Field(ge=0.0, le=1.0)
    product_completion: float = Field(ge=0.0, le=1.0)
    fixed_completion: float = Field(ge=0.0, le=1.0)
    product_safety_ok: bool
    fixed_safety_ok: bool
    fixed_latency_improvement_ratio: float = Field(ge=0.0)
    constrained_metric_regression: bool = False
    matched_comparison: bool = True
    evaluable_population: bool = True
    protocol_complete: bool = True
    unmatched_comparison: bool = False


def decide_study_conclusion(
    protocol: StudyDecisionProtocol,
    metrics: StudyComparisonMetrics,
) -> StudyConclusion:
    if metrics.unmatched_comparison or not metrics.matched_comparison:
        return StudyConclusion.INSUFFICIENT_EVIDENCE
    if protocol.require_evaluable_population and not metrics.evaluable_population:
        return StudyConclusion.INSUFFICIENT_EVIDENCE
    if protocol.require_complete_protocol and not metrics.protocol_complete:
        return StudyConclusion.INSUFFICIENT_EVIDENCE
    if not metrics.product_safety_ok or not metrics.fixed_safety_ok:
        return StudyConclusion.INSUFFICIENT_EVIDENCE
    if metrics.constrained_metric_regression:
        return StudyConclusion.INSUFFICIENT_EVIDENCE

    quality_gap = metrics.product_primary_quality - metrics.fixed_primary_quality
    non_inferior = quality_gap <= protocol.non_inferiority_max_gap
    materially_faster = (
        metrics.fixed_latency_improvement_ratio >= protocol.material_improvement_ratio
    )
    equal_completion = (
        metrics.product_completion == 1.0 and metrics.fixed_completion == 1.0
    )

    if (
        equal_completion
        and non_inferior
        and metrics.fixed_safety_ok
        and materially_faster
        and not metrics.constrained_metric_regression
    ):
        return StudyConclusion.FIXED_PIPELINE_DOMINANCE

    if (
        metrics.product_primary_quality > metrics.fixed_primary_quality + protocol.non_inferiority_max_gap
        and metrics.product_safety_ok
        and metrics.product_completion >= metrics.fixed_completion
    ):
        return StudyConclusion.PLANNER_ADVANTAGE

    return StudyConclusion.INSUFFICIENT_EVIDENCE
