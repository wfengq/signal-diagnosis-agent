"""Phase C Task 7: independent retest planner protocol and SDK adapter."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from signal_diag.agent.retest_planner import (
    RETEST_PLANNER_IDENTITY,
    OpenAICompatibleRetestClient,
    RealLLMRetestPlanner,
    RetestCallLimits,
    RetestPlannerError,
    build_openai_retest_client,
    build_retest_context,
    eligible_retests,
    parse_retest_selection,
    render_recommendation_detail,
)
from signal_diag.app.pcm_wav import encode_pcm32_wav
from signal_diag.app.regression import RegressionWorkbenchService
from signal_diag.rules.regression import ComparisonConditions
from signal_diag.signal import generate_sine
from signal_diag.tools.regression_measurement import (
    ClippingInput,
    HarmonicDistortionInput,
    MeasurementSelection,
)
from tests.app.test_regression_service import _upload


def _conditions(**overrides: object) -> ComparisonConditions:
    base: dict[str, object] = {
        "intent": "preserve_behavior",
        "baseline_version": "v1",
        "candidate_version": "v2",
        "stimulus_key": "sine-200",
        "parameters_key": "default",
        "same_input": "yes",
        "parameters_unchanged": "yes",
        "aligned_ranges": "yes",
        "repeatability": "declared_deterministic",
    }
    base.update(overrides)
    return ComparisonConditions.model_validate(base)


def _selection() -> MeasurementSelection:
    return MeasurementSelection(
        clipping=ClippingInput(channel="left", full_scale_threshold=0.99),
        harmonic=HarmonicDistortionInput(channel="left", fundamental_hz=200.0),
    )


def _mono_wav() -> bytes:
    case = generate_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.5,
        amplitude=0.4,
    )
    return encode_pcm32_wav(case.record.samples, sample_rate_hz=48_000)


async def _record(**condition_overrides: object):
    from datetime import UTC, datetime

    service = RegressionWorkbenchService(clock=lambda: datetime(2026, 10, 4, tzinfo=UTC))
    wav = _mono_wav()
    case = service.create_case("goal")
    upload = _upload(wav, wav, conditions=_conditions(**condition_overrides))
    snap = await service.submit_comparison(case.case_id, upload, request_id="r1")
    await service.aclose()
    return snap.comparisons[0].record


def test_identity_is_unqualified_constant() -> None:
    assert RETEST_PLANNER_IDENTITY == "v0.3-s1-retest-1.0"


def test_limits_reject_bool_and_nonpositive() -> None:
    with pytest.raises((ValidationError, TypeError)):
        RetestCallLimits(max_output_tokens=True, timeout_s=1.0)  # type: ignore[arg-type]
    with pytest.raises((ValidationError, TypeError)):
        RetestCallLimits(max_output_tokens=16, timeout_s=True)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        RetestCallLimits(max_output_tokens=0, timeout_s=1.0)
    with pytest.raises(ValidationError):
        RetestCallLimits(max_output_tokens=16, timeout_s=float("nan"))


@pytest.mark.asyncio
async def test_eligible_complete_when_declaration_missing() -> None:
    record = await _record(same_input="unknown")
    options = eligible_retests(record)
    assert [item.kind for item in options] == ["complete_conditions"]
    assert all(item.option_id.startswith("opt_") for item in options)


@pytest.mark.asyncio
async def test_complete_conditions_not_offered_for_declared_no() -> None:
    record = await _record(same_input="no")
    options = eligible_retests(record)
    assert "complete_conditions" not in {item.kind for item in options}


@pytest.mark.asyncio
async def test_eligible_repeat_when_repeatability_unknown() -> None:
    record = await _record(repeatability="unknown")
    options = eligible_retests(record)
    assert [item.kind for item in options] == ["repeat_conditions"]


@pytest.mark.asyncio
async def test_lower_both_inputs_ineligible_without_approved_level_params() -> None:
    record = await _record()
    options = eligible_retests(record)
    assert options == ()
    assert "lower_both_inputs" not in {item.kind for item in options}


@pytest.mark.asyncio
async def test_context_has_no_waveform_fft_or_oracle() -> None:
    record = await _record(same_input="no")
    context = build_retest_context(record)
    dumped = json.dumps(context.model_dump(mode="json"))
    assert "wav" not in dumped.casefold()
    assert "fft" not in dumped.casefold()
    assert "oracle" not in dumped.casefold()
    assert "goal" not in dumped.casefold()
    assert context.comparison_digest == record.digest


@pytest.mark.asyncio
async def test_parse_rejects_unknown_option_forged_refs_and_forbidden_fields() -> None:
    record = await _record(same_input="unknown")
    context = build_retest_context(record)
    with pytest.raises(RetestPlannerError, match="not in the eligible catalog"):
        parse_retest_selection(
            json.dumps(
                {
                    "option_id": "opt_forged",
                    "basis_refs": [context.compact_findings[0].finding_id],
                    "abstain_reason_code": None,
                }
            ),
            context=context,
        )
    with pytest.raises(RetestPlannerError, match="basis_refs"):
        parse_retest_selection(
            json.dumps(
                {
                    "option_id": context.eligible_options[0].option_id,
                    "basis_refs": ["finding_missing"],
                    "abstain_reason_code": None,
                }
            ),
            context=context,
        )
    with pytest.raises(RetestPlannerError, match="forbidden"):
        parse_retest_selection(
            json.dumps(
                {
                    "option_id": context.eligible_options[0].option_id,
                    "basis_refs": [context.compact_findings[0].finding_id],
                    "abstain_reason_code": None,
                    "gain": 0.5,
                }
            ),
            context=context,
        )
    with pytest.raises(RetestPlannerError, match="at most one"):
        parse_retest_selection(
            json.dumps(
                {
                    "option_ids": [
                        context.eligible_options[0].option_id,
                        "opt_other",
                    ],
                    "basis_refs": [],
                    "abstain_reason_code": None,
                }
            ),
            context=context,
        )


@pytest.mark.asyncio
async def test_parse_rejects_free_text_abstain_and_empty_basis() -> None:
    record = await _record(same_input="unknown")
    context = build_retest_context(record)
    with pytest.raises(RetestPlannerError, match="validation"):
        parse_retest_selection(
            json.dumps(
                {
                    "option_id": None,
                    "basis_refs": [],
                    "abstain_reason_code": (
                        "the candidate build has a clipping FAULT, lower gain by 6 dB"
                    ),
                }
            ),
            context=context,
        )
    with pytest.raises(RetestPlannerError, match="validation"):
        parse_retest_selection(
            json.dumps(
                {
                    "option_id": context.eligible_options[0].option_id,
                    "basis_refs": [],
                    "abstain_reason_code": None,
                }
            ),
            context=context,
        )
    closed = parse_retest_selection(
        json.dumps(
            {
                "option_id": None,
                "basis_refs": [],
                "abstain_reason_code": "planner_abstain",
            }
        ),
        context=context,
    )
    assert closed.abstain_reason_code == "planner_abstain"


class _FakeCompletions:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._response_text = "{}"
        self._error: Exception | None = None

    def set_text(self, text: str) -> None:
        self._response_text = text

    def set_error(self, error: Exception) -> None:
        self._error = error

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        message = SimpleNamespace(content=self._response_text)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


class _FakeChat:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.completions = completions


class _FakeSDK:
    def __init__(self) -> None:
        self.completions = _FakeCompletions()
        self.chat = _FakeChat(self.completions)
        self.closed = False
        self.max_retries = 0

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_real_planner_via_sdk_adapter_one_call_and_limits() -> None:
    record = await _record(same_input="unknown", repeatability="unknown")
    context = build_retest_context(record)
    sdk = _FakeSDK()
    finding = context.compact_findings[0].finding_id
    option_id = context.eligible_options[0].option_id
    sdk.completions.set_text(
        json.dumps(
            {
                "option_id": option_id,
                "basis_refs": [finding],
                "abstain_reason_code": None,
            }
        )
    )
    client = OpenAICompatibleRetestClient(sdk)
    planner = RealLLMRetestPlanner(
        client=client,
        model="fake-model",
        limits=RetestCallLimits(max_output_tokens=128, timeout_s=2.5),
    )
    selection = await planner.choose(context)
    assert selection.option_id == option_id
    assert len(sdk.completions.calls) == 1
    call = sdk.completions.calls[0]
    assert call["model"] == "fake-model"
    assert call["max_tokens"] == 128
    assert call["timeout"] == 2.5
    assert sdk.max_retries == 0
    await planner.aclose()
    assert sdk.closed is True


@pytest.mark.asyncio
async def test_no_eligible_options_skips_sdk_call() -> None:
    record = await _record()
    context = build_retest_context(record)
    sdk = _FakeSDK()
    planner = RealLLMRetestPlanner(
        client=OpenAICompatibleRetestClient(sdk),
        model="fake-model",
        limits=RetestCallLimits(max_output_tokens=64, timeout_s=1.0),
    )
    selection = await planner.choose(context)
    assert selection.option_id is None
    assert selection.abstain_reason_code == "no_eligible_options"
    assert sdk.completions.calls == []


@pytest.mark.asyncio
async def test_transport_timeout_and_invalid_json() -> None:
    record = await _record(same_input="unknown")
    context = build_retest_context(record)
    limits = RetestCallLimits(max_output_tokens=64, timeout_s=1.0)

    sdk_timeout = _FakeSDK()
    sdk_timeout.completions.set_error(TimeoutError("slow"))
    planner = RealLLMRetestPlanner(
        client=OpenAICompatibleRetestClient(sdk_timeout),
        model="m",
        limits=limits,
    )
    with pytest.raises(RetestPlannerError, match="transport failed"):
        await planner.choose(context)
    assert len(sdk_timeout.completions.calls) == 1

    sdk_bad = _FakeSDK()
    sdk_bad.completions.set_text("not-json")
    planner_bad = RealLLMRetestPlanner(
        client=OpenAICompatibleRetestClient(sdk_bad),
        model="m",
        limits=limits,
    )
    with pytest.raises(RetestPlannerError, match="invalid JSON"):
        await planner_bad.choose(context)


@pytest.mark.asyncio
async def test_cancel_during_sdk_call_closes_without_second_request() -> None:
    record = await _record(same_input="unknown")
    context = build_retest_context(record)
    started = asyncio.Event()
    release = asyncio.Event()

    class _SlowSDK(_FakeSDK):
        async def create_proxy(self, **kwargs: Any) -> Any:
            self.completions.calls.append(kwargs)
            started.set()
            await release.wait()
            message = SimpleNamespace(content="{}")
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    sdk = _SlowSDK()

    async def create(**kwargs: Any) -> Any:
        return await sdk.create_proxy(**kwargs)

    sdk.chat.completions.create = create  # type: ignore[method-assign]
    planner = RealLLMRetestPlanner(
        client=OpenAICompatibleRetestClient(sdk),
        model="m",
        limits=RetestCallLimits(max_output_tokens=32, timeout_s=5.0),
    )
    task = asyncio.create_task(planner.choose(context))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    release.set()
    await asyncio.sleep(0.02)
    assert len(sdk.completions.calls) == 1
    await planner.aclose()


def test_adapter_rejects_nonzero_max_retries() -> None:
    sdk = _FakeSDK()
    sdk.max_retries = 2
    with pytest.raises(RetestPlannerError, match="max_retries must be 0"):
        OpenAICompatibleRetestClient(sdk)


def test_build_openai_retest_client_locks_retries_and_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("openai")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://evil.example/v1")
    monkeypatch.setenv("OPENAI_ORG_ID", "org-should-not-matter")
    client = build_openai_retest_client(api_key="sk-test")
    sdk = client._client
    assert sdk.max_retries == 0
    assert str(sdk.base_url).rstrip("/") == "https://api.openai.com/v1"
    custom = build_openai_retest_client(
        api_key="sk-test",
        base_url="https://custom.example/v1",
    )
    assert str(custom._client.base_url).rstrip("/") == "https://custom.example/v1"


@pytest.mark.asyncio
async def test_real_async_openai_mock_transport_one_call_on_http_500() -> None:
    openai = pytest.importorskip("openai")
    httpx = pytest.importorskip("httpx")

    record = await _record(same_input="unknown")
    context = build_retest_context(record)
    hits: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hits.append(request.method)
        return httpx.Response(500, json={"error": {"message": "boom"}})

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    sdk = openai.AsyncOpenAI(
        api_key="sk-test",
        base_url="https://example.test/v1",
        max_retries=0,
        http_client=http_client,
    )
    planner = RealLLMRetestPlanner(
        client=OpenAICompatibleRetestClient(sdk),
        model="fake-model",
        limits=RetestCallLimits(max_output_tokens=32, timeout_s=2.0),
    )
    with pytest.raises(RetestPlannerError, match="transport failed"):
        await planner.choose(context)
    assert len(hits) == 1
    await planner.aclose()
    await http_client.aclose()


@pytest.mark.asyncio
async def test_transport_connection_error_is_planner_error() -> None:
    record = await _record(same_input="unknown")
    context = build_retest_context(record)
    sdk = _FakeSDK()
    sdk.completions.set_error(ConnectionError("down"))
    planner = RealLLMRetestPlanner(
        client=OpenAICompatibleRetestClient(sdk),
        model="m",
        limits=RetestCallLimits(max_output_tokens=32, timeout_s=1.0),
    )
    with pytest.raises(RetestPlannerError, match="transport failed"):
        await planner.choose(context)
    assert len(sdk.completions.calls) == 1


@pytest.mark.asyncio
async def test_render_abstain_uses_closed_user_text_not_model_prose() -> None:
    record = await _record(same_input="unknown")
    context = build_retest_context(record)
    selection = parse_retest_selection(
        json.dumps(
            {
                "option_id": None,
                "basis_refs": [],
                "abstain_reason_code": "planner_abstain",
            }
        ),
        context=context,
    )
    detail = render_recommendation_detail(selection, context=context)
    assert detail == "No retest recommendation (planner abstained)."
    assert "FAULT" not in detail
    assert "gain" not in detail.casefold()
