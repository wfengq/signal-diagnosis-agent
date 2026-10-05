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
