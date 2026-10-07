"""Contextual diagnosis report projection and rendering."""

from __future__ import annotations

import html
import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from signal_diag.app.context_guidance import validate_observed_facts_against_evidence
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
    if snapshot.context_guidance is not None:
        try:
            validate_observed_facts_against_evidence(
                evidence=result.evidence,
                observed_facts=snapshot.context_guidance.observed_facts,
            )
        except ValueError as exc:
            raise TraceIntegrityError(_trace_error(str(exc))) from exc
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
        diagnosis_identity=snapshot.diagnosis_identity,
        test_preview=snapshot.test_preview,
        trace_events=snapshot.trace_events,
        result=result,
        context_guidance=snapshot.context_guidance,
        context_origin=snapshot.context_origin,
        fault_localization=snapshot.fault_localization,
    )


_LOCALIZATION_OPTIONAL = (
    "harmonic_basis",
    "comparison_overlap",
    "windows_not_comparable",
    "harmonic_windows_withheld",
)


def _unset_optional_fields(
    model: ContextualAppRunSnapshot | ContextualDiagnosisReport,
) -> dict[str, Any] | None:
    # §25/§27: unset optional additions are omitted, so older runs keep their shape.
    unset: dict[str, Any] = {
        name: True
        for name in (
            "context_origin",
            "fault_localization",
            "planner_identity",
            "diagnosis_identity",
        )
        if getattr(model, name) is None
    }
    localization = model.fault_localization
    if localization is not None:
        nested = {
            name: True for name in _LOCALIZATION_OPTIONAL if getattr(localization, name) is None
        }
        if nested:
            unset["fault_localization"] = nested
    return unset or None


def dump_contextual_snapshot(snapshot: ContextualAppRunSnapshot) -> dict[str, object]:
    return snapshot.model_dump(mode="json", exclude=_unset_optional_fields(snapshot))


def render_contextual_report_json(
    report: ContextualDiagnosisReport, *, explanation: Mapping[str, object] | None = None
) -> str:
    """``explanation`` (§30) is added only when one was produced for the run."""
    payload = report.model_dump(mode="json", exclude=_unset_optional_fields(report))
    if explanation is not None:
        payload["explanation"] = dict(explanation)
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


_CONTEXT_ORIGIN_LABELS = {
    "intake_confirmed": "free-text draft, confirmed by the user",
}


def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _ref_link(kind: str, reference_id: str) -> str:
    return f'<a href="#{kind}-{_esc(reference_id)}">{_esc(reference_id)}</a>'


_FAULT_LABELS = {"clipping": "clipping", "harmonic_distortion": "harmonic distortion"}


_HARMONIC_BASIS_TEXT = {
    None: "harmonic windows not scanned",
    "nominal_thd": "harmonic windows scanned at the declared fundamental",
    "reference_growth": (
        "harmonic windows compared with the same span of the reference "
        "(non-overlapping windows)"
    ),
}


def _fault_localization_html(localization: dict[str, object] | None) -> list[str]:
    """§27: fault time locations from the deterministic segment scan."""
    if not localization:
        return []
    parts = [
        '<section id="fault-localization">',
        "<h2>Fault locations (deterministic segment scan)</h2>",
        (
            f"<p>{_esc(localization['scan_version'])}: "
            f"{_esc(localization['window_s'])} s windows, "
            f"{_esc(localization['overlap'])} overlap, channels "
            f"{_esc(', '.join(localization['channels']))}; "  # type: ignore[arg-type]
            f"{_esc(_HARMONIC_BASIS_TEXT[localization.get('harmonic_basis')])}.</p>"  # type: ignore[index]
        ),
    ]
    not_comparable = localization.get("windows_not_comparable")
    if not_comparable is not None:
        parts.append(
            f"<p>Reference comparison windows that could not be compared: "
            f"{_esc(not_comparable)}.</p>"
        )
    withheld = localization.get("harmonic_windows_withheld")
    if withheld:
        parts.append(
            f"<p>{_esc(withheld)} reference comparison windows showed harmonic growth; "
            "their locations are not shown because the diagnosis did not support "
            "harmonic distortion.</p>"
        )
    intervals = localization.get("intervals") or ()
    if not intervals:
        parts.append(
            "<p>No fault location to list.</p>"
            if localization.get("harmonic_windows_withheld")
            else "<p>No segment rule failed; no fault location to report.</p>"
        )
    for interval in intervals:  # type: ignore[attr-defined]
        status = (
            "matches the diagnosis"
            if interval["agrees_with_diagnosis"]
            else "found by the scan, not adopted by the diagnosis; review needed"
        )
        parts.append(
            "<p>"
            f"{_esc(_FAULT_LABELS.get(interval['fault'], interval['fault']))}, "
            f"{_esc(interval['channel'])}, "
            f"{float(interval['start_s']):.3f}–{float(interval['end_s']):.3f} s "
            f"({_esc(status)}); evidence "
            f"{_esc(', '.join(interval['evidence_refs']))}; rules "
            f"{_esc(', '.join(interval['evaluation_refs']))}"
            "</p>"
        )
    parts.append("</section>")
    return parts


def render_contextual_report_html(
    report: ContextualDiagnosisReport, *, explanation_html: str | None = None
) -> str:
    data = report.model_dump(mode="json")
    test_source = data["test_source"]
    reference_source = data.get("reference_source")
    context = data["stimulus_context"]
    capabilities = data["effective_capabilities"]
    planner = data.get("planner_identity")
    identity = data.get("diagnosis_identity")
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
        *(
            (
                (
                    "<dt>context_source</dt>"
                    f"<dd>{_esc(_CONTEXT_ORIGIN_LABELS[data['context_origin']])}</dd>"
                ),
            )
            if data.get("context_origin") is not None
            else ()
        ),
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
        ]
    )
    if identity is not None and identity["kind"] == "deterministic_engine":
        parts.extend(
            [
                '<section id="diagnosis-engine">',
                "<h2>Diagnosis engine</h2>",
                (
                    "<p>The verdict was reached by the deterministic engine "
                    f"{_esc(identity['engine_version'])} from versioned rules "
                    f"({_esc(', '.join(identity['rule_profiles']))}); "
                    "no model decided it.</p>"
                ),
            ]
        )
    if planner is not None:
        parts.extend(
            [
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
        [
            "</tbody></table>",
            "</section>",
            '<section id="diagnosis">',
            "<h2>Diagnosis</h2>",
        ]
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
    parts.append("</section>")
    guidance = data.get("context_guidance")
    if guidance:
        parts.extend(
            [
                '<section id="context-guidance">',
                "<h2>Context guidance</h2>",
                f"<p>{_esc(guidance.get('summary'))}</p>",
                "<dl>",
                (
                    f"<dt>reason_codes</dt>"
                    f"<dd>{_esc(', '.join(guidance.get('reason_codes') or ()))}</dd>"
                ),
                (
                    f"<dt>unlockable_modes</dt>"
                    f"<dd>{_esc(', '.join(guidance.get('unlockable_modes') or ()))}</dd>"
                ),
                "</dl>",
            ]
        )
        required = guidance.get("required_inputs") or {}
        for mode_name, inputs in required.items():
            parts.append(f"<p>{_esc(mode_name)}: {_esc(', '.join(inputs or ()))}</p>")
        facts = guidance.get("observed_facts") or ()
        if facts:
            parts.append('<ul id="observed-facts">')
            for fact in facts:
                unit = fact.get("unit")
                unit_suffix = "" if unit is None else f" {_esc(unit)}"
                parts.append(
                    "<li>"
                    f"{_esc(fact.get('evidence_id'))} "
                    f"{_esc(fact.get('metric'))}="
                    f"{_esc(fact.get('value'))}"
                    f"{unit_suffix}"
                    "</li>"
                )
            parts.append("</ul>")
        parts.append("</section>")
    parts.extend(_fault_localization_html(data.get("fault_localization")))
    parts.extend(
        [
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
            *((explanation_html,) if explanation_html else ()),
            "</body>",
            "</html>",
            "",
        ]
    )
    return "\n".join(parts)
