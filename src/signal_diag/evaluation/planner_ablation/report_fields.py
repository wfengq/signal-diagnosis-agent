"""Deterministic report-field parity helpers (evaluation-owned; no app imports)."""

from __future__ import annotations

import math

from signal_diag.agent.models import AgentRunResult, StructuredDiagnosis
from signal_diag.evaluation.models import BaselineRunResult
from signal_diag.evaluation.planner_ablation.models import (
    StudyContextGuidanceView,
    StudyObservedFactView,
)
from signal_diag.tools.evidence import Evidence

_HARMONIC_METRICS = frozenset(
    {
        "thd_percent",
        "even_order_present",
        "fundamental_relative_energy",
        "even_harmonic_growth",
        "odd_harmonic_growth",
        "test_thd_percent",
    }
)

_SUMMARY_TEMPLATES = {
    "harmonic_attribution_requires_context": (
        "Same-run measurements are not enough to attribute added harmonic "
        "distortion from a single file. Provide a clean reference WAV "
        "(paired_reference) or declare a single-tone stimulus with "
        "nominal_fundamental_hz (nominal_single_tone) to unlock "
        "evidence-backed harmonic attribution."
    ),
    "insufficient_evidence_for_supported_fault": (
        "This single-file run ended inconclusive: evidence is insufficient "
        "to support a fault claim under the active gates. Optional upgrades: "
        "paired_reference (clean reference WAV) or nominal_single_tone "
        "(declared single-tone fundamental)."
    ),
}

_FACTS_SUMMARY_SUFFIX = (
    " Listed observed_facts are same-run measurements and are not a "
    "fault attribution."
)

_DISPLAY_WHITELIST: tuple[tuple[str, str, str | None], ...] = (
    ("thd_percent", "analyze_harmonic_distortion", "%"),
)


def _is_finite_float(value: object) -> bool:
    return isinstance(value, float) and math.isfinite(value)


def _row_matches_whitelist(item: Evidence) -> bool:
    for metric, tool, unit in _DISPLAY_WHITELIST:
        if item.metric != metric or item.source_tool != tool:
            continue
        if item.validity != "valid" or item.unit != unit:
            continue
        if not _is_finite_float(item.value):
            continue
        return True
    return False


def _select_observed_facts(
    result: AgentRunResult,
    reason_codes: tuple[str, ...],
) -> tuple[StudyObservedFactView, ...]:
    if "harmonic_attribution_requires_context" not in reason_codes:
        return ()
    candidates = [item for item in result.evidence if _row_matches_whitelist(item)]
    best: dict[tuple[str, str, str | None], Evidence] = {}
    for item in candidates:
        key = (
            item.metric,
            item.channel,
            None if item.time_range is None else item.time_range.model_dump_json(),
        )
        prev = best.get(key)
        if prev is None or item.evidence_id < prev.evidence_id:
            best[key] = item
    ordered_metrics = [m for m, _, _ in _DISPLAY_WHITELIST]
    selected = sorted(
        best.values(),
        key=lambda e: (ordered_metrics.index(e.metric), e.evidence_id),
    )
    return tuple(
        StudyObservedFactView(
            evidence_id=e.evidence_id,
            source_tool=e.source_tool,
            call_id=e.call_id,
            metric=e.metric,
            value=e.value,
            unit=e.unit,
            validity="valid",
            time_range=e.time_range,
            channel=e.channel,
        )
        for e in selected
    )


def _has_harmonic_measurement_evidence(result: AgentRunResult) -> bool:
    for item in result.evidence:
        if item.validity != "valid":
            continue
        if item.metric in _HARMONIC_METRICS:
            return True
    return False


def derive_context_guidance_from_agent_result(
    *,
    mode: str,
    result: AgentRunResult | None,
) -> StudyContextGuidanceView | None:
    if mode != "single_signal":
        return None
    if result is None or result.diagnosis is None:
        return None
    if result.diagnosis.outcome != "inconclusive":
        return None

    reasons: list[str] = []
    if _has_harmonic_measurement_evidence(result):
        reasons.append("harmonic_attribution_requires_context")
    else:
        reasons.append("insufficient_evidence_for_supported_fault")

    reason_tuple = tuple(reasons)
    summary = " ".join(_SUMMARY_TEMPLATES[code] for code in reasons)
    facts = _select_observed_facts(result, reason_tuple)
    if facts:
        summary = summary + _FACTS_SUMMARY_SUFFIX
    return StudyContextGuidanceView(
        reason_codes=reason_tuple,
        unlockable_modes=("paired_reference", "nominal_single_tone"),
        required_inputs={
            "paired_reference": ("reference_wav",),
            "nominal_single_tone": (
                "nominal_fundamental_hz",
                "stimulus_kind=single_tone",
            ),
        },
        summary=summary,
        observed_facts=facts,
    )


def derive_context_guidance_from_baseline(
    *,
    mode: str,
    baseline: BaselineRunResult,
) -> StudyContextGuidanceView | None:
    if baseline.diagnosis is None:
        return None
    pseudo = AgentRunResult(
        run_id=baseline.run_id,
        status=baseline.status,
        diagnosis=StructuredDiagnosis(
            run_id=baseline.diagnosis.run_id,
            task_type="distortion_analysis",
            outcome=baseline.diagnosis.outcome,
            claims=baseline.diagnosis.claims,
            confidence_label=baseline.diagnosis.confidence_label,
            limitations=baseline.diagnosis.limitations,
            termination_reason="planner_finished",
            tool_call_count=baseline.diagnosis.tool_call_count,
            rule_evaluation_batches=baseline.diagnosis.rule_evaluation_batches,
        ),
        observations=baseline.observations,
        evidence=baseline.evidence,
        tool_history=baseline.tool_history,
        termination_reason="planner_finished",
        warnings=baseline.warnings,
        errors=baseline.errors,
        rule_evaluation_batches=baseline.rule_evaluation_batches,
    )
    return derive_context_guidance_from_agent_result(mode=mode, result=pseudo)


def guidance_parity_equal(
    left: StudyContextGuidanceView | None,
    right: StudyContextGuidanceView | None,
) -> bool:
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False
    return left.model_dump() == right.model_dump()
