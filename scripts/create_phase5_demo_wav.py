#!/usr/bin/env python3
"""Write a deterministic one-second 48 kHz mono 16-bit PCM clipping WAV."""

from __future__ import annotations

import argparse
import io
import wave
from pathlib import Path

import numpy as np

from signal_diag.signal import generate_clipped_sine


def build_demo_wav_bytes() -> bytes:
    case = generate_clipped_sine(
        frequency_hz=220.0,
        sample_rate_hz=48_000,
        duration_s=1.0,
        amplitude=1.2,
        clip_level=0.65,
    )
    pcm = np.rint(
        np.clip(case.record.samples[:, 0], -1.0, 32767 / 32768) * 32768
    ).astype("<i2")
    output = io.BytesIO()
    with wave.open(output, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(48_000)
        stream.writeframes(pcm.tobytes())
    return output.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.write_bytes(build_demo_wav_bytes())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
