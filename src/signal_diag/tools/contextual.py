"""Adapter from contextual DSP analysis to compact Tool Evidence."""

from __future__ import annotations

from collections.abc import Callable

from signal_diag.dsp.contextual import ContextualDistortionAnalysis

from .contracts import (
    ContextualDistortionOutput,
    HarmonicGrowthComponentOutput,
    SignalSelection,
)
from .evidence import Evidence


def analysis_to_output(
    analysis: ContextualDistortionAnalysis,
) -> ContextualDistortionOutput:
    return ContextualDistortionOutput(
        algorithm_version=analysis.algorithm_version,
        mode=analysis.mode,
        valid=analysis.valid,
        invalid_reason=analysis.invalid_reason,
        test_f0_hz=analysis.test_f0_hz,
        comparison_f0_hz=analysis.comparison_f0_hz,
        f0_relative_delta=analysis.f0_relative_delta,
        alignment_lag_samples=analysis.alignment_lag_samples,
        alignment_correlation=analysis.alignment_correlation,
        gain_ratio=analysis.gain_ratio,
        reference_thd_percent=analysis.reference_thd_percent,
        test_thd_percent=analysis.test_thd_percent,
        thd_delta_percent=analysis.thd_delta_percent,
        even_harmonic_growth_percent=analysis.even_harmonic_growth_percent,
        test_series_kind=analysis.test_series_kind,
        components=tuple(
            HarmonicGrowthComponentOutput(
                order=component.order,
                reference_relative_amplitude=component.reference_relative_amplitude,
                test_relative_amplitude=component.test_relative_amplitude,
                positive_growth=component.positive_growth,
            )
            for component in analysis.components
        ),
        reference_clipping_ratio=analysis.reference_clipping_ratio,
        reference_flat_top_detected=analysis.reference_flat_top_detected,
        test_clipping_mechanism=analysis.test_clipping_mechanism,
        test_clipping_ratio=analysis.test_clipping_ratio,
        test_flat_top_detected=analysis.test_flat_top_detected,
    )


def build_contextual_evidence(
    *,
    call_id: str,
    selection: SignalSelection,
    output: ContextualDistortionOutput,
    build_evidence: Callable[..., Evidence],
) -> tuple[Evidence, ...]:
    """Emit compact scalar Evidence for contextual comparison results."""
    tool_name = "analyze_contextual_distortion"
    items: list[Evidence] = [
        build_evidence(
            call_id=call_id,
            tool_name=tool_name,
            selection=selection,
            metric="context_valid",
            value=output.valid,
            ordinal=0,
        ),
        build_evidence(
            call_id=call_id,
            tool_name=tool_name,
            selection=selection,
            metric="mode",
            value=output.mode,
            ordinal=1,
        ),
        build_evidence(
            call_id=call_id,
            tool_name=tool_name,
            selection=selection,
            metric="algorithm_version",
            value=output.algorithm_version,
            ordinal=2,
        ),
    ]
    ordinal = 3

    def _append(
        metric: str,
        value: object,
        *,
        unit: str | None = None,
        validity: str = "valid",
    ) -> None:
        nonlocal ordinal
        items.append(
            build_evidence(
                call_id=call_id,
                tool_name=tool_name,
                selection=selection,
                metric=metric,
                value=value,
                unit=unit,
                validity=validity,
                ordinal=ordinal,
            )
        )
        ordinal += 1

    if output.invalid_reason is not None:
        _append("invalid_reason", output.invalid_reason)

    numeric_specs: tuple[tuple[str, float | int | None, str | None], ...] = (
        ("test_f0_hz", output.test_f0_hz, "Hz"),
        ("comparison_f0_hz", output.comparison_f0_hz, "Hz"),
        ("f0_relative_delta", output.f0_relative_delta, None),
        ("alignment_lag_samples", output.alignment_lag_samples, None),
        ("alignment_correlation", output.alignment_correlation, None),
        ("gain_ratio", output.gain_ratio, None),
        ("reference_thd_percent", output.reference_thd_percent, "%"),
        ("test_thd_percent", output.test_thd_percent, "%"),
        ("thd_delta_percent", output.thd_delta_percent, "%"),
        ("even_harmonic_growth_percent", output.even_harmonic_growth_percent, "%"),
    )
    for metric, value, unit in numeric_specs:
        if value is None:
            _append(metric, "not_applicable", unit=unit, validity="not_applicable")
        else:
            _append(metric, value, unit=unit)

    if output.test_series_kind is None:
        _append(
            "test_series_kind",
            "not_applicable",
            validity="not_applicable",
        )
    else:
        _append("test_series_kind", output.test_series_kind)

    if output.reference_clipping_ratio is None:
        _append(
            "reference_clipping_ratio",
            "not_applicable",
            validity="not_applicable",
        )
    else:
        _append("reference_clipping_ratio", output.reference_clipping_ratio)

    if output.reference_flat_top_detected is None:
        _append(
            "reference_flat_top_detected",
            "not_applicable",
            validity="not_applicable",
        )
    else:
        _append("reference_flat_top_detected", output.reference_flat_top_detected)

    _append("test_clipping_ratio", output.test_clipping_ratio)
    _append("test_flat_top_detected", output.test_flat_top_detected)
    _append("test_clipping_mechanism", output.test_clipping_mechanism)
    return tuple(items)
