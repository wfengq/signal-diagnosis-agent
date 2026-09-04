"""Compact Tool input and output contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from signal_diag.signal.models import ChannelMode, TimeRange

ToolName = Literal[
    "detect_clipping",
    "analyze_spectrum",
    "estimate_fundamental",
    "analyze_harmonic_distortion",
    "analyze_contextual_distortion",
]


class SignalSelection(BaseModel):
    model_config = ConfigDict(frozen=True)

    time_range: TimeRange | None = None
    channel: ChannelMode = "mixdown"


class ClippingInput(SignalSelection):
    full_scale_threshold: float = Field(default=0.99, gt=0.0)


class SpectrumInput(SignalSelection):
    window: str = "hann"
    n_fft: int | None = Field(default=None, ge=3)
    max_peaks: int = Field(default=10, ge=1, le=20)


class FundamentalInput(SignalSelection):
    fmin_hz: float = Field(default=50.0, gt=0.0)
    fmax_hz: float = Field(default=1000.0, gt=0.0)

    @model_validator(mode="after")
    def validate_frequency_band(self) -> "FundamentalInput":
        if self.fmax_hz <= self.fmin_hz:
            raise ValueError("fmax_hz must be greater than fmin_hz")
        return self


class HarmonicDistortionInput(SignalSelection):
    fundamental_hz: float | None = Field(default=None, gt=0.0)
    fmin_hz: float = Field(default=50.0, gt=0.0)
    fmax_hz: float = Field(default=1000.0, gt=0.0)
    max_harmonic_order: int = Field(default=5, ge=2, le=10)
    window: str = "hann"

    @model_validator(mode="after")
    def validate_frequency_band(self) -> "HarmonicDistortionInput":
        if self.fmax_hz <= self.fmin_hz:
            raise ValueError("fmax_hz must be greater than fmin_hz")
        return self


class ClippingOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal["clipping"] = "clipping"
    detected: bool
    clipping_ratio: float
    clipped_samples: int
    clipping_events: int
    longest_event_samples: int
    peak_abs: float
    full_scale_detected: bool
    flat_top_detected: bool
    clipping_mechanism: bool = False


class SpectrumPeakOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    frequency_hz: float
    relative_magnitude_db: float


class SpectrumOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal["spectrum"] = "spectrum"
    frequency_resolution_hz: float
    dominant_frequency_hz: float | None
    spectral_centroid_hz: float | None
    spectral_peaks: tuple[SpectrumPeakOutput, ...]


class FundamentalOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal["fundamental"] = "fundamental"
    f0_hz: float | None
    confidence: float
    voiced: bool
    method: str


class HarmonicComponentOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    order: int
    measured_frequency_hz: float
    relative_amplitude: float
    relative_magnitude_db: float


class HarmonicDistortionOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal["harmonic_distortion"] = "harmonic_distortion"
    valid: bool
    invalid_reason: str | None
    fundamental_frequency_hz: float | None
    thd_percent: float | None
    components: tuple[HarmonicComponentOutput, ...]
    series_kind: str | None = None


class ContextualDistortionInput(SignalSelection):
    max_harmonic_order: int = Field(default=5, ge=2, le=10)
    window: Literal["hann", "boxcar"] = "hann"


class HarmonicGrowthComponentOutput(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    order: int = Field(ge=2)
    reference_relative_amplitude: float = Field(ge=0.0)
    test_relative_amplitude: float = Field(ge=0.0)
    positive_growth: float = Field(ge=0.0)


class ContextualDistortionOutput(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    kind: Literal["contextual_distortion"] = "contextual_distortion"
    algorithm_version: Literal["1.0.0"] = "1.0.0"
    mode: Literal["nominal_single_tone", "paired_reference"]
    valid: bool
    invalid_reason: str | None
    test_f0_hz: float | None
    comparison_f0_hz: float | None
    f0_relative_delta: float | None
    alignment_lag_samples: int | None
    alignment_correlation: float | None
    gain_ratio: float | None
    reference_thd_percent: float | None
    test_thd_percent: float | None
    thd_delta_percent: float | None
    even_harmonic_growth_percent: float | None
    test_series_kind: str | None
    components: tuple[HarmonicGrowthComponentOutput, ...]
    reference_clipping_ratio: float | None
    reference_flat_top_detected: bool | None
    test_clipping_ratio: float
    test_flat_top_detected: bool
