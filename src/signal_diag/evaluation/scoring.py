"""Pure per-run and aggregate scoring over EvaluationTrace and EvaluationCase."""

from __future__ import annotations

import hashlib
import json
import operator
from math import ceil

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
    AggregateMetrics,
    AttemptRecord,
    BaselineCompletionReason,
    BaselineRunResult,
    BenchmarkConfig,
    BenchmarkReport,
    BenchmarkStatus,
    CausalFault,
    DatasetManifest,
    EvaluationCase,
    EvaluationTrace,
    EvidenceCondition,
    HarnessStatus,
    KnowledgeRetrievalEvent,
    ObservationEvent,
    PlannerDecisionEvent,
    RateMetric,
    RuleEvaluationEvent,
    RunScore,
    TargetBands,
    TargetStatus,
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


_SLOT_KEY = tuple[str, str, int]
_CONFIG_ERROR_CODES = frozenset(
    {
        "missing_credentials",
        "missing_dependency",
        "authentication",
        "invalid_configuration",
    }
)
_TARGET_RATE_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("first_tool_selection_rate", "first_tool_selection_min", "min"),
    ("observation_driven_replan_rate", "observation_driven_replan_min", "min"),
    ("evidence_grounding_rate", "evidence_grounding_min", "min"),
    ("unsupported_claim_rate", "unsupported_claim_rate_max", "max"),
    ("unnecessary_tool_action_rate", "unnecessary_tool_action_rate_max", "max"),
    ("timely_stopping_rate", "timely_stopping_min", "min"),
    ("applicable_rule_usage_rate", "applicable_rule_usage_min", "min"),
    ("required_knowledge_usage_rate", "required_knowledge_usage_min", "min"),
    ("knowledge_citation_utilization_rate", "knowledge_citation_utilization_min", "min"),
    ("unnecessary_knowledge_retrieval_rate", "unnecessary_knowledge_retrieval_rate_max", "max"),
)


def aggregate_benchmark(
    manifest: DatasetManifest,
    traces: tuple[EvaluationTrace, ...],
    scores: tuple[RunScore, ...],
    attempts: tuple[AttemptRecord, ...],
    config: BenchmarkConfig,
    targets: TargetBands,
    *,
    harness_status: HarnessStatus,
) -> BenchmarkReport:
    cases = _validate_aggregate_inputs(manifest, traces, scores, attempts, config)
    agent_scores = _held_out_scores(scores, cases, "agent")
    baseline_scores = _held_out_scores(scores, cases, "fixed_pipeline")
    agent_metrics = _aggregate_metrics(agent_scores, attempts, planner_applicable=True)
    baseline_metrics = _aggregate_metrics(
        baseline_scores, attempts, planner_applicable=False
    )
    status = _benchmark_status(manifest, config, cases, scores, attempts)
    target_status, warnings = _target_status(status, agent_metrics, targets)
    return BenchmarkReport(
        config=config,
        config_fingerprint_sha256=_config_fingerprint(config),
        manifest=manifest,
        harness_status=harness_status,
        benchmark_status=status,
        target_status=target_status,
        targets=targets,
        agent_metrics=agent_metrics,
        baseline_metrics=baseline_metrics,
        scores=scores,
        traces=traces,
        attempts=attempts,
        warnings=warnings,
    )


def _config_fingerprint(config: BenchmarkConfig) -> str:
    payload = config.model_dump(mode="json", exclude={"benchmark_id", "started_at_utc"})
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _rate(numerator: int, denominator: int) -> RateMetric:
    value = 0.0 if denominator == 0 else numerator / denominator
    return RateMetric(numerator=numerator, denominator=denominator, value=value)


def _slot_key(item: EvaluationTrace | RunScore | AttemptRecord) -> _SLOT_KEY:
    return (item.execution_path, item.case_id, item.run_slot)


def _validate_aggregate_inputs(
    manifest: DatasetManifest,
    traces: tuple[EvaluationTrace, ...],
    scores: tuple[RunScore, ...],
    attempts: tuple[AttemptRecord, ...],
    config: BenchmarkConfig,
) -> dict[str, EvaluationCase]:
    if (
        config.dataset_id != manifest.dataset_id
        or config.dataset_version != manifest.version
        or config.rule_profile_id != manifest.rule_profile_id
        or config.rule_profile_version != manifest.rule_profile_version
    ):
        raise ValueError("foreign dataset/configuration")
    cases = {case.case_id: case for case in manifest.cases}
    _reject_duplicate_slots(traces)
    _reject_duplicate_slots(scores)
    trace_by_id = {}
    for trace in traces:
        if trace.case_id not in cases:
            raise ValueError(f"foreign case_id: {trace.case_id}")
        if trace.config != config:
            raise ValueError("foreign dataset/configuration")
        if trace.trace_id in trace_by_id:
            raise ValueError(f"duplicate trace_id: {trace.trace_id}")
        trace_by_id[trace.trace_id] = trace
    if len(traces) != len(scores):
        raise ValueError("trace/score mismatch")
    scored_ids: set[str] = set()
    for score in scores:
        if score.case_id not in cases:
            raise ValueError(f"foreign case_id: {score.case_id}")
        matched = trace_by_id.get(score.trace_id)
        if matched is None:
            raise ValueError(f"trace/score mismatch: unknown trace_id {score.trace_id}")
        if _slot_key(score) != _slot_key(matched):
            raise ValueError("trace/score mismatch")
        scored_ids.add(score.trace_id)
    if scored_ids != set(trace_by_id):
        raise ValueError("trace/score mismatch")
    for attempt in attempts:
        if attempt.case_id not in cases:
            raise ValueError(f"foreign case_id: {attempt.case_id}")
    return cases


def _reject_duplicate_slots(
    items: tuple[EvaluationTrace, ...] | tuple[RunScore, ...],
) -> None:
    seen: set[_SLOT_KEY] = set()
    for item in items:
        key = _slot_key(item)
        if key in seen:
            raise ValueError(f"duplicate (execution_path, case_id, run_slot): {key}")
        seen.add(key)


def _held_out_scores(
    scores: tuple[RunScore, ...],
    cases: dict[str, EvaluationCase],
    execution_path: str,
) -> tuple[RunScore, ...]:
    return tuple(
        score
        for score in scores
        if score.execution_path == execution_path
        and cases[score.case_id].split == "held_out"
    )


def _aggregate_metrics(
    scores: tuple[RunScore, ...],
    attempts: tuple[AttemptRecord, ...],
    *,
    planner_applicable: bool,
) -> AggregateMetrics | None:
    if not scores:
        return None
    run_count = len(scores)
    first_true = sum(score.first_tool_correct is True for score in scores)
    first_den = sum(score.first_tool_correct is not None for score in scores)
    timely_true = sum(score.timely_stop is True for score in scores)
    timely_den = sum(score.timely_stop is not None for score in scores)
    mean_latency, p50, p95 = _latency_stats(scores, attempts)
    covered = tuple(
        score.provider_usage for score in scores if score.provider_usage is not None
    )
    input_tokens, output_tokens, total_tokens, cost_usd = _usage_totals(covered)
    planner_calls: float | None
    if planner_applicable:
        planner_calls = sum(score.planner_calls for score in scores) / run_count
    else:
        planner_calls = None
    return AggregateMetrics(
        run_count=run_count,
        causal_exact_set_accuracy=_rate(
            sum(score.causal_exact_set_correct for score in scores), run_count
        ),
        causal_macro_f1=_causal_macro_f1(scores),
        outcome_accuracy=_rate(sum(score.outcome_correct for score in scores), run_count),
        evidence_grounding_rate=_rate(
            sum(score.grounded_claims for score in scores),
            sum(score.scored_claims for score in scores),
        ),
        unsupported_claim_rate=_rate(
            sum(score.unsupported_fault_claims for score in scores),
            sum(score.predicted_fault_claims for score in scores),
        ),
        first_tool_selection_rate=_rate(first_true, first_den),
        observation_driven_replan_rate=_rate(
            sum(score.appropriate_replans for score in scores),
            sum(score.replan_opportunities for score in scores),
        ),
        unnecessary_tool_action_rate=_rate(
            sum(score.unnecessary_tool_actions for score in scores),
            sum(score.tool_actions for score in scores),
        ),
        timely_stopping_rate=_rate(timely_true, timely_den),
        applicable_rule_usage_rate=_rate(
            sum(score.correct_rule_actions for score in scores),
            sum(score.rule_action_opportunities for score in scores),
        ),
        required_knowledge_usage_rate=_rate(
            sum(score.required_knowledge_actions for score in scores),
            sum(score.required_knowledge_opportunities for score in scores),
        ),
        unnecessary_knowledge_retrieval_rate=_rate(
            sum(score.unnecessary_knowledge_actions for score in scores),
            sum(score.knowledge_actions for score in scores),
        ),
        knowledge_citation_utilization_rate=_rate(
            sum(score.cited_knowledge_actions for score in scores),
            sum(score.knowledge_actions for score in scores),
        ),
        average_tool_actions=sum(score.tool_actions for score in scores) / run_count,
        average_planner_calls=planner_calls,
        latency_ms_mean=mean_latency,
        latency_ms_p50=p50,
        latency_ms_p95=p95,
        provider_usage_coverage_rate=_rate(len(covered), run_count),
        observed_input_tokens=input_tokens,
        observed_output_tokens=output_tokens,
        observed_total_tokens=total_tokens,
        observed_cost_usd=cost_usd,
    )


def _causal_macro_f1(scores: tuple[RunScore, ...]) -> float:
    f1_values: list[float] = []
    for label in _CAUSAL_FAULTS:
        tp = fp = fn = 0
        for score in scores:
            expected = label in score.expected_faults
            predicted = label in score.predicted_faults
            if expected and predicted:
                tp += 1
            elif predicted:
                fp += 1
            elif expected:
                fn += 1
        denominator = 2 * tp + fp + fn
        f1_values.append(0.0 if denominator == 0 else (2 * tp) / denominator)
    return (f1_values[0] + f1_values[1]) / 2


def _latency_stats(
    scores: tuple[RunScore, ...],
    attempts: tuple[AttemptRecord, ...],
) -> tuple[float | None, float | None, float | None]:
    wanted = {_slot_key(score) for score in scores}
    samples: list[float] = []
    seen: set[_SLOT_KEY] = set()
    for attempt in attempts:
        key = _slot_key(attempt)
        if key not in wanted or attempt.status != "behavior_result":
            continue
        if key in seen:
            continue
        seen.add(key)
        elapsed_ms = (
            attempt.finished_at_utc - attempt.started_at_utc
        ).total_seconds() * 1000.0
        samples.append(elapsed_ms)
    if not samples:
        return None, None, None
    return (
        sum(samples) / len(samples),
        _nearest_rank(samples, 0.50),
        _nearest_rank(samples, 0.95),
    )


def _nearest_rank(samples: list[float], percentile: float) -> float:
    ordered = sorted(samples)
    rank = ceil(percentile * len(ordered))
    return ordered[rank - 1]


def _usage_totals(
    covered: tuple[object, ...],
) -> tuple[int | None, int | None, int | None, float | None]:
    if not covered:
        return None, None, None, None
    return (
        _sum_optional_int(covered, "input_tokens"),
        _sum_optional_int(covered, "output_tokens"),
        _sum_optional_int(covered, "total_tokens"),
        _sum_optional_float(covered, "cost_usd"),
    )


def _sum_optional_int(items: tuple[object, ...], field: str) -> int | None:
    values = [getattr(item, field) for item in items if getattr(item, field) is not None]
    if not values:
        return None
    return int(sum(values))


def _sum_optional_float(items: tuple[object, ...], field: str) -> float | None:
    values = [getattr(item, field) for item in items if getattr(item, field) is not None]
    if not values:
        return None
    return float(sum(values))


def _benchmark_status(
    manifest: DatasetManifest,
    config: BenchmarkConfig,
    cases: dict[str, EvaluationCase],
    scores: tuple[RunScore, ...],
    attempts: tuple[AttemptRecord, ...],
) -> BenchmarkStatus:
    expected = {
        ("agent", case.case_id, slot)
        for case in manifest.cases
        if case.split == "held_out"
        for slot in range(1, config.repetitions + 1)
    }
    scored = {
        ("agent", score.case_id, score.run_slot)
        for score in scores
        if score.execution_path == "agent" and cases[score.case_id].split == "held_out"
    }
    if expected and expected <= scored:
        return "completed"
    has_behavior = bool(scored)
    has_config_block = any(
        attempt.status == "configuration_error"
        or attempt.error_code in _CONFIG_ERROR_CODES
        for attempt in attempts
    )
    if not has_behavior and (has_config_block or not attempts):
        return "pending"
    return "incomplete"


def _target_status(
    status: BenchmarkStatus,
    agent_metrics: AggregateMetrics | None,
    targets: TargetBands,
) -> tuple[TargetStatus, tuple[str, ...]]:
    warnings = _non_applicable_warnings(agent_metrics)
    if status != "completed":
        return "not_evaluated", warnings
    if agent_metrics is None:
        return "not_evaluated", warnings
    if _meets_applicable_targets(agent_metrics, targets):
        return "meets_target", warnings
    return "below_target", warnings


def _non_applicable_warnings(metrics: AggregateMetrics | None) -> tuple[str, ...]:
    if metrics is None:
        return ()
    warnings: list[str] = []
    for metric_name, _, _ in _TARGET_RATE_FIELDS:
        rate: RateMetric = getattr(metrics, metric_name)
        if rate.denominator == 0:
            warnings.append(
                f"{metric_name} is not applicable (zero denominator)"
            )
    return tuple(warnings)


def _meets_applicable_targets(metrics: AggregateMetrics, targets: TargetBands) -> bool:
    if metrics.causal_macro_f1 < targets.causal_macro_f1_min:
        return False
    for metric_name, band_name, direction in _TARGET_RATE_FIELDS:
        rate: RateMetric = getattr(metrics, metric_name)
        if rate.denominator == 0:
            continue
        threshold = getattr(targets, band_name)
        if direction == "min" and rate.value < threshold:
            return False
        if direction == "max" and rate.value > threshold:
            return False
    return True
