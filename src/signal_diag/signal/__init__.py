"""Signal representation and construction."""

from .exceptions import (
    InvalidSignalError,
    InvalidTimeRangeError,
    SignalError,
    SignalNotFoundError,
    UnsupportedChannelError,
)
from .factory import build_signal_record
from .models import (
    ChannelMode,
    FaultLabel,
    SignalMeta,
    SignalRecord,
    SourceType,
    TimeRange,
)
from .repository import InMemorySignalRepository, SignalRepository
from .segment import extract_segment
from .synthetic import (
    GroundTruthValue,
    SyntheticCase,
    SyntheticGroundTruth,
    generate_clipped_sine,
    generate_combined_distortion,
    generate_harmonic_sine,
    generate_sine,
    generate_white_noise,
)
from .wav import (
    InvalidWavError,
    LoadedWav,
    SignalLimitExceededError,
    UnsupportedWavError,
    WavDecodeError,
    WavLoadLimits,
    WavSourceInfo,
    load_wav_bytes,
)

__all__ = [
    "ChannelMode",
    "FaultLabel",
    "GroundTruthValue",
    "InMemorySignalRepository",
    "InvalidSignalError",
    "InvalidTimeRangeError",
    "InvalidWavError",
    "LoadedWav",
    "SignalError",
    "SignalLimitExceededError",
    "SignalMeta",
    "SignalNotFoundError",
    "SignalRecord",
    "SignalRepository",
    "SourceType",
    "SyntheticCase",
    "SyntheticGroundTruth",
    "TimeRange",
    "UnsupportedChannelError",
    "UnsupportedWavError",
    "WavDecodeError",
    "WavLoadLimits",
    "WavSourceInfo",
    "build_signal_record",
    "extract_segment",
    "generate_clipped_sine",
    "generate_combined_distortion",
    "generate_harmonic_sine",
    "generate_sine",
    "generate_white_noise",
    "load_wav_bytes",
]
