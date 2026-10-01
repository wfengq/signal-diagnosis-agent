"""Strict source-bound resource facts for planner-ablation resource policy v1."""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

BoundOrigin = Literal[
    "request_override",
    "sdk_default_audit",
    "provider_spec",
    "control_flow_proof",
    "unknown",
]
BoundScope = Literal[
    "admitted",
    "success_path_only",
    "unsupported",
    "fixture_only",
]
ResourcePolicyId = Literal["planner_ablation_resource_v1"]
TelemetrySchemaId = Literal["planner_ablation_telemetry_v1"]


def _require_finite_number(value: float) -> float | int:
    if isinstance(value, bool):
        raise TypeError("boolean is not a numeric bound")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("bound value must be finite")
    return value


class BoundFact(BaseModel):
    """One reviewed numeric/string-bound fact with exact provenance."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    name: str = Field(min_length=1)
    value: float | int
    unit: str = Field(min_length=1)
    origin: BoundOrigin
    applicable_path: str = Field(min_length=1)
    proof_digest: str = Field(min_length=64, max_length=64)
    code_identity: str = Field(min_length=1)
    dependency_identity: str = Field(min_length=1)
    model_identity: str | None = None
    is_explicit_override: bool = False
    acceptance_reference: str = Field(min_length=1)
    scope: BoundScope = "admitted"

    @field_validator("value")
    @classmethod
    def _finite(cls, value: float) -> float | int:
        return _require_finite_number(value)

    @field_validator("proof_digest")
    @classmethod
    def _hex_digest(cls, value: str) -> str:
        if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("proof_digest must be lowercase sha256 hex")
        return value


class SdkProfileAudit(BaseModel):
    """Exact installed SDK/native-transport identity and audited hook points."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    openai_version: str = Field(min_length=1)
    openai_source_digest: str = Field(min_length=64, max_length=64)
    native_http_family: str = Field(min_length=1)
    native_http_version: str = Field(min_length=1)
    httpcore_version: str = Field(min_length=1)
    source_file_digests: dict[str, str]
    max_retries_default: int = Field(ge=0)
    sdk_attempts_per_call: int = Field(ge=1)
    prepare_options_hook: str = Field(min_length=1)
    send_request_hook: str = Field(min_length=1)
    native_dispatch_hook: str = Field(min_length=1)
    supported: bool
    blockers: tuple[str, ...] = ()
    fixture_only: bool = True

    @field_validator("openai_source_digest")
    @classmethod
    def _hex_digest(cls, value: str) -> str:
        if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("openai_source_digest must be lowercase sha256 hex")
        return value

    @field_validator("source_file_digests")
    @classmethod
    def _digest_map(cls, value: dict[str, str]) -> dict[str, str]:
        if not value:
            raise ValueError("source_file_digests must be non-empty")
        for key, digest in value.items():
            if not key or len(digest) != 64:
                raise ValueError("invalid source_file_digests entry")
            if any(ch not in "0123456789abcdef" for ch in digest):
                raise ValueError("source digest must be lowercase sha256 hex")
        return value

    @field_validator("max_retries_default", "sdk_attempts_per_call")
    @classmethod
    def _no_bool(cls, value: int) -> int:
        if isinstance(value, bool):
            raise TypeError("boolean is not an integer count")
        return value


class ProviderLimitsBinding(BaseModel):
    """Requested vs declared provider model/route and token-limit scope."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    endpoint_origin: str = Field(min_length=1)
    requested_model: str = Field(min_length=1)
    declared_route: str = Field(min_length=1)
    allowed_response_models: tuple[str, ...] = ()
    source_date: str = Field(min_length=1)
    source_digest: str = Field(min_length=64, max_length=64)
    source_reference: str | None = None
    token_limit_scope: str = Field(min_length=1)
    authentication_mode: str = Field(min_length=1)
    model_mapping_accepted: bool = False
    fixture_only: bool = True


class ObservationCapability(BaseModel):
    """Offline-proved observation capability for a bound SDK profile."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    telemetry_schema: TelemetrySchemaId
    resource_policy: ResourcePolicyId
    sdk_profile: SdkProfileAudit
    observes_planner_turns: bool
    observes_repairs: bool
    observes_sdk_attempts: bool
    observes_http_sends: bool
    observes_usage: bool
    offline_evidence_digest: str = Field(min_length=64, max_length=64)
    offline_evidence_reference: str | None = None
    fixture_only: bool = True
    blockers: tuple[str, ...] = ()


class ResourceProofBundle(BaseModel):
    """Independently reviewed bound facts used by assess_resource_budget."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    planner_turn_ceiling: BoundFact | None = None
    sdk_attempt_factor: BoundFact | None = None
    http_send_factor: BoundFact | None = None
    input_token_ceiling: BoundFact | None = None
    output_token_ceiling: BoundFact | None = None
    all_outcome_token_ceiling: BoundFact | None = None
    request_timeout: BoundFact | None = None
    sdk_profile: SdkProfileAudit | None = None
    provider_limits: ProviderLimitsBinding | None = None
    fixture_only: bool = True


class ResourceAssessment(BaseModel):
    """Derived ceilings with named units; unknown factors fail closed."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    resource_policy: ResourcePolicyId = "planner_ablation_resource_v1"
    product_slot_count: Literal[57] = 57
    planner_turn_ceiling: int | None = None
    sdk_attempt_factor: int | None = None
    http_send_factor: int | None = None
    logical_call_ceiling: int | None = None
    sdk_attempt_ceiling: int | None = None
    http_send_ceiling: int | None = None
    # Per-slot ceilings (campaign ceilings remain the products above).
    sdk_attempt_ceiling_per_slot: int | None = None
    http_send_ceiling_per_slot: int | None = None
    input_token_ceiling: int | None = None
    output_token_ceiling: int | None = None
    request_timeout_s: float | None = None
    request_timeout_explicit: bool = False
    transport_retry_override_explicit: bool = False
    allowed_response_models: tuple[str, ...] = ()
    model_mapping_accepted: bool = False
    blockers: tuple[str, ...] = ()
    execution_blocked: bool = True
    seal_ready: bool = False
    fixture_only: bool = True


class ReportedUsage(BaseModel):
    """Validated provider-reported usage totals and optional subdivisions."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    cache_hit_tokens: int | None = None
    cache_miss_tokens: int | None = None
    reasoning_tokens: int | None = None

    @field_validator(
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "cache_hit_tokens",
        "cache_miss_tokens",
        "reasoning_tokens",
    )
    @classmethod
    def _no_bool(cls, value: int | None) -> int | None:
        if isinstance(value, bool):
            raise TypeError("boolean is not a token count")
        return value

    @model_validator(mode="after")
    def _arithmetic(self) -> ReportedUsage:
        if self.total_tokens != self.prompt_tokens + self.completion_tokens:
            raise ValueError("total_tokens must equal prompt_tokens + completion_tokens")
        if (
            self.cache_hit_tokens is not None
            and self.cache_miss_tokens is not None
            and self.cache_hit_tokens + self.cache_miss_tokens != self.prompt_tokens
        ):
            raise ValueError("cache hit+miss must equal prompt_tokens")
        if (
            self.reasoning_tokens is not None
            and self.reasoning_tokens > self.completion_tokens
        ):
            raise ValueError("reasoning_tokens cannot exceed completion_tokens")
        return self


class SlotResourceLedger(BaseModel):
    """Validated event sequence and closure state for one campaign slot."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    slot_key_digest: str = Field(min_length=1)
    run_id: str | None = None
    events: tuple[dict[str, object], ...] = ()
    planner_turn_count: int | None = None
    repair_attempt_count: int | None = None
    logical_call_count: int | None = None
    sdk_attempt_count: int | None = None
    http_send_attempt_count: int | None = None
    reported_usage_subtotal: ReportedUsage | None = None
    exact_total_tokens: int | None = None
    potential_token_exposure: int | None = None
    pending_event_ids: tuple[str, ...] = ()
    worker_drained: bool = False
    telemetry_invalid: bool = False
    incomplete: bool = True
    blockers: tuple[str, ...] = ()
    closed: bool = False

    @model_validator(mode="after")
    def _closure_consistency(self) -> SlotResourceLedger:
        if self.closed and (
            self.incomplete or self.telemetry_invalid or not self.worker_drained
        ):
            raise ValueError("closed ledger cannot be incomplete, invalid, or undrained")
        return self


class ResourceObservation(BaseModel):
    """Aggregated resource observation projected for campaign/decision gates."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    planner_turn_count: int | None = None
    repair_attempt_count: int | None = None
    logical_call_count: int | None = None
    sdk_attempt_count: int | None = None
    http_send_attempt_count: int | None = None
    reported_usage_subtotal: ReportedUsage | None = None
    exact_total_tokens: int | None = None
    potential_token_exposure: int | None = None
    acceptance_blocked: bool = True
    blockers: tuple[str, ...] = ()
    telemetry_invalid: bool = False
    incomplete: bool = True


class ResourceCandidateExtension(BaseModel):
    """Optional resource-policy extension on an unsealed/verified candidate."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    resource_policy: ResourcePolicyId
    telemetry_schema: TelemetrySchemaId
    proofs: ResourceProofBundle
    capability: ObservationCapability
    assessment: ResourceAssessment
    provider_dependency_identity: str = Field(min_length=1)
    label_review_digest: str = Field(min_length=64, max_length=64)
    label_population_digest: str = Field(min_length=64, max_length=64)
    code_identity: str = Field(min_length=64, max_length=64)
    extension_digest: str = Field(min_length=64, max_length=64)
    fixture_only: bool = True


class ResourceCandidateValidation(BaseModel):
    """Recomputed readiness for a resource-policy candidate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    resource_policy: ResourcePolicyId = "planner_ablation_resource_v1"
    ready: bool = False
    reasons: tuple[str, ...] = ()
    assessment: ResourceAssessment | None = None
    recomputed_extension_digest: str | None = None
    fixture_only: bool = True
