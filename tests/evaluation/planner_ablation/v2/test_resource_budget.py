"""T-CX303/304/305/316/324: source-aware resource budget admission (offline)."""

from __future__ import annotations

import inspect

from signal_diag.agent.provider_telemetry import reviewed_openai_capability_identity
from signal_diag.agent.telemetry import SdkObservationProfile
from signal_diag.evaluation.planner_ablation.v2.campaign import (
    inspect_limits,
    snapshot_effective_configuration,
)
from signal_diag.evaluation.planner_ablation.v2.resource_budget import (
    assess_resource_budget,
)
from signal_diag.evaluation.planner_ablation.v2.resource_capability import (
    bind_observation_capability,
    sdk_profile_audit_from_profile,
)
from signal_diag.evaluation.planner_ablation.v2.resource_models import (
    BoundFact,
    ObservationCapability,
    ProviderLimitsBinding,
    ReportedUsage,
    ResourceProofBundle,
    SdkProfileAudit,
    SlotResourceLedger,
)


def _fact(
    *,
    name: str,
    value: float,
    unit: str,
    origin: str,
    applicable_path: str = "product_deepseek_chat",
    proof_digest: str = "a" * 64,
    code_identity: str = "b" * 64,
    dependency_identity: str = "openai==3.6.0",
    model_identity: str | None = "deepseek-v4-flash",
    is_explicit_override: bool = False,
    acceptance_reference: str = "fixture_only_reviewed_fact",
    scope: str = "admitted",
) -> BoundFact:
    return BoundFact(
        name=name,
        value=value,
        unit=unit,
        origin=origin,  # type: ignore[arg-type]
        applicable_path=applicable_path,
        proof_digest=proof_digest,
        code_identity=code_identity,
        dependency_identity=dependency_identity,
        model_identity=model_identity,
        is_explicit_override=is_explicit_override,
        acceptance_reference=acceptance_reference,
        scope=scope,  # type: ignore[arg-type]
    )


def _sdk_audit(**overrides: object) -> SdkProfileAudit:
    base = {
        "openai_version": "3.6.0",
        "openai_source_digest": "c" * 64,
        "native_http_family": "httpx",
        "native_http_version": "0.28.1",
        "httpcore_version": "1.0.9",
        "source_file_digests": {
            "openai/_base_client.py": "d" * 64,
            "openai/_client.py": "e" * 64,
            "openai/_constants.py": "f" * 64,
        },
        "max_retries_default": 2,
        "sdk_attempts_per_call": 3,
        "prepare_options_hook": "AsyncAPIClient._prepare_options",
        "send_request_hook": "AsyncAPIClient._send_request",
        "native_dispatch_hook": "httpx.AsyncClient.send",
        "supported": True,
        "blockers": (),
        "fixture_only": True,
    }
    base.update(overrides)
    return SdkProfileAudit(**base)  # type: ignore[arg-type]


def _capability(**overrides: object) -> ObservationCapability:
    base = {
        "telemetry_schema": "planner_ablation_telemetry_v1",
        "resource_policy": "planner_ablation_resource_v1",
        "sdk_profile": _sdk_audit(),
        "observes_planner_turns": True,
        "observes_repairs": True,
        "observes_sdk_attempts": True,
        "observes_http_sends": True,
        "observes_usage": True,
        "offline_evidence_digest": "1" * 64,
        "fixture_only": True,
    }
    base.update(overrides)
    return ObservationCapability(**base)  # type: ignore[arg-type]


def _provider_binding(**overrides: object) -> ProviderLimitsBinding:
    base = {
        "endpoint_origin": "https://api.deepseek.com",
        "requested_model": "deepseek-v4-flash",
        "declared_route": "deepseek-v4.1-flash",
        "allowed_response_models": ("deepseek-v4-flash", "deepseek-chat"),
        "source_date": "2026-10-01",
        "source_digest": "2" * 64,
        "token_limit_scope": "success_path_only",
        "authentication_mode": "bearer_api_key",
        "model_mapping_accepted": False,
        "fixture_only": True,
    }
    base.update(overrides)
    return ProviderLimitsBinding(**base)  # type: ignore[arg-type]


def _proofs_with_planner_and_sdk(
    *,
    http_send: BoundFact | None = None,
    input_token: BoundFact | None = None,
    output_token: BoundFact | None = None,
    all_outcome_token: BoundFact | None = None,
    provider: ProviderLimitsBinding | None = None,
    sdk_audit: SdkProfileAudit | None = None,
) -> ResourceProofBundle:
    return ResourceProofBundle(
        planner_turn_ceiling=_fact(
            name="planner_turn_ceiling",
            value=28,
            unit="planner_turns_per_slot",
            origin="control_flow_proof",
            applicable_path="runtime_v9_11_agent_limits_default",
        ),
        sdk_attempt_factor=_fact(
            name="sdk_attempt_factor",
            value=3,
            unit="sdk_attempts_per_logical_call",
            origin="sdk_default_audit",
            applicable_path="openai_async_retry_loop",
        ),
        http_send_factor=http_send,
        input_token_ceiling=input_token,
        output_token_ceiling=output_token,
        all_outcome_token_ceiling=all_outcome_token,
        request_timeout=_fact(
            name="request_timeout",
            value=600.0,
            unit="seconds",
            origin="sdk_default_audit",
            applicable_path="openai.DEFAULT_TIMEOUT.read",
            is_explicit_override=False,
        ),
        sdk_profile=sdk_audit or _sdk_audit(),
        provider_limits=provider or _provider_binding(),
        fixture_only=True,
    )


def test_audited_defaults_do_not_set_explicit_flags() -> None:
    config = snapshot_effective_configuration()
    assert config.request_timeout_explicit is False
    assert config.transport_retry_override_explicit is False
    assert config.max_tokens_explicit is False

    proofs = _proofs_with_planner_and_sdk()
    assessment = assess_resource_budget(config, proofs, _capability())
    assert assessment.sdk_attempt_ceiling == 57 * 28 * 3
    assert config.request_timeout_explicit is False
    assert config.transport_retry_override_explicit is False
    # Legacy inspect_limits path remains blocked on default snapshot.
    legacy = inspect_limits(config)
    assert legacy.execution_blocked is True
    assert "unavailable_retry_telemetry" in legacy.blockers


def test_unknown_origin_or_scope_blocks_budget() -> None:
    config = snapshot_effective_configuration()
    proofs = _proofs_with_planner_and_sdk(
        http_send=_fact(
            name="http_send_factor",
            value=21,
            unit="http_sends_per_sdk_attempt",
            origin="unknown",
            scope="unsupported",
        )
    )
    assessment = assess_resource_budget(config, proofs, _capability())
    assert assessment.execution_blocked is True
    assert assessment.http_send_ceiling is None
    assert any(
        code.startswith(("unsupported_bound_origin:", "unsupported_bound_scope:"))
        or code == "unproved_http_send_bound"
        for code in assessment.blockers
    )


def test_sdk_ceiling_is_not_http_ceiling() -> None:
    config = snapshot_effective_configuration()
    proofs = _proofs_with_planner_and_sdk()  # no H proof
    assessment = assess_resource_budget(config, proofs, _capability())
    assert assessment.sdk_attempt_ceiling == 57 * 28 * 3
    assert assessment.http_send_ceiling is None
    assert assessment.execution_blocked is True
    assert "unproved_http_send_bound" in assessment.blockers


def test_context_capacity_does_not_prove_failed_attempt_exposure() -> None:
    config = snapshot_effective_configuration()
    proofs = _proofs_with_planner_and_sdk(
        http_send=_fact(
            name="http_send_factor",
            value=21,
            unit="http_sends_per_sdk_attempt",
            origin="sdk_default_audit",
            applicable_path="httpx_redirect_follow",
        ),
        input_token=_fact(
            name="input_token_ceiling",
            value=128_000,
            unit="tokens_per_http_send",
            origin="provider_spec",
            applicable_path="provider_context_window",
            scope="success_path_only",
        ),
        output_token=_fact(
            name="output_token_ceiling",
            value=8_192,
            unit="tokens_per_http_send",
            origin="provider_spec",
            applicable_path="provider_default_output",
            scope="success_path_only",
        ),
    )
    assessment = assess_resource_budget(config, proofs, _capability())
    assert assessment.execution_blocked is True
    assert "unproven_failed_attempt_token_bound" in assessment.blockers
    # Context capacity may compute a success-path reserve but not clear exposure.
    assert assessment.input_token_ceiling is None or assessment.execution_blocked


def test_missing_observation_capability_blocks_budget() -> None:
    config = snapshot_effective_configuration()
    proofs = _proofs_with_planner_and_sdk()
    assessment = assess_resource_budget(config, proofs, None)
    assert assessment.execution_blocked is True
    assert "missing_observation_capability" in assessment.blockers


def test_incomplete_observation_capability_blocks_budget() -> None:
    config = snapshot_effective_configuration()
    proofs = _proofs_with_planner_and_sdk()
    partial = _capability(observes_http_sends=False)
    assessment = assess_resource_budget(config, proofs, partial)
    assert assessment.execution_blocked is True
    assert "incomplete_observation_capability" in assessment.blockers


def _reviewed_supported_observation_profile() -> SdkObservationProfile:
    """Fixture profile matching reviewed RESOURCE_BOUNDS identity (not live install)."""
    reviewed = reviewed_openai_capability_identity()
    digests = {
        key.removeprefix("source:"): digest
        for key, digest in reviewed.items()
        if key.startswith("source:")
    }
    return SdkObservationProfile(
        openai_version=reviewed["openai_version"],
        openai_source_digest=reviewed["openai_source_digest"],
        native_http_family=reviewed["native_http_family"],
        native_http_version=reviewed["native_http_version"],
        httpcore_version=reviewed["httpcore_version"],
        source_file_digests=tuple(sorted(digests.items())),
        max_retries_default=2,
        sdk_attempts_per_call=3,
        prepare_options_hook=reviewed["prepare_options_hook"],
        send_request_hook=reviewed["send_request_hook"],
        native_dispatch_hook=reviewed["native_dispatch_hook"],
        supported=True,
        blockers=(),
    )


def test_bound_capability_clears_completeness_not_worst_case_blockers() -> None:
    """Completeness bind ≠ HTTP/token ceilings or operator route acceptance."""
    config = snapshot_effective_configuration()
    agent_profile = _reviewed_supported_observation_profile()
    capability = bind_observation_capability(
        agent_profile,
        offline_evidence_digest="f" * 64,
        offline_evidence_reference="tests/evaluation/planner_ablation/v2/test_resource_budget.py",
    )
    sdk_audit = sdk_profile_audit_from_profile(agent_profile)
    proofs = _proofs_with_planner_and_sdk(sdk_audit=sdk_audit)
    assessment = assess_resource_budget(config, proofs, capability)
    assert "missing_observation_capability" not in assessment.blockers
    assert "incomplete_observation_capability" not in assessment.blockers
    assert assessment.execution_blocked is True
    assert "unproved_http_send_bound" in assessment.blockers
    assert "unknown_input_token_bound" in assessment.blockers
    assert "unknown_output_token_bound" in assessment.blockers
    assert "unaccepted_provider_model_mapping" in assessment.blockers
    assert agent_profile.supported is True


def test_t_cx324_closed_ledger_does_not_admit_worst_case_ceilings() -> None:
    """T-CX324: per-run ledger integrity does not substitute for bound proofs."""
    config = snapshot_effective_configuration()
    proofs = _proofs_with_planner_and_sdk()
    capability = bind_observation_capability(
        _reviewed_supported_observation_profile(),
        offline_evidence_digest="e" * 64,
    )
    closed_low_usage = SlotResourceLedger(
        slot_key_digest="slot_digest",
        run_id="run_1",
        events=(),
        planner_turn_count=1,
        repair_attempt_count=0,
        logical_call_count=1,
        sdk_attempt_count=1,
        http_send_attempt_count=1,
        reported_usage_subtotal=ReportedUsage(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        ),
        exact_total_tokens=15,
        potential_token_exposure=15,
        worker_drained=True,
        telemetry_invalid=False,
        incomplete=False,
        closed=True,
    )
    assert closed_low_usage.closed is True
    assert "ledger" not in inspect.signature(assess_resource_budget).parameters
    assessment = assess_resource_budget(config, proofs, capability)
    assert assessment.execution_blocked is True
    assert assessment.http_send_ceiling is None
    assert assessment.input_token_ceiling is None
    assert assessment.output_token_ceiling is None
    assert "unproved_http_send_bound" in assessment.blockers


def test_dependency_or_model_binding_drift_blocks_admission() -> None:
    config = snapshot_effective_configuration()
    drifted = _sdk_audit(
        openai_version="3.20.0",
        supported=False,
        blockers=("dependency_identity_drift:installed_3.6.0_vs_audit_3.20.0",),
    )
    proofs = _proofs_with_planner_and_sdk(sdk_audit=drifted)
    assessment = assess_resource_budget(config, proofs, _capability(sdk_profile=drifted))
    assert assessment.execution_blocked is True
    assert any("dependency" in code or "drift" in code for code in assessment.blockers)

    unaccepted = _proofs_with_planner_and_sdk(
        provider=_provider_binding(model_mapping_accepted=False)
    )
    assessment2 = assess_resource_budget(config, unaccepted, _capability())
    assert assessment2.execution_blocked is True
    assert "unaccepted_provider_model_mapping" in assessment2.blockers
