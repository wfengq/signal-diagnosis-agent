"""T-CX488–T-CX489: test guide model adapter and service (D057). No network."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from signal_diag.agent.guide import (
    GUIDE_PROMPT_VERSION,
    SYSTEM_PROMPT,
    GuideError,
    RealLLMGuide,
    ScriptedGuide,
)
from signal_diag.agent.intake import IntakeCallLimits
from signal_diag.app.errors import ApplicationError
from signal_diag.app.guide_service import (
    GuideIdentity,
    GuideService,
    build_guide_service,
    guide_payload,
)
from signal_diag.app.test_plan import GuideRequest

REQUEST = GuideRequest(text="我的音箱一开大声就破音，可以用声卡录，采样率 48 kHz。", filenames=())
GOOD = {
    "plan_id": "sweep_levels",
    "parameters": {
        "sample_rate_hz": 48000,
        "level_labels": ["低于平时", "平时音量", "出问题的音量"],
        "connection": "line_loopback",
        "test_file": None,
        "reference_file": None,
        "nominal_fundamental_hz": None,
        "defaults": ["level_labels"],
    },
    "missing_fields": [],
    "questions": [],
    "rationale_quotes": ["一开大声就破音", "可以用声卡录"],
}
SCRIPTED = GuideIdentity(provider="scripted", model="s")


class _FakeClient:
    def __init__(self, reply: str | Exception) -> None:
        self.reply = reply
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self, *, model: str, system_prompt: str, user_json: str, limits: IntakeCallLimits
    ) -> str:
        self.calls.append({"model": model, "system_prompt": system_prompt, "user_json": user_json})
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply

    async def aclose(self) -> None:
        return None


def test_t_cx488_adapter_sends_only_the_description() -> None:
    client = _FakeClient(json.dumps(GOOD, ensure_ascii=False))
    guide = RealLLMGuide(client=client, model="deepseek-test")
    assert guide.identity == GUIDE_PROMPT_VERSION == "v0.3-s1-guide-1.0"
    asyncio.run(guide.draft(guide_payload(REQUEST)))
    (call,) = client.calls
    assert call["system_prompt"] == SYSTEM_PROMPT
    assert set(json.loads(call["user_json"])) == {"text", "filenames", "sample_rates_hz"}
    for word in ("never invent", "rationale_quotes", "sweep_levels"):
        assert word in SYSTEM_PROMPT.lower() or word in SYSTEM_PROMPT
    with pytest.raises(GuideError):
        asyncio.run(RealLLMGuide(client=_FakeClient(TimeoutError()), model="m").draft("{}"))
    with pytest.raises(ValueError):
        RealLLMGuide(client=client, model=" ")


def test_t_cx489_questionnaire_default_model_result_and_fallbacks() -> None:
    default = asyncio.run(GuideService().draft(REQUEST))
    assert default.source == "questionnaire" and default.model_calls == 0
    assert default.questionnaire[0].question_id == "can_replay"
    with pytest.raises(ApplicationError) as caught:
        asyncio.run(GuideService().draft(REQUEST, use_model=True))
    assert caught.value.detail.code == "planner_not_configured"

    service = GuideService(ScriptedGuide(json.dumps(GOOD, ensure_ascii=False)), identity=SCRIPTED)
    good = asyncio.run(service.draft(REQUEST, use_model=True))
    assert good.source == "model" and good.draft is not None and good.model_calls == 1
    assert good.draft.plan_id == "sweep_levels"

    invented = json.loads(json.dumps(GOOD))
    invented["parameters"]["nominal_fundamental_hz"] = 440.0
    invented["plan_id"] = "nominal_tone"
    invented["parameters"].update(sample_rate_hz=None, level_labels=[], connection=None)
    cases = {
        "illegal_output": "not json",
        "validation_failed:number": json.dumps(invented, ensure_ascii=False),
        "provider_error": GuideError("down"),
    }
    for reason, reply in cases.items():
        result = asyncio.run(GuideService(ScriptedGuide(reply), identity=SCRIPTED).draft(REQUEST, use_model=True))
        assert result.source == "questionnaire" and result.fallback_reason == reason
        assert result.draft is None and result.model_calls == 1

    assert build_guide_service({}).status().model_available is False
    assert build_guide_service({"DEEPSEEK_API_KEY": "k"}).status().model_available is False
    assert build_guide_service({"SIGNAL_DIAG_GUIDE_MODEL": "enabled"}).status().model_available is False
    enabled = build_guide_service({"DEEPSEEK_API_KEY": "k", "SIGNAL_DIAG_GUIDE_MODEL": "enabled"})
    assert enabled.status().model_available is True
    asyncio.run(enabled.aclose())
