"""T-CX372/T-CX374/T-CX375 follow-ups: 32-bit grid clipping, M7 marking, harmonic inputs."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np

from signal_diag.evaluation.full_scale_characterization import executor
from signal_diag.evaluation.full_scale_characterization.executor import (
    measure_row,
    row_specs_for_pair,
)
from signal_diag.evaluation.full_scale_characterization.groups import (
    enumerate_source_groups,
)
from signal_diag.evaluation.full_scale_characterization.manifest import build_manifest
from signal_diag.evaluation.full_scale_characterization.pcm import encode_pcm_wav
from signal_diag.signal.wav import load_wav_bytes
from tests.evaluation.full_scale_characterization.mini_manifest import MINI


def _decode(wav: bytes) -> np.ndarray:
    return np.asarray(load_wav_bytes(wav, filename="x.wav").record.samples[:, 0], dtype=np.float64)


def _codes32(wav: bytes) -> np.ndarray:
    data = wav[wav.index(b"data") + 8 :]
    return np.frombuffer(data, dtype="<i4").astype(np.int64)


def test_t_cx372_32bit_offset_clips_on_the_2_pow_24_grid() -> None:
    x = np.array([1.0, 0.999999, -1.0, 0.5, -0.5])
    for rounding in ("away_one_step", "random_one_step"):
        wav = encode_pcm_wav([x], sr=48_000, bits=32, rounding=rounding, step_bits=32, seed=7)
        codes = _codes32(wav)
        assert np.all(codes % 128 == 0), rounding
        assert codes.max() <= (2**24 - 1) * 128
        assert codes.min() >= -(2**24) * 128
    away = _codes32(encode_pcm_wav([x], sr=48_000, bits=32, rounding="away_one_step", step_bits=32))
    assert away[0] == (2**24 - 1) * 128
    assert _decode(encode_pcm_wav([x], sr=48_000, bits=32, rounding="away_one_step", step_bits=32))[0] == np.float32(
        (2**24 - 1) / 2**24
    )
    # A 16-bit step on a 32-bit file (P9) also stays on the grid at full scale.
    p9 = _codes32(encode_pcm_wav([x], sr=48_000, bits=32, rounding="away_one_step", step_bits=16))
    assert np.all(p9 % 128 == 0) and p9.max() == (2**24 - 1) * 128


def test_t_cx374_m7_marks_one_to_three_samples_per_peak_for_m2_m3_m5() -> None:
    c = MINI.model_copy(
        update={
            "m2_calibration_peaks": (0.98, 0.9901, 1.0),
            "m3_calibration_levels": (0.9901,),
            "m3_calibration_depths": (0.9999, 0.9),
        }
    )
    marks = {
        (g.family, g.peak, g.level, g.depth): g.m7_marked
        for g in enumerate_source_groups(c)
        if g.side == "calibration" and g.family in {"M2", "M3", "M4"}
    }
    # 100 Hz at 48 kHz, phase 0: peak 0.9901 puts 3 samples per crest over 0.99; 1.0 puts 21.
    assert marks[("M2", 0.9901, None, None)] is True
    assert marks[("M2", 1.0, None, None)] is False
    assert marks[("M2", 0.98, None, None)] is False
    # Pre-clip peak 0.9901 / 0.9999 = 0.99020: 3 samples per crest; depth 0.9 flattens many.
    assert marks[("M3", None, 0.9901, 0.9999)] is True
    assert marks[("M3", None, 0.9901, 0.9)] is False
    assert all(v is False for (fam, *_), v in marks.items() if fam == "M4")


def test_t_cx375_harmonic_input_carries_channel_and_range_only() -> None:
    pair = next(p for p in build_manifest(MINI).pairs if p.family == "M2" and p.perturbation_code == "P0")
    spec = row_specs_for_pair(pair, file_duration_s=MINI.file_duration_s, full_scale_threshold=0.99, m9_layout=None)[0]
    seen = []
    real = executor.measure_output

    def spy(**kwargs):
        seen.append(kwargs["selection"].harmonic)
        return real(**kwargs)

    with patch.object(executor, "measure_output", side_effect=spy):
        row = measure_row(spec)
    assert row.terminal_state == "measured"
    (harmonic,) = seen
    assert harmonic.fundamental_hz is None
    assert harmonic.channel == spec.channel and harmonic.time_range == spec.time_range
