"""Deterministic contextual reference qualification and harmonic comparison."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from signal_diag.dsp.clipping import analyze_clipping
from signal_diag.dsp.harmonics import analyze_harmonic_distortion

CONTEXTUAL_DSP_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class ContextualAnalysisConfig:
    max_lag_s: float = 0.25
    min_alignment_correlation: float = 0.50
    max_f0_relative_delta: float = 0.02
    max_harmonic_order: int = 5
    full_scale_threshold: float = 0.99
    min_samples: int = 256


@dataclass(frozen=True, slots=True)
class HarmonicGrowthComponent:
    order: int
    reference_relative_amplitude: float
    test_relative_amplitude: float
    positive_growth: float


@dataclass(frozen=True, slots=True)
class ContextualDistortionAnalysis:
    algorithm_version: Literal["1.0.0"]
    mode: Literal["nominal_single_tone", "paired_reference"]
    valid: bool
    invalid_reason: str | None
    test_f0_hz: float | None
    comparison_f0_hz: float | None
    f0_relative_delta: float | None
    alignment_lag_samples: int | None
    alignment_correlation: float | None
    gain_ratio: float | None
    reference_thd_percent: float | None
    test_thd_percent: float | None
    thd_delta_percent: float | None
    even_harmonic_growth_percent: float | None
    test_series_kind: str | None
    components: tuple[HarmonicGrowthComponent, ...]
    reference_clipping_ratio: float | None
    reference_flat_top_detected: bool | None
    test_clipping_mechanism: bool
    test_clipping_ratio: float
    test_flat_top_detected: bool


def _invalid(
    *,
    mode: Literal["nominal_single_tone", "paired_reference"],
    reason: str,
    test_clipping_mechanism: bool,
    test_clipping_ratio: float = 0.0,
    test_flat_top_detected: bool = False,
    reference_clipping_ratio: float | None = None,
    reference_flat_top_detected: bool | None = None,
) -> ContextualDistortionAnalysis:
    return ContextualDistortionAnalysis(
        algorithm_version="1.0.0",
        mode=mode,
        valid=False,
        invalid_reason=reason,
        test_f0_hz=None,
        comparison_f0_hz=None,
        f0_relative_delta=None,
        alignment_lag_samples=None,
        alignment_correlation=None,
        gain_ratio=None,
        reference_thd_percent=None,
        test_thd_percent=None,
        thd_delta_percent=None,
        even_harmonic_growth_percent=None,
        test_series_kind=None,
        components=(),
        reference_clipping_ratio=reference_clipping_ratio,
        reference_flat_top_detected=reference_flat_top_detected,
        test_clipping_mechanism=test_clipping_mechanism,
        test_clipping_ratio=test_clipping_ratio,
        test_flat_top_detected=test_flat_top_detected,
    )


def _as_1d(samples: np.ndarray, *, name: str) -> np.ndarray:
    if not isinstance(samples, np.ndarray):
        raise TypeError(f"{name} must be a numpy array")
    values = np.asarray(samples, dtype=np.float64)
    if values.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    if values.size == 0:
        raise ValueError(f"{name} must be non-empty")
    if not np.isfinite(values).all():
        raise ValueError(f"{name} must be finite")
    return values


def _validate_rate(sample_rate_hz: int) -> int:
    if (
        not isinstance(sample_rate_hz, (int, np.integer))
        or isinstance(sample_rate_hz, (bool, np.bool_))
        or int(sample_rate_hz) <= 0
    ):
        raise ValueError("sample_rate_hz must be a positive integer")
    return int(sample_rate_hz)


def _bounded_xcorr_lag(
    reference: np.ndarray,
    test: np.ndarray,
    *,
    max_lag: int,
) -> tuple[int, float]:
    """Return best lag (test relative to reference) and peak correlation."""
    n = min(len(reference), len(test))
    ref = reference[:n] - np.mean(reference[:n])
    tst = test[:n] - np.mean(test[:n])
    ref_norm = float(np.linalg.norm(ref))
    tst_norm = float(np.linalg.norm(tst))
    if ref_norm <= 0.0 or tst_norm <= 0.0:
        return 0, 0.0
    fft_size = 1 << int(np.ceil(np.log2(2 * n - 1)))
    ref_f = np.fft.rfft(ref, n=fft_size)
    tst_f = np.fft.rfft(tst, n=fft_size)
    corr = np.fft.irfft(np.conj(ref_f) * tst_f, n=fft_size)
    # corr[k] for k in 0..n-1 is lag +k; for end is negative lags
    lags = list(range(-max_lag, max_lag + 1))
    scores: list[tuple[float, int]] = []
    for lag in lags:
        if lag >= 0:
            value = float(corr[lag])
        else:
            value = float(corr[fft_size + lag])
        scores.append((value / (ref_norm * tst_norm), lag))
    best_corr, best_lag = max(scores, key=lambda item: item[0])
    return int(best_lag), float(best_corr)


def _apply_lag(samples: np.ndarray, lag: int) -> np.ndarray:
    if lag == 0:
        return samples
    if lag > 0:
        return samples[lag:]
    return samples[: len(samples) + lag]


def _gain_ratio(
    reference: np.ndarray,
    test: np.ndarray,
    *,
    full_scale_threshold: float,
) -> float:
    n = min(len(reference), len(test))
    ref = reference[:n]
    tst = test[:n]
    mask = (np.abs(ref) < full_scale_threshold) & (np.abs(tst) < full_scale_threshold)
    if int(np.count_nonzero(mask)) < 8:
        mask = np.ones(n, dtype=bool)
    ref_m = ref[mask]
    tst_m = tst[mask]
    denom = float(np.dot(ref_m, ref_m))
    if denom <= 0.0:
        return 1.0
    return float(np.dot(tst_m, ref_m) / denom)


def _relative_map(analysis) -> dict[int, float]:
    mapping: dict[int, float] = {1: 1.0}
    for component in analysis.components:
        mapping[int(component.order)] = float(component.relative_amplitude)
    return mapping


def analyze_contextual_distortion(
    test_samples: np.ndarray,
    sample_rate_hz: int,
    *,
    mode: Literal["nominal_single_tone", "paired_reference"],
    reference_samples: np.ndarray | None = None,
    reference_sample_rate_hz: int | None = None,
    nominal_fundamental_hz: float | None = None,
    config: ContextualAnalysisConfig | None = None,
) -> ContextualDistortionAnalysis:
    """Compare test harmonics to a reference or declared single-tone stimulus."""
    if mode not in {"nominal_single_tone", "paired_reference"}:
        raise ValueError("mode must be nominal_single_tone or paired_reference")
    cfg = config or ContextualAnalysisConfig()
    rate = _validate_rate(sample_rate_hz)
    test = _as_1d(test_samples, name="test_samples")
    test_clip = analyze_clipping(
        test.astype(np.float32, copy=False),
        full_scale_threshold=cfg.full_scale_threshold,
    )

    if len(test) < cfg.min_samples:
        return _invalid(
            mode=mode,
            reason="test_too_short",
            test_clipping_mechanism=test_clip.clipping_mechanism,
            test_clipping_ratio=test_clip.clipping_ratio,
            test_flat_top_detected=test_clip.flat_top_detected,
        )

    if mode == "paired_reference":
        if reference_samples is None or reference_sample_rate_hz is None:
            raise ValueError("paired_reference requires reference samples and sample rate")
        ref_rate = _validate_rate(reference_sample_rate_hz)
        reference = _as_1d(reference_samples, name="reference_samples")
        ref_clip = analyze_clipping(
            reference.astype(np.float32, copy=False),
            full_scale_threshold=cfg.full_scale_threshold,
        )
        if ref_rate != rate:
            return _invalid(
                mode=mode,
                reason="sample_rate_mismatch",
                test_clipping_mechanism=test_clip.clipping_mechanism,
                test_clipping_ratio=test_clip.clipping_ratio,
                test_flat_top_detected=test_clip.flat_top_detected,
                reference_clipping_ratio=ref_clip.clipping_ratio,
                reference_flat_top_detected=ref_clip.flat_top_detected,
            )
        if len(reference) < cfg.min_samples:
            return _invalid(
                mode=mode,
                reason="reference_too_short",
                test_clipping_mechanism=test_clip.clipping_mechanism,
                test_clipping_ratio=test_clip.clipping_ratio,
                test_flat_top_detected=test_clip.flat_top_detected,
                reference_clipping_ratio=ref_clip.clipping_ratio,
                reference_flat_top_detected=ref_clip.flat_top_detected,
            )
        if ref_clip.clipping_mechanism:
            return _invalid(
                mode=mode,
                reason="reference_clipping_invalidates_comparison",
                test_clipping_mechanism=test_clip.clipping_mechanism,
                test_clipping_ratio=test_clip.clipping_ratio,
                test_flat_top_detected=test_clip.flat_top_detected,
                reference_clipping_ratio=ref_clip.clipping_ratio,
                reference_flat_top_detected=ref_clip.flat_top_detected,
            )

        # Qualify fundamentals before alignment so F0 mismatches surface clearly.
        pretest_harm = analyze_harmonic_distortion(
            test.astype(np.float32, copy=False),
            rate,
            max_harmonic_order=cfg.max_harmonic_order,
        )
        preref_harm = analyze_harmonic_distortion(
            reference.astype(np.float32, copy=False),
            rate,
            max_harmonic_order=cfg.max_harmonic_order,
        )
        if not pretest_harm.valid or pretest_harm.fundamental_frequency_hz is None:
            return _invalid(
                mode=mode,
                reason="test_fundamental_invalid",
                test_clipping_mechanism=test_clip.clipping_mechanism,
                test_clipping_ratio=test_clip.clipping_ratio,
                test_flat_top_detected=test_clip.flat_top_detected,
                reference_clipping_ratio=ref_clip.clipping_ratio,
                reference_flat_top_detected=ref_clip.flat_top_detected,
            )
        if not preref_harm.valid or preref_harm.fundamental_frequency_hz is None:
            return _invalid(
                mode=mode,
                reason="reference_fundamental_invalid",
                test_clipping_mechanism=test_clip.clipping_mechanism,
                test_clipping_ratio=test_clip.clipping_ratio,
                test_flat_top_detected=test_clip.flat_top_detected,
                reference_clipping_ratio=ref_clip.clipping_ratio,
                reference_flat_top_detected=ref_clip.flat_top_detected,
            )
        pretest_f0 = float(pretest_harm.fundamental_frequency_hz)
        preref_f0 = float(preref_harm.fundamental_frequency_hz)
        pretest_delta = abs(pretest_f0 - preref_f0) / preref_f0
        if pretest_delta > cfg.max_f0_relative_delta:
            return _invalid(
                mode=mode,
                reason="fundamental_incompatible",
                test_clipping_mechanism=test_clip.clipping_mechanism,
                test_clipping_ratio=test_clip.clipping_ratio,
                test_flat_top_detected=test_clip.flat_top_detected,
                reference_clipping_ratio=ref_clip.clipping_ratio,
                reference_flat_top_detected=ref_clip.flat_top_detected,
            )

        max_lag = round(cfg.max_lag_s * rate)
        lag, correlation = _bounded_xcorr_lag(reference, test, max_lag=max_lag)
        if correlation < cfg.min_alignment_correlation:
            return _invalid(
                mode=mode,
                reason="alignment_quality_below_threshold",
                test_clipping_mechanism=test_clip.clipping_mechanism,
                test_clipping_ratio=test_clip.clipping_ratio,
                test_flat_top_detected=test_clip.flat_top_detected,
                reference_clipping_ratio=ref_clip.clipping_ratio,
                reference_flat_top_detected=ref_clip.flat_top_detected,
            )
        aligned_test = _apply_lag(test, lag)
        aligned_ref = reference
        n = min(len(aligned_test), len(aligned_ref))
        aligned_test = aligned_test[:n]
        aligned_ref = aligned_ref[:n]
        gain = _gain_ratio(
            aligned_ref,
            aligned_test,
            full_scale_threshold=cfg.full_scale_threshold,
        )
        # Gain is diagnostic only; harmonic comparison uses per-signal normalization.
        test_harm = analyze_harmonic_distortion(
            aligned_test.astype(np.float32, copy=False),
            rate,
            max_harmonic_order=cfg.max_harmonic_order,
        )
        ref_harm = analyze_harmonic_distortion(
            aligned_ref.astype(np.float32, copy=False),
            rate,
            max_harmonic_order=cfg.max_harmonic_order,
        )
        if not test_harm.valid or test_harm.fundamental_frequency_hz is None:
            return _invalid(
                mode=mode,
                reason="test_fundamental_invalid",
                test_clipping_mechanism=test_clip.clipping_mechanism,
                test_clipping_ratio=test_clip.clipping_ratio,
                test_flat_top_detected=test_clip.flat_top_detected,
                reference_clipping_ratio=ref_clip.clipping_ratio,
                reference_flat_top_detected=ref_clip.flat_top_detected,
            )
        if not ref_harm.valid or ref_harm.fundamental_frequency_hz is None:
            return _invalid(
                mode=mode,
                reason="reference_fundamental_invalid",
                test_clipping_mechanism=test_clip.clipping_mechanism,
                test_clipping_ratio=test_clip.clipping_ratio,
                test_flat_top_detected=test_clip.flat_top_detected,
                reference_clipping_ratio=ref_clip.clipping_ratio,
                reference_flat_top_detected=ref_clip.flat_top_detected,
            )
        comparison_f0 = float(ref_harm.fundamental_frequency_hz)
        test_f0 = float(test_harm.fundamental_frequency_hz)
        f0_delta = abs(test_f0 - comparison_f0) / comparison_f0
        if f0_delta > cfg.max_f0_relative_delta:
            return _invalid(
                mode=mode,
                reason="fundamental_incompatible",
                test_clipping_mechanism=test_clip.clipping_mechanism,
                test_clipping_ratio=test_clip.clipping_ratio,
                test_flat_top_detected=test_clip.flat_top_detected,
                reference_clipping_ratio=ref_clip.clipping_ratio,
                reference_flat_top_detected=ref_clip.flat_top_detected,
            )
        test_map = _relative_map(test_harm)
        ref_map = _relative_map(ref_harm)
        components: list[HarmonicGrowthComponent] = []
        growth_even: list[float] = []
        for order in range(2, cfg.max_harmonic_order + 1):
            test_rel = float(test_map.get(order, 0.0))
            ref_rel = float(ref_map.get(order, 0.0))
            positive = max(test_rel - ref_rel, 0.0)
            components.append(
                HarmonicGrowthComponent(
                    order=order,
                    reference_relative_amplitude=ref_rel,
                    test_relative_amplitude=test_rel,
                    positive_growth=positive,
                )
            )
            if order % 2 == 0:
                growth_even.append(positive)
        even_growth_percent = 100.0 * float(np.sqrt(np.sum(np.square(growth_even))))
        test_thd = float(test_harm.thd_percent) if test_harm.thd_percent is not None else None
        ref_thd = float(ref_harm.thd_percent) if ref_harm.thd_percent is not None else None
        thd_delta = (
            None if test_thd is None or ref_thd is None else float(test_thd - ref_thd)
        )
        return ContextualDistortionAnalysis(
            algorithm_version="1.0.0",
            mode=mode,
            valid=True,
            invalid_reason=None,
            test_f0_hz=test_f0,
            comparison_f0_hz=comparison_f0,
            f0_relative_delta=float(f0_delta),
            alignment_lag_samples=int(lag),
            alignment_correlation=float(correlation),
            gain_ratio=float(gain),
            reference_thd_percent=ref_thd,
            test_thd_percent=test_thd,
            thd_delta_percent=thd_delta,
            even_harmonic_growth_percent=float(even_growth_percent),
            test_series_kind=test_harm.series_kind,
            components=tuple(components),
            reference_clipping_ratio=ref_clip.clipping_ratio,
            reference_flat_top_detected=ref_clip.flat_top_detected,
            test_clipping_mechanism=test_clip.clipping_mechanism,
            test_clipping_ratio=test_clip.clipping_ratio,
            test_flat_top_detected=test_clip.flat_top_detected,
        )

    # nominal_single_tone
    if nominal_fundamental_hz is None or (
        not np.isfinite(nominal_fundamental_hz) or nominal_fundamental_hz <= 0.0
    ):
        raise ValueError("nominal_single_tone requires finite positive nominal_fundamental_hz")
    if reference_samples is not None:
        raise ValueError("nominal_single_tone rejects reference_samples")
    test_harm = analyze_harmonic_distortion(
        test.astype(np.float32, copy=False),
        rate,
        max_harmonic_order=cfg.max_harmonic_order,
    )
    if not test_harm.valid or test_harm.fundamental_frequency_hz is None:
        return _invalid(
            mode=mode,
            reason="test_fundamental_invalid",
            test_clipping_mechanism=test_clip.clipping_mechanism,
            test_clipping_ratio=test_clip.clipping_ratio,
            test_flat_top_detected=test_clip.flat_top_detected,
        )
    test_f0 = float(test_harm.fundamental_frequency_hz)
    comparison_f0 = float(nominal_fundamental_hz)
    f0_delta = abs(test_f0 - comparison_f0) / comparison_f0
    if f0_delta > cfg.max_f0_relative_delta:
        return _invalid(
            mode=mode,
            reason="fundamental_incompatible_with_declaration",
            test_clipping_mechanism=test_clip.clipping_mechanism,
            test_clipping_ratio=test_clip.clipping_ratio,
            test_flat_top_detected=test_clip.flat_top_detected,
        )
    test_map = _relative_map(test_harm)
    components = []
    growth_even = []
    for order in range(2, cfg.max_harmonic_order + 1):
        test_rel = float(test_map.get(order, 0.0))
        positive = max(test_rel, 0.0)
        components.append(
            HarmonicGrowthComponent(
                order=order,
                reference_relative_amplitude=0.0,
                test_relative_amplitude=test_rel,
                positive_growth=positive,
            )
        )
        if order % 2 == 0:
            growth_even.append(positive)
    even_growth_percent = 100.0 * float(np.sqrt(np.sum(np.square(growth_even))))
    test_thd = float(test_harm.thd_percent) if test_harm.thd_percent is not None else None
    return ContextualDistortionAnalysis(
        algorithm_version="1.0.0",
        mode=mode,
        valid=True,
        invalid_reason=None,
        test_f0_hz=test_f0,
        comparison_f0_hz=comparison_f0,
        f0_relative_delta=float(f0_delta),
        alignment_lag_samples=0,
        alignment_correlation=1.0,
        gain_ratio=1.0,
        reference_thd_percent=0.0,
        test_thd_percent=test_thd,
        thd_delta_percent=test_thd,
        even_harmonic_growth_percent=float(even_growth_percent),
        test_series_kind=test_harm.series_kind,
        components=tuple(components),
        reference_clipping_ratio=None,
        reference_flat_top_detected=None,
        test_clipping_mechanism=test_clip.clipping_mechanism,
        test_clipping_ratio=test_clip.clipping_ratio,
        test_flat_top_detected=test_clip.flat_top_detected,
    )
