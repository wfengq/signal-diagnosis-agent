"""Immutable external WAV validity study models."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from signal_diag.agent.models import DiagnosisOutcome
from signal_diag.evaluation.external.reference_models import ReferenceSummary
from signal_diag.evaluation.models import (
    AttemptErrorCode,
    AttemptStatus,
    BenchmarkConfig,
    CausalFault,
    EvaluationTrace,
    EvidenceCondition,
    ExecutionPath,
    KnowledgePolicy,
    RateMetric,
    SufficientEvidenceSet,
)
from signal_diag.tools.contracts import ToolName

ExternalSplit = Literal["development", "validation", "final_external_test"]
SourceGroup = Literal["A", "B", "C"]
LabelConfidence = Literal[
    "strong_ground_truth",
    "reference_supported",
    "weak_observation",
    "unknown",
]
ExternalClass = Literal[
    "clean",
    "clipping",
    "harmonic",
    "combined",
    "inconclusive",
    "ambiguous",
]
TransformKind = Literal["none", "clipping", "second_harmonic", "combined"]
ExternalTargetStatus = Literal["not_evaluated", "meets_target", "below_target"]

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_CASE_ID_PATTERN = re.compile(r"^[0-9a-f]{16}$")
_ANALYSIS_WAV_FILENAME_PATTERN = re.compile(
    r"^extwav_(development|validation|final_external_test)_[0-9a-f]{16}\.wav$"
)
_COMBINED_CAUSAL_FAULTS: tuple[CausalFault, ...] = ("clipping", "harmonic_distortion")
_DEGRADED_B_CLASSES: frozenset[ExternalClass] = frozenset(
    {"clipping", "harmonic", "combined"},
)


def _require_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must be timezone-aware UTC")


def _reject_duplicates(values: tuple[object, ...], label: str) -> None:
    seen: set[object] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"duplicate {label}: {value}")
        seen.add(value)


def _reject_empty(values: tuple[object, ...], label: str) -> None:
    if not values:
        raise ValueError(f"{label} must be non-empty")


def _analysis_filename(path: str) -> str:
    normalized = path.replace("\\", "/")
    return normalized.rsplit("/", maxsplit=1)[-1]


class TransformConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    kind: TransformKind
    tail_proportion: float | None = Field(default=None, gt=0.0, lt=1.0)
    alpha: float | None = Field(default=None, gt=0.0)
    post_gain: float | None = Field(default=None, gt=0.0)
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parameters_identity: str = Field(min_length=1)


class CaptureCoverageMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    loudspeaker: str | None = None
    microphone_position: str | None = None
    distance: str | None = None
    playback_level: str | None = None
    acoustic_environment: str | None = None
    f0_band: str | None = None


class ExternalCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    case_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    split: ExternalSplit
    source_group: SourceGroup
    external_class: ExternalClass
    analysis_wav_path: str = Field(min_length=1)
    wav_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    wav_sample_rate_hz: int = Field(gt=0)
    wav_sample_width_bytes: int = Field(ge=1, le=4)
    wav_channels: int = Field(ge=1, le=2)
    wav_frames: int = Field(ge=1)
    provenance_ref: str = Field(min_length=1)
    source_recording_key: str = Field(min_length=1)
    capture_configuration_key: str = Field(min_length=1)
    parent_master_id: str | None = None
    transform: TransformConfig | None = None
    confidence: LabelConfidence
    review_ref: str = Field(min_length=1)
    observable_conditions: tuple[EvidenceCondition, ...]
    sufficient_evidence_sets: tuple[SufficientEvidenceSet, ...]
    knowledge_policy: KnowledgePolicy
    knowledge_tags: tuple[str, ...] = ()
    acceptable_first_tools: tuple[ToolName, ...]
    acceptable_outcomes: tuple[DiagnosisOutcome, ...]
    causal_faults: tuple[CausalFault, ...] = ()
    requires_limitation: bool = False
    capture_coverage: CaptureCoverageMetadata | None = None

    @model_validator(mode="after")
    def _validate_consistency(self) -> ExternalCase:
        normalized_path = self.analysis_wav_path.replace("\\", "/")
        path = PurePosixPath(normalized_path)
        if (
            path.is_absolute()
            or re.match(r"^[A-Za-z]:", normalized_path)
            or ".." in path.parts
        ):
            raise ValueError(
                "analysis_wav_path must be a repository-relative path without '..'"
            )
        filename = _analysis_filename(self.analysis_wav_path)
        match = _ANALYSIS_WAV_FILENAME_PATTERN.fullmatch(filename)
        if match is None:
            raise ValueError(
                "analysis filename must match "
                "extwav_(development|validation|final_external_test)_[0-9a-f]{16}.wav"
            )
        if match.group(1) != self.split:
            raise ValueError("analysis filename split must match case split")
        if filename != f"extwav_{self.split}_{self.case_id}.wav":
            raise ValueError("analysis filename case_id must match opaque case_id")

        if self.source_group == "B":
            if self.parent_master_id is None:
                raise ValueError("B cases require parent_master_id")
        elif self.parent_master_id is not None:
            raise ValueError("non-B cases must not declare parent_master_id")

        if self.confidence == "strong_ground_truth":
            if (
                self.source_group != "B"
                or self.external_class not in _DEGRADED_B_CLASSES
            ):
                raise ValueError("only B degraded cases may be strong_ground_truth")
            if self.transform is None or self.transform.kind == "none":
                raise ValueError("strong ground truth requires transform provenance")
            expected_kind = {
                "clipping": "clipping",
                "harmonic": "second_harmonic",
                "combined": "combined",
            }[self.external_class]
            if self.transform.kind != expected_kind:
                raise ValueError("transform kind must match external_class")
            if self.transform.output_sha256 != self.wav_sha256:
                raise ValueError("transform output_sha256 must match wav_sha256")

        if self.source_group != "B" and self.transform is not None:
            raise ValueError("non-B cases must not declare transform provenance")

        if self.confidence in {"weak_observation", "unknown"}:
            if self.acceptable_outcomes or self.causal_faults:
                raise ValueError("weak/unknown cases forbid scoring truth")
        elif not self.acceptable_outcomes and not self.causal_faults:
            raise ValueError("strong/reference cases require scoring truth")

        if (
            self.external_class == "combined"
            and self.causal_faults != _COMBINED_CAUSAL_FAULTS
        ):
            raise ValueError(
                "combined causal faults must be ('clipping', 'harmonic_distortion')"
            )

        condition_ids = tuple(
            condition.condition_id for condition in self.observable_conditions
        )
        _reject_duplicates(condition_ids, "condition_id")
        set_ids = tuple(
            evidence_set.evidence_set_id
            for evidence_set in self.sufficient_evidence_sets
        )
        _reject_duplicates(set_ids, "evidence_set_id")
        known = set(condition_ids)
        for evidence_set in self.sufficient_evidence_sets:
            for ref in evidence_set.condition_refs:
                if ref not in known:
                    raise ValueError(f"unresolved condition_ref: {ref}")
        return self


class ExternalDatasetManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    schema_version: Literal["1.0"] = "1.0"
    dataset_id: Literal["s1-distortion-external-wav"] = "s1-distortion-external-wav"
    version: Literal["1.0.0"] = "1.0.0"
    study_id: Literal["v0.2-external-wav-validity-1"] = "v0.2-external-wav-validity-1"
    rule_profile_id: Literal["profile_s1_distortion"] = "profile_s1_distortion"
    rule_profile_version: Literal["1.0.0-demo"] = "1.0.0-demo"
    external_scoring_id: Literal["signal_diag.external_scoring"] = (
        "signal_diag.external_scoring"
    )
    external_scoring_version: Literal["1.0.0"] = "1.0.0"
    cases: tuple[ExternalCase, ...]

    @model_validator(mode="after")
    def _validate_cases(self) -> ExternalDatasetManifest:
        _reject_duplicates(tuple(case.case_id for case in self.cases), "case_id")
        masters = {
            case.parent_master_id: case.wav_sha256
            for case in self.cases
            if case.source_group == "B" and case.external_class == "clean"
        }
        for case in self.cases:
            if case.confidence != "strong_ground_truth" or case.transform is None:
                continue
            master_digest = masters.get(case.parent_master_id)
            if (
                master_digest is not None
                and case.transform.input_sha256 != master_digest
            ):
                raise ValueError(
                    "transform input_sha256 must match clean parent master"
                )
        return self


class SourceCatalogEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    source_id: str = Field(min_length=1)
    official_name: str = Field(min_length=1)
    authoritative_page_url: str = Field(min_length=1)
    direct_asset_url: str = Field(min_length=1)
    citation: str = Field(min_length=1)
    terms_url: str = Field(min_length=1)
    terms_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    upstream_asset_id: str = Field(min_length=1)
    upstream_group_id: str = Field(min_length=1)
    published_checksum: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    maximum_bytes: int = Field(gt=0)
    license_classification: str = Field(min_length=1)
    redistribution_decision: str = Field(min_length=1)
    attribution: str = Field(min_length=1)


class SourceCatalog(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    schema_version: Literal["1.0"] = "1.0"
    catalog_id: str = Field(min_length=1)
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    sources: tuple[SourceCatalogEntry, ...]

    @model_validator(mode="after")
    def _validate_sources(self) -> SourceCatalog:
        _reject_duplicates(
            tuple(entry.source_id for entry in self.sources),
            "source_id",
        )
        return self


class AcquiredAsset(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    asset_id: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(ge=0)
    acquired_at_utc: datetime

    @model_validator(mode="after")
    def _validate_acquired_at(self) -> AcquiredAsset:
        _require_utc(self.acquired_at_utc, "acquired_at_utc")
        return self


class DerivationSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    channel_index: int = Field(ge=0)
    start_frame: int = Field(ge=0)
    stop_frame: int = Field(gt=0)

    @model_validator(mode="after")
    def _validate_window(self) -> DerivationSpec:
        if self.stop_frame <= self.start_frame:
            raise ValueError("stop_frame must be greater than start_frame")
        return self


class DerivedAsset(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sample_rate_hz: int = Field(gt=0)
    sample_width_bytes: int = Field(ge=1, le=4)
    channels: int = Field(ge=1, le=2)
    frames: int = Field(ge=1)


class CoverageDimensionReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    documented_values: tuple[str, ...] = ()
    unavailable: bool = False
    meets_target: bool


class ExternalCoverageReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    loudspeaker: CoverageDimensionReport
    microphone_position: CoverageDimensionReport
    distance: CoverageDimensionReport
    playback_level: CoverageDimensionReport
    acoustic_environment: CoverageDimensionReport
    f0_band: CoverageDimensionReport


class ExternalValidationIssue(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str = Field(min_length=1)
    case_id: str | None = None
    message: str = Field(min_length=1)


class ExternalValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_id: str
    dataset_version: str
    stage: Literal["development", "validation", "final_preflight"]
    valid: bool
    checked_case_ids: tuple[str, ...]
    issues: tuple[ExternalValidationIssue, ...] = ()
    coverage: ExternalCoverageReport | None = None

    @model_validator(mode="after")
    def _validate_valid_matches_issues(self) -> ExternalValidationReport:
        if self.valid != (len(self.issues) == 0):
            raise ValueError("valid is true exactly when issues is empty")
        return self


class ReviewRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    review_alias: str = Field(min_length=1)
    case_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    round_number: Literal[1, 2]
    outcome: DiagnosisOutcome
    causal_faults: tuple[CausalFault, ...] = ()
    confidence: LabelConfidence
    applicability: str = Field(min_length=1)
    reason_codes: tuple[str, ...] = ()
    reviewed_at_utc: datetime

    @model_validator(mode="after")
    def _validate_reviewed_at(self) -> ReviewRecord:
        _require_utc(self.reviewed_at_utc, "reviewed_at_utc")
        return self


class BlindPackageCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    review_alias: str = Field(min_length=1)
    analysis_wav_path: str = Field(min_length=1)
    reference_summary: ReferenceSummary


class BlindPackage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    package_id: str = Field(min_length=1)
    created_at_utc: datetime
    cases: tuple[BlindPackageCase, ...]

    @model_validator(mode="after")
    def _validate_created_at(self) -> BlindPackage:
        _require_utc(self.created_at_utc, "created_at_utc")
        _reject_duplicates(
            tuple(case.review_alias for case in self.cases),
            "review_alias",
        )
        return self


class ReviewAgreement(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    raw_outcome_agreement: float = Field(ge=0.0, le=1.0)
    causal_set_agreement: float | None = Field(default=None, ge=0.0, le=1.0)
    outcome_cohen_kappa: float | None = None
    confidence_quadratic_kappa: float | None = None
    undefined_kappa_reason: str | None = None


class ReviewRound(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    round_number: Literal[1, 2]
    records: tuple[ReviewRecord, ...]
    reference_summaries: dict[str, ReferenceSummary] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_round(self) -> ReviewRound:
        _reject_duplicates(
            tuple(record.case_id for record in self.records), "review case_id"
        )
        if any(record.round_number != self.round_number for record in self.records):
            raise ValueError("review record round_number must match review round")
        if self.round_number == 2 and self.reference_summaries:
            raise ValueError("round 2 must not carry reference summaries")
        return self


class ReviewTargets(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    minimum_raw_outcome_agreement: float = Field(default=0.85, ge=0.0, le=1.0)
    minimum_outcome_kappa: float = Field(default=0.70, ge=-1.0, le=1.0)
    minimum_confidence_kappa: float = Field(default=0.70, ge=-1.0, le=1.0)


class FinalSealInputs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    manifest: ExternalDatasetManifest
    asset_root: Path
    repo_root: Path
    checksum_file: Path
    round1: ReviewRound
    round2: ReviewRound
    review_targets: ReviewTargets
    sealed_at_utc: datetime

    @model_validator(mode="after")
    def _validate_sealed_at(self) -> FinalSealInputs:
        _require_utc(self.sealed_at_utc, "sealed_at_utc")
        return self


class FinalSeal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    seal_id: str = Field(min_length=1)
    study_id: str = Field(min_length=1)
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sealed_at_utc: datetime
    case_count: int = Field(ge=0)
    scoreable_case_count: int = Field(ge=0)

    @model_validator(mode="after")
    def _validate_sealed_at(self) -> FinalSeal:
        _require_utc(self.sealed_at_utc, "sealed_at_utc")
        return self


ExternalStratumDimension = Literal[
    "execution_path",
    "source_group",
    "confidence",
    "external_class",
    "source_recording_key",
    "capture_configuration_key",
    "parent_master_id",
]


class ExternalStratumMetric(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    metric_name: str = Field(min_length=1)
    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)
    exclusions: int = Field(default=0, ge=0)
    value: float | None = Field(default=None, ge=0.0, le=1.0)


class ExternalStratum(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dimension: ExternalStratumDimension
    value: str = Field(min_length=1)
    metrics: tuple[ExternalStratumMetric, ...]


class ExternalRunScore(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    trace_id: str = Field(pattern=r"^trace_")
    case_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    execution_path: ExecutionPath
    external_scoring_id: Literal["signal_diag.external_scoring"] = (
        "signal_diag.external_scoring"
    )
    external_scoring_version: Literal["1.0.0"] = "1.0.0"
    outcome_correct: bool | None = None
    causal_exact_set_correct: bool | None = None
    expected_faults: tuple[CausalFault, ...] = ()
    predicted_faults: tuple[CausalFault, ...] = ()
    predicted_outcome: DiagnosisOutcome | None = None
    predicted_fault_claims: int = Field(default=0, ge=0)
    evidence_grounding: RateMetric | None = None
    unsupported_same_run_claims: int = Field(default=0, ge=0)
    positive_causal_claim_on_unscored: bool | None = None
    unnecessary_tool_actions: int = Field(default=0, ge=0)
    tool_actions: int = Field(default=0, ge=0)
    inconclusive_appropriate: bool | None = None


class ExternalAggregate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    external_scoring_id: Literal["signal_diag.external_scoring"] = (
        "signal_diag.external_scoring"
    )
    external_scoring_version: Literal["1.0.0"] = "1.0.0"
    outcome_accuracy: RateMetric | None = None
    causal_exact_set_accuracy: RateMetric | None = None
    causal_macro_f1: float | None = None
    clipping_precision: RateMetric | None = None
    clipping_recall: RateMetric | None = None
    harmonic_precision: RateMetric | None = None
    harmonic_recall: RateMetric | None = None
    evidence_grounding: RateMetric | None = None
    unsupported_same_run_claim_rate: RateMetric | None = None
    unnecessary_tool_action_rate: RateMetric | None = None
    inconclusive_appropriateness: RateMetric | None = None
    positive_causal_claims_on_unscored: RateMetric | None = None
    scoreable_coverage: RateMetric | None = None
    strata: tuple[ExternalStratum, ...] = ()
    master_cluster_summaries: tuple[ExternalStratum, ...] = ()


class ExternalProvenanceRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    provenance_ref: str = Field(min_length=1)
    source_recording_key: str = Field(min_length=1)
    capture_configuration_key: str = Field(min_length=1)
    original_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    derived_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    original_filename_evaluator_only: str | None = None
    redistribution_permitted: bool = False


class ExternalProtectedAssetsAudit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    checksum_file: str = Field(min_length=1)
    checksum_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ExternalScoredRunArtifact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    record_type: Literal["scored_run"] = "scored_run"
    score: ExternalRunScore
    attempts: tuple[ExternalAttemptRecord, ...] = ()


class ExternalUnscoredSlotArtifact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    record_type: Literal["unscored_slot"] = "unscored_slot"
    execution_path: ExecutionPath
    case_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    run_slot: int = Field(ge=1)
    attempts: tuple[ExternalAttemptRecord, ...]


class ExternalStudyReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    study_id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    seal_id: str = Field(min_length=1)
    harness_status: Literal[
        "external_validation_harness_completed",
        "external_validation_completed",
        "external_validation_completed/below_target",
    ]
    target_status: ExternalTargetStatus
    manifest: ExternalDatasetManifest
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provenance: tuple[ExternalProvenanceRecord, ...]
    reference_summaries: dict[str, ReferenceSummary]
    review_agreement: ReviewAgreement
    attempts: tuple[ExternalAttemptRecord, ...]
    scores: tuple[ExternalRunScore, ...]
    traces: tuple[EvaluationTrace, ...] = ()
    aggregate: ExternalAggregate
    protected_assets: ExternalProtectedAssetsAudit


class ExternalAttemptRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    execution_path: ExecutionPath
    case_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    run_slot: int = Field(ge=1)
    attempt_index: int = Field(ge=1)
    status: AttemptStatus
    error_code: AttemptErrorCode | None = None
    error_message: str | None = None
    started_at_utc: datetime
    finished_at_utc: datetime

    @model_validator(mode="after")
    def _validate_times(self) -> ExternalAttemptRecord:
        _require_utc(self.started_at_utc, "started_at_utc")
        _require_utc(self.finished_at_utc, "finished_at_utc")
        if self.finished_at_utc < self.started_at_utc:
            raise ValueError("finished_at_utc cannot precede started_at_utc")
        return self


class ExternalMaterializedSignal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    signal_id: str = Field(pattern=r"^sig_ext_[0-9a-f]{16}$")
    trace_case_id: str = Field(pattern=r"^case_ext_[0-9a-f]{16}$")
    filename: str = Field(min_length=1)
    wav_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ExternalRunnerReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    execution_path: ExecutionPath
    seal_id: str = Field(min_length=1)
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    config: BenchmarkConfig
    attempts: tuple[ExternalAttemptRecord, ...]
    traces: tuple[EvaluationTrace, ...]
    materialized: tuple[ExternalMaterializedSignal, ...]
