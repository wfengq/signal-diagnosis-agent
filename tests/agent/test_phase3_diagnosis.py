"""Phase 3 diagnosis validation tests (T119)."""

from __future__ import annotations

import pytest

from signal_diag.agent.diagnosis import validate_finish_decision
from signal_diag.agent.models import (
    DiagnosisClaim,
    DiagnosisValidationError,
    FinishDecision,
    TaskAssessment,
)


def assessment() -> TaskAssessment:
    return TaskAssessment(
        task_type="distortion_analysis",
        objective="determine distortion cause",
    )


def test_t119_unknown_rule_reference_is_rejected() -> None:
    decision = FinishDecision(
        outcome="supported_fault",
        claims=(
            DiagnosisClaim(
                claim_id="claim_clip",
                fault_type="clipping",
                statement="Configured clipping rule failed.",
                evidence_refs=("ev_clip_001",),
                rule_refs=("ruleval_missing",),
            ),
        ),
        confidence_label="high",
    )
    with pytest.raises(DiagnosisValidationError, match="unknown rule reference"):
        validate_finish_decision(
            decision,
            known_evidence_ids=frozenset({"ev_clip_001"}),
            known_rule_evaluation_ids=frozenset({"ruleval_real"}),
            known_knowledge_retrieval_ids=frozenset(),
            task_assessment=assessment(),
        )


def test_t119_unknown_knowledge_reference_is_rejected() -> None:
    decision = FinishDecision(
        outcome="supported_fault",
        claims=(
            DiagnosisClaim(
                claim_id="claim_clip",
                fault_type="clipping",
                statement="Clipping with explanation.",
                evidence_refs=("ev_clip_001",),
                knowledge_refs=("know_missing",),
            ),
        ),
        confidence_label="high",
    )
    with pytest.raises(DiagnosisValidationError, match="unknown knowledge reference"):
        validate_finish_decision(
            decision,
            known_evidence_ids=frozenset({"ev_clip_001"}),
            known_rule_evaluation_ids=frozenset(),
            known_knowledge_retrieval_ids=frozenset({"know_real"}),
            task_assessment=assessment(),
        )


def test_t119_phase2_callers_remain_compatible() -> None:
    decision = FinishDecision(
        outcome="supported_fault",
        claims=(
            DiagnosisClaim(
                claim_id="claim_clip",
                fault_type="clipping",
                statement="Clipping detected.",
                evidence_refs=("ev_clip_001",),
            ),
        ),
        confidence_label="high",
    )
    validate_finish_decision(
        decision,
        known_evidence_ids=frozenset({"ev_clip_001"}),
        task_assessment=assessment(),
    )


def test_t119_inconclusive_rejects_unknown_rule_refs() -> None:
    decision = FinishDecision(
        outcome="inconclusive",
        claims=(
            DiagnosisClaim(
                claim_id="claim_noise",
                fault_type="inconclusive",
                statement="Fabricated rule refs must be rejected.",
                rule_refs=("ruleval_fake",),
            ),
        ),
        confidence_label="low",
        limitations=("metrics not applicable",),
    )
    with pytest.raises(DiagnosisValidationError, match="unknown rule reference"):
        validate_finish_decision(
            decision,
            known_evidence_ids=frozenset(),
            known_rule_evaluation_ids=frozenset(),
            known_knowledge_retrieval_ids=frozenset(),
            task_assessment=assessment(),
        )


def test_t119_inconclusive_rejects_unknown_knowledge_refs() -> None:
    decision = FinishDecision(
        outcome="inconclusive",
        claims=(
            DiagnosisClaim(
                claim_id="claim_noise",
                fault_type="inconclusive",
                statement="Fabricated knowledge refs must be rejected.",
                knowledge_refs=("know_fake",),
            ),
        ),
        confidence_label="low",
        limitations=("metrics not applicable",),
    )
    with pytest.raises(DiagnosisValidationError, match="unknown knowledge reference"):
        validate_finish_decision(
            decision,
            known_evidence_ids=frozenset(),
            known_rule_evaluation_ids=frozenset(),
            known_knowledge_retrieval_ids=frozenset(),
            task_assessment=assessment(),
        )


def test_t119_unsupported_rejects_unknown_rule_refs() -> None:
    decision = FinishDecision(
        task_assessment=TaskAssessment(
            task_type="unsupported",
            objective="out of scope",
        ),
        outcome="inconclusive",
        claims=(
            DiagnosisClaim(
                claim_id="claim_unsup",
                fault_type="inconclusive",
                statement="Fabricated rule refs must be rejected.",
                rule_refs=("ruleval_fake",),
            ),
        ),
        confidence_label="low",
        limitations=("task unsupported",),
    )
    with pytest.raises(DiagnosisValidationError, match="unknown rule reference"):
        validate_finish_decision(
            decision,
            known_evidence_ids=frozenset(),
            known_rule_evaluation_ids=frozenset(),
            known_knowledge_retrieval_ids=frozenset(),
            task_assessment=None,
        )


def test_t119_unsupported_rejects_unknown_knowledge_refs() -> None:
    decision = FinishDecision(
        task_assessment=TaskAssessment(
            task_type="unsupported",
            objective="out of scope",
        ),
        outcome="inconclusive",
        claims=(
            DiagnosisClaim(
                claim_id="claim_unsup",
                fault_type="inconclusive",
                statement="Fabricated knowledge refs must be rejected.",
                knowledge_refs=("know_fake",),
            ),
        ),
        confidence_label="low",
        limitations=("task unsupported",),
    )
    with pytest.raises(DiagnosisValidationError, match="unknown knowledge reference"):
        validate_finish_decision(
            decision,
            known_evidence_ids=frozenset(),
            known_rule_evaluation_ids=frozenset(),
            known_knowledge_retrieval_ids=frozenset(),
            task_assessment=None,
        )


def test_t119_valid_rule_and_knowledge_refs_pass() -> None:
    decision = FinishDecision(
        outcome="supported_fault",
        claims=(
            DiagnosisClaim(
                claim_id="claim_clip",
                fault_type="clipping",
                statement="Configured clipping rule failed.",
                evidence_refs=("ev_clip_001",),
                rule_refs=("ruleval_real",),
                knowledge_refs=("know_real",),
            ),
        ),
        confidence_label="high",
    )
    validate_finish_decision(
        decision,
        known_evidence_ids=frozenset({"ev_clip_001"}),
        known_rule_evaluation_ids=frozenset({"ruleval_real"}),
        known_knowledge_retrieval_ids=frozenset({"know_real"}),
        task_assessment=assessment(),
    )
