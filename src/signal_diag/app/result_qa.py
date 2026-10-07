"""Result Q&A (D060 phase C, §33): validator and deterministic fallback.

A user asks about one finished run. An answer is 1-4 sentences that cite the
run's explanation packet (§30) and pass the same checks as the explanation:
citations exist, numbers are cited values, no standards or threshold wording,
no fault the cited evidence does not support. On top of that, an answer may
not name hardware the evidence cannot identify (speaker, amplifier, ...): such
questions must be declined, optionally pointing to a next step from the run's
menu. The deterministic fallback restates the verdict or declines.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

from signal_diag.app.explanation import (
    _FAULT_TERMS,
    _NEGATIONS,
    STEP_TEXT,
    ExplanationPacket,
    ExplanationRejected,
    ExplanationSentence,
    Language,
    check_sentence,
    template_explanation,
)

QA_VERSION = "result-qa-1.1"
MAX_ANSWER_SENTENCES = 4
MAX_QUESTION_CHARS = 500
# Hardware the evidence never identifies; naming it would be speculation.
_COMPONENTS = re.compile(
    r"(喇叭|扬声器|功放|放大器|电容|电阻|晶体管|运放|电源|变压器|线材|线缆|插头|"
    r"\b(?:speaker|driver|woofer|tweeter|amplifier|amp|capacitor|resistor|transistor|op-?amp|"
    r"power supply|transformer|cable|connector)s?\b)",
    re.IGNORECASE,
)


# §33.1: a fault word that names a metric or rule ("削波比", "总谐波失真",
# "clipping ratio") or is negated before or after ("谐波失真无法归因",
# "不等于没有问题") does not assert that fault.
_METRIC_AFTER = ("比", "率", "规则", "检查", "ratio", "rule", "check", "measured")
_METRIC_BEFORE = ("总", "total ")
_NEGATIONS_AFTER = ("无法", "不能", "未", "不", "cannot", "is not", "was not", "not ")


def _asserted(text: str, term: str) -> bool:
    lowered, needle = text.lower(), term.lower()
    start = 0
    while (index := lowered.find(needle, start)) >= 0:
        end = index + len(needle)
        before, after = (
            lowered[max(0, index - 8) : index],
            lowered[end : end + 12].lstrip(),
        )
        metric = after.startswith(_METRIC_AFTER) or before.endswith(_METRIC_BEFORE)
        negated = any(word in before for word in _NEGATIONS) or after.startswith(
            _NEGATIONS_AFTER
        )
        if not (metric or negated):
            return True
        start = index + 1
    return False


def _check_faults(text: str, refs: tuple[str, ...], packet: ExplanationPacket) -> None:
    items = [item for ref in refs if (item := packet.item(ref)) is not None]
    supported = {fault for item in items for fault in item.supports}
    if any(item.kind == "run" for item in items):
        # The run item stands for the run's verdict: the faults its claims support.
        supported |= {
            fault
            for claim in packet.claim_ids
            if (item := packet.item(claim))
            for fault in item.supports
        }
    for fault, terms in _FAULT_TERMS.items():
        if any(_asserted(text, term) for term in terms) and fault not in supported:
            raise QARejected("fault_mismatch", f"mentions {fault} without citing it")


class QAAnswer(BaseModel):
    """What a model (or the fallback) returns for one question."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    declined: bool = False
    sentences: tuple[ExplanationSentence, ...] = ()
    suggested_step: str | None = None


class QARejected(ValueError):
    def __init__(self, check: str, detail: str) -> None:
        super().__init__(f"{check}: {detail}")
        self.check = check
        self.detail = detail


def mentions_component(text: str) -> bool:
    return bool(_COMPONENTS.search(text))


def validate_answer(answer: QAAnswer, packet: ExplanationPacket) -> None:
    """Raise ``QARejected`` unless the answer passes every §33 check."""
    count = len(answer.sentences)
    if answer.declined:
        if count > 2:
            raise QARejected("structure", "a declined answer has at most 2 sentences")
    elif not 1 <= count <= MAX_ANSWER_SENTENCES:
        raise QARejected(
            "structure", f"an answer has 1 to {MAX_ANSWER_SENTENCES} sentences"
        )
    menu = {option.step_id for option in packet.next_steps}
    if answer.suggested_step is not None and answer.suggested_step not in menu:
        raise QARejected(
            "next_step", f"{answer.suggested_step} is not on this run's menu"
        )
    for sentence in answer.sentences:
        try:
            check_sentence(
                sentence.text, sentence.refs, packet, "meaning", check_faults=False
            )
        except ExplanationRejected as rejected:
            raise QARejected(rejected.check, rejected.detail) from rejected
        _check_faults(sentence.text, sentence.refs, packet)
        if mentions_component(sentence.text):
            raise QARejected(
                "speculation", "the evidence does not identify hardware components"
            )


def template_answer(
    packet: ExplanationPacket, question: str, language: Language = "zh"
) -> QAAnswer:
    """Deterministic answer: decline hardware questions, otherwise restate the verdict."""
    if mentions_component(question):
        step = packet.next_steps[0].step_id if packet.next_steps else None
        return QAAnswer(declined=True, suggested_step=step)
    conclusion = template_explanation(packet, language).sections[0].sentences
    return QAAnswer(sentences=tuple(conclusion[:MAX_ANSWER_SENTENCES]))


def answer_lines(answer: QAAnswer, language: Language = "zh") -> tuple[str, ...]:
    """Display lines for an answer, including a decline notice and step text."""
    zh = language == "zh"
    lines = [sentence.text for sentence in answer.sentences]
    if answer.declined:
        lines.insert(
            0,
            "本次测试的证据回答不了这个问题。"
            if zh
            else "This run's evidence cannot answer that question.",
        )
    if answer.suggested_step is not None:
        text = STEP_TEXT[language].get(answer.suggested_step, answer.suggested_step)
        lines.append(("建议：" if zh else "Suggested: ") + text)
    return tuple(lines)


__all__ = [
    "MAX_ANSWER_SENTENCES",
    "QA_VERSION",
    "QAAnswer",
    "QARejected",
    "answer_lines",
    "mentions_component",
    "template_answer",
    "validate_answer",
]
