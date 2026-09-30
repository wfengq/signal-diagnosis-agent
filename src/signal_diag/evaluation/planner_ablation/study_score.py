"""Offline planner-ablation study scoring chain (dual-arm → conclusion)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, model_validator

from signal_diag.evaluation.models import RateMetric
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
from signal_diag.evaluation.planner_ablation.models import (
    FixedPipelineOutcome,
    ProductSlotOutcome,
    StudyMode,
)
from signal_diag.evaluation.planner_ablation.scoring import (
    ScoringPopulationError,
    claim_population_denominator,
    diagnosis_completion_rate,
    validate_scored_slots,
)

_POSITIVE_FAULT_TYPES = frozenset({"clipping", "harmonic_distortion"})


class StudySlotKey(BaseModel):
    """Preregistered schedule key (case + mode)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(min_length=1)
    mode: StudyMode


class StudyOracleLabel(BaseModel):
    """Preregistered oracle label for one scheduled slot."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(min_length=1)
    mode: StudyMode
    expected_outcome: str = Field(min_length=1)
    expected_causal_faults: tuple[str, ...] = ()

    @property
    def slot_key(self) -> StudySlotKey:
        return StudySlotKey(case_id=self.case_id, mode=self.mode)


class VerifiedStudyInput(BaseModel):
    """Frozen verified study input: protocol, identities, schedule, and oracle cover."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    protocol: StudyDecisionProtocol
    population_identity: str = Field(min_length=1)
    oracle_identity: str = Field(min_length=1)
    input_identity: str = Field(min_length=1)
    code_identity: str = Field(min_length=1)
    schedule: tuple[StudySlotKey, ...]
    oracle: tuple[StudyOracleLabel, ...]

    @model_validator(mode="after")
    def _verify_on_build(self) -> VerifiedStudyInput:
        verify_study_input(self)
        return self


def _format_key_set(
    keys: set[StudySlotKey] | frozenset[StudySlotKey] | set[tuple[str, str]] | frozenset[tuple[str, str]],
) -> list[str]:
    if not keys:
        return []
    sample = next(iter(keys))
    if isinstance(sample, tuple):
        return sorted(f"{case_id}/{mode}" for case_id, mode in keys)  # type: ignore[misc]
    return sorted(f"{key.case_id}/{key.mode}" for key in keys)  # type: ignore[union-attr]


def verify_study_input(study: VerifiedStudyInput) -> None:
    """Fail closed when schedule, oracle, identities, or protocol do not align."""
    if study.protocol.study_id != PLANNER_ABLATION_STUDY_ID:
        raise ValueError("foreign study identity in protocol")
    if study.protocol.scoring_identity != PLANNER_ABLATION_SCORING_IDENTITY:
        raise ValueError("foreign scoring identity in protocol")
    if not study.oracle:
        raise ValueError("oracle must be non-empty")
    schedule_keys: list[StudySlotKey] = []
    seen_schedule: set[tuple[str, str]] = set()
    for key in study.schedule:
        token = (key.case_id, key.mode)
        if token in seen_schedule:
            raise ValueError(f"duplicate schedule key: {key.case_id}/{key.mode}")
        seen_schedule.add(token)
        schedule_keys.append(key)
    if not schedule_keys:
        raise ValueError("schedule must be non-empty")

    oracle_by_key: dict[tuple[str, str], StudyOracleLabel] = {}
    for label in study.oracle:
        token = (label.case_id, label.mode)
        if token in oracle_by_key:
            raise ValueError(f"duplicate oracle key: {label.case_id}/{label.mode}")
        oracle_by_key[token] = label

    schedule_set = frozenset(seen_schedule)
    oracle_set = frozenset(oracle_by_key)
    if schedule_set != oracle_set:
        missing = schedule_set - oracle_set
        extra = oracle_set - schedule_set
        if missing:
            raise ValueError(
                f"oracle missing keys for schedule: {_format_key_set(missing)}"
            )
        raise ValueError(f"oracle has keys not in schedule: {_format_key_set(extra)}")


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


def _slot_key_from_mapping(slot: Mapping[str, object]) -> StudySlotKey:
    case_id = slot.get("case_id")
    mode = slot.get("mode")
    if not isinstance(case_id, str) or not case_id:
        raise ValueError("slot missing case_id")
    if mode not in ("single_signal", "paired_reference"):
        raise ValueError("slot missing or invalid mode")
    return StudySlotKey(case_id=case_id, mode=mode)  # type: ignore[arg-type]


def _index_arm_slots(
    slots: Sequence[Mapping[str, object]],
    *,
    arm: str,
    schedule: Sequence[StudySlotKey],
) -> dict[StudySlotKey, Mapping[str, object]]:
    _validate_arm_slots(slots, arm=arm)
    indexed: dict[StudySlotKey, Mapping[str, object]] = {}
    for slot in slots:
        key = _slot_key_from_mapping(slot)
        if key in indexed:
            raise ValueError(f"duplicate slot key in {arm}: {key.case_id}/{key.mode}")
        indexed[key] = slot
    expected = {item for item in schedule}
    found = set(indexed)
    if found != expected:
        missing = expected - found
        extra = found - expected
        if missing:
            raise ValueError(
                f"{arm} missing scheduled slots: {_format_key_set(missing)}"
            )
        raise ValueError(
            f"{arm} has slots not in schedule: {_format_key_set(extra)}"
        )
    return indexed


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
        return None, True
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


def _schedule_quality_rate(
    slots_by_key: Mapping[StudySlotKey, Mapping[str, object]],
    oracle_by_key: Mapping[StudySlotKey, StudyOracleLabel],
    schedule: Sequence[StudySlotKey],
) -> RateMetric:
    correct = 0
    total = len(schedule)
    if total == 0:
        raise ScoringPopulationError("primary quality schedule is empty; not evaluable")
    for key in schedule:
        label = oracle_by_key[key]
        slot = slots_by_key[key]
        if slot.get("completed_diagnosis") is not True:
            continue
        predicted_outcome = slot.get("diagnosis_outcome")
        expected_faults = frozenset(label.expected_causal_faults)
        if (
            predicted_outcome == label.expected_outcome
            and _predicted_causal_faults(slot) == expected_faults
        ):
            correct += 1
    return RateMetric(
        numerator=correct,
        denominator=total,
        value=correct / total,
    )


def primary_quality_rate(
    slots: Sequence[Mapping[str, object]],
    oracle_by_key: Mapping[StudySlotKey, StudyOracleLabel],
    *,
    schedule: Sequence[StudySlotKey],
) -> RateMetric:
    """Primary quality over the preregistered schedule (failures stay in denominator)."""
    slots_by_key = {_slot_key_from_mapping(slot): slot for slot in slots}
    return _schedule_quality_rate(slots_by_key, oracle_by_key, schedule)


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


@dataclass(frozen=True)
class BuiltStudyComparison:
    """Metrics bundle including preregistered population identity and quality rates."""

    metrics: StudyComparisonMetrics
    population_identity: str
    product_primary_quality: RateMetric
    fixed_primary_quality: RateMetric


def _oracle_index(oracle: Sequence[StudyOracleLabel]) -> dict[StudySlotKey, StudyOracleLabel]:
    return {label.slot_key: label for label in oracle}


def _study_protocol_complete(study: VerifiedStudyInput) -> bool:
    try:
        verify_study_input(study)
    except ValueError:
        return False
    return True


def build_study_comparison_metrics(
    *,
    study: VerifiedStudyInput,
    product_slots: Sequence[Mapping[str, object]],
    fixed_slots: Sequence[Mapping[str, object]],
    fixed_latency_improvement_ratio: float = 0.0,
) -> BuiltStudyComparison:
    verify_study_input(study)
    _validate_protocol(study.protocol)
    protocol_complete = _study_protocol_complete(study)

    product_by_key = _index_arm_slots(
        product_slots, arm="product_agent", schedule=study.schedule
    )
    fixed_by_key = _index_arm_slots(
        fixed_slots, arm="fixed_pipeline", schedule=study.schedule
    )
    matched_comparison = True
    oracle_by_key = _oracle_index(study.oracle)

    product_slots_ordered = [product_by_key[key] for key in study.schedule]
    fixed_slots_ordered = [fixed_by_key[key] for key in study.schedule]

    product_quality = _schedule_quality_rate(
        product_by_key, oracle_by_key, study.schedule
    )
    fixed_quality = _schedule_quality_rate(fixed_by_key, oracle_by_key, study.schedule)

    product_completion = diagnosis_completion_rate(product_slots_ordered).value
    fixed_completion = diagnosis_completion_rate(fixed_slots_ordered).value

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

    _, product_unsupported_ok = unsupported_positive_claim_rate(product_slots_ordered)
    _, fixed_unsupported_ok = unsupported_positive_claim_rate(fixed_slots_ordered)

    evaluable = (
        bool(study.schedule)
        and bool(study.oracle)
        and matched_comparison
        and protocol_complete
        and _evaluable_claim_population(product_slots_ordered)
        and _evaluable_claim_population(fixed_slots_ordered)
    )

    metrics = StudyComparisonMetrics(
        product_primary_quality=product_quality.value,
        fixed_primary_quality=fixed_quality.value,
        product_usefulness=usefulness_rate(product_slots_ordered),
        fixed_usefulness=usefulness_rate(fixed_slots_ordered),
        product_completion=product_completion,
        fixed_completion=fixed_completion,
        product_safety_ok=product_unsupported_ok and _grounding_ok(product_slots_ordered),
        fixed_safety_ok=fixed_unsupported_ok and _grounding_ok(fixed_slots_ordered),
        fixed_latency_improvement_ratio=fixed_latency_improvement_ratio,
        matched_comparison=matched_comparison,
        evaluable_population=evaluable,
        protocol_complete=protocol_complete,
        unmatched_comparison=not matched_comparison,
    )
    return BuiltStudyComparison(
        metrics=metrics,
        population_identity=study.population_identity,
        product_primary_quality=product_quality,
        fixed_primary_quality=fixed_quality,
    )


def score_planner_ablation_study(
    *,
    study: VerifiedStudyInput,
    product_slots: Sequence[Mapping[str, object]],
    fixed_slots: Sequence[Mapping[str, object]],
    fixed_latency_improvement_ratio: float = 0.0,
) -> StudyConclusion:
    built = build_study_comparison_metrics(
        study=study,
        product_slots=product_slots,
        fixed_slots=fixed_slots,
        fixed_latency_improvement_ratio=fixed_latency_improvement_ratio,
    )
    return decide_study_conclusion(study.protocol, built.metrics)


def _claims_from_diagnosis(diagnosis: object) -> tuple[dict[str, object], ...]:
    if diagnosis is None:
        return ()
    claims = getattr(diagnosis, "claims", None)
    if not isinstance(claims, Sequence):
        return ()
    projected: list[dict[str, object]] = []
    for claim in claims:
        mapping = _claim_mapping(claim)
        if mapping is None:
            continue
        ev_refs = mapping.get("evidence_refs", ())
        rule_refs = mapping.get("rule_refs", ())
        projected.append(
            {
                "claim_id": mapping.get("claim_id", ""),
                "fault_type": mapping.get("fault_type"),
                "evidence_refs": tuple(ev_refs) if isinstance(ev_refs, Sequence) else (),
                "rule_refs": tuple(rule_refs) if isinstance(rule_refs, Sequence) else (),
            }
        )
    return tuple(projected)


def project_product_outcome(
    outcome: ProductSlotOutcome,
    *,
    case_id: str,
    study_id: str = PLANNER_ABLATION_STUDY_ID,
    scoring_identity: str = PLANNER_ABLATION_SCORING_IDENTITY,
    scheduled: bool = True,
) -> dict[str, object]:
    """Map a product-slot terminal into a scored campaign slot mapping."""
    result = outcome.result
    diagnosis = result.diagnosis if result is not None else None
    completed = outcome.terminal_status == "completed" and diagnosis is not None
    return {
        "arm": outcome.arm,
        "execution_identity": outcome.execution_identity,
        "planner_class": outcome.planner_class,
        "study_id": study_id,
        "scoring_identity": scoring_identity,
        "case_id": case_id,
        "mode": outcome.mode,
        "scheduled": scheduled,
        "completed_diagnosis": completed,
        "diagnosis_outcome": diagnosis.outcome if diagnosis is not None else None,
        "claims": _claims_from_diagnosis(diagnosis),
        "evidence": result.evidence if result is not None else (),
        "rule_evaluation_batches": (
            result.rule_evaluation_batches if result is not None else ()
        ),
    }


def project_fixed_outcome(
    outcome: FixedPipelineOutcome,
    *,
    study_id: str = PLANNER_ABLATION_STUDY_ID,
    scoring_identity: str = PLANNER_ABLATION_SCORING_IDENTITY,
    scheduled: bool = True,
) -> dict[str, object]:
    """Map a fixed-pipeline terminal into a scored campaign slot mapping."""
    baseline = outcome.baseline_result
    diagnosis = baseline.diagnosis
    completed = baseline.status == "success" and diagnosis is not None
    return {
        "arm": "fixed_pipeline",
        "execution_identity": "product_campaign",
        "planner_class": "PlannerAblationFixedPipelineBaseline",
        "study_id": study_id,
        "scoring_identity": scoring_identity,
        "case_id": outcome.case_id,
        "mode": outcome.mode,
        "scheduled": scheduled,
        "completed_diagnosis": completed,
        "diagnosis_outcome": diagnosis.outcome if diagnosis is not None else None,
        "claims": _claims_from_diagnosis(diagnosis),
        "evidence": baseline.evidence,
        "rule_evaluation_batches": baseline.rule_evaluation_batches,
    }
