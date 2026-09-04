"""Finish-decision and diagnosis validation."""

from __future__ import annotations

from collections.abc import Sequence

from signal_diag.rules.models import RuleEvaluation
from signal_diag.tools.evidence import Evidence

from .models import (
    DiagnosisClaim,
    DiagnosisOutcome,
    DiagnosisValidationError,
    FinishDecision,
    TaskAssessment,
    TaskType,
)

_SUBSTANTIAL_CLIPPING_RULE_IDS = frozenset(
    {
        "rule_clipping_ratio_acceptable",
        "rule_flat_top_absent",
    }
)


def _claim_requires_evidence(claim: DiagnosisClaim, outcome: DiagnosisOutcome) -> bool:
    if outcome == "inconclusive":
        return False
    return claim.fault_type != "inconclusive"


def _cited_evidence(
    claim: DiagnosisClaim,
    evidence_by_id: dict[str, Evidence],
) -> list[Evidence]:
    cited: list[Evidence] = []
    for evidence_id in claim.evidence_refs:
        item = evidence_by_id.get(evidence_id)
        if item is not None:
            cited.append(item)
    return cited


def _has_harmonic_even_order_structure(
    claim: DiagnosisClaim,
    evidence_by_id: dict[str, Evidence],
) -> bool:
    return any(
        item.metric == "series_kind"
        and item.value == "even_order_present"
        and item.validity == "valid"
        for item in _cited_evidence(claim, evidence_by_id)
    )


def _has_clipping_mechanism(
    claim: DiagnosisClaim,
    evidence_by_id: dict[str, Evidence],
) -> bool:
    return any(
        item.metric == "clipping_mechanism" and item.value is True
        for item in _cited_evidence(claim, evidence_by_id)
    )


def _has_substantial_clipping_rule_fail(
    claim: DiagnosisClaim,
    evaluations_by_id: dict[str, RuleEvaluation],
) -> bool:
    for rule_id in claim.rule_refs:
        evaluation = evaluations_by_id.get(rule_id)
        if (
            evaluation is not None
            and evaluation.rule_id in _SUBSTANTIAL_CLIPPING_RULE_IDS
            and evaluation.judgment == "fail"
        ):
            return True
    return False


def validate_finish_decision(
    decision: FinishDecision,
    *,
    known_evidence_ids: frozenset[str],
    task_assessment: TaskAssessment | None,
    known_rule_evaluation_ids: frozenset[str] = frozenset(),
    known_knowledge_retrieval_ids: frozenset[str] = frozenset(),
    evidence: Sequence[Evidence] | None = None,
    rule_evaluations: Sequence[RuleEvaluation] | None = None,
) -> None:
    """Validate finish semantics before accepting a terminal diagnosis."""
    assessment = decision.task_assessment or task_assessment
    if assessment is None:
        raise DiagnosisValidationError("finish decision requires task assessment")

    for claim in decision.claims:
        for evidence_id in claim.evidence_refs:
            if evidence_id not in known_evidence_ids:
                raise DiagnosisValidationError(
                    f"unknown evidence reference: {evidence_id}"
                )
        for rule_id in claim.rule_refs:
            if rule_id not in known_rule_evaluation_ids:
                raise DiagnosisValidationError(
                    f"unknown rule reference: {rule_id}"
                )
        for knowledge_id in claim.knowledge_refs:
            if knowledge_id not in known_knowledge_retrieval_ids:
                raise DiagnosisValidationError(
                    f"unknown knowledge reference: {knowledge_id}"
                )

    if assessment.task_type == "unsupported":
        return

    if decision.outcome == "inconclusive":
        if not decision.limitations:
            raise DiagnosisValidationError(
                "inconclusive finish requires at least one limitation"
            )
        return

    if not decision.claims:
        raise DiagnosisValidationError(
            "supported or no-supported-fault finish requires at least one claim"
        )

    if decision.outcome == "supported_fault":
        fault_types = {claim.fault_type for claim in decision.claims}
        positive_faults = fault_types - {"no_supported_fault", "inconclusive"}
        if positive_faults and "no_supported_fault" in fault_types:
            raise DiagnosisValidationError(
                "supported_fault must not include a sibling no_supported_fault claim"
            )

    for claim in decision.claims:
        if not _claim_requires_evidence(claim, decision.outcome):
            continue
        if not claim.evidence_refs:
            raise DiagnosisValidationError(
                f"claim {claim.claim_id} requires evidence references"
            )
        for evidence_id in claim.evidence_refs:
            if evidence_id not in known_evidence_ids:
                raise DiagnosisValidationError(
                    f"unknown evidence reference: {evidence_id}"
                )

    if evidence is None or decision.outcome != "supported_fault":
        return

    evidence_by_id = {item.evidence_id: item for item in evidence}
    evaluations_by_id = {
        item.evaluation_id: item for item in (rule_evaluations or ())
    }
    for claim in decision.claims:
        if (
            claim.fault_type == "harmonic_distortion"
            and not _has_harmonic_even_order_structure(claim, evidence_by_id)
        ):
            raise DiagnosisValidationError(
                "harmonic_distortion supported_fault requires series_kind="
                "even_order_present Evidence"
            )
        if claim.fault_type == "clipping":
            if not _has_clipping_mechanism(claim, evidence_by_id):
                raise DiagnosisValidationError(
                    "clipping supported_fault requires clipping_mechanism=true Evidence"
                )
            if not _has_substantial_clipping_rule_fail(claim, evaluations_by_id):
                raise DiagnosisValidationError(
                    "clipping supported_fault requires a same-run substantial "
                    "clipping rule FAIL (rule_clipping_ratio_acceptable or "
                    "rule_flat_top_absent)"
                )


def build_task_type(decision: FinishDecision, assessment: TaskAssessment) -> TaskType:
    return assessment.task_type
