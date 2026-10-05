"""C.4 / C.5 two-stage calibration fitting (T-CX377).

Stage 1 fits every (approved domain, K row) from the fixed candidate tables.
Stage 2 fits F rows only for one stage-1 selection.  The tool never orders,
scores or prefers rows; a reviewer selects.  Only calibration-side records are
accepted.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from signal_diag.evaluation.full_scale_characterization.constants import (
    ROUND_1,
    CharacterizationConstants,
)
from signal_diag.evaluation.full_scale_characterization.zone import (
    CutVariable,
    F3Base,
    FloorParams,
    ScoredPair,
    SideFacts,
    ZoneParams,
    in_fixed_minimum,
    in_zone,
    pair_exceeds_floor,
    pair_step,
    periods_in_range,
    samples_per_period,
    two_sample_level,
)

STAGE1_MAX_ROWS = 1000
STAGE2_MAX_ROWS = 100

P_MIN_CANDIDATES: tuple[int, ...] = (1, 2, 5, 10, 20, 50, 100)
K3_C_CANDIDATES: tuple[int, ...] = (2, 4, 8, 16, 32, 64)
K_ROW_IDS: tuple[str, ...] = ("K1", "K2", "K4", *(f"K3c{c}" for c in K3_C_CANDIDATES))
F3_BASES: tuple[F3Base, ...] = ("F1", "F2")


class RowLimitExceeded(Exception):
    """A fitting stage would emit more rows than plan C.5 allows."""


class CalibrationOnlyError(ValueError):
    """Fitting received a record that is not from the calibration side."""


class FlipCounts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    flips: int = 0
    outside_k1: int = 0
    outside_k2: int = 0


class OnsetTier(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    total: int = 0
    detected: int = 0
    in_zone: int = 0
    not_detected: int = 0
    not_measured: int = 0
    out_of_domain: int = 0


class AggravationTier(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    total: int = 0
    detected: int = 0
    masked: int = 0
    in_zone: int = 0
    not_both_yes: int = 0
    not_measured: int = 0
    out_of_domain: int = 0


class Stage1Row(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    row_id: str
    n_min: float
    p_min: int
    k_row: str
    zone: ZoneParams
    k0_degenerate: bool
    in_domain_tolerance_pairs: int
    domain_share: float | None
    domain_share_by_family: dict[str, float | None]
    judgeable_share: float | None
    judgeable_share_by_family: dict[str, float | None]
    flip_counts_by_code: dict[str, FlipCounts]
    flip_totals: FlipCounts
    onset_by_tier: dict[str, OnsetTier]


class Stage1Selection(BaseModel):
    """Minimal stage-1 choice consumed by stage 2 (Task 7 wraps it in the freeze record)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    row_id: str
    n_min: float
    p_min: int
    k_row: str
    zone: ZoneParams


class Stage2Row(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    row_id: str
    floor: FloorParams
    applicable_pairs: int
    segment_pairs: tuple[int, int] | None = None
    aggravation_by_tier: dict[str, AggravationTier]
    excluded_by_reason: dict[str, int] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Candidate tables


def n_min_candidates(constants: CharacterizationConstants = ROUND_1) -> tuple[float, ...]:
    """Distinct ``sr / f0`` values of the calibration grid (C.4)."""
    return tuple(sorted({sr / f0 for sr in constants.sample_rates for f0 in constants.calibration_f0}))


def stage1_row_id(n_min: float, p_min: int, k_row: str) -> str:
    return f"n={n_min!r};p={p_min};{k_row}"


def f3_cut_candidates(
    variable: CutVariable,
    *,
    selection: Stage1Selection,
    constants: CharacterizationConstants = ROUND_1,
) -> tuple[float, ...]:
    """F3 cuts: D1 candidates strictly above the selected n_min or p_min."""
    if variable == "N":
        return tuple(n for n in n_min_candidates(constants) if n > selection.n_min)
    if variable == "periods":
        return tuple(float(p) for p in P_MIN_CANDIDATES if p > selection.p_min)
    raise ValueError(f"F3 cut variable must be 'N' or 'periods', got {variable!r}")


def _k_row_zone(k_row: str, zb: float, za: float) -> ZoneParams:
    if k_row in ("K1", "K2", "K4"):
        return ZoneParams(form=k_row, zone_below=zb, zone_above=za)  # type: ignore[arg-type]
    if k_row.startswith("K3c"):
        return ZoneParams(form="K3", zone_below=zb, zone_above=za, min_counted=int(k_row[3:]))
    raise ValueError(f"unknown K row {k_row!r}")


# ---------------------------------------------------------------------------
# Record table


def _require_calibration(records: Sequence[ScoredPair]) -> None:
    for record in records:
        if record.side != "calibration":
            raise CalibrationOnlyError(
                f"fitting accepts calibration records only; got {record.side} pair {record.pair_id}"
            )


class _Table:
    """Measured records with per-pair arrays for vectorised zone evaluation."""

    def __init__(self, records: Sequence[ScoredPair]) -> None:
        self.records = [r for r in records if r.measured]
        rs = self.records
        self.n = np.array([samples_per_period(r) for r in rs], dtype=np.float64)
        self.periods = np.array([periods_in_range(r) for r in rs], dtype=np.float64)
        self.step = np.array([pair_step(r) for r in rs], dtype=np.float64)
        self.cos = np.array([math.cos(math.pi / samples_per_period(r)) for r in rs], dtype=np.float64)
        self.old_yes = np.array([r.old_facts.state == "yes" for r in rs], dtype=bool)
        self.new_yes = np.array([r.new_facts.state == "yes" for r in rs], dtype=bool)
        self.old_peak = np.array([r.old_facts.peak_abs for r in rs], dtype=np.float64)
        self.new_peak = np.array([r.new_facts.peak_abs for r in rs], dtype=np.float64)
        self.old_counted = np.array([r.old_facts.counted_samples for r in rs], dtype=np.int64)
        self.new_counted = np.array([r.new_facts.counted_samples for r in rs], dtype=np.int64)
        self.tolerance = np.array([r.is_tolerance and r.kind == "empty" for r in rs], dtype=bool)
        self.primary = np.array([r.is_primary for r in rs], dtype=bool)
        self.kind = np.array([r.kind for r in rs], dtype=object)
        self.family = np.array([r.family for r in rs], dtype=object)
        self.code = np.array([r.perturbation_code for r in rs], dtype=object)
        self.detail = np.array([r.perturbation_detail for r in rs], dtype=object)
        self.flip = self.old_yes != self.new_yes

    def domain(self, n_min: float, p_min: float) -> np.ndarray:
        return ~(self.n < n_min) & ~(self.periods < p_min)

    def _side_zone(
        self, yes: np.ndarray, peak: np.ndarray, counted: np.ndarray, zone: ZoneParams, thr: float
    ) -> np.ndarray:
        if zone.form == "K4":
            e = peak * self.cos
            no_in = (peak >= thr - self.step) | (e >= thr - zone.zone_below)
            yes_in = e <= thr + zone.zone_above
        else:
            no_in = peak >= thr - np.maximum(zone.zone_below, self.step)
            yes_in = peak <= thr + zone.zone_above
            if zone.min_counted is not None:
                yes_in = yes_in | (counted < zone.min_counted)
        return np.where(yes, yes_in, no_in)

    def old_in_zone(self, zone: ZoneParams, thr: float) -> np.ndarray:
        return self._side_zone(self.old_yes, self.old_peak, self.old_counted, zone, thr)

    def new_in_zone(self, zone: ZoneParams, thr: float) -> np.ndarray:
        return self._side_zone(self.new_yes, self.new_peak, self.new_counted, zone, thr)

    def no_side_outside_fixed(self, thr: float, k: int) -> np.ndarray:
        no_peak = np.where(self.old_yes, self.new_peak, self.old_peak)
        return ~(no_peak >= thr - k * self.step)


# ---------------------------------------------------------------------------
# Stage 1


_Point = tuple[SideFacts, float, float]  # (facts, step, N)


def _covers(points: Sequence[_Point], zone: ZoneParams, thr: float) -> bool:
    return all(in_zone(f, threshold=thr, step=s, zone=zone, n=n) for f, s, n in points)


def _bump(zone: ZoneParams, field: str, points: Sequence[_Point], thr: float) -> ZoneParams:
    """Raise one parameter by ulps until the product predicate covers every point."""
    while not _covers(points, zone, thr):
        value = getattr(zone, field)
        zone = zone.model_copy(update={field: float(np.nextafter(value, math.inf))})
    return zone


def _max_gap(values: list[float]) -> float:
    return max([0.0, *values])


def _fit_zone(k_row: str, no_points: list[_Point], yes_points: list[_Point], thr: float) -> ZoneParams:
    if k_row == "K4":
        zb = _max_gap([thr - two_sample_level(f.peak_abs, n) for f, _, n in no_points])
        za = _max_gap([two_sample_level(f.peak_abs, n) - thr for f, _, n in yes_points])
        zone = _k_row_zone("K4", zb, za)
        zone = _bump(zone, "zone_below", no_points, thr)
        return _bump(zone, "zone_above", yes_points, thr)
    zb = _max_gap([thr - f.peak_abs for f, _, _ in no_points])
    zb = _bump(_k_row_zone("K2", zb, 0.0), "zone_below", no_points, thr).zone_below
    if k_row.startswith("K3c"):
        c = int(k_row[3:])
        remaining_yes = [p for p in yes_points if not p[0].counted_samples < c]
    else:
        remaining_yes = list(yes_points)
    za = _max_gap([f.peak_abs - thr for f, _, _ in remaining_yes])
    za = _bump(_k_row_zone("K2", 0.0, za), "zone_above", remaining_yes, thr).zone_above
    if k_row == "K1":
        v = max(zb, za)
        return _k_row_zone("K1", v, v)
    zone = _k_row_zone(k_row, zb, za)
    assert _covers(no_points, zone, thr) and _covers(yes_points, zone, thr)
    return zone


def _flip_points(table: _Table, mask: np.ndarray, thr: float) -> tuple[list[_Point], list[_Point]]:
    no_points: list[_Point] = []
    yes_points: list[_Point] = []
    for i in np.flatnonzero(mask & table.tolerance & table.flip):
        r = table.records[int(i)]
        step = float(table.step[i])
        n = float(table.n[i])
        for facts in (r.old_facts, r.new_facts):
            if facts.state == "yes":
                yes_points.append((facts, step, n))
            elif not in_fixed_minimum(facts, threshold=thr, step=step, k=1):
                no_points.append((facts, step, n))
    return no_points, yes_points


def _share(num: int, den: int) -> float | None:
    return num / den if den else None


def _by_family_share(
    table: _Table, numerator: np.ndarray, denominator: np.ndarray
) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for family in sorted(set(table.family[denominator].tolist())):
        fam = table.family == family
        out[family] = _share(int(np.count_nonzero(numerator & fam)), int(np.count_nonzero(denominator & fam)))
    return out


def _flip_counts(table: _Table, mask: np.ndarray, thr: float) -> tuple[dict[str, FlipCounts], FlipCounts]:
    flips = mask & table.tolerance & table.flip
    out_k1 = flips & table.no_side_outside_fixed(thr, 1)
    out_k2 = flips & table.no_side_outside_fixed(thr, 2)
    by_code: dict[str, FlipCounts] = {}
    for code in sorted(set(table.code[flips].tolist())):
        c = table.code == code
        by_code[code] = FlipCounts(
            flips=int(np.count_nonzero(flips & c)),
            outside_k1=int(np.count_nonzero(out_k1 & c)),
            outside_k2=int(np.count_nonzero(out_k2 & c)),
        )
    totals = FlipCounts(
        flips=int(np.count_nonzero(flips)),
        outside_k1=int(np.count_nonzero(out_k1)),
        outside_k2=int(np.count_nonzero(out_k2)),
    )
    return by_code, totals


def _onset_tiers(
    records: Sequence[ScoredPair],
    table: _Table,
    domain: np.ndarray,
    any_in_zone: np.ndarray,
) -> dict[str, OnsetTier]:
    counts: dict[str, dict[str, int]] = {}

    def bump(detail: str, key: str) -> None:
        tier = counts.setdefault(detail, {})
        tier[key] = tier.get(key, 0) + 1

    for r in records:
        if r.kind == "onset_change" and not r.measured:
            bump(r.perturbation_detail, "total")
            bump(r.perturbation_detail, "not_measured")
    onset = table.kind == "onset_change"
    for i in np.flatnonzero(onset):
        detail = str(table.detail[i])
        bump(detail, "total")
        if not domain[i]:
            bump(detail, "out_of_domain")
        elif any_in_zone[i]:
            bump(detail, "in_zone")
        elif not table.old_yes[i] and table.new_yes[i]:
            bump(detail, "detected")
        else:
            bump(detail, "not_detected")
    return {d: OnsetTier(**counts[d]) for d in sorted(counts)}


def fit_stage1(
    records: Sequence[ScoredPair],
    *,
    constants: CharacterizationConstants = ROUND_1,
) -> tuple[Stage1Row, ...]:
    """Stage 1: one row per (n_min, p_min, K row) from the fixed tables (C.5)."""
    _require_calibration(records)
    n_mins = n_min_candidates(constants)
    planned = len(n_mins) * len(P_MIN_CANDIDATES) * len(K_ROW_IDS)
    if planned > STAGE1_MAX_ROWS:
        raise RowLimitExceeded(f"stage 1 would emit {planned} rows (limit {STAGE1_MAX_ROWS})")
    thr = constants.full_scale_threshold
    table = _Table(records)
    tolerance = table.tolerance
    total_tol = int(np.count_nonzero(tolerance))
    rows: list[Stage1Row] = []
    for n_min in n_mins:
        for p_min in P_MIN_CANDIDATES:
            domain = table.domain(n_min, p_min)
            dom_tol = domain & tolerance
            no_points, yes_points = _flip_points(table, domain, thr)
            by_code, totals = _flip_counts(table, domain, thr)
            for k_row in K_ROW_IDS:
                zone = _fit_zone(k_row, no_points, yes_points, thr)
                any_in = table.old_in_zone(zone, thr) | table.new_in_zone(zone, thr)
                judgeable = dom_tol & ~any_in
                primary_judgeable = judgeable & table.primary
                rows.append(
                    Stage1Row(
                        row_id=stage1_row_id(n_min, p_min, k_row),
                        n_min=n_min,
                        p_min=p_min,
                        k_row=k_row,
                        zone=zone,
                        k0_degenerate=not bool(np.any(primary_judgeable)),
                        in_domain_tolerance_pairs=int(np.count_nonzero(dom_tol)),
                        domain_share=_share(int(np.count_nonzero(dom_tol)), total_tol),
                        domain_share_by_family=_by_family_share(table, dom_tol, tolerance),
                        judgeable_share=_share(
                            int(np.count_nonzero(judgeable)), int(np.count_nonzero(dom_tol))
                        ),
                        judgeable_share_by_family=_by_family_share(table, judgeable, dom_tol),
                        flip_counts_by_code=by_code,
                        flip_totals=totals,
                        onset_by_tier=_onset_tiers(records, table, domain, any_in),
                    )
                )
    return tuple(rows)


def select_stage1(rows: Sequence[Stage1Row], row_id: str) -> Stage1Selection:
    for row in rows:
        if row.row_id == row_id:
            return Stage1Selection(
                row_id=row.row_id, n_min=row.n_min, p_min=row.p_min, k_row=row.k_row, zone=row.zone
            )
    raise ValueError(f"stage-1 row {row_id!r} is not in the stage-1 output")


def _validate_selection(
    selection: Stage1Selection,
    stage1_rows: Sequence[Stage1Row],
    constants: CharacterizationConstants,
) -> None:
    if selection.n_min not in n_min_candidates(constants):
        raise ValueError(f"n_min {selection.n_min!r} is not a C.4 candidate")
    if selection.p_min not in P_MIN_CANDIDATES:
        raise ValueError(f"p_min {selection.p_min!r} is not a C.4 candidate")
    if selection.k_row not in K_ROW_IDS:
        raise ValueError(f"K row {selection.k_row!r} is not a C.4 candidate")
    expected = select_stage1(stage1_rows, selection.row_id)
    if expected != selection:
        raise ValueError(
            f"stage-1 selection {selection.row_id!r} differs from the fitted row; "
            "parameters can only be selected, not edited"
        )


# ---------------------------------------------------------------------------
# Stage 2


def _floor_rows(
    selection: Stage1Selection,
    applicable: list[ScoredPair],
    constants: CharacterizationConstants,
) -> list[tuple[str, FloorParams, tuple[int, int] | None]]:
    def f1(pairs: list[ScoredPair]) -> float:
        return max([0.0, *(abs(p.ratio_diff) for p in pairs)])

    def f2(pairs: list[ScoredPair]) -> float:
        return float(max([0, *(abs(p.count_diff) for p in pairs)]))

    out: list[tuple[str, FloorParams, tuple[int, int] | None]] = [
        ("F0", FloorParams(form="F0"), None),
        ("F1", FloorParams(form="F1", value=f1(applicable)), None),
        ("F2", FloorParams(form="F2", value=f2(applicable)), None),
    ]
    variables: tuple[CutVariable, ...] = ("N", "periods")
    for variable in variables:
        for cut in f3_cut_candidates(variable, selection=selection, constants=constants):
            value_of = samples_per_period if variable == "N" else periods_in_range
            below = [p for p in applicable if value_of(p) < cut]
            above = [p for p in applicable if not value_of(p) < cut]
            for base in F3_BASES:
                fit = f1 if base == "F1" else f2
                floor = FloorParams(
                    form="F3",
                    f3_base=base,
                    cut_variable=variable,
                    cut=cut,
                    value_below_cut=fit(below),
                    value_at_or_above_cut=fit(above),
                )
                out.append((f"F3[{variable}<{cut!r}|{base}]", floor, (len(below), len(above))))
    return out


def _aggravation_tiers(
    records: Sequence[ScoredPair],
    selection: Stage1Selection,
    floor: FloorParams,
    thr: float,
) -> dict[str, AggravationTier]:
    counts: dict[str, dict[str, int]] = {}

    def bump(detail: str, key: str) -> None:
        tier = counts.setdefault(detail, {})
        tier[key] = tier.get(key, 0) + 1

    for r in records:
        if r.kind != "aggravation_change":
            continue
        d = r.perturbation_detail
        bump(d, "total")
        if not r.measured:
            bump(d, "not_measured")
            continue
        if not _in_selected_domain(r, selection):
            bump(d, "out_of_domain")
        elif _any_side_in_zone(r, selection.zone, thr):
            bump(d, "in_zone")
        elif not (r.old_facts.state == "yes" and r.new_facts.state == "yes"):
            bump(d, "not_both_yes")
        elif pair_exceeds_floor(r, floor, absolute=False):
            bump(d, "detected")
        else:
            bump(d, "masked")
    return {d: AggravationTier(**counts[d]) for d in sorted(counts)}


def _in_selected_domain(r: ScoredPair, selection: Stage1Selection) -> bool:
    return not samples_per_period(r) < selection.n_min and not periods_in_range(r) < selection.p_min


def _any_side_in_zone(r: ScoredPair, zone: ZoneParams, thr: float) -> bool:
    step = pair_step(r)
    n = samples_per_period(r)
    return in_zone(r.old_facts, threshold=thr, step=step, zone=zone, n=n) or in_zone(
        r.new_facts, threshold=thr, step=step, zone=zone, n=n
    )


ExclusionReason = Literal["not_measured", "out_of_domain", "in_zone", "not_both_yes"]


def fit_stage2(
    records: Sequence[ScoredPair],
    *,
    selection: Stage1Selection,
    stage1_rows: Sequence[Stage1Row],
    constants: CharacterizationConstants = ROUND_1,
) -> tuple[Stage2Row, ...]:
    """Stage 2: F0, F1, F2 and single-cut F3 rows for the selected (domain, K row)."""
    _require_calibration(records)
    _validate_selection(selection, stage1_rows, constants)
    thr = constants.full_scale_threshold
    applicable: list[ScoredPair] = []
    excluded: dict[str, int] = {}
    for r in records:
        if not (r.is_tolerance and r.kind == "empty"):
            continue
        reason: ExclusionReason | None = None
        if not r.measured:
            reason = "not_measured"
        elif not _in_selected_domain(r, selection):
            reason = "out_of_domain"
        elif _any_side_in_zone(r, selection.zone, thr):
            reason = "in_zone"
        elif not (r.old_facts.state == "yes" and r.new_facts.state == "yes"):
            reason = "not_both_yes"
        if reason is None:
            applicable.append(r)
        else:
            excluded[reason] = excluded.get(reason, 0) + 1
    floors = _floor_rows(selection, applicable, constants)
    if len(floors) > STAGE2_MAX_ROWS:
        raise RowLimitExceeded(f"stage 2 would emit {len(floors)} rows (limit {STAGE2_MAX_ROWS})")
    return tuple(
        Stage2Row(
            row_id=row_id,
            floor=floor,
            applicable_pairs=len(applicable),
            segment_pairs=segments,
            aggravation_by_tier=_aggravation_tiers(records, selection, floor, thr),
            excluded_by_reason=dict(sorted(excluded.items())),
        )
        for row_id, floor, segments in floors
    )


# ---------------------------------------------------------------------------
# Stage reports (JSON). Freeze records select from these files, so they are built
# here, inside the identity comparison set; reporting.py renders Markdown only.

STAGE1_REPORT_NOTE = (
    "Every (domain, K row) from the fixed C.4 tables is listed in generation order. "
    "The tool does not order or select rows; a reviewer selects one for the freeze record."
)
STAGE2_REPORT_NOTE = (
    "Every F row for the selected (domain, K row) is listed in generation order. "
    "The tool does not order or select rows; a reviewer selects one for the freeze record."
)


def _report_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, allow_nan=False, ensure_ascii=False) + "\n"


def stage1_report_json(rows: Sequence[Stage1Row], *, round_id: str) -> str:
    return _report_text(
        {
            "round_id": round_id,
            "stage": 1,
            "note": STAGE1_REPORT_NOTE,
            "row_count": len(rows),
            "rows": [r.model_dump(mode="json") for r in rows],
        }
    )


def stage2_report_json(
    rows: Sequence[Stage2Row], *, round_id: str, selection: Stage1Selection
) -> str:
    return _report_text(
        {
            "round_id": round_id,
            "stage": 2,
            "note": STAGE2_REPORT_NOTE,
            "stage1_selection": selection.model_dump(mode="json"),
            "row_count": len(rows),
            "rows": [r.model_dump(mode="json") for r in rows],
        }
    )
