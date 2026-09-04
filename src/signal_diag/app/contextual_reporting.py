"""Contextual diagnosis report projection and rendering."""

from __future__ import annotations

import html
import json
from datetime import datetime

from signal_diag.app.contextual_models import (
    ContextualAppRunSnapshot,
    ContextualDiagnosisReport,
)
from signal_diag.app.errors import TraceIntegrityError
from signal_diag.app.models import AppErrorDetail

_DEMO_PROFILE_LABEL = (
    "profile_s1_distortion 1.0.0-demo demonstration settings "
    "(1% clipping, 5% THD), not industry standards or SLAs."
)
_UNCERTIFIED_LABEL = "uncertified by Phase 4.3.1"


def _trace_error(message: str) -> AppErrorDetail:
    return AppErrorDetail(code="trace_integrity_error", message=message)


def build_contextual_diagnosis_report(
    snapshot: ContextualAppRunSnapshot,
    *,
    generated_at: datetime,
) -> ContextualDiagnosisReport:
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
    return ContextualDiagnosisReport(
        generated_at=generated_at,
        run_id=snapshot.run_id,
        test_source=snapshot.test_source,
        reference_source=snapshot.reference_source,
        stimulus_context=snapshot.stimulus_context,
        effective_capabilities=snapshot.effective_capabilities,
        analyzed_channel=snapshot.analyzed_channel,
        user_request=snapshot.user_request,
        planner_identity=snapshot.planner_identity,
        test_preview=snapshot.test_preview,
        trace_events=snapshot.trace_events,
        result=result,
    )


def render_contextual_report_json(report: ContextualDiagnosisReport) -> str:
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


def render_contextual_report_html(report: ContextualDiagnosisReport) -> str:
    data = report.model_dump(mode="json")
    test_source = data["test_source"]
    reference_source = data.get("reference_source")
    context = data["stimulus_context"]
    capabilities = data["effective_capabilities"]
    planner = data["planner_identity"]
    preview = data["test_preview"]
    result = data["result"]
    diagnosis = result.get("diagnosis")
    parts: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>Contextual diagnosis report {_esc(data['run_id'])}</title>",
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
        f'<h1 id="report-{_esc(data["run_id"])}">Contextual diagnosis report</h1>',
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
        '<section id="declared-context">',
        "<h2>Declared context</h2>",
        "<dl>",
        f"<dt>mode</dt><dd>{_esc(context['mode'])}</dd>",
        f"<dt>assertion_source</dt><dd>{_esc(context['assertion_source'])}</dd>",
        f"<dt>test_signal_id</dt><dd>{_esc(context['test_signal_id'])}</dd>",
        (
            f"<dt>reference_signal_id</dt>"
            f"<dd>{_esc(context.get('reference_signal_id'))}</dd>"
        ),
        (
            f"<dt>nominal_fundamental_hz</dt>"
            f"<dd>{_esc(context.get('nominal_fundamental_hz'))}</dd>"
        ),
        f"<dt>stimulus_kind</dt><dd>{_esc(context.get('stimulus_kind'))}</dd>",
        "</dl>",
        "<p>StimulusContext is declared provenance, not measured Evidence.</p>",
        "</section>",
        '<section id="effective-capabilities">',
        "<h2>Effective capabilities</h2>",
        "<dl>",
        f"<dt>clipping</dt><dd>{_esc(capabilities['clipping'])}</dd>",
        (
            f"<dt>absolute_harmonic_description</dt>"
            f"<dd>{_esc(capabilities['absolute_harmonic_description'])}</dd>"
        ),
        (
            f"<dt>nominal_harmonic_attribution</dt>"
            f"<dd>{_esc(capabilities['nominal_harmonic_attribution'])}</dd>"
        ),
        (
            f"<dt>paired_harmonic_attribution</dt>"
            f"<dd>{_esc(capabilities['paired_harmonic_attribution'])}</dd>"
        ),
        "</dl>",
        "</section>",
        '<section id="test-source">',
        "<h2>Test source</h2>",
        "<dl>",
        f"<dt>kind</dt><dd>{_esc(test_source['source_kind'])}</dd>",
        f"<dt>filename</dt><dd>{_esc(test_source['display_name'])}</dd>",
        f"<dt>sample_rate_hz</dt><dd>{_esc(test_source['sample_rate_hz'])}</dd>",
        f"<dt>channels</dt><dd>{_esc(test_source['channels'])}</dd>",
        "</dl>",
        "</section>",
    ]
    parts.extend(
        [
            '<section id="reference-source">',
            "<h2>Reference source</h2>",
        ]
    )
    if reference_source:
        parts.extend(
            [
                "<dl>",
                f"<dt>kind</dt><dd>{_esc(reference_source['source_kind'])}</dd>",
                f"<dt>filename</dt><dd>{_esc(reference_source['display_name'])}</dd>",
                (
                    f"<dt>sample_rate_hz</dt>"
                    f"<dd>{_esc(reference_source['sample_rate_hz'])}</dd>"
                ),
                f"<dt>channels</dt><dd>{_esc(reference_source['channels'])}</dd>",
                "</dl>",
            ]
        )
    else:
        parts.append("<p>No reference source for this mode.</p>")
    parts.extend(
        [
            "</section>",
            '<section id="planner">',
            "<h2>Planner identity</h2>",
            "<dl>",
            f"<dt>provider</dt><dd>{_esc(planner['provider'])}</dd>",
            f"<dt>model</dt><dd>{_esc(planner['model'])}</dd>",
            f"<dt>prompt</dt><dd>{_esc(planner['prompt_version'])}</dd>",
            "</dl>",
        ]
    )
    if not planner.get("phase4_certified_default"):
        parts.append(f"<p>{_esc(_UNCERTIFIED_LABEL)}</p>")
    parts.extend(
        [
            "</section>",
            '<section id="preview">',
            "<h2>Test waveform preview</h2>",
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
    parts.extend(
        ["</tbody></table>", "</section>", '<section id="diagnosis">', "<h2>Diagnosis</h2>"]
    )
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
                _ref_link("knowledge", item)
                for item in claim.get("knowledge_refs") or ()
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
    parts.extend(
        [
            "</section>",
            '<section id="measured-evidence">',
            "<h2>Measured Evidence</h2>",
        ]
    )
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
    parts.extend(
        [
            "</section>",
            '<section id="limitations">',
            "<h2>Comparison limitations</h2>",
        ]
    )
    limitations = (diagnosis or {}).get("limitations") or ()
    if limitations:
        for item in limitations:
            parts.append(f"<p>{_esc(item)}</p>")
    else:
        parts.append("<p>No additional comparison limitations recorded.</p>")
    parts.extend(
        [
            "</section>",
            '<section id="notes">',
            "<h2>Warnings and errors</h2>",
        ]
    )
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
