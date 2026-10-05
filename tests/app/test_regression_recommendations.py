"""Phase C Task 7: recommendation service/API wiring with fake SDK transport."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from signal_diag.agent.retest_planner import (
    OpenAICompatibleRetestClient,
    RealLLMRetestPlanner,
    RetestCallLimits,
    RetestSelection,
)
from signal_diag.app.errors import ApplicationError, InvalidRequestError
from signal_diag.app.pcm_wav import encode_pcm32_wav
from signal_diag.app.regression import (
    RegressionWorkbenchService,
    build_regression_service,
)
from signal_diag.app.regression_api import (
    build_regression_router,
    regression_application_error_handler,
)
from signal_diag.rules.regression import ComparisonConditions
from signal_diag.signal import generate_sine
from tests.app.test_regression_service import _upload

NOW = datetime(2026, 10, 4, 18, 0, tzinfo=UTC)


def _mono_wav() -> bytes:
    case = generate_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.5,
        amplitude=0.4,
    )
    return encode_pcm32_wav(case.record.samples, sample_rate_hz=48_000)


def _conditions(**overrides: object) -> ComparisonConditions:
    base: dict[str, object] = {
        "intent": "preserve_behavior",
        "baseline_version": "v1",
        "candidate_version": "v2",
        "stimulus_key": "sine-200",
        "parameters_key": "default",
        "same_input": "unknown",
        "parameters_unchanged": "yes",
        "aligned_ranges": "yes",
        "repeatability": "declared_deterministic",
    }
    base.update(overrides)
    return ComparisonConditions.model_validate(base)


class _FakeCompletions:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.text = "{}"

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        message = SimpleNamespace(content=self.text)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class _FakeSDK:
    def __init__(self) -> None:
        self.completions = _FakeCompletions()
        self.chat = SimpleNamespace(completions=self.completions)
        self.closed = False
        self.max_retries = 0

    async def close(self) -> None:
        self.closed = True


def _planner_with_sdk(sdk: _FakeSDK) -> RealLLMRetestPlanner:
    return RealLLMRetestPlanner(
        client=OpenAICompatibleRetestClient(sdk),
        model="fake-retest",
        limits=RetestCallLimits(max_output_tokens=64, timeout_s=2.0),
    )


def _configured_service(sdk: _FakeSDK) -> RegressionWorkbenchService:
    limits = RetestCallLimits(max_output_tokens=64, timeout_s=2.0)
    return RegressionWorkbenchService(
        clock=lambda: NOW,
        retest_planner=_planner_with_sdk(sdk),
        retest_model="fake-retest",
        retest_limits=limits,
    )


@pytest.mark.asyncio
async def test_product_builder_recommendations_unavailable() -> None:
    service = build_regression_service()
    assert service.recommendation_available is False
    wav = _mono_wav()
    case = service.create_case("goal")
    snap = await service.submit_comparison(
        case.case_id,
        _upload(wav, wav, conditions=_conditions()),
        request_id="cmp-1",
    )
    before = snap.comparisons[0].record.model_dump_json()
    out = await service.request_recommendation(
        case.case_id,
        snap.comparisons[0].comparison_id,
        request_id="rec-1",
    )
    assert out.recommendations[-1].status == "unavailable"
    assert "not enabled" in (out.recommendations[-1].detail or "")
    after = out.comparisons[0].record.model_dump_json()
    assert before == after
    await service.aclose()


@pytest.mark.asyncio
async def test_fake_sdk_path_one_call_and_idempotent_request_id() -> None:
    sdk = _FakeSDK()
    service = _configured_service(sdk)
    wav = _mono_wav()
    case = service.create_case("goal")
    snap = await service.submit_comparison(
        case.case_id,
        _upload(wav, wav, conditions=_conditions()),
        request_id="cmp-1",
    )
    comparison_id = snap.comparisons[0].comparison_id
    finding_id = "decl_same_input"
    # eligible complete_conditions
    sdk.completions.text = json.dumps(
        {
            "option_id": "opt_complete_conditions",
            "basis_refs": [finding_id],
            "abstain_reason_code": None,
        }
    )
    first = await service.request_recommendation(
        case.case_id,
        comparison_id,
        request_id="rec-1",
    )
    assert first.recommendations[-1].status == "completed"
    assert "Complete the missing" in (first.recommendations[-1].detail or "")
    assert len(sdk.completions.calls) == 1
    second = await service.request_recommendation(
        case.case_id,
        comparison_id,
        request_id="rec-1",
    )
    assert len(sdk.completions.calls) == 1
    assert len(second.recommendations) == len(first.recommendations)
    await service.aclose()
    assert sdk.closed is True


@pytest.mark.asyncio
async def test_request_id_conflict_and_unknown_comparison() -> None:
    sdk = _FakeSDK()
    service = _configured_service(sdk)
    wav = _mono_wav()
    case = service.create_case("goal")
    snap = await service.submit_comparison(
        case.case_id,
        _upload(wav, wav, conditions=_conditions()),
        request_id="cmp-1",
    )
    comparison_id = snap.comparisons[0].comparison_id
    sdk.completions.text = json.dumps(
        {
            "option_id": "opt_complete_conditions",
            "basis_refs": ["decl_same_input"],
            "abstain_reason_code": None,
        }
    )
    await service.request_recommendation(
        case.case_id,
        comparison_id,
        request_id="rec-1",
    )
    # second comparison with different digest, reuse request_id
    snap2 = await service.submit_comparison(
        case.case_id,
        _upload(wav, wav, conditions=_conditions(same_input="no")),
        request_id="cmp-2",
    )
    with pytest.raises(InvalidRequestError, match="different content"):
        await service.request_recommendation(
            case.case_id,
            snap2.comparisons[-1].comparison_id,
            request_id="rec-1",
        )
    with pytest.raises(InvalidRequestError, match="comparison does not exist"):
        await service.request_recommendation(
            case.case_id,
            "cmp_missing",
            request_id="rec-missing",
        )
    await service.aclose()


@pytest.mark.asyncio
async def test_http_recommendation_route_and_capabilities() -> None:
    sdk = _FakeSDK()
    service = _configured_service(sdk)
    app = FastAPI()
    app.include_router(build_regression_router(service))
    app.add_exception_handler(ApplicationError, regression_application_error_handler)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        caps = await client.get("/api/v1/regression/capabilities")
        assert caps.json()["recommendation_available"] is True
        created = await client.post("/api/v1/regression/cases", json={"goal": "g"})
        case_id = created.json()["case_id"]
        wav = _mono_wav()
        from tests.app.test_regression_api import _comparison_form, _metadata_bytes

        body, content_type = _comparison_form(
            wav,
            wav,
            metadata=_metadata_bytes(
                request_id="cmp-http",
                conditions=_conditions().model_dump(mode="json"),
            ),
        )
        compare = await client.post(
            f"/api/v1/regression/cases/{case_id}/comparisons",
            content=body,
            headers={"Content-Type": content_type},
        )
        assert compare.status_code == 200
        comparison_id = compare.json()["comparisons"][0]["comparison_id"]
        sdk.completions.text = json.dumps(
            {
                "option_id": "opt_complete_conditions",
                "basis_refs": ["decl_same_input"],
                "abstain_reason_code": None,
            }
        )
        rec = await client.post(
            f"/api/v1/regression/cases/{case_id}/comparisons/{comparison_id}/recommendations",
            json={"request_id": "rec-http"},
        )
        assert rec.status_code == 200
        assert rec.json()["recommendations"][-1]["status"] == "completed"
    await service.aclose()


@pytest.mark.asyncio
async def test_busy_rejects_second_recommendation_request() -> None:
    import asyncio

    sdk = _FakeSDK()
    service = _configured_service(sdk)
    wav = _mono_wav()
    case = service.create_case("goal")
    snap = await service.submit_comparison(
        case.case_id,
        _upload(wav, wav, conditions=_conditions()),
        request_id="cmp-1",
    )
    comparison_id = snap.comparisons[0].comparison_id
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_create(**kwargs: object) -> Any:
        sdk.completions.calls.append(dict(kwargs))
        started.set()
        await release.wait()
        message = SimpleNamespace(content="{}")
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    sdk.completions.create = slow_create  # type: ignore[method-assign]
    first = asyncio.create_task(
        service.request_recommendation(
            case.case_id,
            comparison_id,
            request_id="rec-a",
        )
    )
    await started.wait()
    with pytest.raises(InvalidRequestError, match="busy"):
        await service.request_recommendation(
            case.case_id,
            comparison_id,
            request_id="rec-b",
        )
    release.set()
    await first
    await service.aclose()


@pytest.mark.asyncio
async def test_cancel_waits_for_recommendation_work() -> None:
    import asyncio

    sdk = _FakeSDK()
    service = _configured_service(sdk)
    wav = _mono_wav()
    case = service.create_case("goal")
    snap = await service.submit_comparison(
        case.case_id,
        _upload(wav, wav, conditions=_conditions()),
        request_id="cmp-1",
    )
    comparison_id = snap.comparisons[0].comparison_id
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_create(**kwargs: object) -> Any:
        sdk.completions.calls.append(dict(kwargs))
        started.set()
        await release.wait()
        message = SimpleNamespace(
            content=json.dumps(
                {
                    "option_id": "opt_complete_conditions",
                    "basis_refs": ["decl_same_input"],
                    "abstain_reason_code": None,
                }
            )
        )
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    sdk.completions.create = slow_create  # type: ignore[method-assign]
    task = asyncio.create_task(
        service.request_recommendation(
            case.case_id,
            comparison_id,
            request_id="rec-cancel",
        )
    )
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    release.set()
    await asyncio.sleep(0.02)
    assert len(sdk.completions.calls) == 1
    assert service._busy is False
    await service.aclose()


@pytest.mark.asyncio
async def test_default_capabilities_recommendation_false() -> None:
    service = build_regression_service()
    app = FastAPI()
    app.include_router(build_regression_router(service))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        caps = await client.get("/api/v1/regression/capabilities")
        assert caps.json()["recommendation_available"] is False
    await service.aclose()


@pytest.mark.asyncio
async def test_service_rejects_forged_selection_from_protocol_planner() -> None:
    class _ForgedPlanner:
        async def choose(self, context: object) -> RetestSelection:
            del context
            return RetestSelection.model_construct(
                option_id="opt_lower_both_inputs",
                basis_refs=("forged",),
                abstain_reason_code=None,
            )

        async def aclose(self) -> None:
            return None

    service = RegressionWorkbenchService(
        clock=lambda: NOW,
        retest_planner=_ForgedPlanner(),  # type: ignore[arg-type]
        retest_model="ignored",
        retest_limits=RetestCallLimits(max_output_tokens=16, timeout_s=1.0),
    )
    wav = _mono_wav()
    case = service.create_case("goal")
    snap = await service.submit_comparison(
        case.case_id,
        _upload(wav, wav, conditions=_conditions()),
        request_id="cmp-1",
    )
    out = await service.request_recommendation(
        case.case_id,
        snap.comparisons[0].comparison_id,
        request_id="rec-forged",
    )
    rec = out.recommendations[-1]
    assert rec.status == "failed"
    assert "eligible catalog" in (rec.detail or "") or "basis_refs" in (rec.detail or "")
    await service.aclose()


@pytest.mark.asyncio
async def test_service_rejects_free_text_abstain_from_protocol_planner() -> None:
    class _FreeTextAbstainPlanner:
        async def choose(self, context: object) -> RetestSelection:
            del context
            return RetestSelection.model_construct(
                option_id=None,
                basis_refs=(),
                abstain_reason_code=(
                    "the candidate build has a clipping FAULT, lower gain by 6 dB"
                ),
            )

        async def aclose(self) -> None:
            return None

    service = RegressionWorkbenchService(
        clock=lambda: NOW,
        retest_planner=_FreeTextAbstainPlanner(),  # type: ignore[arg-type]
        retest_model="ignored",
        retest_limits=RetestCallLimits(max_output_tokens=16, timeout_s=1.0),
    )
    wav = _mono_wav()
    case = service.create_case("goal")
    snap = await service.submit_comparison(
        case.case_id,
        _upload(wav, wav, conditions=_conditions()),
        request_id="cmp-1",
    )
    out = await service.request_recommendation(
        case.case_id,
        snap.comparisons[0].comparison_id,
        request_id="rec-free",
    )
    rec = out.recommendations[-1]
    assert rec.status == "failed"
    assert "FAULT" not in (rec.detail or "")
    assert "gain" not in (rec.detail or "").casefold()
    await service.aclose()
