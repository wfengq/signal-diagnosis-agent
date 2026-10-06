"""Case and arm records for study_s1_agent_increment_1."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Family = Literal["T1", "T2"]
Split = Literal["dev", "heldout"]
ArmName = Literal["agent", "strong_fixed", "weak_fixed"]
Conclusion = Literal["clipping", "harmonic_distortion", "no_supported_fault", "inconclusive"]


class FaultSpan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    start_s: float = Field(ge=0.0)
    end_s: float = Field(gt=0.0)
    channel: Literal["left", "right", "mixdown"]


class CaseTruth(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    conclusion: Conclusion
    cause_set: tuple[str, ...] = ()
    mode: Literal["single_signal", "paired_reference", "nominal_single_tone"]
    nominal_fundamental_hz: float | None = None
    reference_file: str | None = None
    stimulus_kind: Literal["single_tone"] | None = None
    fault_spans: tuple[FaultSpan, ...] = ()
    insufficient: bool = False


class IncrementCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(min_length=1)
    family: Family
    split: Split
    text: str = Field(min_length=1)
    files: tuple[str, ...] = Field(min_length=1)
    test_file: str
    truth: CaseTruth
    favors_baseline: bool = False
    no_fault: bool = False


class ArmOutcome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    family: Family
    arm: ArmName
    conclusion_correct: bool
    unsupported_positive: bool
    evidence_traceable: bool
    context_fields_correct: int = 0
    context_fields_graded: int = 0
    correction_count: int = 0
    localization_correct: bool | None = None
    tool_calls: int = 0
