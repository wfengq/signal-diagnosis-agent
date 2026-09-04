"""Frozen models for the isolated contextual evaluation harness."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from signal_diag.agent.models import DiagnosisOutcome
from signal_diag.evaluation.models import CausalFault, RateMetric

DiagnosticMode = Literal["single_signal", "nominal_single_tone", "paired_reference"]
ConfidenceTier = Literal[
    "strong_ground_truth",
    "reference_supported",
    "weak_observation",
    "unknown",
]
ContextualRole = Literal[
    "clean",
    "clipping",
    "harmonic",
    "combined",
    "natural_even_control",
    "invalid_comparison",
    "frequency_mismatch",
    "controlled_inconclusive",
    "domain_out_inconclusive",
]
ArmKind = Literal["contextual_agent", "fixed_pipeline", "no_context_ablation"]
SplitName = Literal["development", "validation"]

CONTEXTUAL_SCORING_ID: Literal["signal_diag.contextual_scoring"] = (
    "signal_diag.contextual_scoring"
)
CONTEXTUAL_SCORING_VERSION = "1.0.0-dev.1"

_SHA = r"^[0-9a-f]{64}$"


class ArmPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    arm: ArmKind
    mode: DiagnosticMode
    test_wav_sha256: str = Field(pattern=_SHA)
    reference_wav_sha256: str | None = Field(default=None, pattern=_SHA)


class ContextualCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    case_id: str = Field(min_length=1)
    split: SplitName
    mode: DiagnosticMode
    role: ContextualRole
    expected_outcome: DiagnosisOutcome
    expected_causal_set: tuple[CausalFault, ...] = ()
    confidence_tier: ConfidenceTier
    scoreable: bool
    source_id: str = Field(min_length=1)
    license_id: str = Field(min_length=1)
    parent_master_id: str = Field(min_length=1)
    recording_key: str = Field(min_length=1)
    transform_identity: str = Field(min_length=1)
    test_wav_sha256: str = Field(pattern=_SHA)
    reference_wav_sha256: str | None = Field(default=None, pattern=_SHA)
    arms: tuple[ArmPlan, ...]

    @model_validator(mode="after")
    def _validate_case(self) -> ContextualCase:
        if self.mode == "paired_reference" and self.reference_wav_sha256 is None:
            raise ValueError("paired_reference requires reference_wav_sha256")
        if self.mode != "paired_reference" and self.reference_wav_sha256 is not None:
            raise ValueError("non-paired modes reject reference_wav_sha256")
        if len(self.arms) != 3:
            raise ValueError("each case requires exactly three arm plans")
        kinds = tuple(arm.arm for arm in self.arms)
        if set(kinds) != {
            "contextual_agent",
            "fixed_pipeline",
            "no_context_ablation",
        }:
            raise ValueError("arms must cover all three evaluation arms exactly once")
        for arm in self.arms:
            if arm.test_wav_sha256 != self.test_wav_sha256:
                raise ValueError("arm test SHA must match case test SHA")
            if arm.arm == "no_context_ablation" and arm.mode != "single_signal":
                raise ValueError("no-context ablation must use single_signal mode")
            if arm.arm != "no_context_ablation" and arm.mode != self.mode:
                raise ValueError("non-ablation arms must use the case mode")
        if self.scoreable and self.confidence_tier in {"weak_observation", "unknown"}:
            raise ValueError("scoreable cases cannot use weak/unknown confidence")
        if not self.scoreable and self.confidence_tier not in {
            "weak_observation",
            "unknown",
        }:
            raise ValueError("unscored cases require weak_observation or unknown")
        return self


class PairedHarmonicSlot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    contextual: ArmPlan
    ablation: ArmPlan

    @model_validator(mode="after")
    def _same_test_sha(self) -> PairedHarmonicSlot:
        if self.contextual.test_wav_sha256 != self.ablation.test_wav_sha256:
            raise ValueError("ablation must reuse the contextual test SHA")
        return self


class ContextualManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    manifest_id: str = Field(min_length=1)
    split: SplitName
    scoring_id: Literal["signal_diag.contextual_scoring"] = CONTEXTUAL_SCORING_ID
    scoring_version: str = CONTEXTUAL_SCORING_VERSION
    cases: tuple[ContextualCase, ...]
    paired_harmonic_slots: tuple[PairedHarmonicSlot, ...] = ()


class ArmResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    arm: ArmKind
    status: Literal["ok", "infrastructure_failure"]
    predicted_outcome: DiagnosisOutcome | None = None
    predicted_causal_set: tuple[CausalFault, ...] = ()
    evidence_refs_complete: bool = False
    unnecessary_tool: bool = False
    infrastructure_failure: bool = False


class ContextualAggregate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    outcome_accuracy: RateMetric
    causal_exact_set_accuracy: RateMetric
    harmonic_precision: RateMetric | Literal["not_evaluated"]
    harmonic_recall: RateMetric | Literal["not_evaluated"]
    clipping_precision: RateMetric | Literal["not_evaluated"]
    clipping_recall: RateMetric | Literal["not_evaluated"]
    inconclusive_appropriateness: RateMetric
    natural_even_harmonic_fp: int
    unnecessary_tool_rate: RateMetric
    evidence_grounding: RateMetric
    unsupported_claim_rate: RateMetric
    ablation_correct_delta: int | None = None


class ContextualRunScore(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    scoring_id: Literal["signal_diag.contextual_scoring"] = CONTEXTUAL_SCORING_ID
    scoring_version: str = CONTEXTUAL_SCORING_VERSION
    arm: ArmKind
    aggregate: ContextualAggregate
    target_status: Literal["not_evaluated", "meets_target", "below_target"]
