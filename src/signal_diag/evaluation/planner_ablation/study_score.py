"""Offline planner-ablation study scoring chain (dual-arm → conclusion)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from signal_diag.evaluation.planner_ablation.decision import (
    StudyComparisonMetrics,
    StudyConclusion,
    StudyDecisionProtocol,
    decide_study_conclusion,
)
from signal_diag.evaluation.planner_ablation.identity import (
    PLANNER_ABLATION_SCORING_IDENTITY,
    PLANNER_ABLATION_STUDY_ID,
    validate_scored_campaign_input,
)
from signal_diag.evaluation.planner_ablation.scoring import (
    ScoringPopulationError,
    claim_population_denominator,
    diagnosis_completion_rate,
    validate_scored_slots,
)

_POSITIVE_FAULT_TYPES = frozenset({"clipping", "harmonic_distortion"})


class StudyOracleLabel(BaseModel):
    """Preregistered oracle label for one scored case slot."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(min_length=1)
    expected_outcome: str = Field(min_length=1)
    expected_causal_faults: tuple[str, ...] = ()


def _validate_protocol(protocol: StudyDecisionProtocol) -> None:
    if protocol.study_id != PLANNER_ABLATION_STUDY_ID:
        raise ValueError("foreign study identity in protocol")
    if protocol.scoring_identity != PLANNER_ABLATION_SCORING_IDENTITY:
        raise ValueError("foreign scoring identity in protocol")


def _validate_arm_slots(slots: Sequence[Mapping[str, object]], *, arm: str) -> None:
    for slot in slots:
        if slot.get("arm") != arm:
            raise ValueError(f"slot arm mismatch: expected {arm}")
        validate_scored_campaign_input(slot)


def _scheduled_slots(slots: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    return [slot for slot in slots if slot.get("scheduled", True) is not False]


def _claim_mapping(claim: object) -> Mapping[str, object] | None:
    if isinstance(claim, Mapping):
        return claim
    dump = getattr(claim, "model_dump", None)
    if callable(dump):
        return dump()
    return None


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


def _claim_grounded(
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


def unsupported_positive_claim_rate(
    slots: Sequence[Mapping[str, object]],
) -> tuple[float | None, bool]:
    """Rate of ungrounded clipping/harmonic claims over positive-claim population."""
    validate_scored_slots(slots)
    positive = 0
    unsupported = 0
    for slot in slots:
        if slot.get("completed_diagnosis") is not True:
            continue
        evidence_ids = _same_run_evidence_ids(slot)
        rule_eval_ids = _same_run_rule_eval_ids(slot)
        claims = slot.get("claims", ())
        if not isinstance(claims, Sequence):
            continue
        for raw_claim in claims:
            claim = _claim_mapping(raw_claim)
            if claim is None:
                continue
            fault_type = claim.get("fault_type")
            if fault_type not in _POSITIVE_FAULT_TYPES:
                continue
            positive += 1
            if not _claim_grounded(
                claim,
                evidence_ids=evidence_ids,
                rule_eval_ids=rule_eval_ids,
            ):
                unsupported += 1
    if positive == 0:
        return None, False
    return unsupported / positive, unsupported == 0


def _predicted_causal_faults(slot: Mapping[str, object]) -> frozenset[str]:
    outcome = slot.get("diagnosis_outcome")
    if outcome != "supported_fault":
        return frozenset()
    claims = slot.get("claims", ())
    if not isinstance(claims, Sequence):
        return frozenset()
    faults: set[str] = set()
    for raw_claim in claims:
        claim = _claim_mapping(raw_claim)
        if claim is None:
            continue
        fault_type = claim.get("fault_type")
        if fault_type in _POSITIVE_FAULT_TYPES:
            faults.add(str(fault_type))
    return frozenset(faults)


def primary_quality_rate(
    slots: Sequence[Mapping[str, object]],
    oracle_by_case: Mapping[str, StudyOracleLabel],
) -> float:
    correct = 0
    total = 0
    for slot in slots:
        if slot.get("completed_diagnosis") is not True:
            continue
        case_id = str(slot.get("case_id", ""))
        label = oracle_by_case.get(case_id)
        if label is None:
            continue
        total += 1
        predicted_outcome = slot.get("diagnosis_outcome")
        expected_faults = frozenset(label.expected_causal_faults)
        if (
            predicted_outcome == label.expected_outcome
            and _predicted_causal_faults(slot) == expected_faults
        ):
            correct += 1
    if total == 0:
        return 0.0
    return correct / total


def _is_useful_terminal(slot: Mapping[str, object]) -> bool:
    outcome = slot.get("diagnosis_outcome")
    if outcome == "no_supported_fault":
        return True
    if outcome != "supported_fault":
        return False
    claims = slot.get("claims", ())
    if not isinstance(claims, Sequence):
        return False
    for raw_claim in claims:
        claim = _claim_mapping(raw_claim)
        if claim is None:
            continue
        if claim.get("fault_type") in _POSITIVE_FAULT_TYPES:
            return True
    return False


def usefulness_rate(slots: Sequence[Mapping[str, object]]) -> float:
    scheduled = _scheduled_slots(slots)
    if not scheduled:
        return 0.0
    useful = sum(1 for slot in scheduled if _is_useful_terminal(slot))
    return useful / len(scheduled)


def build_study_comparison_metrics(
    *,
    product_slots: Sequence[Mapping[str, object]],
    fixed_slots: Sequence[Mapping[str, object]],
    oracle: Sequence[StudyOracleLabel],
    fixed_latency_improvement_ratio: float = 0.0,
    matched_comparison: bool = True,
) -> StudyComparisonMetrics:
    _validate_arm_slots(product_slots, arm="product_agent")
    _validate_arm_slots(fixed_slots, arm="fixed_pipeline")
    oracle_by_case = {item.case_id: item for item in oracle}

    product_completion = diagnosis_completion_rate(product_slots).value
    fixed_completion = diagnosis_completion_rate(fixed_slots).value

    def _grounding_ok(slots: Sequence[Mapping[str, object]]) -> bool:
        try:
            return claim_population_denominator(slots).value == 1.0
        except ScoringPopulationError:
            return False

    def _evaluable_claim_population(slots: Sequence[Mapping[str, object]]) -> bool:
        try:
            claim_population_denominator(slots)
            return True
        except ScoringPopulationError:
            return False

    _, product_unsupported_ok = unsupported_positive_claim_rate(product_slots)
    _, fixed_unsupported_ok = unsupported_positive_claim_rate(fixed_slots)

    evaluable = (
        bool(product_slots)
        and bool(fixed_slots)
        and _evaluable_claim_population(product_slots)
        and _evaluable_claim_population(fixed_slots)
    )

    return StudyComparisonMetrics(
        product_primary_quality=primary_quality_rate(product_slots, oracle_by_case),
        fixed_primary_quality=primary_quality_rate(fixed_slots, oracle_by_case),
        product_usefulness=usefulness_rate(product_slots),
        fixed_usefulness=usefulness_rate(fixed_slots),
        product_completion=product_completion,
        fixed_completion=fixed_completion,
        product_safety_ok=product_unsupported_ok and _grounding_ok(product_slots),
        fixed_safety_ok=fixed_unsupported_ok and _grounding_ok(fixed_slots),
        fixed_latency_improvement_ratio=fixed_latency_improvement_ratio,
        matched_comparison=matched_comparison,
        evaluable_population=evaluable,
        protocol_complete=True,
        unmatched_comparison=not matched_comparison,
    )


def score_planner_ablation_study(
    *,
    product_slots: Sequence[Mapping[str, object]],
    fixed_slots: Sequence[Mapping[str, object]],
    oracle: Sequence[StudyOracleLabel],
    protocol: StudyDecisionProtocol,
    fixed_latency_improvement_ratio: float = 0.0,
) -> StudyConclusion:
    _validate_protocol(protocol)
    metrics = build_study_comparison_metrics(
        product_slots=product_slots,
        fixed_slots=fixed_slots,
        oracle=oracle,
        fixed_latency_improvement_ratio=fixed_latency_improvement_ratio,
    )
    return decide_study_conclusion(protocol, metrics)
