"""Bounded multichannel PCM derivation and mono PCM24 encoding."""

from __future__ import annotations

import hashlib
import re
import struct
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from signal_diag.evaluation.external.models import DerivationSpec, DerivedAsset

_MAX_SAMPLE_FRAMES = 2_000_000
_MAX_DURATION_S = 30.0
_MAX_UPLOAD_BYTES = 20 * 1024 * 1024
_POSITIVE_PCM24_LIMIT = 1.0 - 2.0**-23
_ANALYSIS_WAV_PATTERN = re.compile(
    r"^extwav_(development|validation|final_external_test)_[0-9a-f]{16}\.wav$"
)


class PcmDerivationError(Exception):
    """Raised when PCM derivation or encoding rules are violated."""


@dataclass(frozen=True, slots=True)
class PcmWindow:
    samples: np.ndarray
    sample_rate_hz: int
    sample_width_bytes: int
    source_channels: int

    def __post_init__(self) -> None:
        copied = np.ascontiguousarray(self.samples, dtype=np.float32)
        copied.setflags(write=False)
        object.__setattr__(self, "samples", copied)


def read_pcm_window(path: Path, spec: DerivationSpec) -> PcmWindow:
    """Decode a bounded PCM crop from *path* without resampling or normalization."""
    if not path.is_file():
        msg = f"source WAV not found: {path}"
        raise PcmDerivationError(msg)

    try:
        with wave.open(str(path), "rb") as handle:
            if handle.getcomptype() != "NONE":
                msg = "compressed WAV is not supported"
                raise PcmDerivationError(msg)

            source_channels = handle.getnchannels()
            sample_width_bytes = handle.getsampwidth()
            sample_rate_hz = handle.getframerate()
            total_frames = handle.getnframes()

            if source_channels <= 0:
                msg = "source WAV has no channels"
                raise PcmDerivationError(msg)
            if sample_width_bytes not in (1, 2, 3, 4):
                msg = f"unsupported sample width: {sample_width_bytes}"
                raise PcmDerivationError(msg)
            if sample_rate_hz <= 0:
                msg = "sample rate must be positive"
                raise PcmDerivationError(msg)
            if total_frames <= 0:
                msg = "source WAV contains no frames"
                raise PcmDerivationError(msg)
            if spec.channel_index >= source_channels:
                msg = (
                    f"channel_index {spec.channel_index} out of range "
                    f"for {source_channels} channels"
                )
                raise PcmDerivationError(msg)
            if spec.start_frame >= total_frames:
                msg = "start_frame is beyond source frame count"
                raise PcmDerivationError(msg)
            if spec.stop_frame > total_frames:
                msg = "stop_frame exceeds source frame count"
                raise PcmDerivationError(msg)

            frame_count = spec.stop_frame - spec.start_frame
            _validate_output_bounds(frame_count, sample_rate_hz)

            handle.setpos(spec.start_frame)
            raw = handle.readframes(frame_count)
    except wave.Error as exc:
        msg = f"unsupported source WAV: {exc}"
        raise PcmDerivationError(msg) from exc

    samples = _decode_selected_channel(
        raw,
        frame_count=frame_count,
        source_channels=source_channels,
        sample_width_bytes=sample_width_bytes,
        channel_index=spec.channel_index,
    )
    return PcmWindow(
        samples=samples,
        sample_rate_hz=sample_rate_hz,
        sample_width_bytes=sample_width_bytes,
        source_channels=source_channels,
    )


def encode_pcm24_mono(samples: np.ndarray, sample_rate_hz: int) -> bytes:
    """Encode mono float32 samples as a little-endian 24-bit PCM WAV."""
    if sample_rate_hz <= 0:
        msg = "sample rate must be positive"
        raise PcmDerivationError(msg)
    if samples.ndim != 1:
        msg = "samples must be a mono 1-D array"
        raise PcmDerivationError(msg)

    mono = np.ascontiguousarray(samples, dtype=np.float32)
    _validate_output_bounds(mono.shape[0], sample_rate_hz)

    pcm_bytes = _quantize_pcm24(mono)
    fmt_payload = struct.pack(
        "<HHIIHH",
        1,
        1,
        sample_rate_hz,
        sample_rate_hz * 3,
        3,
        24,
    )
    fmt_chunk = b"fmt " + struct.pack("<I", len(fmt_payload)) + fmt_payload
    data_chunk = b"data" + struct.pack("<I", len(pcm_bytes)) + pcm_bytes
    wave_payload = b"WAVE" + fmt_chunk + data_chunk
    riff = b"RIFF" + struct.pack("<I", len(wave_payload)) + wave_payload
    if len(riff) > _MAX_UPLOAD_BYTES:
        msg = "encoded WAV exceeds max_upload_bytes"
        raise PcmDerivationError(msg)
    return riff


def derive_analysis_wav(
    source: Path,
    spec: DerivationSpec,
    destination: Path,
) -> DerivedAsset:
    """Derive an immutable mono PCM24 analysis WAV compatible with the frozen loader."""
    _validate_destination_name(destination)
    if destination.exists():
        msg = f"destination already exists: {destination}"
        raise FileExistsError(msg)

    window = read_pcm_window(source, spec)
    payload = encode_pcm24_mono(window.samples, window.sample_rate_hz)
    destination.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    return DerivedAsset(
        path=str(destination),
        sha256=digest,
        sample_rate_hz=window.sample_rate_hz,
        sample_width_bytes=3,
        channels=1,
        frames=window.samples.shape[0],
    )


def _validate_destination_name(destination: Path) -> None:
    if not _ANALYSIS_WAV_PATTERN.fullmatch(destination.name):
        msg = (
            "analysis filename must match "
            "extwav_(development|validation|final_external_test)_[0-9a-f]{16}.wav"
        )
        raise PcmDerivationError(msg)


def _validate_output_bounds(frame_count: int, sample_rate_hz: int) -> None:
    if frame_count <= 0:
        msg = "derived frame count must be positive"
        raise PcmDerivationError(msg)
    if frame_count > _MAX_SAMPLE_FRAMES:
        msg = "frame count exceeds max_sample_frames"
        raise PcmDerivationError(msg)
    duration_s = frame_count / sample_rate_hz
    if duration_s > _MAX_DURATION_S:
        msg = "duration exceeds max_duration_s"
        raise PcmDerivationError(msg)


def _decode_selected_channel(
    raw: bytes,
    *,
    frame_count: int,
    source_channels: int,
    sample_width_bytes: int,
    channel_index: int,
) -> np.ndarray:
    expected_bytes = frame_count * source_channels * sample_width_bytes
    if len(raw) != expected_bytes:
        msg = "decoded frame payload size mismatch"
        raise PcmDerivationError(msg)

    if sample_width_bytes == 1:
        raw8 = np.frombuffer(raw, dtype=np.uint8).reshape(frame_count, source_channels)
        channel = raw8[:, channel_index].astype(np.float64)
        samples = ((channel - 128.0) / 128.0).astype(np.float32)
    elif sample_width_bytes == 2:
        raw16 = np.frombuffer(raw, dtype="<i2").reshape(frame_count, source_channels)
        samples = (raw16[:, channel_index].astype(np.float64) / float(2**15)).astype(
            np.float32,
        )
    elif sample_width_bytes == 3:
        raw24 = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        values = (
            raw24[:, 0].astype(np.int32)
            | (raw24[:, 1].astype(np.int32) << 8)
            | (raw24[:, 2].astype(np.int32) << 16)
        )
        values = np.where(values & 0x800000, values - 0x1000000, values)
        channel_values = values.reshape(frame_count, source_channels)[:, channel_index]
        samples = (channel_values.astype(np.float64) / float(2**23)).astype(np.float32)
    else:
        raw32 = np.frombuffer(raw, dtype="<i4").reshape(frame_count, source_channels)
        samples = (raw32[:, channel_index].astype(np.float64) / float(2**31)).astype(
            np.float32,
        )
    return np.ascontiguousarray(samples, dtype=np.float32)


def _quantize_pcm24(samples: np.ndarray) -> bytes:
    clipped = np.clip(samples.astype(np.float64), -1.0, _POSITIVE_PCM24_LIMIT)
    quantized = np.round(clipped * float(2**23)).astype(np.int32)
    quantized = np.clip(quantized, -(2**23), 2**23 - 1)
    out = bytearray()
    for value in quantized:
        out.extend(int(value).to_bytes(3, "little", signed=True))
    return bytes(out)
