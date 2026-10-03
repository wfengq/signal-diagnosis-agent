"""Codex revise round 5: finite monotonic, ancestry, parent bounds, entity lifecycle."""

from __future__ import annotations

import math

from signal_diag.evaluation.planner_ablation.v2.resource_models import ReportedUsage
from signal_diag.evaluation.planner_ablation.v2.resource_telemetry import (
    aggregate_resource_ledger,
    derive_counts_from_events,
)
from tests.evaluation.planner_ablation.v2.test_codex_revise_round2 import (
    _ledger,
    _open_assessment,
)
from tests.evaluation.planner_ablation.v2.test_codex_revise_round3 import (
    _valid_chain_events,
)


def _exact_ledger(events: tuple[dict[str, object], ...], **count_overrides: int):
    derived = derive_counts_from_events(events)
    derived.update(count_overrides)
    usage = ReportedUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2)
    return _ledger(
        events=events,
        planner_turn_count=derived["planner_turn_count"],
        logical_call_count=derived["logical_call_count"],
        sdk_attempt_count=derived["sdk_attempt_count"],
        http_send_attempt_count=derived["http_send_attempt_count"],
        reported_usage_subtotal=usage,
        exact_total_tokens=2,
        incomplete=False,
        closed=True,
    )


def test_nonfinite_monotonic_s_blocks_exact() -> None:
    events = tuple(dict(event) for event in _valid_chain_events())
    events = tuple(
        {**event, "monotonic_s": math.nan} if "monotonic_s" in event else event
        for event in events
    )
    observation = aggregate_resource_ledger(
        _exact_ledger(events),
        assessment=_open_assessment(),
    )
    assert observation.acceptance_blocked is True
    assert observation.exact_total_tokens is None
    assert any("missing_required_monotonic:" in b for b in observation.blockers)


def test_logical_call_end_after_turn_end_blocked() -> None:
    events = [dict(event) for event in _valid_chain_events()]
    for event in events:
        if event.get("kind") == "logical_call" and event.get("phase") == "end":
            event["monotonic_s"] = 2.0
    observation = aggregate_resource_ledger(
        _exact_ledger(tuple(events)),
        assessment=_open_assessment(),
    )
    assert observation.acceptance_blocked is True
    assert observation.exact_total_tokens is None
    assert any(
        b == "event_graph_temporal:planner_turn:c1:child_after_parent_end"
        for b in observation.blockers
    )


def test_retargeted_turn_id_on_sdk_and_usage_blocked() -> None:
    events = [dict(event) for event in _valid_chain_events()]
    for event in events:
        if event.get("kind") == "usage" or (
            event.get("kind") == "sdk_attempt" and event.get("phase") == "end"
        ):
            event["turn_id"] = "t2"
    events.insert(
        0,
        {
            "kind": "planner_turn",
            "phase": "start",
            "turn_id": "t2",
            "correlation_id": "t2",
            "sequence_id": "pt2-s",
            "monotonic_s": 0.5,
        },
    )
    events.append(
        {
            "kind": "planner_turn",
            "phase": "end",
            "turn_id": "t2",
            "correlation_id": "t2",
            "sequence_id": "pt2-e",
            "monotonic_s": 0.6,
        },
    )
    observation = aggregate_resource_ledger(
        _exact_ledger(tuple(events)),
        assessment=_open_assessment(),
    )
    assert observation.acceptance_blocked is True
    assert observation.exact_total_tokens is None
    assert any("sdk_attempt_ancestry_mismatch:a1" in b for b in observation.blockers)
    assert any("usage_ancestry_mismatch:h1" in b for b in observation.blockers)


def test_aliased_correlation_same_send_entity_blocked() -> None:
    turn_id, call_id, attempt_id, send_id = "t1", "c1", "a1", "h1"
    events = [dict(event) for event in _valid_chain_events()]
    events.append(
        {
            "kind": "http_send",
            "phase": "start",
            "turn_id": turn_id,
            "call_id": call_id,
            "attempt_id": attempt_id,
            "send_id": send_id,
            "correlation_id": f"{send_id}-alias",
            "sequence_id": "http-s2",
            "monotonic_s": 1.31,
        }
    )
    events.append(
        {
            "kind": "http_send",
            "phase": "end",
            "turn_id": turn_id,
            "call_id": call_id,
            "attempt_id": attempt_id,
            "send_id": send_id,
            "correlation_id": f"{send_id}-alias",
            "sequence_id": "http-e2",
            "outcome": "success",
            "monotonic_s": 1.32,
        }
    )
    observation = aggregate_resource_ledger(
        _exact_ledger(tuple(events)),
        assessment=_open_assessment(),
    )
    assert observation.acceptance_blocked is True
    assert observation.exact_total_tokens is None
    assert any(
        "lifecycle_correlation_mismatch:http_send:h1" in b
        or "duplicate_lifecycle_entity_phase:http_send:h1:start" in b
        for b in observation.blockers
    )


def test_valid_full_chain_with_times_still_accepts_exact() -> None:
    events = _valid_chain_events()
    observation = aggregate_resource_ledger(
        _exact_ledger(events),
        assessment=_open_assessment(),
    )
    assert observation.acceptance_blocked is False
    assert observation.exact_total_tokens == 2
