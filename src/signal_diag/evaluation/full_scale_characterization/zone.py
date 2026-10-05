"""C.3 / C.5 zone, domain and floor predicates (pure functions; T-CX377).

Shared by calibration fitting, validation counting and the product parity tests.
The K1–K3 and F1/F2 predicates are written to be case-for-case equivalent to the
product's ``rules.full_scale_check._in_critical_zone``, ``_quantization_step`` and
``_judgment_status``; this package does not import ``rules``, the parity is
asserted in ``tests/`` only.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from signal_diag.evaluation.full_scale_characterization.models import (
    MeasuredPair,
    MeasurementRow,
    PairKind,
    PairRecord,
    PairTerminalState,
    Side,
)

ZoneForm = Literal["K1", "K2", "K3", "K4"]
FloorForm = Literal["F0", "F1", "F2", "F3"]
F3Base = Literal["F1", "F2"]
CutVariable = Literal["N", "periods"]

PRIMARY_FAMILIES_ANY_LEVEL = frozenset({"M2", "M11", "M3"})
PRIMARY_FAMILIES_LEVEL_GATED = frozenset({"M5"})


class SideFacts(BaseModel):
    """Per-side facts needed for zone and floor predicates (from a measurement row)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    state: Literal["yes", "no"]
    peak_abs: float
    counted_samples: int = Field(ge=0)
    analyzed_samples: int = Field(gt=0)
    pcm_bit_depth: Literal[8, 16, 24, 32]


class ScoredPair(BaseModel):
    """Pair-level record consumed by fitting and validation (C.1 pair-table fields)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pair_id: str
    channel: str
    side: Side
    kind: PairKind
    family: str
    perturbation_code: str
    perturbation_detail: str
    is_tolerance: bool
    is_primary: bool
    f0_hz: float
    sample_rate_hz: int
    range_length_s: float
    terminal_state: PairTerminalState
    old: SideFacts | None = None
    new: SideFacts | None = None

    @property
    def measured(self) -> bool:
        return self.terminal_state == "measured" and self.old is not None and self.new is not None

    @property
    def flip(self) -> bool:
        return self.measured and self.old_facts.state != self.new_facts.state

    @property
    def old_facts(self) -> SideFacts:
        assert self.old is not None
        return self.old

    @property
    def new_facts(self) -> SideFacts:
        assert self.new is not None
        return self.new

    @property
    def count_diff(self) -> int:
        return self.new_facts.counted_samples - self.old_facts.counted_samples

    @property
    def ratio_diff(self) -> float:
        return self.count_diff / self.old_facts.analyzed_samples


class ZoneParams(BaseModel):
    """Critical-zone parameters; ``min_counted`` is the K3 gate ``c``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    form: ZoneForm
    zone_below: float = Field(ge=0)
    zone_above: float = Field(ge=0)
    min_counted: int | None = Field(default=None, ge=0)


class FloorParams(BaseModel):
    """Sample-count floor; F3 is a single cut on N or periods with two same-form segments."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    form: FloorForm
    value: float | None = None
    f3_base: F3Base | None = None
    cut_variable: CutVariable | None = None
    cut: float | None = None
    value_below_cut: float | None = None
    value_at_or_above_cut: float | None = None


def _side_facts(row: MeasurementRow) -> SideFacts | None:
    if (
        row.terminal_state != "measured"
        or row.state is None
        or row.peak_abs is None
        or row.counted_samples is None
        or row.analyzed_samples is None
        or row.pcm_bit_depth is None
    ):
        return None
    return SideFacts(
        state=row.state,
        peak_abs=row.peak_abs,
        counted_samples=row.counted_samples,
        analyzed_samples=row.analyzed_samples,
        pcm_bit_depth=row.pcm_bit_depth,
    )


def is_primary_condition(family: str, level: float | None, threshold: float) -> bool:
    """Main conditions (B.2): M2/M11, M3; M5 only when its level is at or above threshold."""
    if family in PRIMARY_FAMILIES_ANY_LEVEL:
        return True
    if family in PRIMARY_FAMILIES_LEVEL_GATED:
        return level is not None and level >= threshold
    return False


def scored_pair_from(
    pair: PairRecord,
    measured: MeasuredPair,
    *,
    tolerance_codes: frozenset[str],
    full_scale_threshold: float,
) -> ScoredPair:
    if pair.pair_id != measured.pair_id:
        raise ValueError(f"pair record {pair.pair_id} does not match {measured.pair_id}")
    return ScoredPair(
        pair_id=pair.pair_id,
        channel=measured.channel,
        side=pair.side,
        kind=pair.kind,
        family=pair.family,
        perturbation_code=pair.perturbation_code,
        perturbation_detail=pair.perturbation_detail,
        is_tolerance=pair.perturbation_code in tolerance_codes,
        is_primary=is_primary_condition(
            pair.family, pair.old_side.effective.level, full_scale_threshold
        ),
        f0_hz=pair.f0_hz,
        sample_rate_hz=pair.sample_rate_hz,
        range_length_s=pair.range_length_s,
        terminal_state=measured.terminal_state,
        old=_side_facts(measured.old_row),
        new=_side_facts(measured.new_row),
    )


# ---------------------------------------------------------------------------
# Product-equivalent arithmetic


def quantization_step(*bit_depths: int) -> float:
    """Product ``_quantization_step``: max(2^-(b-1), 2^-24), b = coarsest depth."""
    if not bit_depths:
        return 2.0 ** -24
    min_bits = min(bit_depths)
    return max(2.0 ** -(min_bits - 1), 2.0 ** -24)


def pair_step(pair: ScoredPair) -> float:
    return quantization_step(pair.old_facts.pcm_bit_depth, pair.new_facts.pcm_bit_depth)


def samples_per_period(pair: ScoredPair) -> float:
    """N, verbatim with the product: ``sr / f0``."""
    sr = pair.sample_rate_hz
    f0 = pair.f0_hz
    return sr / f0


def periods_in_range(pair: ScoredPair) -> float:
    """Periods in range, verbatim with the product (baseline = old side analyzed samples)."""
    sr = pair.sample_rate_hz
    f0 = pair.f0_hz
    analyzed_for_periods = pair.old_facts.analyzed_samples
    return analyzed_for_periods * f0 / sr


def in_domain(pair: ScoredPair, *, n_min: float, p_min: float) -> bool:
    """D1 membership, as the complement of the product's below-domain tests."""
    if samples_per_period(pair) < n_min:
        return False
    return not periods_in_range(pair) < p_min


def two_sample_level(peak_abs: float, n: float) -> float:
    """K4 two-sample equivalent level ``e = peak_abs * cos(pi / N)``."""
    return peak_abs * math.cos(math.pi / n)


def in_fixed_minimum(facts: SideFacts, *, threshold: float, step: float, k: int = 1) -> bool:
    """C.3 fixed minimum: a "no" side with ``peak_abs >= thr - k * step``."""
    if facts.state != "no":
        return False
    return facts.peak_abs >= threshold - k * step


def in_zone(
    facts: SideFacts,
    *,
    threshold: float,
    step: float,
    zone: ZoneParams | None,
    n: float | None = None,
) -> bool:
    """State-based critical-zone membership (K1–K3 match product ``_in_critical_zone``)."""
    if zone is not None and zone.form == "K4":
        if n is None:
            raise ValueError("K4 requires N")
        e = two_sample_level(facts.peak_abs, n)
        if facts.state == "no":
            return in_fixed_minimum(facts, threshold=threshold, step=step, k=1) or (
                e >= threshold - zone.zone_below
            )
        return e <= threshold + zone.zone_above
    if facts.state == "no":
        margin = step
        if zone is not None:
            margin = max(zone.zone_below, step)
        return facts.peak_abs >= threshold - margin
    if zone is None:
        return False
    above = facts.peak_abs <= threshold + zone.zone_above
    below_min = zone.min_counted is not None and facts.counted_samples < zone.min_counted
    return above or below_min


def side_in_zone(
    pair: ScoredPair, which: Literal["old", "new"], *, threshold: float, zone: ZoneParams | None
) -> bool:
    facts = pair.old_facts if which == "old" else pair.new_facts
    return in_zone(
        facts,
        threshold=threshold,
        step=pair_step(pair),
        zone=zone,
        n=samples_per_period(pair),
    )


def both_outside_zone(pair: ScoredPair, *, threshold: float, zone: ZoneParams | None) -> bool:
    return not side_in_zone(pair, "old", threshold=threshold, zone=zone) and not side_in_zone(
        pair, "new", threshold=threshold, zone=zone
    )


def no_side_outside_fixed_minimum(pair: ScoredPair, *, threshold: float, k: int) -> bool:
    """For a flip: the "no" side lies below ``thr - k * step``."""
    no_side = pair.old_facts if pair.old_facts.state == "no" else pair.new_facts
    return not in_fixed_minimum(no_side, threshold=threshold, step=pair_step(pair), k=k)


# ---------------------------------------------------------------------------
# Floors


def floor_value_for(pair: ScoredPair, floor: FloorParams) -> tuple[F3Base | None, float | None]:
    """Resolve (form, value) for this pair; F3 picks the segment by its cut variable."""
    if floor.form == "F0":
        return None, None
    if floor.form in ("F1", "F2"):
        return floor.form, floor.value
    if floor.cut_variable not in ("N", "periods") or floor.cut is None:
        raise ValueError("F3 needs a single cut on N or periods")
    variable = (
        samples_per_period(pair) if floor.cut_variable == "N" else periods_in_range(pair)
    )
    value = floor.value_below_cut if variable < floor.cut else floor.value_at_or_above_cut
    return floor.f3_base, value


def exceeds_floor(
    count_diff: int,
    old_analyzed_samples: int,
    *,
    form: F3Base | None,
    value: float | None,
    absolute: bool,
) -> bool:
    """Strictly-greater floor test; product-signed unless ``absolute`` (hard condition two)."""
    if form is None:
        diff_f0 = abs(count_diff) if absolute else count_diff
        return diff_f0 > 0
    assert value is not None
    diff = abs(count_diff) if absolute else count_diff
    if form == "F2":
        return diff > value
    return diff / old_analyzed_samples > value


def pair_exceeds_floor(pair: ScoredPair, floor: FloorParams, *, absolute: bool) -> bool:
    form, value = floor_value_for(pair, floor)
    return exceeds_floor(
        pair.count_diff,
        pair.old_facts.analyzed_samples,
        form=form,
        value=value,
        absolute=absolute,
    )
