"""C.6 validation-side counting (T-CX379).

Applies the frozen (domain, K row) and F row unchanged.  Only two hard
conditions are counted; everything else is disclosure.  Judgments reuse the
predicates of ``zone.py``.  Statements are counts, never product judgments.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from signal_diag.evaluation.full_scale_characterization.checks import (
    PairSanityAbort,
    run_sanity_checks,
)
from signal_diag.evaluation.full_scale_characterization.constants import (
    ROUND_1,
    CharacterizationConstants,
)
from signal_diag.evaluation.full_scale_characterization.fitting import FlipCounts
from signal_diag.evaluation.full_scale_characterization.freeze import FreezeRecord
from signal_diag.evaluation.full_scale_characterization.gate import (
    ValidationAccess,
    ValidationLocked,
    require_validation_access,
)
from signal_diag.evaluation.full_scale_characterization.models import (
    MeasuredPair,
    PairRecord,
    SanityAbort,
)
from signal_diag.evaluation.full_scale_characterization.pairs import TOLERANCE_CODES
from signal_diag.evaluation.full_scale_characterization.store import (
    CharacterizationStore,
)
from signal_diag.evaluation.full_scale_characterization.zone import (
    FloorParams,
    ScoredPair,
    ZoneParams,
    floor_value_for,
    in_domain,
    no_side_outside_fixed_minimum,
    pair_exceeds_floor,
    scored_pair_from,
    side_in_zone,
)

P5_NEAR_REPRODUCTION_NOTE = (
    "P5 output-gain pairs can approximate held-out peak values of other groups "
    "(plan A.15 / B.3); validation-side P5 gains of 3e-4 and 1e-2 may land near "
    "held-out peaks. P5 pairs are sensitivity pairs and are disclosed only."
)
M11_NOTE = (
    "M11: the existing outputs cannot distinguish a flattened from an unflattened "
    "sine at the threshold (characterization design section 10.4)."
)
FUNDAMENTAL_SOURCE_NOTE = (
    "Fundamental source: characterization uses the generated fundamental; the product "
    "uses the user-declared fundamental and does not check it (section 10.6)."
)


class Violation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    pair_id: str
    channel: str
    family: str
    perturbation_code: str
    perturbation_detail: str
    old_state: str
    new_state: str
    old_peak_abs: float
    new_peak_abs: float
    count_diff: int
    ratio_diff: float
    floor_form: str | None = None
    floor_value: float | None = None


class HardConditionResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    applicable_pairs: int
    violation_count: int
    violations: tuple[Violation, ...]


class SensitivitySummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    pairs: int
    flips: int
    count_diff_min: int
    count_diff_median: int
    count_diff_max: int
    abs_ratio_diff_max: float


class BlindChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    pair_id: str
    family: str
    perturbation_code: str
    perturbation_detail: str
    terminal_state: str
    old_state: str | None = None
    new_state: str | None = None
    old_peak_abs: float | None = None
    new_peak_abs: float | None = None
    count_diff: int | None = None
    old_in_zone: bool | None = None
    new_in_zone: bool | None = None


class OnsetTierCounts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    total: int = 0
    detected_outside_zone: int = 0
    in_zone_no_judgment: int = 0
    not_detected: int = 0
    out_of_domain: int = 0
    not_measured: int = 0


class AggravationTierCounts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    total: int = 0
    judged: int = 0
    detected: int = 0
    masked: int = 0
    in_zone: int = 0
    not_both_yes: int = 0
    out_of_domain: int = 0
    not_measured: int = 0


class FamilyCoverage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tolerance_pairs: int
    in_domain: int
    judgeable: int
    judgeable_share: float | None


class UnseenFlip(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    pair_id: str
    family: str
    perturbation_code: str
    perturbation_detail: str


class Disclosures(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sensitivity_by_code: dict[str, SensitivitySummary]
    p5_near_reproduction_note: str
    blind_changes: tuple[BlindChange, ...]
    coverage_by_family: dict[str, FamilyCoverage]
    onset_by_tier: dict[str, OnsetTierCounts]
    aggravation_by_tier: dict[str, AggravationTierCounts]
    minimum_detectable_tier: str | None
    flips_unseen_in_calibration: tuple[UnseenFlip, ...]
    fixed_minimum_flips_by_code: dict[str, FlipCounts]
    fixed_minimum_flip_totals: FlipCounts
    m11_note: str
    fundamental_source_note: str


class ValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    round_id: str
    freeze_digest: str
    domain_n_min: float
    domain_p_min: int
    zone: ZoneParams
    floor: FloorParams
    hard_conditions_met: bool
    hard_condition_1: HardConditionResult
    hard_condition_2: HardConditionResult
    excluded_by_reason: dict[str, int]
    out_of_domain_cells: dict[str, int]
    disclosures: Disclosures


# ---------------------------------------------------------------------------


def _tier_value(tier: str) -> float:
    return float(tier.rsplit("=", 1)[-1])


def minimum_detectable_tier(tiers: Mapping[str, AggravationTierCounts]) -> str | None:
    """Smallest tier from which every tier upward has judged pairs and none masked."""
    ordered = sorted(tiers, key=_tier_value)
    smallest: str | None = None
    for tier in reversed(ordered):
        counts = tiers[tier]
        if counts.judged > 0 and counts.masked == 0:
            smallest = tier
        else:
            break
    return smallest


def _violation(pair: ScoredPair, floor: FloorParams | None = None) -> Violation:
    form, value = floor_value_for(pair, floor) if floor is not None else (None, None)
    return Violation(
        pair_id=pair.pair_id,
        channel=pair.channel,
        family=pair.family,
        perturbation_code=pair.perturbation_code,
        perturbation_detail=pair.perturbation_detail,
        old_state=pair.old_facts.state,
        new_state=pair.new_facts.state,
        old_peak_abs=pair.old_facts.peak_abs,
        new_peak_abs=pair.new_facts.peak_abs,
        count_diff=pair.count_diff,
        ratio_diff=pair.ratio_diff,
        floor_form=form,
        floor_value=value,
    )


def _bump(counter: dict[str, dict[str, int]], key: str, field: str) -> None:
    entry = counter.setdefault(key, {})
    entry[field] = entry.get(field, 0) + 1


def _cell(pair: ScoredPair) -> str:
    return (
        f"{pair.family}|{pair.kind}|f0={pair.f0_hz!r}|sr={pair.sample_rate_hz}"
        f"|range={pair.range_length_s!r}"
    )


def _is_tolerance(pair: ScoredPair) -> bool:
    return pair.is_tolerance and pair.kind == "empty"


def _sensitivity_summary(pairs: list[ScoredPair]) -> SensitivitySummary:
    diffs = sorted(p.count_diff for p in pairs)
    return SensitivitySummary(
        pairs=len(pairs),
        flips=sum(1 for p in pairs if p.flip),
        count_diff_min=diffs[0],
        count_diff_median=diffs[(len(diffs) - 1) // 2],
        count_diff_max=diffs[-1],
        abs_ratio_diff_max=max(abs(p.ratio_diff) for p in pairs),
    )


def count_validation(
    records: Sequence[ScoredPair],
    *,
    freeze: FreezeRecord,
    validation_access: object,
    calibration_records: Sequence[ScoredPair],
    constants: CharacterizationConstants = ROUND_1,
) -> ValidationResult:
    """Count C.6 hard conditions and disclosures for validation-side records."""
    require_validation_access(validation_access, what="count validation pairs")
    assert isinstance(validation_access, ValidationAccess)
    if validation_access.freeze_digest != freeze.digest:
        raise ValidationLocked("validation access was issued for a different freeze record")
    for r in records:
        if r.side != "validation":
            raise ValueError(f"validation counting received {r.side} pair {r.pair_id}")

    thr = constants.full_scale_threshold
    zone = freeze.stage1.zone_params
    floor = freeze.floor_params
    n_min = freeze.stage1.domain.n_min
    p_min = freeze.stage1.domain.p_min

    def dom(p: ScoredPair) -> bool:
        return in_domain(p, n_min=n_min, p_min=p_min)

    def old_in(p: ScoredPair) -> bool:
        return side_in_zone(p, "old", threshold=thr, zone=zone)

    def new_in(p: ScoredPair) -> bool:
        return side_in_zone(p, "new", threshold=thr, zone=zone)

    hc1: list[Violation] = []
    hc2: list[Violation] = []
    hc1_applicable = 0
    hc2_applicable = 0
    excluded: dict[str, int] = {}
    out_cells: dict[str, int] = {}
    coverage: dict[str, dict[str, int]] = {}
    flip_counts: dict[str, dict[str, int]] = {}

    def exclude(reason: str) -> None:
        excluded[reason] = excluded.get(reason, 0) + 1

    for p in records:
        if p.measured and not dom(p):
            out_cells[_cell(p)] = out_cells.get(_cell(p), 0) + 1
        if not _is_tolerance(p):
            continue
        fam = coverage.setdefault(p.family, {"tolerance_pairs": 0, "in_domain": 0, "judgeable": 0})
        fam["tolerance_pairs"] += 1
        if not p.measured:
            exclude("not_measured")
            continue
        if p.flip:
            _bump(flip_counts, p.perturbation_code, "flips")
            if no_side_outside_fixed_minimum(p, threshold=thr, k=1):
                _bump(flip_counts, p.perturbation_code, "outside_k1")
            if no_side_outside_fixed_minimum(p, threshold=thr, k=2):
                _bump(flip_counts, p.perturbation_code, "outside_k2")
        if not dom(p):
            exclude("out_of_domain")
            continue
        fam["in_domain"] += 1
        any_in = old_in(p) or new_in(p)
        if not any_in:
            fam["judgeable"] += 1
        hc1_applicable += 1
        if p.flip:
            if any_in:
                exclude("flip_in_zone")
            else:
                hc1.append(_violation(p))
            continue
        both_yes = p.old_facts.state == "yes" and p.new_facts.state == "yes"
        if not both_yes:
            exclude("not_both_yes")
            continue
        if any_in:
            exclude("in_zone")
            continue
        hc2_applicable += 1
        if pair_exceeds_floor(p, floor, absolute=True):
            hc2.append(_violation(p, floor))

    # Sensitivity (incl. combos and P8): disclosure only.
    sens_groups: dict[str, list[ScoredPair]] = {}
    for p in records:
        if p.kind == "empty" and not p.is_tolerance and p.measured:
            sens_groups.setdefault(p.perturbation_code, []).append(p)
    sensitivity = {code: _sensitivity_summary(sens_groups[code]) for code in sorted(sens_groups)}

    blind: list[BlindChange] = []
    for p in records:
        if p.kind != "blind_change":
            continue
        if p.measured:
            blind.append(
                BlindChange(
                    pair_id=p.pair_id,
                    family=p.family,
                    perturbation_code=p.perturbation_code,
                    perturbation_detail=p.perturbation_detail,
                    terminal_state=p.terminal_state,
                    old_state=p.old_facts.state,
                    new_state=p.new_facts.state,
                    old_peak_abs=p.old_facts.peak_abs,
                    new_peak_abs=p.new_facts.peak_abs,
                    count_diff=p.count_diff,
                    old_in_zone=old_in(p),
                    new_in_zone=new_in(p),
                )
            )
        else:
            blind.append(
                BlindChange(
                    pair_id=p.pair_id,
                    family=p.family,
                    perturbation_code=p.perturbation_code,
                    perturbation_detail=p.perturbation_detail,
                    terminal_state=p.terminal_state,
                )
            )

    onset: dict[str, dict[str, int]] = {}
    aggr: dict[str, dict[str, int]] = {}
    for p in records:
        if p.kind == "onset_change":
            d = p.perturbation_detail
            _bump(onset, d, "total")
            if not p.measured:
                _bump(onset, d, "not_measured")
            elif not dom(p):
                _bump(onset, d, "out_of_domain")
            elif old_in(p) or new_in(p):
                _bump(onset, d, "in_zone_no_judgment")
            elif p.old_facts.state == "no" and p.new_facts.state == "yes":
                _bump(onset, d, "detected_outside_zone")
            else:
                _bump(onset, d, "not_detected")
        elif p.kind == "aggravation_change":
            d = p.perturbation_detail
            _bump(aggr, d, "total")
            if not p.measured:
                _bump(aggr, d, "not_measured")
            elif not dom(p):
                _bump(aggr, d, "out_of_domain")
            elif old_in(p) or new_in(p):
                _bump(aggr, d, "in_zone")
            elif not (p.old_facts.state == "yes" and p.new_facts.state == "yes"):
                _bump(aggr, d, "not_both_yes")
            else:
                _bump(aggr, d, "judged")
                _bump(aggr, d, "detected" if pair_exceeds_floor(p, floor, absolute=False) else "masked")
    aggravation = {d: AggravationTierCounts(**aggr[d]) for d in sorted(aggr, key=_tier_value)}

    calibration_flip_cells = {
        (c.family, c.perturbation_code)
        for c in calibration_records
        if _is_tolerance(c) and c.measured and c.flip
    }
    unseen = tuple(
        UnseenFlip(
            pair_id=p.pair_id,
            family=p.family,
            perturbation_code=p.perturbation_code,
            perturbation_detail=p.perturbation_detail,
        )
        for p in records
        if _is_tolerance(p)
        and p.measured
        and p.flip
        and (p.family, p.perturbation_code) not in calibration_flip_cells
    )

    fixed_by_code = {code: FlipCounts(**flip_counts[code]) for code in sorted(flip_counts)}
    fixed_totals = FlipCounts(
        flips=sum(c.flips for c in fixed_by_code.values()),
        outside_k1=sum(c.outside_k1 for c in fixed_by_code.values()),
        outside_k2=sum(c.outside_k2 for c in fixed_by_code.values()),
    )

    disclosures = Disclosures(
        sensitivity_by_code=sensitivity,
        p5_near_reproduction_note=P5_NEAR_REPRODUCTION_NOTE,
        blind_changes=tuple(blind),
        coverage_by_family={
            fam: FamilyCoverage(
                **counts,
                judgeable_share=(counts["judgeable"] / counts["in_domain"]) if counts["in_domain"] else None,
            )
            for fam, counts in sorted(coverage.items())
        },
        onset_by_tier={d: OnsetTierCounts(**onset[d]) for d in sorted(onset)},
        aggravation_by_tier=aggravation,
        minimum_detectable_tier=minimum_detectable_tier(aggravation),
        flips_unseen_in_calibration=unseen,
        fixed_minimum_flips_by_code=fixed_by_code,
        fixed_minimum_flip_totals=fixed_totals,
        m11_note=M11_NOTE,
        fundamental_source_note=FUNDAMENTAL_SOURCE_NOTE,
    )
    hc1_sorted = tuple(sorted(hc1, key=lambda v: (v.pair_id, v.channel)))
    hc2_sorted = tuple(sorted(hc2, key=lambda v: (v.pair_id, v.channel)))
    return ValidationResult(
        round_id=freeze.stage1.round_id,
        freeze_digest=freeze.digest,
        domain_n_min=n_min,
        domain_p_min=p_min,
        zone=zone,
        floor=floor,
        hard_conditions_met=not hc1_sorted and not hc2_sorted,
        hard_condition_1=HardConditionResult(
            applicable_pairs=hc1_applicable, violation_count=len(hc1_sorted), violations=hc1_sorted
        ),
        hard_condition_2=HardConditionResult(
            applicable_pairs=hc2_applicable, violation_count=len(hc2_sorted), violations=hc2_sorted
        ),
        excluded_by_reason=dict(sorted(excluded.items())),
        out_of_domain_cells=dict(sorted(out_cells.items())),
        disclosures=disclosures,
    )


# ---------------------------------------------------------------------------


def abort_record_payload(error: SanityAbort, *, stage: Literal["calibration", "validation"]) -> dict[str, Any]:
    if isinstance(error, PairSanityAbort):
        return {
            "stage": stage,
            "pair_id": error.pair_id,
            "check": error.check,
            "perturbation_code": error.perturbation_code,
            "perturbation_detail": error.perturbation_detail,
            "channel": error.channel,
            "values": error.values,
            "message": str(error),
        }
    return {
        "stage": stage,
        "pair_id": None,
        "check": None,
        "perturbation_code": None,
        "perturbation_detail": None,
        "channel": None,
        "values": None,
        "message": str(error),
    }


def write_abort_record(
    store: CharacterizationStore, error: SanityAbort, *, stage: Literal["calibration", "validation"]
) -> None:
    store.write_json("abort_record.json", abort_record_payload(error, stage=stage))


def finalize_validation(
    store: CharacterizationStore,
    *,
    freeze: FreezeRecord,
    validation_access: object,
    items: Sequence[tuple[PairRecord, MeasuredPair]],
    calibration_records: Sequence[ScoredPair],
    constants: CharacterizationConstants = ROUND_1,
    m9_layouts: Mapping[str, dict[str, Any]] | None = None,
) -> ValidationResult:
    """Sanity checks, counting and report writing; a SanityAbort writes only abort_record.json."""
    # Imported here: reporting is a record-only module outside the identity comparison set.
    from signal_diag.evaluation.full_scale_characterization.reporting import (
        validation_report_json,
        validation_report_markdown,
    )

    require_validation_access(validation_access, what="finalize validation")
    try:
        run_sanity_checks(
            items,
            file_duration_s=constants.file_duration_s,
            full_scale_threshold=constants.full_scale_threshold,
            m9_layouts=m9_layouts,
            validation_access=validation_access,
        )
    except SanityAbort as error:
        write_abort_record(store, error, stage="validation")
        raise
    scored = [
        scored_pair_from(
            pair,
            measured,
            tolerance_codes=TOLERANCE_CODES,
            full_scale_threshold=constants.full_scale_threshold,
        )
        for pair, measured in items
    ]
    result = count_validation(
        scored,
        freeze=freeze,
        validation_access=validation_access,
        calibration_records=calibration_records,
        constants=constants,
    )
    round_id = result.round_id
    store.write_text(
        "validation_report.json",
        validation_report_json(result, round_id=round_id),
        validation_access=validation_access,
    )
    store.write_text(
        "validation_report.md",
        validation_report_markdown(result, round_id=round_id),
        validation_access=validation_access,
    )
    return result
