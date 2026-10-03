"""Study-only helpers: bind agent SDK identity to resource-policy capability models."""

from __future__ import annotations

from signal_diag.agent.telemetry import SdkObservationProfile
from signal_diag.evaluation.planner_ablation.v2.resource_models import (
    BoundFact,
    InstalledSdkIdentity,
    ObservationCapability,
    ProviderLimitsBinding,
    SdkProfileAudit,
)

# Reviewed hook names from RESOURCE_BOUNDS / provider telemetry audit (identity only).
_PREPARE_OPTIONS_HOOK = "AsyncAPIClient._prepare_options"
_SEND_REQUEST_HOOK = "AsyncAPIClient._send_request"
_NATIVE_DISPATCH_HOOK = "httpx.AsyncClient.send"
_AUDITED_MAX_RETRIES_DEFAULT = 2
_AUDITED_SDK_ATTEMPTS_PER_CALL = 3
_ADMITTED_HTTP_SEND_FACTOR = 21
_HTTP_SEND_UNIT = "http_sends_per_sdk_attempt"
_HTTP_SEND_DEPENDENCY_IDENTITY = "openai==3.6.0;httpx==0.28.1"
_HTTP_SEND_APPLICABLE_PATH = (
    "openai_async_follow_redirects_plus_httpx_default_max_redirects_20"
)
_D041_ACCEPTANCE_REFERENCE = (
    "docs/DECISIONS.md#d041--oq-019dev_2-residual-preseal-route-acceptance-and-http-send-factor-h"
)
_OPERATOR_ROUTE_DECLARED = "deepseek-v4.1-flash"
_OPERATOR_ROUTE_REQUESTED = "deepseek-v4-flash"
_OPERATOR_ROUTE_ENDPOINT = "https://api.deepseek.com"
_OPERATOR_ROUTE_SOURCE_DATE = "2026-10-01"


def installed_sdk_identity_from_profile(profile: SdkObservationProfile) -> InstalledSdkIdentity:
    """Project an agent observation profile to study ``InstalledSdkIdentity``."""
    return InstalledSdkIdentity(
        openai_version=profile.openai_version,
        openai_source_digest=profile.openai_source_digest,
        native_http_family=profile.native_http_family,
        native_http_version=profile.native_http_version,
        httpcore_version=profile.httpcore_version,
        source_file_digests=dict(profile.source_file_digests),
        supported=profile.supported,
        blockers=profile.blockers,
    )


def sdk_profile_audit_from_installed(
    identity: InstalledSdkIdentity,
    *,
    fixture_only: bool = True,
    max_retries_default: int = _AUDITED_MAX_RETRIES_DEFAULT,
    sdk_attempts_per_call: int = _AUDITED_SDK_ATTEMPTS_PER_CALL,
) -> SdkProfileAudit:
    """Map installed identity to ``SdkProfileAudit`` without upgrading ``supported``."""
    return SdkProfileAudit(
        openai_version=identity.openai_version,
        openai_source_digest=identity.openai_source_digest,
        native_http_family=identity.native_http_family,
        native_http_version=identity.native_http_version,
        httpcore_version=identity.httpcore_version,
        source_file_digests=dict(identity.source_file_digests),
        max_retries_default=max_retries_default,
        sdk_attempts_per_call=sdk_attempts_per_call,
        prepare_options_hook=_PREPARE_OPTIONS_HOOK,
        send_request_hook=_SEND_REQUEST_HOOK,
        native_dispatch_hook=_NATIVE_DISPATCH_HOOK,
        supported=identity.supported,
        blockers=identity.blockers,
        fixture_only=fixture_only,
    )


def sdk_profile_audit_from_profile(
    profile: SdkObservationProfile,
    *,
    fixture_only: bool = True,
) -> SdkProfileAudit:
    """Map ``SdkObservationProfile`` to ``SdkProfileAudit`` (preserves supported/blockers)."""
    return SdkProfileAudit(
        openai_version=profile.openai_version,
        openai_source_digest=profile.openai_source_digest,
        native_http_family=profile.native_http_family,
        native_http_version=profile.native_http_version,
        httpcore_version=profile.httpcore_version,
        source_file_digests=dict(profile.source_file_digests),
        max_retries_default=profile.max_retries_default,
        sdk_attempts_per_call=profile.sdk_attempts_per_call,
        prepare_options_hook=profile.prepare_options_hook,
        send_request_hook=profile.send_request_hook,
        native_dispatch_hook=profile.native_dispatch_hook,
        supported=profile.supported,
        blockers=profile.blockers,
        fixture_only=fixture_only,
    )


def bind_observation_capability(
    sdk: SdkObservationProfile | InstalledSdkIdentity,
    *,
    offline_evidence_digest: str,
    observes_planner_turns: bool = True,
    observes_repairs: bool = True,
    observes_sdk_attempts: bool = True,
    observes_http_sends: bool = True,
    observes_usage: bool = True,
    offline_evidence_reference: str | None = None,
    fixture_only: bool = True,
    capability_blockers: tuple[str, ...] = (),
) -> ObservationCapability:
    """Build study ``ObservationCapability`` from installed or agent SDK identity."""
    if isinstance(sdk, InstalledSdkIdentity):
        audit = sdk_profile_audit_from_installed(sdk, fixture_only=fixture_only)
    else:
        audit = sdk_profile_audit_from_profile(sdk, fixture_only=fixture_only)
    return ObservationCapability(
        telemetry_schema="planner_ablation_telemetry_v1",
        resource_policy="planner_ablation_resource_v1",
        sdk_profile=audit,
        observes_planner_turns=observes_planner_turns,
        observes_repairs=observes_repairs,
        observes_sdk_attempts=observes_sdk_attempts,
        observes_http_sends=observes_http_sends,
        observes_usage=observes_usage,
        offline_evidence_digest=offline_evidence_digest,
        offline_evidence_reference=offline_evidence_reference,
        fixture_only=fixture_only,
        blockers=capability_blockers,
    )


def operator_accepted_provider_limits_binding(
    *,
    source_digest: str,
    fixture_only: bool = True,
    source_reference: str = _D041_ACCEPTANCE_REFERENCE,
) -> ProviderLimitsBinding:
    """Study-only Task 6 route package after operator acceptance (D041).

    Does not change product model strings or live provider wiring.
    """
    return ProviderLimitsBinding(
        endpoint_origin=_OPERATOR_ROUTE_ENDPOINT,
        requested_model=_OPERATOR_ROUTE_REQUESTED,
        declared_route=_OPERATOR_ROUTE_DECLARED,
        allowed_response_models=(_OPERATOR_ROUTE_REQUESTED, "deepseek-chat"),
        source_date=_OPERATOR_ROUTE_SOURCE_DATE,
        source_digest=source_digest,
        source_reference=source_reference,
        token_limit_scope="success_path_only",
        authentication_mode="bearer_api_key",
        model_mapping_accepted=True,
        fixture_only=fixture_only,
    )


def admitted_http_send_factor_bound_fact(
    *,
    proof_digest: str,
    code_identity: str,
    acceptance_reference: str = _D041_ACCEPTANCE_REFERENCE,
    applicable_path: str = _HTTP_SEND_APPLICABLE_PATH,
) -> BoundFact:
    """Admitted redirect-chain HTTP send factor ``H`` for reviewed ``openai==3.6.0`` install."""
    return BoundFact(
        name="http_send_factor",
        value=_ADMITTED_HTTP_SEND_FACTOR,
        unit=_HTTP_SEND_UNIT,
        origin="sdk_default_audit",
        applicable_path=applicable_path,
        proof_digest=proof_digest,
        code_identity=code_identity,
        dependency_identity=_HTTP_SEND_DEPENDENCY_IDENTITY,
        model_identity=_OPERATOR_ROUTE_REQUESTED,
        acceptance_reference=acceptance_reference,
        scope="admitted",
    )
