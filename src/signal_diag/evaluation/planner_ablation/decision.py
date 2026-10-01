"""Parameterized study conclusion language (§19.5 / T-CX286)."""

from __future__ import annotations

from enum import Enum
from typing import Literal

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
    advantage_endpoint: Literal["quality", "usefulness"] = "quality"


class StudyComparisonMetrics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    product_primary_quality: float = Field(ge=0.0, le=1.0)
    fixed_primary_quality: float = Field(ge=0.0, le=1.0)
    product_usefulness: float = Field(ge=0.0, le=1.0)
    fixed_usefulness: float = Field(ge=0.0, le=1.0)
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
    if not metrics.evaluable_population:
        return StudyConclusion.INSUFFICIENT_EVIDENCE
    if not metrics.protocol_complete:
        return StudyConclusion.INSUFFICIENT_EVIDENCE
    if not metrics.product_safety_ok or not metrics.fixed_safety_ok:
        return StudyConclusion.INSUFFICIENT_EVIDENCE
    if metrics.constrained_metric_regression:
        return StudyConclusion.INSUFFICIENT_EVIDENCE

    gap = protocol.non_inferiority_max_gap
    quality_non_inferior = (
        metrics.fixed_primary_quality >= metrics.product_primary_quality - gap
    )
    usefulness_non_inferior = (
        metrics.fixed_usefulness >= metrics.product_usefulness - gap
    )
    completion_non_inferior = (
        metrics.fixed_completion >= metrics.product_completion - gap
    )
    materially_faster = (
        metrics.fixed_latency_improvement_ratio >= protocol.material_improvement_ratio
    )

    if (
        quality_non_inferior
        and usefulness_non_inferior
        and completion_non_inferior
        and metrics.fixed_safety_ok
        and materially_faster
        and not metrics.constrained_metric_regression
    ):
        return StudyConclusion.FIXED_PIPELINE_DOMINANCE

    if protocol.advantage_endpoint == "usefulness":
        usefulness_gap = metrics.product_usefulness - metrics.fixed_usefulness
        if (
            usefulness_gap > gap
            and metrics.product_safety_ok
            and metrics.product_completion >= metrics.fixed_completion - gap
            and metrics.product_primary_quality >= metrics.fixed_primary_quality - gap
        ):
            return StudyConclusion.PLANNER_ADVANTAGE
    else:
        quality_gap = metrics.product_primary_quality - metrics.fixed_primary_quality
        if (
            quality_gap > gap
            and metrics.product_safety_ok
            and metrics.product_completion >= metrics.fixed_completion - gap
            and metrics.product_usefulness >= metrics.fixed_usefulness - gap
        ):
            return StudyConclusion.PLANNER_ADVANTAGE

    return StudyConclusion.INSUFFICIENT_EVIDENCE
