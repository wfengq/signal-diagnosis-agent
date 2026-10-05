"""T-CX377: two-stage calibration fitting on hand-made records (numbers test logic only)."""

from __future__ import annotations

import json
import math
from typing import Literal

import numpy as np
import pytest

from signal_diag.evaluation.full_scale_characterization import fitting
from signal_diag.evaluation.full_scale_characterization.constants import ROUND_1
from signal_diag.evaluation.full_scale_characterization.fitting import (
    K3_C_CANDIDATES,
    K_ROW_IDS,
    P_MIN_CANDIDATES,
    CalibrationOnlyError,
    RowLimitExceeded,
    Stage1Row,
    Stage1Selection,
    f3_cut_candidates,
    fit_stage1,
    fit_stage2,
    n_min_candidates,
    select_stage1,
)
from signal_diag.evaluation.full_scale_characterization.pairs import TOLERANCE_CODES
from signal_diag.evaluation.full_scale_characterization.reporting import (
    stage1_report_json,
    stage1_report_markdown,
    stage2_report_json,
    stage2_report_markdown,
)
from signal_diag.evaluation.full_scale_characterization.zone import (
    ScoredPair,
    SideFacts,
    ZoneParams,
    both_outside_zone,
    in_zone,
    is_primary_condition,
    quantization_step,
)
from tests.evaluation.full_scale_characterization.mini_manifest import MINI

THR = 0.99
STEP16 = quantization_step(16)
N = 480.0  # 48 kHz / 100 Hz
ANALYZED = 4800  # 10 periods

State = tuple[Literal["yes", "no"], float, int]
_counter = iter(range(10**6))


def rec(
    old: State,
    new: State,
    *,
    code: str = "P7a",
    family: str = "M2",
    kind: Literal["empty", "onset_change", "aggravation_change", "blind_change"] = "empty",
    side: Literal["calibration", "validation"] = "calibration",
    detail: str = "",
    bits: tuple[Literal[16, 24, 32], Literal[16, 24, 32]] = (16, 16),
    level: float | None = None,
    analyzed: int = ANALYZED,
    sr: int = 48_000,
    f0: float = 100.0,
    terminal: Literal["measured", "invalid", "generation_failed"] = "measured",
) -> ScoredPair:
    def facts(s: State, b: Literal[16, 24, 32]) -> SideFacts:
        return SideFacts(
            state=s[0], peak_abs=s[1], counted_samples=s[2], analyzed_samples=analyzed, pcm_bit_depth=b
        )

    return ScoredPair(
        pair_id=f"p{next(_counter)}",
        channel="left",
        side=side,
        kind=kind,
        family=family,
        perturbation_code=code,
        perturbation_detail=detail,
        is_tolerance=code in TOLERANCE_CODES,
        is_primary=is_primary_condition(family, level, THR),
        f0_hz=f0,
        sample_rate_hz=sr,
        range_length_s=analyzed / sr,
        terminal_state=terminal,
        old=facts(old, bits[0]) if terminal == "measured" else None,
        new=facts(new, bits[1]) if terminal == "measured" else None,
    )


def _rows(records: list[ScoredPair]) -> dict[str, Stage1Row]:
    return {r.row_id: r for r in fit_stage1(records, constants=MINI)}


def _rid(k: str, p: int = 1, n: float = N) -> str:
    return f"n={n!r};p={p};{k}"


# Flip population: no-sides at thr-0.002, thr-0.0005 and thr-1e-5 (inside the k=1
# fixed minimum, so removed); yes-sides at thr+0.003 (counted 3) and thr+0.001 (counted 40).
def _flip_population() -> list[ScoredPair]:
    return [
        rec(("no", THR - 0.002, 0), ("yes", THR + 0.003, 3)),
        rec(("yes", THR + 0.001, 40), ("no", THR - 0.0005, 0), code="P9a"),
        rec(("no", THR - 1e-5, 0), ("yes", THR + 0.001, 40), code="P4"),
        # Primary tolerance pair far from any zone (both yes, large counts).
        rec(("yes", 1.0, 400), ("yes", 1.0, 404), code="P7d", family="M3"),
    ]


def _assert_minimal_cover(points: list[SideFacts], zone: ZoneParams, which: str) -> None:
    for p in points:
        assert in_zone(p, threshold=THR, step=STEP16, zone=zone, n=N)
    value = zone.zone_below if which == "below" else zone.zone_above
    if value > 0:
        # Two ulps of the threshold: the finest resolution the predicate ``thr -/+ z`` has.
        tighter_value = max(0.0, value - 2 * float(np.spacing(THR)))
        tighter = zone.model_copy(
            update={("zone_below" if which == "below" else "zone_above"): tighter_value}
        )
        assert not all(in_zone(p, threshold=THR, step=STEP16, zone=tighter, n=N) for p in points)


def _sf(state: Literal["yes", "no"], peak: float, counted: int) -> SideFacts:
    return SideFacts(
        state=state, peak_abs=peak, counted_samples=counted, analyzed_samples=ANALYZED, pcm_bit_depth=16
    )


def test_t_cx377_candidate_tables_are_fixed() -> None:
    assert P_MIN_CANDIDATES == (1, 2, 5, 10, 20, 50, 100)
    assert K3_C_CANDIDATES == (2, 4, 8, 16, 32, 64)
    assert K_ROW_IDS == ("K1", "K2", "K4", "K3c2", "K3c4", "K3c8", "K3c16", "K3c32", "K3c64")
    round_1 = n_min_candidates(ROUND_1)
    assert len(round_1) == 12
    assert round_1 == tuple(sorted({sr / f0 for sr in ROUND_1.sample_rates for f0 in ROUND_1.calibration_f0}))
    assert n_min_candidates(MINI) == (N,)


def test_t_cx377_stage1_emits_every_domain_and_k_row() -> None:
    rows = fit_stage1(_flip_population(), constants=MINI)
    assert len(rows) == 1 * 7 * 9
    assert len({r.row_id for r in rows}) == len(rows)
    assert {(r.p_min, r.k_row) for r in rows} == {(p, k) for p in P_MIN_CANDIDATES for k in K_ROW_IDS}


def test_t_cx377_k2_k1_minimal_parameters_match_hand_calculation() -> None:
    rows = _rows(_flip_population())
    k2 = rows[_rid("K2")].zone
    assert k2.form == "K2"
    assert k2.zone_below == pytest.approx(0.002, rel=1e-12)
    assert k2.zone_above == pytest.approx(0.003, rel=1e-12)
    no_points = [_sf("no", THR - 0.002, 0), _sf("no", THR - 0.0005, 0), _sf("no", THR - 1e-5, 0)]
    yes_points = [_sf("yes", THR + 0.003, 3), _sf("yes", THR + 0.001, 40)]
    _assert_minimal_cover(no_points, k2, "below")
    _assert_minimal_cover(yes_points, k2, "above")

    k1 = rows[_rid("K1")].zone
    assert k1.form == "K1"
    assert k1.zone_below == k1.zone_above == max(k2.zone_below, k2.zone_above)
    for row in rows.values():
        assert row.zone.zone_below >= 0.0
        assert row.zone.zone_above >= 0.0


def test_t_cx377_points_inside_fixed_minimum_are_removed() -> None:
    only_fixed = [rec(("no", THR - 1e-5, 0), ("yes", THR + 0.001, 40), code="P4")]
    k2 = _rows(only_fixed)[_rid("K2")].zone
    assert k2.zone_below == 0.0
    assert k2.zone_above == pytest.approx(0.001, rel=1e-12)


def test_t_cx377_k4_uses_two_sample_level_and_is_non_negative() -> None:
    rows = _rows(_flip_population())
    k4 = rows[_rid("K4")].zone
    c = math.cos(math.pi / N)
    assert k4.form == "K4"
    assert k4.zone_below == pytest.approx(THR - (THR - 0.002) * c, rel=1e-9)
    assert k4.zone_above == pytest.approx(max(0.0, (THR + 0.003) * c - THR), rel=1e-9)
    # e below threshold on every yes side: zone_above clamps to 0, never negative.
    near = [rec(("no", THR - 0.002, 0), ("yes", THR + 1e-6, 2))]
    k4_near = _rows(near)[_rid("K4")].zone
    assert (THR + 1e-6) * c < THR
    assert k4_near.zone_above == 0.0
    for p in (_sf("no", THR - 0.002, 0), _sf("yes", THR + 0.003, 3), _sf("yes", THR + 0.001, 40)):
        assert in_zone(p, threshold=THR, step=STEP16, zone=k4, n=N)


def test_t_cx377_k3_rows_match_hand_calculation_and_use_or() -> None:
    rows = _rows(_flip_population())
    k2 = rows[_rid("K2")].zone
    expected_above = {2: 0.003, 4: 0.001, 8: 0.001, 16: 0.001, 32: 0.001, 64: 0.0}
    for c, above in expected_above.items():
        zone = rows[_rid(f"K3c{c}")].zone
        assert zone.form == "K3"
        assert zone.min_counted == c
        assert zone.zone_below == k2.zone_below
        assert zone.zone_above == pytest.approx(above, rel=1e-12, abs=0.0)
    k3 = rows[_rid("K3c8")].zone
    # "or": far above but few counted -> in zone; within za but many counted -> in zone.
    assert in_zone(_sf("yes", 1.0, 3), threshold=THR, step=STEP16, zone=k3)
    assert in_zone(_sf("yes", THR + 0.0005, 500), threshold=THR, step=STEP16, zone=k3)
    assert not in_zone(_sf("yes", 1.0, 500), threshold=THR, step=STEP16, zone=k3)


def test_t_cx377_k0_label_only_counts_tolerance_pairs_of_main_conditions() -> None:
    flips = _flip_population()[:3]
    outside_primary_tol = rec(("yes", 1.0, 400), ("yes", 1.0, 404), code="P7d", family="M3")
    outside_primary_sens = rec(("yes", 1.0, 400), ("yes", 1.0, 404), code="P5", family="M3")
    outside_nonprimary = rec(("no", 0.5, 0), ("no", 0.5, 0), code="P0", family="M1")
    m5_low = rec(("yes", 1.0, 400), ("yes", 1.0, 400), code="P0", family="M5", level=0.9)
    m5_high = rec(("yes", 1.0, 400), ("yes", 1.0, 400), code="P0", family="M5", level=0.995)

    assert not _rows([*flips, outside_primary_tol])[_rid("K2")].k0_degenerate
    assert _rows([*flips, outside_primary_sens])[_rid("K2")].k0_degenerate
    assert _rows([*flips, outside_nonprimary])[_rid("K2")].k0_degenerate
    assert _rows([*flips, m5_low])[_rid("K2")].k0_degenerate
    assert not _rows([*flips, m5_high])[_rid("K2")].k0_degenerate
    # Out of domain (p_min above the 10 periods available): no evidence -> K0.
    assert _rows([*flips, outside_primary_tol])[_rid("K2", p=20)].k0_degenerate


def test_t_cx377_k1_k2_flip_counts_reported_separately() -> None:
    records = [
        rec(("no", THR - 1.5 * STEP16, 0), ("yes", THR + 0.001, 40), code="P9a"),
        rec(("no", THR - 3 * STEP16, 0), ("yes", THR + 0.001, 40), code="P9b"),
        rec(("no", THR - 0.5 * STEP16, 0), ("yes", THR + 0.001, 40), code="P7c"),
    ]
    row = _rows(records)[_rid("K2")]
    assert row.flip_counts_by_code["P9a"].model_dump() == {"flips": 1, "outside_k1": 1, "outside_k2": 0}
    assert row.flip_counts_by_code["P9b"].model_dump() == {"flips": 1, "outside_k1": 1, "outside_k2": 1}
    assert row.flip_counts_by_code["P7c"].model_dump() == {"flips": 1, "outside_k1": 0, "outside_k2": 0}
    assert row.flip_totals.model_dump() == {"flips": 3, "outside_k1": 2, "outside_k2": 1}


def test_t_cx377_shares_and_onset_tiers() -> None:
    records = [
        *_flip_population(),
        rec(("no", 0.9, 0), ("yes", 0.995, 50), kind="onset_change", code="ONSET", family="M1", detail="depth=0.99"),
        rec(("no", 0.9, 0), ("yes", THR + 0.0001, 2), kind="onset_change", code="ONSET", family="M1", detail="depth=0.9995"),
        rec(("no", 0.9, 0), ("no", 0.9, 0), kind="onset_change", code="ONSET", family="M1", detail="depth=0.9995"),
        rec(("no", 0.5, 0), ("no", 0.5, 0), code="P0", family="M1", sr=48_000, f0=100.0, analyzed=480),
    ]
    rows = _rows(records)
    row = rows[_rid("K2", p=2)]
    tol = [r for r in records if r.is_tolerance]
    in_dom = [r for r in tol if r.old_facts.analyzed_samples == ANALYZED]
    assert row.in_domain_tolerance_pairs == len(in_dom)
    assert row.domain_share == pytest.approx(len(in_dom) / len(tol))
    judgeable = [r for r in in_dom if both_outside_zone(r, threshold=THR, zone=row.zone)]
    assert row.judgeable_share == pytest.approx(len(judgeable) / len(in_dom))
    assert row.domain_share_by_family["M1"] == 0.0
    assert row.onset_by_tier["depth=0.99"].detected == 1
    tier = row.onset_by_tier["depth=0.9995"]
    assert (tier.total, tier.detected, tier.in_zone, tier.not_detected) == (2, 0, 1, 1)


def test_t_cx377_fitting_rejects_validation_records() -> None:
    records = [*_flip_population(), rec(("no", 0.5, 0), ("no", 0.5, 0), side="validation")]
    with pytest.raises(CalibrationOnlyError):
        fit_stage1(records, constants=MINI)
    good = _flip_population()
    rows = fit_stage1(good, constants=MINI)
    selection = select_stage1(rows, _rid("K2"))
    with pytest.raises(CalibrationOnlyError):
        fit_stage2(records, selection=selection, stage1_rows=rows, constants=MINI)


def _stage2_population() -> list[ScoredPair]:
    return [
        *_flip_population(),
        rec(("yes", 1.0, 400), ("yes", 1.0, 390), code="P4", family="M3"),
        rec(("yes", 1.0, 400), ("yes", 1.0, 406), code="P9c", family="M3", analyzed=9600),
        rec(("yes", 1.0, 400), ("yes", 1.0, 401), code="P5", family="M3"),  # sensitivity: ignored
        rec(("yes", 1.0, 400), ("yes", 1.0, 403), kind="aggravation_change", code="AGGR", family="M3", detail="rel_peak=0.0001"),
        rec(("yes", 1.0, 400), ("yes", 1.0, 480), kind="aggravation_change", code="AGGR", family="M3", detail="rel_peak=0.1"),
    ]


def test_t_cx377_f1_f2_are_plain_maxima_without_margin() -> None:
    records = _stage2_population()
    rows = fit_stage1(records, constants=MINI)
    selection = select_stage1(rows, _rid("K2"))
    stage2 = {r.row_id: r for r in fit_stage2(records, selection=selection, stage1_rows=rows, constants=MINI)}
    # Applicable: both yes and both outside the K2 zone -> P7d (+4/4800), P4 (-10/4800), P9c (+6/9600).
    assert stage2["F2"].floor.value == 10.0
    assert stage2["F1"].floor.value == max(4 / 4800, 10 / 4800, 6 / 9600)
    assert stage2["F2"].applicable_pairs == 3
    assert stage2["F0"].floor.value is None
    aggr = stage2["F2"].aggravation_by_tier
    assert aggr["rel_peak=0.0001"].masked == 1
    assert aggr["rel_peak=0.1"].detected == 1
    assert stage2["F0"].aggravation_by_tier["rel_peak=0.0001"].masked == 0
    assert sum(stage2["F2"].excluded_by_reason.values()) > 0


def test_t_cx377_f3_only_single_cut_on_n_or_periods() -> None:
    records = _stage2_population()
    rows = fit_stage1(records, constants=MINI)
    selection = select_stage1(rows, _rid("K2"))
    stage2 = fit_stage2(records, selection=selection, stage1_rows=rows, constants=MINI)
    f3 = [r for r in stage2 if r.floor.form == "F3"]
    # MINI has a single N candidate (no cut above n_min); periods cuts above p_min=1.
    assert {r.floor.cut_variable for r in f3} == {"periods"}
    assert {r.floor.cut for r in f3} == {2, 5, 10, 20, 50, 100}
    assert {r.floor.f3_base for r in f3} == {"F1", "F2"}
    assert len(stage2) == 3 + 6 * 2
    cut20 = next(r for r in f3 if r.floor.cut == 20 and r.floor.f3_base == "F2")
    # periods: 10 for 4800-sample pairs, 20 for the 9600-sample pair.
    assert cut20.floor.value_below_cut == 10.0
    assert cut20.floor.value_at_or_above_cut == 6.0
    assert cut20.segment_pairs == (2, 1)
    with pytest.raises(ValueError):
        f3_cut_candidates("family", selection=selection, constants=MINI)  # type: ignore[arg-type]
    assert f3_cut_candidates("N", selection=selection, constants=ROUND_1) == tuple(
        n for n in n_min_candidates(ROUND_1) if n > N
    )


def test_t_cx377_stage2_accepts_only_stage1_selection() -> None:
    records = _stage2_population()
    rows = fit_stage1(records, constants=MINI)
    selection = select_stage1(rows, _rid("K3c8", p=5))
    assert fit_stage2(records, selection=selection, stage1_rows=rows, constants=MINI)
    with pytest.raises(ValueError):
        select_stage1(rows, "n=480.0;p=3;K2")
    edited = selection.model_copy(
        update={"zone": selection.zone.model_copy(update={"zone_above": selection.zone.zone_above + 0.001})}
    )
    with pytest.raises(ValueError):
        fit_stage2(records, selection=edited, stage1_rows=rows, constants=MINI)
    off_table = Stage1Selection(
        row_id="n=480.0;p=3;K2", n_min=N, p_min=3, k_row="K2", zone=rows[0].zone
    )
    with pytest.raises(ValueError):
        fit_stage2(records, selection=off_table, stage1_rows=rows, constants=MINI)


def test_t_cx377_row_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    records = _stage2_population()
    rows = fit_stage1(records, constants=MINI)
    selection = select_stage1(rows, _rid("K2"))
    monkeypatch.setattr(fitting, "STAGE1_MAX_ROWS", 62)
    with pytest.raises(RowLimitExceeded):
        fit_stage1(records, constants=MINI)
    monkeypatch.setattr(fitting, "STAGE2_MAX_ROWS", 14)
    with pytest.raises(RowLimitExceeded):
        fit_stage2(records, selection=selection, stage1_rows=rows, constants=MINI)
    assert fitting.STAGE1_MAX_ROWS == 62
    assert len(n_min_candidates(ROUND_1)) * len(P_MIN_CANDIDATES) * len(K_ROW_IDS) == 756


_FORBIDDEN = ("rank", "recommend", "pass", "best", "通过", "推荐", "排名", "最佳")


def test_t_cx377_reports_list_all_rows_without_ranking_language() -> None:
    records = _stage2_population()
    rows = fit_stage1(records, constants=MINI)
    selection = select_stage1(rows, _rid("K2"))
    stage2 = fit_stage2(records, selection=selection, stage1_rows=rows, constants=MINI)
    j1 = stage1_report_json(rows, round_id="mini")
    m1 = stage1_report_markdown(rows, round_id="mini")
    j2 = stage2_report_json(stage2, round_id="mini", selection=selection)
    m2 = stage2_report_markdown(stage2, round_id="mini", selection=selection)
    assert [r["row_id"] for r in json.loads(j1)["rows"]] == [r.row_id for r in rows]
    assert [r["row_id"] for r in json.loads(j2)["rows"]] == [r.row_id for r in stage2]
    for r in rows:
        assert r.row_id in m1
    for r in stage2:
        assert r.row_id in m2
    for text in (j1, m1, j2, m2):
        lowered = text.lower()
        for word in _FORBIDDEN:
            assert word not in lowered, word
    assert stage1_report_json(rows, round_id="mini") == j1


def test_t_cx377_vectorised_zone_matches_scalar_predicate_for_every_row() -> None:
    records = [
        *_stage2_population(),
        rec(("no", THR - 0.0021, 0), ("no", THR - 0.0001, 0), code="P7c"),
        rec(("yes", THR + 0.0029, 2), ("yes", THR + 0.0031, 9), code="P7d", bits=(16, 24)),
        rec(("yes", THR + 0.004, 70), ("yes", THR + 0.002, 12), code="P4", bits=(24, 32), family="M5", level=0.995),
    ]
    tol = [r for r in records if r.is_tolerance]
    for row in fit_stage1(records, constants=MINI):
        in_dom = [r for r in tol if r.old_facts.analyzed_samples * r.f0_hz / r.sample_rate_hz >= row.p_min]
        judgeable = [r for r in in_dom if both_outside_zone(r, threshold=THR, zone=row.zone)]
        expected = len(judgeable) / len(in_dom) if in_dom else None
        assert row.judgeable_share == expected, row.row_id
