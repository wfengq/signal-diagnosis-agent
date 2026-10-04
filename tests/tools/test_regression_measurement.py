"""Regression workbench measurement bundles (Task 2)."""

from __future__ import annotations

import hashlib
import math
import struct

import numpy as np
import pytest
from pydantic import ValidationError

from signal_diag.app.pcm_wav import encode_pcm32_wav
from signal_diag.signal import (
    InMemorySignalRepository,
    TimeRange,
    generate_sine,
    generate_white_noise,
    load_wav_bytes,
)
from signal_diag.tools.contracts import ClippingInput, HarmonicDistortionInput
from signal_diag.tools.regression_measurement import (
    InputIdentity,
    MeasurementSelection,
    ToolParameterSnapshot,
    measure_output,
)


def _mono_wav_bytes(
    *,
    frequency_hz: float = 200.0,
    sample_rate_hz: int = 48_000,
    duration_s: float = 0.5,
    amplitude: float = 0.4,
) -> bytes:
    case = generate_sine(
        frequency_hz=frequency_hz,
        sample_rate_hz=sample_rate_hz,
        duration_s=duration_s,
        amplitude=amplitude,
    )
    return encode_pcm32_wav(case.record.samples, sample_rate_hz=sample_rate_hz)


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


def _stereo_wav_bytes(*, sample_rate_hz: int = 48_000) -> bytes:
    frames = 4_096
    t = np.arange(frames, dtype=np.float64) / sample_rate_hz
    left = (0.4 * np.sin(2 * math.pi * 200.0 * t)).astype(np.float64)
    right = (0.4 * np.sin(2 * math.pi * 400.0 * t)).astype(np.float64)
    interleaved = np.empty(frames * 2, dtype=np.int16)
    interleaved[0::2] = np.clip(np.rint(left * 32767.0), -32768, 32767)
    interleaved[1::2] = np.clip(np.rint(right * 32767.0), -32768, 32767)
    return _riff_wave(
        fmt_payload=_pcm_fmt(channels=2, rate=sample_rate_hz, bits=16),
        data=interleaved.tobytes(),
    )


def _load_into_repo(data: bytes, repository: InMemorySignalRepository) -> tuple[str, str]:
    loaded = load_wav_bytes(data, filename="regression.wav")
    repository.put(loaded.record)
    return loaded.record.meta.signal_id, hashlib.sha256(data).hexdigest()


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


def _identity(
    *,
    run_id: str,
    side: str,
    wav_sha256: str,
    signal_id: str,
    repository: InMemorySignalRepository,
    selection: MeasurementSelection,
) -> InputIdentity:
    record = repository.get(signal_id)
    start, end = _resolved_bounds(repository, signal_id, selection)
    snapshot = ToolParameterSnapshot(
        clipping=selection.clipping,
        harmonic=selection.harmonic,
    )
    return InputIdentity(
        run_id=run_id,
        side=side,
        wav_sha256=wav_sha256,
        signal_id=signal_id,
        sample_rate_hz=record.meta.sample_rate_hz,
        source_channels=record.meta.channels,
        total_frames=record.meta.num_samples,
        resolved_start_sample=start,
        resolved_end_sample=end,
        channel=selection.clipping.channel,
        tool_parameter_snapshot=snapshot,
    )


def _default_selection(
    *,
    channel: str = "left",
    fundamental_hz: float = 200.0,
    time_range: TimeRange | None = None,
) -> MeasurementSelection:
    tr = time_range or TimeRange()
    return MeasurementSelection(
        clipping=ClippingInput(channel=channel, time_range=tr),
        harmonic=HarmonicDistortionInput(
            channel=channel,
            time_range=tr,
            fundamental_hz=fundamental_hz,
        ),
    )


def test_real_pcm_measurements_keep_two_run_identities() -> None:
    repository = InMemorySignalRepository()
    wav_bytes = _mono_wav_bytes()
    signal_id, wav_sha = _load_into_repo(wav_bytes, repository)
    selection = _default_selection()

    baseline = measure_output(
        repository=repository,
        identity=_identity(
            run_id="run_base",
            side="baseline",
            wav_sha256=wav_sha,
            signal_id=signal_id,
            repository=repository,
            selection=selection,
        ),
        selection=selection,
    )
    candidate = measure_output(
        repository=repository,
        identity=_identity(
            run_id="run_cand",
            side="candidate",
            wav_sha256=wav_sha,
            signal_id=signal_id,
            repository=repository,
            selection=selection,
        ),
        selection=selection,
    )

    assert baseline.identity.wav_sha256 == candidate.identity.wav_sha256 == wav_sha
    assert baseline.identity.run_id != candidate.identity.run_id
    assert baseline.identity.side == "baseline"
    assert candidate.identity.side == "candidate"
    assert baseline.clipping.status == "success"
    assert candidate.clipping.status == "success"
    base_ratio = next(
        item.value
        for item in baseline.clipping.evidence
        if item.metric == "clipping_ratio"
    )
    cand_ratio = next(
        item.value
        for item in candidate.clipping.evidence
        if item.metric == "clipping_ratio"
    )
    assert base_ratio == cand_ratio
    assert baseline.digest != candidate.digest


def test_selection_and_sample_bytes_are_preserved() -> None:
    repository = InMemorySignalRepository()
    wav_bytes = _mono_wav_bytes()
    signal_id, wav_sha = _load_into_repo(wav_bytes, repository)
    record = repository.get(signal_id)
    before = record.samples.copy()
    selection = _default_selection()
    measure_output(
        repository=repository,
        identity=_identity(
            run_id="run_a",
            side="baseline",
            wav_sha256=wav_sha,
            signal_id=signal_id,
            repository=repository,
            selection=selection,
        ),
        selection=selection,
    )
    after = repository.get(signal_id).samples
    assert np.array_equal(before, after)

    stereo_bytes = _stereo_wav_bytes()
    stereo_id, stereo_sha = _load_into_repo(stereo_bytes, repository)
    right_only = _default_selection(channel="right")
    measure_output(
        repository=repository,
        identity=_identity(
            run_id="run_stereo",
            side="baseline",
            wav_sha256=stereo_sha,
            signal_id=stereo_id,
            repository=repository,
            selection=right_only,
        ),
        selection=right_only,
    )

    mono_id, mono_sha = signal_id, wav_sha
    mono_record = repository.get(mono_id)
    oob = MeasurementSelection(
        clipping=ClippingInput(
            channel="left",
            time_range=TimeRange(start_s=10.0, end_s=11.0),
        ),
        harmonic=HarmonicDistortionInput(
            channel="left",
            time_range=TimeRange(start_s=10.0, end_s=11.0),
            fundamental_hz=200.0,
        ),
    )
    oob_snapshot = ToolParameterSnapshot(clipping=oob.clipping, harmonic=oob.harmonic)
    with pytest.raises(ValueError, match="resolved"):
        measure_output(
            repository=repository,
            identity=InputIdentity(
                run_id="run_oob",
                side="baseline",
                wav_sha256=mono_sha,
                signal_id=mono_id,
                sample_rate_hz=mono_record.meta.sample_rate_hz,
                source_channels=mono_record.meta.channels,
                total_frames=mono_record.meta.num_samples,
                resolved_start_sample=0,
                resolved_end_sample=mono_record.meta.num_samples,
                channel="left",
                tool_parameter_snapshot=oob_snapshot,
            ),
            selection=oob,
        )

    with pytest.raises(ValueError, match="right channel"):
        bad_right = _default_selection(channel="right")
        measure_output(
            repository=repository,
            identity=_identity(
                run_id="run_mono_right",
                side="baseline",
                wav_sha256=mono_sha,
                signal_id=mono_id,
                repository=repository,
                selection=bad_right,
            ),
            selection=bad_right,
        )

    with pytest.raises(ValidationError, match="time_range"):
        MeasurementSelection(
            clipping=ClippingInput(
                channel="left",
                time_range=TimeRange(start_s=0.0, end_s=0.1),
            ),
            harmonic=HarmonicDistortionInput(
                channel="left",
                time_range=TimeRange(start_s=0.1, end_s=0.2),
                fundamental_hz=200.0,
            ),
        )

    with pytest.raises(ValidationError):
        ClippingInput(channel="left", full_scale_threshold=float("nan"))


def test_invalid_harmonic_is_not_zero() -> None:
    repository = InMemorySignalRepository()
    noise = generate_white_noise(
        sample_rate_hz=48_000,
        duration_s=0.5,
        seed=17,
    )
    repository.put(noise.record)
    signal_id = noise.record.meta.signal_id
    wav_bytes = encode_pcm32_wav(noise.record.samples, sample_rate_hz=48_000)
    wav_sha = hashlib.sha256(wav_bytes).hexdigest()
    selection = _default_selection(fundamental_hz=200.0)

    bundle = measure_output(
        repository=repository,
        identity=_identity(
            run_id="run_noise",
            side="baseline",
            wav_sha256=wav_sha,
            signal_id=signal_id,
            repository=repository,
            selection=selection,
        ),
        selection=selection,
    )

    assert bundle.clipping.status == "success"
    assert bundle.harmonic.status == "invalid"
    assert bundle.harmonic.result is not None
    assert bundle.harmonic.result.valid is False
    assert bundle.harmonic.result.thd_percent is None
    assert not any(item.metric == "thd_percent" for item in bundle.harmonic.evidence)

    noise_record = repository.get(signal_id)
    start, end = _resolved_bounds(repository, signal_id, selection)
    missing_identity = InputIdentity(
        run_id="run_missing",
        side="baseline",
        wav_sha256=wav_sha,
        signal_id="missing-signal",
        sample_rate_hz=noise_record.meta.sample_rate_hz,
        source_channels=noise_record.meta.channels,
        total_frames=noise_record.meta.num_samples,
        resolved_start_sample=start,
        resolved_end_sample=end,
        channel="left",
        tool_parameter_snapshot=ToolParameterSnapshot(
            clipping=selection.clipping,
            harmonic=selection.harmonic,
        ),
    )
    missing = measure_output(
        repository=repository,
        identity=missing_identity,
        selection=selection,
    )
    assert missing.harmonic.status == "error"
    assert missing.harmonic.result is None
