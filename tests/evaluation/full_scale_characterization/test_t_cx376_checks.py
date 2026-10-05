"""T-CX376: C.2 sanity aborts and P9 out-of-fixed-zone flip counting."""

from __future__ import annotations

import math
from functools import cache
from unittest.mock import patch

import pytest

from signal_diag.evaluation.full_scale_characterization.checks import (
    CHECK_FACTS,
    CHECK_P0,
    CHECK_P7_EQUALITY,
    CHECK_P7_FLIP,
    CHECK_SANDWICH,
    measure_pair_checked,
    p9_out_of_zone_flip_counts,
    run_sanity_checks,
)
from signal_diag.evaluation.full_scale_characterization.executor import assemble_pair
from signal_diag.evaluation.full_scale_characterization.manifest import build_manifest
from signal_diag.evaluation.full_scale_characterization.models import (
    EffectiveMaterialParams,
    Manifest,
    MeasuredPair,
    PairRecord,
    SanityAbort,
    SourceGroupRecord,
)
from signal_diag.evaluation.full_scale_characterization.pairs import TOLERANCE_CODES
from tests.evaluation.full_scale_characterization.mini_manifest import MINI

THR = MINI.full_scale_threshold
DUR = MINI.file_duration_s

# 100 Hz at 48 kHz, phase pi/480: the two samples straddling each crest equal
# A*cos(pi/480).  A is chosen so that, after 16-bit rounding, the crest pair lies in
# [thr, thr + 2^-15): count(x, thr + d) = 0 while count(x, thr) = count(x, thr - d) > 0.
_NEAR_PEAK = 0.9900365
# Review counterexample (plan A.10): 16-bit round peak below thr - 2^-15, yet a 32-bit
# file shifted away by one 16-bit step crosses the threshold.
_P9_COUNTEREXAMPLE_PEAK = 0.989993


@cache
def _manifest() -> Manifest:
    return build_manifest(MINI)


def _group(family: str) -> SourceGroupRecord:
    return next(
        g for g in _manifest().source_groups if g.family == family and g.side == "calibration"
    )


def _tolerance_pairs(group: SourceGroupRecord) -> list[PairRecord]:
    return [
        p
        for p in _manifest().pairs
        if p.source_group_key == group.group_key and p.perturbation_code in TOLERANCE_CODES
    ]


def _pair(code: str, detail_contains: str = "", family: str = "M2") -> PairRecord:
    group = _group(family)
    return next(
        p
        for p in _tolerance_pairs(group)
        if p.perturbation_code == code and detail_contains in p.perturbation_detail
    )


def _with_peak(pair: PairRecord, peak: float, phase_rad: float = math.pi / 480.0) -> PairRecord:
    def _eff(eff: EffectiveMaterialParams) -> EffectiveMaterialParams:
        return eff.model_copy(update={"peak": peak, "phase_rad": phase_rad})

    return pair.model_copy(
        update={
            "pair_id": f"{pair.pair_id}-peak{peak}",
            "old_side": pair.old_side.model_copy(update={"effective": _eff(pair.old_side.effective)}),
            "new_side": pair.new_side.model_copy(update={"effective": _eff(pair.new_side.effective)}),
        }
    )


def _measure(pair: PairRecord, m9_layout: dict | None = None) -> list[MeasuredPair]:
    rows = measure_pair_checked(
        pair, file_duration_s=DUR, full_scale_threshold=THR, m9_layout=m9_layout
    )
    channels = ("left", "right") if pair.family == "M9" else ("left",)
    return [assemble_pair(pair, rows, channel=ch) for ch in channels]  # type: ignore[arg-type]


def _check(pair: PairRecord, measured: MeasuredPair, m9_layout: dict | None = None):
    return run_sanity_checks(
        [(pair, measured)],
        file_duration_s=DUR,
        full_scale_threshold=THR,
        m9_layouts={pair.pair_id: m9_layout} if m9_layout is not None else None,
    )


def _tamper_new(measured: MeasuredPair, **updates: object) -> MeasuredPair:
    new_row = measured.new_row.model_copy(update=updates)
    update: dict[str, object] = {"new_row": new_row}
    if "counted_samples" in updates:
        assert measured.old_row.counted_samples is not None
        count = updates["counted_samples"]
        assert isinstance(count, int)
        update["count_diff"] = count - measured.old_row.counted_samples
    return measured.model_copy(update=update)


def _assert_abort(excinfo: pytest.ExceptionInfo[SanityAbort], pair: PairRecord, check: str) -> None:
    message = str(excinfo.value)
    assert pair.pair_id in message
    assert check in message


@cache
def _near_p7(code: str) -> tuple[PairRecord, MeasuredPair]:
    pair = _with_peak(_pair(code, "bits=16"), _NEAR_PEAK)
    return pair, _measure(pair)[0]


def test_t_cx376_near_material_separates_the_three_thresholds() -> None:
    _, measured = _near_p7("P7b")
    assert measured.old_row.counted_samples is not None
    assert measured.old_row.counted_samples > 0
    assert measured.new_row.counted_samples == 0
    assert measured.flip is True


def test_t_cx376_all_checks_pass_on_legal_material() -> None:
    items: list[tuple[PairRecord, MeasuredPair]] = []
    layouts: dict[str, dict] = {}
    for family in ("M2", "M3", "M9"):
        group = _group(family)
        for pair in _tolerance_pairs(group):
            if family == "M2":
                pair = _with_peak(pair, _NEAR_PEAK)
            if group.m9_layout is not None:
                layouts[pair.pair_id] = group.m9_layout
            for measured in _measure(pair, group.m9_layout):
                items.append((pair, measured))
    codes = {p.perturbation_code for p, _ in items}
    assert codes == set(TOLERANCE_CODES)
    assert any(m.flip for _, m in items)
    counts = run_sanity_checks(
        items, file_duration_s=DUR, full_scale_threshold=THR, m9_layouts=layouts
    )
    assert counts.out_of_zone_k2_total == 0


def test_t_cx376_p0_nonzero_count_diff_aborts() -> None:
    pair = _pair("P0", "bits=16", family="M3")
    measured = _measure(pair)[0]
    assert measured.old_row.counted_samples is not None
    tampered = _tamper_new(measured, counted_samples=measured.old_row.counted_samples + 1)
    with pytest.raises(SanityAbort) as excinfo:
        _check(pair, tampered)
    _assert_abort(excinfo, pair, CHECK_P0)


def test_t_cx376_p0_wav_sha256_mismatch_aborts() -> None:
    pair = _pair("P0", "bits=24", family="M3")
    measured = _measure(pair)[0]
    tampered = _tamper_new(measured, wav_sha256="f" * 64)
    with pytest.raises(SanityAbort) as excinfo:
        _check(pair, tampered)
    _assert_abort(excinfo, pair, CHECK_P0)


def test_t_cx376_sandwich_upper_bound_violation_aborts() -> None:
    pair = _pair("P4", "coarse16<-fine32", family="M3")
    measured = _measure(pair)[0]
    assert measured.new_row.counted_samples is not None
    tampered = _tamper_new(measured, counted_samples=measured.new_row.counted_samples + 7)
    with pytest.raises(SanityAbort) as excinfo:
        _check(pair, tampered)
    _assert_abort(excinfo, pair, CHECK_SANDWICH)


def test_t_cx376_sandwich_lower_bound_violation_aborts() -> None:
    pair = _pair("P7d", "bits=16", family="M3")
    measured = _measure(pair)[0]
    assert measured.new_row.counted_samples is not None
    assert measured.new_row.counted_samples > 0
    tampered = _tamper_new(measured, counted_samples=0)
    with pytest.raises(SanityAbort) as excinfo:
        _check(pair, tampered)
    _assert_abort(excinfo, pair, CHECK_SANDWICH)


def test_t_cx376_p9_sandwich_uses_two_steps_and_still_aborts_outside() -> None:
    pair = _with_peak(_pair("P9a", "coarse16<-fine32"), _P9_COUNTEREXAMPLE_PEAK)
    measured = _measure(pair)[0]
    assert measured.new_row.counted_samples is not None
    tampered = _tamper_new(measured, counted_samples=measured.new_row.counted_samples + 1)
    with pytest.raises(SanityAbort) as excinfo:
        _check(pair, tampered)
    _assert_abort(excinfo, pair, CHECK_SANDWICH)


def test_t_cx376_p7a_equality_violation_aborts() -> None:
    pair, measured = _near_p7("P7a")
    assert measured.new_row.counted_samples is not None
    assert measured.new_row.counted_samples > 0
    # 0 stays inside the sandwich [count(x, thr+d), count(x, thr-d)] = [0, n].
    tampered = _tamper_new(measured, counted_samples=0)
    with pytest.raises(SanityAbort) as excinfo:
        _check(pair, tampered)
    _assert_abort(excinfo, pair, CHECK_P7_EQUALITY)


def test_t_cx376_p7b_equality_violation_aborts() -> None:
    pair, measured = _near_p7("P7b")
    assert measured.old_row.counted_samples is not None
    tampered = _tamper_new(
        measured, counted_samples=measured.old_row.counted_samples, state="yes"
    )
    with pytest.raises(SanityAbort) as excinfo:
        _check(pair, tampered)
    _assert_abort(excinfo, pair, CHECK_P7_EQUALITY)


def test_t_cx376_p7_flip_outside_fixed_zone_aborts() -> None:
    pair, measured = _near_p7("P7b")
    assert measured.flip is True
    assert measured.new_row.state == "no"
    tampered = _tamper_new(measured, peak_abs=0.9)
    with pytest.raises(SanityAbort) as excinfo:
        _check(pair, tampered)
    _assert_abort(excinfo, pair, CHECK_P7_FLIP)


def test_t_cx376_facts_verification_failure_aborts_with_pair_id() -> None:
    pair = _pair("P0", "bits=32", family="M1")
    with (
        patch(
            "signal_diag.evaluation.full_scale_characterization.executor.verify_full_scale_facts",
            side_effect=ValueError("full-scale facts digest mismatch"),
        ),
        pytest.raises(SanityAbort) as excinfo,
    ):
        measure_pair_checked(pair, file_duration_s=DUR, full_scale_threshold=THR, m9_layout=None)
    _assert_abort(excinfo, pair, CHECK_FACTS)
    assert "digest mismatch" in str(excinfo.value)


def test_t_cx376_p9_flip_outside_k1_zone_is_counted_not_aborted() -> None:
    pair = _with_peak(_pair("P9a", "coarse16<-fine32"), _P9_COUNTEREXAMPLE_PEAK)
    measured = _measure(pair)[0]
    assert measured.flip is True
    assert measured.old_row.state == "no"
    assert measured.old_row.peak_abs is not None
    assert measured.old_row.peak_abs < THR - 2.0**-15

    counts = _check(pair, measured)
    assert counts.flips_by_code == {"P9a": 1}
    assert counts.out_of_zone_k1_by_code == {"P9a": 1}
    assert counts.out_of_zone_k2_by_code == {}
    assert counts.out_of_zone_k1_total == 1
    assert counts.out_of_zone_k2_total == 0

    direct = p9_out_of_zone_flip_counts([(pair, measured)], full_scale_threshold=THR)
    assert direct == counts


# Crest pair at A*cos(pi/480) between thr - 4*2^-15 and thr - 2*2^-15 after 16-bit rounding.
_BETWEEN_2_AND_4_STEPS_PEAK = 0.9899296


def test_t_cx376_p9_deviation_beyond_two_steps_aborts() -> None:
    """A P9 count only reachable with |y - x| in (2d, 4d] must abort (guards d' = 2d, not 4d)."""
    pair = _with_peak(_pair("P9a", "coarse16<-fine32"), _BETWEEN_2_AND_4_STEPS_PEAK)
    measured = _measure(pair)[0]
    assert measured.old_row.counted_samples == 0
    assert measured.old_row.peak_abs is not None
    step = 2.0**-15
    assert THR - 4 * step < measured.old_row.peak_abs < THR - 2 * step
    tampered = _tamper_new(measured, counted_samples=40)
    with pytest.raises(SanityAbort) as excinfo:
        _check(pair, tampered)
    _assert_abort(excinfo, pair, CHECK_SANDWICH)
