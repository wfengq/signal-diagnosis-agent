"""Repository-backed Tool service integrating signal selection and DSP."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

import numpy as np

from signal_diag.dsp import (
    analyze_clipping,
    analyze_contextual_distortion,
    analyze_fft,
    analyze_harmonic_distortion,
    estimate_f0_autocorrelation,
)
from signal_diag.dsp.contextual import ContextualAnalysisConfig
from signal_diag.dsp.models import HarmonicComponent, SpectrumPeak
from signal_diag.signal import (
    InvalidTimeRangeError,
    SignalNotFoundError,
    SignalRecord,
    SignalRepository,
    UnsupportedChannelError,
    extract_segment,
)
from signal_diag.signal.context import StimulusContext

from .contextual import analysis_to_output, build_contextual_evidence
from .contracts import (
    ClippingInput,
    ClippingOutput,
    ContextualDistortionInput,
    ContextualDistortionOutput,
    FundamentalInput,
    FundamentalOutput,
    HarmonicComponentOutput,
    HarmonicDistortionInput,
    HarmonicDistortionOutput,
    SignalSelection,
    SpectrumInput,
    SpectrumOutput,
    SpectrumPeakOutput,
    ToolName,
)
from .evidence import Evidence
from .results import ToolResult

SPECTRAL_PEAK_MIN_RELATIVE_DB = -60.0
HARMONIC_MIN_RELATIVE_AMPLITUDE = 1e-6

TArgs = TypeVar("TArgs", bound=SignalSelection)
TOutput = TypeVar("TOutput")


class SignalToolService:
    """Execute Phase 1 Tools against repository-backed signal selections."""

    def __init__(self, repository: SignalRepository) -> None:
        self._repository = repository
        self._call_sequence = 0

    def detect_clipping(
        self,
        signal_id: str,
        args: ClippingInput,
    ) -> ToolResult[ClippingOutput]:
        return self._run_tool(
            "detect_clipping",
            signal_id,
            args,
            self._detect_clipping,
        )

    def analyze_spectrum(
        self,
        signal_id: str,
        args: SpectrumInput,
    ) -> ToolResult[SpectrumOutput]:
        return self._run_tool(
            "analyze_spectrum",
            signal_id,
            args,
            self._analyze_spectrum,
        )

    def estimate_fundamental(
        self,
        signal_id: str,
        args: FundamentalInput,
    ) -> ToolResult[FundamentalOutput]:
        return self._run_tool(
            "estimate_fundamental",
            signal_id,
            args,
            self._estimate_fundamental,
        )

    def analyze_harmonic_distortion(
        self,
        signal_id: str,
        args: HarmonicDistortionInput,
    ) -> ToolResult[HarmonicDistortionOutput]:
        return self._run_tool(
            "analyze_harmonic_distortion",
            signal_id,
            args,
            self._analyze_harmonic_distortion,
        )

    def analyze_contextual_distortion(
        self,
        context: StimulusContext,
        args: ContextualDistortionInput,
    ) -> ToolResult[ContextualDistortionOutput]:
        call_id = self._next_call_id("analyze_contextual_distortion")
        if context.mode == "single_signal":
            return ToolResult(
                call_id=call_id,
                tool_name="analyze_contextual_distortion",
                status="error",
                error_message=(
                    "analyze_contextual_distortion is unavailable in single_signal mode"
                ),
            )
        try:
            test_record, test_samples = self._load_selected(
                context.test_signal_id,
                args,
            )
            reference_samples = None
            reference_rate: int | None = None
            if context.mode == "paired_reference":
                if context.reference_signal_id is None:
                    return ToolResult(
                        call_id=call_id,
                        tool_name="analyze_contextual_distortion",
                        status="error",
                        error_message="paired_reference requires reference_signal_id",
                    )
                ref_record, reference_samples = self._load_selected(
                    context.reference_signal_id,
                    args,
                )
                reference_rate = ref_record.meta.sample_rate_hz
        except (
            SignalNotFoundError,
            InvalidTimeRangeError,
            UnsupportedChannelError,
        ) as error:
            return ToolResult(
                call_id=call_id,
                tool_name="analyze_contextual_distortion",
                status="error",
                error_message=str(error),
            )

        config = ContextualAnalysisConfig(max_harmonic_order=args.max_harmonic_order)
        if context.mode == "paired_reference":
            analysis = analyze_contextual_distortion(
                test_samples,
                test_record.meta.sample_rate_hz,
                mode="paired_reference",
                reference_samples=reference_samples,
                reference_sample_rate_hz=reference_rate,
                config=config,
            )
        else:
            analysis = analyze_contextual_distortion(
                test_samples,
                test_record.meta.sample_rate_hz,
                mode="nominal_single_tone",
                nominal_fundamental_hz=context.nominal_fundamental_hz,
                config=config,
            )

        output = analysis_to_output(analysis)
        evidence = build_contextual_evidence(
            call_id=call_id,
            selection=args,
            output=output,
            build_evidence=self._build_evidence,
        )
        if not analysis.valid:
            warning = analysis.invalid_reason or "contextual distortion analysis invalid"
            return ToolResult(
                call_id=call_id,
                tool_name="analyze_contextual_distortion",
                status="invalid",
                result=output,
                evidence=evidence,
                warnings=(warning,),
            )
        return ToolResult(
            call_id=call_id,
            tool_name="analyze_contextual_distortion",
            status="success",
            result=output,
            evidence=evidence,
        )

    def _next_call_id(self, tool_name: ToolName) -> str:
        call_id = f"call_{tool_name}_{self._call_sequence:06d}"
        self._call_sequence += 1
        return call_id

    def _load_selected(
        self,
        signal_id: str,
        selection: SignalSelection,
    ) -> tuple[SignalRecord, np.ndarray]:
        record = self._repository.get(signal_id)
        samples = extract_segment(
            record,
            time_range=selection.time_range,
            channel=selection.channel,
        )
        return record, samples

    def _run_tool(
        self,
        tool_name: ToolName,
        signal_id: str,
        args: TArgs,
        handler: Callable[
            [str, SignalRecord, np.ndarray, TArgs],
            ToolResult[TOutput],
        ],
    ) -> ToolResult[TOutput]:
        call_id = self._next_call_id(tool_name)
        try:
            record, samples = self._load_selected(signal_id, args)
        except (
            SignalNotFoundError,
            InvalidTimeRangeError,
            UnsupportedChannelError,
        ) as error:
            return ToolResult(
                call_id=call_id,
                tool_name=tool_name,
                status="error",
                error_message=str(error),
            )
        return handler(call_id, record, samples, args)

    def _build_evidence(
        self,
        *,
        call_id: str,
        tool_name: ToolName,
        selection: SignalSelection,
        metric: str,
        value: object,
        unit: str | None = None,
        validity: str = "valid",
        confidence: float | None = None,
        ordinal: int,
    ) -> Evidence:
        return Evidence(
            evidence_id=f"ev_{tool_name}_{call_id.removeprefix('call_')}_{ordinal:03d}",
            source_tool=tool_name,
            call_id=call_id,
            metric=metric,
            value=value,  # type: ignore[arg-type]
            unit=unit,
            validity=validity,  # type: ignore[arg-type]
            confidence=confidence,
            time_range=selection.time_range,
            channel=selection.channel,
        )

    def _detect_clipping(
        self,
        call_id: str,
        record: SignalRecord,
        samples: np.ndarray,
        args: ClippingInput,
    ) -> ToolResult[ClippingOutput]:
        analysis = analyze_clipping(
            samples,
            full_scale_threshold=args.full_scale_threshold,
        )
        output = ClippingOutput(
            detected=analysis.detected,
            clipping_ratio=analysis.clipping_ratio,
            clipped_samples=analysis.clipped_samples,
            clipping_events=analysis.clipping_events,
            longest_event_samples=analysis.longest_event_samples,
            peak_abs=analysis.peak_abs,
            full_scale_detected=analysis.full_scale_detected,
            flat_top_detected=analysis.flat_top_detected,
            clipping_mechanism=analysis.clipping_mechanism,
        )
        evidence = (
            self._build_evidence(
                call_id=call_id,
                tool_name="detect_clipping",
                selection=args,
                metric="clipping_detected",
                value=output.detected,
                ordinal=0,
            ),
            self._build_evidence(
                call_id=call_id,
                tool_name="detect_clipping",
                selection=args,
                metric="clipping_ratio",
                value=output.clipping_ratio,
                ordinal=1,
            ),
            self._build_evidence(
                call_id=call_id,
                tool_name="detect_clipping",
                selection=args,
                metric="clipped_samples",
                value=output.clipped_samples,
                ordinal=2,
            ),
            self._build_evidence(
                call_id=call_id,
                tool_name="detect_clipping",
                selection=args,
                metric="clipping_events",
                value=output.clipping_events,
                ordinal=3,
            ),
            self._build_evidence(
                call_id=call_id,
                tool_name="detect_clipping",
                selection=args,
                metric="peak_abs",
                value=output.peak_abs,
                ordinal=4,
            ),
            self._build_evidence(
                call_id=call_id,
                tool_name="detect_clipping",
                selection=args,
                metric="full_scale_detected",
                value=output.full_scale_detected,
                ordinal=5,
            ),
            self._build_evidence(
                call_id=call_id,
                tool_name="detect_clipping",
                selection=args,
                metric="flat_top_detected",
                value=output.flat_top_detected,
                ordinal=6,
            ),
            self._build_evidence(
                call_id=call_id,
                tool_name="detect_clipping",
                selection=args,
                metric="clipping_mechanism",
                value=output.clipping_mechanism,
                ordinal=7,
            ),
        )
        return ToolResult(
            call_id=call_id,
            tool_name="detect_clipping",
            status="success",
            result=output,
            evidence=evidence,
        )

    def _filter_spectral_peaks(
        self,
        peaks: tuple[SpectrumPeak, ...],
    ) -> tuple[SpectrumPeakOutput, ...]:
        filtered = [
            SpectrumPeakOutput(
                frequency_hz=float(peak.frequency_hz),
                relative_magnitude_db=float(peak.magnitude_db),
            )
            for peak in peaks
            if float(peak.magnitude_db) >= SPECTRAL_PEAK_MIN_RELATIVE_DB
        ]
        return tuple(filtered)

    def _analyze_spectrum(
        self,
        call_id: str,
        record: SignalRecord,
        samples: np.ndarray,
        args: SpectrumInput,
    ) -> ToolResult[SpectrumOutput]:
        analysis = analyze_fft(
            samples,
            record.meta.sample_rate_hz,
            window=args.window,
            n_fft=args.n_fft,
            max_peaks=args.max_peaks,
        )
        output = SpectrumOutput(
            frequency_resolution_hz=analysis.frequency_resolution_hz,
            dominant_frequency_hz=analysis.dominant_frequency_hz,
            spectral_centroid_hz=analysis.spectral_centroid_hz,
            spectral_peaks=self._filter_spectral_peaks(analysis.peaks),
        )
        evidence_items: list[Evidence] = []
        ordinal = 0

        def append_evidence(
            metric: str,
            value: object,
            unit: str | None = None,
        ) -> None:
            nonlocal ordinal
            evidence_items.append(
                self._build_evidence(
                    call_id=call_id,
                    tool_name="analyze_spectrum",
                    selection=args,
                    metric=metric,
                    value=value,
                    unit=unit,
                    ordinal=ordinal,
                )
            )
            ordinal += 1

        append_evidence(
            "frequency_resolution_hz",
            output.frequency_resolution_hz,
            "Hz",
        )
        if output.dominant_frequency_hz is not None:
            append_evidence(
                "dominant_frequency_hz",
                output.dominant_frequency_hz,
                "Hz",
            )
        if output.spectral_centroid_hz is not None:
            append_evidence(
                "spectral_centroid_hz",
                output.spectral_centroid_hz,
                "Hz",
            )

        return ToolResult(
            call_id=call_id,
            tool_name="analyze_spectrum",
            status="success",
            result=output,
            evidence=tuple(evidence_items),
        )

    def _estimate_fundamental(
        self,
        call_id: str,
        record: SignalRecord,
        samples: np.ndarray,
        args: FundamentalInput,
    ) -> ToolResult[FundamentalOutput]:
        estimate = estimate_f0_autocorrelation(
            samples,
            record.meta.sample_rate_hz,
            fmin_hz=args.fmin_hz,
            fmax_hz=args.fmax_hz,
        )
        output = FundamentalOutput(
            f0_hz=estimate.f0_hz,
            confidence=estimate.confidence,
            voiced=estimate.voiced,
            method=estimate.method,
        )
        evidence_items: list[Evidence] = [
            self._build_evidence(
                call_id=call_id,
                tool_name="estimate_fundamental",
                selection=args,
                metric="voiced",
                value=output.voiced,
                ordinal=0,
            ),
            self._build_evidence(
                call_id=call_id,
                tool_name="estimate_fundamental",
                selection=args,
                metric="confidence",
                value=output.confidence,
                ordinal=1,
            ),
        ]
        if output.voiced and output.f0_hz is not None:
            evidence_items.append(
                self._build_evidence(
                    call_id=call_id,
                    tool_name="estimate_fundamental",
                    selection=args,
                    metric="f0_hz",
                    value=output.f0_hz,
                    unit="Hz",
                    confidence=output.confidence,
                    ordinal=2,
                )
            )
            return ToolResult(
                call_id=call_id,
                tool_name="estimate_fundamental",
                status="success",
                result=output,
                evidence=tuple(evidence_items),
            )

        warning = "fundamental could not be estimated reliably"
        return ToolResult(
            call_id=call_id,
            tool_name="estimate_fundamental",
            status="invalid",
            result=output,
            evidence=tuple(evidence_items),
            warnings=(warning,),
        )

    def _filter_harmonic_components(
        self,
        components: tuple[HarmonicComponent, ...],
    ) -> tuple[HarmonicComponentOutput, ...]:
        filtered = [
            HarmonicComponentOutput(
                order=int(component.order),
                measured_frequency_hz=float(component.measured_frequency_hz),
                relative_amplitude=float(component.relative_amplitude),
                relative_magnitude_db=float(component.relative_magnitude_db),
            )
            for component in components
            if float(component.relative_amplitude) >= HARMONIC_MIN_RELATIVE_AMPLITUDE
        ]
        return tuple(filtered)

    def _analyze_harmonic_distortion(
        self,
        call_id: str,
        record: SignalRecord,
        samples: np.ndarray,
        args: HarmonicDistortionInput,
    ) -> ToolResult[HarmonicDistortionOutput]:
        analysis = analyze_harmonic_distortion(
            samples,
            record.meta.sample_rate_hz,
            fundamental_hz=args.fundamental_hz,
            fmin_hz=args.fmin_hz,
            fmax_hz=args.fmax_hz,
            max_harmonic_order=args.max_harmonic_order,
            window=args.window,
        )
        output = HarmonicDistortionOutput(
            valid=analysis.valid,
            invalid_reason=analysis.invalid_reason,
            fundamental_frequency_hz=analysis.fundamental_frequency_hz,
            thd_percent=analysis.thd_percent,
            components=self._filter_harmonic_components(analysis.components),
            series_kind=analysis.series_kind,
        )
        if not analysis.valid:
            evidence = (
                self._build_evidence(
                    call_id=call_id,
                    tool_name="analyze_harmonic_distortion",
                    selection=args,
                    metric="valid",
                    value=False,
                    validity="not_applicable",
                    ordinal=0,
                ),
                self._build_evidence(
                    call_id=call_id,
                    tool_name="analyze_harmonic_distortion",
                    selection=args,
                    metric="series_kind",
                    value=analysis.series_kind or "not_applicable",
                    validity="not_applicable",
                    ordinal=1,
                ),
            )
            warning = analysis.invalid_reason or "harmonic distortion analysis invalid"
            return ToolResult(
                call_id=call_id,
                tool_name="analyze_harmonic_distortion",
                status="invalid",
                result=output,
                evidence=evidence,
                warnings=(warning,),
            )

        evidence_items: list[Evidence] = [
            self._build_evidence(
                call_id=call_id,
                tool_name="analyze_harmonic_distortion",
                selection=args,
                metric="valid",
                value=True,
                ordinal=0,
            ),
            self._build_evidence(
                call_id=call_id,
                tool_name="analyze_harmonic_distortion",
                selection=args,
                metric="fundamental_frequency_hz",
                value=output.fundamental_frequency_hz,
                unit="Hz",
                ordinal=1,
            ),
            self._build_evidence(
                call_id=call_id,
                tool_name="analyze_harmonic_distortion",
                selection=args,
                metric="thd_percent",
                value=output.thd_percent,
                unit="%",
                ordinal=2,
            ),
        ]
        ordinal = 3
        if output.series_kind is not None:
            evidence_items.append(
                self._build_evidence(
                    call_id=call_id,
                    tool_name="analyze_harmonic_distortion",
                    selection=args,
                    metric="series_kind",
                    value=output.series_kind,
                    ordinal=ordinal,
                )
            )
            ordinal += 1
        for component in output.components:
            evidence_items.append(
                self._build_evidence(
                    call_id=call_id,
                    tool_name="analyze_harmonic_distortion",
                    selection=args,
                    metric=f"harmonic_order_{component.order}_relative_amplitude",
                    value=component.relative_amplitude,
                    ordinal=ordinal,
                )
            )
            ordinal += 1

        return ToolResult(
            call_id=call_id,
            tool_name="analyze_harmonic_distortion",
            status="success",
            result=output,
            evidence=tuple(evidence_items),
        )
