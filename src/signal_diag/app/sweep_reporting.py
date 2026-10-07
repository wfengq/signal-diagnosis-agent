"""Sweep test reports: JSON, standalone HTML and the band THD chart (D054, §29)."""

from __future__ import annotations

import html
import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from signal_diag.app.sweep import SweepDiagnosis, SweepLevelResult

SWEEP_REPORT_VERSION = "sweep-report-1.0"
THRESHOLD_NOTICE = (
    "Thresholds are profile_s1_sweep 1.0.0-demo demonstration settings "
    "(1% full scale, 5% band THD), not industry standards or SLAs."
)
SERIES_COLORS = ("#2a78d6", "#eb6834", "#1baf7a")

_W, _H = 640, 280
_GRID, _AXIS, _INK2 = "#e1e0d9", "#c3c2b7", "#52514e"
_TICK = f'fill="{_INK2}" font-size="11" font-family="system-ui, sans-serif"'
_LEFT, _RIGHT, _TOP, _BOTTOM = 48, 16, 16, 40


class SweepReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    report_version: str = SWEEP_REPORT_VERSION
    generated_at: datetime
    threshold_notice: str = THRESHOLD_NOTICE
    diagnosis: SweepDiagnosis


def validate_sweep_report_integrity(diagnosis: SweepDiagnosis) -> None:
    """Every claim cites rule evaluations and facts of its own level."""
    for level in diagnosis.levels:
        facts = {fact.fact_id for fact in level.measurement.facts}
        evaluations = {item.evaluation_id for item in level.rule_evaluations}
        for item in level.rule_evaluations:
            if not set(item.fact_refs) <= facts:
                raise ValueError("rule evaluation cites a fact of another run")
        for claim in level.claims:
            if not claim.rule_refs or not set(claim.rule_refs) <= evaluations:
                raise ValueError("claim cites a rule evaluation of another run")
            if not set(claim.fact_refs) <= facts:
                raise ValueError("claim cites a fact of another run")


def build_sweep_report(
    diagnosis: SweepDiagnosis, *, generated_at: datetime
) -> SweepReport:
    validate_sweep_report_integrity(diagnosis)
    return SweepReport(generated_at=generated_at, diagnosis=diagnosis)


def render_sweep_json(
    report: SweepReport, *, explanation: Mapping[str, object] | None = None
) -> str:
    payload = report.model_dump(mode="json")
    if explanation is not None:
        payload["explanation"] = dict(explanation)
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def sweep_payload(diagnosis: SweepDiagnosis) -> dict[str, Any]:
    """API payload: the diagnosis plus the rendered chart and notice."""
    payload = diagnosis.model_dump(mode="json")
    payload["threshold_notice"] = THRESHOLD_NOTICE
    payload["chart_svg"] = render_band_chart_svg(diagnosis)
    return payload


def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _band_label(center: float) -> str:
    return f"{center / 1000:g}k" if center >= 1000 else f"{center:g}"


_NICE_SCALES = ((6.0, 2.0), (10.0, 2.0), (20.0, 5.0), (50.0, 10.0), (100.0, 20.0))


def _nice_scale(value: float) -> tuple[float, float]:
    """Axis top and tick step, both clean numbers."""
    for top, step in _NICE_SCALES:
        if value <= top:
            return top, step
    top = float(int(value / 100.0 + 1) * 100)
    return top, top / 5


def _threshold(diagnosis: SweepDiagnosis) -> float:
    for level in diagnosis.levels:
        for item in level.rule_evaluations:
            if item.role == "harmonic" and isinstance(item.threshold, (int, float)):
                return float(item.threshold)
    return 5.0


def render_band_chart_svg(diagnosis: SweepDiagnosis) -> str:
    """Octave-band THD per level, with the demo limit as a reference line."""
    centers = [band.center_hz for band in diagnosis.levels[0].measurement.bands]
    limit = _threshold(diagnosis)
    values = [
        band.thd_percent
        for level in diagnosis.levels
        for band in level.measurement.bands
        if band.measurable and band.thd_percent is not None
    ]
    top, tick = _nice_scale(max([limit * 1.2, *values]))
    plot_w = _W - _LEFT - _RIGHT
    plot_h = _H - _TOP - _BOTTOM
    step = plot_w / max(len(centers) - 1, 1)

    def x(index: int) -> float:
        return _LEFT + index * step

    def y(value: float) -> float:
        return _TOP + plot_h * (1 - min(value, top) / top)

    parts = [
        (
            f'<svg class="sweep-chart" viewBox="0 0 {_W} {_H}" role="img" '
            'aria-labelledby="sweep-chart-title" xmlns="http://www.w3.org/2000/svg">'
        ),
        (
            '<title id="sweep-chart-title">Octave-band THD (%) per level; '
            "the dashed line is the demonstration limit</title>"
        ),
    ]
    for index in range(round(top / tick) + 1):
        value = index * tick
        parts.append(
            f'<line stroke="{_GRID}" stroke-width="1" x1="{_LEFT}" x2="{_W - _RIGHT}" '
            f'y1="{y(value):.1f}" y2="{y(value):.1f}"/>'
        )
        parts.append(
            f'<text {_TICK} x="{_LEFT - 6}" y="{y(value) + 4:.1f}" '
            f'text-anchor="end">{value:g}%</text>'
        )
    parts.append(
        f'<line stroke="{_AXIS}" stroke-width="1" x1="{_LEFT}" x2="{_W - _RIGHT}" '
        f'y1="{_TOP + plot_h}" y2="{_TOP + plot_h}"/>'
    )
    for index, center in enumerate(centers):
        parts.append(
            f'<text {_TICK} x="{x(index):.1f}" y="{_TOP + plot_h + 16}" '
            f'text-anchor="middle">{_esc(_band_label(center))}</text>'
        )
    parts.append(
        f'<text {_TICK} x="{_LEFT + plot_w / 2:.1f}" y="{_H - 4}" '
        'text-anchor="middle">Octave band centre (Hz)</text>'
    )
    parts.append(
        f'<line stroke="{_INK2}" stroke-width="1" stroke-dasharray="4 3" x1="{_LEFT}" x2="{_W - _RIGHT}" '
        f'y1="{y(limit):.1f}" y2="{y(limit):.1f}"/>'
    )
    parts.append(
        f'<text {_TICK} x="{_W - _RIGHT}" y="{y(limit) - 5:.1f}" '
        f'text-anchor="end">{limit:g}% demo limit</text>'
    )
    for series, level in enumerate(diagnosis.levels):
        parts.extend(_series_marks(level, SERIES_COLORS[series], x, y))
    parts.append("</svg>")
    return "".join(parts)


def _series_marks(level: SweepLevelResult, color: str, x: Any, y: Any) -> list[str]:
    runs: list[list[tuple[int, float]]] = [[]]
    for index, band in enumerate(level.measurement.bands):
        if band.measurable and band.thd_percent is not None:
            runs[-1].append((index, band.thd_percent))
        elif runs[-1]:
            runs.append([])
    marks: list[str] = []
    for run in runs:
        if len(run) > 1:
            points = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in run)
            marks.append(
                f'<polyline fill="none" stroke-width="2" stroke-linejoin="round" '
                f'stroke-linecap="round" stroke="{color}" points="{points}"/>'
            )
    label = _esc(level.level_label)
    for run in runs:
        for index, value in run:
            band = level.measurement.bands[index]
            tip = f"{value:.2f}% · {label} · {_band_label(band.center_hz)} Hz"
            if band.dominant_order is not None:
                tip += f" · order {band.dominant_order}"
            marks.append(
                f'<circle class="sc-hit" fill="transparent" cx="{x(index):.1f}" cy="{y(value):.1f}" r="12" '
                f'tabindex="0"><title>{tip}</title></circle>'
                f'<circle class="sc-dot" stroke="#ffffff" stroke-width="2" cx="{x(index):.1f}" cy="{y(value):.1f}" r="4" '
                f'fill="{color}" pointer-events="none"/>'
            )
    return marks


def _legend(diagnosis: SweepDiagnosis) -> str:
    items = "".join(
        '<li><svg width="18" height="8" aria-hidden="true">'
        f'<line x1="1" x2="17" y1="4" y2="4" stroke="{SERIES_COLORS[i]}" '
        'stroke-width="2" stroke-linecap="round"/></svg> '
        f"{_esc(level.level_label)}</li>"
        for i, level in enumerate(diagnosis.levels)
    )
    return f'<ul class="sweep-legend">{items}</ul>'


def _band_table(diagnosis: SweepDiagnosis) -> str:
    head = "".join(f"<th>{_esc(level.level_label)}</th>" for level in diagnosis.levels)
    rows: list[str] = []
    centers = [band.center_hz for band in diagnosis.levels[0].measurement.bands]
    for index, center in enumerate(centers):
        cells: list[str] = []
        for level in diagnosis.levels:
            band = level.measurement.bands[index]
            if band.measurable and band.thd_percent is not None:
                order = f" (order {band.dominant_order})" if band.dominant_order else ""
                cells.append(f"<td>{band.thd_percent:.2f}%{order}</td>")
            else:
                cells.append('<td class="muted">not measurable</td>')
        rows.append(f"<tr><th>{_esc(_band_label(center))} Hz</th>{''.join(cells)}</tr>")
    return (
        '<table class="sweep-table"><thead><tr><th>Band</th>'
        f"{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )


def _level_section(level: SweepLevelResult) -> str:
    measurement = level.measurement
    claims = "".join(
        f"<li><strong>{_esc(claim.fault_type)}</strong>: {_esc(claim.statement)}"
        f'<br><span class="muted">rules: {_esc(", ".join(claim.rule_refs))}</span></li>'
        for claim in level.claims
    )
    rules = "".join(
        "<tr>"
        f"<td>{_esc(item.rule_id)}</td>"
        f"<td>{_esc(item.band_hz if item.band_hz is not None else '')}</td>"
        f"<td>{_esc(item.observed_value)}</td>"
        f"<td>{_esc(item.comparator)} {_esc(item.threshold)}</td>"
        f"<td>{_esc(item.judgment)}</td>"
        f"<td>{_esc(item.evaluation_id)}</td>"
        "</tr>"
        for item in level.rule_evaluations
        if item.band_hz is None or item.judgment != "not_applicable"
    )
    return (
        f"<section><h2>Level {_esc(level.level_label)}: {_esc(level.outcome)}</h2>"
        f"<ul>{claims}</ul>"
        f'<p class="muted">recording sha256 {_esc(measurement.recording_sha256)}; '
        f"stimulus {_esc(measurement.stimulus_version)} "
        f"({_esc(measurement.stimulus_digest)})</p>"
        "<table><thead><tr><th>rule</th><th>band Hz</th><th>observed</th>"
        "<th>limit</th><th>judgment</th><th>evaluation</th></tr></thead>"
        f"<tbody>{rules}</tbody></table></section>"
    )


def render_sweep_html(report: SweepReport, *, explanation_html: str | None = None) -> str:
    diagnosis = report.diagnosis
    return "".join(
        [
            "<!DOCTYPE html>",
            '<html lang="en"><head><meta charset="utf-8">',
            f"<title>Sweep test {_esc(diagnosis.run_id)}</title>",
            "<style>",
            "body{font-family:system-ui,sans-serif;margin:1.5rem;color:#0b0b0b;background:#fff}",
            "section{margin-bottom:1.25rem}h1,h2{margin:0 0 .75rem}",
            "table{border-collapse:collapse;width:100%}",
            (
                "th,td{border:1px solid #e1e0d9;padding:.3rem;text-align:left;"
                "font-variant-numeric:tabular-nums}"
            ),
            ".muted{color:#52514e}.notice{font-style:italic;color:#52514e}",
            ".sweep-chart{max-width:640px;width:100%;height:auto}",
            ".sweep-legend{list-style:none;padding:0;display:flex;gap:1rem}",
            ".sc-hit:hover+.sc-dot,.sc-hit:focus+.sc-dot{stroke:#0b0b0b}",
            "</style></head><body>",
            f"<h1>Sweep test {_esc(diagnosis.run_id)}</h1>",
            f"<p><strong>{_esc(diagnosis.outcome)}</strong>: {_esc(diagnosis.summary)}</p>",
            f'<p class="notice">{_esc(report.threshold_notice)}</p>',
            (
                f'<p class="muted">engine {_esc(diagnosis.engine_version)}; profile '
                f"{_esc(diagnosis.profile_id)} {_esc(diagnosis.profile_version)}; "
                f"{diagnosis.sample_rate_hz} Hz; model calls {diagnosis.model_calls}; "
                f"generated {_esc(report.generated_at.isoformat())}</p>"
            ),
            "<section><h2>Band THD</h2>",
            _legend(diagnosis),
            render_band_chart_svg(diagnosis),
            _band_table(diagnosis),
            "</section>",
            *(_level_section(level) for level in diagnosis.levels),
            explanation_html or "",
            "</body></html>",
        ]
    )


__all__ = [
    "SERIES_COLORS",
    "SWEEP_REPORT_VERSION",
    "THRESHOLD_NOTICE",
    "SweepReport",
    "build_sweep_report",
    "render_band_chart_svg",
    "render_sweep_html",
    "render_sweep_json",
    "sweep_payload",
    "validate_sweep_report_integrity",
]
