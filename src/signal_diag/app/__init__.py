"""Local presentation application layer."""

from signal_diag.app.composition import build_product_service
from signal_diag.app.contextual_models import (
    ContextualAppRunSnapshot,
    ContextualDiagnosisReport,
    ContextualRunSubmission,
)
from signal_diag.app.contextual_reporting import (
    build_contextual_diagnosis_report,
    render_contextual_report_html,
    render_contextual_report_json,
)
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
from signal_diag.app.service import DiagnosisApplicationService

__all__ = [
    "AcceptedEvaluationSummary",
    "AppErrorCode",
    "AppErrorDetail",
    "AppErrorEnvelope",
    "AppRunSnapshot",
    "AppRunStatus",
    "ContextualAppRunSnapshot",
    "ContextualDiagnosisReport",
    "ContextualRunSubmission",
    "DemoPresetDescriptor",
    "DemoPresetId",
    "DiagnosisApplicationService",
    "DiagnosisReport",
    "PlannerIdentity",
    "RunSubmission",
    "SourceSummary",
    "TraceEventView",
    "WaveformPoint",
    "WaveformPreview",
    "build_contextual_diagnosis_report",
    "build_demo_preset",
    "build_diagnosis_report",
    "build_product_service",
    "build_waveform_preview",
    "list_demo_presets",
    "load_accepted_evaluation_summary",
    "project_agent_events",
    "render_contextual_report_html",
    "render_contextual_report_json",
    "render_report_html",
    "render_report_json",
]
