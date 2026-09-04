"""Frozen result containers for deterministic DSP analysis."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class ClippingAnalysis:
    detected: bool
    clipping_ratio: float
    clipped_samples: int
    clipping_events: int
    longest_event_samples: int
    peak_abs: float
    full_scale_detected: bool
    flat_top_detected: bool
    clipping_mechanism: bool


@dataclass(frozen=True, slots=True)
class SpectrumPeak:
    frequency_hz: float
    magnitude_db: float


@dataclass(frozen=True, slots=True)
class FFTAnalysis:
    frequencies_hz: np.ndarray
    magnitude_db: np.ndarray
    frequency_resolution_hz: float
    dominant_frequency_hz: float | None
    dominant_magnitude_db: float | None
    spectral_centroid_hz: float | None
    peaks: tuple[SpectrumPeak, ...]


@dataclass(frozen=True, slots=True)
class F0Estimate:
    f0_hz: float | None
    confidence: float
    voiced: bool
    method: str
    f0_reliability: str | None = None
    octave_ambiguity_detected: bool = False


@dataclass(frozen=True, slots=True)
class HarmonicComponent:
    order: int
    target_frequency_hz: float
    measured_frequency_hz: float
    relative_amplitude: float
    relative_magnitude_db: float


@dataclass(frozen=True, slots=True)
class HarmonicAnalysis:
    valid: bool
    invalid_reason: str | None
    fundamental_frequency_hz: float | None
    fundamental_amplitude: float | None
    thd_percent: float | None
    max_harmonic_order: int
    frequency_resolution_hz: float
    components: tuple[HarmonicComponent, ...]
    fundamental_relative_energy: float | None = None
    octave_ambiguity_detected: bool = False
    series_kind: str | None = None
