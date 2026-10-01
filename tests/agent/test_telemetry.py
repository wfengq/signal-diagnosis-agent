"""Opt-in agent telemetry binding and safe emission (T-CX306–308)."""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest

from signal_diag.agent.planner import RealLLMPlanner, bind_planner_telemetry
from signal_diag.agent.telemetry import (
    PlannerTurnEvent,
    RepairEvent,
    TelemetryBinding,
    TelemetryEvent,
    emit_safely,
    get_planner_telemetry_binding,
)

_SRC = Path(__file__).resolve().parents[2] / "src" / "signal_diag"


def _binding() -> tuple[TelemetryBinding, list[TelemetryEvent]]:
    events: list[TelemetryEvent] = []
    binding = TelemetryBinding(slot_id="slot_test", sink=events.append)
    return binding, events


def test_unbound_default_constructor_is_unchanged() -> None:
    planner = RealLLMPlanner(client=object())  # type: ignore[arg-type]
    assert get_planner_telemetry_binding(planner) is None
    assert planner._client is not None
    # Public construction kwargs unchanged: no telemetry parameters required.
    RealLLMPlanner()


def test_factory_probes_are_not_turns() -> None:
    binding, events = _binding()
    planner = RealLLMPlanner(client=object())  # type: ignore[arg-type]
    bind_planner_telemetry(planner, binding=binding)
    # Construction / attribute probes must not emit planner turns.
    _ = planner.prompt_version
    _ = planner.model_id
    _ = get_planner_telemetry_binding(planner)
    assert events == []
    assert all(getattr(e, "kind", None) != "planner_turn" for e in events)


def test_observer_failure_preserves_product_exception() -> None:
    def boom(_event: TelemetryEvent) -> None:
        raise RuntimeError("observer exploded")

    binding = TelemetryBinding(slot_id="slot_boom", sink=boom)
    planner = RealLLMPlanner(provider="deepseek", api_key="k", base_url="http://x", client=object())  # type: ignore[arg-type]
    bind_planner_telemetry(planner, binding=binding)

    async def _run() -> None:
        from signal_diag.agent.models import PlannerContext
        from signal_diag.signal.models import SignalMeta
        from signal_diag.tools.registry import get_tool_descriptors

        context = PlannerContext(
            run_id="run_obs",
            user_request="Why?",
            signal_meta=SignalMeta(
                signal_id="s",
                source_type="generated",
                sample_rate_hz=48_000,
                channels=1,
                num_samples=48_000,
                duration_s=1.0,
                original_dtype="float32",
            ),
            task_assessment=None,
            observations=(),
            evidence=(),
            tool_history=(),
            available_tools=get_tool_descriptors(),
            remaining_tool_calls=8,
            remaining_planner_retries=2,
            no_progress_count=0,
        )
        with pytest.raises(Exception) as first:
            await planner.decide(context)
        # Re-bind a fresh planner for parity without observation.
        plain = RealLLMPlanner(
            provider="deepseek",
            api_key="k",
            base_url="http://x",
            client=object(),  # type: ignore[arg-type]
        )
        with pytest.raises(Exception) as second:
            await plain.decide(context)
        assert type(first.value) is type(second.value)
        assert binding.invalid is True

    import asyncio

    asyncio.run(_run())


def test_emit_safely_latches_overflow_without_raise() -> None:
    events: list[TelemetryEvent] = []
    binding = TelemetryBinding(slot_id="slot", sink=events.append, max_events=1)
    emit_safely(
        binding,
        PlannerTurnEvent(
            sequence_id="a",
            correlation_id="c",
            phase="start",
            turn_id="t1",
            monotonic_s=0.0,
        ),
    )
    emit_safely(
        binding,
        PlannerTurnEvent(
            sequence_id="b",
            correlation_id="c",
            phase="end",
            turn_id="t1",
            monotonic_s=0.1,
            outcome="success",
        ),
    )
    assert len(events) == 1
    assert binding.invalid is True
    assert "telemetry_buffer_overflow" in binding.invalid_reasons


def test_bind_rejects_subclass_and_second_binding() -> None:
    from signal_diag.agent.planner import _Phase4V8_1RealLLMPlanner

    binding, _ = _binding()
    with pytest.raises(TypeError):
        bind_planner_telemetry(
            _Phase4V8_1RealLLMPlanner(client=object()),  # type: ignore[arg-type]
            binding=binding,
        )
    planner = RealLLMPlanner(client=object())  # type: ignore[arg-type]
    bind_planner_telemetry(planner, binding=binding)
    with pytest.raises(RuntimeError):
        bind_planner_telemetry(planner, binding=binding)


def test_agent_telemetry_stdlib_only_no_app_evaluation_imports() -> None:
    path = _SRC / "agent" / "telemetry.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("signal_diag.app")
            assert not node.module.startswith("signal_diag.evaluation")
            assert "openai" not in node.module
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("signal_diag.app")
                assert not alias.name.startswith("signal_diag.evaluation")
                assert alias.name != "openai"


def test_repair_event_type_is_frozen_dataclass() -> None:
    event = RepairEvent(
        sequence_id="s",
        correlation_id="c",
        turn_id="t",
        reason="parse_error",
        retries_consumed=1,
        monotonic_s=1.0,
    )
    assert event.kind == "repair"
    with pytest.raises((AttributeError, TypeError, dataclasses.FrozenInstanceError)):
        event.retries_consumed = 2  # type: ignore[misc]
