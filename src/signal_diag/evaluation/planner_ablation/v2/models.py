"""Frozen study-owned DTOs for planner-ablation protocol revision (dev_2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from signal_diag.agent.models import (
    DiagnosisClaim,
    DiagnosisOutcome,
    Observation,
    TaskAssessment,
    ToolHistoryEntry,
)
from signal_diag.evaluation.planner_ablation.models import StudyContextGuidanceView
from signal_diag.rules.models import RuleEvaluationBatch
from signal_diag.signal.context import StimulusContext
from signal_diag.tools.evidence import Evidence

StudyMode = Literal["single_signal", "paired_reference"]
ScoredArm = Literal["product_agent", "fixed_pipeline"]
OracleOutcome = Literal["supported_fault", "no_supported_fault", "inconclusive"]
ChannelPolicy = Literal["mixdown"]
SegmentPolicy = Literal["full_signal"]
PrimaryEndpoint = Literal["quality"]
TimingContract = Literal["encoded_bytes_to_terminal_v1"]
ReviewStatus = Literal["pending", "approved", "rejected"]
TerminalStatus = Literal["completed", "failed"]
FailureCauseKind = Literal[
    "behavioral",
    "decode_failure",
    "deadline_exceeded",
    "infrastructure",
    "unknown",
]
ExecutionIdentity = Literal["product_campaign", "harness_only"]
PhaseName = Literal["decode", "execution", "guidance"]

STUDY_ID_V2 = "study_s1_planner_ablation_dev_2"
SCORING_IDENTITY_V2 = "signal_diag.planner_ablation_scoring"
SCORING_VERSION_V2 = "2.0.0-dev.1"
DEFAULT_STUDY_QUESTION = "Diagnose supported S1 distortion conservatively."
TIMING_CONTRACT_V1: TimingContract = "encoded_bytes_to_terminal_v1"
REQUIRED_PHASES: tuple[PhaseName, ...] = ("decode", "execution", "guidance")


class ByteRequest(BaseModel):
    """Truth-free execution request. Offline labels never appear here."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: StudyMode
    test_wav_bytes: bytes = Field(min_length=1)
    reference_wav_bytes: bytes | None = None
    channel: ChannelPolicy = "mixdown"
    segment_policy: SegmentPolicy = "full_signal"
    question: str = Field(min_length=1, max_length=2_000)

    @model_validator(mode="after")
    def _mode_shape(self) -> ByteRequest:
        if self.mode == "single_signal":
            if self.reference_wav_bytes is not None:
                raise ValueError("single_signal rejects a supplied reference")
        elif self.reference_wav_bytes is None:
            raise ValueError("paired_reference requires reference WAV bytes")
        return self


class OracleLabel(BaseModel):
    """Mode-specific offline oracle. Exact causal set for supported faults."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    outcome: OracleOutcome
    exact_causal_faults: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _faults_match_outcome(self) -> OracleLabel:
        faults = tuple(self.exact_causal_faults)
        if self.outcome == "supported_fault":
            if not faults:
                raise ValueError("supported_fault requires a non-empty exact causal set")
        elif faults:
            raise ValueError(f"{self.outcome} requires an empty exact causal set")
        return self

    def fingerprint(self) -> tuple[str, tuple[str, ...]]:
        return (self.outcome, tuple(self.exact_causal_faults))


class LabelReviewRecord(BaseModel):
    """Offline review provenance. Never fabricate approval."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: ReviewStatus = "pending"
    reviewer: str | None = None
    reviewed_at: str | None = None
    notes: str | None = None
    prior_output_exposure_disclosed: bool = True


class ScenarioDefinition(BaseModel):
    """Offline-only scenario metadata, oracles, and U/C/G construction labels."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    parent_master_id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    license_id: str = Field(min_length=1)
    test_wav_relpath: str = Field(min_length=1)
    test_wav_sha256: str = Field(min_length=64, max_length=64)
    reference_wav_relpath: str = Field(min_length=1)
    reference_wav_sha256: str = Field(min_length=64, max_length=64)
    single_oracle: OracleLabel
    paired_oracle: OracleLabel
    rationale: str = Field(min_length=1)
    review_record: LabelReviewRecord = Field(default_factory=LabelReviewRecord)
    upgrade_target: str | None = None
    in_upgrade_population: bool = False
    context_obtainable: bool = False
    context_valid: bool = False
    context_sufficient: bool = False
    in_guidance_population: bool = False

    @property
    def in_conditional_population(self) -> bool:
        return (
            self.in_upgrade_population
            and self.context_obtainable
            and self.context_valid
            and self.context_sufficient
        )


class SlotKey(BaseModel):
    """One scheduled arm execution of a unique request in one round."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    request_key: str = Field(min_length=64, max_length=64)
    arm: ScoredArm
    round_index: int = Field(ge=0)


class CanonicalRequest(BaseModel):
    """One unique scored analysis request with representative scenario ownership."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    request_key: str = Field(min_length=64, max_length=64)
    mode: StudyMode
    representative_scenario_id: str = Field(min_length=1)
    byte_request: ByteRequest


class Schedule(BaseModel):
    """Frozen unique-request schedule, aliases, and expanded ordered slots."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    canonical_requests: tuple[CanonicalRequest, ...]
    scenario_aliases: dict[str, str]
    slots: tuple[SlotKey, ...]
    schedule_digest: str = Field(min_length=64, max_length=64)


class LabelReviewResult(BaseModel):
    """Label-review outcome. Never fabricates approval."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    errors: tuple[str, ...] = ()
    review_status: str = "pending"
    approved: bool = False
    review_provenance: tuple[str, ...] = ()
    upgrade_population: frozenset[str] = Field(default_factory=frozenset)
    conditional_population: frozenset[str] = Field(default_factory=frozenset)
    guidance_population: frozenset[str] = Field(default_factory=frozenset)


class StudyProtocolV2(BaseModel):
    """Exact v2 protocol identities and decision/timing bands (awaiting seal)."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    study_id: Literal["study_s1_planner_ablation_dev_2"] = "study_s1_planner_ablation_dev_2"
    scoring_identity: Literal["signal_diag.planner_ablation_scoring"] = (
        "signal_diag.planner_ablation_scoring"
    )
    scoring_version: Literal["2.0.0-dev.1"] = "2.0.0-dev.1"
    rounds: Literal[3] = 3
    deadline_s: float = Field(default=120.0, gt=0.0)
    timing_contract: TimingContract = "encoded_bytes_to_terminal_v1"
    quality_loss_tolerance: float = Field(default=0.0, ge=0.0)
    material_improvement_ratio: float = Field(default=0.20, gt=0.0, lt=1.0)
    material_absolute_saving_s: float = Field(default=0.100, gt=0.0)
    primary_endpoint: PrimaryEndpoint = "quality"
    runtime_limits: dict[str, object] | None = None
    binding_references: tuple[str, ...] = ()


class PhaseMarker(BaseModel):
    """Observable phase boundary within the common request interval."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    phase: PhaseName
    started_at: float
    ended_at: float

    @model_validator(mode="after")
    def _ordered(self) -> PhaseMarker:
        if not (self.ended_at >= self.started_at):
            raise ValueError("phase marker end must be at or after start")
        return self


class RequestTiming(BaseModel):
    """Outer encoded-bytes-to-terminal timing under the v1 contract."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    timing_contract: TimingContract = "encoded_bytes_to_terminal_v1"
    request_start: float
    terminal_result_ready: float
    elapsed_s: float
    phase_markers: tuple[PhaseMarker, ...] = ()
    residual_overhead_notes: tuple[str, ...] = ()


class FailureCause(BaseModel):
    """Typed terminal failure cause (behavioral vs infrastructure family)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: FailureCauseKind
    detail: str | None = None


class ExecutionProvenance(BaseModel):
    """Actual planner/provider mode from construction/execution — never arm labels."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    planner_class: str = Field(min_length=1)
    execution_identity: ExecutionIdentity
    provider_client_bound: bool = False
    offline_session: bool = True


class StudyTerminal(BaseModel):
    """Common arm-neutral terminal view for measured study slots."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(min_length=1)
    arm: ScoredArm
    mode: StudyMode
    status: TerminalStatus
    failure_cause: FailureCause | None = None
    outcome: DiagnosisOutcome | None = None
    claims: tuple[DiagnosisClaim, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    rule_evaluation_batches: tuple[RuleEvaluationBatch, ...] = ()
    task_assessment: TaskAssessment | None = None
    stimulus_context: StimulusContext | None = None
    guidance: StudyContextGuidanceView | None = None
    observations: tuple[Observation, ...] = ()
    tool_history: tuple[ToolHistoryEntry, ...] = ()
    provenance: ExecutionProvenance
    timing: RequestTiming | None = None
    slot_key: SlotKey | None = None
    request_key: str | None = None
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _status_shape(self) -> StudyTerminal:
        if self.status == "completed" and self.failure_cause is not None:
            raise ValueError("completed terminal rejects failure_cause")
        if self.status == "failed" and self.failure_cause is None:
            raise ValueError("failed terminal requires failure_cause")
        return self


# --- Task 4: metrics, prerequisites, decision (study-only) ---

PINNED_CAUSAL_POLICY_V2 = "v9_11_mode_aware_no_fault_recovery"
MachineConclusion = Literal[
    "planner_advantage",
    "fixed_pipeline_dominance",
    "insufficient_evidence",
]
VerifiedConstructionPath = Literal[
    "synthetic_test_stub",
    "verify_manifest",
    "legacy_fixture_seal",
]


class OptionalRate(BaseModel):
    """Rate with explicit not-evaluable state (never fabricate 1.0)."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)
    value: float | None = None
    evaluable: bool = False

    @model_validator(mode="after")
    def _consistent(self) -> OptionalRate:
        if self.denominator == 0:
            if self.evaluable:
                raise ValueError("zero denominator cannot be evaluable")
            if self.value is not None:
                raise ValueError("not-evaluable rate must have value=None")
            return self
        expected = self.numerator / self.denominator
        if self.value != expected:
            raise ValueError("OptionalRate.value must equal numerator/denominator")
        if not self.evaluable:
            raise ValueError("nonzero denominator must be marked evaluable")
        return self


class LatencyStats(BaseModel):
    """Shared-boundary latency including behavioral failure time."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    count: int = Field(ge=0)
    mean_s: float | None = None
    median_s: float | None = None
    p95_s: float | None = None
    max_s: float | None = None


class ArmModeRoundCell(BaseModel):
    """Authoritative per-arm/mode/round metric cell."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    arm: ScoredArm
    mode: StudyMode
    round_index: int = Field(ge=0)
    scheduled_denominator: int = Field(ge=0)
    quality: OptionalRate
    outcome_accuracy: OptionalRate
    usefulness: OptionalRate
    completion: OptionalRate
    unsupported_positive_claims: OptionalRate
    grounding: OptionalRate
    positive_claim_count: int = Field(ge=0)
    claim_data_complete: bool
    safety_ok: bool
    latency: LatencyStats
    tool_action_count: int = Field(ge=0)
    mean_tool_actions: float | None = None
    quality_correct_keys: frozenset[str] = Field(default_factory=frozenset)


class UpgradeCell(BaseModel):
    """Round-level upgrade endpoints (cross-mode; fixed U/C labels)."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    arm: ScoredArm
    round_index: int = Field(ge=0)
    u_size: int = Field(ge=0)
    c_size: int = Field(ge=0)
    s_count: int = Field(ge=0)
    s_over_u: OptionalRate
    s_over_c: OptionalRate
    invalid_reference_abstention_correct: bool | None = None
    incremental_gain_count: int = Field(ge=0)
    already_met_not_incremental_count: int = Field(ge=0)


class GuidanceCell(BaseModel):
    """Round-level guidance endpoints over fixed G population."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    arm: ScoredArm
    round_index: int = Field(ge=0)
    g_size: int = Field(ge=0)
    emitted_count: int = Field(ge=0)
    emitted_and_correct: OptionalRate
    conditional_template_ok: OptionalRate


class ArmModeTotals(BaseModel):
    """Across-round totals for one arm/mode (never 114 as a per-arm denom)."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    arm: ScoredArm
    mode: StudyMode
    scheduled_denominator: int = Field(ge=0)
    quality: OptionalRate
    usefulness: OptionalRate
    completion: OptionalRate


class DescriptiveAcrossRoundSummary(BaseModel):
    """Equal mode-weighting descriptive aggregate only; not authoritative."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    arm: ScoredArm
    equal_mode_quality: float | None = None
    equal_mode_usefulness: float | None = None
    equal_mode_completion: float | None = None
    notes: str = "descriptive_only_equal_mode_weighting"


class MetricTables(BaseModel):
    """Derived metric tables. Callers cannot inject safety/matching booleans."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    cells: tuple[ArmModeRoundCell, ...]
    upgrade_cells: tuple[UpgradeCell, ...]
    guidance_cells: tuple[GuidanceCell, ...]
    arm_mode_totals: tuple[ArmModeTotals, ...]
    descriptive_summaries: tuple[DescriptiveAcrossRoundSummary, ...] = ()
    descriptive_record_count: int = Field(ge=0)
    scheduled_slot_count: int = Field(ge=0)
    campaign_records_complete: bool
    partial_campaign: bool


class PrerequisiteReport(BaseModel):
    """Independently derived prerequisites; fail closed with reason codes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    identity_ok: bool
    timing_ok: bool
    oracle_ok: bool
    report_parity_ok: bool
    matching_ok: bool
    campaign_complete: bool
    product_safety_ok: bool
    fixed_safety_ok: bool
    positive_claims_evaluable: bool
    pinned_gate_identity_ok: bool
    resource_observation_ok: bool | None = None
    reason_codes: tuple[str, ...] = ()
    all_passed: bool


class DecisionResult(BaseModel):
    """Machine candidate distinct from human review and product authority."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    machine_candidate: MachineConclusion
    eligible_conclusion: MachineConclusion
    reason_codes: tuple[str, ...] = ()
    review_status: Literal["pending"] = "pending"


class VerifiedStudyV2(BaseModel):
    """Protocol/schedule/labels bound to verified identity.

    Production construction is ``verify_manifest`` (Task 6). Task 4 tests may
    use ``build_synthetic_verified_study_v2_for_tests`` only.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    protocol: StudyProtocolV2
    schedule: Schedule
    scenarios: tuple[ScenarioDefinition, ...]
    label_review: LabelReviewResult
    verified_identity: str = Field(min_length=64, max_length=64)
    input_identity: str = Field(min_length=64, max_length=64)
    code_identity: str = Field(min_length=64, max_length=64)
    construction_path: VerifiedConstructionPath
    pinned_causal_policy: Literal["v9_11_mode_aware_no_fault_recovery"] = (
        "v9_11_mode_aware_no_fault_recovery"
    )
    resource_policy: str | None = None
    resource_extension: dict[str, object] | None = None


# --- Task 5: campaign execution, limits, resource telemetry (study-only) ---

PRODUCT_SLOT_COUNT_V2: Literal[57] = 57
SlotAttemptStatus = Literal["unstarted", "attempted", "completed", "failed"]
CampaignStatus = Literal[
    "completed",
    "infrastructure_stopped",
    "blocked",
    "resource_stopped",
]
ExecutionMode = Literal["offline", "online"]
AUDITED_AGENT_LIMIT_DEFAULTS: dict[str, int] = {
    "max_tool_calls": 8,
    "max_planner_retries": 2,
    "max_no_progress": 2,
    "max_rule_evaluations": 4,
    "max_knowledge_retrievals": 4,
}


class ResourceTelemetry(BaseModel):
    """Study-owned resource observation. Unknown fields are explicit, never invented."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    planner_call_count: int | None = None
    tool_call_count: int | None = None
    rule_evaluation_count: int | None = None
    repair_attempt_count: int | None = None
    transport_attempt_count: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    unknown_fields: tuple[str, ...] = ()
    credentials_redacted: bool = True
    raw_waveform_persisted: bool = False
    raw_fft_persisted: bool = False


class EffectiveConfiguration(BaseModel):
    """Pinned product-path limits snapshot for budget preflight (study-only)."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    max_tool_calls: int | None = None
    max_planner_retries: int | None = None
    max_no_progress: int | None = None
    max_rule_evaluations: int | None = None
    max_knowledge_retrievals: int | None = None
    temperature: float | None = None
    thinking_disabled: bool | None = None
    max_tokens_explicit: bool = False
    max_tokens: int | None = None
    request_timeout_explicit: bool = False
    request_timeout_s: float | None = None
    transport_retry_override_explicit: bool = False
    transport_retry_override: int | None = None
    transport_attempts_per_call_bound: int | None = None
    planner_calls_per_slot_bound: int | None = None
    input_token_bound_per_call: int | None = None
    output_token_bound_per_call: int | None = None
    retry_telemetry_available: bool = False
    provider_sdk_version: str | None = None
    notes: tuple[str, ...] = ()


class BudgetAssessment(BaseModel):
    """Worst-case budget and explicit blockers. Unknown limits never silently pass."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    product_slot_count: Literal[57] = 57
    planner_calls_per_slot_bound: int | None = None
    transport_attempts_per_call_bound: int | None = None
    worst_case_requests: int | None = None
    worst_case_input_tokens: int | None = None
    worst_case_output_tokens: int | None = None
    audited_agent_limits: dict[str, int | None]
    temperature: float | None = None
    thinking_disabled: bool | None = None
    blockers: tuple[str, ...] = ()
    execution_blocked: bool
    seal_ready: bool = False


class SlotAttemptRecord(BaseModel):
    """One schedule slot attempt against the unchanged full schedule."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    slot_key: SlotKey
    status: SlotAttemptStatus
    attempt_count: int = Field(ge=0, le=1)
    terminal: StudyTerminal | None = None
    resource_telemetry: ResourceTelemetry | None = None
    resource_ledger: dict[str, object] | None = None
    resource_observation: dict[str, object] | None = None
    resource_stop_reason: str | None = None
    teardown_duration_s: float | None = None
    teardown_error: str | None = None
    drain_failed: bool = False
    stop_campaign: bool = False

    @model_validator(mode="after")
    def _attempt_shape(self) -> SlotAttemptRecord:
        if self.status == "unstarted":
            if self.attempt_count != 0:
                raise ValueError("unstarted slots must have attempt_count=0")
            if self.terminal is not None:
                raise ValueError("unstarted slots reject terminals")
        else:
            if self.attempt_count != 1:
                raise ValueError("attempted/completed/failed slots require attempt_count=1")
        return self


class CampaignRecord(BaseModel):
    """Full-schedule campaign ledger. Truncation never yields an accepted conclusion."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    study_id: Literal["study_s1_planner_ablation_dev_2"] = "study_s1_planner_ablation_dev_2"
    schedule_digest: str = Field(min_length=64, max_length=64)
    execution_mode: ExecutionMode
    status: CampaignStatus
    slot_records: tuple[SlotAttemptRecord, ...]
    planned_slot_count: int = Field(ge=0)
    attempted_slot_count: int = Field(ge=0)
    completed_slot_count: int = Field(ge=0)
    failed_slot_count: int = Field(ge=0)
    unstarted_slot_count: int = Field(ge=0)
    stopped_after: SlotKey | None = None
    accepted_conclusion_available: bool = False
    budget_assessment: BudgetAssessment | None = None
    resource_policy: str | None = None
    schedule_order_preserved: bool = True
    campaign_retry_policy: Literal["forbidden"] = "forbidden"
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _counts(self) -> CampaignRecord:
        if len(self.slot_records) != self.planned_slot_count:
            raise ValueError("slot_records must cover the full planned schedule")
        if self.status != "completed" and self.accepted_conclusion_available:
            raise ValueError("truncated campaigns cannot accept a conclusion")
        if self.status == "completed" and self.unstarted_slot_count != 0:
            raise ValueError("completed campaigns cannot leave unstarted slots")
        return self


# --- Task 6: protocol sealing / verified-input construction (study-only) ---

SLOT_COUNT_V2: Literal[114] = 114


class SealedCanonicalRequest(BaseModel):
    """Truth-free request identity without embedding waveform bytes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    request_key: str = Field(min_length=64, max_length=64)
    mode: StudyMode
    representative_scenario_id: str = Field(min_length=1)
    test_wav_sha256: str = Field(min_length=64, max_length=64)
    reference_wav_sha256: str | None = None
    question: str = Field(min_length=1, max_length=2_000)
    channel: ChannelPolicy = "mixdown"
    segment_policy: SegmentPolicy = "full_signal"


class CodeBindingsV2(BaseModel):
    """Immutable implementation identity distinct from a later seal-artifact commit."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    implementation_commit: str = Field(min_length=40, max_length=40)
    aggregate_code_identity: str = Field(min_length=64, max_length=64)
    bound_file_digests: dict[str, str]
    entry_script_digests: dict[str, str]
    prompt_module_digest: str = Field(min_length=64, max_length=64)
    prompt_version: str = Field(min_length=1)
    profile_digests: dict[str, str]
    corpus_digests: dict[str, str]
    dependency_versions: dict[str, str]
    python_version: str = Field(min_length=1)


class EnvironmentBindingV2(BaseModel):
    """Environment measurement policy recorded at candidate construction."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    platform: str = Field(min_length=1)
    measurement_policy: str = Field(min_length=1)
    notes: tuple[str, ...] = ()


class CandidateManifestV2(BaseModel):
    """Seal-ready (or blocked) candidate binding for study_s1_planner_ablation_dev_2."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    study_id: Literal["study_s1_planner_ablation_dev_2"] = (
        "study_s1_planner_ablation_dev_2"
    )
    scoring_identity: Literal["signal_diag.planner_ablation_scoring"] = (
        "signal_diag.planner_ablation_scoring"
    )
    scoring_version: Literal["2.0.0-dev.1"] = "2.0.0-dev.1"
    protocol: StudyProtocolV2
    scenarios: tuple[ScenarioDefinition, ...]
    schedule_digest: str = Field(min_length=64, max_length=64)
    scenario_aliases: dict[str, str]
    sealed_requests: tuple[SealedCanonicalRequest, ...]
    slots: tuple[SlotKey, ...]
    label_review: LabelReviewResult
    input_identity: str = Field(min_length=64, max_length=64)
    code_identity: str = Field(min_length=64, max_length=64)
    code_bindings: CodeBindingsV2
    environment: EnvironmentBindingV2
    operator_authorization_references: tuple[str, ...] = ()
    effective_configuration: EffectiveConfiguration | None = None
    budget_assessment: BudgetAssessment | None = None
    resource_extension: dict[str, object] | None = None
    question: str = Field(min_length=1, max_length=2_000)
    channel: ChannelPolicy = "mixdown"
    segment_policy: SegmentPolicy = "full_signal"
    seal_ready: bool = False
    candidate_digest: str = Field(min_length=64, max_length=64)

    @model_validator(mode="after")
    def _slot_count(self) -> CandidateManifestV2:
        if len(self.slots) != SLOT_COUNT_V2:
            raise ValueError(
                f"candidate must preserve {SLOT_COUNT_V2} slot identities, "
                f"got {len(self.slots)}"
            )
        if len(self.sealed_requests) != 19:
            raise ValueError(
                "candidate must bind 19 unique requests "
                f"(9 single + 10 paired), got {len(self.sealed_requests)}"
            )
        return self
