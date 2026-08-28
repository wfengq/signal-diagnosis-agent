"""Validated public models for canonical signal records."""

from dataclasses import dataclass
import sys
from typing import Literal, Optional

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .exceptions import InvalidSignalError

SourceType = Literal["wav", "pcm", "csv", "generated"]
ChannelMode = Literal["left", "right", "mixdown"]
FaultLabel = Literal["clipping", "harmonic_distortion", "noise"]


def _frozen_signal_dataclass(cls):
    """Use the contracted slots layout where the supported runtime provides it."""
    if sys.version_info >= (3, 10):
        return dataclass(frozen=True, slots=True)(cls)
    return dataclass(frozen=True)(cls)


class TimeRange(BaseModel):
    """A left-closed, right-open selection interval in seconds."""

    model_config = ConfigDict(frozen=True)

    start_s: float = Field(default=0.0, ge=0.0)
    end_s: Optional[float] = Field(default=None, gt=0.0)

    @model_validator(mode="after")
    def validate_interval(self) -> "TimeRange":
        if self.end_s is not None and self.end_s <= self.start_s:
            raise ValueError("end_s must be greater than start_s")
        return self


class SignalMeta(BaseModel):
    """Metadata derived from a canonical waveform."""

    model_config = ConfigDict(frozen=True)

    signal_id: str = Field(min_length=1)
    source_type: SourceType
    filename: Optional[str] = None
    sample_rate_hz: int = Field(gt=0)
    channels: int = Field(gt=0)
    num_samples: int = Field(gt=0)
    duration_s: float = Field(gt=0.0)
    original_dtype: str
    amplitude_unit: str = "FS"

    @model_validator(mode="after")
    def validate_duration(self) -> "SignalMeta":
        expected_duration_s = self.num_samples / self.sample_rate_hz
        if abs(self.duration_s - expected_duration_s) > 1e-12:
            raise ValueError("duration_s must equal num_samples / sample_rate_hz")
        return self


@_frozen_signal_dataclass
class SignalRecord:
    """A canonical, two-dimensional waveform and its derived metadata."""

    meta: SignalMeta
    samples: np.ndarray

    def __post_init__(self) -> None:
        if not isinstance(self.samples, np.ndarray):
            raise InvalidSignalError("samples must be a numpy array")
        if self.samples.dtype != np.float32:
            raise InvalidSignalError("samples must have dtype float32")
        if self.samples.ndim != 2:
            raise InvalidSignalError("samples must have shape (num_samples, channels)")
        if not self.samples.flags.c_contiguous:
            raise InvalidSignalError("samples must be C-contiguous")
        if not np.isfinite(self.samples).all():
            raise InvalidSignalError("samples must be finite")
        if self.samples.shape != (self.meta.num_samples, self.meta.channels):
            raise InvalidSignalError("samples shape must agree with metadata")
