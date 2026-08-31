"""Strict bounded little-endian PCM WAV ingestion."""

import struct
from dataclasses import dataclass
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .exceptions import InvalidSignalError
from .factory import build_signal_record
from .models import SignalRecord

_PCM_SUBTYPE_GUID = bytes.fromhex("0100000000001000800000aa00389b71")
_FLOAT_SUBTYPE_GUID = bytes.fromhex("0300000000001000800000aa00389b71")


class WavDecodeError(InvalidSignalError):
    """Base error for bounded WAV ingestion."""


class UnsupportedWavError(WavDecodeError):
    """Unsupported WAV encoding or channel layout."""


class InvalidWavError(WavDecodeError):
    """Malformed or inconsistent RIFF/WAVE structure."""


class SignalLimitExceededError(WavDecodeError):
    """Valid WAV that exceeds configured resource limits."""


class WavLoadLimits(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_upload_bytes: int = Field(default=20 * 1024 * 1024, ge=1)
    max_sample_frames: int = Field(default=2_000_000, ge=1)
    max_duration_s: float = Field(default=30.0, gt=0.0)
    min_sample_rate_hz: int = Field(default=8_000, ge=1)
    max_sample_rate_hz: int = Field(default=192_000, ge=1)

    @model_validator(mode="after")
    def validate_rate_interval(self) -> "WavLoadLimits":
        if self.min_sample_rate_hz > self.max_sample_rate_hz:
            raise ValueError("min_sample_rate_hz must not exceed max_sample_rate_hz")
        return self


class WavSourceInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    filename: str | None = Field(default=None, max_length=255)
    file_size_bytes: int = Field(ge=0)
    format_tag: Literal["pcm", "extensible_pcm"]
    bits_per_sample: Literal[8, 16, 24, 32]
    sample_rate_hz: int = Field(gt=0)
    channels: Literal[1, 2]
    num_frames: int = Field(gt=0)
    duration_s: float = Field(gt=0.0)


@dataclass(frozen=True, slots=True)
class LoadedWav:
    record: SignalRecord
    source_info: WavSourceInfo


@dataclass(frozen=True, slots=True)
class _FmtFields:
    format_tag: Literal["pcm", "extensible_pcm"]
    channels: Literal[1, 2]
    sample_rate_hz: int
    bits_per_sample: Literal[8, 16, 24, 32]
    block_align: int


def _read_chunk_header(view: memoryview, offset: int) -> tuple[bytes, int, int]:
    if offset + 8 > len(view):
        raise InvalidWavError("truncated RIFF chunk header")
    chunk_id = bytes(view[offset : offset + 4])
    size = int.from_bytes(view[offset + 4 : offset + 8], "little")
    data_start = offset + 8
    remaining = len(view) - data_start
    if size > remaining:
        raise InvalidWavError("declared RIFF chunk exceeds input")
    data_end = data_start + size
    return chunk_id, data_start, data_end


def _display_filename(filename: str | None) -> str | None:
    if filename is None:
        return None
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    return basename[:255]


def _as_channels(channels: int) -> Literal[1, 2]:
    if channels == 1:
        return 1
    return 2


def _as_bits(bits: int) -> Literal[8, 16, 24, 32]:
    if bits == 8:
        return 8
    if bits == 16:
        return 16
    if bits == 24:
        return 24
    return 32


def _parse_fmt(fmt_payload: bytes) -> _FmtFields:
    if len(fmt_payload) < 16:
        raise InvalidWavError("fmt chunk is truncated")
    audio_format, channels, sample_rate, byte_rate, block_align, bits = struct.unpack_from(
        "<HHIIHH", fmt_payload, 0
    )

    if channels == 0:
        raise InvalidWavError("channel count is zero")
    if channels > 2:
        raise UnsupportedWavError("more than two channels is not supported")

    if audio_format == 3:
        raise UnsupportedWavError("IEEE float WAV is not supported")
    if audio_format not in (1, 0xFFFE):
        raise UnsupportedWavError("compressed or non-PCM WAV is not supported")

    format_tag: Literal["pcm", "extensible_pcm"]
    if audio_format == 1:
        if len(fmt_payload) == 16:
            pass
        elif len(fmt_payload) == 18:
            cb_size = int.from_bytes(fmt_payload[16:18], "little")
            if cb_size != 0:
                raise InvalidWavError("PCM fmt cbSize must be 0")
        else:
            raise InvalidWavError("unexpected PCM fmt chunk size")
        format_tag = "pcm"
    else:
        if len(fmt_payload) != 40:
            raise InvalidWavError("extensible fmt chunk must be 40 bytes")
        cb_size = int.from_bytes(fmt_payload[16:18], "little")
        valid_bits = int.from_bytes(fmt_payload[18:20], "little")
        subtype = bytes(fmt_payload[24:40])
        if cb_size != 22:
            raise InvalidWavError("extensible fmt cbSize must be 22")
        if subtype == _FLOAT_SUBTYPE_GUID:
            raise UnsupportedWavError("extensible IEEE float is not supported")
        if subtype != _PCM_SUBTYPE_GUID:
            raise UnsupportedWavError("non-PCM extensible subtype is not supported")
        if valid_bits != bits:
            raise UnsupportedWavError("valid bits must equal container bits")
        format_tag = "extensible_pcm"

    if bits not in (8, 16, 24, 32):
        raise UnsupportedWavError("unsupported PCM bit depth")
    if sample_rate <= 0:
        raise InvalidWavError("sample rate must be positive")

    expected_block_align = channels * (bits // 8)
    if block_align != expected_block_align:
        raise InvalidWavError("inconsistent block alignment")
    if byte_rate != sample_rate * block_align:
        raise InvalidWavError("inconsistent byte rate")

    return _FmtFields(
        format_tag=format_tag,
        channels=_as_channels(channels),
        sample_rate_hz=sample_rate,
        bits_per_sample=_as_bits(bits),
        block_align=block_align,
    )


def _decode_pcm(payload: memoryview, *, channels: int, bits: int) -> np.ndarray:
    if bits == 8:
        raw8 = np.frombuffer(payload, dtype=np.dtype("<u1")).reshape(-1, channels)
        samples = ((raw8.astype(np.float64) - 128.0) / 128.0).astype(np.float32)
    elif bits == 16:
        raw16 = np.frombuffer(payload, dtype=np.dtype("<i2")).reshape(-1, channels)
        samples = (raw16.astype(np.float64) / float(2**15)).astype(np.float32)
    elif bits == 24:
        raw24 = np.frombuffer(payload, dtype=np.uint8).reshape(-1, 3)
        value = (
            raw24[:, 0].astype(np.int32)
            | (raw24[:, 1].astype(np.int32) << 8)
            | (raw24[:, 2].astype(np.int32) << 16)
        )
        value = np.where(value & 0x800000, value - 0x1000000, value)
        samples = (value.astype(np.float64) / float(2**23)).astype(np.float32)
        samples = samples.reshape(-1, channels)
    else:
        raw32 = np.frombuffer(payload, dtype=np.dtype("<i4")).reshape(-1, channels)
        samples = (raw32.astype(np.float64) / float(2**31)).astype(np.float32)
    return np.ascontiguousarray(samples, dtype=np.float32)


def _parse_chunks(view: memoryview) -> tuple[bytes, memoryview]:
    offset = 12
    fmt_payload: bytes | None = None
    data_payload: memoryview | None = None
    seen_fmt = False
    seen_data = False

    while offset < len(view):
        chunk_id, data_start, data_end = _read_chunk_header(view, offset)
        size = data_end - data_start
        if chunk_id == b"fmt ":
            if seen_fmt:
                raise InvalidWavError("duplicate fmt chunk")
            seen_fmt = True
            fmt_payload = bytes(view[data_start:data_end])
        elif chunk_id == b"data":
            if not seen_fmt:
                raise InvalidWavError("data chunk before fmt chunk")
            if seen_data:
                raise InvalidWavError("duplicate data chunk")
            seen_data = True
            data_payload = view[data_start:data_end]
        offset = data_end
        if size % 2 == 1 and offset < len(view):
            if view[offset] != 0:
                raise InvalidWavError("odd-size chunk pad byte must be zero")
            offset += 1

    if not seen_fmt or fmt_payload is None:
        raise InvalidWavError("missing fmt chunk")
    if not seen_data or data_payload is None:
        raise InvalidWavError("missing data chunk")
    return fmt_payload, data_payload


def load_wav_bytes(
    data: bytes,
    *,
    filename: str | None = None,
    limits: WavLoadLimits = WavLoadLimits(),  # noqa: B008
) -> LoadedWav:
    if len(data) > limits.max_upload_bytes:
        raise SignalLimitExceededError("upload exceeds max_upload_bytes")
    if len(data) < 4:
        raise InvalidWavError("truncated RIFF header")

    magic = data[:4]
    if magic == b"RIFX":
        raise UnsupportedWavError("RIFX is not supported")
    if magic == b"RF64":
        raise UnsupportedWavError("RF64 is not supported")
    if magic != b"RIFF":
        raise InvalidWavError("not a little-endian RIFF container")
    if len(data) < 12:
        raise InvalidWavError("truncated RIFF/WAVE header")

    declared_size = int.from_bytes(data[4:8], "little")
    if declared_size != len(data) - 8:
        raise InvalidWavError("declared RIFF size does not match input")
    if data[8:12] != b"WAVE":
        raise InvalidWavError("RIFF form is not WAVE")

    view = memoryview(data)
    fmt_payload, data_payload = _parse_chunks(view)
    fields = _parse_fmt(fmt_payload)

    if fields.block_align <= 0:
        raise InvalidWavError("block alignment is zero")
    if len(data_payload) % fields.block_align != 0:
        raise InvalidWavError("data size is not a multiple of block_align")
    num_frames = len(data_payload) // fields.block_align
    if num_frames <= 0:
        raise InvalidWavError("data chunk contains no sample frames")

    duration_s = num_frames / fields.sample_rate_hz
    if not np.isfinite(duration_s):
        raise InvalidWavError("duration is not finite")

    if (
        fields.sample_rate_hz < limits.min_sample_rate_hz
        or fields.sample_rate_hz > limits.max_sample_rate_hz
    ):
        raise SignalLimitExceededError("sample rate outside allowed range")
    if num_frames > limits.max_sample_frames:
        raise SignalLimitExceededError("frame count exceeds max_sample_frames")
    if duration_s > limits.max_duration_s:
        raise SignalLimitExceededError("duration exceeds max_duration_s")

    samples = _decode_pcm(
        data_payload,
        channels=fields.channels,
        bits=fields.bits_per_sample,
    )
    display_name = _display_filename(filename)
    record = build_signal_record(
        samples,
        sample_rate_hz=fields.sample_rate_hz,
        source_type="wav",
        filename=display_name,
    )
    source_info = WavSourceInfo(
        filename=display_name,
        file_size_bytes=len(data),
        format_tag=fields.format_tag,
        bits_per_sample=fields.bits_per_sample,
        sample_rate_hz=fields.sample_rate_hz,
        channels=fields.channels,
        num_frames=num_frames,
        duration_s=record.meta.duration_s,
    )
    return LoadedWav(record=record, source_info=source_info)
