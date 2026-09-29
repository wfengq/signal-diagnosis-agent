"""Deterministic context-guidance for single-file inconclusive runs (D037)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from signal_diag.agent.models import AgentRunResult
from signal_diag.signal.context import DiagnosticMode

ContextGuidanceReasonCode = Literal[
    "harmonic_attribution_requires_context",
    "insufficient_evidence_for_supported_fault",
]

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

_SUMMARY_TEMPLATES: dict[ContextGuidanceReasonCode, str] = {
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


class ContextGuidance(BaseModel):
    """Additive report block; never a soft diagnosis."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    reason_codes: tuple[ContextGuidanceReasonCode, ...] = Field(min_length=1)
    unlockable_modes: tuple[Literal["paired_reference", "nominal_single_tone"], ...]
    required_inputs: dict[str, tuple[str, ...]]
    summary: str = Field(min_length=1, max_length=2_000)

    @field_validator("reason_codes")
    @classmethod
    def _unique_ordered(cls, value: tuple[ContextGuidanceReasonCode, ...]) -> tuple[
        ContextGuidanceReasonCode, ...
    ]:
        if len(set(value)) != len(value):
            raise ValueError("reason_codes must be unique")
        return value


def _has_harmonic_measurement_evidence(result: AgentRunResult) -> bool:
    for item in result.evidence:
        if item.validity != "valid":
            continue
        if item.metric in _HARMONIC_METRICS:
            return True
    return False


def build_context_guidance(
    *,
    mode: DiagnosticMode,
    result: AgentRunResult | None,
) -> ContextGuidance | None:
    if mode != "single_signal":
        return None
    if result is None or result.diagnosis is None:
        return None
    if result.diagnosis.outcome != "inconclusive":
        return None

    reasons: list[ContextGuidanceReasonCode] = []
    if _has_harmonic_measurement_evidence(result):
        reasons.append("harmonic_attribution_requires_context")
    else:
        reasons.append("insufficient_evidence_for_supported_fault")

    summary = " ".join(_SUMMARY_TEMPLATES[code] for code in reasons)
    return ContextGuidance(
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
