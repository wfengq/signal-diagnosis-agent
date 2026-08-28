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

__all__ = [
    "ChannelMode",
    "FaultLabel",
    "GroundTruthValue",
    "InMemorySignalRepository",
    "InvalidSignalError",
    "InvalidTimeRangeError",
    "SignalError",
    "SignalMeta",
    "SignalNotFoundError",
    "SignalRecord",
    "SignalRepository",
    "SourceType",
    "SyntheticCase",
    "SyntheticGroundTruth",
    "TimeRange",
    "UnsupportedChannelError",
    "build_signal_record",
    "extract_segment",
    "generate_clipped_sine",
    "generate_combined_distortion",
    "generate_harmonic_sine",
    "generate_sine",
    "generate_white_noise",
]
