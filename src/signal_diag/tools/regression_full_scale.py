"""Full-scale facts captured alongside regression measurement bundles."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from signal_diag.signal import SignalRepository
from signal_diag.signal.segment import extract_segment
from signal_diag.tools.regression_measurement import (
    ComparisonSide,
    MeasurementBundle,
    _canonical_json,
)
from signal_diag.dsp.full_scale import count_full_scale_samples

FULL_SCALE_FACTS_VERSION = "v0.3-full-scale-facts-1"
FULL_SCALE_MIN_CONSECUTIVE_SAMPLES = 2


class FullScaleFacts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    side: ComparisonSide
    run_id: str
    wav_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bundle_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    full_scale_threshold: float
    min_consecutive_samples: int
    counted_samples: int = Field(ge=0)
    over_threshold_uncounted: int = Field(ge=0)
    state: Literal["yes", "no"]
    peak_abs: float
    analyzed_samples: int = Field(gt=0)
    pcm_bit_depth: Literal[8, 16, 24, 32]
    facts_version: str
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_state(self) -> FullScaleFacts:
        expected = "yes" if self.counted_samples > 0 else "no"
        if self.state != expected:
            raise ValueError("state must match counted_samples")
        return self


def measure_full_scale_facts(
    *,
    repository: SignalRepository,
    bundle: MeasurementBundle,
    pcm_bit_depth: int,
) -> FullScaleFacts | None:
    """Derive full-scale facts from the same segment and threshold as clipping."""
    if bundle.clipping.status != "success" or bundle.clipping.result is None:
        return None

    identity = bundle.identity
    selection = identity.tool_parameter_snapshot.clipping
    record = repository.get(identity.signal_id)
    segment = extract_segment(
        record,
        time_range=selection.time_range,
        channel=selection.channel,
    )
    counts = count_full_scale_samples(
        segment,
        full_scale_threshold=selection.full_scale_threshold,
        min_consecutive_samples=FULL_SCALE_MIN_CONSECUTIVE_SAMPLES,
    )
    state: Literal["yes", "no"] = "yes" if counts.counted_samples > 0 else "no"
    if pcm_bit_depth not in (8, 16, 24, 32):
        raise ValueError("pcm_bit_depth must be 8, 16, 24, or 32")

    without_digest = FullScaleFacts(
        side=identity.side,
        run_id=identity.run_id,
        wav_sha256=identity.wav_sha256,
        bundle_digest=bundle.digest,
        full_scale_threshold=selection.full_scale_threshold,
        min_consecutive_samples=FULL_SCALE_MIN_CONSECUTIVE_SAMPLES,
        counted_samples=counts.counted_samples,
        over_threshold_uncounted=counts.over_threshold_uncounted,
        state=state,
        peak_abs=counts.peak_abs,
        analyzed_samples=counts.analyzed_samples,
        pcm_bit_depth=pcm_bit_depth,
        facts_version=FULL_SCALE_FACTS_VERSION,
        digest="0" * 64,
    )
    return without_digest.model_copy(update={"digest": full_scale_facts_digest(without_digest)})


def full_scale_facts_digest(facts: FullScaleFacts) -> str:
    payload = facts.model_dump(mode="json")
    payload.pop("digest", None)
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def verify_full_scale_facts(facts: FullScaleFacts, bundle: MeasurementBundle) -> None:
    if full_scale_facts_digest(facts) != facts.digest:
        raise ValueError("full-scale facts digest mismatch")

    identity = bundle.identity
    if facts.side != identity.side:
        raise ValueError("facts side mismatch")
    if facts.run_id != identity.run_id:
        raise ValueError("facts run_id mismatch")
    if facts.wav_sha256 != identity.wav_sha256:
        raise ValueError("facts wav_sha256 mismatch")
    if facts.bundle_digest != bundle.digest:
        raise ValueError("facts bundle_digest mismatch")

    clipping = bundle.clipping
    if clipping.status != "success" or clipping.result is None:
        raise ValueError("bundle clipping must succeed for facts verification")

    threshold = identity.tool_parameter_snapshot.clipping.full_scale_threshold
    if facts.full_scale_threshold != threshold:
        raise ValueError("facts full_scale_threshold mismatch")
    if facts.min_consecutive_samples != FULL_SCALE_MIN_CONSECUTIVE_SAMPLES:
        raise ValueError("facts min_consecutive_samples mismatch")
    if facts.facts_version != FULL_SCALE_FACTS_VERSION:
        raise ValueError("facts facts_version mismatch")

    expected_state = "yes" if facts.counted_samples > 0 else "no"
    if facts.state != expected_state:
        raise ValueError("facts state inconsistent with counted_samples")
    if clipping.result.full_scale_detected != (facts.counted_samples > 0):
        raise ValueError("facts counted_samples inconsistent with clipping full_scale_detected")
    if facts.peak_abs != clipping.result.peak_abs:
        raise ValueError("facts peak_abs mismatch")

    expected_analyzed = identity.resolved_end_sample - identity.resolved_start_sample
    if facts.analyzed_samples != expected_analyzed:
        raise ValueError("facts analyzed_samples mismatch")
