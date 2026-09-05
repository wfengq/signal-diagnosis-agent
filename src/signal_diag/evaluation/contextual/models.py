"""Frozen models for the isolated contextual evaluation harness."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from signal_diag.agent.models import DiagnosisOutcome
from signal_diag.evaluation.models import CausalFault, RateMetric
from signal_diag.signal.context import StimulusContext

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


class ContextualRuntimeIdentity(BaseModel):
    """Sealed, non-secret identity required before live campaign execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: Literal["deepseek"]
    model: str = Field(min_length=1)
    base_url: str = Field(min_length=1)
    planner_class: Literal["RealLLMPlanner"]
    prompt_version: str = Field(min_length=1)
    prompt_sha256: str = Field(pattern=_SHA)
    causal_policy_version: str = Field(min_length=1)
    product_tree_sha256: str = Field(pattern=_SHA)


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


class ContextualBaselineRequest(BaseModel):
    """Truth-free input boundary for deterministic contextual execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(min_length=1)
    signal_id: str = Field(min_length=1)
    stimulus_context: StimulusContext

    @model_validator(mode="after")
    def _signal_matches_context(self) -> ContextualBaselineRequest:
        if self.signal_id != self.stimulus_context.test_signal_id:
            raise ValueError("signal_id must match stimulus_context.test_signal_id")
        return self


class ContextualExecutionInput(BaseModel):
    """Truth-free local inputs required to execute one validation case."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    case_id: str = Field(min_length=1)
    mode: DiagnosticMode
    test_wav_path: str = Field(min_length=1)
    reference_wav_path: str | None = None
    nominal_fundamental_hz: float | None = Field(default=None, gt=0.0)
    stimulus_kind: Literal["single_tone"] | None = None

    @model_validator(mode="after")
    def _validate_mode_inputs(self) -> ContextualExecutionInput:
        if self.mode == "paired_reference":
            if self.reference_wav_path is None:
                raise ValueError("paired_reference requires reference_wav_path")
            if self.nominal_fundamental_hz is not None or self.stimulus_kind is not None:
                raise ValueError("paired_reference rejects nominal stimulus fields")
        elif self.mode == "nominal_single_tone":
            if self.reference_wav_path is not None:
                raise ValueError("nominal_single_tone rejects reference_wav_path")
            if self.nominal_fundamental_hz is None:
                raise ValueError("nominal_single_tone requires nominal_fundamental_hz")
            if self.stimulus_kind != "single_tone":
                raise ValueError("nominal_single_tone requires stimulus_kind=single_tone")
        elif any(
            value is not None
            for value in (
                self.reference_wav_path,
                self.nominal_fundamental_hz,
                self.stimulus_kind,
            )
        ):
            raise ValueError("single_signal rejects reference and nominal fields")
        return self


class ContextualExecutionSlot(BaseModel):
    """One truth-free arm/case execution request."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    case_id: str = Field(min_length=1)
    arm: ArmKind
    mode: DiagnosticMode
    test_wav_path: str = Field(min_length=1)
    reference_wav_path: str | None = None
    nominal_fundamental_hz: float | None = Field(default=None, gt=0.0)
    stimulus_kind: Literal["single_tone"] | None = None


class ContextualExecutionPlan(BaseModel):
    """Frozen arm-major expansion of truth-free case inputs."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    cases: tuple[ContextualExecutionInput, ...]
    arm_order: tuple[ArmKind, ...] = (
        "contextual_agent",
        "fixed_pipeline",
        "no_context_ablation",
    )

    @model_validator(mode="after")
    def _validate_plan(self) -> ContextualExecutionPlan:
        if self.arm_order != (
            "contextual_agent",
            "fixed_pipeline",
            "no_context_ablation",
        ):
            raise ValueError("execution plan requires frozen arm-major order")
        case_ids = tuple(item.case_id for item in self.cases)
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("execution plan case IDs must be unique")
        return self

    @property
    def slots(self) -> tuple[ContextualExecutionSlot, ...]:
        slots: list[ContextualExecutionSlot] = []
        for arm in self.arm_order:
            for item in self.cases:
                ablation = arm == "no_context_ablation"
                slots.append(
                    ContextualExecutionSlot(
                        case_id=item.case_id,
                        arm=arm,
                        mode="single_signal" if ablation else item.mode,
                        test_wav_path=item.test_wav_path,
                        reference_wav_path=(
                            None if ablation else item.reference_wav_path
                        ),
                        nominal_fundamental_hz=(
                            None if ablation else item.nominal_fundamental_hz
                        ),
                        stimulus_kind=None if ablation else item.stimulus_kind,
                    )
                )
        return tuple(slots)


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
