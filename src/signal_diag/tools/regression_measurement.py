"""Deterministic regression measurement bundles using real DSP tools."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from signal_diag.signal import SignalNotFoundError, SignalRepository
from signal_diag.signal.models import ChannelMode, TimeRange
from signal_diag.signal.segment import _resolve_sample_bounds
from signal_diag.tools.contracts import (
    ClippingInput,
    ClippingOutput,
    HarmonicDistortionInput,
    HarmonicDistortionOutput,
)
from signal_diag.tools.results import ToolResult
from signal_diag.tools.service import SignalToolService

ComparisonSide = Literal["baseline", "candidate"]

MEASUREMENT_VERSION = "v0.3-regression-measurement-1"


class ToolParameterSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    clipping: ClippingInput
    harmonic: HarmonicDistortionInput


class MeasurementSelection(BaseModel):
    model_config = ConfigDict(frozen=True)

    clipping: ClippingInput
    harmonic: HarmonicDistortionInput

    @model_validator(mode="after")
    def validate_shared_selection(self) -> MeasurementSelection:
        if self.clipping.time_range != self.harmonic.time_range:
            raise ValueError("clipping and harmonic must share the same time_range")
        if self.clipping.channel != self.harmonic.channel:
            raise ValueError("clipping and harmonic must share the same channel")
        if self.clipping.channel not in ("left", "right"):
            raise ValueError("first-phase compare channel must be left or right")
        _assert_finite_clipping(self.clipping)
        _assert_finite_harmonic(self.harmonic)
        return self


class InputIdentity(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str = Field(min_length=1)
    side: ComparisonSide
    wav_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    signal_id: str = Field(min_length=1)
    sample_rate_hz: int = Field(gt=0)
    source_channels: int = Field(gt=0)
    total_frames: int = Field(gt=0)
    resolved_start_sample: int = Field(ge=0)
    resolved_end_sample: int = Field(gt=0)
    channel: ChannelMode
    tool_parameter_snapshot: ToolParameterSnapshot

    @model_validator(mode="after")
    def validate_channel(self) -> InputIdentity:
        if self.channel not in ("left", "right"):
            raise ValueError("first-phase compare channel must be left or right")
        if self.resolved_end_sample <= self.resolved_start_sample:
            raise ValueError("resolved_end_sample must be greater than resolved_start_sample")
        return self


class MeasurementBundle(BaseModel):
    model_config = ConfigDict(frozen=True)

    identity: InputIdentity
    clipping: ToolResult[ClippingOutput]
    harmonic: ToolResult[HarmonicDistortionOutput]
    measurement_version: str
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")


def measure_output(
    *,
    repository: SignalRepository,
    identity: InputIdentity,
    selection: MeasurementSelection,
) -> MeasurementBundle:
    """Run clipping and harmonic tools for one regression side."""
    snapshot = ToolParameterSnapshot(
        clipping=selection.clipping,
        harmonic=selection.harmonic,
    )
    if identity.tool_parameter_snapshot != snapshot:
        raise ValueError("identity tool_parameter_snapshot must match selection")
    if identity.channel != selection.clipping.channel:
        raise ValueError("identity channel must match selection channel")

    try:
        record = repository.get(identity.signal_id)
    except SignalNotFoundError:
        record = None

    if record is None:
        service = SignalToolService(repository)
        clipping = service.detect_clipping(identity.signal_id, selection.clipping)
        harmonic = service.analyze_harmonic_distortion(
            identity.signal_id,
            selection.harmonic,
        )
        bundle_without_digest = MeasurementBundle(
            identity=identity,
            clipping=clipping,
            harmonic=harmonic,
            measurement_version=MEASUREMENT_VERSION,
            digest="0" * 64,
        )
        return bundle_without_digest.model_copy(
            update={"digest": _bundle_digest(bundle_without_digest)},
        )

    if record.meta.sample_rate_hz != identity.sample_rate_hz:
        raise ValueError("identity sample_rate_hz does not match repository signal")
    if record.meta.channels != identity.source_channels:
        raise ValueError("identity source_channels does not match repository signal")
    if record.meta.num_samples != identity.total_frames:
        raise ValueError("identity total_frames does not match repository signal")

    time_range = selection.clipping.time_range or TimeRange()
    try:
        resolved_start, resolved_end = _resolve_sample_bounds(record, time_range)
    except Exception as error:
        raise ValueError(f"resolved sample range is invalid: {error}") from error

    if (
        identity.resolved_start_sample != resolved_start
        or identity.resolved_end_sample != resolved_end
    ):
        raise ValueError(
            "identity resolved sample range does not match selection on repository signal"
        )

    if identity.channel == "right" and record.meta.channels < 2:
        raise ValueError("right channel is unavailable for mono signals")

    service = SignalToolService(repository)
    clipping = service.detect_clipping(identity.signal_id, selection.clipping)
    harmonic = service.analyze_harmonic_distortion(
        identity.signal_id,
        selection.harmonic,
    )

    bundle_without_digest = MeasurementBundle(
        identity=identity,
        clipping=clipping,
        harmonic=harmonic,
        measurement_version=MEASUREMENT_VERSION,
        digest="0" * 64,
    )
    return bundle_without_digest.model_copy(
        update={"digest": _bundle_digest(bundle_without_digest)},
    )


def _assert_finite_clipping(selection: ClippingInput) -> None:
    if not math.isfinite(selection.full_scale_threshold):
        raise ValueError("clipping full_scale_threshold must be finite")


def _assert_finite_harmonic(selection: HarmonicDistortionInput) -> None:
    for name, value in (
        ("fmin_hz", selection.fmin_hz),
        ("fmax_hz", selection.fmax_hz),
        ("max_harmonic_order", float(selection.max_harmonic_order)),
    ):
        if not math.isfinite(value):
            raise ValueError(f"harmonic {name} must be finite")
    if selection.fundamental_hz is not None and not math.isfinite(selection.fundamental_hz):
        raise ValueError("harmonic fundamental_hz must be finite when provided")


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _bundle_digest(bundle: MeasurementBundle) -> str:
    payload = bundle.model_dump(mode="json")
    payload.pop("digest", None)
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
