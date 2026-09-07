"""Contextual evaluation scoring with frozen denominators."""

from __future__ import annotations

from collections.abc import Sequence

from signal_diag.evaluation.contextual.models import (
    CONTEXTUAL_SCORING_VERSION,
    ArmKind,
    ArmResult,
    ContextualAggregate,
    ContextualCase,
    ContextualManifest,
    ContextualRunScore,
)
from signal_diag.evaluation.models import CausalFault, RateMetric

_SCOREABLE_DENOM = 17
_INCONCLUSIVE_DENOM = 6


def _rate(numerator: int, denominator: int) -> RateMetric:
    if denominator == 0:
        return RateMetric(numerator=0, denominator=0, value=0.0)
    return RateMetric(
        numerator=numerator,
        denominator=denominator,
        value=numerator / denominator,
    )


def _precision_or_na(tp: int, fp: int) -> RateMetric | str:
    denom = tp + fp
    if denom == 0:
        return "not_evaluated"
    return _rate(tp, denom)


def _recall_or_na(tp: int, fn: int) -> RateMetric | str:
    denom = tp + fn
    if denom == 0:
        return "not_evaluated"
    return _rate(tp, denom)


def _causal_set(case: ContextualCase) -> frozenset[CausalFault]:
    return frozenset(case.expected_causal_set)


def _predicted_set(result: ArmResult) -> frozenset[CausalFault]:
    return frozenset(result.predicted_causal_set)


def score_contextual_run(
    manifest: ContextualManifest,
    results: Sequence[ArmResult],
    *,
    arm: ArmKind,
    ablation_results: Sequence[ArmResult] | None = None,
) -> ContextualRunScore:
    by_id = {item.case_id: item for item in results if item.arm == arm}
    if len(by_id) != len(manifest.cases):
        raise ValueError("results must cover every manifest case for the selected arm")

    scoreable_cases = [case for case in manifest.cases if case.scoreable]
    outcome_correct = 0
    causal_correct = 0
    grounded = sum(item.grounded_claim_count for item in by_id.values())
    claim_count = sum(item.claim_count for item in by_id.values())
    unsupported = sum(
        item.unsupported_positive_fault_claim_count for item in by_id.values()
    )
    positive_claim_count = sum(
        item.predicted_positive_fault_claim_count for item in by_id.values()
    )
    unnecessary = 0
    tool_actions = 0
    natural_even_fp = 0

    harm_tp = harm_fp = harm_fn = 0
    clip_tp = clip_fp = clip_fn = 0

    for case in scoreable_cases:
        result = by_id[case.case_id]
        # Infrastructure failures occupy denominators as incorrect.
        if result.infrastructure_failure or result.status != "ok":
            tool_actions += 1
            continue
        tool_actions += 1
        if result.unnecessary_tool:
            unnecessary += 1
        if result.predicted_outcome == case.expected_outcome:
            outcome_correct += 1
        if _predicted_set(result) == _causal_set(case):
            causal_correct += 1

        expected_h = "harmonic_distortion" in _causal_set(case)
        predicted_h = "harmonic_distortion" in _predicted_set(result)
        if predicted_h and expected_h:
            harm_tp += 1
        elif predicted_h and not expected_h:
            harm_fp += 1
        elif expected_h and not predicted_h:
            harm_fn += 1

        expected_c = "clipping" in _causal_set(case)
        predicted_c = "clipping" in _predicted_set(result)
        if predicted_c and expected_c:
            clip_tp += 1
        elif predicted_c and not expected_c:
            clip_fp += 1
        elif expected_c and not predicted_c:
            clip_fn += 1

        if (
            case.role == "natural_even_control"
            and "harmonic_distortion" in _predicted_set(result)
        ):
            natural_even_fp += 1

    inconclusive_cases = [
        case for case in manifest.cases if case.expected_outcome == "inconclusive"
    ]
    if len(inconclusive_cases) != _INCONCLUSIVE_DENOM:
        raise ValueError("manifest must contain exactly six inconclusive roles")
    inconclusive_ok = 0
    for case in inconclusive_cases:
        result = by_id[case.case_id]
        if (
            not result.infrastructure_failure
            and result.status == "ok"
            and result.predicted_outcome == "inconclusive"
        ):
            inconclusive_ok += 1

    ablation_delta: int | None = None
    if arm == "contextual_agent" and ablation_results is not None:
        ablation_by_id = {
            item.case_id: item
            for item in ablation_results
            if item.arm == "no_context_ablation"
        }
        delta = 0
        for slot in manifest.paired_harmonic_slots or ():
            case = next(item for item in manifest.cases if item.case_id == slot.case_id)
            contextual = by_id[case.case_id]
            ablation = ablation_by_id[case.case_id]
            contextual_ok = (
                not contextual.infrastructure_failure
                and _predicted_set(contextual) == _causal_set(case)
            )
            ablation_ok = (
                not ablation.infrastructure_failure
                and _predicted_set(ablation) == _causal_set(case)
            )
            if contextual_ok and not ablation_ok:
                delta += 1
            elif ablation_ok and not contextual_ok:
                delta -= 1
        ablation_delta = delta

    aggregate = ContextualAggregate(
        outcome_accuracy=_rate(outcome_correct, _SCOREABLE_DENOM),
        causal_exact_set_accuracy=_rate(causal_correct, _SCOREABLE_DENOM),
        harmonic_precision=_precision_or_na(harm_tp, harm_fp),  # type: ignore[arg-type]
        harmonic_recall=_recall_or_na(harm_tp, harm_fn),  # type: ignore[arg-type]
        clipping_precision=_precision_or_na(clip_tp, clip_fp),  # type: ignore[arg-type]
        clipping_recall=_recall_or_na(clip_tp, clip_fn),  # type: ignore[arg-type]
        inconclusive_appropriateness=_rate(inconclusive_ok, _INCONCLUSIVE_DENOM),
        natural_even_harmonic_fp=natural_even_fp,
        unnecessary_tool_rate=_rate(unnecessary, max(tool_actions, 1)),
        evidence_grounding=_rate(grounded, claim_count),
        unsupported_claim_rate=_rate(unsupported, positive_claim_count),
        ablation_correct_delta=ablation_delta,
    )
    return ContextualRunScore(
        scoring_version=CONTEXTUAL_SCORING_VERSION,
        arm=arm,
        aggregate=aggregate,
        target_status="not_evaluated",
    )
