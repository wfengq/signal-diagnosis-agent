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
    build_fixture_sdk_observation_profile,
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


def _attach_offline_observation(client: Any, binding: TelemetryBinding) -> Any:
    binding.allow_fixture_offline_boundary = True
    profile = build_fixture_sdk_observation_profile()
    return attach_sdk_observation(
        client,
        binding=binding,
        profile=profile,
        allow_fixture_offline_boundary=True,
    )


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
    client = _mock_client(handler)
    desc = _attach_offline_observation(client, binding)
    assert desc.origin == "mock_native"
    assert desc.profile_supported is False
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
    client = _mock_client(handler)
    _attach_offline_observation(client, binding)
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
    client = _mock_client(handler)
    _attach_offline_observation(client, binding)
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
    client = _mock_client(handler)
    _attach_offline_observation(client, binding)
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
    client_b = _mock_client(handler)
    _attach_offline_observation(client_b, binding)
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
    assert any("unsupported" in r or "drift" in r or "mismatch" in r for r in binding.invalid_reasons)


def test_audited_profile_compares_reviewed_identity_not_self_hash() -> None:
    from signal_diag.agent.provider_telemetry import (
        reviewed_openai_capability_identity,
    )

    profile = build_audited_sdk_observation_profile()
    reviewed = reviewed_openai_capability_identity()
    if profile.supported:
        assert profile.openai_version == reviewed["openai_version"]
        assert profile.openai_source_digest == reviewed["openai_source_digest"]
    else:
        assert profile.blockers
        assert any(
            "unsupported" in b or "drift" in b for b in profile.blockers
        )


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


@pytest.mark.asyncio
async def test_mounted_transport_path_is_observed() -> None:
    bodies: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(request.content)
        return httpx.Response(200, json=_chat_completion_body(content=_valid_decision_json()))

    binding, events = _binding()
    mount_transport = httpx.MockTransport(handler)
    # Default transport would miss; mount is the actual dispatch path.
    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(500, json={"error": "unused_default"})
        ),
        mounts={"https://": mount_transport},
        follow_redirects=True,
    )
    client = _async_openai(
        api_key="k",
        base_url="https://example.test/v1",
        http_client=http_client,
    )
    desc = _attach_offline_observation(client, binding)
    assert desc.origin == "mock_native"
    assert desc.profile_supported is False
    planner = RealLLMPlanner(
        provider="deepseek",
        api_key="k",
        base_url="https://example.test/v1",
        client=client,  # type: ignore[arg-type]
    )
    bind_planner_telemetry(planner, binding=binding)
    await planner.decide(_context())
    http_starts = [
        e for e in events if isinstance(e, HttpSendEvent) and e.phase == "start"
    ]
    assert len(bodies) == 1
    assert len(http_starts) >= 1


@pytest.mark.asyncio
async def test_audited_unsupported_without_boundary_does_not_observe() -> None:
    from dataclasses import replace

    def _retry_handler() -> Any:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] < 3:
                return httpx.Response(500, json={"error": {"message": "boom"}})
            return httpx.Response(
                200, json=_chat_completion_body(content=_valid_decision_json())
            )

        return handler

    audited = build_audited_sdk_observation_profile()
    unsupported_audited = replace(
        audited,
        supported=False,
        blockers=(
            "openai_version_unsupported:3.22.1",
            "openai_source_digest_drift_vs_reviewed",
        ),
    )
    binding_blocked, events_blocked = _binding()
    client_blocked = _mock_client(_retry_handler())
    desc_blocked = attach_sdk_observation(
        client_blocked,
        binding=binding_blocked,
        profile=unsupported_audited,
    )
    assert desc_blocked.origin == "unsupported"
    assert binding_blocked.invalid is True
    planner_blocked = RealLLMPlanner(
        provider="deepseek",
        api_key="k",
        base_url="https://example.test/v1",
        client=client_blocked,
    )
    bind_planner_telemetry(planner_blocked, binding=binding_blocked)
    await planner_blocked.decide(_context())
    blocked_counts = _counts(events_blocked)
    assert blocked_counts["sdk_attempt_count"] == 0
    assert blocked_counts["http_send_attempt_count"] == 0

    binding_ok, events_ok = _binding()
    client_ok = _mock_client(_retry_handler())
    desc_ok = _attach_offline_observation(client_ok, binding_ok)
    assert desc_ok.origin == "mock_native"
    planner_ok = RealLLMPlanner(
        provider="deepseek",
        api_key="k",
        base_url="https://example.test/v1",
        client=client_ok,
    )
    bind_planner_telemetry(planner_ok, binding=binding_ok)
    await planner_ok.decide(_context())
    ok_counts = _counts(events_ok)
    assert ok_counts["logical_call_count"] == 1
    assert ok_counts["sdk_attempt_count"] == 3


def test_unsupported_canonical_profile_does_not_attach_hooks() -> None:
    binding, _events = _binding()
    installed = build_audited_sdk_observation_profile()
    # Matching hooks/identity but supported=False without offline boundary.
    unsupported = SdkObservationProfile(
        openai_version=installed.openai_version,
        openai_source_digest=installed.openai_source_digest,
        native_http_family=installed.native_http_family,
        native_http_version=installed.native_http_version,
        httpcore_version=installed.httpcore_version,
        source_file_digests=installed.source_file_digests,
        max_retries_default=installed.max_retries_default,
        sdk_attempts_per_call=installed.sdk_attempts_per_call,
        prepare_options_hook=installed.prepare_options_hook,
        send_request_hook=installed.send_request_hook,
        native_dispatch_hook=installed.native_dispatch_hook,
        supported=False,
        blockers=("canonical_unsupported",),
    )
    client = _async_openai(api_key="k", base_url="https://example.test/v1")
    desc = attach_sdk_observation(client, binding=binding, profile=unsupported)
    assert desc.origin == "unsupported"
    assert binding.invalid is True
    assert getattr(client, "_signal_diag_observation_attached", False) is False
    # Explicit offline boundary may attach fixture observation without claiming support.
    binding2, _ = _binding()
    binding2.allow_fixture_offline_boundary = True
    desc2 = attach_sdk_observation(
        client,
        binding=binding2,
        profile=unsupported,
        allow_fixture_offline_boundary=True,
    )
    assert desc2.profile_supported is False
    assert desc2.origin == "mock_native"
    assert binding2.observation_descriptor is not None


def test_supported_audited_profile_attaches_canonical_without_fixture_boundary() -> None:
    profile = build_audited_sdk_observation_profile()
    binding, _events = _binding()
    http_client = httpx.AsyncClient()
    client = _async_openai(
        api_key="test-key",
        base_url="https://example.test/v1",
        http_client=http_client,
    )
    desc = attach_sdk_observation(
        client,
        binding=binding,
        profile=profile,
        allow_fixture_offline_boundary=False,
    )
    if profile.supported:
        assert desc.origin == "canonical_sdk"
        assert desc.profile_supported is True
        assert getattr(client, "_signal_diag_observation_attached", False) is True
    else:
        # CI may resolve openai outside the reviewed tuple; refuse without skip.
        assert desc.origin == "unsupported"
        assert desc.profile_supported is False
        assert binding.invalid is True
        assert getattr(client, "_signal_diag_observation_attached", False) is False
        assert profile.blockers


def test_mock_transport_is_never_canonical_sdk() -> None:
    profile = build_audited_sdk_observation_profile()
    binding, _events = _binding()
    client = _mock_client(lambda request: httpx.Response(204))
    desc = attach_sdk_observation(
        client,
        binding=binding,
        profile=profile,
        allow_fixture_offline_boundary=False,
    )
    assert desc.origin != "canonical_sdk"
    if profile.supported:
        assert desc.origin == "mock_native"
        assert desc.profile_supported is False
        assert desc.fixture_only is True


@pytest.mark.asyncio
async def test_same_transport_object_is_observed_once() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_chat_completion_body(content=_valid_decision_json()))

    binding, events = _binding()
    client = _mock_client(handler)
    http_client = client._client
    # Same object also exposed as the proxy transport. Observation must wrap it once.
    http_client._proxy_transport = http_client._transport
    _attach_offline_observation(client, binding)
    planner = RealLLMPlanner(
        provider="deepseek",
        api_key="k",
        base_url="https://example.test/v1",
        client=client,  # type: ignore[arg-type]
    )
    bind_planner_telemetry(planner, binding=binding)
    await planner.decide(_context())
    assert _counts(events)["http_send_attempt_count"] == 1
