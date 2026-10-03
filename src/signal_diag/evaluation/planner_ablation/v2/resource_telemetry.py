"""Pure resource ledger aggregation for planner-ablation resource policy v1."""

from __future__ import annotations

import math

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


_LIFECYCLE_KINDS = frozenset(
    {"planner_turn", "logical_call", "sdk_attempt", "http_send"}
)


def _nonempty_text(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _correlation_key(event: dict[str, object]) -> str:
    return str(event.get("correlation_id") or event.get("sequence_id") or "")


def _lifecycle_graph(
    events: tuple[dict[str, object], ...],
) -> tuple[tuple[str, ...], list[str]]:
    """Pair lifecycle starts with ends and reject broken parent links.

    Reviewed zero-use strings are not consulted here. Redirect coverage is a
    separate gate that stays blocked until a bound proof exists.
    """
    starts: dict[tuple[str, str], int] = {}
    ends: dict[tuple[str, str], int] = {}
    blockers: list[str] = []
    seen_sequence: set[str] = set()
    open_starts: dict[tuple[str, str], list[int]] = {}
    for index, event in enumerate(events):
        sequence_id = _nonempty_text(event.get("sequence_id"))
        if sequence_id is not None:
            if sequence_id in seen_sequence:
                blockers.append(f"duplicate_sequence_id:{sequence_id}")
            seen_sequence.add(sequence_id)
        kind = _event_kind(event)
        if kind not in _LIFECYCLE_KINDS:
            continue
        phase = _event_phase(event)
        correlation = _correlation_key(event)
        key = (kind, correlation)
        if phase == "start":
            starts[key] = starts.get(key, 0) + 1
            if starts[key] > 1:
                blockers.append(f"duplicate_lifecycle_phase:{kind}:{correlation}:start")
            open_starts.setdefault(key, []).append(index)
        elif phase == "end":
            ends[key] = ends.get(key, 0) + 1
            if ends[key] > 1:
                blockers.append(f"duplicate_lifecycle_phase:{kind}:{correlation}:end")
            stack = open_starts.get(key)
            if not stack:
                blockers.append(f"lifecycle_end_before_start:{kind}:{correlation}")
            else:
                stack.pop()
        else:
            blockers.append(f"unpaired_phase:{kind}:{correlation}")
    pending: list[str] = []
    for key, count in starts.items():
        end_count = ends.get(key, 0)
        if end_count == count:
            continue
        pending.append(f"{key[0]}:{key[1]}")
        if end_count < count:
            blockers.append(f"unpaired_start:{key[0]}:{key[1]}")
        else:
            blockers.append(f"unpaired_end:{key[0]}:{key[1]}")
    for key in ends:
        if key not in starts:
            pending.append(f"{key[0]}:{key[1]}")
            blockers.append(f"orphan_end:{key[0]}:{key[1]}")
    blockers.extend(_entity_lifecycle_blockers(events))
    blockers.extend(_parent_link_blockers(events))
    return tuple(dict.fromkeys(pending)), blockers


def _resolved_turn_id(event: dict[str, object]) -> str | None:
    return _nonempty_text(event.get("turn_id")) or _nonempty_text(
        event.get("correlation_id")
        if _event_kind(event) == "planner_turn"
        else None
    )


def _resolved_call_id(event: dict[str, object]) -> str | None:
    return _nonempty_text(event.get("call_id")) or (
        _nonempty_text(event.get("correlation_id"))
        if _event_kind(event) == "logical_call"
        else None
    )


def _resolved_attempt_id(event: dict[str, object]) -> str | None:
    return _nonempty_text(event.get("attempt_id")) or (
        _nonempty_text(event.get("correlation_id"))
        if _event_kind(event) == "sdk_attempt"
        else None
    )


def _resolved_send_id(event: dict[str, object]) -> str | None:
    return _nonempty_text(event.get("send_id")) or (
        _nonempty_text(event.get("correlation_id"))
        if _event_kind(event) == "http_send"
        else None
    )


def _monotonic(event: dict[str, object]) -> float | None:
    value = event.get("monotonic_s")
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    ):
        return float(value)
    return None


def _lifecycle_entity_id(event: dict[str, object]) -> str | None:
    kind = _event_kind(event)
    if kind == "planner_turn":
        return _resolved_turn_id(event)
    if kind == "logical_call":
        return _resolved_call_id(event)
    if kind == "sdk_attempt":
        return _resolved_attempt_id(event)
    if kind == "http_send":
        return _resolved_send_id(event)
    return None


def _entity_lifecycle_blockers(events: tuple[dict[str, object], ...]) -> list[str]:
    """Reject duplicate lifecycle phases and correlation drift for one entity id."""
    blockers: list[str] = []
    entity_correlation: dict[tuple[str, str], str] = {}
    entity_phase_counts: dict[tuple[str, str, str], int] = {}
    for event in events:
        kind = _event_kind(event)
        if kind not in _LIFECYCLE_KINDS:
            continue
        phase = _event_phase(event)
        if phase not in {"start", "end"}:
            continue
        entity_id = _lifecycle_entity_id(event)
        if entity_id is None:
            continue
        correlation = _correlation_key(event)
        entity_key = (kind, entity_id)
        seen_correlation = entity_correlation.get(entity_key)
        if seen_correlation is not None and seen_correlation != correlation:
            blockers.append(f"lifecycle_correlation_mismatch:{kind}:{entity_id}")
        else:
            entity_correlation.setdefault(entity_key, correlation)
        phase_key = (kind, entity_id, phase)
        entity_phase_counts[phase_key] = entity_phase_counts.get(phase_key, 0) + 1
        if entity_phase_counts[phase_key] > 1:
            blockers.append(
                f"duplicate_lifecycle_entity_phase:{kind}:{entity_id}:{phase}"
            )
    return blockers


def _graph_required(events: tuple[dict[str, object], ...]) -> bool:
    for event in events:
        kind = _event_kind(event)
        if kind in _LIFECYCLE_KINDS or kind == "usage":
            return True
    return False


def _self_bounds_blockers(
    meta: dict[str, dict[str, float | None]],
    kind: str,
) -> list[str]:
    blockers: list[str] = []
    for entity_id, bounds in meta.items():
        start = bounds.get("start")
        end = bounds.get("end")
        if start is not None and end is not None and end < start:
            blockers.append(f"event_graph_temporal:{kind}:{entity_id}:end_before_start")
    return blockers


def _parent_link_blockers(events: tuple[dict[str, object], ...]) -> list[str]:
    """Require full parent IDs and links when lifecycle or usage events exist."""
    if not _graph_required(events):
        return []

    blockers: list[str] = []
    turn_ids: set[str] = set()
    call_ids: set[str] = set()
    attempt_ids: set[str] = set()
    send_ids: set[str] = set()
    turn_meta: dict[str, dict[str, float | None]] = {}
    call_meta: dict[str, dict[str, float | None]] = {}
    attempt_meta: dict[str, dict[str, float | None]] = {}
    send_meta: dict[str, dict[str, float | None]] = {}
    call_turn: dict[str, str] = {}
    attempt_chain: dict[str, tuple[str, str]] = {}
    send_chain: dict[str, tuple[str, str, str]] = {}

    for event in events:
        kind = _event_kind(event)
        if kind not in _LIFECYCLE_KINDS and kind != "usage":
            continue
        label = kind if kind != "usage" else "usage"
        if _nonempty_text(event.get("sequence_id")) is None:
            blockers.append(f"missing_required_id:{label}:sequence_id")
        if _monotonic(event) is None:
            blockers.append(f"missing_required_monotonic:{label}")

    for event in events:
        kind = _event_kind(event)
        phase = _event_phase(event)
        if kind not in _LIFECYCLE_KINDS:
            continue
        if kind == "planner_turn":
            turn_id = _resolved_turn_id(event)
            if turn_id is None:
                blockers.append("missing_required_id:planner_turn:turn_id")
                continue
            if phase == "start":
                turn_ids.add(turn_id)
                turn_meta.setdefault(turn_id, {})["start"] = _monotonic(event)
            elif phase == "end":
                turn_meta.setdefault(turn_id, {})["end"] = _monotonic(event)
        elif kind == "logical_call":
            turn_id = _nonempty_text(event.get("turn_id"))
            call_id = _resolved_call_id(event)
            if turn_id is None:
                blockers.append("missing_required_id:logical_call:turn_id")
            if call_id is None:
                blockers.append("missing_required_id:logical_call:call_id")
                continue
            if turn_id is not None and turn_id not in turn_ids:
                blockers.append(f"logical_call_parent_missing:{turn_id}")
            if phase == "start":
                call_ids.add(call_id)
                if turn_id is not None:
                    call_turn[call_id] = turn_id
                call_meta.setdefault(call_id, {})["start"] = _monotonic(event)
            elif phase == "end":
                call_meta.setdefault(call_id, {})["end"] = _monotonic(event)
                if turn_id is not None:
                    expected_turn = call_turn.get(call_id)
                    if expected_turn is not None and expected_turn != turn_id:
                        blockers.append(f"logical_call_ancestry_mismatch:{call_id}")
        elif kind == "sdk_attempt":
            turn_id = _nonempty_text(event.get("turn_id"))
            call_id = _nonempty_text(event.get("call_id"))
            attempt_id = _resolved_attempt_id(event)
            if turn_id is None:
                blockers.append("missing_required_id:sdk_attempt:turn_id")
            if call_id is None:
                blockers.append("missing_required_id:sdk_attempt:call_id")
            if attempt_id is None:
                blockers.append("missing_required_id:sdk_attempt:attempt_id")
                continue
            if call_id is not None and call_id not in call_ids:
                blockers.append(f"sdk_attempt_parent_missing:{call_id}")
            if (
                call_id is not None
                and turn_id is not None
                and call_id in call_turn
                and turn_id != call_turn[call_id]
            ):
                blockers.append(f"sdk_attempt_ancestry_mismatch:{attempt_id}")
            if phase == "start":
                attempt_ids.add(attempt_id)
                if turn_id is not None and call_id is not None:
                    attempt_chain[attempt_id] = (turn_id, call_id)
                attempt_meta.setdefault(attempt_id, {})["start"] = _monotonic(event)
            elif phase == "end":
                attempt_meta.setdefault(attempt_id, {})["end"] = _monotonic(event)
                expected = attempt_chain.get(attempt_id)
                if expected is not None and (
                    turn_id != expected[0] or call_id != expected[1]
                ):
                    blockers.append(f"sdk_attempt_ancestry_mismatch:{attempt_id}")
        elif kind == "http_send":
            turn_id = _nonempty_text(event.get("turn_id"))
            call_id = _nonempty_text(event.get("call_id"))
            attempt_id = _nonempty_text(event.get("attempt_id"))
            send_id = _resolved_send_id(event)
            if turn_id is None:
                blockers.append("missing_required_id:http_send:turn_id")
            if call_id is None:
                blockers.append("missing_required_id:http_send:call_id")
            if attempt_id is None:
                blockers.append("missing_required_id:http_send:attempt_id")
            if send_id is None:
                blockers.append("missing_required_id:http_send:send_id")
                continue
            if attempt_id is not None and attempt_id not in attempt_ids:
                blockers.append(f"http_send_parent_missing:{attempt_id}")
            elif attempt_id is not None:
                expected = attempt_chain.get(attempt_id)
                if expected is not None and (
                    turn_id != expected[0] or call_id != expected[1]
                ):
                    blockers.append(f"http_send_ancestry_mismatch:{send_id}")
            if phase == "start":
                send_ids.add(send_id)
                if (
                    turn_id is not None
                    and call_id is not None
                    and attempt_id is not None
                ):
                    send_chain[send_id] = (turn_id, call_id, attempt_id)
                send_meta.setdefault(send_id, {})["start"] = _monotonic(event)
            elif phase == "end":
                send_meta.setdefault(send_id, {})["end"] = _monotonic(event)
                expected_send = send_chain.get(send_id)
                if expected_send is not None and (
                    turn_id != expected_send[0]
                    or call_id != expected_send[1]
                    or attempt_id != expected_send[2]
                ):
                    blockers.append(f"http_send_ancestry_mismatch:{send_id}")

    for event in events:
        if _event_kind(event) != "usage":
            continue
        send_id = _nonempty_text(event.get("send_id"))
        call_id = _nonempty_text(event.get("call_id"))
        attempt_id = _nonempty_text(event.get("attempt_id"))
        turn_id = _nonempty_text(event.get("turn_id"))
        if send_id is None:
            blockers.append("missing_required_id:usage:send_id")
            continue
        if call_id is None:
            blockers.append("missing_required_id:usage:call_id")
        if attempt_id is None:
            blockers.append("missing_required_id:usage:attempt_id")
        if turn_id is None:
            blockers.append("missing_required_id:usage:turn_id")
        if send_id not in send_ids:
            blockers.append(f"usage_without_send:{send_id}")
        if call_id is not None and call_id not in call_ids:
            blockers.append(f"usage_parent_missing_call:{call_id}")
        elif call_id is not None and turn_id is not None:
            expected_turn = call_turn.get(call_id)
            if expected_turn is not None and expected_turn != turn_id:
                blockers.append(f"usage_ancestry_mismatch:{send_id}")
        if attempt_id is not None and attempt_id not in attempt_ids:
            blockers.append(f"usage_parent_missing_attempt:{attempt_id}")
        if turn_id is not None and turn_id not in turn_ids:
            blockers.append(f"usage_parent_missing_turn:{turn_id}")
        expected_send = send_chain.get(send_id)
        if expected_send is not None and (
            turn_id != expected_send[0]
            or call_id != expected_send[1]
            or attempt_id != expected_send[2]
        ):
            blockers.append(f"usage_ancestry_mismatch:{send_id}")

    blockers.extend(_self_bounds_blockers(turn_meta, "planner_turn"))
    blockers.extend(_self_bounds_blockers(call_meta, "logical_call"))
    blockers.extend(_self_bounds_blockers(attempt_meta, "sdk_attempt"))
    blockers.extend(_self_bounds_blockers(send_meta, "http_send"))

    def _order_blocker(parent: str, child: str, reason: str) -> None:
        blockers.append(f"event_graph_temporal:{parent}:{child}:{reason}")

    for event in events:
        kind = _event_kind(event)
        phase = _event_phase(event)
        mono = _monotonic(event)
        if mono is None:
            continue
        if kind == "logical_call" and phase == "start":
            turn_id = _nonempty_text(event.get("turn_id"))
            call_id = _resolved_call_id(event)
            if turn_id is not None:
                t_start = turn_meta.get(turn_id, {}).get("start")
                if t_start is not None and mono < t_start:
                    _order_blocker(
                        "planner_turn",
                        call_id or "call",
                        "child_before_parent_start",
                    )
            if call_id is not None:
                t_end = turn_meta.get(turn_id or "", {}).get("end")
                if t_end is not None and mono > t_end:
                    _order_blocker("planner_turn", call_id, "child_after_parent_end")
        if kind == "logical_call" and phase == "end":
            call_id = _resolved_call_id(event)
            turn_id = _nonempty_text(event.get("turn_id"))
            c_start = call_meta.get(call_id or "", {}).get("start")
            if c_start is not None and mono < c_start:
                _order_blocker("logical_call", call_id or "call", "end_before_start")
            if turn_id is not None:
                t_bounds = turn_meta.get(turn_id, {})
                t_start = t_bounds.get("start")
                if t_start is not None and mono < t_start:
                    _order_blocker(
                        "planner_turn",
                        call_id or "call",
                        "child_before_parent_start",
                    )
                t_end = t_bounds.get("end")
                if t_end is not None and mono > t_end:
                    _order_blocker(
                        "planner_turn",
                        call_id or "call",
                        "child_after_parent_end",
                    )
        if kind == "sdk_attempt" and phase == "start":
            call_id = _nonempty_text(event.get("call_id"))
            attempt_id = _resolved_attempt_id(event)
            if call_id is not None:
                c_start = call_meta.get(call_id, {}).get("start")
                if c_start is not None and mono < c_start:
                    _order_blocker(
                        "logical_call",
                        attempt_id or "attempt",
                        "child_before_parent_start",
                    )
        if kind == "sdk_attempt" and phase == "end":
            attempt_id = _resolved_attempt_id(event)
            call_id = _nonempty_text(event.get("call_id"))
            turn_id = _nonempty_text(event.get("turn_id"))
            a_start = attempt_meta.get(attempt_id or "", {}).get("start")
            if a_start is not None and mono < a_start:
                _order_blocker("sdk_attempt", attempt_id or "attempt", "end_before_start")
            if call_id is not None:
                c_bounds = call_meta.get(call_id, {})
                c_end = c_bounds.get("end")
                if c_end is not None and mono > c_end:
                    _order_blocker(
                        "logical_call",
                        attempt_id or "attempt",
                        "child_after_parent_end",
                    )
            if turn_id is not None:
                t_end = turn_meta.get(turn_id, {}).get("end")
                if t_end is not None and mono > t_end:
                    _order_blocker(
                        "planner_turn",
                        attempt_id or "attempt",
                        "child_after_parent_end",
                    )
        if kind == "http_send":
            attempt_id = _nonempty_text(event.get("attempt_id"))
            send_id = _resolved_send_id(event) or "send"
            if attempt_id is not None:
                a_meta = attempt_meta.get(attempt_id, {})
                if phase == "start":
                    a_start = a_meta.get("start")
                    if a_start is not None and mono < a_start:
                        _order_blocker("sdk_attempt", send_id, "child_before_parent_start")
                if phase == "end":
                    a_end = a_meta.get("end")
                    s_start = send_meta.get(send_id, {}).get("start")
                    if s_start is not None and mono < s_start:
                        _order_blocker("http_send", send_id, "end_before_start")
                    if a_end is not None and mono > a_end:
                        _order_blocker("sdk_attempt", send_id, "child_after_parent_end")
        if kind == "usage":
            send_id = _nonempty_text(event.get("send_id"))
            attempt_id = _nonempty_text(event.get("attempt_id"))
            if send_id is not None:
                s_start = send_meta.get(send_id, {}).get("start")
                if s_start is not None and mono < s_start:
                    blockers.append(f"usage_temporal_outside_send:{send_id}")
            if attempt_id is not None:
                a_start = attempt_meta.get(attempt_id, {}).get("start")
                if a_start is not None and mono < a_start:
                    blockers.append(
                        f"usage_temporal_outside_attempt:{send_id or attempt_id}"
                    )

    return blockers


def _zero_usage(usage: ReportedUsage | None) -> bool:
    return (
        usage is not None
        and usage.prompt_tokens == 0
        and usage.completion_tokens == 0
        and usage.total_tokens == 0
    )


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
) -> tuple[ReportedUsage | None, bool, dict[str, dict[str, object]], tuple[str, ...]]:
    """Return (subtotal, all_complete_objects, usage_by_send_link, usage_blockers)."""
    usages: list[ReportedUsage] = []
    usage_by_send: dict[str, dict[str, object]] = {}
    complete_objects = True
    usage_blockers: list[str] = []
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
        try:
            # Pass raw optional subdivisions through model_validate so illegal
            # present values remain malformed instead of being type-narrowed away.
            reported = ReportedUsage.model_validate(
                {
                    "prompt_tokens": prompt,
                    "completion_tokens": completion,
                    "total_tokens": total,
                    "cache_hit_tokens": event.get("cache_hit_tokens"),
                    "cache_miss_tokens": event.get("cache_miss_tokens"),
                    "reasoning_tokens": event.get("reasoning_tokens"),
                }
            )
        except Exception:  # noqa: BLE001
            complete_objects = False
            if "malformed_usage_fields" not in usage_blockers:
                usage_blockers.append("malformed_usage_fields")
            continue
        link = event.get("send_id") or event.get("call_id")
        if isinstance(link, str) and link:
            if link in usage_by_send:
                complete_objects = False
                blocker = f"duplicate_usage_for_send:{link}"
                if blocker not in usage_blockers:
                    usage_blockers.append(blocker)
                continue
            usage_by_send[link] = event
        usages.append(reported)
    return (
        sum_reported_usage(usages),
        complete_objects,
        usage_by_send,
        tuple(usage_blockers),
    )


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
    fixed_zero_use: bool = False,
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

    usage_subtotal, usage_complete, usage_by_send, usage_blockers = (
        _derive_usage_from_events(ledger.events)
    )
    blockers.extend(usage_blockers)
    fixed_zero_usage = (
        fixed_zero_use
        and not ledger.events
        and usage_subtotal is None
        and (
            ledger.reported_usage_subtotal is None
            or _zero_usage(ledger.reported_usage_subtotal)
        )
    )
    if not fixed_zero_usage and (
        ledger.reported_usage_subtotal is not None
        and usage_subtotal is not None
        and ledger.reported_usage_subtotal.model_dump(mode="json")
        != usage_subtotal.model_dump(mode="json")
    ):
        blockers.append("usage_subtotal_recompute_mismatch")
    if (
        not fixed_zero_usage
        and ledger.reported_usage_subtotal is not None
        and usage_subtotal is None
    ):
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
            # A caller-supplied zero_use_proof string is not a bound proof.
            send_coverage_complete = False
            link_text = link if isinstance(link, str) and link else "missing"
            blockers.append(f"redirect_without_zero_use_proof:{link_text}")
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

    graph_pending, pairing_blockers = _lifecycle_graph(ledger.events)
    blockers.extend(pairing_blockers)
    if tuple(ledger.pending_event_ids) != graph_pending:
        blockers.append("pending_event_recompute_mismatch")

    coverage_incomplete = (not send_coverage_complete and http_count > 0) or (
        logical > 0 and not usage_complete
    )
    empty_graph = not ledger.events and all(value == 0 for value in derived.values())
    empty_unproved = empty_graph and not fixed_zero_use
    if empty_unproved and exact_total == 0:
        blockers.append("product_empty_exact_not_fixed_zero")
    graph_incomplete = (
        (not ledger.worker_drained)
        or bool(graph_pending)
        or bool(pairing_blockers)
        or coverage_incomplete
        or empty_unproved
    )
    if ledger.incomplete != graph_incomplete:
        blockers.append("incomplete_recompute_mismatch")
    graph_closed = (
        ledger.worker_drained
        and not ledger.telemetry_invalid
        and not graph_incomplete
        and not graph_pending
        and bool(ledger.run_id)
    )
    if ledger.closed != graph_closed:
        blockers.append("closed_recompute_mismatch")

    # Exact totals require complete per-send usage coverage derived from events.
    if exact_total is not None:
        if not (
            usage_complete
            and send_coverage_complete
            and usage_subtotal is not None
            and exact_total == usage_subtotal.total_tokens
            and not graph_pending
            and not pairing_blockers
            and ledger.worker_drained
            and not ledger.telemetry_invalid
        ):
            fixed_zero = (
                fixed_zero_use
                and exact_total == 0
                and empty_graph
                and ledger.worker_drained
                and not graph_pending
                and not ledger.telemetry_invalid
                and all(getattr(ledger, field) == 0 for field in derived)
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
    acceptance_blocked = bool(unique) or graph_incomplete or ledger.telemetry_invalid
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
        incomplete=graph_incomplete or not graph_closed,
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
    logical_values: list[int] = []
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
        if observation.logical_call_count is None:
            blockers.append("campaign_unknown_logical_call_count")
        else:
            logical_values.append(observation.logical_call_count)
    token_blockers = _campaign_reported_token_blockers(observations, assessment)
    if blockers:
        return tuple(dict.fromkeys([*blockers, *token_blockers]))
    sdk_total = sum(sdk_values)
    http_total = sum(http_values)
    logical_total = sum(logical_values)
    if (
        assessment.logical_call_ceiling is not None
        and logical_total > assessment.logical_call_ceiling
    ):
        blockers.append("campaign_logical_call_ceiling_exceeded")
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
