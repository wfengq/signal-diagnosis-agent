"""Regression workbench case report projection and rendering."""

from __future__ import annotations

import html
import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from signal_diag.app.regression import (
    CaseComparisonItem,
    CaseFailureRecord,
    CaseRecommendationRecord,
    RegressionCaseSnapshot,
)
from signal_diag.rules.regression import ComparisonRecord, validate_comparison_record

_MEASUREMENT_ONLY_NOTICE = (
    "Reporting measurement changes only; no approved comparison tolerances yet"
)


def validate_regression_case_report_integrity(
    *,
    case_id: str,
    comparisons: tuple[CaseComparisonItem, ...],
    failures: tuple[CaseFailureRecord, ...],
    recommendations: tuple[CaseRecommendationRecord, ...],
) -> None:
    """Reject tampered or inconsistent case report payloads."""
    seen_ids: set[str] = set()
    for item in comparisons:
        if item.case_id != case_id:
            raise ValueError("comparison item case_id must match report case_id")
        if item.comparison_id != item.record.comparison_id:
            raise ValueError(
                "comparison item comparison_id must match record.comparison_id"
            )
        if item.comparison_id in seen_ids:
            raise ValueError("duplicate comparison_id in report")
        if (
            item.parent_comparison_id is not None
            and item.parent_comparison_id not in seen_ids
        ):
            raise ValueError("parent comparison_id is missing or out of order")
        validate_comparison_record(item.record)
        seen_ids.add(item.comparison_id)

    for failure in failures:
        if failure.case_id != case_id:
            raise ValueError("failure case_id must match report case_id")
        if (
            failure.parent_comparison_id is not None
            and failure.parent_comparison_id not in seen_ids
        ):
            raise ValueError("failure parent_comparison_id is not in this report")

    for recommendation in recommendations:
        if recommendation.case_id != case_id:
            raise ValueError("recommendation case_id must match report case_id")
        if recommendation.comparison_id not in seen_ids:
            raise ValueError(
                "recommendation comparison_id is not present in this report"
            )


class RegressionCaseReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "regression_case_report_v1"
    generated_at: datetime
    case_id: str
    goal: str
    revision: int
    comparisons: tuple[CaseComparisonItem, ...]
    failures: tuple[CaseFailureRecord, ...]
    recommendations: tuple[CaseRecommendationRecord, ...]
    latest_submit_status: str
    measurement_only_notice: str = Field(default=_MEASUREMENT_ONLY_NOTICE)

    @model_validator(mode="after")
    def validate_integrity(self) -> RegressionCaseReport:
        validate_regression_case_report_integrity(
            case_id=self.case_id,
            comparisons=self.comparisons,
            failures=self.failures,
            recommendations=self.recommendations,
        )
        return self


def build_case_report(
    snapshot: RegressionCaseSnapshot,
    *,
    generated_at: datetime,
) -> RegressionCaseReport:
    validate_regression_case_report_integrity(
        case_id=snapshot.case_id,
        comparisons=snapshot.comparisons,
        failures=snapshot.failures,
        recommendations=snapshot.recommendations,
    )
    return RegressionCaseReport(
        generated_at=generated_at,
        case_id=snapshot.case_id,
        goal=snapshot.goal,
        revision=snapshot.revision,
        comparisons=snapshot.comparisons,
        failures=snapshot.failures,
        recommendations=snapshot.recommendations,
        latest_submit_status=snapshot.latest_submit_status,
    )


def render_case_json(report: RegressionCaseReport) -> str:
    return (
        json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _render_metric_rows(record: ComparisonRecord) -> str:
    rows: list[str] = []
    for row in record.metric_comparisons:
        baseline_value = (
            row.baseline_ref.value if row.baseline_ref is not None else None
        )
        candidate_value = (
            row.candidate_ref.value if row.candidate_ref is not None else None
        )
        rows.append(
            "<tr>"
            f"<td>{_esc(row.metric)}</td>"
            f"<td>{_esc(baseline_value)}</td>"
            f"<td>{_esc(candidate_value)}</td>"
            f"<td>{_esc(row.difference)}</td>"
            f"<td>{_esc(row.difference_unit)}</td>"
            f"<td>{_esc(row.status)}</td>"
            f"<td>{_esc(', '.join(row.reason_codes))}</td>"
            f"<td>{_esc(row.rule_ref)}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _render_coverage(record: ComparisonRecord) -> str:
    items: list[str] = []
    for entry in record.coverage:
        items.append(
            "<li>"
            f"{_esc(entry.check_id)}: {_esc(entry.status)}"
            + (f" ({_esc(entry.detail)})" if entry.detail else "")
            + "</li>"
        )
    return "\n".join(items)


def render_case_html(report: RegressionCaseReport) -> str:
    parts: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>Regression case {_esc(report.case_id)}</title>",
        "<style>",
        "body{font-family:sans-serif;margin:1.5rem;color:#111;background:#fff}",
        "section{margin-bottom:1.25rem}h1,h2{margin:0 0 .75rem}",
        "table{border-collapse:collapse;width:100%}",
        "th,td{border:1px solid #ccc;padding:.35rem;text-align:left}",
        ".notice{font-style:italic;color:#444}",
        "</style>",
        "</head>",
        "<body>",
        f"<h1>Regression case {_esc(report.case_id)}</h1>",
        '<section id="goal">',
        "<h2>Goal and conditions</h2>",
        f"<p><strong>Goal</strong>: {_esc(report.goal)}</p>",
        f"<p class=\"notice\">{_esc(report.measurement_only_notice)}</p>",
        "</section>",
    ]
    for index, item in enumerate(report.comparisons):
        record = item.record
        conditions = record.conditions
        parts.extend(
            [
                f'<section id="comparison-{index}">',
                f"<h2>Comparison {_esc(item.comparison_id)}</h2>",
                (
                    "<p>"
                    f"<strong>Baseline version</strong>: {_esc(conditions.baseline_version)}; "
                    f"<strong>Candidate version</strong>: {_esc(conditions.candidate_version)}"
                    "</p>"
                ),
                "<table>",
                (
                    "<thead><tr>"
                    "<th>metric</th><th>baseline</th><th>candidate</th>"
                    "<th>difference</th><th>unit</th><th>status</th>"
                    "<th>reasons</th><th>rule_ref</th>"
                    "</tr></thead>"
                ),
                "<tbody>",
                _render_metric_rows(record),
                "</tbody></table>",
                "<h3>Coverage</h3>",
                "<ul>",
                _render_coverage(record),
                "</ul>",
                "</section>",
            ]
        )
    if report.failures:
        parts.append('<section id="failures"><h2>Failures</h2><ul>')
        for failure in report.failures:
            parts.append(
                f"<li>{_esc(failure.request_id)}: {_esc(failure.message)}</li>"
            )
        parts.append("</ul></section>")
    if report.recommendations:
        parts.append('<section id="recommendations"><h2>Recommendations</h2><ul>')
        for rec in report.recommendations:
            parts.append(
                "<li>"
                f"{_esc(rec.comparison_id)} / {_esc(rec.status)}"
                + (f": {_esc(rec.detail)}" if rec.detail else "")
                + "</li>"
            )
        parts.append("</ul></section>")
    parts.extend(
        [
            '<section id="export-meta">',
            (
                f"<p>Revision {_esc(report.revision)}; "
                f"latest submit {_esc(report.latest_submit_status)}; "
                f"generated {_esc(report.generated_at.isoformat())}</p>"
            ),
            "</section>",
            "</body></html>",
        ]
    )
    return "\n".join(parts)
