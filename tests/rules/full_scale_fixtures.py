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


def redigest(model):  # noqa: ANN001, ANN201
    """Recompute digest field after model_copy updates (full-scale facts/floor helpers)."""
    from pydantic import BaseModel

    if not isinstance(model, BaseModel):
        raise TypeError("expected a Pydantic model")
    name = type(model).__name__
    if name == "FullScaleFacts":
        from signal_diag.tools.regression_full_scale import full_scale_facts_digest

        return model.model_copy(update={"digest": full_scale_facts_digest(model)})
    raise TypeError(f"redigest not implemented for {name}")
