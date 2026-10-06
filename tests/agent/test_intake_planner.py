"""T-CX387 and T-CX388: intake draft validation and credential fail-closed."""

from __future__ import annotations

import json

import httpx
import pytest
from pydantic import ValidationError

from signal_diag.agent.intake import (
    INTAKE_PLANNER_IDENTITY,
    ConfirmedContext,
    ContextDraft,
    IntakeCallLimits,
    IntakeCredentialsError,
    IntakePlannerError,
    IntakeRequest,
    RealLLMIntakePlanner,
    ScriptedIntakePlanner,
    build_openai_intake_client,
    to_contextual_submit_kwargs,
    validate_context_draft,
)
from signal_diag.app.composition import build_product_service


def _request(**overrides: object) -> IntakeRequest:
    payload: dict[str, object] = {
        "text": "新功放放 1 kHz 测试音发毛，旧功放的录音也附上了",
        "filenames": ("new.wav", "old.wav"),
        "test_file": "new.wav",
        "sample_rates_hz": (48_000.0, 48_000.0),
    }
    payload.update(overrides)
    return IntakeRequest.model_validate(payload)


def _draft(**overrides: object) -> ContextDraft:
    payload: dict[str, object] = {
        "mode": "paired_reference",
        "nominal_fundamental_hz": 1000.0,
        "reference_file": "old.wav",
        "stimulus_kind": "single_tone",
        "missing_fields": (),
        "questions": (),
    }
    payload.update(overrides)
    return ContextDraft.model_validate(payload)


def test_t_cx387_nominal_hz_must_match_text_including_khz() -> None:
    request = _request()
    validate_context_draft(_draft(), request)
    validate_context_draft(_draft(nominal_fundamental_hz=1.0), request)
    with pytest.raises(IntakePlannerError, match="nominal"):
        validate_context_draft(_draft(nominal_fundamental_hz=440.0), request)
    hz_request = _request(text="标称 1000 Hz 正弦")
    validate_context_draft(
        _draft(nominal_fundamental_hz=1000.0, stimulus_kind="single_tone"),
        hz_request,
    )
    with pytest.raises(IntakePlannerError, match="nominal"):
        validate_context_draft(_draft(nominal_fundamental_hz=1.0), hz_request)


def test_t_cx387_reference_file_must_be_an_upload_and_not_the_test_file() -> None:
    request = _request()
    with pytest.raises(IntakePlannerError, match="reference"):
        validate_context_draft(_draft(reference_file="new.wav"), request)
    with pytest.raises(IntakePlannerError, match="reference"):
        validate_context_draft(_draft(reference_file="missing.wav"), request)


def test_t_cx387_paired_reference_requires_two_files() -> None:
    request = _request(filenames=("only.wav",), test_file="only.wav", sample_rates_hz=(48_000.0,))
    with pytest.raises(IntakePlannerError, match="paired_reference"):
        validate_context_draft(
            _draft(mode="paired_reference", reference_file=None, nominal_fundamental_hz=None),
            request,
        )


def test_t_cx387_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ContextDraft.model_validate(
            {
                "mode": "single_signal",
                "nominal_fundamental_hz": None,
                "reference_file": None,
                "stimulus_kind": None,
                "missing_fields": (),
                "questions": (),
                "thd_limit_percent": 1.0,
            }
        )


def test_t_cx387_empty_nominal_needs_no_number_in_the_text() -> None:
    request = _request(
        text="听着发毛",
        filenames=("only.wav",),
        test_file="only.wav",
        sample_rates_hz=(48_000.0,),
    )
    validate_context_draft(
        _draft(
            mode="single_signal",
            nominal_fundamental_hz=None,
            reference_file=None,
            stimulus_kind=None,
            missing_fields=("nominal_fundamental_hz",),
            questions=("标称频率是多少？",),
        ),
        request,
    )


@pytest.mark.asyncio
async def test_t_cx388_planner_sends_text_and_file_metadata_only() -> None:
    seen: list[str] = []

    class _Client:
        async def complete(
            self,
            *,
            model: str,
            system_prompt: str,
            user_json: str,
            limits: IntakeCallLimits,
        ) -> str:
            del model, system_prompt, limits
            seen.append(user_json)
            return json.dumps(
                {
                    "mode": "paired_reference",
                    "nominal_fundamental_hz": 1000.0,
                    "reference_file": "old.wav",
                    "stimulus_kind": "single_tone",
                    "missing_fields": [],
                    "questions": [],
                }
            )

        async def aclose(self) -> None:
            return None

    planner = RealLLMIntakePlanner(
        client=_Client(),
        model="deepseek-v4-flash",
        limits=IntakeCallLimits(max_output_tokens=64, timeout_s=1.0),
    )
    draft = await planner.propose(_request())
    assert draft.reference_file == "old.wav"
    payload = json.loads(seen[0])
    assert payload["text"].startswith("新功放")
    assert payload["filenames"] == ["new.wav", "old.wav"]
    assert payload["file_count"] == 2
    assert payload["sample_rates_hz"] == [48000.0, 48000.0]
    assert "waveform" not in payload
    assert "samples" not in payload
    assert "f0" not in payload
    assert planner.identity == INTAKE_PLANNER_IDENTITY


def test_t_cx388_missing_credentials_fail_without_scripted_fallback() -> None:
    from signal_diag.app.service import (
        intake_planner_from_diagnosis_planner,
        product_intake_planner,
    )

    service = build_product_service(environ={})
    assert service._dependencies.planner_configured is False
    assert service._dependencies.intake_planner_factory is None
    with pytest.raises(IntakeCredentialsError):
        product_intake_planner(api_key=None, base_url=None, model=None)
    configured = build_product_service(environ={"DEEPSEEK_API_KEY": "sk-test"})
    intake = intake_planner_from_diagnosis_planner(configured._dependencies.planner_factory())
    assert type(intake).__name__ == "RealLLMIntakePlanner"
    root = __import__("pathlib").Path(__file__).resolve().parents[2]
    composition = (root / "src/signal_diag/app/composition.py").read_text(encoding="utf-8")
    service_source = (root / "src/signal_diag/app/service.py").read_text(encoding="utf-8")
    assert "ScriptedIntakePlanner" not in composition
    assert "ScriptedIntakePlanner" not in service_source


def test_t_cx388_scripted_planner_is_not_the_product_factory() -> None:
    scripted = ScriptedIntakePlanner(_draft())
    assert scripted.identity == "scripted-intake-test-double"


@pytest.mark.asyncio
async def test_t_cx388_scripted_planner_still_validates() -> None:
    scripted = ScriptedIntakePlanner(_draft(nominal_fundamental_hz=440.0))
    with pytest.raises(IntakePlannerError, match="nominal"):
        await scripted.propose(_request())


def test_t_cx388_sdk_client_locks_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "https://evil.example/v1")
    client = build_openai_intake_client(api_key="sk-test")
    sdk = client._client
    assert sdk.max_retries == 0
    assert str(sdk.base_url).rstrip("/") == "https://api.openai.com/v1"
    assert sdk.organization == ""
    assert sdk.project == ""


@pytest.mark.asyncio
async def test_t_cx388_mock_transport_does_not_retry_on_http_500() -> None:
    hits: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hits.append(request.method)
        return httpx.Response(500, json={"error": {"message": "boom"}})

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    adapter = build_openai_intake_client(
        api_key="sk-test",
        base_url="https://example.test/v1",
        http_client=http_client,
    )
    planner = RealLLMIntakePlanner(
        client=adapter,
        model="deepseek-v4-flash",
        limits=IntakeCallLimits(max_output_tokens=32, timeout_s=2.0),
    )
    with pytest.raises(IntakePlannerError, match="transport"):
        await planner.propose(_request())
    assert len(hits) == 1
    await planner.aclose()


@pytest.mark.asyncio
async def test_t_cx405_intake_request_matches_planner_settings() -> None:
    """The wire body disables reasoning and asks for JSON, like the diagnosis planner.

    D1 round 1: without these, deepseek-v4-flash spent the output budget on
    reasoning and returned empty content for most intake calls.
    """
    bodies: list[dict[str, object]] = []
    draft = _draft().model_dump(mode="json")

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "x",
                "object": "chat.completion",
                "created": 0,
                "model": "deepseek-v4-flash",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": json.dumps(draft)},
                    }
                ],
            },
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = build_openai_intake_client(
        api_key="sk-test",
        base_url="https://example.test/v1",
        http_client=http_client,
    )
    planner = RealLLMIntakePlanner(
        client=adapter,
        model="deepseek-v4-flash",
        limits=IntakeCallLimits(max_output_tokens=800, timeout_s=2.0),
    )
    await planner.propose(_request())
    await planner.aclose()
    assert len(bodies) == 1
    body = bodies[0]
    assert body["thinking"] == {"type": "disabled"}
    assert body["response_format"] == {"type": "json_object"}
    assert body["temperature"] == 0.0
    assert body["max_tokens"] == 800


def test_t_cx389_confirmed_context_is_distinct_from_a_draft() -> None:
    confirmed = ConfirmedContext(
        mode="nominal_single_tone",
        nominal_fundamental_hz=1000.0,
        reference_file=None,
        stimulus_kind="single_tone",
    )
    kwargs = to_contextual_submit_kwargs(confirmed)
    assert kwargs["mode"] == "nominal_single_tone"
    assert kwargs["nominal_fundamental_hz"] == 1000.0
    with pytest.raises(TypeError, match="ConfirmedContext"):
        to_contextual_submit_kwargs(_draft())
