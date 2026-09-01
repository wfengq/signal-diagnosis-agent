"""Additive external WAV validity study scoring (signal_diag.external_scoring 1.0.0)."""

from __future__ import annotations

import operator
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from signal_diag.agent.models import (
    CallToolDecision,
    DiagnosisClaim,
)
from signal_diag.evaluation.external.models import (
    ExternalAggregate,
    ExternalCase,
    ExternalRunScore,
    ExternalStratum,
    ExternalStratumMetric,
    ExternalTargetStatus,
    ReviewAgreement,
)
from signal_diag.evaluation.models import (
    AttemptRecord,
    CausalFault,
    EvaluationTrace,
    EvidenceCondition,
    KnowledgeRetrievalEvent,
    ObservationEvent,
    PlannerDecisionEvent,
    RateMetric,
    RuleEvaluationEvent,
)
from signal_diag.tools.contracts import ToolName
from signal_diag.tools.evidence import Evidence

EXTERNAL_SCORING_ID = "signal_diag.external_scoring"
EXTERNAL_SCORING_VERSION = "1.0.0"

_SCOREABLE_CONFIDENCE = frozenset({"strong_ground_truth", "reference_supported"})
_UNSCORED_CONFIDENCE = frozenset({"weak_observation", "unknown"})
_CAUSAL_FAULTS: tuple[CausalFault, ...] = ("clipping", "harmonic_distortion")
_DSP_TOOLS: frozenset[str] = frozenset(
    {
        "detect_clipping",
        "analyze_spectrum",
        "estimate_fundamental",
        "analyze_harmonic_distortion",
    }
)
_FAILED_TOOL_STATUSES = frozenset({"error", "invalid"})
_COMPARATORS = {
    "eq": operator.eq,
    "neq": operator.ne,
    "lt": operator.lt,
    "lte": operator.le,
    "gt": operator.gt,
    "gte": operator.ge,
}

_OUTCOME_ACCURACY_MIN = 0.80
_CAUSAL_EXACT_SET_ACCURACY_MIN = 0.75
_CAUSAL_MACRO_F1_MIN = 0.75
_EVIDENCE_GROUNDING_TARGET = 1.0
_UNSUPPORTED_CLAIM_RATE_TARGET = 0.0
_UNNECESSARY_TOOL_ACTION_RATE_MAX = 0.20
_INCONCLUSIVE_APPROPRIATENESS_MIN = 5
_INCONCLUSIVE_APPROPRIATENESS_DENOMINATOR = 6
_RAW_OUTCOME_AGREEMENT_MIN = 0.85
_OUTCOME_KAPPA_MIN = 0.70
_CONFIDENCE_KAPPA_MIN = 0.70


@dataclass
class _PathScore:
    first_dsp_tool: ToolName | None = None
    unnecessary_tool_actions: int = 0
    tool_actions: int = 0
    pending_knowledge_replan: bool = False


def score_external_trace(
    case: ExternalCase,
    trace: EvaluationTrace,
) -> ExternalRunScore:
    diagnosis = trace.result.diagnosis
    claims = diagnosis.claims if diagnosis is not None else ()
    predicted_outcome = diagnosis.outcome if diagnosis is not None else None
    predicted_faults, predicted_fault_claims, _unsupported_claims = _fault_counts(
        case, claims
    )
    grounded, scored, unsupported_same_run = _ground_claims(case, trace, claims)
    evidence_grounding = _rate(grounded, scored) if scored else None
    path = _score_path(case, trace)
    scoreable = case.confidence in _SCOREABLE_CONFIDENCE

    outcome_correct: bool | None
    causal_exact_set_correct: bool | None
    positive_causal_claim_on_unscored: bool | None
    inconclusive_appropriate: bool | None

    if scoreable:
        outcome_correct = (
            predicted_outcome is not None
            and predicted_outcome in case.acceptable_outcomes
        )
        causal_exact_set_correct = predicted_faults == case.causal_faults
        positive_causal_claim_on_unscored = None
        if (
            case.confidence == "reference_supported"
            and case.external_class == "inconclusive"
        ):
            inconclusive_appropriate = outcome_correct
        else:
            inconclusive_appropriate = None
    else:
        outcome_correct = None
        causal_exact_set_correct = None
        positive_causal_claim_on_unscored = predicted_fault_claims > 0
        inconclusive_appropriate = None

    return ExternalRunScore(
        trace_id=trace.trace_id,
        case_id=case.case_id,
        execution_path=trace.execution_path,
        external_scoring_id=EXTERNAL_SCORING_ID,  # type: ignore[arg-type]
        external_scoring_version=EXTERNAL_SCORING_VERSION,  # type: ignore[arg-type]
        outcome_correct=outcome_correct,
        causal_exact_set_correct=causal_exact_set_correct,
        expected_faults=case.causal_faults if scoreable else (),
        predicted_faults=predicted_faults,
        predicted_outcome=predicted_outcome,
        predicted_fault_claims=predicted_fault_claims,
        evidence_grounding=evidence_grounding,
        unsupported_same_run_claims=unsupported_same_run,
        positive_causal_claim_on_unscored=positive_causal_claim_on_unscored,
        unnecessary_tool_actions=path.unnecessary_tool_actions,
        tool_actions=path.tool_actions,
        inconclusive_appropriate=inconclusive_appropriate,
    )


def aggregate_external_scores(
    cases: tuple[ExternalCase, ...],
    scores: tuple[ExternalRunScore, ...],
    attempts: tuple[AttemptRecord, ...],
) -> ExternalAggregate:
    case_by_id = {case.case_id: case for case in cases}
    _validate_aggregate_inputs(case_by_id, scores, attempts)

    scoreable = tuple(
        score
        for score in scores
        if case_by_id[score.case_id].confidence in _SCOREABLE_CONFIDENCE
    )
    unscored = tuple(
        score
        for score in scores
        if case_by_id[score.case_id].confidence in _UNSCORED_CONFIDENCE
    )
    inconclusive_scores = tuple(
        score
        for score in scoreable
        if case_by_id[score.case_id].external_class == "inconclusive"
        and case_by_id[score.case_id].confidence == "reference_supported"
    )

    outcome_accuracy = _boolean_rate(
        scoreable,
        lambda score: score.outcome_correct is True,
        lambda score: score.outcome_correct is not None,
    )
    causal_exact_set_accuracy = _boolean_rate(
        scoreable,
        lambda score: score.causal_exact_set_correct is True,
        lambda score: score.causal_exact_set_correct is not None,
    )
    evidence_grounding = _sum_rate_metrics(scores, "evidence_grounding")
    unsupported_same_run_claim_rate = _rate(
        sum(score.unsupported_same_run_claims for score in scores),
        sum(score.predicted_fault_claims for score in scores),
    )
    unnecessary_tool_action_rate = _rate(
        sum(score.unnecessary_tool_actions for score in scores),
        sum(score.tool_actions for score in scores),
    )
    inconclusive_appropriateness = _boolean_rate(
        inconclusive_scores,
        lambda score: score.inconclusive_appropriate is True,
        lambda score: score.inconclusive_appropriate is not None,
    )
    positive_causal_claims_on_unscored = _boolean_rate(
        unscored,
        lambda score: score.positive_causal_claim_on_unscored is True,
        lambda score: score.positive_causal_claim_on_unscored is not None,
    )
    scoreable_coverage = _rate(len(scoreable), len(scores))

    strata = _build_strata(cases, scores, case_by_id)
    master_cluster_summaries = _build_master_cluster_summaries(cases, scores, case_by_id)

    return ExternalAggregate(
        external_scoring_id=EXTERNAL_SCORING_ID,  # type: ignore[arg-type]
        external_scoring_version=EXTERNAL_SCORING_VERSION,  # type: ignore[arg-type]
        outcome_accuracy=outcome_accuracy,
        causal_exact_set_accuracy=causal_exact_set_accuracy,
        causal_macro_f1=_causal_macro_f1(scoreable),
        clipping_precision=_per_label_precision(scoreable, "clipping"),
        clipping_recall=_per_label_recall(scoreable, "clipping"),
        harmonic_precision=_per_label_precision(scoreable, "harmonic_distortion"),
        harmonic_recall=_per_label_recall(scoreable, "harmonic_distortion"),
        evidence_grounding=evidence_grounding,
        unsupported_same_run_claim_rate=unsupported_same_run_claim_rate,
        unnecessary_tool_action_rate=unnecessary_tool_action_rate,
        inconclusive_appropriateness=inconclusive_appropriateness,
        positive_causal_claims_on_unscored=positive_causal_claims_on_unscored,
        scoreable_coverage=scoreable_coverage,
        strata=strata,
        master_cluster_summaries=master_cluster_summaries,
    )


def evaluate_external_targets(
    aggregate: ExternalAggregate,
    review: ReviewAgreement,
) -> ExternalTargetStatus:
    required = (
        aggregate.outcome_accuracy,
        aggregate.causal_exact_set_accuracy,
        aggregate.causal_macro_f1,
        aggregate.evidence_grounding,
        aggregate.unsupported_same_run_claim_rate,
        aggregate.unnecessary_tool_action_rate,
        aggregate.inconclusive_appropriateness,
    )
    if any(item is None for item in required):
        return "not_evaluated"

    assert aggregate.outcome_accuracy is not None
    assert aggregate.causal_exact_set_accuracy is not None
    assert aggregate.causal_macro_f1 is not None
    assert aggregate.evidence_grounding is not None
    assert aggregate.unsupported_same_run_claim_rate is not None
    assert aggregate.unnecessary_tool_action_rate is not None
    assert aggregate.inconclusive_appropriateness is not None

    checks = [
        aggregate.outcome_accuracy.value >= _OUTCOME_ACCURACY_MIN,
        aggregate.causal_exact_set_accuracy.value >= _CAUSAL_EXACT_SET_ACCURACY_MIN,
        aggregate.causal_macro_f1 >= _CAUSAL_MACRO_F1_MIN,
        aggregate.evidence_grounding.value == _EVIDENCE_GROUNDING_TARGET,
        aggregate.unsupported_same_run_claim_rate.value
        == _UNSUPPORTED_CLAIM_RATE_TARGET,
        aggregate.unnecessary_tool_action_rate.value
        <= _UNNECESSARY_TOOL_ACTION_RATE_MAX,
        aggregate.inconclusive_appropriateness.numerator
        >= _INCONCLUSIVE_APPROPRIATENESS_MIN,
        aggregate.inconclusive_appropriateness.denominator
        >= _INCONCLUSIVE_APPROPRIATENESS_DENOMINATOR,
    ]
    if review.evaluation_status == "not_evaluated":
        pass
    elif review.raw_outcome_agreement is not None:
        checks.append(review.raw_outcome_agreement >= _RAW_OUTCOME_AGREEMENT_MIN)
    if review.outcome_cohen_kappa is not None:
        checks.append(review.outcome_cohen_kappa >= _OUTCOME_KAPPA_MIN)
    if review.confidence_quadratic_kappa is not None:
        checks.append(review.confidence_quadratic_kappa >= _CONFIDENCE_KAPPA_MIN)

    return "meets_target" if all(checks) else "below_target"


def _validate_aggregate_inputs(
    case_by_id: dict[str, ExternalCase],
    scores: tuple[ExternalRunScore, ...],
    attempts: tuple[AttemptRecord, ...],
) -> None:
    seen: set[tuple[str, str, int]] = set()
    for score in scores:
        if score.case_id not in case_by_id:
            raise ValueError(f"foreign case_id: {score.case_id}")
        key = (score.execution_path, score.case_id, 1)
        if key in seen:
            raise ValueError(
                f"duplicate (execution_path, case_id, run_slot): {key}"
            )
        seen.add(key)
    for attempt in attempts:
        if attempt.case_id not in case_by_id and not attempt.case_id.startswith(
            "case_"
        ):
            raise ValueError(f"foreign case_id: {attempt.case_id}")


def _score_path(case: ExternalCase, trace: EvaluationTrace) -> _PathScore:
    score = _PathScore()
    if trace.execution_path == "fixed_pipeline":
        _score_baseline_path(case, trace, score)
        return score

    satisfied: set[str] = set()
    contradicted: set[str] = set()
    pending_tool: dict[str, object] | None = None
    last_status: str | None = None
    sufficient = False

    for event in trace.events:
        if isinstance(event, PlannerDecisionEvent):
            record = event.record
            if record.status != "decision" or record.decision is None:
                continue
            if pending_tool is not None:
                score.unnecessary_tool_actions += 1
                pending_tool = None
            decision = record.decision
            if isinstance(decision, CallToolDecision):
                pending_tool = {
                    "satisfied": set(satisfied),
                    "contradicted": set(contradicted),
                    "error_recovery": last_status in _FAILED_TOOL_STATUSES,
                }
        elif isinstance(event, ObservationEvent):
            score.tool_actions += 1
            tool_name = event.observation.tool_name
            if score.first_dsp_tool is None and tool_name in _DSP_TOOLS:
                score.first_dsp_tool = tool_name
            if sufficient:
                pass
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
                pending_tool = None
            if event.observation.status == "success":
                _apply_evidence(case, event.evidence, satisfied, contradicted)
                sufficient = _any_sufficient(case, satisfied, contradicted)
            last_status = event.observation.status
        elif isinstance(event, KnowledgeRetrievalEvent):
            pending_tool = None

    if pending_tool is not None:
        score.unnecessary_tool_actions += 1
    return score


def _score_baseline_path(
    case: ExternalCase,
    trace: EvaluationTrace,
    score: _PathScore,
) -> None:
    satisfied: set[str] = set()
    contradicted: set[str] = set()
    sufficient = False
    for event in trace.events:
        if isinstance(event, ObservationEvent):
            score.tool_actions += 1
            if score.first_dsp_tool is None:
                score.first_dsp_tool = event.observation.tool_name
            if sufficient:
                score.unnecessary_tool_actions += 1
            if event.observation.status == "success":
                _apply_evidence(case, event.evidence, satisfied, contradicted)
                sufficient = _any_sufficient(case, satisfied, contradicted)


def _fault_counts(
    case: ExternalCase,
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
    case: ExternalCase,
    trace: EvaluationTrace,
    claims: tuple[DiagnosisClaim, ...],
) -> tuple[int, int, int]:
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
    unsupported_same_run = 0
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
        elif claim.fault_type in _CAUSAL_FAULTS:
            unsupported_same_run += 1
    return grounded, len(claims), unsupported_same_run


def _apply_evidence(
    case: ExternalCase,
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
    case: ExternalCase,
    satisfied: set[str],
    contradicted: set[str],
) -> bool:
    for evidence_set in case.sufficient_evidence_sets:
        if any(ref in contradicted for ref in evidence_set.condition_refs):
            continue
        if all(ref in satisfied for ref in evidence_set.condition_refs):
            return True
    return False


def _advances_viable_set(
    case: ExternalCase,
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
    case: ExternalCase,
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


def _rate(numerator: int, denominator: int) -> RateMetric:
    if denominator == 0:
        return RateMetric(numerator=0, denominator=0, value=0.0)
    return RateMetric(
        numerator=numerator,
        denominator=denominator,
        value=numerator / denominator,
    )


def _boolean_rate(
    scores: Sequence[ExternalRunScore],
    is_true: Callable[[ExternalRunScore], bool],
    is_eligible: Callable[[ExternalRunScore], bool],
) -> RateMetric | None:
    eligible = [score for score in scores if is_eligible(score)]
    if not eligible:
        return None
    numerator = sum(1 for score in eligible if is_true(score))
    return _rate(numerator, len(eligible))


def _sum_rate_metrics(
    scores: Sequence[ExternalRunScore],
    field: str,
) -> RateMetric | None:
    numerator = 0
    denominator = 0
    for score in scores:
        metric = getattr(score, field)
        if metric is None:
            continue
        numerator += metric.numerator
        denominator += metric.denominator
    if denominator == 0:
        return None
    return _rate(numerator, denominator)


def _causal_macro_f1(scores: Sequence[ExternalRunScore]) -> float | None:
    if not scores:
        return None
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


def _per_label_precision(
    scores: Sequence[ExternalRunScore],
    label: CausalFault,
) -> RateMetric | None:
    tp = fp = 0
    for score in scores:
        predicted = label in score.predicted_faults
        expected = label in score.expected_faults
        if predicted and expected:
            tp += 1
        elif predicted:
            fp += 1
    denominator = tp + fp
    if denominator == 0:
        return None
    return _rate(tp, denominator)


def _per_label_recall(
    scores: Sequence[ExternalRunScore],
    label: CausalFault,
) -> RateMetric | None:
    tp = fn = 0
    for score in scores:
        predicted = label in score.predicted_faults
        expected = label in score.expected_faults
        if predicted and expected:
            tp += 1
        elif expected:
            fn += 1
    denominator = tp + fn
    if denominator == 0:
        return None
    return _rate(tp, denominator)


def _build_strata(
    cases: tuple[ExternalCase, ...],
    scores: tuple[ExternalRunScore, ...],
    case_by_id: dict[str, ExternalCase],
) -> tuple[ExternalStratum, ...]:
    score_by_case = {score.case_id: score for score in scores}
    grouped: dict[tuple[str, str], list[ExternalRunScore]] = defaultdict(list)

    for case in cases:
        score = score_by_case.get(case.case_id)
        if score is None:
            continue
        dimensions = {
            "execution_path": score.execution_path,
            "source_group": case.source_group,
            "confidence": case.confidence,
            "external_class": case.external_class,
            "source_recording_key": case.source_recording_key,
            "capture_configuration_key": case.capture_configuration_key,
            "parent_master_id": case.parent_master_id or "none",
        }
        for dimension, value in dimensions.items():
            grouped[(dimension, value)].append(score)

    strata: list[ExternalStratum] = []
    for (dimension, value), bucket in sorted(grouped.items()):
        metrics = _stratum_metrics(bucket, case_by_id)
        strata.append(
            ExternalStratum(
                dimension=dimension,  # type: ignore[arg-type]
                value=value,
                metrics=metrics,
            )
        )
    return tuple(strata)


def _build_master_cluster_summaries(
    cases: tuple[ExternalCase, ...],
    scores: tuple[ExternalRunScore, ...],
    case_by_id: dict[str, ExternalCase],
) -> tuple[ExternalStratum, ...]:
    score_by_case = {score.case_id: score for score in scores}
    clusters: dict[str, list[ExternalRunScore]] = defaultdict(list)
    for case in cases:
        if case.parent_master_id is None:
            continue
        score = score_by_case.get(case.case_id)
        if score is None:
            continue
        clusters[case.parent_master_id].append(score)

    summaries: list[ExternalStratum] = []
    for master_id, bucket in sorted(clusters.items()):
        metrics = _stratum_metrics(bucket, case_by_id)
        summaries.append(
            ExternalStratum(
                dimension="parent_master_id",
                value=master_id,
                metrics=metrics,
            )
        )
    return tuple(summaries)


def _stratum_metrics(
    scores: Sequence[ExternalRunScore],
    case_by_id: dict[str, ExternalCase],
) -> tuple[ExternalStratumMetric, ...]:
    scoreable = [
        score
        for score in scores
        if case_by_id[score.case_id].confidence in _SCOREABLE_CONFIDENCE
    ]
    unscored = [
        score
        for score in scores
        if case_by_id[score.case_id].confidence in _UNSCORED_CONFIDENCE
    ]
    exclusions = len(scores) - len(scoreable)

    def _metric(
        name: str,
        numerator: int,
        denominator: int,
        *,
        exclusions_count: int = 0,
    ) -> ExternalStratumMetric:
        value = None if denominator == 0 else numerator / denominator
        return ExternalStratumMetric(
            metric_name=name,
            numerator=numerator,
            denominator=denominator,
            exclusions=exclusions_count,
            value=value,
        )

    outcome_num = sum(1 for score in scoreable if score.outcome_correct is True)
    outcome_den = sum(1 for score in scoreable if score.outcome_correct is not None)
    grounding_num = sum(
        score.evidence_grounding.numerator
        for score in scores
        if score.evidence_grounding is not None
    )
    grounding_den = sum(
        score.evidence_grounding.denominator
        for score in scores
        if score.evidence_grounding is not None
    )
    positive_unscored_num = sum(
        1 for score in unscored if score.positive_causal_claim_on_unscored is True
    )

    return (
        _metric(
            "outcome_accuracy",
            outcome_num,
            outcome_den,
            exclusions_count=exclusions,
        ),
        _metric("evidence_grounding", grounding_num, grounding_den),
        _metric(
            "positive_causal_claims_on_unscored",
            positive_unscored_num,
            len(unscored),
        ),
    )
