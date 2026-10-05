"""T-CX372: integer PCM WAV encoder aligned with load_wav_bytes."""

from __future__ import annotations

import struct

import numpy as np

from signal_diag.evaluation.full_scale_characterization.pcm import encode_pcm_wav
from signal_diag.evaluation.full_scale_characterization.synthesis import sine
from signal_diag.signal.wav import load_wav_bytes


def _raw_pcm_payload(wav: bytes) -> memoryview:
    offset = 12
    view = memoryview(wav)
    data_payload: memoryview | None = None
    while offset < len(view):
        chunk_id = bytes(view[offset : offset + 4])
        size = int.from_bytes(view[offset + 4 : offset + 8], "little")
        data_start = offset + 8
        data_end = data_start + size
        if chunk_id == b"data":
            data_payload = view[data_start:data_end]
            break
        offset = data_end + (size % 2)
    assert data_payload is not None
    return data_payload


def _decode_codes_from_wav(wav: bytes, *, bits: int, channels: int = 1) -> np.ndarray:
    payload = _raw_pcm_payload(wav)
    if bits == 8:
        raw = np.frombuffer(payload, dtype=np.uint8).reshape(-1, channels)
        return raw[:, 0].astype(np.int64)
    if bits == 16:
        raw = np.frombuffer(payload, dtype="<i2").reshape(-1, channels)
        return raw[:, 0].astype(np.int64)
    if bits == 24:
        raw = np.frombuffer(payload, dtype=np.uint8).reshape(-1, 3)
        value = (
            raw[:, 0].astype(np.int32)
            | (raw[:, 1].astype(np.int32) << 8)
            | (raw[:, 2].astype(np.int32) << 16)
        )
        value = np.where(value & 0x800000, value - 0x1000000, value)
        return value.astype(np.int64)
    raw = np.frombuffer(payload, dtype="<i4").reshape(-1, channels)
    return raw[:, 0].astype(np.int64)


def _expected_codes_16(x: np.ndarray) -> np.ndarray:
    q = np.rint(x.astype(np.float64) * 32768.0)
    return np.clip(q, -32768, 32767).astype(np.int64)


def _expected_codes_24(x: np.ndarray) -> np.ndarray:
    q = np.rint(x.astype(np.float64) * float(2**23))
    return np.clip(q, -(2**23), 2**23 - 1).astype(np.int64)


def _expected_codes_8(x: np.ndarray) -> np.ndarray:
    signed = np.rint(x.astype(np.float64) * 128.0)
    signed = np.clip(signed, -128, 127)
    return (signed + 128).astype(np.int64)


def _expected_codes_32_round(x: np.ndarray) -> np.ndarray:
    q = np.rint(x.astype(np.float64) * float(2**24))
    q = np.clip(q, -(2**24), 2**24 - 1)
    return (q * 128).astype(np.int64)


def test_t_cx372_round_trip_codes_16_24_8() -> None:
    sr = 48_000
    x = sine(f0=997.0, sr=sr, duration_s=0.002, amplitude=0.989993, phase_rad=np.pi / 480.0)
    for bits, expected_fn, scale in (
        (16, _expected_codes_16, 32768.0),
        (24, _expected_codes_24, float(2**23)),
        (8, _expected_codes_8, 128.0),
    ):
        wav = encode_pcm_wav([x], sr=sr, bits=bits, rounding="round")
        loaded = load_wav_bytes(wav)
        decoded = loaded.record.samples[:, 0].astype(np.float64)
        if bits == 8:
            codes_from_decode = np.rint(decoded * scale + 128.0).astype(np.int64)
        else:
            codes_from_decode = np.rint(decoded * scale).astype(np.int64)
        expected = expected_fn(x)
        np.testing.assert_array_equal(codes_from_decode, expected)
        np.testing.assert_array_equal(_decode_codes_from_wav(wav, bits=bits), expected)


def test_t_cx372_round_trip_32_matches_float32_decode() -> None:
    sr = 48_000
    x = sine(f0=440.0, sr=sr, duration_s=0.003, amplitude=0.9, phase_rad=0.0)
    wav = encode_pcm_wav([x], sr=sr, bits=32, rounding="round")
    loaded = load_wav_bytes(wav)
    decoded = loaded.record.samples[:, 0]
    codes = _decode_codes_from_wav(wav, bits=32)
    expected_decode = (codes.astype(np.float64) / float(2**31)).astype(np.float32)
    np.testing.assert_array_equal(decoded, expected_decode)


def test_t_cx372_pm_one_no_overflow_all_bit_depths() -> None:
    sr = 48_000
    n = 8
    x = np.linspace(-1.0, 1.0, n, dtype=np.float64)
    for bits in (8, 16, 24, 32):
        wav = encode_pcm_wav([x], sr=sr, bits=bits, rounding="round")
        loaded = load_wav_bytes(wav)
        assert np.all(np.isfinite(loaded.record.samples))
        assert np.max(np.abs(loaded.record.samples)) <= 1.0 + 1e-6


def _step_float(step_bits: int) -> float:
    if step_bits == 32:
        return 2.0**-24
    return 2.0 ** (-(step_bits - 1))


def test_t_cx372_one_step_perturbations_bounded_and_directional() -> None:
    sr = 48_000
    rng = np.random.default_rng(1001)
    x = rng.uniform(-0.95, 0.95, size=256).astype(np.float64)
    for bits in (16, 24, 32):
        step_bits = bits if bits != 8 else 8
        base_wav = encode_pcm_wav([x], sr=sr, bits=bits, rounding="round")
        base = load_wav_bytes(base_wav).record.samples[:, 0].astype(np.float64)
        step = _step_float(step_bits)
        for mode in ("away_one_step", "toward_one_step"):
            wav = encode_pcm_wav([x], sr=sr, bits=bits, rounding=mode, step_bits=step_bits)
            pert = load_wav_bytes(wav).record.samples[:, 0].astype(np.float64)
            diff = pert - base
            assert np.all(np.abs(diff) <= step + 1e-6)
            mask_pos = base > 0
            mask_neg = base < 0
            if mode == "away_one_step":
                assert np.all(diff[mask_pos] >= -1e-7)
                assert np.all(diff[mask_neg] <= 1e-7)
            else:
                assert np.all(diff[mask_pos] <= 1e-7)
                assert np.all(diff[mask_neg] >= -1e-7)


def test_t_cx372_32bit_decode_offset_exactly_one_step_for_large_samples() -> None:
    sr = 48_000
    step = 2.0**-24
    x = np.array([0.5, -0.6, 0.75, -0.9], dtype=np.float64)
    base_wav = encode_pcm_wav([x], sr=sr, bits=32, rounding="round")
    base = load_wav_bytes(base_wav).record.samples[:, 0].astype(np.float64)
    away_wav = encode_pcm_wav([x], sr=sr, bits=32, rounding="away_one_step")
    away = load_wav_bytes(away_wav).record.samples[:, 0].astype(np.float64)
    np.testing.assert_allclose(away - base, np.sign(base) * step, rtol=0.0, atol=1e-7)


def test_t_cx372_random_one_step_seed_deterministic_and_varies() -> None:
    sr = 48_000
    x = sine(f0=200.0, sr=sr, duration_s=0.001, amplitude=0.3, phase_rad=0.0)
    a = encode_pcm_wav([x], sr=sr, bits=16, rounding="random_one_step", seed=42)
    b = encode_pcm_wav([x], sr=sr, bits=16, rounding="random_one_step", seed=42)
    c = encode_pcm_wav([x], sr=sr, bits=16, rounding="random_one_step", seed=43)
    assert a == b
    assert a != c


def test_t_cx372_32bit_trunc_differs_from_round_not_p0() -> None:
    sr = 48_000
    grid = (np.arange(1, 20, dtype=np.float64) + 0.6) * (2.0**-24)
    x = np.concatenate([grid, -grid])
    round_wav = encode_pcm_wav([x], sr=sr, bits=32, rounding="round")
    trunc_wav = encode_pcm_wav([x], sr=sr, bits=32, rounding="trunc")
    assert round_wav != trunc_wav
    round_codes = _decode_codes_from_wav(round_wav, bits=32)
    trunc_codes = _decode_codes_from_wav(trunc_wav, bits=32)
    assert np.any(round_codes != trunc_codes)


def test_t_cx372_does_not_import_app_pcm_wav() -> None:
    import ast
    from pathlib import Path

    path = Path(__file__).resolve().parents[3] / "src" / "signal_diag" / "evaluation" / "full_scale_characterization" / "pcm.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    assert "signal_diag.app.pcm_wav" not in modules
    assert not any(m.startswith("signal_diag.app") for m in modules)
