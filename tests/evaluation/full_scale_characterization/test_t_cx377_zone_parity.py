"""T-CX377: zone.py K1–K3 / F1 / F2 predicates agree case-for-case with the product rules."""

from __future__ import annotations

import inspect
import itertools
from typing import Literal

from signal_diag.evaluation.full_scale_characterization import zone
from signal_diag.evaluation.full_scale_characterization.zone import (
    SideFacts,
    ZoneParams,
    exceeds_floor,
    in_zone,
    quantization_step,
)
from signal_diag.rules import full_scale_check as product
from signal_diag.rules.full_scale_check import (
    FullScaleMethodFloor,
    _in_critical_zone,
    _judgment_status,
    _quantization_step,
)
from signal_diag.tools.regression_full_scale import FullScaleFacts
from tests.rules.full_scale_fixtures import FIXTURE_FLOOR, redigest

THR = 0.99
_HEX = "a" * 64
Bits = Literal[16, 24, 32]


def _facts(
    *, state: Literal["yes", "no"], peak: float, counted: int, analyzed: int = 4800, bits: Bits = 16
) -> FullScaleFacts:
    return FullScaleFacts(
        side="baseline",
        run_id="run_x",
        wav_sha256=_HEX,
        bundle_digest=_HEX,
        full_scale_threshold=THR,
        min_consecutive_samples=2,
        counted_samples=counted,
        over_threshold_uncounted=0,
        state=state,
        peak_abs=peak,
        analyzed_samples=analyzed,
        pcm_bit_depth=bits,
        facts_version=FIXTURE_FLOOR.facts_version,
        digest=_HEX,
    )


def _side(f: FullScaleFacts) -> SideFacts:
    return SideFacts(
        state=f.state,
        peak_abs=f.peak_abs,
        counted_samples=f.counted_samples,
        analyzed_samples=f.analyzed_samples,
        pcm_bit_depth=f.pcm_bit_depth,
    )


def _floor(**updates: object) -> FullScaleMethodFloor:
    return redigest(FIXTURE_FLOOR.model_copy(update=updates))


def _zone_for(floor: FullScaleMethodFloor) -> ZoneParams:
    if floor.zone_min_counted_samples is not None:
        form: Literal["K1", "K2", "K3"] = "K3"
    elif floor.zone_below_threshold == floor.zone_above_threshold:
        form = "K1"
    else:
        form = "K2"
    return ZoneParams(
        form=form,
        zone_below=floor.zone_below_threshold,
        zone_above=floor.zone_above_threshold,
        min_counted=floor.zone_min_counted_samples,
    )


def test_t_cx377_quantization_step_matches_product() -> None:
    for a, b in itertools.product((8, 16, 24, 32), repeat=2):
        base = _facts(state="no", peak=0.5, counted=0, bits=a)  # type: ignore[arg-type]
        cand = _facts(state="no", peak=0.5, counted=0, bits=b)  # type: ignore[arg-type]
        assert quantization_step(a, b) == _quantization_step(base, cand)
        assert quantization_step(a) == _quantization_step(base, None)
    assert quantization_step() == _quantization_step(None, None)


def test_t_cx377_zone_k1_k2_k3_match_product_in_critical_zone() -> None:
    floors: list[FullScaleMethodFloor | None] = [
        None,
        _floor(zone_below_threshold=0.0, zone_above_threshold=0.0),
        _floor(zone_below_threshold=0.002, zone_above_threshold=0.002),
        _floor(zone_below_threshold=0.002, zone_above_threshold=0.0005),
        _floor(zone_below_threshold=1e-5, zone_above_threshold=0.003),
        _floor(zone_below_threshold=0.001, zone_above_threshold=0.001, zone_min_counted_samples=8),
        _floor(zone_below_threshold=0.0, zone_above_threshold=0.0, zone_min_counted_samples=2),
    ]
    cases = 0
    for bits in (16, 24, 32):
        step = quantization_step(bits)
        for floor in floors:
            zb = floor.zone_below_threshold if floor else 0.0
            za = floor.zone_above_threshold if floor else 0.0
            no_peaks = {
                0.5,
                THR - 2 * step,
                THR - step,
                THR - step - 2**-30,
                THR - zb,
                THR - zb - 2**-30,
                THR - max(zb, step),
                THR,
            }
            yes_peaks = {THR, THR + za, THR + za + 2**-30, THR + 0.01, 1.0}
            for peak in sorted(no_peaks):
                f = _facts(state="no", peak=peak, counted=0, bits=bits)  # type: ignore[arg-type]
                expected = _in_critical_zone(f, threshold=THR, step=step, floor=floor)
                got = in_zone(
                    _side(f), threshold=THR, step=step, zone=_zone_for(floor) if floor else None
                )
                assert got == expected, (bits, floor, peak)
                cases += 1
            for peak, counted in itertools.product(sorted(yes_peaks), (1, 2, 7, 8, 9, 500)):
                f = _facts(state="yes", peak=peak, counted=counted, bits=bits)  # type: ignore[arg-type]
                expected = _in_critical_zone(f, threshold=THR, step=step, floor=floor)
                got = in_zone(
                    _side(f), threshold=THR, step=step, zone=_zone_for(floor) if floor else None
                )
                assert got == expected, (bits, floor, peak, counted)
                cases += 1
    assert cases > 300


def test_t_cx377_f1_f2_match_product_judgment_status() -> None:
    analyzed = 4800
    baseline = _facts(state="yes", peak=1.0, counted=100, analyzed=analyzed)
    for floor_samples in (0, 5, 10, 47):
        floor = _floor(count_floor_samples=floor_samples, count_floor_ratio=None)
        for diff in sorted({1, floor_samples - 1, floor_samples, floor_samples + 1, 1000}):
            if diff <= 0:
                continue
            expected = (
                _judgment_status("yes_to_yes_increase", diff, baseline, floor)
                == "regression_detected"
            )
            got = exceeds_floor(diff, analyzed, form="F2", value=floor_samples, absolute=False)
            assert got == expected, (floor_samples, diff)
    for ratio in (0.0, 5 / analyzed, 0.001, 0.0105):
        floor = _floor(count_floor_samples=None, count_floor_ratio=ratio)
        boundary = int(ratio * analyzed)
        for diff in sorted({1, boundary - 1, boundary, boundary + 1, 4800}):
            if diff <= 0:
                continue
            expected = (
                _judgment_status("yes_to_yes_increase", diff, baseline, floor)
                == "regression_detected"
            )
            got = exceeds_floor(diff, analyzed, form="F1", value=ratio, absolute=False)
            assert got == expected, (ratio, diff)


def test_t_cx377_hard_condition_uses_absolute_difference() -> None:
    assert exceeds_floor(-11, 4800, form="F2", value=10, absolute=True)
    assert not exceeds_floor(-11, 4800, form="F2", value=10, absolute=False)
    assert not exceeds_floor(-10, 4800, form="F2", value=10, absolute=True)
    assert exceeds_floor(-49, 4800, form="F1", value=0.01, absolute=True)
    assert not exceeds_floor(-48, 4800, form="F1", value=0.01, absolute=True)


def test_t_cx377_domain_expressions_are_verbatim_with_product() -> None:
    product_src = inspect.getsource(product.evaluate_full_scale_check)
    zone_src = inspect.getsource(zone)
    assert "sr / f0 < floor.min_samples_per_period" in product_src
    assert "analyzed_for_periods * f0 / sr < floor.min_periods_in_range" in product_src
    assert "return sr / f0" in zone_src
    assert "return analyzed_for_periods * f0 / sr" in zone_src
    assert "analyzed_for_periods = anchor_base.analyzed_samples" in product_src
    assert "analyzed_for_periods = pair.old_facts.analyzed_samples" in zone_src
