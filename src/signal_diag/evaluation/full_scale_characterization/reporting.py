"""Calibration stage reports (JSON + Markdown); rows are listed in grid order, unordered by merit."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from signal_diag.evaluation.full_scale_characterization.fitting import (
    Stage1Row,
    Stage1Selection,
    Stage2Row,
)
from signal_diag.evaluation.full_scale_characterization.validation import (
    ValidationResult,
    Violation,
)

_STAGE1_NOTE = (
    "Every (domain, K row) from the fixed C.4 tables is listed in generation order. "
    "The tool does not order or select rows; a reviewer selects one for the freeze record."
)
_STAGE2_NOTE = (
    "Every F row for the selected (domain, K row) is listed in generation order. "
    "The tool does not order or select rows; a reviewer selects one for the freeze record."
)


def _dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, allow_nan=False, ensure_ascii=False) + "\n"


def stage1_report_json(rows: Sequence[Stage1Row], *, round_id: str) -> str:
    return _dumps(
        {
            "round_id": round_id,
            "stage": 1,
            "note": _STAGE1_NOTE,
            "row_count": len(rows),
            "rows": [r.model_dump(mode="json") for r in rows],
        }
    )


def stage2_report_json(
    rows: Sequence[Stage2Row], *, round_id: str, selection: Stage1Selection
) -> str:
    return _dumps(
        {
            "round_id": round_id,
            "stage": 2,
            "note": _STAGE2_NOTE,
            "stage1_selection": selection.model_dump(mode="json"),
            "row_count": len(rows),
            "rows": [r.model_dump(mode="json") for r in rows],
        }
    )


def _fmt(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return repr(value)
    return str(value)


def _family_cell(values: dict[str, float | None]) -> str:
    return "; ".join(f"{k}={_fmt(v)}" for k, v in values.items()) or "-"


def stage1_report_markdown(rows: Sequence[Stage1Row], *, round_id: str) -> str:
    lines = [
        f"# Calibration stage 1 — {round_id}",
        "",
        _STAGE1_NOTE,
        "",
        (
            "| row_id | zone_below | zone_above | min_counted | K0 | in-domain tolerance pairs "
            "| domain share | judgeable share | judgeable share by family | flips | outside k=1 "
            "| outside k=2 | onset tiers (detected/in_zone/not_detected/total) |"
        ),
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        onset = "; ".join(
            f"{tier}: {t.detected}/{t.in_zone}/{t.not_detected}/{t.total}"
            for tier, t in r.onset_by_tier.items()
        ) or "-"
        lines.append(
            f"| {r.row_id} | {_fmt(r.zone.zone_below)} | {_fmt(r.zone.zone_above)} "
            f"| {_fmt(r.zone.min_counted)} | {'K0' if r.k0_degenerate else '-'} "
            f"| {r.in_domain_tolerance_pairs} | {_fmt(r.domain_share)} | {_fmt(r.judgeable_share)} "
            f"| {_family_cell(r.judgeable_share_by_family)} | {r.flip_totals.flips} "
            f"| {r.flip_totals.outside_k1} | {r.flip_totals.outside_k2} | {onset} |"
        )
    return "\n".join(lines) + "\n"


def stage2_report_markdown(
    rows: Sequence[Stage2Row], *, round_id: str, selection: Stage1Selection
) -> str:
    lines = [
        f"# Calibration stage 2 — {round_id}",
        "",
        _STAGE2_NOTE,
        "",
        f"Stage-1 selection: `{selection.row_id}`",
        "",
        (
            "| row_id | form | value | cut | below cut | at/above cut | applicable pairs "
            "| segment pairs | aggravation masked by tier | excluded |"
        ),
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        f = r.floor
        masked = "; ".join(f"{tier}: {t.masked}/{t.total}" for tier, t in r.aggravation_by_tier.items()) or "-"
        excluded = "; ".join(f"{k}={v}" for k, v in r.excluded_by_reason.items()) or "-"
        cut = f"{f.cut_variable}<{_fmt(f.cut)}" if f.cut_variable is not None else "-"
        segments = f"{r.segment_pairs[0]}/{r.segment_pairs[1]}" if r.segment_pairs else "-"
        lines.append(
            f"| {r.row_id} | {f.form}{'/' + f.f3_base if f.f3_base else ''} | {_fmt(f.value)} | {cut} "
            f"| {_fmt(f.value_below_cut)} | {_fmt(f.value_at_or_above_cut)} | {r.applicable_pairs} "
            f"| {segments} | {masked} | {excluded} |"
        )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Validation report (C.6): counts only; disclosures are kept in their own section.


def validation_report_json(result: ValidationResult, *, round_id: str) -> str:
    payload = result.model_dump(mode="json")
    payload["report_round_id"] = round_id
    payload["statement"] = _validation_statement(result)
    return _dumps(payload)


def _validation_statement(result: ValidationResult) -> str:
    met = "all met" if result.hard_conditions_met else "not all met"
    return (
        f"Hard condition 1: {result.hard_condition_1.violation_count} violating pairs of "
        f"{result.hard_condition_1.applicable_pairs} applicable. Hard condition 2: "
        f"{result.hard_condition_2.violation_count} violating pairs of "
        f"{result.hard_condition_2.applicable_pairs} applicable. Hard conditions {met}."
    )


def _violation_table(violations: Sequence[Violation]) -> list[str]:
    if not violations:
        return ["No violating pairs.", ""]
    lines = [
        (
            "| pair_id | channel | family | code | detail | old state/peak | new state/peak "
            "| count_diff | ratio_diff | floor |"
        ),
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for v in violations:
        lines.append(
            f"| {v.pair_id} | {v.channel} | {v.family} | {v.perturbation_code} "
            f"| {v.perturbation_detail} | {v.old_state}/{v.old_peak_abs!r} "
            f"| {v.new_state}/{v.new_peak_abs!r} | {v.count_diff} | {v.ratio_diff!r} "
            f"| {_fmt(v.floor_form)} {_fmt(v.floor_value)} |"
        )
    return [*lines, ""]


def validation_report_markdown(result: ValidationResult, *, round_id: str) -> str:
    d = result.disclosures
    z = result.zone
    f = result.floor
    lines = [
        f"# Validation report — {round_id}",
        "",
        f"Freeze record digest: `{result.freeze_digest}`",
        "",
        f"Frozen domain: N >= {result.domain_n_min!r}, periods >= {result.domain_p_min}; "
        f"zone {z.form} (below {z.zone_below!r}, above {z.zone_above!r}, "
        f"min_counted {_fmt(z.min_counted)}); floor {f.form}"
        + (f"/{f.f3_base}" if f.f3_base else "")
        + f" value {_fmt(f.value)}"
        + (
            f", cut {f.cut_variable} < {_fmt(f.cut)}: {_fmt(f.value_below_cut)} / "
            f"{_fmt(f.value_at_or_above_cut)}"
            if f.cut_variable
            else ""
        ),
        "",
        "## Hard conditions",
        "",
        _validation_statement(result),
        "",
        "### Hard condition 1 — flips with both sides outside the zone (in-domain tolerance pairs)",
        "",
        *_violation_table(result.hard_condition_1.violations),
        "### Hard condition 2 — |difference| strictly above the floor (both sides yes, outside the zone)",
        "",
        *_violation_table(result.hard_condition_2.violations),
        "### Excluded tolerance pairs by reason",
        "",
        *([f"- {k}: {v}" for k, v in result.excluded_by_reason.items()] or ["- none"]),
        "",
        "## Disclosures",
        "",
        "### Out-of-domain cells",
        "",
        *([f"- {k}: {v}" for k, v in result.out_of_domain_cells.items()] or ["- none"]),
        "",
        "### Sensitivity pairs (including combined perturbations and P8)",
        "",
        "| code | pairs | flips | count_diff min | median | max | max abs ratio_diff |",
        "|---|---|---|---|---|---|---|",
        *[
            f"| {code} | {s.pairs} | {s.flips} | {s.count_diff_min} | {s.count_diff_median} "
            f"| {s.count_diff_max} | {s.abs_ratio_diff_max!r} |"
            for code, s in d.sensitivity_by_code.items()
        ],
        "",
        "### P5 near-reproduction",
        "",
        d.p5_near_reproduction_note,
        "",
        "### Blind-spot change pairs",
        "",
        *(
            [
                f"- {b.pair_id} {b.family} {b.perturbation_code} {b.perturbation_detail}: "
                f"{_fmt(b.old_state)} -> {_fmt(b.new_state)}, count_diff {_fmt(b.count_diff)}, "
                f"in zone old/new {_fmt(b.old_in_zone)}/{_fmt(b.new_in_zone)} ({b.terminal_state})"
                for b in d.blind_changes
            ]
            or ["- none"]
        ),
        "",
        "### Coverage by family",
        "",
        *[
            f"- {fam}: tolerance {c.tolerance_pairs}, in domain {c.in_domain}, "
            f"judgeable {c.judgeable}, share {_fmt(c.judgeable_share)}"
            for fam, c in d.coverage_by_family.items()
        ],
        "",
        "### Onset change pairs",
        "",
        *(
            [
                f"- {tier}: total {t.total}, onset outside zone {t.detected_outside_zone}, "
                f"in zone without judgment {t.in_zone_no_judgment}, no onset {t.not_detected}, "
                f"out of domain {t.out_of_domain}, not measured {t.not_measured}"
                for tier, t in d.onset_by_tier.items()
            ]
            or ["- none"]
        ),
        "",
        "### Aggravation change pairs",
        "",
        *(
            [
                f"- {tier}: total {t.total}, judged {t.judged}, above floor {t.detected}, "
                f"covered by floor {t.masked}, in zone {t.in_zone}, not both yes {t.not_both_yes}, "
                f"out of domain {t.out_of_domain}, not measured {t.not_measured}"
                for tier, t in d.aggravation_by_tier.items()
            ]
            or ["- none"]
        ),
        "",
        "### Minimum detectable change",
        "",
        f"Smallest tier from which every tier upward is above the floor: {_fmt(d.minimum_detectable_tier)}",
        "",
        "### Flips not seen in calibration",
        "",
        *(
            [
                f"- {u.pair_id} {u.family} {u.perturbation_code} {u.perturbation_detail}"
                for u in d.flips_unseen_in_calibration
            ]
            or ["- none"]
        ),
        "",
        "### Fixed minimum k=1 / k=2 (C.3)",
        "",
        *[
            f"- {code}: flips {c.flips}, outside k=1 {c.outside_k1}, outside k=2 {c.outside_k2}"
            for code, c in d.fixed_minimum_flips_by_code.items()
        ],
        (
            f"- total: flips {d.fixed_minimum_flip_totals.flips}, outside k=1 "
            f"{d.fixed_minimum_flip_totals.outside_k1}, outside k=2 "
            f"{d.fixed_minimum_flip_totals.outside_k2}"
        ),
        "",
        "### M11",
        "",
        d.m11_note,
        "",
        "### Fundamental source",
        "",
        d.fundamental_source_note,
        "",
    ]
    return "\n".join(lines)
