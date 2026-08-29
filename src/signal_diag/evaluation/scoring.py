"""Pure per-run scoring over EvaluationTrace and EvaluationCase."""

from __future__ import annotations

import operator

from signal_diag.agent.models import (
    CallToolDecision,
    DiagnosisClaim,
    EvaluateRulesDecision,
    FinishDecision,
    RetrieveKnowledgeDecision,
    TerminationReason,
    ToolStatus,
)
from signal_diag.evaluation.models import (
    BaselineCompletionReason,
    BaselineRunResult,
    CausalFault,
    EvaluationCase,
    EvaluationTrace,
    EvidenceCondition,
    KnowledgeRetrievalEvent,
    ObservationEvent,
    PlannerDecisionEvent,
    RuleEvaluationEvent,
    RunScore,
)
from signal_diag.knowledge.models import KnowledgeRetrievalResult
from signal_diag.tools.contracts import ToolName
from signal_diag.tools.evidence import Evidence

_DSP_TOOLS: frozenset[str] = frozenset(
    {
        "detect_clipping",
        "analyze_spectrum",
        "estimate_fundamental",
        "analyze_harmonic_distortion",
    }
)
_FAILED_TOOL_STATUSES: frozenset[str] = frozenset({"error", "invalid"})
_CAUSAL_FAULTS: tuple[CausalFault, ...] = ("clipping", "harmonic_distortion")
_COMPARATORS = {
    "eq": operator.eq,
    "neq": operator.ne,
    "lt": operator.lt,
    "lte": operator.le,
    "gt": operator.gt,
    "gte": operator.ge,
}

FAILURE_EXACT_SET = "exact_set_mismatch"
FAILURE_OUTCOME = "outcome_mismatch"
FAILURE_UNGROUNDED = "ungrounded_claim"
FAILURE_UNSUPPORTED = "unsupported_fault_claim"
FAILURE_FIRST_TOOL = "first_tool_incorrect"
FAILURE_INAPPROPRIATE_REPLAN = "inappropriate_replan"
FAILURE_UNNECESSARY_TOOL = "unnecessary_tool"
FAILURE_LATE_TOOL = "late_tool_after_sufficiency"
FAILURE_PREMATURE_RULE = "premature_rule"
FAILURE_REDUNDANT_RULE = "redundant_rule"
FAILURE_OMITTED_RULE = "omitted_rule"
FAILURE_REQUIRED_KNOWLEDGE_OMITTED = "required_knowledge_omitted"
FAILURE_UNNECESSARY_KNOWLEDGE = "unnecessary_knowledge"
FAILURE_IRRELEVANT_TAGS = "irrelevant_knowledge_tags"
FAILURE_UNCITED_KNOWLEDGE = "uncited_knowledge"


def score_evaluation_trace(case: EvaluationCase, trace: EvaluationTrace) -> RunScore:
    diagnosis = trace.result.diagnosis
    claims = diagnosis.claims if diagnosis is not None else ()
    predicted_outcome = diagnosis.outcome if diagnosis is not None else None
    predicted_faults, predicted_fault_claims, unsupported_fault_claims = _fault_counts(
        case, claims
    )
    causal_exact_set_correct = predicted_faults == case.causal_faults
    outcome_correct = (
        predicted_outcome is not None
        and predicted_outcome in case.acceptable_outcomes
    )
    grounded_claims, scored_claims, grounding_failures = _ground_claims(
        case, trace, claims
    )
    path = _score_path(case, trace, claims)

    failure_codes = list(path.failure_codes)
    failure_codes.extend(grounding_failures)
    if not causal_exact_set_correct:
        failure_codes.append(FAILURE_EXACT_SET)
    if not outcome_correct:
        failure_codes.append(FAILURE_OUTCOME)
    if unsupported_fault_claims:
        failure_codes.append(FAILURE_UNSUPPORTED)

    completion_reason = _completion_reason(trace)
    first_tool_correct: bool | None
    if trace.execution_path == "fixed_pipeline":
        first_tool_correct = None
    else:
        first_tool_correct = (
            path.first_dsp_tool is not None
            and path.first_dsp_tool in case.acceptable_first_tools
        )
        if not first_tool_correct:
            failure_codes.append(FAILURE_FIRST_TOOL)

    return RunScore(
        trace_id=trace.trace_id,
        case_id=trace.case_id,
        run_slot=trace.run_slot,
        execution_path=trace.execution_path,
        expected_faults=case.causal_faults,
        predicted_faults=predicted_faults,
        acceptable_outcomes=case.acceptable_outcomes,
        predicted_outcome=predicted_outcome,
        causal_exact_set_correct=causal_exact_set_correct,
        outcome_correct=outcome_correct,
        grounded_claims=grounded_claims,
        scored_claims=scored_claims,
        unsupported_fault_claims=unsupported_fault_claims,
        predicted_fault_claims=predicted_fault_claims,
        first_tool_correct=first_tool_correct,
        appropriate_replans=path.appropriate_replans,
        replan_opportunities=path.replan_opportunities,
        unnecessary_tool_actions=path.unnecessary_tool_actions,
        tool_actions=path.tool_actions,
        timely_stop=path.timely_stop,
        correct_rule_actions=path.correct_rule_actions,
        rule_action_opportunities=path.rule_action_opportunities,
        required_knowledge_actions=path.required_knowledge_actions,
        required_knowledge_opportunities=path.required_knowledge_opportunities,
        unnecessary_knowledge_actions=path.unnecessary_knowledge_actions,
        knowledge_actions=path.knowledge_actions,
        cited_knowledge_actions=path.cited_knowledge_actions,
        planner_calls=path.planner_calls,
        end_to_end_latency_ms=None,
        provider_usage=trace.provider_usage,
        completion_reason=completion_reason,
        failure_codes=_unique(failure_codes),
    )


class _PathScore:
    def __init__(self) -> None:
        self.first_dsp_tool: ToolName | None = None
        self.appropriate_replans = 0
        self.replan_opportunities = 0
        self.unnecessary_tool_actions = 0
        self.tool_actions = 0
        self.timely_stop = True
        self.correct_rule_actions = 0
        self.rule_action_opportunities = 0
        self.required_knowledge_actions = 0
        self.required_knowledge_opportunities = 0
        self.unnecessary_knowledge_actions = 0
        self.knowledge_actions = 0
        self.cited_knowledge_actions = 0
        self.planner_calls = 0
        self.failure_codes: list[str] = []
        self.pending_knowledge_replan = False


def _score_path(
    case: EvaluationCase,
    trace: EvaluationTrace,
    claims: tuple[DiagnosisClaim, ...],
) -> _PathScore:
    score = _PathScore()
    satisfied: set[str] = set()
    contradicted: set[str] = set()
    success_evidence_ids: list[str] = []
    seen_rule_states: set[frozenset[str]] = set()
    pending_delta = False
    last_status: ToolStatus | None = None
    sufficient = False
    pending_tool: dict[str, object] | None = None
    rule_decisions = 0
    retrievals: list[KnowledgeRetrievalResult] = []

    if trace.execution_path == "fixed_pipeline":
        _score_baseline_path(case, trace, score)
        return score

    for event in trace.events:
        if isinstance(event, PlannerDecisionEvent):
            score.planner_calls += 1
            record = event.record
            if record.status != "decision" or record.decision is None:
                continue
            is_replan = pending_delta
            if is_replan:
                score.replan_opportunities += 1
                pending_delta = False
            decision = record.decision
            if isinstance(decision, CallToolDecision):
                _note_tool_decision(
                    score,
                    decision.call.tool_name,
                    sufficient=sufficient,
                )
                pending_tool = {
                    "is_replan": is_replan,
                    "error_recovery": last_status in _FAILED_TOOL_STATUSES,
                    "satisfied": set(satisfied),
                    "contradicted": set(contradicted),
                }
            elif isinstance(decision, EvaluateRulesDecision):
                appropriate = _note_rule_decision(
                    score,
                    success_evidence_ids,
                    seen_rule_states,
                )
                rule_decisions += 1
                if is_replan:
                    _note_replan(score, appropriate)
            elif isinstance(decision, RetrieveKnowledgeDecision):
                pending_tool = None
                score.pending_knowledge_replan = is_replan
            elif isinstance(decision, FinishDecision):
                pending_tool = None
                appropriate = sufficient or last_status in _FAILED_TOOL_STATUSES
                if is_replan:
                    _note_replan(score, appropriate)
        elif isinstance(event, ObservationEvent):
            if pending_tool is not None:
                failed = event.observation.status in _FAILED_TOOL_STATUSES
                advanced = False
                if not failed:
                    advanced = _advances_viable_set(
                        case,
                        event.evidence,
                        satisfied=pending_tool["satisfied"],  # type: ignore[arg-type]
                        contradicted=pending_tool["contradicted"],  # type: ignore[arg-type]
                    )
                error_recovery = bool(pending_tool["error_recovery"])
                if not failed and not advanced and not error_recovery:
                    score.unnecessary_tool_actions += 1
                    score.failure_codes.append(FAILURE_UNNECESSARY_TOOL)
                if pending_tool["is_replan"]:
                    _note_replan(score, failed or advanced or error_recovery)
                pending_tool = None
            if event.observation.status == "success":
                _apply_evidence(case, event.evidence, satisfied, contradicted)
                success_evidence_ids.extend(
                    item.evidence_id for item in event.evidence
                )
                sufficient = _any_sufficient(case, satisfied, contradicted)
            last_status = event.observation.status
            pending_delta = True
        elif isinstance(event, RuleEvaluationEvent):
            pending_delta = True
        elif isinstance(event, KnowledgeRetrievalEvent):
            retrievals.append(event.retrieval)
            _score_one_retrieval(score, event.retrieval, claims)
            if score.pending_knowledge_replan:
                relevant = _retrieval_relevant(case, event.retrieval)
                appropriate = case.knowledge_policy != "not_needed" and relevant
                _note_replan(score, appropriate)
            score.pending_knowledge_replan = False
            pending_delta = True

    if success_evidence_ids and score.correct_rule_actions == 0:
        score.failure_codes.append(FAILURE_OMITTED_RULE)
        if rule_decisions == 0:
            score.rule_action_opportunities += 1

    _finalize_knowledge(case, score, retrievals)
    return score


def _score_baseline_path(
    case: EvaluationCase,
    trace: EvaluationTrace,
    score: _PathScore,
) -> None:
    satisfied: set[str] = set()
    contradicted: set[str] = set()
    sufficient = False
    success_evidence_ids: list[str] = []
    seen_rule_states: set[frozenset[str]] = set()
    last_status: ToolStatus | None = None
    for event in trace.events:
        if isinstance(event, ObservationEvent):
            score.tool_actions += 1
            if score.first_dsp_tool is None:
                score.first_dsp_tool = event.observation.tool_name
            if sufficient:
                score.timely_stop = False
                score.failure_codes.append(FAILURE_LATE_TOOL)
            status = event.observation.status
            failed = status in _FAILED_TOOL_STATUSES
            error_recovery = last_status in _FAILED_TOOL_STATUSES
            if not failed:
                advanced = _advances_viable_set(
                    case,
                    event.evidence,
                    satisfied=satisfied,
                    contradicted=contradicted,
                )
                if not advanced and not error_recovery:
                    score.unnecessary_tool_actions += 1
                    score.failure_codes.append(FAILURE_UNNECESSARY_TOOL)
                _apply_evidence(case, event.evidence, satisfied, contradicted)
                success_evidence_ids.extend(
                    item.evidence_id for item in event.evidence
                )
                sufficient = _any_sufficient(case, satisfied, contradicted)
            last_status = status
        elif isinstance(event, RuleEvaluationEvent):
            _note_rule_decision(score, success_evidence_ids, seen_rule_states)
    if success_evidence_ids and score.correct_rule_actions == 0:
        score.failure_codes.append(FAILURE_OMITTED_RULE)
        if score.rule_action_opportunities == 0:
            score.rule_action_opportunities += 1


def _note_tool_decision(
    score: _PathScore,
    tool_name: ToolName,
    *,
    sufficient: bool,
) -> None:
    score.tool_actions += 1
    if score.first_dsp_tool is None and tool_name in _DSP_TOOLS:
        score.first_dsp_tool = tool_name
    if sufficient:
        score.timely_stop = False
        score.failure_codes.append(FAILURE_LATE_TOOL)


def _note_rule_decision(
    score: _PathScore,
    success_evidence_ids: list[str],
    seen_rule_states: set[frozenset[str]],
) -> bool:
    score.rule_action_opportunities += 1
    state = frozenset(success_evidence_ids)
    if not success_evidence_ids:
        score.failure_codes.append(FAILURE_PREMATURE_RULE)
        return False
    if state in seen_rule_states:
        score.failure_codes.append(FAILURE_REDUNDANT_RULE)
        return False
    seen_rule_states.add(state)
    score.correct_rule_actions += 1
    return True


def _note_replan(score: _PathScore, appropriate: bool) -> None:
    if appropriate:
        score.appropriate_replans += 1
        return
    score.failure_codes.append(FAILURE_INAPPROPRIATE_REPLAN)


def _score_one_retrieval(
    score: _PathScore,
    retrieval: KnowledgeRetrievalResult,
    claims: tuple[DiagnosisClaim, ...],
) -> None:
    score.knowledge_actions += 1
    cited = {ref for claim in claims for ref in claim.knowledge_refs}
    if retrieval.retrieval_id in cited:
        score.cited_knowledge_actions += 1
    else:
        score.failure_codes.append(FAILURE_UNCITED_KNOWLEDGE)


def _finalize_knowledge(
    case: EvaluationCase,
    score: _PathScore,
    retrievals: list[KnowledgeRetrievalResult],
) -> None:
    if case.knowledge_policy == "required":
        score.required_knowledge_opportunities = 1
    seen: set[frozenset[str]] = set()
    non_duplicate_relevant = False
    for retrieval in retrievals:
        tags = frozenset(_normalize_tags(retrieval.query_tags))
        relevant = _retrieval_relevant(case, retrieval)
        duplicate = tags in seen
        if not duplicate:
            seen.add(tags)
        if relevant and not duplicate:
            non_duplicate_relevant = True
        if case.knowledge_policy == "not_needed":
            score.unnecessary_knowledge_actions += 1
            score.failure_codes.append(FAILURE_UNNECESSARY_KNOWLEDGE)
        elif not relevant:
            score.unnecessary_knowledge_actions += 1
            score.failure_codes.append(FAILURE_IRRELEVANT_TAGS)
            score.failure_codes.append(FAILURE_UNNECESSARY_KNOWLEDGE)
    if case.knowledge_policy == "required":
        if non_duplicate_relevant:
            score.required_knowledge_actions = 1
        else:
            score.failure_codes.append(FAILURE_REQUIRED_KNOWLEDGE_OMITTED)


def _retrieval_relevant(
    case: EvaluationCase, retrieval: KnowledgeRetrievalResult
) -> bool:
    wanted = set(_normalize_tags(case.knowledge_tags))
    got = set(_normalize_tags(retrieval.query_tags))
    return bool(wanted and got & wanted)


def _normalize_tags(tags: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(tag.strip() for tag in tags if tag.strip())


def _advances_viable_set(
    case: EvaluationCase,
    evidence: tuple[Evidence, ...],
    *,
    satisfied: set[str],
    contradicted: set[str],
) -> bool:
    unsatisfied = _viable_unsatisfied(case, satisfied, contradicted)
    for item in evidence:
        for condition in case.observable_conditions:
            if condition.condition_id in unsatisfied and _condition_matches(
                condition, item
            ):
                return True
    return False


def _viable_unsatisfied(
    case: EvaluationCase,
    satisfied: set[str],
    contradicted: set[str],
) -> set[str]:
    pending: set[str] = set()
    for evidence_set in case.sufficient_evidence_sets:
        if any(ref in contradicted for ref in evidence_set.condition_refs):
            continue
        for ref in evidence_set.condition_refs:
            if ref not in satisfied:
                pending.add(ref)
    return pending


def _apply_evidence(
    case: EvaluationCase,
    evidence: tuple[Evidence, ...],
    satisfied: set[str],
    contradicted: set[str],
) -> None:
    for item in evidence:
        for condition in case.observable_conditions:
            if _condition_matches(condition, item):
                satisfied.add(condition.condition_id)
            if _contradicts(condition, item):
                contradicted.add(condition.condition_id)


def _any_sufficient(
    case: EvaluationCase,
    satisfied: set[str],
    contradicted: set[str],
) -> bool:
    for evidence_set in case.sufficient_evidence_sets:
        if any(ref in contradicted for ref in evidence_set.condition_refs):
            continue
        if all(ref in satisfied for ref in evidence_set.condition_refs):
            return True
    return False


def _condition_matches(condition: EvidenceCondition, evidence: Evidence) -> bool:
    if evidence.source_tool != condition.tool_name:
        return False
    if evidence.metric != condition.metric:
        return False
    if evidence.validity != condition.validity:
        return False
    if type(evidence.value) is not type(condition.expected_value):
        return False
    if evidence.unit != condition.unit:
        return False
    return bool(
        _COMPARATORS[condition.comparator](evidence.value, condition.expected_value)
    )


def _contradicts(condition: EvidenceCondition, evidence: Evidence) -> bool:
    if evidence.validity != "valid":
        return False
    if evidence.source_tool != condition.tool_name:
        return False
    if evidence.metric != condition.metric:
        return False
    if type(evidence.value) is not type(condition.expected_value):
        return False
    if evidence.unit != condition.unit:
        return False
    return not bool(
        _COMPARATORS[condition.comparator](evidence.value, condition.expected_value)
    )


def _fault_counts(
    case: EvaluationCase,
    claims: tuple[DiagnosisClaim, ...],
) -> tuple[tuple[CausalFault, ...], int, int]:
    expected = set(case.causal_faults)
    predicted_types = [
        claim.fault_type for claim in claims if claim.fault_type in _CAUSAL_FAULTS
    ]
    predicted_faults = tuple(
        fault for fault in _CAUSAL_FAULTS if fault in predicted_types
    )
    unsupported = sum(1 for fault in predicted_types if fault not in expected)
    return predicted_faults, len(predicted_types), unsupported


def _ground_claims(
    case: EvaluationCase,
    trace: EvaluationTrace,
    claims: tuple[DiagnosisClaim, ...],
) -> tuple[int, int, list[str]]:
    evidence_ids: set[str] = set()
    evidence_by_id: dict[str, Evidence] = {}
    rule_ids: set[str] = set()
    knowledge_ids: set[str] = set()
    for event in trace.events:
        if isinstance(event, ObservationEvent):
            for item in event.evidence:
                evidence_ids.add(item.evidence_id)
                evidence_by_id[item.evidence_id] = item
        elif isinstance(event, RuleEvaluationEvent):
            for evaluation in event.batch.evaluations:
                rule_ids.add(evaluation.evaluation_id)
        elif isinstance(event, KnowledgeRetrievalEvent):
            knowledge_ids.add(event.retrieval.retrieval_id)
    grounded = 0
    failures: list[str] = []
    for claim in claims:
        refs_ok = (
            all(ref in evidence_ids for ref in claim.evidence_refs)
            and all(ref in rule_ids for ref in claim.rule_refs)
            and all(ref in knowledge_ids for ref in claim.knowledge_refs)
        )
        supported = False
        if refs_ok:
            for ref in claim.evidence_refs:
                cited = evidence_by_id.get(ref)
                if cited is None:
                    continue
                for condition in case.observable_conditions:
                    if (
                        _condition_matches(condition, cited)
                        and claim.fault_type in condition.supports_claims
                    ):
                        supported = True
                        break
                if supported:
                    break
        if refs_ok and supported:
            grounded += 1
        else:
            failures.append(FAILURE_UNGROUNDED)
    return grounded, len(claims), failures


def _completion_reason(
    trace: EvaluationTrace,
) -> TerminationReason | BaselineCompletionReason:
    result = trace.result
    if isinstance(result, BaselineRunResult):
        return result.completion_reason
    return result.termination_reason


def _unique(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))
