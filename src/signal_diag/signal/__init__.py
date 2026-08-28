"""Signal representation and construction."""

from .exceptions import (
    InvalidSignalError,
    InvalidTimeRangeError,
    SignalError,
    SignalNotFoundError,
    UnsupportedChannelError,
)
from .factory import build_signal_record
from .models import ChannelMode, FaultLabel, SignalMeta, SignalRecord, SourceType, TimeRange

__all__ = [
    "ChannelMode",
    "FaultLabel",
    "InvalidSignalError",
    "InvalidTimeRangeError",
    "SignalError",
    "SignalMeta",
    "SignalNotFoundError",
    "SignalRecord",
    "SourceType",
    "TimeRange",
    "UnsupportedChannelError",
    "build_signal_record",
]
