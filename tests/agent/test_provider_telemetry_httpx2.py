"""T-CX425–T-CX427: SDK observation identity names the HTTP client that dispatches (D048)."""

from __future__ import annotations

import asyncio
import importlib
from dataclasses import replace
from typing import Any

import pytest

from signal_diag.agent import provider_telemetry
from signal_diag.agent.provider_telemetry import (
    attach_sdk_observation,
    build_audited_sdk_observation_profile,
    reviewed_openai_capability_identity,
)
from signal_diag.agent.telemetry import HttpSendEvent, SdkAttemptEvent, TelemetryBinding

# A closed local port: the SDK fails to connect, so no request leaves the machine.
_CLOSED_BASE_URL = "http://127.0.0.1:9/v1"


def _openai() -> Any:
    return importlib.import_module("openai")


def _client() -> Any:
    return _openai().AsyncOpenAI(api_key="x", base_url=_CLOSED_BASE_URL, max_retries=0)


def _dispatch_module() -> str:
    client = _client()
    for cls in type(client._client).__mro__:
        module = cls.__module__.split(".", 1)[0]
        if module in ("httpx", "httpx2"):
            return module
    raise AssertionError("SDK client is not built on an httpx-family client")


def test_t_cx425_profile_names_the_dispatching_http_client() -> None:
    family = _dispatch_module()
    profile = build_audited_sdk_observation_profile()
    assert family == "httpx2"
    assert profile.native_http_family == family
    assert profile.native_http_version == importlib.import_module(family).__version__
    assert profile.native_dispatch_hook == f"{family}.AsyncClient.send"
    reviewed = reviewed_openai_capability_identity()
    assert reviewed["native_http_family"] == family
    assert reviewed["native_dispatch_hook"] == f"{family}.AsyncClient.send"
    assert profile.supported, profile.blockers


def test_t_cx426_httpx2_version_drift_blocks_support(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(provider_telemetry, "_AUDITED_HTTPX2_VERSION", "0.0.0")
    profile = build_audited_sdk_observation_profile()
    assert profile.supported is False
    assert any(item.startswith("httpx2_version_drift:") for item in profile.blockers)


def test_t_cx426_mismatched_dispatch_family_is_rejected() -> None:
    profile = build_audited_sdk_observation_profile()
    wrong = replace(profile, native_http_family="httpx")
    binding = TelemetryBinding(slot_id="slot_family", sink=lambda _event: None)
    client = _client()
    descriptor = attach_sdk_observation(client, binding=binding, profile=wrong)
    assert descriptor.profile_supported is False
    assert "native_http_family_mismatch" in descriptor.blockers


def test_t_cx427_observation_sees_sends_through_httpx2() -> None:
    events: list[object] = []
    binding = TelemetryBinding(slot_id="slot_probe", sink=events.append)
    client = _client()
    descriptor = attach_sdk_observation(
        client, binding=binding, profile=build_audited_sdk_observation_profile()
    )
    assert descriptor.origin == "canonical_sdk"

    async def call() -> None:
        with pytest.raises(_openai().APIConnectionError):
            await client.chat.completions.create(
                model="m", messages=[{"role": "user", "content": "probe"}]
            )

    asyncio.run(call())
    phases = [
        (type(event).__name__, event.phase)
        for event in events
        if isinstance(event, SdkAttemptEvent | HttpSendEvent)
    ]
    assert phases == [
        ("SdkAttemptEvent", "start"),
        ("HttpSendEvent", "start"),
        ("HttpSendEvent", "end"),
        ("SdkAttemptEvent", "end"),
    ]
