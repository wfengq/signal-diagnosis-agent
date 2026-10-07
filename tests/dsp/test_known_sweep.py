"""T-CX477–T-CX479: analysis of a known external exponential sweep (D056)."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pytest

from signal_diag.dsp.sweep import (
    KNOWN_SWEEP_ANALYSIS_VERSION,
    analyze_known_sweep,
    estimate_sweep_rate,
    generate_stimulus,
    stimulus_spec,
)
from tests.dsp.test_sweep import _butter_low_pass, _steady_tone_thd_percent

RATE = 48_000
Device = Callable[[np.ndarray], np.ndarray]


def _external_sweep(
    f1: float = 5.0, f2: float = 24_000.0, seconds: float = 4.0, peak: float = 0.63
) -> np.ndarray:
    """A pOD-set-like stimulus: exponential, no silence, not synchronized."""
    rate_l = seconds / np.log(f2 / f1)
    t = np.arange(int(seconds * RATE)) / RATE
    return peak * np.sin(2 * np.pi * f1 * rate_l * (np.exp(t / rate_l) - 1) + 0.3)


def _poly(samples: np.ndarray) -> np.ndarray:
    return samples + 0.1 * samples**2 + 0.05 * samples**3


def alias_free(device: Device, samples: np.ndarray, factor: int = 4) -> np.ndarray:
    """Apply ``device`` at 4x the rate and band-limit, as an analog device recorded
    through an anti-aliasing filter would be. A digital nonlinearity on a sweep
    up to 24 kHz otherwise folds harmonics back below Nyquist."""
    n = len(samples)
    spectrum = np.fft.rfft(samples)
    upsampled = np.zeros(n * factor // 2 + 1, dtype=complex)
    upsampled[: len(spectrum)] = spectrum
    output = device(np.fft.irfft(upsampled, n * factor) * factor)
    return np.fft.irfft(np.fft.rfft(output)[: len(spectrum)], n) / factor


def _analytic(amplitude: float) -> float:
    fundamental = amplitude + 3 * 0.05 * amplitude**3 / 4
    return 100 * float(np.hypot(0.1 * amplitude**2 / 2, 0.05 * amplitude**3 / 4)) / fundamental


def _bands(stimulus: np.ndarray, recording: np.ndarray) -> dict[float, float | None]:
    analysis = analyze_known_sweep(recording, stimulus, RATE)
    return {band.center_hz: band.thd_percent for band in analysis.bands if band.measurable}


def test_t_cx477_rate_estimate_matches_the_sweep_law() -> None:
    external = _external_sweep()
    rate_l, f_start = estimate_sweep_rate(external, RATE)
    assert rate_l == pytest.approx(4.0 / np.log(24_000 / 5.0), rel=0.005)
    assert f_start == pytest.approx(5.0, rel=0.05)
    ours, spec = generate_stimulus(RATE)
    sweep = ours[spec.pre_samples : spec.pre_samples + spec.sweep_samples]
    assert estimate_sweep_rate(sweep, RATE)[0] == pytest.approx(stimulus_spec(RATE).rate_l, rel=0.005)
    with pytest.raises(ValueError):
        estimate_sweep_rate(np.zeros(RATE), RATE)


def test_t_cx478_synthetic_devices_on_an_external_sweep() -> None:
    stimulus = _external_sweep()
    analysis = analyze_known_sweep(stimulus, stimulus, RATE)
    assert analysis.version == KNOWN_SWEEP_ANALYSIS_VERSION == "known-sweep-analysis-1.0"
    for center, thd in _bands(stimulus, stimulus).items():
        assert thd is not None and thd <= 0.05, center
    expected = _analytic(0.63)
    poly = _bands(stimulus, alias_free(_poly, stimulus))
    for center in (125.0, 250.0, 500.0, 1_000.0, 2_000.0, 4_000.0):
        assert poly[center] == pytest.approx(expected, abs=0.1), center

    def filtered(samples: np.ndarray) -> np.ndarray:
        return _butter_low_pass(_poly(samples))

    bands = _bands(stimulus, _butter_low_pass(alias_free(_poly, stimulus)))
    for center in (250.0, 500.0, 1_000.0, 2_000.0):
        target = _steady_tone_thd_percent(lambda s: filtered(s / 0.5 * 0.63), center)
        assert bands[center] == pytest.approx(target, rel=0.15, abs=0.05), center


def test_t_cx479_dataset_format_lag_scaling_and_determinism() -> None:
    stimulus = _external_sweep(peak=0.16)
    device: Device = lambda s: np.tanh(8 * s) / 8
    response = alias_free(device, stimulus)
    delayed = np.concatenate([np.zeros(40), response])[: len(stimulus)]
    normalized = 0.9 * delayed / np.max(np.abs(delayed))
    first = analyze_known_sweep(normalized, stimulus, RATE)
    assert first.lag_samples == 40
    reference = _bands(stimulus, response)
    for band in first.bands:
        if band.measurable and band.center_hz in reference and band.center_hz <= 4_000:
            assert band.thd_percent == pytest.approx(reference[band.center_hz], rel=0.02, abs=0.02)
    assert first == analyze_known_sweep(normalized, stimulus, RATE)
    with pytest.raises(ValueError):
        analyze_known_sweep(normalized[:1000], stimulus, RATE)
