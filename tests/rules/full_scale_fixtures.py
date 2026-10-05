"""Test fixtures for full-scale check (values are not product tolerances)."""

from __future__ import annotations

import hashlib
import math
import struct
from typing import Literal

import numpy as np

from signal_diag.signal import (
    InMemorySignalRepository,
    TimeRange,
    generate_sine,
    load_wav_bytes,
)
from signal_diag.tools.contracts import ClippingInput, HarmonicDistortionInput
from signal_diag.rules.regression import ComparisonConditions, compare_measurements
from signal_diag.rules.full_scale_check import (
    TOLERATED_DIFFERENCE_ID,
    FullScaleDeclarations,
    FullScaleMethodFloor,
    FullScaleSubmission,
    full_scale_floor_digest,
)
from signal_diag.tools.regression_full_scale import measure_full_scale_facts
from signal_diag.tools.regression_measurement import (
    InputIdentity,
    MeasurementBundle,
    MeasurementSelection,
    ToolParameterSnapshot,
    measure_output,
)


def q16(value: float) -> float:
    code = int(round(value * 32768.0))
    code = max(-32768, min(32767, code))
    return code / 32768.0


def _pcm_fmt(*, channels: int, rate: int, bits: int) -> bytes:
    block_align = channels * (bits // 8)
    return struct.pack("<HHIIHH", 1, channels, rate, rate * block_align, block_align, bits)


def _riff_wave(*, fmt_payload: bytes, data: bytes) -> bytes:
    chunks = [
        b"fmt " + struct.pack("<I", len(fmt_payload)) + fmt_payload,
        b"data" + struct.pack("<I", len(data)) + data,
    ]
    body = b"WAVE" + b"".join(
        chunk + (b"\x00" if len(chunk) % 2 else b"") for chunk in chunks
    )
    return b"RIFF" + struct.pack("<I", len(body)) + body


def wav16(samples: np.ndarray, *, sample_rate_hz: int = 48_000) -> bytes:
    mono = np.asarray(samples, dtype=np.float64).reshape(-1)
    codes = np.clip(np.rint(mono * 32768.0), -32768, 32767).astype("<i2")
    return _riff_wave(
        fmt_payload=_pcm_fmt(channels=1, rate=sample_rate_hz, bits=16),
        data=codes.tobytes(),
    )


def wav24(samples: np.ndarray, *, sample_rate_hz: int = 48_000) -> bytes:
    mono = np.asarray(samples, dtype=np.float64).reshape(-1)
    packed = bytearray()
    for sample in np.clip(np.rint(mono * 8388608.0), -8388608, 8388607).astype(np.int32):
        packed.extend(int(sample).to_bytes(3, "little", signed=True))
    return _riff_wave(
        fmt_payload=_pcm_fmt(channels=1, rate=sample_rate_hz, bits=24),
        data=bytes(packed),
    )


def wav16_stereo(
    left: np.ndarray,
    right: np.ndarray,
    *,
    sample_rate_hz: int = 48_000,
) -> bytes:
    left_c = np.clip(np.rint(np.asarray(left, dtype=np.float64) * 32768.0), -32768, 32767).astype(
        "<i2"
    )
    right_c = np.clip(np.rint(np.asarray(right, dtype=np.float64) * 32768.0), -32768, 32767).astype(
        "<i2"
    )
    frames = min(len(left_c), len(right_c))
    interleaved = np.empty(frames * 2, dtype="<i2")
    interleaved[0::2] = left_c[:frames]
    interleaved[1::2] = right_c[:frames]
    return _riff_wave(
        fmt_payload=_pcm_fmt(channels=2, rate=sample_rate_hz, bits=16),
        data=interleaved.tobytes(),
    )


def sine(
    *,
    frequency_hz: float = 100.0,
    amplitude: float = 0.5,
    duration_s: float = 2.0,
    sample_rate_hz: int = 48_000,
) -> np.ndarray:
    case = generate_sine(
        frequency_hz=frequency_hz,
        sample_rate_hz=sample_rate_hz,
        duration_s=duration_s,
        amplitude=amplitude,
    )
    return case.record.samples[:, 0]


def _resolved_bounds(
    repository: InMemorySignalRepository,
    signal_id: str,
    selection: MeasurementSelection,
) -> tuple[int, int]:
    record = repository.get(signal_id)
    time_range = selection.clipping.time_range or TimeRange()
    start = round(time_range.start_s * record.meta.sample_rate_hz)
    end = (
        record.meta.num_samples
        if time_range.end_s is None
        else min(
            round(time_range.end_s * record.meta.sample_rate_hz),
            record.meta.num_samples,
        )
    )
    return start, end


def measured(
    samples_or_wav: np.ndarray | bytes,
    *,
    side: Literal["baseline", "candidate"] = "baseline",
    bits: int = 16,
    time_range: TimeRange | None = None,
    channel: Literal["left", "right"] = "left",
    full_scale_threshold: float = 0.99,
) -> tuple[MeasurementBundle, InMemorySignalRepository, int]:
    tr = time_range or TimeRange()
    if isinstance(samples_or_wav, np.ndarray):
        if bits == 16:
            wav = wav16(samples_or_wav)
        elif bits == 24:
            wav = wav24(samples_or_wav)
        else:
            raise ValueError(f"unsupported bits for ndarray encoding: {bits}")
    else:
        wav = samples_or_wav

    repository = InMemorySignalRepository()
    loaded = load_wav_bytes(wav, filename="fixture.wav")
    repository.put(loaded.record)
    wav_sha = hashlib.sha256(wav).hexdigest()
    signal_id = loaded.record.meta.signal_id
    selection = MeasurementSelection(
        clipping=ClippingInput(
            channel=channel,
            time_range=tr,
            full_scale_threshold=full_scale_threshold,
        ),
        harmonic=HarmonicDistortionInput(
            channel=channel,
            time_range=tr,
            fundamental_hz=100.0,
        ),
    )
    start, end = _resolved_bounds(repository, signal_id, selection)
    snapshot = ToolParameterSnapshot(
        clipping=selection.clipping,
        harmonic=selection.harmonic,
    )
    identity = InputIdentity(
        run_id=f"run_{side}",
        side=side,
        wav_sha256=wav_sha,
        signal_id=signal_id,
        sample_rate_hz=loaded.record.meta.sample_rate_hz,
        source_channels=loaded.record.meta.channels,
        total_frames=loaded.record.meta.num_samples,
        resolved_start_sample=start,
        resolved_end_sample=end,
        channel=channel,
        tool_parameter_snapshot=snapshot,
    )
    bundle = measure_output(
        repository=repository,
        identity=identity,
        selection=selection,
    )
    return bundle, repository, loaded.source_info.bits_per_sample


def shaped(
    counted: int,
    peak: float,
    *,
    isolated: int = 0,
    duration_s: float = 2.0,
    sample_rate_hz: int = 48_000,
) -> np.ndarray:
    samples = sine(amplitude=0.25, duration_s=duration_s, sample_rate_hz=sample_rate_hz)
    if counted == 0 and isolated == 0:
        return sine(amplitude=peak, duration_s=duration_s, sample_rate_hz=sample_rate_hz)
    if counted > 0:
        end = min(1000 + counted, len(samples))
        samples[1000:end] = q16(peak)
    if isolated > 0:
        isolated_peak = peak if peak >= 0.99 else 1.0
        index = 2000
        placed = 0
        while placed < isolated and index < len(samples):
            samples[index] = q16(isolated_peak)
            placed += 1
            index += 97
    return samples


def _conditions(**overrides: object) -> ComparisonConditions:
    base: dict[str, object] = {
        "baseline_version": "v1",
        "candidate_version": "v2",
        "stimulus_key": "fixture",
        "parameters_key": "default",
        "same_input": "yes",
        "parameters_unchanged": "yes",
        "aligned_ranges": "yes",
        "repeatability": "declared_deterministic",
        "nominal_fundamental_hz": 100.0,
    }
    base.update(overrides)
    return ComparisonConditions(**base)


def make_submission(
    *,
    comparison_id: str,
    parent: str | None = None,
    kind: str | None = None,
    baseline: tuple[int, float] = (0, 0.5),
    candidate: tuple[int, float] = (0, 0.5),
    baseline_isolated: int = 0,
    candidate_isolated: int = 0,
    bits: tuple[int, int] = (16, 16),
    declarations: FullScaleDeclarations | None = None,
    time_range: TimeRange | None = None,
    baseline_samples: np.ndarray | None = None,
    candidate_samples: np.ndarray | None = None,
    drop_facts: str | None = None,
    full_scale_threshold: float = 0.99,
    candidate_version: str | None = None,
    **condition_overrides: object,
) -> FullScaleSubmission:
    b_samples = baseline_samples
    if b_samples is None:
        b_samples = shaped(*baseline, isolated=baseline_isolated)
    c_samples = candidate_samples
    if c_samples is None:
        c_samples = shaped(*candidate, isolated=candidate_isolated)

    b_bundle, b_repo, _ = measured(
        b_samples,
        side="baseline",
        bits=16 if bits[0] != 8 else 16,
        time_range=time_range,
        full_scale_threshold=full_scale_threshold,
    )
    c_bundle, c_repo, _ = measured(
        c_samples,
        side="candidate",
        bits=16 if bits[1] != 8 else 16,
        time_range=time_range,
        full_scale_threshold=full_scale_threshold,
    )
    b_bits = bits[0]
    c_bits = bits[1]
    b_facts = measure_full_scale_facts(
        repository=b_repo, bundle=b_bundle, pcm_bit_depth=b_bits
    )
    c_facts = measure_full_scale_facts(
        repository=c_repo, bundle=c_bundle, pcm_bit_depth=c_bits
    )
    if drop_facts == "baseline":
        b_facts = None
    if drop_facts == "candidate":
        c_facts = None

    if candidate_version is not None:
        condition_overrides = {**condition_overrides, "candidate_version": candidate_version}

    record = compare_measurements(
        b_bundle,
        c_bundle,
        conditions=_conditions(**condition_overrides),
        comparison_id=comparison_id,
    )
    return FullScaleSubmission(
        comparison_id=comparison_id,
        parent_comparison_id=parent,
        link_kind=kind,
        record=record,
        declarations=declarations or FullScaleDeclarations(),
        baseline_facts=b_facts,
        candidate_facts=c_facts,
    )


def eligible(
    *,
    baseline: tuple[int, float] = (0, 0.5),
    candidate: tuple[int, float] = (0, 0.5),
    periodic: str = "yes",
    drop_repeats: str | None = None,
    repeat_baseline: tuple[int, float] | None = None,
    repeat_candidate: tuple[int, float] | None = None,
    baseline_isolated: int = 0,
    baseline_samples: np.ndarray | None = None,
    candidate_samples: np.ndarray | None = None,
    **kw: object,
) -> tuple[FullScaleSubmission, tuple[FullScaleSubmission, ...]]:
    decl = FullScaleDeclarations(periodic_test_signal=periodic)
    anchor = make_submission(
        comparison_id="a",
        baseline=baseline,
        candidate=candidate,
        declarations=decl,
        baseline_isolated=baseline_isolated,
        baseline_samples=baseline_samples,
        candidate_samples=candidate_samples,
        **kw,
    )
    indep = FullScaleDeclarations(
        periodic_test_signal=periodic,
        baseline_independent_render="yes",
        candidate_independent_render="yes",
    )
    if drop_repeats == "candidate":
        indep = FullScaleDeclarations(
            periodic_test_signal=periodic,
            baseline_independent_render="yes",
            candidate_independent_render="unknown",
        )
    repeat = make_submission(
        comparison_id="r1",
        parent="a",
        kind="repeat",
        baseline=repeat_baseline or baseline,
        candidate=repeat_candidate or candidate,
        declarations=indep,
        baseline_isolated=baseline_isolated,
        baseline_samples=baseline_samples,
        candidate_samples=candidate_samples,
        **kw,
    )
    return anchor, (repeat,)


def index(*subs: FullScaleSubmission) -> dict[str, FullScaleSubmission]:
    return {s.comparison_id: s for s in subs}


_fixture_floor_body = FullScaleMethodFloor(
    floor_id="fixture_floor",
    version="test-1",
    facts_version="v0.3-full-scale-facts-1",
    full_scale_threshold=0.99,
    min_consecutive_samples=2,
    min_samples_per_period=20.0,
    min_periods_in_range=10.0,
    zone_below_threshold=0.001,
    zone_above_threshold=0.001,
    zone_min_counted_samples=None,
    count_floor_samples=10,
    count_floor_ratio=None,
    tolerated_difference=TOLERATED_DIFFERENCE_ID,
    digest="0" * 64,
)
FIXTURE_FLOOR = _fixture_floor_body.model_copy(
    update={"digest": full_scale_floor_digest(_fixture_floor_body)}
)


def redigest(model):  # noqa: ANN001, ANN201
    """Recompute digest field after model_copy updates (full-scale facts/floor helpers)."""
    from pydantic import BaseModel

    if not isinstance(model, BaseModel):
        raise TypeError("expected a Pydantic model")
    name = type(model).__name__
    if name == "FullScaleFacts":
        from signal_diag.tools.regression_full_scale import full_scale_facts_digest

        return model.model_copy(update={"digest": full_scale_facts_digest(model)})
    if name == "FullScaleMethodFloor":
        return model.model_copy(update={"digest": full_scale_floor_digest(model)})
    if name == "FullScaleCheckRecord":
        from signal_diag.rules.full_scale_check import _check_record_digest

        return model.model_copy(update={"digest": _check_record_digest(model)})
    raise TypeError(f"redigest not implemented for {name}")
