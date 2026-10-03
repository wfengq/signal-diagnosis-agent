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

# Reviewed capability identity from RESOURCE_BOUNDS.md §7 (lock-aligned openai==3.6.0).
_AUDITED_OPENAI_VERSION = "3.6.0"
_AUDITED_OPENAI_SOURCE_DIGESTS: dict[str, str] = {
    "openai/__init__.py": (
        "2c6e2a8d358b4bd705fa019a0d5b10d5b457591cf699e53b8aff36d9ba30fb1d"
    ),
    "openai/_base_client.py": (
        "53dc8c82344056600a08f51df158956827bdcc1a15cd4d3e1ce905a22663bd4c"
    ),
    "openai/_client.py": (
        "e2421659ea3ebd4ede9c940ae449e3cea65c096f21d97a1ece44f194aeda85ae"
    ),
    "openai/_constants.py": (
        "eeccbc82822f0e4372f42f666afd1d1e1fe80cb2ef71357018a0170ac6b9ce32"
    ),
}
_AUDITED_OPENAI_AGGREGATE_DIGEST = (
    "a4a2193775e68b1497d61c84ad851e785597db0f0a2a443856d3b890fa412e47"
)
_AUDITED_HTTPX_VERSION = "0.28.1"
_AUDITED_HTTPCORE_VERSION = "1.0.9"
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


def reviewed_openai_capability_identity() -> dict[str, str]:
    """Return the reviewed RESOURCE_BOUNDS capability identity (not self-hash)."""
    return {
        "openai_version": _AUDITED_OPENAI_VERSION,
        "openai_source_digest": _AUDITED_OPENAI_AGGREGATE_DIGEST,
        "native_http_family": "httpx",
        "native_http_version": _AUDITED_HTTPX_VERSION,
        "httpcore_version": _AUDITED_HTTPCORE_VERSION,
        "prepare_options_hook": _PREPARE_HOOK,
        "send_request_hook": _SEND_HOOK,
        "native_dispatch_hook": _NATIVE_HOOK,
        **{f"source:{k}": v for k, v in _AUDITED_OPENAI_SOURCE_DIGESTS.items()},
    }


def _installed_matches_reviewed(
    *,
    version: str,
    digests: dict[str, str],
    aggregate: str,
    httpx_version: str,
    httpcore_version: str,
) -> tuple[bool, tuple[str, ...]]:
    blockers: list[str] = []
    if version != _AUDITED_OPENAI_VERSION:
        blockers.append(
            f"unsupported_openai_version:installed_{version}"
            f"_audited_{_AUDITED_OPENAI_VERSION}"
        )
    if aggregate != _AUDITED_OPENAI_AGGREGATE_DIGEST:
        blockers.append("openai_source_digest_drift_vs_reviewed")
    for key, expected in _AUDITED_OPENAI_SOURCE_DIGESTS.items():
        actual = digests.get(key)
        if actual != expected:
            blockers.append(f"openai_source_file_digest_drift:{key}")
    if httpx_version != _AUDITED_HTTPX_VERSION:
        blockers.append(
            f"httpx_version_drift:installed_{httpx_version}"
            f"_audited_{_AUDITED_HTTPX_VERSION}"
        )
    if httpcore_version != _AUDITED_HTTPCORE_VERSION:
        blockers.append(
            f"httpcore_version_drift:installed_{httpcore_version}"
            f"_audited_{_AUDITED_HTTPCORE_VERSION}"
        )
    return (len(blockers) == 0), tuple(dict.fromkeys(blockers))


def build_audited_sdk_observation_profile() -> SdkObservationProfile:
    """Build profile for installed SDK; supported only if it matches reviewed identity."""
    version = importlib.metadata.version("openai")
    import httpx

    digests = installed_openai_source_digests()
    aggregate = aggregate_openai_source_digest(digests)
    httpx_version = httpx.__version__
    httpcore_version = importlib.metadata.version("httpcore")
    matches, blockers = _installed_matches_reviewed(
        version=version,
        digests=digests,
        aggregate=aggregate,
        httpx_version=httpx_version,
        httpcore_version=httpcore_version,
    )
    return SdkObservationProfile(
        openai_version=version,
        openai_source_digest=aggregate,
        native_http_family="httpx",
        native_http_version=httpx_version,
        httpcore_version=httpcore_version,
        source_file_digests=tuple(sorted(digests.items())),
        max_retries_default=2,
        sdk_attempts_per_call=3,
        prepare_options_hook=_PREPARE_HOOK,
        send_request_hook=_SEND_HOOK,
        native_dispatch_hook=_NATIVE_HOOK,
        supported=matches,
        blockers=blockers,
    )


def build_fixture_sdk_observation_profile() -> SdkObservationProfile:
    """Installed-hook fixture profile for offline MockTransport tests.

    Never claims reviewed/production support. Used only for harness observation
    wiring when the installed tuple differs from the RESOURCE_BOUNDS audit.
    """
    version = importlib.metadata.version("openai")
    import httpx

    digests = installed_openai_source_digests()
    aggregate = aggregate_openai_source_digest(digests)
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
        supported=False,
        blockers=("fixture_only_installed_profile_not_reviewed",),
    )


def _profile_hook_identity_ok(profile: SdkObservationProfile) -> tuple[bool, tuple[str, ...]]:
    blockers: list[str] = []
    if profile.prepare_options_hook != _PREPARE_HOOK:
        blockers.append("prepare_options_hook_mismatch")
    if profile.send_request_hook != _SEND_HOOK:
        blockers.append("send_request_hook_mismatch")
    if profile.native_dispatch_hook != _NATIVE_HOOK:
        blockers.append("native_dispatch_hook_mismatch")
    return (len(blockers) == 0), tuple(blockers)


def _profile_identity_blockers(
    profile: SdkObservationProfile,
    installed: SdkObservationProfile,
) -> list[str]:
    """Compare transport identity fields the version check does not cover."""
    blockers: list[str] = []
    if profile.native_http_family != installed.native_http_family:
        blockers.append("native_http_family_mismatch")
    if profile.native_http_version != installed.native_http_version:
        blockers.append("native_http_version_mismatch")
    if profile.httpcore_version != installed.httpcore_version:
        blockers.append("httpcore_version_mismatch")
    if tuple(sorted(profile.source_file_digests)) != tuple(
        sorted(installed.source_file_digests)
    ):
        blockers.append("source_file_digests_mismatch")
    if profile.max_retries_default != installed.max_retries_default:
        blockers.append("max_retries_default_mismatch")
    if profile.sdk_attempts_per_call != installed.sdk_attempts_per_call:
        blockers.append("sdk_attempts_per_call_mismatch")
    return blockers


def _profile_matches_installed(
    profile: SdkObservationProfile,
    *,
    allow_fixture_offline_boundary: bool = False,
) -> tuple[bool, tuple[str, ...], bool]:
    """Return (ok_to_attach, blockers, audited_supported).

    Audited support requires reviewed identity. Fixture-only attach requires an
    explicit verified offline boundary and never claims unsupported profiles as
    supported.
    """
    installed = build_audited_sdk_observation_profile()
    blockers: list[str] = []
    hook_ok, hook_blockers = _profile_hook_identity_ok(profile)
    blockers.extend(hook_blockers)
    identity_blockers = _profile_identity_blockers(profile, installed)
    blockers.extend(identity_blockers)

    if profile.openai_version != installed.openai_version:
        blockers.append(
            "dependency_identity_drift:"
            f"profile_{profile.openai_version}_vs_installed_{installed.openai_version}"
        )
    if profile.openai_source_digest != installed.openai_source_digest:
        blockers.append("openai_source_digest_drift")

    audited_supported = bool(profile.supported and installed.supported and not blockers)
    if profile.supported and not installed.supported:
        blockers.extend(installed.blockers or ("unsupported_sdk_profile",))
    if profile.supported and not audited_supported and installed.supported:
        blockers.append("profile_claims_support_without_reviewed_match")

    # Canonical unsupported profiles must not attach.
    if not profile.supported and not allow_fixture_offline_boundary:
        blockers.append("unsupported_sdk_profile_requires_offline_boundary")
        return False, tuple(dict.fromkeys(blockers + list(profile.blockers))), False

    fixture_attach_ok = (
        allow_fixture_offline_boundary
        and hook_ok
        and not identity_blockers
        and profile.openai_version == installed.openai_version
        and profile.openai_source_digest == installed.openai_source_digest
        and not any(
            reason.startswith("dependency_identity_drift")
            or reason == "openai_source_digest_drift"
            or reason.endswith("hook_mismatch")
            for reason in blockers
        )
    )
    if profile.supported and not audited_supported:
        return False, tuple(dict.fromkeys(blockers)), False
    if audited_supported:
        return True, (), True
    if fixture_attach_ok:
        return True, tuple(dict.fromkeys(profile.blockers)), False
    return False, tuple(dict.fromkeys(blockers or profile.blockers)), False


def attach_sdk_observation(
    client: object,
    *,
    binding: TelemetryBinding,
    profile: SdkObservationProfile,
    allow_fixture_offline_boundary: bool = False,
) -> ClientObservationDescriptor:
    """Attach per-instance observation to an already-constructed AsyncOpenAI client."""
    ok, blockers, audited = _profile_matches_installed(
        profile,
        allow_fixture_offline_boundary=allow_fixture_offline_boundary,
    )
    if not ok:
        binding.mark_invalid("unsupported_sdk_profile")
        for reason in blockers:
            binding.mark_invalid(reason)
        descriptor = ClientObservationDescriptor(
            origin="unsupported",
            openai_version=profile.openai_version,
            native_http_family=profile.native_http_family,
            profile_supported=False,
            blockers=blockers,
            fixture_only=True,
        )
        binding.attach_descriptor(descriptor)
        return descriptor

    # Instance-local wrappers; never patch the class globally.
    prepare = getattr(client, "_prepare_options", None)
    send_request = getattr(client, "_send_request", None)
    http_client = getattr(client, "_client", None)
    if prepare is None or send_request is None or http_client is None:
        blockers = ("unavailable_retry_telemetry:missing_hook_points",)
        binding.mark_invalid(blockers[0])
        descriptor = ClientObservationDescriptor(
            origin="unsupported",
            openai_version=profile.openai_version,
            native_http_family=profile.native_http_family,
            profile_supported=False,
            blockers=blockers,
            fixture_only=True,
        )
        binding.attach_descriptor(descriptor)
        return descriptor

    state: dict[str, Any] = {
        "attempt_index": 0,
        "current_attempt_id": None,
        "last_attempt_id": None,
        "current_send_id": None,
        "last_send_id": None,
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
            state["last_attempt_id"] = attempt_id
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
            elif status in {408, 409, 429} or (
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
            # Keep last_attempt_id for post-return usage emission; send_request
            # ends before planner reads the response and emits UsageObservation.
            state["last_attempt_id"] = attempt_id
            state["current_attempt_id"] = None

    seen_transport_ids: set[int] = set()

    def _transport_is_mock(transport: Any) -> bool:
        return transport is not None and type(transport).__name__ == "MockTransport"

    def _wrap_transport(transport: Any) -> bool:
        if transport is None or not hasattr(transport, "handle_async_request"):
            return False
        identity = id(transport)
        if identity in seen_transport_ids:
            return True
        seen_transport_ids.add(identity)
        original_transport_request = transport.handle_async_request

        async def observed_transport_request(request: Any) -> Any:
            attempt_id = state.get("current_attempt_id") or ""
            send_id = binding.new_id("http")
            state["current_send_id"] = send_id
            state["last_send_id"] = send_id
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
        return True

    # Observe the actual dispatch path: default transport, mounts, and proxy
    # transports. Wrapping only ``_transport`` misses mounted/proxy routes.
    wrapped_any = False
    wrapped_any = _wrap_transport(getattr(http_client, "_transport", None)) or wrapped_any
    mounts = getattr(http_client, "_mounts", None)
    if isinstance(mounts, dict):
        for mounted in mounts.values():
            wrapped_any = _wrap_transport(mounted) or wrapped_any
    # Some httpx proxy configurations expose an additional pool transport.
    for attr in ("_proxy_transport", "_proxies"):
        extra = getattr(http_client, attr, None)
        if extra is None:
            continue
        if isinstance(extra, dict):
            for mounted in extra.values():
                wrapped_any = _wrap_transport(mounted) or wrapped_any
        else:
            wrapped_any = _wrap_transport(extra) or wrapped_any

    if not wrapped_any:

        async def observed_http_send(request: Any, *args: Any, **kwargs: Any) -> Any:
            attempt_id = state.get("current_attempt_id") or ""
            send_id = binding.new_id("http")
            state["current_send_id"] = send_id
            state["last_send_id"] = send_id
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
    mock_transport = _transport_is_mock(getattr(http_client, "_transport", None))
    if not mock_transport:
        mounts = getattr(http_client, "_mounts", None)
        if isinstance(mounts, dict):
            mock_transport = any(_transport_is_mock(item) for item in mounts.values())
    canonical = audited and not mock_transport and not allow_fixture_offline_boundary
    descriptor = ClientObservationDescriptor(
        origin="canonical_sdk" if canonical else "mock_native",
        openai_version=profile.openai_version,
        native_http_family=profile.native_http_family,
        profile_supported=canonical,
        blockers=() if canonical else blockers,
        fixture_only=not canonical,
    )
    object.__setattr__(client, "_signal_diag_observation_descriptor", descriptor)
    binding.attach_descriptor(descriptor)
    return descriptor


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("non-int subdivision")
    if value < 0:
        raise ValueError("negative subdivision")
    return value


def _extract_subdivisions(usage: object) -> tuple[int | None, int | None, int | None]:
    cache_hit = None
    cache_miss = None
    reasoning = None
    prompt_details = getattr(usage, "prompt_tokens_details", None)
    if prompt_details is not None:
        # OpenAI-style cached_tokens maps to cache_hit; miss derived when both known.
        cached = getattr(prompt_details, "cached_tokens", None)
        if cached is None and isinstance(prompt_details, dict):
            cached = prompt_details.get("cached_tokens")
        cache_hit = _optional_int(cached)
    completion_details = getattr(usage, "completion_tokens_details", None)
    if completion_details is not None:
        reasoning_raw = getattr(completion_details, "reasoning_tokens", None)
        if reasoning_raw is None and isinstance(completion_details, dict):
            reasoning_raw = completion_details.get("reasoning_tokens")
        reasoning = _optional_int(reasoning_raw)
    # Provider-specific cache hit/miss pair (DeepSeek-style).
    hit = getattr(usage, "prompt_cache_hit_tokens", None)
    miss = getattr(usage, "prompt_cache_miss_tokens", None)
    if hit is not None or miss is not None:
        cache_hit = _optional_int(hit)
        cache_miss = _optional_int(miss)
    return cache_hit, cache_miss, reasoning


def emit_usage_from_response(
    binding: TelemetryBinding,
    response: object,
    *,
    send_id: str | None = None,
    attempt_id: str | None = None,
) -> None:
    """Extract allowlisted usage/model metadata before planner JSON validation."""
    usage = getattr(response, "usage", None)
    model = getattr(response, "model", None)
    fingerprint = getattr(response, "system_fingerprint", None)
    resolved_attempt = attempt_id or binding.current_attempt_id or ""
    call_id = binding.current_call_id or ""
    turn_id = binding.current_turn_id or ""
    resolved_send = send_id or ""
    usage_corr = binding.new_id("usage")
    if usage is None:
        emit_safely(
            binding,
            UsageObservation(
                sequence_id=binding.new_id("seq"),
                correlation_id=usage_corr,
                turn_id=turn_id,
                call_id=call_id,
                attempt_id=resolved_attempt,
                send_id=resolved_send,
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
        cache_hit, cache_miss, reasoning = _extract_subdivisions(usage)
        if (
            cache_hit is not None
            and cache_miss is not None
            and cache_hit + cache_miss != prompt
        ):
            raise ValueError("cache hit+miss must equal prompt_tokens")
        if reasoning is not None and reasoning > completion:
            raise ValueError("reasoning_tokens cannot exceed completion_tokens")
        status: UsageStatus = "complete"
    except Exception:  # noqa: BLE001
        emit_safely(
            binding,
            UsageObservation(
                sequence_id=binding.new_id("seq"),
                correlation_id=usage_corr,
                turn_id=turn_id,
                call_id=call_id,
                attempt_id=resolved_attempt,
                send_id=resolved_send,
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
            correlation_id=usage_corr,
            turn_id=turn_id,
            call_id=call_id,
            attempt_id=resolved_attempt,
            send_id=resolved_send,
            status=status,
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
            cache_hit_tokens=cache_hit,
            cache_miss_tokens=cache_miss,
            reasoning_tokens=reasoning,
            response_model=model if isinstance(model, str) else None,
            fingerprint=fingerprint if isinstance(fingerprint, str) else None,
            monotonic_s=binding.clock(),
            parent_id=call_id or None,
        ),
    )
