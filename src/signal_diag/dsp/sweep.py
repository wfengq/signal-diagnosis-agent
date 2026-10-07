"""Synchronized exponential swept-sine stimulus and analysis (D054).

Follows Novak, Lotton and Simon, "Synchronized Swept-Sine: Theory, Application,
and Implementation", JAES 63(10), 2015. The stimulus is deterministic; the
recording of a device's response is aligned to it, deconvolved with the
sweep's analytic inverse spectrum, and split into the linear response and the
harmonic responses of orders 2–5, which land at separate, known delays.
Numerical results come only from this module (numpy only).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import numpy as np

SWEEP_STIMULUS_VERSION = "sweep-stimulus-1.0"
SWEEP_ANALYSIS_VERSION = "sweep-analysis-1.0"
SUPPORTED_RATES = (44_100, 48_000)
F1_HZ = 20.0
F2_HZ = 20_000.0
TARGET_DURATION_S = 8.0
PEAK = 0.5  # -6 dBFS
FADE_S = 0.05
PRE_SILENCE_S = 0.5
POST_SILENCE_S = 1.0
MAX_ORDER = 5
IR_WINDOW_S = 0.05
MAX_SEARCH_S = 2.0
BAND_CENTERS_HZ = (63.0, 125.0, 250.0, 500.0, 1_000.0, 2_000.0, 4_000.0, 8_000.0, 16_000.0)
FULL_SCALE_THRESHOLD = 0.99
MIN_FULL_SCALE_RUN = 2
_SPECTRUM_SIZE = 1 << 15


@dataclass(frozen=True, slots=True)
class SweepStimulusSpec:
    version: str
    sample_rate_hz: int
    f1_hz: float
    f2_hz: float
    rate_l: float
    sweep_samples: int
    pre_samples: int
    post_samples: int
    peak: float

    @property
    def total_samples(self) -> int:
        return self.pre_samples + self.sweep_samples + self.post_samples

    def digest(self) -> str:
        payload = json.dumps(
            {
                "version": self.version,
                "sample_rate_hz": self.sample_rate_hz,
                "f1_hz": self.f1_hz,
                "f2_hz": self.f2_hz,
                "rate_l": round(self.rate_l, 12),
                "sweep_samples": self.sweep_samples,
                "pre_samples": self.pre_samples,
                "post_samples": self.post_samples,
                "peak": self.peak,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def instantaneous_frequency(self, sample_index: int) -> float:
        """Sweep frequency at an index of the stimulus (pre-silence included)."""
        t = (sample_index - self.pre_samples) / self.sample_rate_hz
        return float(self.f1_hz * np.exp(t / self.rate_l))


def stimulus_spec(sample_rate_hz: int) -> SweepStimulusSpec:
    if sample_rate_hz not in SUPPORTED_RATES:
        raise ValueError(f"sample rate must be one of {SUPPORTED_RATES}")
    # Synchronization (Novak 2015): L = round(f1 T / ln(f2/f1)) / f1.
    rate_l = round(F1_HZ * TARGET_DURATION_S / np.log(F2_HZ / F1_HZ)) / F1_HZ
    duration = rate_l * np.log(F2_HZ / F1_HZ)
    return SweepStimulusSpec(
        version=SWEEP_STIMULUS_VERSION,
        sample_rate_hz=sample_rate_hz,
        f1_hz=F1_HZ,
        f2_hz=F2_HZ,
        rate_l=float(rate_l),
        sweep_samples=round(duration * sample_rate_hz),
        pre_samples=round(PRE_SILENCE_S * sample_rate_hz),
        post_samples=round(POST_SILENCE_S * sample_rate_hz),
        peak=PEAK,
    )


def _sweep(spec: SweepStimulusSpec) -> np.ndarray:
    t = np.arange(spec.sweep_samples) / spec.sample_rate_hz
    sweep = np.sin(2 * np.pi * spec.f1_hz * spec.rate_l * np.exp(t / spec.rate_l))
    fade = round(FADE_S * spec.sample_rate_hz)
    ramp = 0.5 - 0.5 * np.cos(np.pi * np.arange(fade) / fade)
    window = np.ones(spec.sweep_samples)
    window[:fade] = ramp
    window[-fade:] = ramp[::-1]
    return spec.peak * sweep * window


def generate_stimulus(sample_rate_hz: int) -> tuple[np.ndarray, SweepStimulusSpec]:
    """The versioned stimulus: silence, synchronized sweep, silence (mono float64)."""
    spec = stimulus_spec(sample_rate_hz)
    samples = np.concatenate(
        [np.zeros(spec.pre_samples), _sweep(spec), np.zeros(spec.post_samples)]
    )
    return samples, spec


@dataclass(frozen=True, slots=True)
class BandResult:
    center_hz: float
    measurable: bool
    thd_percent: float | None
    noise_floor_percent: float | None
    dominant_order: int | None
    orders_used: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class SweepAnalysis:
    version: str
    stimulus_digest: str
    valid: bool
    invalid_reason: str | None
    alignment_lag_samples: int | None
    alignment_correlation: float
    drift_ppm: float | None
    snr_db: float | None
    full_scale_ratio: float
    clipped_frequency_hz: tuple[float, float] | None
    bands: tuple[BandResult, ...]


def _xcorr_lag(reference: np.ndarray, signal: np.ndarray, max_lag: int) -> tuple[int, float]:
    """Best non-negative lag of ``reference`` inside ``signal`` and its normalized peak."""
    n = len(signal)
    size = 1 << int(np.ceil(np.log2(n + len(reference))))
    corr = np.fft.irfft(np.fft.rfft(signal, size) * np.conj(np.fft.rfft(reference, size)), size)
    window = corr[: max_lag + 1]
    lag = int(np.argmax(window))
    segment = signal[lag : lag + len(reference)]
    if len(segment) < len(reference):
        segment = np.pad(segment, (0, len(reference) - len(segment)))
    denominator = float(np.linalg.norm(reference) * np.linalg.norm(segment))
    score = float(window[lag] / denominator) if denominator > 0 else 0.0
    return lag, score


def _inverse_spectrum(spec: SweepStimulusSpec, freqs: np.ndarray) -> np.ndarray:
    """Analytic spectrum of the synchronized sweep (Novak 2015, eq. 42)."""
    out = np.zeros(freqs.shape, dtype=complex)
    nonzero = freqs > 0
    f = freqs[nonzero]
    out[nonzero] = (
        0.5
        * np.sqrt(f / spec.rate_l)
        * np.exp(1j * 2 * np.pi * f * spec.rate_l * (1 - np.log(f / spec.f1_hz)) - 1j * np.pi / 4)
    )
    return out


def _harmonic_spectra(
    aligned: np.ndarray, spec: SweepStimulusSpec
) -> tuple[np.ndarray, dict[int, np.ndarray], np.ndarray]:
    rate = spec.sample_rate_hz
    size = 1 << int(np.ceil(np.log2(2 * len(aligned))))
    freqs = np.fft.rfftfreq(size, 1 / rate)
    sweep_spectrum = _inverse_spectrum(spec, freqs)
    recorded = np.fft.rfft(aligned, size)
    band = (freqs >= spec.f1_hz) & (freqs <= spec.f2_hz)
    response = np.zeros_like(recorded)
    response[band] = recorded[band] / sweep_spectrum[band] / spec.peak
    impulse = np.fft.irfft(response, size)
    window = round(IR_WINDOW_S * rate)
    taper = np.hanning(window)
    spectra: dict[int, np.ndarray] = {}
    for order in range(1, MAX_ORDER + 1):
        delay = round(spec.rate_l * np.log(order) * rate)
        start = (spec.pre_samples - delay - window // 4) % size
        index = (start + np.arange(window)) % size
        spectra[order] = np.fft.rfft(impulse[index] * taper, _SPECTRUM_SIZE)
    # Noise reference: a window well after the linear response, before the
    # harmonic responses that wrap around to the end of the buffer.
    noise_start = spec.pre_samples + round(0.3 * rate)
    noise_index = (noise_start + np.arange(window)) % size
    noise = np.fft.rfft(impulse[noise_index] * taper, _SPECTRUM_SIZE)
    return np.fft.rfftfreq(_SPECTRUM_SIZE, 1 / rate), spectra, noise


def _bands(
    freqs: np.ndarray, spectra: dict[int, np.ndarray], noise: np.ndarray, rate: int
) -> tuple[BandResult, ...]:
    nyquist = rate / 2
    results: list[BandResult] = []
    for center in BAND_CENTERS_HZ:
        low, high = center / np.sqrt(2), center * np.sqrt(2)
        mask = (freqs >= low) & (freqs < high)
        orders = tuple(n for n in range(2, MAX_ORDER + 1) if n * high < nyquist)
        linear = float(np.sqrt(np.mean(np.abs(spectra[1][mask]) ** 2))) if mask.any() else 0.0
        if not orders or linear <= 0.0:
            results.append(BandResult(center, False, None, None, None, orders))
            continue
        energies = {n: float(np.mean(np.abs(spectra[n][mask]) ** 2)) for n in orders}
        thd = 100.0 * float(np.sqrt(sum(energies.values()))) / linear
        floor = 100.0 * float(np.sqrt(np.mean(np.abs(noise[mask]) ** 2) * len(orders))) / linear
        dominant = max(energies, key=lambda n: energies[n])
        results.append(
            BandResult(
                center_hz=center,
                measurable=floor <= 0.5,
                thd_percent=round(thd, 4),
                noise_floor_percent=round(floor, 4),
                dominant_order=dominant,
                orders_used=orders,
            )
        )
    return tuple(results)


def _full_scale_mask(values: np.ndarray) -> np.ndarray:
    """Samples in runs of at least ``MIN_FULL_SCALE_RUN`` at or above full scale.

    The flat-top detector of ``dsp.clipping`` is not used: slow low-frequency
    sweep crests look flat to it, so only the recorder's full scale counts here.
    """
    hot = np.abs(values) >= FULL_SCALE_THRESHOLD
    padded = np.pad(hot, (1, 1)).astype(np.int8)
    edges = np.diff(padded)
    mask = np.zeros(hot.shape, dtype=bool)
    for start, stop in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1), strict=True):
        if stop - start >= MIN_FULL_SCALE_RUN:
            mask[start:stop] = True
    return mask


def _clipped_span(
    mask: np.ndarray, spec: SweepStimulusSpec
) -> tuple[float, float] | None:
    indices = np.flatnonzero(mask)
    if indices.size == 0:
        return None
    first = spec.instantaneous_frequency(spec.pre_samples + int(indices[0]))
    last = spec.instantaneous_frequency(spec.pre_samples + int(indices[-1]))
    return (round(first, 1), round(last, 1))


def analyze_sweep_recording(recording: np.ndarray, sample_rate_hz: int) -> SweepAnalysis:
    """Analyse a mono recording of a device driven by the versioned stimulus.

    Only structural problems (non-finite samples, a truncated recording) make
    the analysis invalid here; alignment quality, clock drift and SNR are
    reported and judged by the versioned sweep rule profile.
    """
    values = np.asarray(recording, dtype=np.float64).reshape(-1)
    spec = stimulus_spec(sample_rate_hz)
    digest = spec.digest()

    def invalid(reason: str, **fields: object) -> SweepAnalysis:
        base: dict[str, object] = {
            "alignment_lag_samples": None,
            "alignment_correlation": 0.0,
            "drift_ppm": None,
            "snr_db": None,
            "full_scale_ratio": 0.0,
            "clipped_frequency_hz": None,
        }
        base.update(fields)
        return SweepAnalysis(
            version=SWEEP_ANALYSIS_VERSION,
            stimulus_digest=digest,
            valid=False,
            invalid_reason=reason,
            bands=(),
            **base,  # type: ignore[arg-type]
        )

    if not np.all(np.isfinite(values)):
        return invalid("non_finite_samples")
    sweep = _sweep(spec)
    max_lag = round(MAX_SEARCH_S * sample_rate_hz)
    lag, correlation = _xcorr_lag(sweep, values, max_lag)
    start = lag - spec.pre_samples
    if start < 0 or lag + spec.sweep_samples > len(values):
        return invalid(
            "recording_truncated",
            alignment_lag_samples=lag,
            alignment_correlation=round(correlation, 6),
        )
    aligned = values[start : start + spec.total_samples]
    if len(aligned) < spec.total_samples:
        aligned = np.pad(aligned, (0, spec.total_samples - len(aligned)))
    # Clock drift from two segments above typical high-pass corners and below
    # low-pass corners (about 0.9–1.8 kHz and 5–10 kHz), where devices'
    # frequency-dependent delay is small.
    segment = spec.sweep_samples // 10
    first_at = int(0.55 * spec.sweep_samples)
    second_at = int(0.80 * spec.sweep_samples)
    first_lag, _ = _xcorr_lag(sweep[first_at : first_at + segment], values, max_lag + first_at)
    second_lag, _ = _xcorr_lag(sweep[second_at : second_at + segment], values, max_lag + second_at)
    drift = 1e6 * ((second_lag - first_lag) - (second_at - first_at)) / (second_at - first_at)
    sweep_part = aligned[spec.pre_samples : spec.pre_samples + spec.sweep_samples]
    noise_part = aligned[: spec.pre_samples]
    signal_rms = float(np.sqrt(np.mean(sweep_part**2)))
    noise_rms = float(np.sqrt(np.mean(noise_part**2)))
    snr = 200.0 if noise_rms == 0.0 else 20.0 * float(np.log10(max(signal_rms, 1e-12) / noise_rms))
    full_scale = _full_scale_mask(sweep_part)
    common = {
        "alignment_lag_samples": lag,
        "alignment_correlation": round(correlation, 6),
        "drift_ppm": round(drift, 3),
        "snr_db": round(min(snr, 200.0), 3),
        "full_scale_ratio": round(float(np.mean(full_scale)), 6),
        "clipped_frequency_hz": _clipped_span(full_scale, spec),
    }
    freqs, spectra, noise = _harmonic_spectra(aligned, spec)
    return SweepAnalysis(
        version=SWEEP_ANALYSIS_VERSION,
        stimulus_digest=digest,
        valid=True,
        invalid_reason=None,
        bands=_bands(freqs, spectra, noise, sample_rate_hz),
        **common,  # type: ignore[arg-type]
    )


__all__ = [
    "BAND_CENTERS_HZ",
    "SUPPORTED_RATES",
    "SWEEP_ANALYSIS_VERSION",
    "SWEEP_STIMULUS_VERSION",
    "BandResult",
    "SweepAnalysis",
    "SweepStimulusSpec",
    "analyze_sweep_recording",
    "generate_stimulus",
    "stimulus_spec",
]
