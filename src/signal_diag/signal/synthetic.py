"""Deterministic synthetic signal generation with recorded ground truth."""

from dataclasses import dataclass

import numpy as np
from pydantic import BaseModel, ConfigDict

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
    return round(duration_s * sample_rate_hz)


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


def generate_white_noise(
    *,
    sample_rate_hz: int = 48_000,
    duration_s: float = 2.0,
    rms: float = 0.1,
    seed: int = 0,
) -> SyntheticCase:
    """Generate seeded Gaussian noise without normalizing the realization."""
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
