"""T-CX457–T-CX460, T-CX462: synchronized sweep stimulus and analysis (D054)."""

from __future__ import annotations

import hashlib
from collections.abc import Callable

import numpy as np
import pytest

from signal_diag.dsp.sweep import (
    BAND_CENTERS_HZ,
    SWEEP_STIMULUS_VERSION,
    SweepAnalysis,
    analyze_sweep_recording,
    generate_stimulus,
    stimulus_spec,
)

Device = Callable[[np.ndarray], np.ndarray]
A2, A3 = 0.1, 0.05


def _record(device: Device, rate: int = 48_000, *, lead_s: float = 0.2) -> SweepAnalysis:
    stimulus, _ = generate_stimulus(rate)
    response = device(stimulus)
    recording = np.concatenate(
        [np.zeros(int(lead_s * rate)), response, np.zeros(int(0.3 * rate))]
    )
    return analyze_sweep_recording(recording, rate)


def _bands(analysis: SweepAnalysis) -> dict[float, float | None]:
    return {
        band.center_hz: band.thd_percent for band in analysis.bands if band.measurable
    }


def _polynomial(samples: np.ndarray) -> np.ndarray:
    return samples + A2 * samples**2 + A3 * samples**3


def _analytic_thd_percent(amplitude: float = 0.5) -> float:
    fundamental = amplitude + 3 * A3 * amplitude**3 / 4
    second = A2 * amplitude**2 / 2
    third = A3 * amplitude**3 / 4
    return 100 * float(np.hypot(second, third)) / fundamental


def _biquad_high_pass(samples: np.ndarray, rate: int = 48_000, cutoff: float = 80.0) -> np.ndarray:
    w0 = 2 * np.pi * cutoff / rate
    alpha = np.sin(w0) / (2 * 0.707)
    cos = np.cos(w0)
    a0 = 1 + alpha
    b = np.array([(1 + cos) / 2, -(1 + cos), (1 + cos) / 2]) / a0
    a1, a2 = -2 * cos / a0, (1 - alpha) / a0
    out = np.zeros_like(samples)
    x1 = x2 = y1 = y2 = 0.0
    for index, value in enumerate(samples):
        y = b[0] * value + b[1] * x1 + b[2] * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, value, y1, y
        out[index] = y
    return out


def _chorus(samples: np.ndarray, rate: int = 48_000) -> np.ndarray:
    n = np.arange(len(samples))
    delay = (0.010 + 0.003 * np.sin(2 * np.pi * 0.5 * n / rate)) * rate
    position = n - delay
    base = np.clip(np.floor(position).astype(int), 0, len(samples) - 2)
    fraction = position - np.floor(position)
    delayed = (1 - fraction) * samples[base] + fraction * samples[base + 1]
    return 0.7 * samples + 0.3 * delayed


def _drift(samples: np.ndarray, ppm: float) -> np.ndarray:
    factor = 1 + ppm * 1e-6
    n = np.arange(int(len(samples) * factor))
    return np.interp(n / factor, np.arange(len(samples)), samples)


@pytest.mark.parametrize("rate", [44_100, 48_000])
def test_t_cx457_stimulus_is_versioned_and_deterministic(rate: int) -> None:
    first, spec = generate_stimulus(rate)
    second, _ = generate_stimulus(rate)
    assert spec.version == SWEEP_STIMULUS_VERSION == "sweep-stimulus-1.0"
    assert hashlib.sha256(first.tobytes()).digest() == hashlib.sha256(second.tobytes()).digest()
    assert spec.digest() == stimulus_spec(rate).digest()
    assert spec.sample_rate_hz == rate and (spec.f1_hz, spec.f2_hz) == (20.0, 20_000.0)
    assert 7.0 <= spec.sweep_samples / rate <= 9.0
    assert float(np.max(np.abs(first))) == pytest.approx(0.5, abs=1e-3)
    assert not first[: spec.pre_samples].any() and not first[-spec.post_samples :].any()
    assert spec.instantaneous_frequency(spec.pre_samples) == pytest.approx(20.0)
    with pytest.raises(ValueError):
        stimulus_spec(32_000)


def test_t_cx458_polynomial_thd_matches_the_analytic_value() -> None:
    expected = _analytic_thd_percent()
    bands = _bands(_record(_polynomial))
    for center in (250.0, 500.0, 1_000.0, 2_000.0, 4_000.0):
        assert bands[center] == pytest.approx(expected, abs=0.05), center


@pytest.mark.parametrize(
    "name,device",
    [
        ("identity", lambda s: s),
        ("chorus", _chorus),
        ("high_pass", _biquad_high_pass),
    ],
)
def test_t_cx458_linear_devices_show_no_distortion(name: str, device: Device) -> None:
    analysis = _record(device)
    assert analysis.valid and analysis.full_scale_ratio == 0.0
    for center, thd in _bands(analysis).items():
        if center >= 125.0:
            assert thd is not None and thd < 0.1, (name, center, thd)


def test_t_cx459_band_limited_distortion_is_localized() -> None:
    def low_band_clip(samples: np.ndarray) -> np.ndarray:
        size = 1 << int(np.ceil(np.log2(len(samples))))
        spectrum = np.fft.rfft(samples, size)
        freqs = np.fft.rfftfreq(size, 1 / 48_000)
        low = np.fft.irfft(np.where(freqs < 300.0, spectrum, 0), size)[: len(samples)]
        return np.clip(low, -0.3, 0.3) + (samples - low)

    bands = _bands(_record(low_band_clip))
    assert bands[125.0] is not None and bands[125.0] > 5.0
    assert bands[2_000.0] is not None and bands[2_000.0] < 1.0
    assert bands[4_000.0] is not None and bands[4_000.0] < 1.0


def test_t_cx459_clipping_shows_and_recorder_full_scale_maps_to_frequency() -> None:
    hard = _record(lambda s: np.clip(s, -0.4, 0.4))
    assert hard.full_scale_ratio == 0.0
    dominant = {band.dominant_order for band in hard.bands if band.measurable}
    assert dominant <= {3, 5}
    assert all(thd is not None and thd > 5.0 for c, thd in _bands(hard).items() if 125 <= c <= 2_000)

    soft = _record(lambda s: np.tanh(2 * s) / 2)
    assert all(thd is not None and thd > 5.0 for c, thd in _bands(soft).items() if 125 <= c <= 2_000)

    recorder = _record(lambda s: np.clip(2.5 * s, -1.0, 1.0))
    assert recorder.full_scale_ratio > 0.1
    span = recorder.clipped_frequency_hz
    assert span is not None and span[0] < 100.0 and span[1] > 10_000.0


@pytest.mark.parametrize("rate", [44_100, 48_000])
@pytest.mark.parametrize("lead_s", [0.0, 0.2, 1.5])
def test_t_cx460_delay_and_rate_do_not_change_results(rate: int, lead_s: float) -> None:
    analysis = _record(_polynomial, rate, lead_s=lead_s)
    assert analysis.valid and analysis.alignment_correlation > 0.99
    assert abs(analysis.drift_ppm or 0.0) < 20.0
    assert _bands(analysis)[1_000.0] == pytest.approx(_analytic_thd_percent(), abs=0.05)


def test_t_cx460_quality_signals_are_reported() -> None:
    rng = np.random.default_rng(20261007)
    stimulus, _ = generate_stimulus(48_000)
    wrong = analyze_sweep_recording(0.3 * rng.standard_normal(len(stimulus)), 48_000)
    assert wrong.alignment_correlation < 0.05

    noisy = _record(lambda s: s + 0.05 * rng.standard_normal(len(s)))
    assert noisy.snr_db is not None and noisy.snr_db < 30.0
    assert any(not band.measurable for band in noisy.bands if band.center_hz >= 500.0)

    drifted = _record(lambda s: _drift(s, 500.0))
    assert drifted.drift_ppm is not None and drifted.drift_ppm > 200.0
    slight = _record(lambda s: _drift(s, 50.0))
    assert slight.drift_ppm is not None and abs(slight.drift_ppm) < 100.0
    high_pass = _record(_biquad_high_pass)
    assert abs(high_pass.drift_ppm or 0.0) < 50.0

    truncated = analyze_sweep_recording(stimulus[: len(stimulus) // 2], 48_000)
    assert not truncated.valid and truncated.invalid_reason == "recording_truncated"
    non_finite = analyze_sweep_recording(np.full(len(stimulus), np.nan), 48_000)
    assert not non_finite.valid and non_finite.invalid_reason == "non_finite_samples"


def test_t_cx460_bands_cover_the_octaves_and_respect_nyquist() -> None:
    analysis = _record(_polynomial, 44_100)
    assert tuple(band.center_hz for band in analysis.bands) == BAND_CENTERS_HZ
    by_center = {band.center_hz: band for band in analysis.bands}
    assert not by_center[16_000.0].measurable and by_center[16_000.0].orders_used == ()
    assert by_center[4_000.0].orders_used == (2, 3)
    assert not by_center[8_000.0].measurable and by_center[8_000.0].orders_used == ()


def test_t_cx462_analysis_is_deterministic() -> None:
    first = _record(_polynomial)
    second = _record(_polynomial)
    assert first == second


def _butter_low_pass(samples: np.ndarray, rate: int = 48_000, cutoff: float = 1_500.0) -> np.ndarray:
    w0 = 2 * np.pi * cutoff / rate
    alpha = np.sin(w0) / (2 * 0.7071)
    cos = np.cos(w0)
    a0 = 1 + alpha
    b = np.array([(1 - cos) / 2, 1 - cos, (1 - cos) / 2]) / a0
    a1, a2 = -2 * cos / a0, (1 - alpha) / a0
    out = np.zeros_like(samples)
    x1 = x2 = y1 = y2 = 0.0
    for index, value in enumerate(samples):
        y = b[0] * value + b[1] * x1 + b[2] * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, value, y1, y
        out[index] = y
    return out


def _steady_tone_thd_percent(device: Device, frequency: float, rate: int = 48_000) -> float:
    t = np.arange(rate) / rate
    settled = device(0.5 * np.sin(2 * np.pi * frequency * t))[rate // 2 :]
    spectrum = np.abs(np.fft.rfft(settled * np.hanning(len(settled))))
    freqs = np.fft.rfftfreq(len(settled), 1 / rate)

    def amplitude(target: float) -> float:
        return float(spectrum[np.argmin(np.abs(freqs - target))])

    harmonics = sum(amplitude(n * frequency) ** 2 for n in range(2, 6))
    return 100 * float(np.sqrt(harmonics)) / amplitude(frequency)


def test_t_cx458_harmonics_are_read_at_their_own_frequency() -> None:
    """A filter after the nonlinearity changes THD with frequency (Hammerstein)."""

    def device(samples: np.ndarray) -> np.ndarray:
        return _butter_low_pass(_polynomial(samples))

    bands = _bands(_record(device))
    for center in (250.0, 500.0, 1_000.0, 2_000.0):
        expected = _steady_tone_thd_percent(device, center)
        assert bands[center] == pytest.approx(expected, rel=0.15, abs=0.05), center
    assert bands[2_000.0] is not None and bands[250.0] is not None
    assert bands[2_000.0] < 0.5 * bands[250.0]
