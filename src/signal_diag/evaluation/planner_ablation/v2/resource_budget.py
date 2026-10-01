"""Pure source-aware resource budget derivation (no SDK / app imports)."""

from __future__ import annotations

from signal_diag.evaluation.planner_ablation.v2.models import (
    PRODUCT_SLOT_COUNT_V2,
    EffectiveConfiguration,
)
from signal_diag.evaluation.planner_ablation.v2.resource_models import (
    BoundFact,
    ObservationCapability,
    ResourceAssessment,
    ResourceProofBundle,
)

_ADMITTED_ORIGINS = frozenset(
    {
        "request_override",
        "sdk_default_audit",
        "provider_spec",
        "control_flow_proof",
    }
)
_PLANNER_UNIT = "planner_turns_per_slot"
_SDK_UNIT = "sdk_attempts_per_logical_call"
_HTTP_UNIT = "http_sends_per_sdk_attempt"
_TOKEN_UNIT = "tokens_per_http_send"
_TIMEOUT_UNIT = "seconds"


def _positive_int(fact: BoundFact | None, *, unit: str, blockers: list[str], label: str) -> int | None:
    if fact is None:
        return None
    if fact.origin == "unknown" or fact.origin not in _ADMITTED_ORIGINS:
        blockers.append(f"unsupported_bound_origin:{label}:{fact.origin}")
        return None
    if fact.scope == "unsupported":
        blockers.append(f"unsupported_bound_scope:{label}:{fact.scope}")
        return None
    if fact.unit != unit:
        blockers.append(f"unit_mismatch:{label}:expected_{unit}:actual_{fact.unit}")
        return None
    if isinstance(fact.value, bool) or not isinstance(fact.value, (int, float)):
        blockers.append(f"non_numeric_bound:{label}")
        return None
    if isinstance(fact.value, float) and not fact.value.is_integer():
        blockers.append(f"non_integer_count_bound:{label}")
        return None
    as_int = int(fact.value)
    if as_int <= 0:
        blockers.append(f"non_positive_bound:{label}")
        return None
    if not fact.acceptance_reference:
        blockers.append(f"missing_proof_acceptance:{label}")
        return None
    return as_int


def _timeout_seconds(fact: BoundFact | None, blockers: list[str]) -> float | None:
    if fact is None:
        return None
    if fact.origin == "unknown" or fact.origin not in _ADMITTED_ORIGINS:
        blockers.append(f"unsupported_bound_origin:request_timeout:{fact.origin}")
        return None
    if fact.unit != _TIMEOUT_UNIT:
        blockers.append(
            f"unit_mismatch:request_timeout:expected_{_TIMEOUT_UNIT}:actual_{fact.unit}"
        )
        return None
    if isinstance(fact.value, bool):
        blockers.append("non_numeric_bound:request_timeout")
        return None
    value = float(fact.value)
    if value <= 0.0:
        blockers.append("non_positive_bound:request_timeout")
        return None
    return value


def assess_resource_budget(
    config: EffectiveConfiguration,
    proofs: ResourceProofBundle,
    capability: ObservationCapability | None,
) -> ResourceAssessment:
    """Derive named-unit ceilings; absent proofs/capability fail closed.

    Audited SDK defaults never flip EffectiveConfiguration ``*_explicit`` flags.
    Context-window / success-path token facts do not prove failed-attempt exposure.
    """
    blockers: list[str] = []

    # Defaults never become explicit through this path.
    request_timeout_explicit = False
    transport_retry_override_explicit = False
    if config.request_timeout_explicit:
        # Preserve caller truth without inventing it from audits.
        request_timeout_explicit = True
    if config.transport_retry_override_explicit:
        transport_retry_override_explicit = True

    if capability is None:
        blockers.append("missing_observation_capability")
    else:
        if capability.resource_policy != "planner_ablation_resource_v1":
            blockers.append("resource_policy_mismatch")
        if capability.telemetry_schema != "planner_ablation_telemetry_v1":
            blockers.append("telemetry_schema_mismatch")
        if not capability.sdk_profile.supported:
            blockers.extend(capability.sdk_profile.blockers or ("unsupported_sdk_profile",))
        if not (
            capability.observes_planner_turns
            and capability.observes_repairs
            and capability.observes_sdk_attempts
            and capability.observes_http_sends
            and capability.observes_usage
        ):
            blockers.append("incomplete_observation_capability")
        blockers.extend(capability.blockers)

    if proofs.sdk_profile is None:
        blockers.append("missing_sdk_profile_audit")
    elif not proofs.sdk_profile.supported:
        blockers.extend(proofs.sdk_profile.blockers or ("unsupported_sdk_profile",))
    elif capability is not None and proofs.sdk_profile.openai_version != (
        capability.sdk_profile.openai_version
    ):
        blockers.append(
            "dependency_identity_drift:"
            f"capability_{capability.sdk_profile.openai_version}"
            f"_vs_proof_{proofs.sdk_profile.openai_version}"
        )

    provider = proofs.provider_limits
    allowed_models: tuple[str, ...] = ()
    model_mapping_accepted = False
    if provider is None:
        blockers.append("missing_provider_limits_binding")
    else:
        allowed_models = provider.allowed_response_models
        model_mapping_accepted = provider.model_mapping_accepted
        if not provider.model_mapping_accepted:
            blockers.append("unaccepted_provider_model_mapping")

    planner = _positive_int(
        proofs.planner_turn_ceiling,
        unit=_PLANNER_UNIT,
        blockers=blockers,
        label="planner_turn_ceiling",
    )
    sdk_factor = _positive_int(
        proofs.sdk_attempt_factor,
        unit=_SDK_UNIT,
        blockers=blockers,
        label="sdk_attempt_factor",
    )
    http_factor = _positive_int(
        proofs.http_send_factor,
        unit=_HTTP_UNIT,
        blockers=blockers,
        label="http_send_factor",
    )
    if proofs.http_send_factor is None:
        blockers.append("unproved_http_send_bound")

    timeout_s = _timeout_seconds(proofs.request_timeout, blockers)

    logical_ceiling: int | None = None
    sdk_ceiling: int | None = None
    http_ceiling: int | None = None
    sdk_ceiling_per_slot: int | None = None
    http_ceiling_per_slot: int | None = None
    if planner is not None:
        logical_ceiling = PRODUCT_SLOT_COUNT_V2 * planner
    if planner is not None and sdk_factor is not None:
        sdk_ceiling_per_slot = planner * sdk_factor
        sdk_ceiling = PRODUCT_SLOT_COUNT_V2 * sdk_ceiling_per_slot
    if sdk_ceiling is not None and http_factor is not None and sdk_ceiling_per_slot is not None:
        http_ceiling_per_slot = sdk_ceiling_per_slot * http_factor
        http_ceiling = sdk_ceiling * http_factor

    input_ceiling: int | None = None
    output_ceiling: int | None = None
    all_outcome = proofs.all_outcome_token_ceiling
    if all_outcome is not None:
        all_val = _positive_int(
            all_outcome,
            unit=_TOKEN_UNIT,
            blockers=blockers,
            label="all_outcome_token_ceiling",
        )
        if all_val is not None and http_ceiling is not None:
            if all_outcome.scope not in {"admitted"}:
                blockers.append(
                    f"unsupported_bound_scope:all_outcome_token_ceiling:{all_outcome.scope}"
                )
            else:
                input_ceiling = http_ceiling * all_val
                output_ceiling = http_ceiling * all_val
    else:
        # Success-path / context-capacity facts cannot clear failed-attempt exposure.
        input_fact = proofs.input_token_ceiling
        output_fact = proofs.output_token_ceiling
        if input_fact is None:
            blockers.append("unknown_input_token_bound")
        elif input_fact.scope != "admitted" or input_fact.origin == "unknown":
            blockers.append("unproven_failed_attempt_token_bound")
            if input_fact.origin == "unknown" or input_fact.origin not in _ADMITTED_ORIGINS:
                blockers.append(
                    f"unsupported_bound_origin:input_token_ceiling:{input_fact.origin}"
                )
        else:
            input_val = _positive_int(
                input_fact,
                unit=_TOKEN_UNIT,
                blockers=blockers,
                label="input_token_ceiling",
            )
            if input_val is not None and http_ceiling is not None:
                input_ceiling = http_ceiling * input_val

        if output_fact is None:
            blockers.append("unknown_output_token_bound")
        elif output_fact.scope != "admitted" or output_fact.origin == "unknown":
            if "unproven_failed_attempt_token_bound" not in blockers:
                blockers.append("unproven_failed_attempt_token_bound")
            if output_fact.origin == "unknown" or output_fact.origin not in _ADMITTED_ORIGINS:
                blockers.append(
                    f"unsupported_bound_origin:output_token_ceiling:{output_fact.origin}"
                )
        else:
            output_val = _positive_int(
                output_fact,
                unit=_TOKEN_UNIT,
                blockers=blockers,
                label="output_token_ceiling",
            )
            if output_val is not None and http_ceiling is not None:
                output_ceiling = http_ceiling * output_val

        if (
            input_fact is not None
            and input_fact.scope == "success_path_only"
            and "unproven_failed_attempt_token_bound" not in blockers
        ):
            blockers.append("unproven_failed_attempt_token_bound")
        if (
            output_fact is not None
            and output_fact.scope == "success_path_only"
            and "unproven_failed_attempt_token_bound" not in blockers
        ):
            blockers.append("unproven_failed_attempt_token_bound")

    unique = tuple(dict.fromkeys(blockers))
    execution_blocked = len(unique) > 0 or sdk_ceiling is None
    return ResourceAssessment(
        product_slot_count=PRODUCT_SLOT_COUNT_V2,
        planner_turn_ceiling=planner,
        sdk_attempt_factor=sdk_factor,
        http_send_factor=http_factor,
        logical_call_ceiling=logical_ceiling,
        sdk_attempt_ceiling=sdk_ceiling,
        http_send_ceiling=http_ceiling,
        sdk_attempt_ceiling_per_slot=sdk_ceiling_per_slot,
        http_send_ceiling_per_slot=http_ceiling_per_slot,
        input_token_ceiling=input_ceiling,
        output_token_ceiling=output_ceiling,
        request_timeout_s=timeout_s,
        request_timeout_explicit=request_timeout_explicit,
        transport_retry_override_explicit=transport_retry_override_explicit,
        allowed_response_models=allowed_models,
        model_mapping_accepted=model_mapping_accepted,
        blockers=unique,
        execution_blocked=execution_blocked,
        seal_ready=False,
        fixture_only=proofs.fixture_only or (capability.fixture_only if capability else True),
    )
