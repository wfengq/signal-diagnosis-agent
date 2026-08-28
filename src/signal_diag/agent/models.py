"""Agent runtime models, decisions, observations, and run results."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from signal_diag.signal.models import SignalMeta
from signal_diag.tools.contracts import (
    ClippingInput,
    ClippingOutput,
    FundamentalInput,
    FundamentalOutput,
    HarmonicDistortionInput,
    HarmonicDistortionOutput,
    SpectrumInput,
    SpectrumOutput,
    ToolName,
)
from signal_diag.tools.evidence import Evidence
from signal_diag.tools.registry import ToolDescriptor

TaskType = Literal[
    "distortion_analysis",
    "unsupported",
]

DiagnosisOutcome = Literal[
    "supported_fault",
    "no_supported_fault",
    "inconclusive",
]

ConfidenceLabel = Literal[
    "low",
    "medium",
    "high",
]

TerminationReason = Literal[
    "planner_finished",
    "unsupported_task",
    "max_tool_calls",
    "max_planner_retries",
    "no_progress",
    "runtime_error",
]

RunStatus = Literal["success", "inconclusive", "error"]

ToolOutput = Annotated[
    ClippingOutput
    | SpectrumOutput
    | FundamentalOutput
    | HarmonicDistortionOutput,
    Field(discriminator="kind"),
]

ToolStatus = Literal["success", "invalid", "error"]


class AgentError(Exception):
    """Base Agent runtime exception."""


class PlannerError(AgentError):
    pass


class PlannerOutputError(PlannerError):
    pass


class ScriptExhaustedError(PlannerError):
    pass


class DiagnosisValidationError(AgentError):
    pass


class TaskAssessment(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_type: TaskType
    objective: str = Field(min_length=1)
    hypotheses: tuple[str, ...] = ()


class DetectClippingCall(BaseModel):
    model_config = ConfigDict(frozen=True)

    tool_name: Literal["detect_clipping"] = "detect_clipping"
    args: ClippingInput


class AnalyzeSpectrumCall(BaseModel):
    model_config = ConfigDict(frozen=True)

    tool_name: Literal["analyze_spectrum"] = "analyze_spectrum"
    args: SpectrumInput


class EstimateFundamentalCall(BaseModel):
    model_config = ConfigDict(frozen=True)

    tool_name: Literal["estimate_fundamental"] = "estimate_fundamental"
    args: FundamentalInput


class AnalyzeHarmonicDistortionCall(BaseModel):
    model_config = ConfigDict(frozen=True)

    tool_name: Literal["analyze_harmonic_distortion"] = "analyze_harmonic_distortion"
    args: HarmonicDistortionInput


ToolInvocation = Annotated[
    DetectClippingCall
    | AnalyzeSpectrumCall
    | EstimateFundamentalCall
    | AnalyzeHarmonicDistortionCall,
    Field(discriminator="tool_name"),
]


class DiagnosisClaim(BaseModel):
    model_config = ConfigDict(frozen=True)

    claim_id: str = Field(pattern=r"^claim_")
    fault_type: Literal[
        "clipping",
        "harmonic_distortion",
        "no_supported_fault",
        "inconclusive",
    ]
    statement: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = ()


class CallToolDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision_type: Literal["call_tool"] = "call_tool"
    task_assessment: TaskAssessment | None = None
    call: ToolInvocation
    purpose: str = Field(min_length=1)
    expected_evidence: tuple[str, ...] = ()


class FinishDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision_type: Literal["finish"] = "finish"
    task_assessment: TaskAssessment | None = None
    outcome: DiagnosisOutcome
    claims: tuple[DiagnosisClaim, ...]
    confidence_label: ConfidenceLabel
    limitations: tuple[str, ...] = ()


AgentDecision = Annotated[
    CallToolDecision | FinishDecision,
    Field(discriminator="decision_type"),
]


class Observation(BaseModel):
    model_config = ConfigDict(frozen=True)

    observation_id: str = Field(pattern=r"^obs_")
    call_id: str = Field(pattern=r"^call_")
    tool_name: ToolName
    normalized_arguments: dict[str, object]
    purpose: str
    status: ToolStatus
    result: ToolOutput | None = None
    evidence_refs: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    error_message: str | None = None


class ToolHistoryEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    call_id: str
    tool_name: ToolName
    normalized_arguments: dict[str, object]
    purpose: str
    status: ToolStatus


class PlannerContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str = Field(pattern=r"^run_")
    user_request: str = Field(min_length=1)
    signal_meta: SignalMeta
    task_assessment: TaskAssessment | None
    observations: tuple[Observation, ...]
    evidence: tuple[Evidence, ...]
    tool_history: tuple[ToolHistoryEntry, ...]
    available_tools: tuple[ToolDescriptor, ...]
    remaining_tool_calls: int = Field(ge=0)
    remaining_planner_retries: int = Field(ge=0)
    no_progress_count: int = Field(ge=0)
    warnings: tuple[str, ...] = ()
    recoverable_errors: tuple[str, ...] = ()


class StructuredDiagnosis(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    task_type: TaskType
    outcome: DiagnosisOutcome
    claims: tuple[DiagnosisClaim, ...]
    confidence_label: ConfidenceLabel
    limitations: tuple[str, ...]
    termination_reason: TerminationReason
    tool_call_count: int = Field(ge=0)


class AgentRunResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    status: RunStatus
    diagnosis: StructuredDiagnosis | None
    observations: tuple[Observation, ...]
    evidence: tuple[Evidence, ...]
    tool_history: tuple[ToolHistoryEntry, ...]
    termination_reason: TerminationReason
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
