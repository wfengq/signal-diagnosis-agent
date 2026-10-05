"""Integer PCM WAV encoding aligned with ``signal_diag.signal.wav.load_wav_bytes``."""

from __future__ import annotations

import struct
from collections.abc import Sequence
from typing import Literal

import numpy as np

RoundingMode = Literal[
    "round",
    "trunc",
    "away_one_step",
    "toward_one_step",
    "random_one_step",
]
BitDepth = Literal[8, 16, 24, 32]
StepBits = Literal[16, 24, 32]


def _step_float(step_bits: StepBits) -> float:
    if step_bits == 32:
        return 2.0**-24
    return 2.0 ** (-(step_bits - 1))


def _step_in_codes(step_bits: StepBits, file_bits: BitDepth) -> int:
    step_f = _step_float(step_bits)
    if file_bits == 8:
        return max(1, round(step_f * 128.0))
    if file_bits == 16:
        return max(1, round(step_f * 32768.0))
    if file_bits == 24:
        return max(1, round(step_f * float(2**23)))
    return max(128, round(step_f * float(2**31)))


def _quantize_round(x: np.ndarray, *, bits: BitDepth) -> np.ndarray:
    mono = np.asarray(x, dtype=np.float64)
    if bits == 8:
        signed = np.rint(mono * 128.0)
        signed = np.clip(signed, -128, 127)
        return signed.astype(np.int64) + 128
    if bits == 16:
        q = np.rint(mono * 32768.0)
        return np.clip(q, -32768, 32767).astype(np.int64)
    if bits == 24:
        q = np.rint(mono * float(2**23))
        return np.clip(q, -(2**23), 2**23 - 1).astype(np.int64)
    q = np.rint(mono * float(2**24))
    q = np.clip(q, -(2**24), 2**24 - 1)
    return (q * 128).astype(np.int64)


def _quantize_trunc(x: np.ndarray, *, bits: BitDepth) -> np.ndarray:
    mono = np.asarray(x, dtype=np.float64)
    if bits == 8:
        signed = np.trunc(mono * 128.0)
        signed = np.clip(signed, -128, 127)
        return signed.astype(np.int64) + 128
    if bits == 16:
        q = np.trunc(mono * 32768.0)
        return np.clip(q, -32768, 32767).astype(np.int64)
    if bits == 24:
        q = np.trunc(mono * float(2**23))
        return np.clip(q, -(2**23), 2**23 - 1).astype(np.int64)
    q = np.trunc(mono * float(2**24))
    q = np.clip(q, -(2**24), 2**24 - 1)
    return (q * 128).astype(np.int64)


def _apply_step_offset(
    codes: np.ndarray,
    *,
    direction: Literal["away", "toward", "random"],
    step: int,
    seed: int | None,
) -> np.ndarray:
    out = codes.astype(np.int64, copy=True)
    if direction == "away":
        positive = out > 0
        negative = out < 0
        zero = out == 0
        out[positive] += step
        out[negative] -= step
        out[zero] += step
    elif direction == "toward":
        positive = out > 0
        negative = out < 0
        out[positive] -= step
        out[negative] += step
    else:
        if seed is None:
            msg = "random_one_step requires seed"
            raise ValueError(msg)
        rng = np.random.default_rng(seed)
        deltas = rng.choice(np.array([-step, step], dtype=np.int64), size=out.shape[0])
        out = out + deltas
    return out


def _clip_codes(codes: np.ndarray, *, bits: BitDepth) -> np.ndarray:
    if bits == 8:
        return np.clip(codes, 0, 255).astype(np.int64)
    if bits == 16:
        return np.clip(codes, -32768, 32767).astype(np.int64)
    if bits == 24:
        return np.clip(codes, -(2**23), 2**23 - 1).astype(np.int64)
    # 32-bit codes live on the 2^-24 grid (A.6): clip to the grid's extremes.
    return np.clip(codes, -(2**24) * 128, (2**24 - 1) * 128).astype(np.int64)


def _encode_channel_codes(
    x: np.ndarray,
    *,
    bits: BitDepth,
    rounding: RoundingMode,
    step_bits: StepBits,
    seed: int | None,
) -> np.ndarray:
    if rounding == "trunc":
        codes = _quantize_trunc(x, bits=bits)
        return _clip_codes(codes, bits=bits)
    if rounding == "round":
        codes = _quantize_round(x, bits=bits)
        return _clip_codes(codes, bits=bits)

    base = _quantize_round(x, bits=bits)
    step = _step_in_codes(step_bits, bits)
    if rounding == "away_one_step":
        codes = _apply_step_offset(base, direction="away", step=step, seed=seed)
    elif rounding == "toward_one_step":
        codes = _apply_step_offset(base, direction="toward", step=step, seed=seed)
    elif rounding == "random_one_step":
        codes = _apply_step_offset(base, direction="random", step=step, seed=seed)
    else:
        msg = f"unsupported rounding mode: {rounding}"
        raise ValueError(msg)
    return _clip_codes(codes, bits=bits)


def _pack_codes(codes: np.ndarray, *, bits: BitDepth) -> bytes:
    if bits == 8:
        return codes.astype(np.uint8).tobytes()
    if bits == 16:
        return codes.astype("<i2").tobytes()
    if bits == 24:
        out = bytearray()
        for value in codes.astype(np.int64):
            out.extend(int(value).to_bytes(3, "little", signed=True))
        return bytes(out)
    return codes.astype("<i4").tobytes()


def _interleave_channel_bytes(channel_codes: list[np.ndarray], *, bits: BitDepth) -> bytes:
    if len(channel_codes) == 1:
        return _pack_codes(channel_codes[0], bits=bits)
    frames = channel_codes[0].shape[0]
    if bits == 8:
        interleaved = np.empty(frames * len(channel_codes), dtype=np.uint8)
        for ch_idx, codes in enumerate(channel_codes):
            interleaved[ch_idx:: len(channel_codes)] = codes.astype(np.uint8)
        return interleaved.tobytes()
    if bits == 16:
        interleaved = np.empty(frames * len(channel_codes), dtype="<i2")
        for ch_idx, codes in enumerate(channel_codes):
            interleaved[ch_idx:: len(channel_codes)] = codes.astype("<i2")
        return interleaved.tobytes()
    if bits == 32:
        interleaved = np.empty(frames * len(channel_codes), dtype="<i4")
        for ch_idx, codes in enumerate(channel_codes):
            interleaved[ch_idx:: len(channel_codes)] = codes.astype("<i4")
        return interleaved.tobytes()
    # 24-bit interleave
    out = bytearray()
    for frame in range(frames):
        for codes in channel_codes:
            value = int(codes[frame])
            out.extend(value.to_bytes(3, "little", signed=True))
    return bytes(out)


def encode_pcm_wav(
    channels: Sequence[np.ndarray],
    *,
    sr: int,
    bits: BitDepth,
    rounding: RoundingMode = "round",
    step_bits: StepBits | None = None,
    seed: int | None = None,
) -> bytes:
    """Encode float64 channel buffers as little-endian integer PCM WAV."""
    if sr <= 0:
        raise ValueError("sr must be positive")
    if not channels:
        raise ValueError("channels must not be empty")
    lengths = {int(np.asarray(ch).shape[0]) for ch in channels}
    if len(lengths) != 1:
        raise ValueError("all channels must have the same length")
    n_channels = len(channels)
    if n_channels not in (1, 2):
        raise ValueError("only mono or stereo PCM is supported")

    resolved_step: StepBits = step_bits if step_bits is not None else bits  # type: ignore[assignment]
    if resolved_step not in (16, 24, 32):
        resolved_step = 16 if bits == 8 else bits  # type: ignore[assignment]

    channel_codes = [
        _encode_channel_codes(
            np.asarray(ch, dtype=np.float64),
            bits=bits,
            rounding=rounding,
            step_bits=resolved_step,
            seed=seed,
        )
        for ch in channels
    ]
    data = _interleave_channel_bytes(channel_codes, bits=bits)
    block_align = n_channels * (bits // 8)
    byte_rate = sr * block_align
    fmt_payload = struct.pack(
        "<HHIIHH",
        1,
        n_channels,
        sr,
        byte_rate,
        block_align,
        bits,
    )
    chunks = [
        b"fmt " + struct.pack("<I", len(fmt_payload)) + fmt_payload,
        b"data" + struct.pack("<I", len(data)) + data,
    ]
    body = b"WAVE" + b"".join(
        chunk + (b"\x00" if len(chunk) % 2 else b"") for chunk in chunks
    )
    return b"RIFF" + struct.pack("<I", len(body)) + body
