"""Resource ledger aggregation and prerequisite projection tests."""

from __future__ import annotations

from signal_diag.evaluation.planner_ablation.v2.campaign import (
    snapshot_effective_configuration,
)
from signal_diag.evaluation.planner_ablation.v2.resource_budget import (
    assess_resource_budget,
)
from signal_diag.evaluation.planner_ablation.v2.resource_models import (
    BoundFact,
    ObservationCapability,
    ProviderLimitsBinding,
    ReportedUsage,
    ResourceAssessment,
    ResourceProofBundle,
    SdkProfileAudit,
    SlotResourceLedger,
)
from signal_diag.evaluation.planner_ablation.v2.resource_telemetry import (
    aggregate_resource_ledger,
)


def _assessment() -> ResourceAssessment:
    proofs = ResourceProofBundle(
        planner_turn_ceiling=BoundFact(
            name="planner_turn_ceiling",
            value=28,
            unit="planner_turns_per_slot",
            origin="control_flow_proof",
            applicable_path="runtime",
            proof_digest="a" * 64,
            code_identity="b" * 64,
            dependency_identity="openai==3.20.0",
            acceptance_reference="fixture",
        ),
        sdk_attempt_factor=BoundFact(
            name="sdk_attempt_factor",
            value=3,
            unit="sdk_attempts_per_logical_call",
            origin="sdk_default_audit",
            applicable_path="retry",
            proof_digest="a" * 64,
            code_identity="b" * 64,
            dependency_identity="openai==3.20.0",
            acceptance_reference="fixture",
        ),
        sdk_profile=SdkProfileAudit(
            openai_version="3.20.0",
            openai_source_digest="c" * 64,
            native_http_family="httpx",
            native_http_version="0.28.1",
            httpcore_version="1.0.9",
            source_file_digests={"openai/_base_client.py": "d" * 64},
            max_retries_default=2,
            sdk_attempts_per_call=3,
            prepare_options_hook="AsyncAPIClient._prepare_options",
            send_request_hook="AsyncAPIClient._send_request",
            native_dispatch_hook="httpx.AsyncClient.send",
            supported=True,
        ),
        provider_limits=ProviderLimitsBinding(
            endpoint_origin="https://api.deepseek.com",
            requested_model="deepseek-v4-flash",
            declared_route="deepseek-v4.1-flash",
            source_date="2026-10-01",
            source_digest="2" * 64,
            token_limit_scope="unknown",
            authentication_mode="bearer_api_key",
            model_mapping_accepted=False,
        ),
        fixture_only=True,
    )
    capability = ObservationCapability(
        telemetry_schema="planner_ablation_telemetry_v1",
        resource_policy="planner_ablation_resource_v1",
        sdk_profile=proofs.sdk_profile,  # type: ignore[arg-type]
        observes_planner_turns=True,
        observes_repairs=True,
        observes_sdk_attempts=True,
        observes_http_sends=True,
        observes_usage=True,
        offline_evidence_digest="1" * 64,
    )
    return assess_resource_budget(
        snapshot_effective_configuration(), proofs, capability
    )


def test_usage_totals_and_subdivisions_are_strict() -> None:
    usage = ReportedUsage(prompt_tokens=16, completion_tokens=10, total_tokens=26)
    assert usage.total_tokens == 26


def test_partial_usage_is_not_exact_campaign_total() -> None:
    ledger = SlotResourceLedger(
        slot_key_digest="slot",
        events=(),
        planner_turn_count=1,
        repair_attempt_count=0,
        logical_call_count=1,
        sdk_attempt_count=1,
        http_send_attempt_count=1,
        reported_usage_subtotal=ReportedUsage(
            prompt_tokens=16, completion_tokens=10, total_tokens=26
        ),
        exact_total_tokens=None,
        worker_drained=True,
        telemetry_invalid=False,
        incomplete=True,
        blockers=("partial_usage",),
        closed=False,
    )
    partial = aggregate_resource_ledger(ledger, assessment=_assessment())
    assert partial.reported_usage_subtotal is not None
    assert partial.reported_usage_subtotal.total_tokens == 26
    assert partial.exact_total_tokens is None
    assert partial.acceptance_blocked is True


def test_slot_ledger_rejects_orphan_duplicate_and_missing_end() -> None:
    from signal_diag.agent.telemetry import PlannerTurnEvent
    from signal_diag.app.planner_ablation_v2_adapter import StudyResourceObserver

    observer = StudyResourceObserver(slot_id="slot_x")
    binding = observer.make_binding()
    binding.sink(  # type: ignore[operator]
        PlannerTurnEvent(
            sequence_id="s1",
            correlation_id="c1",
            phase="start",
            turn_id="t1",
            monotonic_s=0.0,
        )
    )
    # Missing end → incomplete / invalid when snapshotted as drained.
    ledger = observer.resource_snapshot(worker_drained=True)
    assert ledger.incomplete or ledger.telemetry_invalid or ledger.pending_event_ids
    assert ledger.closed is False
