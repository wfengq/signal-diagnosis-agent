"""Checkpoint Y — diagnosis reports and accepted evaluation summary (T256–T263, T279)."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path

import pytest

from signal_diag.app.errors import TraceIntegrityError, sanitize_application_error
from signal_diag.app.models import (
    AppErrorDetail,
    AppRunSnapshot,
    DiagnosisReport,
    PlannerIdentity,
    SourceSummary,
    TraceEventView,
    WaveformPoint,
    WaveformPreview,
)
from signal_diag.app.reporting import (
    build_diagnosis_report,
    load_accepted_evaluation_summary,
    project_agent_events,
    render_report_html,
    render_report_json,
)
from signal_diag.evaluation.models import (
    AggregateMetrics,
    KnowledgeRetrievalEvent,
    ObservationEvent,
    PlannerDecisionEvent,
    RuleEvaluationEvent,
    TargetBands,
)
from signal_diag.evaluation.recording import assemble_agent_events
from tests.evaluation.test_recording import _full_agent_chain

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
STARTED = datetime(2026, 8, 31, 12, 1, tzinfo=UTC)
FINISHED = datetime(2026, 8, 31, 12, 2, tzinfo=UTC)
GENERATED_AT = datetime(2026, 8, 31, 12, 3, tzinfo=UTC)
RUN_ID = "run_0123456789abcdef0123456789abcdef"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
OFFICIAL_BUNDLE = (
    PROJECT_ROOT
    / "docs"
    / "evaluations"
    / "phase4_3_1"
    / "official"
    / "bench_official_s1_v12_planner8_1_gate5"
)
ASSET_PATH = (
    PROJECT_ROOT
    / "src"
    / "signal_diag"
    / "evaluation"
    / "assets"
    / "phase4_3_1_official_summary.json"
)
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "build_phase5_evaluation_summary.py"
OFFICIAL_CHECKSUMS = {
    "benchmark_manifest.json": (
        "355fc75eab5d4580606fb3eb31a71566cc4b2a8303d412aa309df5b3c9ae71a7"
    ),
    "case_summary.csv": (
        "3699061f726cf8de1b8d6eff9bcf3bd8487431d64f23944dbf0c95ce87bcaeae"
    ),
    "metrics.json": (
        "e60aa63de6f030bf88fd7154cd0f7b72fd7bf36589ad769a234ee02fd6e956d0"
    ),
    "report.md": "8f2f47e34731254ae45987445076e041f8675da17f56cc0463530c412ec1b4f0",
    "runs.jsonl": "cff5a41ea8ed6f7838cc72e25b678d7b11eb97976e27a039e80d877d781ac35d",
}
FORBIDDEN_RENDER_TOKENS = (
    "api_key",
    "api-key",
    "authorization",
    "bearer ",
    "sk-",
    "traceback",
    "ndarray",
    "numpy.",
    "raw_response",
    "provider_response",
    "response_body",
    "raw_body",
    "raw_provider_response",
)
CONTEXT_LEAK_TOKENS = (
    "available_tools",
    "signal_meta",
    "remaining_tool_calls",
    "remaining_planner_retries",
    "PlannerContext",
    "in_progress",
)


def _wav_source(filename: str = "input.wav") -> SourceSummary:
    return SourceSummary(
        source_kind="wav",
        display_name=filename,
        sample_rate_hz=48_000,
        channels=2,
        num_frames=48_000,
        duration_s=1.0,
        bits_per_sample=16,
    )


def _preview() -> WaveformPreview:
    return WaveformPreview(
        sample_rate_hz=48_000,
        original_num_samples=1,
        points=(WaveformPoint(sample_index=0, time_s=0.0, amplitude=0.5),),
    )


def _planner(
    *,
    certified: bool = True,
    model: str = "deepseek-v4-flash",
) -> PlannerIdentity:
    return PlannerIdentity(
        provider="deepseek",
        model=model,
        prompt_version="v0.2-s1-planner-8.1",
        phase4_certified_default=certified,
    )


def _completed_snapshot(**overrides: object) -> AppRunSnapshot:
    _case, records, result, _config = _full_agent_chain()
    events = assemble_agent_events(records, result)
    payload: dict[str, object] = {
        "run_id": RUN_ID,
        "status": "completed",
        "created_at": NOW,
        "started_at": STARTED,
        "finished_at": FINISHED,
        "user_request": "Why does this signal sound distorted?",
        "analyzed_channel": "mixdown",
        "source": _wav_source(),
        "planner_identity": _planner(),
        "waveform_preview": _preview(),
        "trace_events": project_agent_events(events),
        "result": result,
    }
    payload.update(overrides)
    return AppRunSnapshot.model_validate(payload)


def _report(*, filename: str | None = None, **overrides: object) -> DiagnosisReport:
    snapshot_overrides: dict[str, object] = dict(overrides)
    if filename is not None:
        snapshot_overrides["source"] = _wav_source(filename)
    return build_diagnosis_report(
        _completed_snapshot(**snapshot_overrides),
        generated_at=GENERATED_AT,
    )


def _replace_claim(snapshot: AppRunSnapshot, **claim_updates: object) -> AppRunSnapshot:
    assert snapshot.result is not None
    assert snapshot.result.diagnosis is not None
    claim = snapshot.result.diagnosis.claims[0].model_copy(update=claim_updates)
    diagnosis = snapshot.result.diagnosis.model_copy(update={"claims": (claim,)})
    result = snapshot.result.model_copy(update={"diagnosis": diagnosis})
    return snapshot.model_copy(update={"result": result})


def test_t256_projection_is_compact_ordered_and_unleaky() -> None:
    _case, records, result, _config = _full_agent_chain()
    events = assemble_agent_events(records, result)
    projected = project_agent_events(events)

    assert len(projected) == len(events)
    assert [item.event_index for item in projected] == [item.event_index for item in events]
    assert [item.kind for item in projected] == [
        "planner",
        "observation",
        "planner",
        "planner",
        "rule",
        "planner",
        "knowledge",
        "planner",
    ]
    assert [type(item) for item in events] == [
        PlannerDecisionEvent,
        ObservationEvent,
        PlannerDecisionEvent,
        PlannerDecisionEvent,
        RuleEvaluationEvent,
        PlannerDecisionEvent,
        KnowledgeRetrievalEvent,
        PlannerDecisionEvent,
    ]

    planner = projected[0]
    assert planner.action_name == "call_tool"
    assert planner.purpose == "inspect clipping"
    assert planner.status == "decision"
    assert planner.reference_ids == ()
    assert planner.latency_ms == 1.0
    assert planner.provider_usage is None

    observation = projected[1]
    assert observation.action_name == "detect_clipping"
    assert observation.reference_ids == ("ev_clip_001",)
    assert observation.purpose == "inspect clipping"
    assert observation.status == "success"

    error_event = projected[2]
    assert error_event.action_name == "planner_error"
    assert error_event.status == "planner_error"
    assert error_event.purpose is None

    rule_event = projected[4]
    assert rule_event.action_name == "profile_s1_distortion"
    assert rule_event.reference_ids == ("ruleval_clip_001",)
    assert rule_event.status == "completed"

    knowledge = projected[6]
    assert knowledge.action_name == "retrieve_knowledge"
    assert knowledge.reference_ids == ("know_clip_001",)
    assert knowledge.status == "completed"

    finish = projected[7]
    assert finish.action_name == "finish"

    dumped = json.dumps([item.model_dump(mode="json") for item in projected])
    for token in CONTEXT_LEAK_TOKENS:
        assert token not in dumped
    for item in projected:
        assert set(item.model_dump()) <= set(TraceEventView.model_fields)


def test_t257_completed_snapshot_builds_schema_report() -> None:
    snapshot = _completed_snapshot()
    report = build_diagnosis_report(snapshot, generated_at=GENERATED_AT)

    assert report.schema_version == "1.0.0"
    assert report.status == "completed"
    assert report.run_id == snapshot.run_id
    assert report.source == snapshot.source
    assert report.analyzed_channel == snapshot.analyzed_channel
    assert report.user_request == snapshot.user_request
    assert report.planner_identity == snapshot.planner_identity
    assert report.waveform_preview == snapshot.waveform_preview
    assert report.trace_events == snapshot.trace_events
    assert report.result == snapshot.result
    assert report.result.warnings == ()
    assert report.result.errors == ()
    assert report.generated_at == GENERATED_AT
    claim = report.result.diagnosis.claims[0] if report.result.diagnosis else None
    assert claim is not None
    assert claim.evidence_refs == ("ev_clip_001",)
    assert claim.rule_refs == ("ruleval_clip_001",)
    assert claim.knowledge_refs == ("know_clip_001",)


def test_t257_rejects_non_completed_snapshots() -> None:
    queued = AppRunSnapshot(
        run_id=RUN_ID,
        status="queued",
        created_at=NOW,
        user_request="Why does this signal sound distorted?",
        analyzed_channel="mixdown",
        source=_wav_source(),
        planner_identity=_planner(),
        waveform_preview=_preview(),
    )
    running = queued.model_copy(update={"status": "running", "started_at": STARTED})
    failed = queued.model_copy(
        update={
            "status": "failed",
            "started_at": STARTED,
            "finished_at": FINISHED,
            "application_error": AppErrorDetail(
                code="runtime_error",
                message="application failed",
            ),
        }
    )
    for snapshot in (queued, running, failed):
        with pytest.raises(ValueError, match="completed"):
            build_diagnosis_report(snapshot, generated_at=GENERATED_AT)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("evidence_refs", ("ev_unknown_001",), "unknown Evidence reference"),
        ("rule_refs", ("ruleval_unknown_001",), "unknown Rule reference"),
        ("knowledge_refs", ("know_unknown_001",), "unknown Knowledge reference"),
    ],
)
def test_t258_unknown_refs_raise_before_render(
    field: str,
    value: tuple[str, ...],
    message: str,
) -> None:
    snapshot = _replace_claim(_completed_snapshot(), **{field: value})
    with pytest.raises(TraceIntegrityError) as caught:
        build_diagnosis_report(snapshot, generated_at=GENERATED_AT)
    detail = caught.value.detail
    assert detail.code == "trace_integrity_error"
    assert detail.message == message
    assert value[0] not in detail.message
    assert value[0] not in str(caught.value)
    assert "traceback" not in detail.message.casefold()
    assert detail.details == {}


@pytest.mark.parametrize(
    ("fault_type", "outcome"),
    [
        ("clipping", "supported_fault"),
        ("no_supported_fault", "no_supported_fault"),
        ("inconclusive", "inconclusive"),
    ],
)
def test_t258_valid_reports_retain_every_reference(
    fault_type: str,
    outcome: str,
) -> None:
    snapshot = _completed_snapshot()
    assert snapshot.result is not None
    assert snapshot.result.diagnosis is not None
    claim = snapshot.result.diagnosis.claims[0].model_copy(update={"fault_type": fault_type})
    diagnosis = snapshot.result.diagnosis.model_copy(
        update={"claims": (claim,), "outcome": outcome}
    )
    result = snapshot.result.model_copy(update={"diagnosis": diagnosis})
    report = build_diagnosis_report(
        snapshot.model_copy(update={"result": result}),
        generated_at=GENERATED_AT,
    )
    retained = report.result.diagnosis.claims[0] if report.result.diagnosis else None
    assert retained is not None
    assert retained.evidence_refs == ("ev_clip_001",)
    assert retained.rule_refs == ("ruleval_clip_001",)
    assert retained.knowledge_refs == ("know_clip_001",)


def test_t259_json_is_canonical_and_round_trips() -> None:
    report = _report()
    first = render_report_json(report)
    second = render_report_json(report)
    assert first == second
    assert first.endswith("\n")
    assert DiagnosisReport.model_validate_json(first) == report
    parsed = json.loads(first)
    assert list(parsed) == sorted(parsed)


def test_t260_html_escapes_external_text() -> None:
    report = _report(filename='<img src=x onerror="alert(1)">')
    html = render_report_html(report)
    assert "<img" not in html
    assert "&lt;img" in html
    assert "<script" not in html.casefold()
    assert "http://" not in html and "https://" not in html


def test_t260_html_is_offline_and_uses_stable_anchors() -> None:
    report = _report()
    html = render_report_html(report)
    assert "<style>" in html
    assert "cdn" not in html.casefold()
    assert 'id="event-0"' in html
    assert 'id="evidence-ev_clip_001"' in html
    assert 'id="rule-ruleval_clip_001"' in html
    assert 'id="knowledge-know_clip_001"' in html
    assert 'href="#evidence-ev_clip_001"' in html
    assert 'href="#rule-ruleval_clip_001"' in html
    assert 'href="#knowledge-know_clip_001"' in html


def test_t260_html_escapes_question_llm_knowledge_and_errors() -> None:
    snapshot = _completed_snapshot()
    assert snapshot.result is not None
    assert snapshot.result.diagnosis is not None
    claim = snapshot.result.diagnosis.claims[0].model_copy(
        update={"statement": '<script>alert("claim")</script>'}
    )
    chunk = snapshot.result.knowledge_retrievals[0].chunks[0].model_copy(
        update={"excerpt": "<img src=y>"}
    )
    retrieval = snapshot.result.knowledge_retrievals[0].model_copy(
        update={"chunks": (chunk,)}
    )
    diagnosis = snapshot.result.diagnosis.model_copy(
        update={"claims": (claim,), "knowledge_retrievals": (retrieval,)}
    )
    result = snapshot.result.model_copy(
        update={
            "diagnosis": diagnosis,
            "knowledge_retrievals": (retrieval,),
            "errors": ('<script src="evil">boom</script>',),
            "warnings": ("<iframe>",),
        }
    )
    report = build_diagnosis_report(
        snapshot.model_copy(
            update={
                "result": result,
                "user_request": "<svg onload=alert(1)>question</svg>",
            }
        ),
        generated_at=GENERATED_AT,
    )
    html = render_report_html(report)
    assert "<script" not in html.casefold()
    assert "<svg" not in html
    assert "&lt;svg" in html
    assert "&lt;script" in html
    assert "<iframe" not in html
    assert "&lt;iframe" in html
    assert "<img" not in html
    assert "&lt;img" in html


def test_t261_forbidden_data_absent_and_sanitizer_still_works() -> None:
    report = _report()
    rendered = render_report_json(report) + render_report_html(report)
    lowered = rendered.casefold()
    for token in FORBIDDEN_RENDER_TOKENS:
        assert token not in lowered
    assert '"samples"' not in rendered
    assert '"waveform"' not in rendered
    assert "fft" not in lowered
    for token in CONTEXT_LEAK_TOKENS:
        assert token not in rendered

    leaked = TraceIntegrityError(
        AppErrorDetail(code="trace_integrity_error", message="api_key=secret leaked")
    )
    assert "secret" not in leaked.detail.message
    assert "[redacted]" in leaked.detail.message
    sanitized = sanitize_application_error(leaked)
    assert sanitized.code == "trace_integrity_error"
    assert "secret" not in sanitized.message


def test_t262_records_actual_identity_and_demo_labels() -> None:
    report = _report()
    assert report.planner_identity.provider == "deepseek"
    assert report.planner_identity.model == "deepseek-v4-flash"
    assert report.planner_identity.prompt_version == "v0.2-s1-planner-8.1"
    html = render_report_html(report)
    assert "deepseek" in html
    assert "deepseek-v4-flash" in html
    assert "v0.2-s1-planner-8.1" in html
    assert "profile_s1_distortion" in html
    assert "1.0.0-demo" in html
    assert "demonstration" in html.casefold()
    assert "1%" in html
    assert "5%" in html

    uncertified = _report(planner_identity=_planner(certified=False, model="other-model"))
    html_uncertified = render_report_html(uncertified)
    assert "other-model" in html_uncertified
    assert "uncertified by Phase 4.3.1" in html_uncertified


def test_t263_preview_change_cannot_mutate_nested_result() -> None:
    snapshot = _completed_snapshot()
    assert snapshot.result is not None
    original_result_bytes = snapshot.result.model_dump_json().encode("utf-8")
    original_trace = snapshot.trace_events
    alt_preview = WaveformPreview(
        sample_rate_hz=48_000,
        original_num_samples=2_000,
        points=tuple(
            WaveformPoint(sample_index=index, time_s=index / 48_000, amplitude=0.1)
            for index in range(1_000)
        ),
    )
    mutated = snapshot.model_copy(update={"waveform_preview": alt_preview})
    first = build_diagnosis_report(snapshot, generated_at=GENERATED_AT)
    second = build_diagnosis_report(mutated, generated_at=GENERATED_AT)
    assert first.result == second.result
    assert first.result.model_dump_json().encode("utf-8") == original_result_bytes
    assert second.result.model_dump_json().encode("utf-8") == original_result_bytes
    assert first.trace_events == original_trace == second.trace_events
    assert first.result.diagnosis == second.result.diagnosis
    assert first.result.evidence == second.result.evidence
    assert first.result.rule_evaluation_batches == second.result.rule_evaluation_batches
    assert first.result.tool_history == second.result.tool_history
    assert len(second.waveform_preview.points) <= 1_000
    assert second.waveform_preview.label == "visualization_only"


def test_t279_packaged_summary_matches_official_bundle_and_script(
    tmp_path: Path,
) -> None:
    for name, digest in OFFICIAL_CHECKSUMS.items():
        payload = (OFFICIAL_BUNDLE / name).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(payload).hexdigest() == digest

    rebuilt = tmp_path / "phase4_3_1_official_summary.json"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    completed = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(rebuilt)],
        check=True,
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    committed = ASSET_PATH.read_bytes()
    assert rebuilt.read_bytes() == committed

    summary = load_accepted_evaluation_summary()
    assert summary.source_bundle_relative_path == (
        "docs/evaluations/phase4_3_1/official/bench_official_s1_v12_planner8_1_gate5"
    )
    assert summary.source_checksums_sha256 == OFFICIAL_CHECKSUMS
    assert summary.benchmark_id == "bench_official_s1_v12_planner8_1_gate5"
    assert summary.dataset_id == "s1-distortion-synthetic"
    assert summary.dataset_version == "1.2.0"
    assert summary.provider == "deepseek"
    assert summary.model == "deepseek-v4-flash"
    assert summary.prompt_version == "v0.2-s1-planner-8.1"
    assert summary.prompt_sha256 == (
        "f2f0a81cc8f36f0301ee67c43e692886e86f9aa9136adeea4d592707133423ca"
    )
    assert summary.rule_profile_id == "profile_s1_distortion"
    assert summary.rule_profile_version == "1.0.0-demo"
    assert summary.scoring_version == "2.0.0"
    assert summary.benchmark_status == "completed"
    assert summary.target_status == "meets_target"
    assert summary.agent_slot_count == 80
    assert summary.behavioral_failure_slot_count == 2
    assert summary.outcome_error_slot_count == 1
    assert summary.disclaimer == "demonstration_targets_not_standards_or_slas"

    official_metrics = json.loads((OFFICIAL_BUNDLE / "metrics.json").read_text(encoding="utf-8"))
    official_manifest = json.loads(
        (OFFICIAL_BUNDLE / "benchmark_manifest.json").read_text(encoding="utf-8")
    )
    assert summary.targets == TargetBands.model_validate(official_metrics["targets"])
    assert summary.agent_metrics == AggregateMetrics.model_validate(
        official_metrics["agent_metrics"]
    )
    assert summary.baseline_metrics == AggregateMetrics.model_validate(
        official_metrics["baseline_metrics"]
    )
    assert official_manifest["config"]["benchmark_id"] == summary.benchmark_id
    assert official_manifest["config"]["sdk_versions"]["signal_diag.scoring"] == "2.0.0"

    packaged = files("signal_diag.evaluation.assets").joinpath(
        "phase4_3_1_official_summary.json"
    ).read_bytes()
    assert packaged == committed
    assets_init = (
        PROJECT_ROOT / "src" / "signal_diag" / "evaluation" / "assets" / "__init__.py"
    ).read_text(encoding="utf-8")
    assert "signal_diag.app" not in assets_init
