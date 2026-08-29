"""Immutable Phase 4 evaluation models."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    model_validator,
)

from signal_diag.agent.models import (
    AgentDecision,
    AgentRunResult,
    ConfidenceLabel,
    DiagnosisClaim,
    DiagnosisOutcome,
    Observation,
    PlannerContext,
    RunStatus,
    TerminationReason,
    ToolHistoryEntry,
)
from signal_diag.knowledge.models import KnowledgeRetrievalResult
from signal_diag.rules.models import RuleEvaluationBatch
from signal_diag.tools.contracts import ToolName
from signal_diag.tools.evidence import Evidence, EvidenceValidity

EvaluationSplit = Literal["development", "held_out"]
EvaluationCategory = Literal[
    "clean",
    "clipping",
    "harmonic",
    "combined",
    "invalid_noise",
]
CausalFault = Literal["clipping", "harmonic_distortion"]
DiagnosisClaimType = Literal[
    "clipping",
    "harmonic_distortion",
    "no_supported_fault",
    "inconclusive",
]
KnowledgePolicy = Literal["required", "optional", "not_needed"]
EvidenceComparator = Literal["eq", "neq", "lt", "lte", "gt", "gte"]
EvidenceScalar = StrictStr | StrictInt | StrictFloat | StrictBool

_CATEGORY_RULES: dict[
    EvaluationCategory,
    tuple[str, tuple[CausalFault, ...], tuple[DiagnosisOutcome, ...], KnowledgePolicy],
] = {
    "clean": ("sine", (), ("no_supported_fault",), "not_needed"),
    "clipping": ("clipped_sine", ("clipping",), ("supported_fault",), "optional"),
    "harmonic": (
        "harmonic_sine",
        ("harmonic_distortion",),
        ("supported_fault",),
        "optional",
    ),
    "combined": (
        "combined_distortion",
        ("clipping", "harmonic_distortion"),
        ("supported_fault",),
        "optional",
    ),
    "invalid_noise": ("white_noise", (), ("inconclusive",), "required"),
}


def _reject_duplicates(values: tuple[object, ...], label: str) -> None:
    seen: set[object] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"duplicate {label}: {value}")
        seen.add(value)


def _reject_empty(values: tuple[object, ...], label: str) -> None:
    if not values:
        raise ValueError(f"{label} must be non-empty")


def _require_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must be timezone-aware UTC")


class HarmonicRatioSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    order: int = Field(ge=2)
    ratio: float = Field(ge=0.0)


def _validate_harmonic_ratios(ratios: tuple[HarmonicRatioSpec, ...]) -> None:
    _reject_empty(ratios, "harmonic_ratios")
    _reject_duplicates(tuple(item.order for item in ratios), "harmonic order")
    if not any(item.ratio > 0.0 for item in ratios):
        raise ValueError("harmonic_ratios must contain at least one positive ratio")


class SineSignalSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    generator: Literal["sine"] = "sine"
    frequency_hz: float = Field(gt=0.0)
    sample_rate_hz: int = Field(default=48_000, gt=0)
    duration_s: float = Field(default=2.0, gt=0.0)
    amplitude: float = Field(default=0.5, gt=0.0, le=1.0)
    phase_rad: float = 0.0
    dc_offset: float = 0.0


class ClippedSineSignalSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    generator: Literal["clipped_sine"] = "clipped_sine"
    frequency_hz: float = Field(gt=0.0)
    clip_level: float = Field(gt=0.0, le=1.0)
    sample_rate_hz: int = Field(default=48_000, gt=0)
    duration_s: float = Field(default=2.0, gt=0.0)
    amplitude: float = Field(default=0.9, gt=0.0, le=1.0)


class HarmonicSineSignalSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    generator: Literal["harmonic_sine"] = "harmonic_sine"
    fundamental_hz: float = Field(gt=0.0)
    harmonic_ratios: tuple[HarmonicRatioSpec, ...]
    sample_rate_hz: int = Field(default=48_000, gt=0)
    duration_s: float = Field(default=2.0, gt=0.0)
    fundamental_amplitude: float = Field(default=0.5, gt=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate_ratios(self) -> HarmonicSineSignalSpec:
        _validate_harmonic_ratios(self.harmonic_ratios)
        return self


class CombinedDistortionSignalSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    generator: Literal["combined_distortion"] = "combined_distortion"
    fundamental_hz: float = Field(gt=0.0)
    harmonic_ratios: tuple[HarmonicRatioSpec, ...]
    clip_level: float = Field(gt=0.0, le=1.0)
    sample_rate_hz: int = Field(default=48_000, gt=0)
    duration_s: float = Field(default=2.0, gt=0.0)
    fundamental_amplitude: float = Field(default=0.9, gt=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate_ratios(self) -> CombinedDistortionSignalSpec:
        _validate_harmonic_ratios(self.harmonic_ratios)
        return self


class WhiteNoiseSignalSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    generator: Literal["white_noise"] = "white_noise"
    sample_rate_hz: int = Field(default=48_000, gt=0)
    duration_s: float = Field(default=2.0, gt=0.0)
    rms: float = Field(default=0.1, gt=0.0)
    seed: int = 0


SyntheticSignalSpec = Annotated[
    SineSignalSpec
    | ClippedSineSignalSpec
    | HarmonicSineSignalSpec
    | CombinedDistortionSignalSpec
    | WhiteNoiseSignalSpec,
    Field(discriminator="generator"),
]


class EvidenceCondition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    condition_id: str = Field(pattern=r"^cond_")
    tool_name: ToolName
    metric: str = Field(min_length=1)
    validity: EvidenceValidity
    comparator: EvidenceComparator
    expected_value: EvidenceScalar
    unit: str | None = None
    supports_claims: tuple[DiagnosisClaimType, ...] = ()

    @model_validator(mode="after")
    def _validate_claims(self) -> EvidenceCondition:
        _reject_duplicates(self.supports_claims, "supports_claims")
        return self


class SufficientEvidenceSet(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_set_id: str = Field(pattern=r"^evset_")
    condition_refs: tuple[str, ...]
    supported_claims: tuple[DiagnosisClaimType, ...]
    acceptable_outcomes: tuple[DiagnosisOutcome, ...]

    @model_validator(mode="after")
    def _validate_tuples(self) -> SufficientEvidenceSet:
        _reject_empty(self.condition_refs, "condition_refs")
        _reject_empty(self.supported_claims, "supported_claims")
        _reject_empty(self.acceptable_outcomes, "acceptable_outcomes")
        _reject_duplicates(self.condition_refs, "condition_ref")
        _reject_duplicates(self.supported_claims, "supported claim")
        _reject_duplicates(self.acceptable_outcomes, "acceptable outcome")
        return self


class CombinedIdentifiabilitySpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    signature_metric: str = Field(
        pattern=r"^harmonic_order_[2-9][0-9]*_relative_amplitude$"
    )
    minimum_absolute_separation: float = Field(gt=0.0)


class EvaluationCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(pattern=r"^case_")
    split: EvaluationSplit
    category: EvaluationCategory
    user_request: str = Field(min_length=1)
    signal: SyntheticSignalSpec
    causal_faults: tuple[CausalFault, ...] = ()
    observable_conditions: tuple[EvidenceCondition, ...]
    acceptable_first_tools: tuple[ToolName, ...]
    sufficient_evidence_sets: tuple[SufficientEvidenceSet, ...]
    knowledge_policy: KnowledgePolicy
    knowledge_tags: tuple[str, ...] = ()
    acceptable_outcomes: tuple[DiagnosisOutcome, ...]
    requires_limitation: bool = False
    tags: tuple[str, ...] = ()
    identifiability: CombinedIdentifiabilitySpec | None = None

    @model_validator(mode="after")
    def _validate_consistency(self) -> EvaluationCase:
        generator, faults, outcomes, policy = _CATEGORY_RULES[self.category]
        if self.signal.generator != generator:
            raise ValueError("signal generator does not match category")
        if self.causal_faults != faults:
            raise ValueError("causal_faults do not match category")
        if self.acceptable_outcomes != outcomes:
            raise ValueError("acceptable_outcomes do not match category")
        if self.knowledge_policy != policy:
            raise ValueError("knowledge_policy does not match category")
        if policy == "not_needed" and self.knowledge_tags:
            raise ValueError("knowledge_tags must be empty when policy is not_needed")
        if policy == "required" and not self.knowledge_tags:
            raise ValueError("knowledge_tags must be non-empty when policy is required")
        if self.category == "combined":
            if self.identifiability is None:
                raise ValueError("combined cases require identifiability")
        elif self.identifiability is not None:
            raise ValueError("identifiability is only allowed for combined cases")
        if self.category == "invalid_noise" and not self.requires_limitation:
            raise ValueError("invalid_noise cases require a limitation")
        condition_ids = tuple(
            condition.condition_id for condition in self.observable_conditions
        )
        _reject_duplicates(condition_ids, "condition_id")
        set_ids = tuple(
            evidence_set.evidence_set_id for evidence_set in self.sufficient_evidence_sets
        )
        _reject_duplicates(set_ids, "evidence_set_id")
        known = set(condition_ids)
        for evidence_set in self.sufficient_evidence_sets:
            for ref in evidence_set.condition_refs:
                if ref not in known:
                    raise ValueError(f"unresolved condition_ref: {ref}")
        return self


class DatasetManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    dataset_id: str = Field(min_length=1)
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    rule_profile_id: str = Field(pattern=r"^profile_")
    rule_profile_version: str = Field(min_length=1)
    cases: tuple[EvaluationCase, ...]

    @model_validator(mode="after")
    def _validate_identity(self) -> DatasetManifest:
        _reject_duplicates(tuple(case.case_id for case in self.cases), "case_id")
        return self


class DatasetValidationIssue(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str = Field(min_length=1)
    case_id: str | None = None
    message: str = Field(min_length=1)


class DatasetValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    dataset_id: str
    dataset_version: str
    valid: bool
    checked_case_ids: tuple[str, ...]
    issues: tuple[DatasetValidationIssue, ...] = ()

    @model_validator(mode="after")
    def _validate_valid_matches_issues(self) -> DatasetValidationReport:
        if self.valid != (len(self.issues) == 0):
            raise ValueError("valid is true exactly when issues is empty")
        return self


class ProviderUsage(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def _validate_token_sum(self) -> ProviderUsage:
        if (
            self.total_tokens is not None
            and self.input_tokens is not None
            and self.output_tokens is not None
            and self.total_tokens != self.input_tokens + self.output_tokens
        ):
            raise ValueError("total_tokens must equal input_tokens + output_tokens")
        return self


PlannerCallStatus = Literal[
    "decision",
    "planner_output_error",
    "planner_error",
    "provider_error",
]


class PlannerDecisionRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    record_id: str = Field(pattern=r"^decision_")
    decision_index: int = Field(ge=0)
    context: PlannerContext
    status: PlannerCallStatus
    decision: AgentDecision | None = None
    error_type: str | None = None
    error_message: str | None = None
    latency_ms: float | None = Field(default=None, ge=0.0)
    provider_usage: ProviderUsage | None = None

    @model_validator(mode="after")
    def _validate_status(self) -> PlannerDecisionRecord:
        if self.status == "decision":
            if self.decision is None:
                raise ValueError("decision status requires a decision")
            if self.error_type is not None or self.error_message is not None:
                raise ValueError("decision status forbids error fields")
        else:
            if self.decision is not None:
                raise ValueError("error status forbids a decision")
            if not self.error_type or not self.error_message:
                raise ValueError("error status requires error type and message")
        return self


class PlannerDecisionEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_type: Literal["planner_call"] = "planner_call"
    event_index: int = Field(ge=0)
    record: PlannerDecisionRecord


class ObservationEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_type: Literal["observation"] = "observation"
    event_index: int = Field(ge=0)
    caused_by_decision_index: int = Field(ge=0)
    observation: Observation
    evidence: tuple[Evidence, ...]


class RuleEvaluationEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_type: Literal["rule_evaluation"] = "rule_evaluation"
    event_index: int = Field(ge=0)
    caused_by_decision_index: int = Field(ge=0)
    batch: RuleEvaluationBatch


class KnowledgeRetrievalEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_type: Literal["knowledge_retrieval"] = "knowledge_retrieval"
    event_index: int = Field(ge=0)
    caused_by_decision_index: int = Field(ge=0)
    retrieval: KnowledgeRetrievalResult


EvaluationEvent = Annotated[
    PlannerDecisionEvent
    | ObservationEvent
    | RuleEvaluationEvent
    | KnowledgeRetrievalEvent,
    Field(discriminator="event_type"),
]

ExecutionPath = Literal["agent", "fixed_pipeline"]
ConfigScalar = str | int | float | bool | None
ConfigObject = dict[str, ConfigScalar | dict[str, ConfigScalar]]
ConfigValue = ConfigScalar | tuple[ConfigScalar, ...] | ConfigObject
BaselineCompletionReason = Literal[
    "baseline_completed",
    "insufficient_evidence",
    "runtime_error",
]
AttemptStatus = Literal[
    "behavior_result",
    "infrastructure_error",
    "configuration_error",
    "evaluator_error",
]
AttemptErrorCode = Literal[
    "timeout",
    "rate_limited",
    "provider_5xx",
    "provider_other",
    "authentication",
    "missing_credentials",
    "missing_dependency",
    "invalid_configuration",
    "trace_assembly",
    "scoring",
    "reporting",
]


class BenchmarkConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    benchmark_id: str = Field(pattern=r"^bench_")
    dataset_id: str
    dataset_version: str
    rule_profile_id: str = Field(pattern=r"^profile_")
    rule_profile_version: str
    provider: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    prompt_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    model_parameters: dict[str, ConfigValue] = Field(default_factory=dict)
    sdk_versions: dict[str, str] = Field(default_factory=dict)
    repetitions: int = Field(default=1, ge=1)
    max_infrastructure_retries: int = Field(default=2, ge=0)
    max_concurrency: int = Field(default=1, ge=1)
    started_at_utc: datetime

    @model_validator(mode="after")
    def _validate_config(self) -> BenchmarkConfig:
        _require_utc(self.started_at_utc, "started_at_utc")
        real_fields = (
            self.provider,
            self.model,
            self.prompt_version,
            self.prompt_sha256,
        )
        present = [field is not None for field in real_fields]
        if any(present) and not all(present):
            raise ValueError(
                "real-model configuration requires provider, model, "
                "prompt_version, and prompt_sha256 together"
            )
        return self


class AttemptRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    execution_path: ExecutionPath
    case_id: str = Field(pattern=r"^case_")
    run_slot: int = Field(ge=1)
    attempt_index: int = Field(ge=1)
    status: AttemptStatus
    error_code: AttemptErrorCode | None = None
    error_message: str | None = None
    started_at_utc: datetime
    finished_at_utc: datetime

    @model_validator(mode="after")
    def _validate_times(self) -> AttemptRecord:
        _require_utc(self.started_at_utc, "started_at_utc")
        _require_utc(self.finished_at_utc, "finished_at_utc")
        if self.finished_at_utc < self.started_at_utc:
            raise ValueError("finished_at_utc cannot precede started_at_utc")
        return self


class BaselineDiagnosis(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str = Field(pattern=r"^baseline_")
    task_type: Literal["distortion_analysis"] = "distortion_analysis"
    outcome: DiagnosisOutcome
    claims: tuple[DiagnosisClaim, ...]
    confidence_label: ConfidenceLabel
    limitations: tuple[str, ...] = ()
    tool_call_count: int = Field(ge=0)
    rule_evaluation_batches: tuple[RuleEvaluationBatch, ...]


class BaselineRunResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    result_type: Literal["fixed_pipeline"] = "fixed_pipeline"
    run_id: str = Field(pattern=r"^baseline_")
    status: RunStatus
    diagnosis: BaselineDiagnosis | None
    observations: tuple[Observation, ...]
    evidence: tuple[Evidence, ...]
    tool_history: tuple[ToolHistoryEntry, ...]
    completion_reason: BaselineCompletionReason
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    rule_evaluation_batches: tuple[RuleEvaluationBatch, ...]


class EvaluationTrace(BaseModel):
    model_config = ConfigDict(frozen=True)

    trace_id: str = Field(pattern=r"^trace_")
    case_id: str = Field(pattern=r"^case_")
    run_slot: int = Field(ge=1)
    execution_path: ExecutionPath
    config: BenchmarkConfig
    events: tuple[EvaluationEvent, ...]
    result: AgentRunResult | BaselineRunResult
    provider_usage: ProviderUsage | None = None


class RateMetric(BaseModel):
    model_config = ConfigDict(frozen=True)

    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)
    value: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate_value(self) -> RateMetric:
        if self.denominator == 0:
            if self.value != 0.0:
                raise ValueError("zero-denominator RateMetric value must be 0.0")
            return self
        if self.numerator > self.denominator:
            raise ValueError("numerator cannot exceed denominator")
        expected = self.numerator / self.denominator
        if self.value != expected:
            raise ValueError("RateMetric.value must equal numerator / denominator")
        return self


class RunScore(BaseModel):
    model_config = ConfigDict(frozen=True)

    trace_id: str = Field(pattern=r"^trace_")
    case_id: str = Field(pattern=r"^case_")
    run_slot: int = Field(ge=1)
    execution_path: ExecutionPath
    expected_faults: tuple[CausalFault, ...]
    predicted_faults: tuple[CausalFault, ...]
    acceptable_outcomes: tuple[DiagnosisOutcome, ...]
    predicted_outcome: DiagnosisOutcome | None
    causal_exact_set_correct: bool
    outcome_correct: bool
    grounded_claims: int = Field(ge=0)
    scored_claims: int = Field(ge=0)
    unsupported_fault_claims: int = Field(ge=0)
    predicted_fault_claims: int = Field(ge=0)
    first_tool_correct: bool | None = None
    appropriate_replans: int = Field(ge=0)
    replan_opportunities: int = Field(ge=0)
    unnecessary_tool_actions: int = Field(ge=0)
    tool_actions: int = Field(ge=0)
    timely_stop: bool | None = None
    correct_rule_actions: int = Field(ge=0)
    rule_action_opportunities: int = Field(ge=0)
    required_knowledge_actions: int = Field(ge=0)
    required_knowledge_opportunities: int = Field(ge=0)
    unnecessary_knowledge_actions: int = Field(ge=0)
    knowledge_actions: int = Field(ge=0)
    cited_knowledge_actions: int = Field(ge=0)
    planner_calls: int = Field(ge=0)
    end_to_end_latency_ms: float | None = Field(default=None, ge=0.0)
    provider_usage: ProviderUsage | None = None
    completion_reason: TerminationReason | BaselineCompletionReason
    failure_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate_count_bounds(self) -> RunScore:
        pairs = (
            (self.grounded_claims, self.scored_claims, "grounded_claims"),
            (
                self.unsupported_fault_claims,
                self.predicted_fault_claims,
                "unsupported_fault_claims",
            ),
            (self.appropriate_replans, self.replan_opportunities, "appropriate_replans"),
            (
                self.unnecessary_tool_actions,
                self.tool_actions,
                "unnecessary_tool_actions",
            ),
            (
                self.correct_rule_actions,
                self.rule_action_opportunities,
                "correct_rule_actions",
            ),
            (
                self.required_knowledge_actions,
                self.required_knowledge_opportunities,
                "required_knowledge_actions",
            ),
            (
                self.unnecessary_knowledge_actions,
                self.knowledge_actions,
                "unnecessary_knowledge_actions",
            ),
            (
                self.cited_knowledge_actions,
                self.knowledge_actions,
                "cited_knowledge_actions",
            ),
        )
        for numerator, denominator, name in pairs:
            if numerator > denominator:
                raise ValueError(f"{name} cannot exceed its denominator")
        return self


class AggregateMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_count: int = Field(ge=0)
    causal_exact_set_accuracy: RateMetric
    causal_macro_f1: float = Field(ge=0.0, le=1.0)
    outcome_accuracy: RateMetric
    evidence_grounding_rate: RateMetric
    unsupported_claim_rate: RateMetric
    first_tool_selection_rate: RateMetric
    observation_driven_replan_rate: RateMetric
    unnecessary_tool_action_rate: RateMetric
    timely_stopping_rate: RateMetric
    applicable_rule_usage_rate: RateMetric
    required_knowledge_usage_rate: RateMetric
    unnecessary_knowledge_retrieval_rate: RateMetric
    knowledge_citation_utilization_rate: RateMetric
    average_tool_actions: float = Field(ge=0.0)
    average_planner_calls: float | None = Field(default=None, ge=0.0)
    latency_ms_mean: float | None = Field(default=None, ge=0.0)
    latency_ms_p50: float | None = Field(default=None, ge=0.0)
    latency_ms_p95: float | None = Field(default=None, ge=0.0)
    provider_usage_coverage_rate: RateMetric
    observed_input_tokens: int | None = Field(default=None, ge=0)
    observed_output_tokens: int | None = Field(default=None, ge=0)
    observed_total_tokens: int | None = Field(default=None, ge=0)
    observed_cost_usd: float | None = Field(default=None, ge=0.0)


class TargetBands(BaseModel):
    model_config = ConfigDict(frozen=True)

    causal_macro_f1_min: float = 0.80
    first_tool_selection_min: float = 0.80
    observation_driven_replan_min: float = 0.80
    evidence_grounding_min: float = 1.00
    unsupported_claim_rate_max: float = 0.05
    unnecessary_tool_action_rate_max: float = 0.20
    timely_stopping_min: float = 0.80
    applicable_rule_usage_min: float = 0.80
    required_knowledge_usage_min: float = 0.80
    knowledge_citation_utilization_min: float = 1.00
    unnecessary_knowledge_retrieval_rate_max: float = 0.20


BenchmarkStatus = Literal["pending", "incomplete", "completed"]
TargetStatus = Literal["not_evaluated", "meets_target", "below_target"]
HarnessStatus = Literal["pending", "accepted"]


class BenchmarkReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    config: BenchmarkConfig
    config_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest: DatasetManifest
    harness_status: HarnessStatus
    benchmark_status: BenchmarkStatus
    target_status: TargetStatus
    targets: TargetBands
    agent_metrics: AggregateMetrics | None
    baseline_metrics: AggregateMetrics | None
    scores: tuple[RunScore, ...]
    traces: tuple[EvaluationTrace, ...]
    attempts: tuple[AttemptRecord, ...]
    warnings: tuple[str, ...] = ()


class ScoredRunArtifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    record_type: Literal["scored_run"] = "scored_run"
    trace: EvaluationTrace
    score: RunScore
    attempts: tuple[AttemptRecord, ...]


class UnscoredSlotArtifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    record_type: Literal["unscored_slot"] = "unscored_slot"
    execution_path: ExecutionPath
    case_id: str = Field(pattern=r"^case_")
    run_slot: int = Field(ge=1)
    attempts: tuple[AttemptRecord, ...]


RunArtifact = Annotated[
    ScoredRunArtifact | UnscoredSlotArtifact,
    Field(discriminator="record_type"),
]
