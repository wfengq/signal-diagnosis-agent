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
    with_sub = ReportedUsage(
        prompt_tokens=16,
        completion_tokens=10,
        total_tokens=26,
        cache_hit_tokens=4,
        cache_miss_tokens=12,
        reasoning_tokens=3,
    )
    assert with_sub.cache_hit_tokens == 4
    try:
        ReportedUsage(
            prompt_tokens=16,
            completion_tokens=10,
            total_tokens=26,
            cache_hit_tokens=4,
            cache_miss_tokens=11,
        )
        raised = False
    except Exception:  # noqa: BLE001
        raised = True
    assert raised


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


def test_per_slot_ceiling_not_campaign_ceiling() -> None:
    assessment = _assessment()
    # Campaign SDK ceiling is 57*28*3; a single slot with 85 attempts exceeds
    # per-slot 28*3=84 even though it is far below the campaign total.
    ledger = SlotResourceLedger(
        slot_key_digest="slot",
        events=(),
        planner_turn_count=28,
        repair_attempt_count=0,
        logical_call_count=28,
        sdk_attempt_count=85,
        http_send_attempt_count=85,
        worker_drained=True,
        telemetry_invalid=False,
        incomplete=False,
        closed=True,
        exact_total_tokens=0,
    )
    obs = aggregate_resource_ledger(ledger, assessment=assessment)
    assert "sdk_attempt_ceiling_exceeded" in obs.blockers
    assert assessment.sdk_attempt_ceiling == 57 * 28 * 3
    assert assessment.sdk_attempt_ceiling_per_slot == 28 * 3


def test_slot_ledger_rejects_orphan_duplicate_and_missing_end() -> None:
    from signal_diag.agent.telemetry import (
        LogicalCallEvent,
        PlannerTurnEvent,
        UsageObservation,
    )
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

    # Usage end + logical-call end sharing a parent call id must not false-duplicate.
    observer2 = StudyResourceObserver(slot_id="slot_y")
    binding2 = observer2.make_binding()
    call_id = "call_shared"
    for phase in ("start", "end"):
        binding2.sink(  # type: ignore[operator]
            LogicalCallEvent(
                sequence_id=f"lc_{phase}",
                correlation_id=call_id,
                phase=phase,  # type: ignore[arg-type]
                turn_id="t1",
                call_id=call_id,
                monotonic_s=0.0,
            )
        )
    binding2.sink(  # type: ignore[operator]
        UsageObservation(
            sequence_id="u1",
            correlation_id="usage_independent",
            phase="end",
            call_id=call_id,
            send_id="http_1",
            status="complete",
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
            monotonic_s=0.1,
        )
    )
    ledger2 = observer2.resource_snapshot(worker_drained=True)
    assert not any(
        isinstance(r, str) and r.startswith("duplicate_phase") for r in ledger2.blockers
    )


def test_forged_closed_flag_is_rejected_by_strict_ledger() -> None:
    try:
        SlotResourceLedger(
            slot_key_digest="forged",
            closed=True,
            incomplete=True,
            worker_drained=False,
        )
        raised = False
    except Exception:  # noqa: BLE001
        raised = True
    assert raised


def test_incomplete_send_coverage_keeps_exact_total_unknown() -> None:
    from signal_diag.agent.telemetry import HttpSendEvent, UsageObservation
    from signal_diag.app.planner_ablation_v2_adapter import StudyResourceObserver

    observer = StudyResourceObserver(slot_id="slot_cov")
    binding = observer.make_binding()
    # Two HTTP sends; usage only for the final one (500 then 200 pattern).
    for idx, outcome in enumerate(("http_error", "success")):
        send_id = f"http_{idx}"
        binding.sink(  # type: ignore[operator]
            HttpSendEvent(
                sequence_id=f"hs_{idx}",
                correlation_id=send_id,
                phase="start",
                send_id=send_id,
                monotonic_s=float(idx),
            )
        )
        binding.sink(  # type: ignore[operator]
            HttpSendEvent(
                sequence_id=f"he_{idx}",
                correlation_id=send_id,
                phase="end",
                send_id=send_id,
                outcome=outcome,  # type: ignore[arg-type]
                status_code=500 if outcome == "http_error" else 200,
                monotonic_s=float(idx) + 0.1,
            )
        )
    binding.sink(  # type: ignore[operator]
        UsageObservation(
            sequence_id="u_final",
            correlation_id="usage_final",
            send_id="http_1",
            status="complete",
            prompt_tokens=16,
            completion_tokens=10,
            total_tokens=26,
            monotonic_s=1.2,
        )
    )
    ledger = observer.resource_snapshot(worker_drained=True)
    assert ledger.reported_usage_subtotal is not None
    assert ledger.reported_usage_subtotal.total_tokens == 26
    assert ledger.exact_total_tokens is None
    assert any("incomplete_send_usage_coverage" in b for b in ledger.blockers)