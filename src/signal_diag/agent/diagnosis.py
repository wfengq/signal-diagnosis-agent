"""Finish-decision and diagnosis validation."""

from __future__ import annotations

from .models import (
    DiagnosisClaim,
    DiagnosisOutcome,
    DiagnosisValidationError,
    FinishDecision,
    TaskAssessment,
    TaskType,
)


def _claim_requires_evidence(claim: DiagnosisClaim, outcome: DiagnosisOutcome) -> bool:
    if outcome == "inconclusive":
        return False
    return claim.fault_type != "inconclusive"


def validate_finish_decision(
    decision: FinishDecision,
    *,
    known_evidence_ids: frozenset[str],
    task_assessment: TaskAssessment | None,
    known_rule_evaluation_ids: frozenset[str] = frozenset(),
    known_knowledge_retrieval_ids: frozenset[str] = frozenset(),
) -> None:
    """Validate finish semantics before accepting a terminal diagnosis."""
    assessment = decision.task_assessment or task_assessment
    if assessment is None:
        raise DiagnosisValidationError("finish decision requires task assessment")

    for claim in decision.claims:
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


def build_task_type(decision: FinishDecision, assessment: TaskAssessment) -> TaskType:
    return assessment.task_type
