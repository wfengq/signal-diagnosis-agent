"""PCM WAV writer for study audio. Integer scaling is full-scale, not peak-normalized."""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np


def write_pcm16_wav(path: Path, samples: np.ndarray, *, sample_rate_hz: int) -> None:
    if samples.ndim != 2 or samples.shape[1] not in (1, 2):
        raise ValueError("samples must have shape (frames, 1 or 2)")
    if sample_rate_hz < 8000:
        raise ValueError("sample_rate_hz must be at least 8000")
    pcm = np.rint(np.asarray(samples, dtype=np.float64) * float(2**15))
    clipped = np.clip(pcm, -float(2**15), float(2**15 - 1)).astype("<i2")
    data = np.ascontiguousarray(clipped).tobytes()
    channels = int(samples.shape[1])
    bits = 16
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
    body = b"WAVE" + b"".join(chunks)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"RIFF" + struct.pack("<I", len(body)) + body)
