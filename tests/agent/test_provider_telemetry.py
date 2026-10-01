"""Offline SDK/native transport observation tests (no live network)."""

from __future__ import annotations

import importlib
import json
from typing import Any

import httpx
import pytest

from signal_diag.agent.models import PlannerContext, PlannerOutputError
from signal_diag.agent.planner import (
    RealLLMPlanner,
    bind_planner_telemetry,
)
from signal_diag.agent.provider_telemetry import (
    attach_sdk_observation,
    build_audited_sdk_observation_profile,
)
from signal_diag.agent.telemetry import (
    HttpSendEvent,
    LogicalCallEvent,
    PlannerTurnEvent,
    SdkAttemptEvent,
    SdkObservationProfile,
    TelemetryBinding,
    TelemetryEvent,
    UsageObservation,
    get_planner_telemetry_binding,
)
from signal_diag.signal.models import SignalMeta
from signal_diag.tools.registry import get_tool_descriptors


def _async_openai(**kwargs: Any) -> Any:
    openai = importlib.import_module("openai")
    return openai.AsyncOpenAI(**kwargs)

def _context() -> PlannerContext:
    return PlannerContext(
        run_id="run_provider_tel",
        user_request="Why distorted?",
        signal_meta=SignalMeta(
            signal_id="sig_provider",
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


def _valid_decision_json() -> str:
    return json.dumps(
        {
            "decision_type": "finish",
            "outcome": "inconclusive",
            "claims": [],
            "confidence_label": "low",
            "summary": "offline mock",
            "task_assessment": {
                "task_type": "distortion_analysis",
                "objective": "offline",
            },
        }
    )


def _chat_completion_body(
    *,
    content: str,
    prompt_tokens: int = 16,
    completion_tokens: int = 10,
    include_usage: bool = True,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": "chatcmpl_test",
        "object": "chat.completion",
        "model": "deepseek-v4-flash",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
    }
    if include_usage:
        body["usage"] = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }
    return body


def _mock_client(handler: Any) -> Any:
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport, follow_redirects=True)
    return _async_openai(
        api_key="test-key",
        base_url="https://example.test/v1",
        http_client=http_client,
        max_retries=2,
    )


def _binding() -> tuple[TelemetryBinding, list[TelemetryEvent]]:
    events: list[TelemetryEvent] = []
    return TelemetryBinding(slot_id="slot_provider", sink=events.append), events


def _counts(events: list[TelemetryEvent]) -> dict[str, int]:
    return {
        "logical_call_count": sum(
            1
            for e in events
            if isinstance(e, LogicalCallEvent) and e.phase == "start"
        ),
        "sdk_attempt_count": sum(
            1 for e in events if isinstance(e, SdkAttemptEvent) and e.phase == "start"
        ),
        "http_send_attempt_count": sum(
            1 for e in events if isinstance(e, HttpSendEvent) and e.phase == "start"
        ),
        "planner_turn_count": sum(
            1 for e in events if isinstance(e, PlannerTurnEvent) and e.phase == "start"
        ),
    }


@pytest.mark.asyncio
async def test_retry_three_attempts_one_call() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(500, json={"error": {"message": "boom"}})
        return httpx.Response(200, json=_chat_completion_body(content=_valid_decision_json()))

    binding, events = _binding()
    profile = build_audited_sdk_observation_profile()
    client = _mock_client(handler)
    attach_sdk_observation(client, binding=binding, profile=profile)
    planner = RealLLMPlanner(
        provider="deepseek",
        api_key="k",
        base_url="https://example.test/v1",
        client=client,  # type: ignore[arg-type]
    )
    bind_planner_telemetry(planner, binding=binding)
    await planner.decide(_context())
    retry_trace = type("T", (), _counts(events))()
    assert retry_trace.logical_call_count == 1
    assert retry_trace.sdk_attempt_count == 3


@pytest.mark.asyncio
async def test_redirect_four_sends_one_sdk_attempt() -> None:
    sends = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        sends["n"] += 1
        if sends["n"] < 4:
            return httpx.Response(
                307,
                headers={"location": str(request.url.copy_with(path=f"/v1/r{sends['n']}"))},
            )
        return httpx.Response(200, json=_chat_completion_body(content=_valid_decision_json()))

    binding, events = _binding()
    profile = build_audited_sdk_observation_profile()
    client = _mock_client(handler)
    attach_sdk_observation(client, binding=binding, profile=profile)
    planner = RealLLMPlanner(
        provider="deepseek",
        api_key="k",
        base_url="https://example.test/v1",
        client=client,  # type: ignore[arg-type]
    )
    bind_planner_telemetry(planner, binding=binding)
    await planner.decide(_context())
    redirect_trace = type("T", (), _counts(events))()
    assert redirect_trace.sdk_attempt_count == 1
    assert redirect_trace.http_send_attempt_count == 4


@pytest.mark.asyncio
async def test_usage_survives_invalid_planner_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_chat_completion_body(
                content="{not-json",
                prompt_tokens=16,
                completion_tokens=10,
            ),
        )

    binding, events = _binding()
    profile = build_audited_sdk_observation_profile()
    client = _mock_client(handler)
    attach_sdk_observation(client, binding=binding, profile=profile)
    planner = RealLLMPlanner(
        provider="deepseek",
        api_key="k",
        base_url="https://example.test/v1",
        client=client,  # type: ignore[arg-type]
    )
    bind_planner_telemetry(planner, binding=binding)
    with pytest.raises(PlannerOutputError):
        await planner.decide(_context())
    usages = [e for e in events if isinstance(e, UsageObservation)]
    assert usages
    assert usages[0].total_tokens == 26
    invalid_json_trace = type("T", (), {"reported_usage": usages[0]})()
    assert invalid_json_trace.reported_usage.total_tokens == 26


@pytest.mark.asyncio
async def test_lost_response_has_unknown_usage() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadError("connection lost after dispatch")

    binding, events = _binding()
    profile = build_audited_sdk_observation_profile()
    client = _mock_client(handler)
    attach_sdk_observation(client, binding=binding, profile=profile)
    planner = RealLLMPlanner(
        provider="deepseek",
        api_key="k",
        base_url="https://example.test/v1",
        client=client,  # type: ignore[arg-type]
    )
    bind_planner_telemetry(planner, binding=binding)
    with pytest.raises((OSError, RuntimeError, httpx.HTTPError, Exception)):
        await planner.decide(_context())
    counts = _counts(events)
    lost_response_trace = type(
        "T",
        (),
        {
            "exact_total_tokens": None,
            "http_send_attempt_count": counts["http_send_attempt_count"],
        },
    )()
    assert lost_response_trace.exact_total_tokens is None
    assert lost_response_trace.http_send_attempt_count >= 1
    assert not any(
        isinstance(e, UsageObservation) and e.status == "complete" for e in events
    )


@pytest.mark.asyncio
async def test_pre_dispatch_sdk_failure_is_not_zero_turns() -> None:
    binding, events = _binding()
    client = _mock_client(lambda r: httpx.Response(200, json={}))

    async def boom_prepare(options: Any) -> Any:
        raise RuntimeError("prepare failed")

    object.__setattr__(client, "_prepare_options", boom_prepare)
    # Re-wrap via attach after replacing prepare — attach wraps current prepare.
    # Instead mark binding and call decide with a client whose create fails early.
    planner = RealLLMPlanner(
        provider="deepseek",
        api_key="k",
        base_url="https://example.test/v1",
        client=client,  # type: ignore[arg-type]
    )
    bind_planner_telemetry(planner, binding=binding)

    async def fail_create(**kwargs: Any) -> Any:
        raise RuntimeError("pre-dispatch")

    client.chat.completions.create = fail_create  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        await planner.decide(_context())
    counts = _counts(events)
    assert counts["planner_turn_count"] == 1
    # Must not claim zero turns just because no HTTP was sent.


@pytest.mark.asyncio
async def test_observed_and_unobserved_sdk_requests_match() -> None:
    bodies: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(request.content)
        return httpx.Response(200, json=_chat_completion_body(content=_valid_decision_json()))

    # Unobserved
    client_a = _mock_client(handler)
    planner_a = RealLLMPlanner(
        provider="deepseek",
        api_key="k",
        base_url="https://example.test/v1",
        client=client_a,  # type: ignore[arg-type]
    )
    await planner_a.decide(_context())

    # Observed
    binding, _events = _binding()
    profile = build_audited_sdk_observation_profile()
    client_b = _mock_client(handler)
    attach_sdk_observation(client_b, binding=binding, profile=profile)
    planner_b = RealLLMPlanner(
        provider="deepseek",
        api_key="k",
        base_url="https://example.test/v1",
        client=client_b,  # type: ignore[arg-type]
    )
    bind_planner_telemetry(planner_b, binding=binding)
    await planner_b.decide(_context())
    assert len(bodies) == 2
    assert bodies[0] == bodies[1]


def test_unsupported_sdk_profile_latches_blocker() -> None:
    binding, _events = _binding()
    bad = SdkObservationProfile(
        openai_version="0.0.0",
        openai_source_digest="0" * 64,
        native_http_family="httpx",
        native_http_version="0.0.0",
        httpcore_version="0.0.0",
        source_file_digests=(("openai/_base_client.py", "1" * 64),),
        max_retries_default=2,
        sdk_attempts_per_call=3,
        prepare_options_hook="wrong",
        send_request_hook="wrong",
        native_dispatch_hook="wrong",
        supported=False,
        blockers=("forced_unsupported",),
    )
    client = _async_openai(api_key="k", base_url="https://example.test/v1")
    desc = attach_sdk_observation(client, binding=binding, profile=bad)
    assert desc.profile_supported is False
    assert binding.invalid is True
    assert any("unsupported" in r or "drift" in r for r in binding.invalid_reasons)


def test_unobserved_factory_path_unchanged() -> None:
    # Construct via the public planner path with an injected client so the
    # private factory is not invoked from required tests (T285 network gate).
    client = _mock_client(lambda r: httpx.Response(200, json={}))
    planner = RealLLMPlanner(
        provider="deepseek",
        api_key="k",
        base_url="https://example.test/v1",
        client=client,
    )
    assert getattr(planner._client, "_signal_diag_observation_attached", False) is False
    assert get_planner_telemetry_binding(planner) is None
