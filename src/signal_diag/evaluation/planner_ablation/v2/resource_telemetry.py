"""Pure resource ledger aggregation for planner-ablation resource policy v1."""

from __future__ import annotations

from signal_diag.evaluation.planner_ablation.v2.resource_models import (
    ReportedUsage,
    ResourceAssessment,
    ResourceObservation,
    SlotResourceLedger,
)


def _per_slot_sdk_ceiling(assessment: ResourceAssessment) -> int | None:
    if assessment.sdk_attempt_ceiling_per_slot is not None:
        return assessment.sdk_attempt_ceiling_per_slot
    if (
        assessment.planner_turn_ceiling is not None
        and assessment.sdk_attempt_factor is not None
    ):
        return assessment.planner_turn_ceiling * assessment.sdk_attempt_factor
    return None


def _per_slot_http_ceiling(assessment: ResourceAssessment) -> int | None:
    if assessment.http_send_ceiling_per_slot is not None:
        return assessment.http_send_ceiling_per_slot
    per_sdk = _per_slot_sdk_ceiling(assessment)
    if per_sdk is not None and assessment.http_send_factor is not None:
        return per_sdk * assessment.http_send_factor
    return None


def _event_kind(event: dict[str, object]) -> str:
    return str(event.get("kind") or "")


def _event_phase(event: dict[str, object]) -> str:
    return str(event.get("phase") or "")


def derive_counts_from_events(
    events: tuple[dict[str, object], ...],
) -> dict[str, int]:
    """Derive named-unit counts from the full event graph (start phases)."""
    return {
        "planner_turn_count": sum(
            1
            for event in events
            if _event_kind(event) == "planner_turn" and _event_phase(event) == "start"
        ),
        "repair_attempt_count": sum(
            1 for event in events if _event_kind(event) == "repair"
        ),
        "logical_call_count": sum(
            1
            for event in events
            if _event_kind(event) == "logical_call" and _event_phase(event) == "start"
        ),
        "sdk_attempt_count": sum(
            1
            for event in events
            if _event_kind(event) == "sdk_attempt" and _event_phase(event) == "start"
        ),
        "http_send_attempt_count": sum(
            1
            for event in events
            if _event_kind(event) == "http_send" and _event_phase(event) == "start"
        ),
    }


def _derive_usage_from_events(
    events: tuple[dict[str, object], ...],
) -> tuple[ReportedUsage | None, bool, dict[str, dict[str, object]]]:
    """Return (subtotal, all_complete_objects, usage_by_send_link)."""
    usages: list[ReportedUsage] = []
    usage_by_send: dict[str, dict[str, object]] = {}
    complete_objects = True
    for event in events:
        if _event_kind(event) != "usage":
            continue
        status = event.get("status")
        if status != "complete":
            complete_objects = False
            continue
        prompt = event.get("prompt_tokens")
        completion = event.get("completion_tokens")
        total = event.get("total_tokens")
        if not (
            isinstance(prompt, int)
            and isinstance(completion, int)
            and isinstance(total, int)
            and not isinstance(prompt, bool)
            and not isinstance(completion, bool)
            and not isinstance(total, bool)
        ):
            complete_objects = False
            continue
        cache_hit_raw = event.get("cache_hit_tokens")
        cache_miss_raw = event.get("cache_miss_tokens")
        reasoning_raw = event.get("reasoning_tokens")
        cache_hit = cache_hit_raw if isinstance(cache_hit_raw, int) else None
        cache_miss = cache_miss_raw if isinstance(cache_miss_raw, int) else None
        reasoning = reasoning_raw if isinstance(reasoning_raw, int) else None
        try:
            reported = ReportedUsage(
                prompt_tokens=prompt,
                completion_tokens=completion,
                total_tokens=total,
                cache_hit_tokens=cache_hit,
                cache_miss_tokens=cache_miss,
                reasoning_tokens=reasoning,
            )
        except Exception:  # noqa: BLE001
            complete_objects = False
            continue
        usages.append(reported)
        link = event.get("send_id") or event.get("call_id")
        if isinstance(link, str) and link:
            usage_by_send[link] = event
    return sum_reported_usage(usages), complete_objects, usage_by_send


def _http_end_events(
    events: tuple[dict[str, object], ...],
) -> list[dict[str, object]]:
    return [
        event
        for event in events
        if _event_kind(event) == "http_send" and _event_phase(event) == "end"
    ]


def admitted_per_send_token_ceilings(
    assessment: ResourceAssessment,
) -> tuple[int | None, int | None]:
    """Campaign ceilings divided into per-send reservations when the split is exact."""
    input_ceiling = assessment.input_token_ceiling
    output_ceiling = assessment.output_token_ceiling
    http_ceiling = assessment.http_send_ceiling
    per_send_input: int | None = None
    per_send_output: int | None = None
    if (
        isinstance(input_ceiling, int)
        and not isinstance(input_ceiling, bool)
        and isinstance(http_ceiling, int)
        and not isinstance(http_ceiling, bool)
        and http_ceiling > 0
        and input_ceiling % http_ceiling == 0
    ):
        per_send_input = input_ceiling // http_ceiling
    if (
        isinstance(output_ceiling, int)
        and not isinstance(output_ceiling, bool)
        and isinstance(http_ceiling, int)
        and not isinstance(http_ceiling, bool)
        and http_ceiling > 0
        and output_ceiling % http_ceiling == 0
    ):
        per_send_output = output_ceiling // http_ceiling
    return per_send_input, per_send_output


def _campaign_token_budget(assessment: ResourceAssessment) -> int | None:
    parts: list[int] = []
    if isinstance(assessment.input_token_ceiling, int) and not isinstance(
        assessment.input_token_ceiling, bool
    ):
        parts.append(assessment.input_token_ceiling)
    if isinstance(assessment.output_token_ceiling, int) and not isinstance(
        assessment.output_token_ceiling, bool
    ):
        parts.append(assessment.output_token_ceiling)
    if not parts:
        return None
    return sum(parts)


def _http_end_lacks_complete_usage(
    send: dict[str, object],
    usage_by_send: dict[str, dict[str, object]],
) -> bool:
    link = send.get("send_id") or send.get("correlation_id")
    if not isinstance(link, str) or not link:
        return True
    matched = usage_by_send.get(link)
    return matched is None or matched.get("status") != "complete"


def _compute_potential_token_exposure(
    *,
    http_ends: list[dict[str, object]],
    usage_by_send: dict[str, dict[str, object]],
    assessment: ResourceAssessment,
) -> int | None:
    """Reserve admitted per-send ceilings for sends without complete usage."""
    per_send_input, per_send_output = admitted_per_send_token_ceilings(assessment)
    if per_send_input is None and per_send_output is None:
        return None

    exposure = 0
    any_unknown = False
    for send in http_ends:
        link = send.get("send_id") or send.get("correlation_id")
        if not isinstance(link, str) or not link:
            any_unknown = True
            continue
        matched = usage_by_send.get(link)
        if matched is not None and matched.get("status") == "complete":
            continue
        # Redirect label alone is not a zero-use proof; reserve ceilings when known.
        outcome = send.get("outcome")
        if outcome == "redirect" or matched is None or matched.get("status") != "complete":
            if per_send_input is not None:
                exposure += per_send_input
            if per_send_output is not None:
                exposure += per_send_output
            any_unknown = True
            continue
        any_unknown = True
    if not any_unknown:
        return 0
    if per_send_input is None and per_send_output is None:
        return None
    return exposure


def _validate_response_models(
    events: tuple[dict[str, object], ...],
    assessment: ResourceAssessment,
    blockers: list[str],
) -> None:
    allowed = assessment.allowed_response_models
    if not allowed:
        return
    for event in events:
        if _event_kind(event) != "usage":
            continue
        model = event.get("response_model")
        if model is None:
            continue
        if not isinstance(model, str) or model not in allowed:
            blockers.append(f"response_model_outside_policy:{model}")


def aggregate_resource_ledger(
    ledger: SlotResourceLedger,
    *,
    assessment: ResourceAssessment,
) -> ResourceObservation:
    """Validate counts/usage closure from the event graph; never invent zeros."""
    blockers = list(ledger.blockers)
    if assessment.execution_blocked:
        blockers.append("resource_assessment_execution_blocked")
        blockers.extend(assessment.blockers)
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
    if not ledger.run_id:
        blockers.append("missing_run_id_association")

    derived = derive_counts_from_events(ledger.events)
    for field, derived_count in derived.items():
        claimed = getattr(ledger, field)
        if claimed is None:
            # Unknown caller summaries cannot become silent zeros for acceptance.
            blockers.append(f"unknown_count:{field}")
        elif claimed != derived_count:
            blockers.append(f"count_summary_mismatch:{field}")

    usage_subtotal, usage_complete, usage_by_send = _derive_usage_from_events(
        ledger.events
    )
    if (
        ledger.reported_usage_subtotal is not None
        and usage_subtotal is not None
        and ledger.reported_usage_subtotal.model_dump(mode="json")
        != usage_subtotal.model_dump(mode="json")
    ):
        blockers.append("usage_subtotal_recompute_mismatch")
    if ledger.reported_usage_subtotal is not None and usage_subtotal is None:
        blockers.append("usage_subtotal_recompute_mismatch")

    http_ends = _http_end_events(ledger.events)
    send_coverage_complete = True
    for send in http_ends:
        outcome = send.get("outcome")
        link = send.get("send_id") or send.get("correlation_id")
        # Redirect hops are observed sends but are not completion usage and are
        # not an approved zero-use proof. They reserve exposure separately and
        # do not satisfy per-send usage coverage for exact totals.
        if outcome == "redirect":
            continue
        if not isinstance(link, str) or not link:
            send_coverage_complete = False
            blockers.append("http_send_missing_link")
            continue
        matched = usage_by_send.get(link)
        if matched is None or matched.get("status") != "complete":
            send_coverage_complete = False
            blockers.append(f"incomplete_send_usage_coverage:{link}")

    logical = derived["logical_call_count"]
    http_count = derived["http_send_attempt_count"]
    if logical > 0 and http_count == 0 and not any(
        _event_kind(event) == "usage" for event in ledger.events
    ):
        send_coverage_complete = False
        blockers.append("logical_call_without_send_or_usage_proof")
    if logical > 0 and http_count == 0 and usage_subtotal is not None:
        # Usage without observed HTTP dispatch (mounted/proxy miss) is invalid.
        blockers.append("usage_without_http_dispatch_observation")
        send_coverage_complete = False

    exposure = _compute_potential_token_exposure(
        http_ends=http_ends,
        usage_by_send=usage_by_send,
        assessment=assessment,
    )
    if (
        ledger.potential_token_exposure is not None
        and exposure is not None
        and ledger.potential_token_exposure != exposure
    ):
        blockers.append("potential_token_exposure_mismatch")
    incomplete_sends = [
        send
        for send in http_ends
        if _http_end_lacks_complete_usage(send, usage_by_send)
    ]
    if incomplete_sends and exposure is None:
        blockers.append("unknown_token_exposure_for_incomplete_send")
    token_budget = _campaign_token_budget(assessment)
    if (
        exposure is not None
        and token_budget is not None
        and exposure > token_budget
    ):
        blockers.append("potential_token_exposure_exceeds_campaign_ceiling")
    if usage_subtotal is not None:
        if (
            isinstance(assessment.input_token_ceiling, int)
            and not isinstance(assessment.input_token_ceiling, bool)
            and usage_subtotal.prompt_tokens > assessment.input_token_ceiling
        ):
            blockers.append("input_token_ceiling_exceeded")
        if (
            isinstance(assessment.output_token_ceiling, int)
            and not isinstance(assessment.output_token_ceiling, bool)
            and usage_subtotal.completion_tokens > assessment.output_token_ceiling
        ):
            blockers.append("output_token_ceiling_exceeded")
    exact_total = ledger.exact_total_tokens
    if (
        exact_total is not None
        and token_budget is not None
        and exact_total > token_budget
    ):
        blockers.append("exact_token_total_exceeds_campaign_ceiling")

    # Exact totals require complete per-send usage coverage derived from events.
    if exact_total is not None:
        if not (
            usage_complete
            and send_coverage_complete
            and usage_subtotal is not None
            and exact_total == usage_subtotal.total_tokens
            and not ledger.pending_event_ids
            and ledger.worker_drained
            and not ledger.telemetry_invalid
        ):
            # Fixed zero-use: empty event graph with proven zeros may keep exact 0.
            fixed_zero = (
                exact_total == 0
                and not ledger.events
                and all(value == 0 for value in derived.values())
                and ledger.worker_drained
                and not ledger.pending_event_ids
                and not ledger.telemetry_invalid
                and all(
                    getattr(ledger, field) == 0
                    for field in derived
                )
            )
            if not fixed_zero:
                blockers.append("exact_total_not_event_justified")
    elif usage_subtotal is not None:
        blockers.append("partial_usage_not_exact_total")

    # Per-slot ceilings (never compare a single slot to campaign-wide totals).
    if (
        assessment.planner_turn_ceiling is not None
        and derived["planner_turn_count"] > assessment.planner_turn_ceiling
    ):
        blockers.append("planner_turn_ceiling_exceeded")
    per_slot_sdk = _per_slot_sdk_ceiling(assessment)
    if per_slot_sdk is not None and derived["sdk_attempt_count"] > per_slot_sdk:
        blockers.append("sdk_attempt_ceiling_exceeded")
    per_slot_http = _per_slot_http_ceiling(assessment)
    if per_slot_http is not None and derived["http_send_attempt_count"] > per_slot_http:
        blockers.append("http_send_ceiling_exceeded")

    if (
        assessment.sdk_attempt_ceiling is not None
        and per_slot_sdk is not None
        and assessment.sdk_attempt_ceiling < per_slot_sdk
    ):
        blockers.append("campaign_sdk_ceiling_inconsistent")

    _validate_response_models(ledger.events, assessment, blockers)

    unique = tuple(dict.fromkeys(blockers))
    acceptance_blocked = bool(unique) or ledger.incomplete or ledger.telemetry_invalid
    return ResourceObservation(
        planner_turn_count=derived["planner_turn_count"],
        repair_attempt_count=derived["repair_attempt_count"],
        logical_call_count=derived["logical_call_count"],
        sdk_attempt_count=derived["sdk_attempt_count"],
        http_send_attempt_count=derived["http_send_attempt_count"],
        reported_usage_subtotal=usage_subtotal,
        exact_total_tokens=exact_total if "exact_total_not_event_justified" not in unique else None,
        potential_token_exposure=exposure,
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
    if (
        observation.sdk_attempt_count is not None
        and observation.http_send_attempt_count is not None
        and observation.sdk_attempt_count == observation.http_send_attempt_count
    ):
        transport = observation.http_send_attempt_count
    elif (
        observation.sdk_attempt_count is not None
        or observation.http_send_attempt_count is not None
    ):
        unknown.append("transport_attempt_count")
    input_tokens = None
    output_tokens = None
    total_tokens = None
    if observation.exact_total_tokens is not None:
        total_tokens = observation.exact_total_tokens
        if observation.reported_usage_subtotal is not None:
            input_tokens = observation.reported_usage_subtotal.prompt_tokens
            output_tokens = observation.reported_usage_subtotal.completion_tokens
    else:
        unknown.extend(["input_tokens", "output_tokens", "total_tokens"])
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


def validate_campaign_resource_totals(
    observations: list[ResourceObservation],
    *,
    assessment: ResourceAssessment,
) -> tuple[str, ...]:
    """Validate summed campaign totals against campaign-wide ceilings."""
    blockers: list[str] = []
    sdk_values: list[int] = []
    http_values: list[int] = []
    turn_values: list[int] = []
    for observation in observations:
        if observation.sdk_attempt_count is None:
            blockers.append("campaign_unknown_sdk_attempt_count")
        else:
            sdk_values.append(observation.sdk_attempt_count)
        if observation.http_send_attempt_count is None:
            blockers.append("campaign_unknown_http_send_attempt_count")
        else:
            http_values.append(observation.http_send_attempt_count)
        if observation.planner_turn_count is None:
            blockers.append("campaign_unknown_planner_turn_count")
        else:
            turn_values.append(observation.planner_turn_count)
    token_blockers = _campaign_reported_token_blockers(observations, assessment)
    if blockers:
        return tuple(dict.fromkeys([*blockers, *token_blockers]))
    sdk_total = sum(sdk_values)
    http_total = sum(http_values)
    turn_total = sum(turn_values)
    if (
        assessment.logical_call_ceiling is not None
        and turn_total > assessment.logical_call_ceiling
    ):
        blockers.append("campaign_planner_turn_ceiling_exceeded")
    if (
        assessment.sdk_attempt_ceiling is not None
        and sdk_total > assessment.sdk_attempt_ceiling
    ):
        blockers.append("campaign_sdk_attempt_ceiling_exceeded")
    if (
        assessment.http_send_ceiling is not None
        and http_total > assessment.http_send_ceiling
    ):
        blockers.append("campaign_http_send_ceiling_exceeded")
    blockers.extend(token_blockers)
    return tuple(dict.fromkeys(blockers))


def _campaign_reported_token_blockers(
    observations: list[ResourceObservation],
    assessment: ResourceAssessment,
) -> list[str]:
    """Sum reported prompt/completion and exact totals against campaign ceilings."""
    blockers: list[str] = []
    prompt = 0
    completion = 0
    exact = 0
    saw_reported = False
    saw_exact = False
    for observation in observations:
        usage = observation.reported_usage_subtotal
        if usage is not None:
            saw_reported = True
            prompt += usage.prompt_tokens
            completion += usage.completion_tokens
        if observation.exact_total_tokens is not None:
            saw_exact = True
            exact += observation.exact_total_tokens
    input_ceiling = assessment.input_token_ceiling
    output_ceiling = assessment.output_token_ceiling
    if (
        isinstance(input_ceiling, int)
        and not isinstance(input_ceiling, bool)
        and saw_reported
        and prompt > input_ceiling
    ):
        blockers.append("campaign_input_token_ceiling_exceeded")
    if (
        isinstance(output_ceiling, int)
        and not isinstance(output_ceiling, bool)
        and saw_reported
        and completion > output_ceiling
    ):
        blockers.append("campaign_output_token_ceiling_exceeded")
    budget = _campaign_token_budget(assessment)
    if saw_exact and budget is not None and exact > budget:
        blockers.append("campaign_exact_token_ceiling_exceeded")
    return blockers
