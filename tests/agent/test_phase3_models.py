"""Phase 3 Agent model extensions (T113–T116)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from signal_diag.agent.models import (
    DiagnosisClaim,
    EvaluateRulesDecision,
    PlannerContext,
    RetrieveKnowledgeDecision,
)
from signal_diag.agent.state import DiagnosisState
from signal_diag.knowledge.models import KnowledgeRetrievalResult
from signal_diag.rules.models import RuleEvaluation, RuleEvaluationBatch
from signal_diag.signal.models import SignalMeta
from signal_diag.tools.registry import get_tool_descriptors


def _batch() -> RuleEvaluationBatch:
    evaluation = RuleEvaluation(
        evaluation_id="ruleval_test_001",
        rule_id="rule_ratio",
        judgment="pass",
        observed_value=0.0,
        comparator="lte",
        threshold=0.01,
        profile_id="profile_s1_distortion",
        profile_version="1.0.0-demo",
        evidence_refs=("ev_clip_001",),
    )
    return RuleEvaluationBatch(
        batch_id="rulebatch_test_001",
        profile_id="profile_s1_distortion",
        profile_version="1.0.0-demo",
        evaluations=(evaluation,),
    )


def _retrieval() -> KnowledgeRetrievalResult:
    from signal_diag.knowledge.models import KnowledgeChunk, KnowledgeMatch

    chunk = KnowledgeChunk(
        chunk_id="chunk_clipping_000",
        document_id="doc_clipping",
        title="Clipping / Observable evidence",
        excerpt="Flat tops support clipping.",
    )
    match = KnowledgeMatch(
        document_id="doc_clipping",
        chunk_id="chunk_clipping_000",
        matched_terms=("clipping",),
    )
    return KnowledgeRetrievalResult(
        retrieval_id="know_test_001",
        query_text="clipping",
        matches=(match,),
        chunks=(chunk,),
    )


def planner_context(
    *,
    rule_evaluation_batches: tuple[RuleEvaluationBatch, ...] = (),
    knowledge_retrievals: tuple[KnowledgeRetrievalResult, ...] = (),
) -> PlannerContext:
    return PlannerContext(
        run_id="run_phase3",
        user_request="Why distorted?",
        signal_meta=SignalMeta(
            signal_id="sig_phase3",
            source_type="generated",
            sample_rate_hz=48_000,
            channels=1,
            num_samples=96_000,
            duration_s=2.0,
            original_dtype="float32",
        ),
        task_assessment=None,
        observations=(),
        evidence=(),
        tool_history=(),
        available_tools=get_tool_descriptors(),
        remaining_tool_calls=8,
        remaining_planner_retries=2,
        no_progress_count=0,
        rule_evaluation_batches=rule_evaluation_batches,
        knowledge_retrievals=knowledge_retrievals,
    )


def test_t113_evaluate_rules_decision_validation() -> None:
    decision = EvaluateRulesDecision(
        profile_id="profile_s1_distortion",
        evidence_refs=("ev_clip_001",),
        purpose="apply configured limits",
    )
    assert decision.decision_type == "evaluate_rules"
    with pytest.raises(ValidationError):
        EvaluateRulesDecision(profile_id="bad", purpose="x")


def test_t114_retrieve_knowledge_requires_query() -> None:
    with pytest.raises(ValidationError):
        RetrieveKnowledgeDecision(query_text="", purpose="explain")


def test_t115_context_uses_immutable_snapshots() -> None:
    context = planner_context(
        rule_evaluation_batches=(_batch(),),
        knowledge_retrievals=(_retrieval(),),
    )
    assert isinstance(context.rule_evaluation_batches, tuple)
    assert isinstance(context.knowledge_retrievals, tuple)


def test_t116_diagnosis_state_mutability() -> None:
    state: DiagnosisState = {
        "run_id": "run_state",
        "signal_id": "sig_state",
        "user_request": "test",
        "signal_meta": planner_context().signal_meta,
        "task_assessment": None,
        "observations": [],
        "evidence": [],
        "tool_history": [],
        "planner_attempt_count": 0,
        "tool_call_count": 0,
        "no_progress_count": 0,
        "warnings": [],
        "errors": [],
        "termination_reason": None,
        "diagnosis": None,
        "rule_evaluation_batches": [],
        "knowledge_retrievals": [],
        "rule_evaluation_count": 0,
        "knowledge_retrieval_count": 0,
    }
    state["rule_evaluation_batches"].append(_batch())
    state["knowledge_retrievals"].append(_retrieval())
    assert len(state["rule_evaluation_batches"]) == 1
    assert len(state["knowledge_retrievals"]) == 1


def test_diagnosis_claim_supports_phase3_refs() -> None:
    claim = DiagnosisClaim(
        claim_id="claim_phase3",
        fault_type="clipping",
        statement="Configured clipping rule failed.",
        evidence_refs=("ev_clip_001",),
        rule_refs=("ruleval_test_001",),
        knowledge_refs=("know_test_001",),
    )
    assert claim.rule_refs == ("ruleval_test_001",)
    assert claim.knowledge_refs == ("know_test_001",)
