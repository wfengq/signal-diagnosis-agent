"""Study-owned DTOs for planner-ablation evaluation."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from signal_diag.agent.models import AgentRunResult
from signal_diag.evaluation.models import BaselineRunResult
from signal_diag.signal.context import StimulusContext

StudyMode = Literal["single_signal", "paired_reference"]
ScoredArm = Literal["product_agent", "fixed_pipeline"]
ExecutionIdentity = Literal["product_campaign", "harness_only"]


class ProductSlotRequest(BaseModel):
    """Truth-free product-slot execution request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(min_length=1)
    test_wav_bytes: bytes = Field(min_length=1)
    test_filename: str | None = None
    mode: StudyMode
    reference_wav_bytes: bytes | None = None
    reference_filename: str | None = None
    user_request: str = Field(min_length=1, max_length=2_000)

    @model_validator(mode="after")
    def _mode_shape(self) -> ProductSlotRequest:
        if self.mode == "single_signal":
            if self.reference_wav_bytes is not None or self.reference_filename is not None:
                raise ValueError("single_signal rejects reference WAV fields")
        elif self.reference_wav_bytes is None:
            raise ValueError("paired_reference requires reference WAV bytes")
        return self


class StudyContextGuidanceView(BaseModel):
    """Parity-facing guidance fields (not planner skill)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    reason_codes: tuple[str, ...] = Field(min_length=1)
    unlockable_modes: tuple[str, ...]
    required_inputs: dict[str, tuple[str, ...]]
    summary: str = Field(min_length=1)


class ProductSlotOutcome(BaseModel):
    """Mapped product-slot terminal without app composition in evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(min_length=1)
    mode: StudyMode
    arm: ScoredArm = "product_agent"
    terminal_status: Literal["completed", "failed"]
    result: AgentRunResult | None = None
    context_guidance: StudyContextGuidanceView | None = None
    planner_class: str = Field(min_length=1)
    execution_identity: ExecutionIdentity = "product_campaign"


class PlannerAblationBaselineRequest(BaseModel):
    """Truth-free fixed-pipeline request for the study baseline."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(min_length=1)
    signal_id: str = Field(min_length=1)
    stimulus_context: StimulusContext

    @model_validator(mode="after")
    def _signal_matches(self) -> PlannerAblationBaselineRequest:
        if self.signal_id != self.stimulus_context.test_signal_id:
            raise ValueError("signal_id must match stimulus_context.test_signal_id")
        mode = self.stimulus_context.mode
        if mode not in ("single_signal", "paired_reference"):
            raise ValueError("planner-ablation study supports single_signal and paired_reference only")
        return self


class FixedPipelineOutcome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    mode: StudyMode
    arm: Literal["fixed_pipeline"] = "fixed_pipeline"
    baseline_result: BaselineRunResult
    context_guidance: StudyContextGuidanceView | None = None
