"""Deterministic report-field parity helpers (evaluation-owned; no app imports)."""

from __future__ import annotations

from signal_diag.agent.models import AgentRunResult, StructuredDiagnosis
from signal_diag.evaluation.models import BaselineRunResult
from signal_diag.evaluation.planner_ablation.models import StudyContextGuidanceView

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

    summary = " ".join(_SUMMARY_TEMPLATES[code] for code in reasons)
    return StudyContextGuidanceView(
        reason_codes=tuple(reasons),
        unlockable_modes=("paired_reference", "nominal_single_tone"),
        required_inputs={
            "paired_reference": ("reference_wav",),
            "nominal_single_tone": (
                "nominal_fundamental_hz",
                "stimulus_kind=single_tone",
            ),
        },
        summary=summary,
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
