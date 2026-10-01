"""Pure resource ledger aggregation for planner-ablation resource policy v1."""

from __future__ import annotations

from signal_diag.evaluation.planner_ablation.v2.resource_models import (
    ReportedUsage,
    ResourceAssessment,
    ResourceObservation,
    SlotResourceLedger,
)


def aggregate_resource_ledger(
    ledger: SlotResourceLedger,
    *,
    assessment: ResourceAssessment,
) -> ResourceObservation:
    """Validate counts/usage closure; never invent exact totals from partials."""
    blockers = list(ledger.blockers)
    if ledger.telemetry_invalid:
        blockers.append("telemetry_invalid")
    if not ledger.worker_drained:
        blockers.append("worker_not_drained")
    if ledger.pending_event_ids:
        blockers.append("pending_events")
    if ledger.incomplete:
        blockers.append("ledger_incomplete")
    if not ledger.closed:
        blockers.append("ledger_not_closed")

    if (
        assessment.planner_turn_ceiling is not None
        and ledger.planner_turn_count is not None
        and ledger.planner_turn_count > assessment.planner_turn_ceiling
    ):
        blockers.append("planner_turn_ceiling_exceeded")
    if (
        assessment.sdk_attempt_ceiling is not None
        and ledger.sdk_attempt_count is not None
        and ledger.sdk_attempt_count > assessment.sdk_attempt_ceiling
    ):
        blockers.append("sdk_attempt_ceiling_exceeded")
    if (
        assessment.http_send_ceiling is not None
        and ledger.http_send_attempt_count is not None
        and ledger.http_send_attempt_count > assessment.http_send_ceiling
    ):
        blockers.append("http_send_ceiling_exceeded")

    exact_total = ledger.exact_total_tokens
    subtotal = ledger.reported_usage_subtotal
    # Partial known usage never becomes an exact campaign/slot total.
    if exact_total is None and subtotal is not None:
        blockers.append("partial_usage_not_exact_total")

    unique = tuple(dict.fromkeys(blockers))
    acceptance_blocked = bool(unique) or ledger.incomplete or ledger.telemetry_invalid
    return ResourceObservation(
        planner_turn_count=ledger.planner_turn_count,
        repair_attempt_count=ledger.repair_attempt_count,
        logical_call_count=ledger.logical_call_count,
        sdk_attempt_count=ledger.sdk_attempt_count,
        http_send_attempt_count=ledger.http_send_attempt_count,
        reported_usage_subtotal=subtotal,
        exact_total_tokens=exact_total,
        potential_token_exposure=ledger.potential_token_exposure,
        acceptance_blocked=acceptance_blocked,
        blockers=unique,
        telemetry_invalid=ledger.telemetry_invalid,
        incomplete=ledger.incomplete or not ledger.closed,
    )


def project_legacy_resource_telemetry(
    observation: ResourceObservation,
    *,
    tool_call_count: int | None = None,
    rule_evaluation_count: int | None = None,
    fixed_zero_use: bool = False,
) -> dict[str, object]:
    """Project named units into legacy ResourceTelemetry fields."""
    if fixed_zero_use:
        return {
            "planner_call_count": 0,
            "tool_call_count": tool_call_count,
            "rule_evaluation_count": rule_evaluation_count,
            "repair_attempt_count": 0,
            "transport_attempt_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "unknown_fields": (),
        }
    unknown: list[str] = []
    transport = None
    # Ambiguous nonzero transport_attempt_count stays unknown rather than redefined.
    if observation.sdk_attempt_count is None and observation.http_send_attempt_count is None or (
        observation.sdk_attempt_count is not None
        and observation.http_send_attempt_count is not None
        and observation.sdk_attempt_count != observation.http_send_attempt_count
    ):
        unknown.append("transport_attempt_count")
    else:
        transport = observation.sdk_attempt_count or observation.http_send_attempt_count

    input_tokens = None
    output_tokens = None
    total_tokens = observation.exact_total_tokens
    if total_tokens is None:
        unknown.extend(["input_tokens", "output_tokens", "total_tokens"])
    elif observation.reported_usage_subtotal is not None:
        input_tokens = observation.reported_usage_subtotal.prompt_tokens
        output_tokens = observation.reported_usage_subtotal.completion_tokens

    if observation.planner_turn_count is None:
        unknown.append("planner_call_count")
    if observation.repair_attempt_count is None:
        unknown.append("repair_attempt_count")

    return {
        "planner_call_count": observation.planner_turn_count,
        "tool_call_count": tool_call_count,
        "rule_evaluation_count": rule_evaluation_count,
        "repair_attempt_count": observation.repair_attempt_count,
        "transport_attempt_count": transport,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "unknown_fields": tuple(dict.fromkeys(unknown)),
    }


def sum_reported_usage(usages: list[ReportedUsage]) -> ReportedUsage | None:
    if not usages:
        return None
    prompt = sum(u.prompt_tokens for u in usages)
    completion = sum(u.completion_tokens for u in usages)
    return ReportedUsage(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=prompt + completion,
    )
