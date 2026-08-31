"""Canonical diagnosis reports and packaged evaluation summary loading."""

from __future__ import annotations

import html
import json
from datetime import datetime
from importlib.resources import files
from typing import Literal

from signal_diag.app.errors import TraceIntegrityError
from signal_diag.app.models import (
    AcceptedEvaluationSummary,
    AppErrorDetail,
    AppRunSnapshot,
    DiagnosisReport,
    TraceEventView,
)
from signal_diag.evaluation.models import (
    EvaluationEvent,
    KnowledgeRetrievalEvent,
    ObservationEvent,
    PlannerDecisionEvent,
    ProviderUsage,
    RuleEvaluationEvent,
)

_DEMO_PROFILE_LABEL = (
    "profile_s1_distortion 1.0.0-demo demonstration settings "
    "(1% clipping, 5% THD), not industry standards or SLAs."
)
_UNCERTIFIED_LABEL = "uncertified by Phase 4.3.1"


def _trace_error(message: str) -> AppErrorDetail:
    return AppErrorDetail(code="trace_integrity_error", message=message)


def project_agent_events(
    events: tuple[EvaluationEvent, ...],
) -> tuple[TraceEventView, ...]:
    projected: list[TraceEventView] = []
    for event in events:
        action: str
        refs: tuple[str, ...]
        kind: Literal["planner", "observation", "rule", "knowledge"]
        purpose: str | None
        status: str
        usage: ProviderUsage | None
        latency: float | None
        if isinstance(event, PlannerDecisionEvent):
            record = event.record
            action = (
                record.decision.decision_type
                if record.decision is not None
                else record.status
            )
            refs = ()
            kind = "planner"
            purpose = getattr(record.decision, "purpose", None)
            status = record.status
            usage = record.provider_usage
            latency = record.latency_ms
        elif isinstance(event, ObservationEvent):
            action = event.observation.tool_name
            refs = event.observation.evidence_refs
            kind, purpose, status, usage, latency = (
                "observation",
                event.observation.purpose,
                event.observation.status,
                None,
                None,
            )
        elif isinstance(event, RuleEvaluationEvent):
            action = event.batch.profile_id
            refs = tuple(item.evaluation_id for item in event.batch.evaluations)
            kind, purpose, status, usage, latency = (
                "rule",
                None,
                "completed",
                None,
                None,
            )
        elif isinstance(event, KnowledgeRetrievalEvent):
            action = "retrieve_knowledge"
            refs = (event.retrieval.retrieval_id,)
            kind, purpose, status, usage, latency = (
                "knowledge",
                None,
                "completed",
                None,
                None,
            )
        else:
            raise TypeError(f"unsupported evaluation event: {type(event)!r}")
        projected.append(
            TraceEventView(
                event_index=event.event_index,
                kind=kind,
                action_name=action,
                status=status,
                purpose=purpose,
                reference_ids=refs,
                latency_ms=latency,
                provider_usage=usage,
            )
        )
    return tuple(projected)


def build_diagnosis_report(
    snapshot: AppRunSnapshot,
    *,
    generated_at: datetime,
) -> DiagnosisReport:
    if snapshot.status != "completed" or snapshot.result is None:
        raise ValueError("report requires a completed snapshot with a result")
    result = snapshot.result
    evidence_ids = {item.evidence_id for item in result.evidence}
    rule_ids = {
        item.evaluation_id
        for batch in result.rule_evaluation_batches
        for item in batch.evaluations
    }
    knowledge_ids = {item.retrieval_id for item in result.knowledge_retrievals}
    for claim in result.diagnosis.claims if result.diagnosis else ():
        if not set(claim.evidence_refs) <= evidence_ids:
            raise TraceIntegrityError(_trace_error("unknown Evidence reference"))
        if not set(claim.rule_refs) <= rule_ids:
            raise TraceIntegrityError(_trace_error("unknown Rule reference"))
        if not set(claim.knowledge_refs) <= knowledge_ids:
            raise TraceIntegrityError(_trace_error("unknown Knowledge reference"))
    return DiagnosisReport(
        generated_at=generated_at,
        run_id=snapshot.run_id,
        source=snapshot.source,
        analyzed_channel=snapshot.analyzed_channel,
        user_request=snapshot.user_request,
        planner_identity=snapshot.planner_identity,
        waveform_preview=snapshot.waveform_preview,
        trace_events=snapshot.trace_events,
        result=result,
    )


def render_report_json(report: DiagnosisReport) -> str:
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


def _ref_link(kind: str, reference_id: str) -> str:
    return f'<a href="#{kind}-{_esc(reference_id)}">{_esc(reference_id)}</a>'


def render_report_html(report: DiagnosisReport) -> str:
    data = report.model_dump(mode="json")
    source = data["source"]
    planner = data["planner_identity"]
    preview = data["waveform_preview"]
    result = data["result"]
    diagnosis = result.get("diagnosis")
    parts: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>Diagnosis report {_esc(data['run_id'])}</title>",
        "<style>",
        "body{font-family:sans-serif;margin:1.5rem;color:#111;background:#fff}",
        "section{margin-bottom:1.5rem}h1,h2{margin:0 0 .75rem}",
        "dl{display:grid;grid-template-columns:max-content 1fr;gap:.25rem 1rem}",
        "dt{font-weight:600}table{border-collapse:collapse;width:100%}",
        "th,td{border:1px solid #ccc;padding:.35rem;text-align:left}",
        ".preview-note{font-style:italic}",
        "</style>",
        "</head>",
        "<body>",
        f'<h1 id="report-{_esc(data["run_id"])}">Diagnosis report</h1>',
        '<section id="identity">',
        "<h2>Run identity</h2>",
        "<dl>",
        f"<dt>schema</dt><dd>{_esc(data['schema_version'])}</dd>",
        f"<dt>generated_at</dt><dd>{_esc(data['generated_at'])}</dd>",
        f"<dt>run_id</dt><dd>{_esc(data['run_id'])}</dd>",
        f"<dt>status</dt><dd>{_esc(data['status'])}</dd>",
        f"<dt>channel</dt><dd>{_esc(data['analyzed_channel'])}</dd>",
        f"<dt>question</dt><dd>{_esc(data['user_request'])}</dd>",
        "</dl>",
        "</section>",
        '<section id="source">',
        "<h2>Source</h2>",
        "<dl>",
        f"<dt>kind</dt><dd>{_esc(source['source_kind'])}</dd>",
        f"<dt>filename</dt><dd>{_esc(source['display_name'])}</dd>",
        f"<dt>sample_rate_hz</dt><dd>{_esc(source['sample_rate_hz'])}</dd>",
        f"<dt>channels</dt><dd>{_esc(source['channels'])}</dd>",
        "</dl>",
        "</section>",
        '<section id="planner">',
        "<h2>Planner identity</h2>",
        "<dl>",
        f"<dt>provider</dt><dd>{_esc(planner['provider'])}</dd>",
        f"<dt>model</dt><dd>{_esc(planner['model'])}</dd>",
        f"<dt>prompt</dt><dd>{_esc(planner['prompt_version'])}</dd>",
        "</dl>",
    ]
    if not planner.get("phase4_certified_default"):
        parts.append(f"<p>{_esc(_UNCERTIFIED_LABEL)}</p>")
    parts.extend(
        [
            "</section>",
            '<section id="preview">',
            "<h2>Waveform preview</h2>",
            f'<p class="preview-note">{_esc(str(preview["label"]).replace("_", " "))}</p>',
            (
                f"<p>points: {_esc(len(preview.get('points') or ()))} / "
                f"{_esc(preview['original_num_samples'])} samples at "
                f"{_esc(preview['sample_rate_hz'])} Hz</p>"
            ),
            "</section>",
            '<section id="trace">',
            "<h2>Trace</h2>",
            (
                "<table><thead><tr><th>index</th><th>kind</th><th>action</th>"
                "<th>status</th><th>refs</th></tr></thead><tbody>"
            ),
        ]
    )
    for event in data.get("trace_events") or ():
        refs = event.get("reference_ids") or ()
        kind = event["kind"]
        prefix = {
            "observation": "evidence",
            "rule": "rule",
            "knowledge": "knowledge",
        }.get(kind, "ref")
        linked = ", ".join(_ref_link(prefix, item) for item in refs)
        parts.append(
            f'<tr id="event-{_esc(event["event_index"])}">'
            f"<td>{_esc(event['event_index'])}</td>"
            f"<td>{_esc(kind)}</td>"
            f"<td>{_esc(event['action_name'])}</td>"
            f"<td>{_esc(event['status'])}</td>"
            f"<td>{linked}</td></tr>"
        )
    parts.extend(["</tbody></table>", "</section>", '<section id="diagnosis">', "<h2>Diagnosis</h2>"])
    if diagnosis:
        parts.append("<dl>")
        parts.append(f"<dt>outcome</dt><dd>{_esc(diagnosis.get('outcome'))}</dd>")
        parts.append(
            f"<dt>termination</dt><dd>{_esc(result.get('termination_reason'))}</dd>"
        )
        parts.append("</dl>")
        for claim in diagnosis.get("claims") or ():
            claim_id = _esc(claim.get("claim_id"))
            evidence_links = ", ".join(
                _ref_link("evidence", item) for item in claim.get("evidence_refs") or ()
            )
            rule_links = ", ".join(
                _ref_link("rule", item) for item in claim.get("rule_refs") or ()
            )
            knowledge_links = ", ".join(
                _ref_link("knowledge", item) for item in claim.get("knowledge_refs") or ()
            )
            parts.extend(
                [
                    f'<article id="claim-{claim_id}">',
                    f"<h3>{claim_id}</h3>",
                    f"<p>{_esc(claim.get('statement'))}</p>",
                    f"<p>fault: {_esc(claim.get('fault_type'))}</p>",
                    f"<p>evidence: {evidence_links}</p>",
                    f"<p>rules: {rule_links}</p>",
                    f"<p>knowledge: {knowledge_links}</p>",
                    "</article>",
                ]
            )
    else:
        parts.append("<p>No structured diagnosis.</p>")
    parts.extend(["</section>", '<section id="evidence">', "<h2>Evidence</h2>"])
    for item in result.get("evidence") or ():
        parts.append(
            f'<article id="evidence-{_esc(item.get("evidence_id"))}">'
            f"<p>{_esc(item.get('evidence_id'))} {_esc(item.get('metric'))} "
            f"{_esc(item.get('value'))}</p></article>"
        )
    parts.extend(["</section>", '<section id="rules">', "<h2>Rule evaluations</h2>"])
    for batch in result.get("rule_evaluation_batches") or ():
        for item in batch.get("evaluations") or ():
            parts.append(
                f'<article id="rule-{_esc(item.get("evaluation_id"))}">'
                f"<p>{_esc(item.get('evaluation_id'))} "
                f"{_esc(item.get('profile_id'))} {_esc(item.get('profile_version'))} "
                f"{_esc(item.get('judgment'))}</p></article>"
            )
    parts.extend(["</section>", '<section id="knowledge">', "<h2>Knowledge</h2>"])
    for retrieval in result.get("knowledge_retrievals") or ():
        excerpts = " ".join(
            _esc(chunk.get("excerpt")) for chunk in retrieval.get("chunks") or ()
        )
        parts.append(
            f'<article id="knowledge-{_esc(retrieval.get("retrieval_id"))}">'
            f"<p>{_esc(retrieval.get('retrieval_id'))} {excerpts}</p></article>"
        )
    parts.extend(["</section>", '<section id="notes">', "<h2>Warnings and errors</h2>"])
    for warning in result.get("warnings") or ():
        parts.append(f"<p>warning: {_esc(warning)}</p>")
    for error in result.get("errors") or ():
        parts.append(f"<p>error: {_esc(error)}</p>")
    parts.extend(
        [
            "</section>",
            '<section id="limits">',
            "<h2>Limits</h2>",
            f"<p>{_esc(_DEMO_PROFILE_LABEL)}</p>",
            "</section>",
            "</body>",
            "</html>",
            "",
        ]
    )
    return "\n".join(parts)


def load_accepted_evaluation_summary() -> AcceptedEvaluationSummary:
    payload = (
        files("signal_diag.evaluation.assets")
        .joinpath("phase4_3_1_official_summary.json")
        .read_text(encoding="utf-8")
    )
    return AcceptedEvaluationSummary.model_validate_json(payload)
