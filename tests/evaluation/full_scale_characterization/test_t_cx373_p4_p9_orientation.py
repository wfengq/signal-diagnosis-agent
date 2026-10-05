"""T-CX373: P4/P9 tolerance pairs are oriented coarse-old / fine-new (plan B.3, C.1)."""

from __future__ import annotations

import math
from functools import cache

import numpy as np

from signal_diag.evaluation.full_scale_characterization.executor import measure_row
from signal_diag.evaluation.full_scale_characterization.manifest import build_manifest
from signal_diag.evaluation.full_scale_characterization.materials import (
    synthesize_side_waveform,
)
from signal_diag.evaluation.full_scale_characterization.models import (
    EffectiveMaterialParams,
    EncodingSpec,
    Manifest,
    MeasurementRowSpec,
    PairRecord,
    SideGenerationSpec,
)
from signal_diag.evaluation.full_scale_characterization.pcm import encode_pcm_wav
from signal_diag.signal.models import TimeRange
from signal_diag.signal.wav import load_wav_bytes
from tests.evaluation.full_scale_characterization.mini_manifest import MINI

_P4_P9 = ("P4", "P9a", "P9b", "P9c")


@cache
def _manifest() -> Manifest:
    return build_manifest(MINI)


def _pairs(codes: tuple[str, ...]) -> list[PairRecord]:
    return [p for p in _manifest().pairs if p.perturbation_code in codes]


def _coarse_step(bits: int) -> float:
    return 2.0**-24 if bits == 32 else 2.0 ** (-(bits - 1))


def _decoded(side: SideGenerationSpec, encoding: EncodingSpec) -> np.ndarray:
    channels = synthesize_side_waveform(
        side, file_duration_s=MINI.file_duration_s, m9_layout=None
    )
    wav = encode_pcm_wav(
        list(channels),
        sr=side.effective.sample_rate_hz,
        bits=encoding.bits,
        rounding=encoding.rounding,
        step_bits=encoding.step_bits,
        seed=encoding.seed,
    )
    loaded = load_wav_bytes(wav, filename=encoding.filename)
    return np.asarray(loaded.record.samples[:, 0], dtype=np.float64)


def test_t_cx373_p4_p9_old_side_is_coarser_bit_depth() -> None:
    pairs = _pairs(_P4_P9)
    assert pairs
    combos: set[tuple[str, int, int]] = set()
    for pair in pairs:
        old_bits = pair.old_side.encoding.bits
        new_bits = pair.new_side.encoding.bits
        assert old_bits < new_bits, (pair.perturbation_code, pair.perturbation_detail)
        combos.add((pair.perturbation_code, old_bits, new_bits))
        assert pair.perturbation_detail == f"coarse{old_bits}<-fine{new_bits}"
    expected = {(code, c, f) for code in _P4_P9 for c, f in ((16, 32), (16, 24), (24, 32))}
    assert combos == expected


def test_t_cx373_p4_both_sides_round() -> None:
    for pair in _pairs(("P4",)):
        assert pair.old_side.encoding.rounding == "round"
        assert pair.new_side.encoding.rounding == "round"


def test_t_cx373_p9c_old_side_truncates_coarse_new_side_rounds_fine() -> None:
    pairs = _pairs(("P9c",))
    assert pairs
    for pair in pairs:
        assert pair.old_side.encoding.rounding == "trunc"
        assert pair.new_side.encoding.rounding == "round"
        assert pair.new_side.encoding.step_bits is None


def test_t_cx373_p9ab_fine_file_shifted_by_exactly_one_coarse_step() -> None:
    pairs = [
        p
        for p in _pairs(("P9a", "P9b"))
        if p.family == "M2" and p.side == "calibration"
    ]
    assert len(pairs) == 6
    for pair in pairs:
        old_enc = pair.old_side.encoding
        new_enc = pair.new_side.encoding
        assert old_enc.rounding == "round"
        assert new_enc.step_bits == old_enc.bits
        expected_rounding = "away_one_step" if pair.perturbation_code == "P9a" else "toward_one_step"
        assert new_enc.rounding == expected_rounding

        shifted = _decoded(pair.new_side, new_enc)
        rounded = _decoded(
            pair.new_side,
            new_enc.model_copy(update={"rounding": "round", "step_bits": None}),
        )
        mask = np.abs(rounded) >= 0.5
        assert np.count_nonzero(mask) > 0
        delta = np.abs(shifted[mask]) - np.abs(rounded[mask])
        step = _coarse_step(old_enc.bits)
        signed = step if pair.perturbation_code == "P9a" else -step
        np.testing.assert_array_equal(delta, np.full(delta.shape, signed))
        assert np.all(np.sign(shifted[mask]) == np.sign(rounded[mask]))


def test_t_cx373_p9a_review_counterexample_flips_on_full_tool_path() -> None:
    """Review reproduction (plan A.10); demonstrates the phenomenon only, not a floor."""
    effective = EffectiveMaterialParams(
        family="M2",
        f0_hz=100.0,
        sample_rate_hz=48_000,
        phase_rad=math.pi / 480.0,
        peak=0.989993,
    )
    old = SideGenerationSpec(
        encoding=EncodingSpec(bits=16, rounding="round"), effective=effective
    )
    new = SideGenerationSpec(
        encoding=EncodingSpec(bits=32, rounding="away_one_step", step_bits=16),
        effective=effective,
    )
    rows = {}
    for role, side in (("old", old), ("new", new)):
        rows[role] = measure_row(
            MeasurementRowSpec(
                side_spec=side,
                role=role,  # type: ignore[arg-type]
                channel="left",
                time_range=TimeRange(start_s=0.0, end_s=0.1),
                file_duration_s=0.1,
                full_scale_threshold=0.99,
            )
        )
    assert rows["old"].terminal_state == "measured"
    assert rows["new"].terminal_state == "measured"
    assert rows["old"].counted_samples == 0
    assert rows["old"].state == "no"
    assert rows["new"].counted_samples is not None and rows["new"].counted_samples > 0
    assert rows["new"].state == "yes"
