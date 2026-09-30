"""Planner-ablation scoring helpers and execution-input guards."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from signal_diag.evaluation.models import RateMetric
from signal_diag.evaluation.planner_ablation.labels import (
    assert_guidance_not_planner_attributed,
    guidance_attribution_label,
)
from signal_diag.evaluation.planner_ablation.models import StudyContextGuidanceView

_OFFLINE_CONTEXT_LABELS = frozenset(
    {"context_obtainable", "context_valid", "context_sufficient"}
)


def _rate(numerator: int, denominator: int) -> RateMetric:
    if denominator == 0:
        return RateMetric(numerator=0, denominator=0, value=0.0)
    return RateMetric(
        numerator=numerator,
        denominator=denominator,
        value=numerator / denominator,
    )


def reject_offline_context_labels_on_execution_inputs(
    payload: Mapping[str, object],
) -> None:
    """T-CX284: offline oracle labels must not appear on execution-arm inputs."""
    for key in payload:
        if key in _OFFLINE_CONTEXT_LABELS:
            raise ValueError(f"offline context label {key} is forbidden on execution inputs")


def score_guidance_fields(
    guidance: StudyContextGuidanceView | None,
) -> dict[str, object]:
    label = guidance_attribution_label()
    assert_guidance_not_planner_attributed(label)
    return {
        "context_guidance_present": guidance is not None,
        "guidance_attribution": label,
        "reason_codes": tuple(guidance.reason_codes) if guidance else (),
        "required_inputs": dict(guidance.required_inputs) if guidance else {},
    }


def completion_denominator(
    slots: Sequence[Mapping[str, object]],
) -> RateMetric:
    """T-CX283: diagnosis-less terminals remain in completion denominators."""
    denominator = len(slots)
    numerator = sum(
        1
        for slot in slots
        if slot.get("terminal_reached") is True
        and slot.get("infrastructure_failure") is not True
    )
    return _rate(numerator, denominator)


def claim_population_denominator(
    slots: Sequence[Mapping[str, object]],
) -> RateMetric:
    population = [slot for slot in slots if slot.get("completed_diagnosis") is True]
    return _rate(len(population), len(population))


def upgrade_success_denominators(
    *,
    pre_fixed_population: int,
    conditional_successes: int,
    conditional_population: int,
) -> tuple[RateMetric, RateMetric]:
    """T-CX285: report full pre-fixed and conditional-success denominators."""
    full = _rate(conditional_successes, pre_fixed_population)
    conditional = _rate(conditional_successes, conditional_population)
    return full, conditional
