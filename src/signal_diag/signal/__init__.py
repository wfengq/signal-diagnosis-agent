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

__all__ = [
    "ChannelMode",
    "FaultLabel",
    "InMemorySignalRepository",
    "InvalidSignalError",
    "InvalidTimeRangeError",
    "SignalError",
    "SignalMeta",
    "SignalNotFoundError",
    "SignalRecord",
    "SignalRepository",
    "SourceType",
    "TimeRange",
    "UnsupportedChannelError",
    "build_signal_record",
    "extract_segment",
]
