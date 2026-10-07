"""T-CX471–T-CX472: explanation model adapter and service (D055). No network."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from signal_diag.agent.explain import (
    EXPLAIN_PROMPT_VERSION,
    SYSTEM_PROMPT,
    ExplainerError,
    RealLLMExplainer,
    ScriptedExplainer,
)
from signal_diag.agent.intake import IntakeCallLimits
from signal_diag.app.errors import ApplicationError
from signal_diag.app.explanation import ExplanationPacket, template_explanation
from signal_diag.app.explanation_service import (
    ExplainerIdentity,
    ExplanationService,
    build_explanation_service,
    model_payload,
)
from tests.app.test_explanation import _packet, _sweep_packet

SCRIPTED = ExplainerIdentity(provider="scripted", model="scripted")


class _FakeClient:
    def __init__(self, reply: str | Exception) -> None:
        self.reply = reply
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    async def complete(
        self, *, model: str, system_prompt: str, user_json: str, limits: IntakeCallLimits
    ) -> str:
        self.calls.append(
            {"model": model, "system_prompt": system_prompt, "user_json": user_json, "limits": limits}
        )
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply

    async def aclose(self) -> None:
        self.closed = True


def _rewritten(packet: ExplanationPacket) -> str:
    """A model-like rewrite of the template that still passes validation."""
    draft = template_explanation(packet, "zh").model_dump(mode="json")
    first = draft["sections"][0]["sentences"][0]
    first["text"] = "本次测试：" + first["text"]
    return json.dumps(draft, ensure_ascii=False)


def test_t_cx471_adapter_sends_packet_and_baseline_only() -> None:
    packet = _packet("both")
    client = _FakeClient(_rewritten(packet))
    explainer = RealLLMExplainer(client=client, model="deepseek-test")
    assert explainer.identity == EXPLAIN_PROMPT_VERSION == "v0.3-s1-explain-1.0"
    raw = asyncio.run(explainer.explain(model_payload(packet, "zh")))
    assert raw == client.reply
    (call,) = client.calls
    assert call["system_prompt"] == SYSTEM_PROMPT and call["model"] == "deepseek-test"
    payload = json.loads(call["user_json"])
    assert set(payload) == {"language", "packet", "baseline"}
    assert payload["packet"]["run_id"] == packet.run_id
    text = call["user_json"]
    assert "samples" not in text and "spectrum" not in text.lower()
    for word in ("演示", "demo"):
        assert word in SYSTEM_PROMPT
    failing = RealLLMExplainer(client=_FakeClient(TimeoutError("slow")), model="m")
    with pytest.raises(ExplainerError):
        asyncio.run(failing.explain("{}"))
    with pytest.raises(ValueError):
        RealLLMExplainer(client=client, model=" ")


def test_t_cx472_template_is_the_default_and_needs_no_model() -> None:
    packet = _packet("clipping")
    result = asyncio.run(ExplanationService().explain(packet))
    assert result.source == "template" and result.model_calls == 0
    assert result.fallback_reason is None and result.explainer is None
    assert result.packet_digest == packet.digest()
    assert ExplanationService().status().model_available is False
    with pytest.raises(ApplicationError) as caught:
        asyncio.run(ExplanationService().explain(packet, use_model=True))
    assert caught.value.detail.code == "planner_not_configured"


def test_t_cx472_model_result_or_recorded_fallback() -> None:
    packet = _sweep_packet("levels")
    service = ExplanationService(ScriptedExplainer(_rewritten(packet)), identity=SCRIPTED)
    assert service.status().model_available is True
    good = asyncio.run(service.explain(packet, use_model=True))
    assert good.source == "model" and good.model_calls == 1 and good.explainer == SCRIPTED
    assert good.draft.sections[0].sentences[0].text.startswith("本次测试：")

    template = template_explanation(packet, "zh")
    bad_number = json.loads(_rewritten(packet))
    bad_number["sections"][1]["sentences"][0]["text"] = "频段 THD 最高 99.99%，高于演示阈值 5.00%。"
    cases = {
        "illegal_output": "not json",
        "validation_failed:number": json.dumps(bad_number, ensure_ascii=False),
        "provider_error": ExplainerError("down"),
    }
    for reason, reply in cases.items():
        service = ExplanationService(ScriptedExplainer(reply), identity=SCRIPTED)
        result = asyncio.run(service.explain(packet, use_model=True))
        assert result.source == "template" and result.fallback_reason == reason
        assert result.draft == template and result.model_calls == 1


def test_t_cx472_builder_requires_credentials_and_the_enable_flag() -> None:
    assert build_explanation_service({}).status().model_available is False
    keyed = {"DEEPSEEK_API_KEY": "test-key"}
    assert build_explanation_service(keyed).status().model_available is False
    flagged = {"SIGNAL_DIAG_EXPLAIN_MODEL": "enabled"}
    assert build_explanation_service(flagged).status().model_available is False
    pytest.importorskip("openai")
    enabled = build_explanation_service({**keyed, **flagged})
    assert enabled.status().model_available is True
    asyncio.run(enabled.aclose())
