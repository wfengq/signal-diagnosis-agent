"""Deterministic context-guidance for single-file inconclusive runs (D037)."""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from signal_diag.agent.models import AgentRunResult
from signal_diag.signal.context import DiagnosticMode
from signal_diag.signal.models import ChannelMode, TimeRange
from signal_diag.tools.contracts import ToolName
from signal_diag.tools.evidence import Evidence

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

_FACTS_SUMMARY_SUFFIX = (
    " Listed observed_facts are same-run measurements and are not a fault attribution."
)

_DISPLAY_WHITELIST: tuple[tuple[str, ToolName, str | None], ...] = (
    ("thd_percent", "analyze_harmonic_distortion", "%"),
)


class ObservedFact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    evidence_id: str
    source_tool: ToolName
    call_id: str
    metric: str = Field(min_length=1)
    value: bool | int | float | str
    unit: str | None = None
    validity: Literal["valid"] = "valid"
    time_range: TimeRange | None = None
    channel: ChannelMode

    @field_validator("value")
    @classmethod
    def _reject_non_finite_float(cls, value: bool | float | str) -> bool | float | str:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("observed fact float values must be finite")
        return value


class ContextGuidance(BaseModel):
    """Additive report block; never a soft diagnosis."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    reason_codes: tuple[ContextGuidanceReasonCode, ...] = Field(min_length=1)
    unlockable_modes: tuple[Literal["paired_reference", "nominal_single_tone"], ...]
    required_inputs: dict[str, tuple[str, ...]]
    summary: str = Field(min_length=1, max_length=2_000)
    observed_facts: tuple[ObservedFact, ...] = ()

    @field_validator("reason_codes")
    @classmethod
    def _unique_ordered(
        cls, value: tuple[ContextGuidanceReasonCode, ...]
    ) -> tuple[ContextGuidanceReasonCode, ...]:
        if len(set(value)) != len(value):
            raise ValueError("reason_codes must be unique")
        return value


def _is_finite_float(value: object) -> bool:
    return isinstance(value, float) and math.isfinite(value)


def _fact_matches_source(fact: ObservedFact, source: Evidence) -> bool:
    return (
        fact.evidence_id == source.evidence_id
        and fact.source_tool == source.source_tool
        and fact.call_id == source.call_id
        and fact.metric == source.metric
        and fact.value == source.value
        and fact.unit == source.unit
        and fact.validity == source.validity
        and fact.time_range == source.time_range
        and fact.channel == source.channel
    )


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


def validate_observed_facts_against_evidence(
    *,
    evidence: tuple[Evidence, ...] | list[Evidence],
    observed_facts: tuple[ObservedFact, ...],
) -> None:
    """Reject facts that are not display-eligible field-faithful same-run copies."""
    by_id = {item.evidence_id: item for item in evidence}
    for fact in observed_facts:
        source = by_id.get(fact.evidence_id)
        if source is None:
            raise ValueError("observed_facts reference unknown Evidence")
        if not _fact_matches_source(fact, source):
            raise ValueError("observed_facts do not match same-run Evidence")
        if not _row_matches_whitelist(source):
            raise ValueError("observed_facts fail display whitelist")


def _select_observed_facts(
    result: AgentRunResult,
    reason_codes: tuple[ContextGuidanceReasonCode, ...],
) -> tuple[ObservedFact, ...]:
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
        ObservedFact(
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
    facts = _select_observed_facts(result, tuple(reasons))
    if facts:
        summary = summary + _FACTS_SUMMARY_SUFFIX
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
        observed_facts=facts,
    )
