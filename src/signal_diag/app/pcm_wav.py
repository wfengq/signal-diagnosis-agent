"""App-layer integer PCM WAV encoder for Demo preset materialization."""

from __future__ import annotations

import struct

import numpy as np


def encode_pcm32_wav(
    samples: np.ndarray,
    *,
    sample_rate_hz: int,
) -> bytes:
    """Encode mono float32 samples as little-endian 32-bit integer PCM WAV.

    Integer PCM uses full-scale conversion without per-signal peak normalization,
    matching :func:`signal_diag.signal.wav.load_wav_bytes` decode polarity.
    """
    if samples.ndim != 2 or samples.shape[1] != 1:
        raise ValueError("samples must have shape (num_frames, 1)")
    if sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be positive")

    mono = np.asarray(samples[:, 0], dtype=np.float64)
    scaled = np.rint(mono * float(2**31))
    pcm = np.clip(scaled, -float(2**31), float(2**31 - 1)).astype("<i4")
    data = pcm.tobytes()
    channels = 1
    bits = 32
    block_align = channels * (bits // 8)
    byte_rate = sample_rate_hz * block_align
    fmt_payload = struct.pack(
        "<HHIIHH",
        1,
        channels,
        sample_rate_hz,
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
