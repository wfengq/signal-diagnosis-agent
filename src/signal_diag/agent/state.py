"""Mutable runtime state owned by DistortionDiagnosisRuntime."""

from typing import NotRequired, TypedDict

from signal_diag.knowledge.models import KnowledgeRetrievalResult
from signal_diag.rules.models import RuleEvaluationBatch
from signal_diag.signal.context import StimulusContext
from signal_diag.signal.models import SignalMeta
from signal_diag.tools.evidence import Evidence

from .models import (
    Observation,
    StructuredDiagnosis,
    TaskAssessment,
    TerminationReason,
    ToolHistoryEntry,
)


class DiagnosisState(TypedDict):
    run_id: str
    signal_id: str
    user_request: str
    signal_meta: SignalMeta
    stimulus_context: StimulusContext
    reference_signal_meta: NotRequired[SignalMeta | None]
    task_assessment: TaskAssessment | None
    observations: list[Observation]
    evidence: list[Evidence]
    tool_history: list[ToolHistoryEntry]
    planner_attempt_count: int
    tool_call_count: int
    no_progress_count: int
    warnings: list[str]
    errors: list[str]
    termination_reason: TerminationReason | None
    diagnosis: StructuredDiagnosis | None
    rule_evaluation_batches: list[RuleEvaluationBatch]
    knowledge_retrievals: list[KnowledgeRetrievalResult]
    rule_evaluation_count: int
    knowledge_retrieval_count: int
