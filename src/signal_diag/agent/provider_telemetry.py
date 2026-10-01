"""Private version-bound SDK/native transport observation (lazy openai import)."""

from __future__ import annotations

import hashlib
import importlib.metadata
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from signal_diag.agent.telemetry import (
    ClientObservationDescriptor,
    HttpSendEvent,
    SdkAttemptEvent,
    SdkObservationProfile,
    TelemetryBinding,
    UsageObservation,
    UsageStatus,
    emit_safely,
)

_AUDITED_OPENAI_VERSION = "3.20.0"
_PREPARE_HOOK = "AsyncAPIClient._prepare_options"
_SEND_HOOK = "AsyncAPIClient._send_request"
_NATIVE_HOOK = "httpx.AsyncClient.send"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def installed_openai_source_digests() -> dict[str, str]:
    import openai

    root = Path(openai.__file__).resolve().parent
    return {
        "openai/__init__.py": _sha256_file(root / "__init__.py"),
        "openai/_base_client.py": _sha256_file(root / "_base_client.py"),
        "openai/_client.py": _sha256_file(root / "_client.py"),
        "openai/_constants.py": _sha256_file(root / "_constants.py"),
    }


def aggregate_openai_source_digest(digests: dict[str, str]) -> str:
    ordered = (
        "openai/__init__.py",
        "openai/_base_client.py",
        "openai/_client.py",
        "openai/_constants.py",
    )
    h = hashlib.sha256()
    for key in ordered:
        h.update(digests[key].encode("ascii"))
    return h.hexdigest()


def build_audited_sdk_observation_profile() -> SdkObservationProfile:
    """Build the exact 3.20.0 profile for the currently installed distribution."""
    version = importlib.metadata.version("openai")
    import httpx

    digests = installed_openai_source_digests()
    aggregate = aggregate_openai_source_digest(digests)
    blockers: list[str] = []
    supported = True
    if version != _AUDITED_OPENAI_VERSION:
        supported = False
        blockers.append(
            f"unsupported_openai_version:installed_{version}"
            f"_audited_{_AUDITED_OPENAI_VERSION}"
        )
    return SdkObservationProfile(
        openai_version=version,
        openai_source_digest=aggregate,
        native_http_family="httpx",
        native_http_version=httpx.__version__,
        httpcore_version=importlib.metadata.version("httpcore"),
        source_file_digests=tuple(sorted(digests.items())),
        max_retries_default=2,
        sdk_attempts_per_call=3,
        prepare_options_hook=_PREPARE_HOOK,
        send_request_hook=_SEND_HOOK,
        native_dispatch_hook=_NATIVE_HOOK,
        supported=supported,
        blockers=tuple(blockers),
    )


def _profile_matches_installed(profile: SdkObservationProfile) -> tuple[bool, tuple[str, ...]]:
    installed = build_audited_sdk_observation_profile()
    blockers: list[str] = []
    if profile.openai_version != installed.openai_version:
        blockers.append(
            "dependency_identity_drift:"
            f"profile_{profile.openai_version}_vs_installed_{installed.openai_version}"
        )
    if profile.openai_source_digest != installed.openai_source_digest:
        blockers.append("openai_source_digest_drift")
    if profile.prepare_options_hook != _PREPARE_HOOK:
        blockers.append("prepare_options_hook_mismatch")
    if profile.send_request_hook != _SEND_HOOK:
        blockers.append("send_request_hook_mismatch")
    if profile.native_dispatch_hook != _NATIVE_HOOK:
        blockers.append("native_dispatch_hook_mismatch")
    if not profile.supported:
        blockers.extend(profile.blockers or ("unsupported_sdk_profile",))
    if not installed.supported:
        blockers.extend(installed.blockers)
    return (len(blockers) == 0), tuple(dict.fromkeys(blockers))


def attach_sdk_observation(
    client: object,
    *,
    binding: TelemetryBinding,
    profile: SdkObservationProfile,
) -> ClientObservationDescriptor:
    """Attach per-instance observation to an already-constructed AsyncOpenAI client."""
    ok, blockers = _profile_matches_installed(profile)
    if not ok:
        binding.mark_invalid("unsupported_sdk_profile")
        for reason in blockers:
            binding.mark_invalid(reason)
        return ClientObservationDescriptor(
            origin="unsupported",
            openai_version=profile.openai_version,
            native_http_family=profile.native_http_family,
            profile_supported=False,
            blockers=blockers,
            fixture_only=True,
        )

    # Instance-local wrappers; never patch the class globally.
    prepare = getattr(client, "_prepare_options", None)
    send_request = getattr(client, "_send_request", None)
    http_client = getattr(client, "_client", None)
    if prepare is None or send_request is None or http_client is None:
        blockers = ("unavailable_retry_telemetry:missing_hook_points",)
        binding.mark_invalid(blockers[0])
        return ClientObservationDescriptor(
            origin="unsupported",
            openai_version=profile.openai_version,
            native_http_family=profile.native_http_family,
            profile_supported=False,
            blockers=blockers,
            fixture_only=True,
        )

    state: dict[str, Any] = {
        "attempt_index": 0,
        "current_attempt_id": None,
        "current_send_id": None,
        "send_index": 0,
    }

    original_prepare: Callable[..., Awaitable[Any]] = prepare
    original_send_request: Callable[..., Awaitable[Any]] = send_request
    original_http_send: Callable[..., Awaitable[Any]] = http_client.send

    async def observed_prepare(options: Any) -> Any:
        attempt_id = binding.new_id("sdk")
        state["current_attempt_id"] = attempt_id
        state["send_index"] = 0
        retry_index = state["attempt_index"]
        state["attempt_index"] += 1
        emit_safely(
            binding,
            SdkAttemptEvent(
                sequence_id=binding.new_id("seq"),
                correlation_id=attempt_id,
                phase="start",
                turn_id=binding.current_turn_id or "",
                call_id=binding.current_call_id or "",
                attempt_id=attempt_id,
                retry_index=retry_index,
                monotonic_s=binding.clock(),
                parent_id=binding.current_call_id,
            ),
        )
        try:
            return await original_prepare(options)
        except BaseException:
            emit_safely(
                binding,
                SdkAttemptEvent(
                    sequence_id=binding.new_id("seq"),
                    correlation_id=attempt_id,
                    phase="end",
                    turn_id=binding.current_turn_id or "",
                    call_id=binding.current_call_id or "",
                    attempt_id=attempt_id,
                    retry_index=retry_index,
                    monotonic_s=binding.clock(),
                    outcome="pre_dispatch_failure",
                    parent_id=binding.current_call_id,
                ),
            )
            state["current_attempt_id"] = None
            raise

    async def observed_send_request(request: Any, *args: Any, **kwargs: Any) -> Any:
        attempt_id = state.get("current_attempt_id") or binding.new_id("sdk")
        retry_index = max(0, state["attempt_index"] - 1)
        outcome = "unknown"
        try:
            response = await original_send_request(request, *args, **kwargs)
            status = getattr(response, "status_code", None)
            if isinstance(status, int) and 200 <= status < 300:
                outcome = "success"
            elif isinstance(status, int) and status in {408, 409, 429} or (
                isinstance(status, int) and status >= 500
            ):
                outcome = "retryable_response"
            else:
                outcome = "fatal_response"
            return response
        except BaseException:
            outcome = "transport_error"
            raise
        finally:
            emit_safely(
                binding,
                SdkAttemptEvent(
                    sequence_id=binding.new_id("seq"),
                    correlation_id=attempt_id,
                    phase="end",
                    turn_id=binding.current_turn_id or "",
                    call_id=binding.current_call_id or "",
                    attempt_id=attempt_id,
                    retry_index=retry_index,
                    monotonic_s=binding.clock(),
                    outcome=outcome,  # type: ignore[arg-type]
                    parent_id=binding.current_call_id,
                ),
            )
            state["current_attempt_id"] = None

    # Prefer transport-level observation so redirect hops are visible even when
    # httpx follows redirects inside a single AsyncClient.send call.
    transport = getattr(http_client, "_transport", None)
    original_transport_request = None
    if transport is not None and hasattr(transport, "handle_async_request"):
        original_transport_request = transport.handle_async_request

        async def observed_transport_request(request: Any) -> Any:
            attempt_id = state.get("current_attempt_id") or ""
            send_id = binding.new_id("http")
            state["current_send_id"] = send_id
            redirect_index = state["send_index"]
            state["send_index"] += 1
            url = str(getattr(request, "url", ""))
            sanitized = url.split("?", 1)[0]
            emit_safely(
                binding,
                HttpSendEvent(
                    sequence_id=binding.new_id("seq"),
                    correlation_id=send_id,
                    phase="start",
                    turn_id=binding.current_turn_id or "",
                    call_id=binding.current_call_id or "",
                    attempt_id=attempt_id,
                    send_id=send_id,
                    redirect_index=redirect_index,
                    sanitized_endpoint=sanitized,
                    monotonic_s=binding.clock(),
                    parent_id=attempt_id or None,
                ),
            )
            outcome = "unknown"
            status_code: int | None = None
            try:
                response = await original_transport_request(request)
                status_code = getattr(response, "status_code", None)
                if isinstance(status_code, int) and 300 <= status_code < 400:
                    outcome = "redirect"
                elif isinstance(status_code, int) and 200 <= status_code < 300:
                    outcome = "success"
                elif isinstance(status_code, int):
                    outcome = "http_error"
                return response
            except BaseException:
                outcome = "transport_error"
                raise
            finally:
                emit_safely(
                    binding,
                    HttpSendEvent(
                        sequence_id=binding.new_id("seq"),
                        correlation_id=send_id,
                        phase="end",
                        turn_id=binding.current_turn_id or "",
                        call_id=binding.current_call_id or "",
                        attempt_id=attempt_id,
                        send_id=send_id,
                        redirect_index=redirect_index,
                        sanitized_endpoint=sanitized,
                        monotonic_s=binding.clock(),
                        status_code=status_code,
                        outcome=outcome,  # type: ignore[arg-type]
                        parent_id=attempt_id or None,
                    ),
                )
                state["current_send_id"] = None

        object.__setattr__(transport, "handle_async_request", observed_transport_request)
    else:

        async def observed_http_send(request: Any, *args: Any, **kwargs: Any) -> Any:
            attempt_id = state.get("current_attempt_id") or ""
            send_id = binding.new_id("http")
            state["current_send_id"] = send_id
            redirect_index = state["send_index"]
            state["send_index"] += 1
            url = str(getattr(request, "url", ""))
            sanitized = url.split("?", 1)[0]
            emit_safely(
                binding,
                HttpSendEvent(
                    sequence_id=binding.new_id("seq"),
                    correlation_id=send_id,
                    phase="start",
                    turn_id=binding.current_turn_id or "",
                    call_id=binding.current_call_id or "",
                    attempt_id=attempt_id,
                    send_id=send_id,
                    redirect_index=redirect_index,
                    sanitized_endpoint=sanitized,
                    monotonic_s=binding.clock(),
                    parent_id=attempt_id or None,
                ),
            )
            outcome = "unknown"
            status_code = None
            try:
                response = await original_http_send(request, *args, **kwargs)
                status_code = getattr(response, "status_code", None)
                if isinstance(status_code, int) and 300 <= status_code < 400:
                    outcome = "redirect"
                elif isinstance(status_code, int) and 200 <= status_code < 300:
                    outcome = "success"
                elif isinstance(status_code, int):
                    outcome = "http_error"
                return response
            except BaseException:
                outcome = "transport_error"
                raise
            finally:
                emit_safely(
                    binding,
                    HttpSendEvent(
                        sequence_id=binding.new_id("seq"),
                        correlation_id=send_id,
                        phase="end",
                        turn_id=binding.current_turn_id or "",
                        call_id=binding.current_call_id or "",
                        attempt_id=attempt_id,
                        send_id=send_id,
                        redirect_index=redirect_index,
                        sanitized_endpoint=sanitized,
                        monotonic_s=binding.clock(),
                        status_code=status_code,
                        outcome=outcome,  # type: ignore[arg-type]
                        parent_id=attempt_id or None,
                    ),
                )
                state["current_send_id"] = None

        object.__setattr__(http_client, "send", observed_http_send)

    object.__setattr__(client, "_prepare_options", observed_prepare)
    object.__setattr__(client, "_send_request", observed_send_request)
    object.__setattr__(client, "_signal_diag_observation_attached", True)
    object.__setattr__(client, "_signal_diag_observation_state", state)
    return ClientObservationDescriptor(
        origin="canonical_sdk",
        openai_version=profile.openai_version,
        native_http_family=profile.native_http_family,
        profile_supported=True,
        blockers=(),
        fixture_only=True,
    )


def emit_usage_from_response(
    binding: TelemetryBinding,
    response: object,
    *,
    send_id: str | None = None,
) -> None:
    """Extract allowlisted usage/model metadata before planner JSON validation."""
    usage = getattr(response, "usage", None)
    model = getattr(response, "model", None)
    fingerprint = getattr(response, "system_fingerprint", None)
    attempt_id = binding.current_attempt_id or ""
    call_id = binding.current_call_id or ""
    turn_id = binding.current_turn_id or ""
    if usage is None:
        emit_safely(
            binding,
            UsageObservation(
                sequence_id=binding.new_id("seq"),
                correlation_id=call_id or binding.new_id("usage"),
                turn_id=turn_id,
                call_id=call_id,
                attempt_id=attempt_id,
                send_id=send_id or "",
                status="missing",
                response_model=model if isinstance(model, str) else None,
                fingerprint=fingerprint if isinstance(fingerprint, str) else None,
                monotonic_s=binding.clock(),
                parent_id=call_id or None,
            ),
        )
        return
    try:
        prompt = getattr(usage, "prompt_tokens", None)
        completion = getattr(usage, "completion_tokens", None)
        total = getattr(usage, "total_tokens", None)
        if not (
            isinstance(prompt, int)
            and isinstance(completion, int)
            and isinstance(total, int)
            and not isinstance(prompt, bool)
            and not isinstance(completion, bool)
            and not isinstance(total, bool)
        ):
            raise TypeError("non-int usage")
        if total != prompt + completion:
            raise ValueError("inconsistent total")
        status: UsageStatus = "complete"
    except Exception:  # noqa: BLE001
        emit_safely(
            binding,
            UsageObservation(
                sequence_id=binding.new_id("seq"),
                correlation_id=call_id or binding.new_id("usage"),
                turn_id=turn_id,
                call_id=call_id,
                attempt_id=attempt_id,
                send_id=send_id or "",
                status="malformed",
                monotonic_s=binding.clock(),
                parent_id=call_id or None,
            ),
        )
        return
    emit_safely(
        binding,
        UsageObservation(
            sequence_id=binding.new_id("seq"),
            correlation_id=call_id or binding.new_id("usage"),
            turn_id=turn_id,
            call_id=call_id,
            attempt_id=attempt_id,
            send_id=send_id or "",
            status=status,
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
            response_model=model if isinstance(model, str) else None,
            fingerprint=fingerprint if isinstance(fingerprint, str) else None,
            monotonic_s=binding.clock(),
            parent_id=call_id or None,
        ),
    )
