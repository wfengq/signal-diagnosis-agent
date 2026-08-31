"""Local presentation application layer."""

from signal_diag.app.models import (
    AcceptedEvaluationSummary,
    AppErrorCode,
    AppErrorDetail,
    AppErrorEnvelope,
    AppRunSnapshot,
    AppRunStatus,
    DemoPresetDescriptor,
    DemoPresetId,
    DiagnosisReport,
    PlannerIdentity,
    RunSubmission,
    SourceSummary,
    TraceEventView,
    WaveformPoint,
    WaveformPreview,
)
from signal_diag.app.presets import build_demo_preset, list_demo_presets
from signal_diag.app.preview import build_waveform_preview
from signal_diag.app.reporting import (
    build_diagnosis_report,
    load_accepted_evaluation_summary,
    project_agent_events,
    render_report_html,
    render_report_json,
)

__all__ = [
    "AcceptedEvaluationSummary",
    "AppErrorCode",
    "AppErrorDetail",
    "AppErrorEnvelope",
    "AppRunSnapshot",
    "AppRunStatus",
    "DemoPresetDescriptor",
    "DemoPresetId",
    "DiagnosisReport",
    "PlannerIdentity",
    "RunSubmission",
    "SourceSummary",
    "TraceEventView",
    "WaveformPoint",
    "WaveformPreview",
    "build_demo_preset",
    "build_diagnosis_report",
    "build_waveform_preview",
    "list_demo_presets",
    "load_accepted_evaluation_summary",
    "project_agent_events",
    "render_report_html",
    "render_report_json",
]
