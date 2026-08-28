"""Deterministic synthetic signal generation with recorded ground truth."""

from dataclasses import dataclass

import numpy as np
from pydantic import BaseModel, ConfigDict

from .exceptions import InvalidSignalError
from .factory import build_signal_record
from .models import FaultLabel, SignalRecord

GroundTruthValue = str | int | float | bool | dict[str, float]


class SyntheticGroundTruth(BaseModel):
    """The generator identity, fault labels, and parameters of a synthetic case."""

    model_config = ConfigDict(frozen=True)

    generator: str
    fault_labels: tuple[FaultLabel, ...] = ()
    parameters: dict[str, GroundTruthValue]


@dataclass(frozen=True, slots=True)
class SyntheticCase:
    """A canonical generated record paired with its known ground truth."""

    record: SignalRecord
    ground_truth: SyntheticGroundTruth


def _sample_count(sample_rate_hz: int, duration_s: float) -> int:
    if sample_rate_hz <= 0:
        raise InvalidSignalError("sample_rate_hz must be positive")
    if duration_s <= 0:
        raise InvalidSignalError("duration_s must be positive")
    num_samples = round(duration_s * sample_rate_hz)
    if num_samples <= 0:
        raise InvalidSignalError("duration_s and sample_rate_hz must produce samples")
    return num_samples


def _time_axis(sample_rate_hz: int, duration_s: float) -> np.ndarray:
    num_samples = _sample_count(sample_rate_hz, duration_s)
    return np.arange(num_samples, dtype=np.float64) / sample_rate_hz


def _as_case(
    waveform: np.ndarray,
    *,
    sample_rate_hz: int,
    ground_truth: SyntheticGroundTruth,
) -> SyntheticCase:
    record = build_signal_record(
        waveform,
        sample_rate_hz=sample_rate_hz,
        source_type="generated",
    )
    return SyntheticCase(record=record, ground_truth=ground_truth)


def _require_positive(name: str, value: float) -> None:
    if value <= 0:
        raise InvalidSignalError(f"{name} must be positive")


def _validate_clip_level(clip_level: float) -> None:
    if not 0 < clip_level <= 1:
        raise InvalidSignalError("clip_level must be greater than 0 and at most 1")


def _harmonic_waveform(
    *,
    fundamental_hz: float,
    harmonic_ratios: dict[int, float],
    sample_rate_hz: int,
    duration_s: float,
    fundamental_amplitude: float,
) -> np.ndarray:
    _require_positive("fundamental_hz", fundamental_hz)
    if not harmonic_ratios:
        raise InvalidSignalError("harmonic_ratios must not be empty")

    has_positive_ratio = False
    for order, ratio in harmonic_ratios.items():
        if type(order) is not int or order < 2:
            raise InvalidSignalError("harmonic orders must be integers of at least 2")
        if not np.isfinite(ratio) or ratio < 0:
            raise InvalidSignalError("harmonic ratios must be finite and non-negative")
        has_positive_ratio = has_positive_ratio or ratio > 0
    if not has_positive_ratio:
        raise InvalidSignalError("at least one harmonic ratio must be positive")

    t = _time_axis(sample_rate_hz, duration_s)
    waveform = fundamental_amplitude * np.sin(2 * np.pi * fundamental_hz * t)
    for order, ratio in sorted(harmonic_ratios.items()):
        waveform = waveform + fundamental_amplitude * ratio * np.sin(
            2 * np.pi * order * fundamental_hz * t
        )
    return waveform


def generate_sine(
    *,
    frequency_hz: float,
    sample_rate_hz: int = 48_000,
    duration_s: float = 2.0,
    amplitude: float = 0.5,
    phase_rad: float = 0.0,
    dc_offset: float = 0.0,
) -> SyntheticCase:
    """Generate a clean sine without normalization or injected faults."""
    _require_positive("frequency_hz", frequency_hz)
    t = _time_axis(sample_rate_hz, duration_s)
    waveform = amplitude * np.sin(2 * np.pi * frequency_hz * t + phase_rad) + dc_offset

    parameters: dict[str, GroundTruthValue] = {
        "sample_rate_hz": sample_rate_hz,
        "duration_s": duration_s,
        "frequency_hz": frequency_hz,
        "amplitude": amplitude,
        "phase_rad": phase_rad,
        "dc_offset": dc_offset,
    }
    return _as_case(
        waveform,
        sample_rate_hz=sample_rate_hz,
        ground_truth=SyntheticGroundTruth(generator="sine", parameters=parameters),
    )


def generate_clipped_sine(
    *,
    frequency_hz: float,
    clip_level: float,
    sample_rate_hz: int = 48_000,
    duration_s: float = 2.0,
    amplitude: float = 0.9,
) -> SyntheticCase:
    """Generate a symmetrically hard-clipped sine retaining its clipping fault."""
    _require_positive("frequency_hz", frequency_hz)
    _validate_clip_level(clip_level)
    t = _time_axis(sample_rate_hz, duration_s)
    clean = amplitude * np.sin(2 * np.pi * frequency_hz * t)
    waveform = np.clip(clean, -clip_level, clip_level)

    parameters: dict[str, GroundTruthValue] = {
        "sample_rate_hz": sample_rate_hz,
        "duration_s": duration_s,
        "frequency_hz": frequency_hz,
        "input_amplitude": amplitude,
        "clip_level": clip_level,
    }
    return _as_case(
        waveform,
        sample_rate_hz=sample_rate_hz,
        ground_truth=SyntheticGroundTruth(
            generator="clipped_sine",
            fault_labels=("clipping",),
            parameters=parameters,
        ),
    )


def generate_harmonic_sine(
    *,
    fundamental_hz: float,
    harmonic_ratios: dict[int, float],
    sample_rate_hz: int = 48_000,
    duration_s: float = 2.0,
    fundamental_amplitude: float = 0.5,
) -> SyntheticCase:
    """Generate a sine with explicit harmonic amplitude ratios."""
    waveform = _harmonic_waveform(
        fundamental_hz=fundamental_hz,
        harmonic_ratios=harmonic_ratios,
        sample_rate_hz=sample_rate_hz,
        duration_s=duration_s,
        fundamental_amplitude=fundamental_amplitude,
    )
    serialized_ratios = {str(order): ratio for order, ratio in harmonic_ratios.items()}
    parameters: dict[str, GroundTruthValue] = {
        "sample_rate_hz": sample_rate_hz,
        "duration_s": duration_s,
        "fundamental_hz": fundamental_hz,
        "fundamental_amplitude": fundamental_amplitude,
        "harmonic_ratios": serialized_ratios,
    }
    return _as_case(
        waveform,
        sample_rate_hz=sample_rate_hz,
        ground_truth=SyntheticGroundTruth(
            generator="harmonic_sine",
            fault_labels=("harmonic_distortion",),
            parameters=parameters,
        ),
    )


def generate_combined_distortion(
    *,
    fundamental_hz: float,
    harmonic_ratios: dict[int, float],
    clip_level: float,
    sample_rate_hz: int = 48_000,
    duration_s: float = 2.0,
    fundamental_amplitude: float = 0.9,
) -> SyntheticCase:
    """Generate harmonic distortion followed by symmetric hard clipping."""
    _validate_clip_level(clip_level)
    harmonic = _harmonic_waveform(
        fundamental_hz=fundamental_hz,
        harmonic_ratios=harmonic_ratios,
        sample_rate_hz=sample_rate_hz,
        duration_s=duration_s,
        fundamental_amplitude=fundamental_amplitude,
    )
    waveform = np.clip(harmonic, -clip_level, clip_level)
    serialized_ratios = {str(order): ratio for order, ratio in harmonic_ratios.items()}
    parameters: dict[str, GroundTruthValue] = {
        "sample_rate_hz": sample_rate_hz,
        "duration_s": duration_s,
        "fundamental_hz": fundamental_hz,
        "fundamental_amplitude": fundamental_amplitude,
        "harmonic_ratios": serialized_ratios,
        "clip_level": clip_level,
    }
    return _as_case(
        waveform,
        sample_rate_hz=sample_rate_hz,
        ground_truth=SyntheticGroundTruth(
            generator="combined_distortion",
            fault_labels=("clipping", "harmonic_distortion"),
            parameters=parameters,
        ),
    )


def generate_white_noise(
    *,
    sample_rate_hz: int = 48_000,
    duration_s: float = 2.0,
    rms: float = 0.1,
    seed: int = 0,
) -> SyntheticCase:
    """Generate seeded Gaussian noise without normalizing the realization."""
    _require_positive("rms", rms)
    num_samples = _sample_count(sample_rate_hz, duration_s)
    waveform = np.random.default_rng(seed).normal(0.0, rms, size=num_samples)

    parameters: dict[str, GroundTruthValue] = {
        "sample_rate_hz": sample_rate_hz,
        "duration_s": duration_s,
        "rms": rms,
        "seed": seed,
    }
    return _as_case(
        waveform,
        sample_rate_hz=sample_rate_hz,
        ground_truth=SyntheticGroundTruth(
            generator="white_noise",
            fault_labels=("noise",),
            parameters=parameters,
        ),
    )
