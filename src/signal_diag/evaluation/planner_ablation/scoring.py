"""Planner-ablation scoring helpers and execution-input guards."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from signal_diag.evaluation.models import RateMetric
from signal_diag.evaluation.planner_ablation.identity import (
    validate_scored_campaign_input,
)
from signal_diag.evaluation.planner_ablation.labels import (
    assert_guidance_not_planner_attributed,
    guidance_attribution_label,
)
from signal_diag.evaluation.planner_ablation.models import StudyContextGuidanceView

_OFFLINE_CONTEXT_LABELS = frozenset(
    {"context_obtainable", "context_valid", "context_sufficient"}
)


class ScoringPopulationError(ValueError):
    """Raised when a rate metric has no evaluable denominator."""


def _rate(numerator: int, denominator: int) -> RateMetric:
    if denominator == 0:
        raise ScoringPopulationError("metric denominator is zero; not evaluable")
    return RateMetric(
        numerator=numerator,
        denominator=denominator,
        value=numerator / denominator,
    )


def _scheduled_slots(slots: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    return [slot for slot in slots if slot.get("scheduled", True) is not False]


def _same_run_evidence_ids(slot: Mapping[str, object]) -> frozenset[str]:
    evidence = slot.get("evidence", ())
    if not isinstance(evidence, Sequence):
        return frozenset()
    ids: set[str] = set()
    for item in evidence:
        evidence_id = getattr(item, "evidence_id", None)
        if evidence_id is None and isinstance(item, Mapping):
            evidence_id = item.get("evidence_id")
        if isinstance(evidence_id, str):
            ids.add(evidence_id)
    return frozenset(ids)


def _same_run_rule_eval_ids(slot: Mapping[str, object]) -> frozenset[str]:
    batches = slot.get("rule_evaluation_batches", ())
    if not isinstance(batches, Sequence):
        return frozenset()
    ids: set[str] = set()
    for batch in batches:
        evaluations = getattr(batch, "evaluations", None)
        if evaluations is None and isinstance(batch, Mapping):
            evaluations = batch.get("evaluations", ())
        if not isinstance(evaluations, Sequence):
            continue
        for item in evaluations:
            evaluation_id = getattr(item, "evaluation_id", None)
            if evaluation_id is None and isinstance(item, Mapping):
                evaluation_id = item.get("evaluation_id")
            if isinstance(evaluation_id, str):
                ids.add(evaluation_id)
    return frozenset(ids)


def _claim_has_same_run_refs(
    claim: Mapping[str, object],
    *,
    evidence_ids: frozenset[str],
    rule_eval_ids: frozenset[str],
) -> bool:
    evidence_refs = claim.get("evidence_refs", ())
    rule_refs = claim.get("rule_refs", ())
    if not isinstance(evidence_refs, Sequence) or not isinstance(rule_refs, Sequence):
        return False
    if not evidence_refs and not rule_refs:
        return False
    for ref in evidence_refs:
        if ref not in evidence_ids:
            return False
    for ref in rule_refs:
        if ref not in rule_eval_ids:
            return False
    return True


def validate_scored_slots(slots: Sequence[Mapping[str, object]]) -> None:
    """T-CX288: scored metrics require validated campaign provenance."""
    for slot in slots:
        validate_scored_campaign_input(slot)


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


def terminal_reach_rate(slots: Sequence[Mapping[str, object]]) -> RateMetric:
    """T-CX283: terminal reach over scheduled slots (infrastructure failures excluded)."""
    validate_scored_slots(slots)
    scheduled = _scheduled_slots(slots)
    numerator = sum(
        1
        for slot in scheduled
        if slot.get("terminal_reached") is True
        and slot.get("infrastructure_failure") is not True
    )
    return _rate(numerator, len(scheduled))


def diagnosis_completion_rate(slots: Sequence[Mapping[str, object]]) -> RateMetric:
    """T-CX283: completed_diagnosis over all scheduled slots (diagnosis-less stays in denom)."""
    validate_scored_slots(slots)
    scheduled = _scheduled_slots(slots)
    numerator = sum(
        1 for slot in scheduled if slot.get("completed_diagnosis") is True
    )
    return _rate(numerator, len(scheduled))


def completion_denominator(slots: Sequence[Mapping[str, object]]) -> RateMetric:
    """Alias for diagnosis completion rate (legacy name in harness tests)."""
    return diagnosis_completion_rate(slots)


def claim_population_denominator(
    slots: Sequence[Mapping[str, object]],
) -> RateMetric:
    """T-CX283: grounding rate over every claim on completed diagnoses."""
    validate_scored_slots(slots)
    grounded = 0
    total = 0
    for slot in slots:
        if slot.get("completed_diagnosis") is not True:
            continue
        evidence_ids = _same_run_evidence_ids(slot)
        rule_eval_ids = _same_run_rule_eval_ids(slot)
        claims = slot.get("claims", ())
        if not isinstance(claims, Sequence):
            continue
        for claim in claims:
            if not isinstance(claim, Mapping):
                claim_mapping = getattr(claim, "model_dump", None)
                if callable(claim_mapping):
                    claim = claim_mapping()
                else:
                    continue
            total += 1
            if _claim_has_same_run_refs(
                claim,
                evidence_ids=evidence_ids,
                rule_eval_ids=rule_eval_ids,
            ):
                grounded += 1
    return _rate(grounded, total)


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
