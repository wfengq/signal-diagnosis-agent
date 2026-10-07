"""T-CX513–T-CX515: result Q&A validator, template, adapter and service (D060 C, §33)."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from signal_diag.agent.intake import IntakeCallLimits
from signal_diag.agent.qa import (
    QA_PROMPT_VERSION,
    SYSTEM_PROMPT,
    AnswererError,
    RealLLMAnswerer,
    ScriptedAnswerer,
)
from signal_diag.app.errors import ApplicationError
from signal_diag.app.explanation import ExplanationPacket, ExplanationSentence
from signal_diag.app.qa_service import (
    AnswererIdentity,
    QARejection,
    QAService,
    build_qa_service,
    qa_payload,
)
from signal_diag.app.result_qa import (
    QAAnswer,
    QARejected,
    answer_lines,
    mentions_component,
    template_answer,
    validate_answer,
)
from tests.app.test_explanation import _packet, _sweep_packet

SCRIPTED = AnswererIdentity(provider="scripted", model="scripted")


def _ref(packet: ExplanationPacket, kind: str, *, valued: bool = False) -> str:
    return next(
        item.ref_id
        for item in packet.items
        if item.kind == kind and (item.values or not valued)
    )


def _answer(text: str, *refs: str, **extra: Any) -> QAAnswer:
    return QAAnswer(sentences=(ExplanationSentence(text=text, refs=refs),), **extra)


def _rejected(answer: QAAnswer, packet: ExplanationPacket) -> str:
    with pytest.raises(QARejected) as caught:
        validate_answer(answer, packet)
    return caught.value.check


def test_t_cx513_validator_accepts_grounded_answers() -> None:
    packet = _packet("clipping")
    claim = _ref(packet, "claim")
    evaluation = _ref(packet, "rule_evaluation", valued=True)
    validate_answer(_answer("本次测试判定存在削波。", claim), packet)
    validate_answer(
        _answer("削波比例为 0.2382，高于演示阈值 0.01。", evaluation), packet
    )
    validate_answer(
        QAAnswer(
            declined=True,
            sentences=(
                ExplanationSentence(text="本次测试测量的是削波和谐波。", refs=(claim,)),
            ),
            suggested_step="lower_playback_level",
        ),
        packet,
    )
    validate_answer(QAAnswer(declined=True), packet)


def test_t_cx513_validator_rejects_each_violation() -> None:
    packet = _packet("clipping")
    claim = _ref(packet, "claim")
    evaluation = _ref(packet, "rule_evaluation", valued=True)
    assert _rejected(QAAnswer(), packet) == "structure"
    five = tuple(
        ExplanationSentence(text="存在削波。", refs=(claim,)) for _ in range(5)
    )
    assert _rejected(QAAnswer(sentences=five), packet) == "structure"
    three = five[:3]
    assert _rejected(QAAnswer(declined=True, sentences=three), packet) == "structure"
    assert _rejected(
        _answer("存在削波。", claim, suggested_step="run_sweep_test"), packet
    ) == ("next_step")
    assert _rejected(_answer("存在削波。"), packet) == "citation"
    assert _rejected(_answer("存在削波。", "claim_missing"), packet) == "citation"
    assert _rejected(_answer(f"见 {claim}。", claim), packet) == "ids_in_text"
    assert _rejected(_answer("削波比例为 0.75。", evaluation), packet) == "number"
    assert _rejected(_answer("该结果符合 IEC 标准。", claim), packet) == "wording"
    assert _rejected(_answer("存在谐波失真。", claim), packet) == "fault_mismatch"
    assert _rejected(_answer("削波很可能来自功放。", claim), packet) == "speculation"
    assert (
        _rejected(_answer("The amplifier is clipping.", claim), packet) == "speculation"
    )


def test_t_cx513_component_terms() -> None:
    for text in (
        "是不是喇叭坏了？",
        "Is my speaker broken?",
        "Which amp stage clips?",
        "换根线缆有用吗",
    ):
        assert mentions_component(text), text
    for text in (
        "削波比例是多少？",
        "What does the amplitude mean?",
        "Why is THD high?",
    ):
        assert not mentions_component(text), text


@pytest.mark.parametrize(
    "name", ["clipping", "harmonic", "both", "inconclusive", "no_fault", "single"]
)
@pytest.mark.parametrize("language", ["zh", "en"])
def test_t_cx514_template_answer_is_valid_on_every_case(
    name: str, language: str
) -> None:
    packet = _packet(name)
    for question in ("结论是什么？", "Is the speaker broken?"):
        answer = template_answer(packet, question, language)  # type: ignore[arg-type]
        validate_answer(answer, packet)
        assert answer_lines(answer, language)  # type: ignore[arg-type]


def test_t_cx514_template_declines_hardware_and_points_to_the_menu() -> None:
    packet = _sweep_packet("levels")
    answer = template_answer(packet, "是不是喇叭坏了？", "zh")
    assert answer.declined and answer.sentences == ()
    assert answer.suggested_step == "lower_playback_level"
    lines = answer_lines(answer, "zh")
    assert lines[0].startswith("本次测试的证据回答不了") and lines[-1].startswith(
        "建议："
    )
    plain = template_answer(packet, "结论是什么？", "en")
    assert not plain.declined and 1 <= len(plain.sentences) <= 4
    assert template_answer(packet, "结论是什么？", "en") == plain


class _FakeClient:
    def __init__(self, reply: str | Exception) -> None:
        self.reply = reply
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    async def complete(
        self,
        *,
        model: str,
        system_prompt: str,
        user_json: str,
        limits: IntakeCallLimits,
    ) -> str:
        self.calls.append(
            {"model": model, "system_prompt": system_prompt, "user_json": user_json}
        )
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply

    async def aclose(self) -> None:
        self.closed = True


def test_t_cx515_adapter_sends_packet_and_question_only() -> None:
    packet = _packet("clipping")
    client = _FakeClient('{"declined": true}')
    answerer = RealLLMAnswerer(client=client, model="m")
    payload = qa_payload(packet, "是不是喇叭坏了？", "zh")
    assert asyncio.run(answerer.answer(payload)) == '{"declined": true}'
    call = client.calls[0]
    assert (
        call["system_prompt"] == SYSTEM_PROMPT
        and answerer.identity == QA_PROMPT_VERSION
    )
    sent = json.loads(call["user_json"])
    assert set(sent) == {"language", "question", "packet"}
    assert sent["packet"] == packet.model_dump(mode="json")
    failing = RealLLMAnswerer(client=_FakeClient(RuntimeError("down")), model="m")
    with pytest.raises(AnswererError):
        asyncio.run(failing.answer(payload))
    asyncio.run(answerer.aclose())
    assert client.closed
    with pytest.raises(ValueError):
        RealLLMAnswerer(client=client, model=" ")


def test_t_cx515_template_is_the_default_and_model_needs_enabling() -> None:
    packet = _packet("clipping")
    service = QAService()
    assert service.status().model_available is False
    result = asyncio.run(service.answer(packet, "结论是什么？"))
    assert result.source == "template" and result.model_calls == 0
    assert result.packet_digest == packet.digest()
    with pytest.raises(ApplicationError):
        asyncio.run(service.answer(packet, "结论是什么？", use_model=True))


def test_t_cx515_model_answer_or_recorded_fallback() -> None:
    packet = _packet("clipping")
    claim = _ref(packet, "claim")
    good = _answer("本次测试判定存在削波。", claim).model_dump_json()
    service = QAService(ScriptedAnswerer(good), identity=SCRIPTED)
    assert service.status().model_available is True
    result = asyncio.run(service.answer(packet, "结论是什么？", use_model=True))
    assert (
        result.source == "model"
        and result.model_calls == 1
        and result.answerer == SCRIPTED
    )
    assert result.lines == ("本次测试判定存在削波。",)

    fallback = template_answer(packet, "削波来自功放吗？", "zh")
    speculative = _answer("削波来自功放。", claim).model_dump_json()
    cases: dict[str, str | Exception] = {
        "illegal_output": "not json",
        "validation_failed:speculation": speculative,
        "provider_error": AnswererError("down"),
    }
    for reason, reply in cases.items():
        rejections: list[QARejection] = []
        service = QAService(
            ScriptedAnswerer(reply), identity=SCRIPTED
        ).with_rejection_sink(rejections.append)
        result = asyncio.run(service.answer(packet, "削波来自功放吗？", use_model=True))
        assert result.source == "template" and result.fallback_reason == reason
        assert result.answer == fallback and result.model_calls == 1
        assert len(rejections) == (0 if reason == "provider_error" else 1)


def test_t_cx515_builder_requires_credentials_and_the_enable_flag() -> None:
    assert build_qa_service({}).status().model_available is False
    keyed = {"DEEPSEEK_API_KEY": "test-key"}
    assert build_qa_service(keyed).status().model_available is False
    flagged = {"SIGNAL_DIAG_QA_MODEL": "enabled"}
    assert build_qa_service(flagged).status().model_available is False
    enabled = build_qa_service({**keyed, **flagged})
    assert enabled.status().model_available is True
    asyncio.run(enabled.aclose())


def _rule(packet: ExplanationPacket, label: str) -> str:
    return next(item.ref_id for item in packet.items if item.label == label)


def test_t_cx519_metric_names_negations_and_the_run_verdict_pass() -> None:
    no_fault, single, inconclusive = (
        _packet("no_fault"),
        _packet("single"),
        _packet("inconclusive"),
    )
    clip_rule = _rule(no_fault, "rule_test_clipping_ratio_acceptable")
    validate_answer(
        _answer("削波比观测值为 0，低于演示阈值 0.01。", clip_rule), no_fault
    )
    validate_answer(
        _answer(
            "The clipping ratio measured 0 against a demo threshold of 0.01.", clip_rule
        ),
        no_fault,
    )
    thd_rule = _rule(single, "rule_thd_acceptable")
    validate_answer(
        _answer("总谐波失真为 1.74%，低于 5.00% 的演示阈值。", thd_rule), single
    )
    validate_answer(
        _answer("Total harmonic distortion measured 1.74%.", thd_rule), single
    )
    claim = _ref(inconclusive, "claim")
    validate_answer(
        _answer("单文件模式下没有参考时，谐波失真无法归因。", claim), inconclusive
    )
    validate_answer(_answer("无法判定不等于设备没有问题。", claim), inconclusive)
    rules = [
        _rule(inconclusive, "rule_even_harmonic_growth_acceptable"),
        _rule(inconclusive, "rule_nominal_thd_acceptable"),
    ]
    validate_answer(
        _answer("偶次谐波增长和标称总谐波失真两项规则均为不适用。", *rules),
        inconclusive,
    )
    run = _ref(no_fault, "run")
    validate_answer(_answer("The run reports no supported fault.", run), no_fault)


def test_t_cx519_affirmed_unsupported_faults_are_still_rejected() -> None:
    no_fault, inconclusive, clipping = (
        _packet("no_fault"),
        _packet("inconclusive"),
        _packet("clipping"),
    )
    claim = _ref(no_fault, "claim")
    clip_rule = _rule(no_fault, "rule_test_clipping_ratio_acceptable")
    assert _rejected(_answer("本次存在削波。", claim), no_fault) == "fault_mismatch"
    assert (
        _rejected(_answer("削波比为 0，但仍存在削波。", clip_rule), no_fault)
        == "fault_mismatch"
    )
    assert (
        _rejected(_answer("The device has harmonic distortion.", claim), no_fault)
        == "fault_mismatch"
    )
    assert (
        _rejected(_answer("设备没有问题。", _ref(inconclusive, "claim")), inconclusive)
        == "fault_mismatch"
    )
    assert _rejected(
        _answer("The run reports no supported fault.", _ref(clipping, "run")), clipping
    ) == ("fault_mismatch")
    assert (
        _rejected(_answer("本次运行判定无法判定。", _ref(clipping, "claim")), clipping)
        == "fault_mismatch"
    )
