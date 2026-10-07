"""Result Q&A service (D060 phase C, §33): deterministic answer by default.

The model path needs DeepSeek credentials and ``SIGNAL_DIAG_QA_MODEL=enabled``
(off until the real-model acceptance passes). Asking for it while unavailable
is an error; after a call, any failure returns the deterministic answer with
the reason recorded.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from signal_diag.agent.intake import IntakePlannerError, build_openai_intake_client
from signal_diag.agent.qa import (
    QA_PROMPT_VERSION,
    Answerer,
    AnswererError,
    RealLLMAnswerer,
)
from signal_diag.app.composition import (
    DEFAULT_DEEPSEEK_BASE_URL,
    DEFAULT_DEEPSEEK_MODEL,
)
from signal_diag.app.errors import ApplicationError
from signal_diag.app.explanation import ExplanationPacket, Language
from signal_diag.app.models import AppErrorDetail
from signal_diag.app.result_qa import (
    QA_VERSION,
    QAAnswer,
    QARejected,
    answer_lines,
    template_answer,
    validate_answer,
)

ENABLE_FLAG = "SIGNAL_DIAG_QA_MODEL"


class AnswererIdentity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: Literal["deepseek", "scripted"]
    model: str
    prompt_version: str = QA_PROMPT_VERSION


class QAResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: Literal["model", "template"]
    fallback_reason: str | None = None
    question: str
    language: Language
    answer: QAAnswer
    lines: tuple[str, ...]
    packet_digest: str
    qa_version: str = QA_VERSION
    answerer: AnswererIdentity | None = None
    model_calls: int = 0


class QAStatus(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    model_available: bool
    prompt_version: str = QA_PROMPT_VERSION


class QARejection(BaseModel):
    """A model answer that was not used: why, and the model's text (evaluation only)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    check: str
    detail: str
    raw: str


QARejectionSink = Callable[[QARejection], None]


def qa_payload(packet: ExplanationPacket, question: str, language: Language) -> str:
    return json.dumps(
        {
            "language": language,
            "question": question,
            "packet": packet.model_dump(mode="json"),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


class QAService:
    def __init__(
        self,
        answerer: Answerer | None = None,
        *,
        identity: AnswererIdentity | None = None,
        rejection_sink: QARejectionSink | None = None,
    ) -> None:
        if (answerer is None) != (identity is None):
            raise ValueError("answerer and identity go together")
        self._answerer = answerer
        self._identity = identity
        self._rejection_sink = rejection_sink

    def status(self) -> QAStatus:
        return QAStatus(model_available=self._answerer is not None)

    def with_rejection_sink(self, sink: QARejectionSink) -> QAService:
        return QAService(self._answerer, identity=self._identity, rejection_sink=sink)

    def _reject(self, check: str, detail: str, raw: str) -> None:
        if self._rejection_sink is not None:
            self._rejection_sink(QARejection(check=check, detail=detail, raw=raw))

    def _result(
        self,
        packet: ExplanationPacket,
        question: str,
        language: Language,
        answer: QAAnswer,
        **extra: object,
    ) -> QAResult:
        return QAResult(
            question=question,
            language=language,
            answer=answer,
            lines=answer_lines(answer, language),
            packet_digest=packet.digest(),
            **extra,  # type: ignore[arg-type]
        )

    async def answer(
        self,
        packet: ExplanationPacket,
        question: str,
        *,
        language: Language = "zh",
        use_model: bool = False,
    ) -> QAResult:
        fallback = template_answer(packet, question, language)
        if not use_model:
            return self._result(packet, question, language, fallback, source="template")
        if self._answerer is None:
            raise ApplicationError(
                AppErrorDetail(
                    code="planner_not_configured",
                    message="AI answers are not enabled; the report holds the run's evidence",
                )
            )
        try:
            raw = await self._answerer.answer(qa_payload(packet, question, language))
        except (AnswererError, IntakePlannerError):
            reason = "provider_error"
        else:
            try:
                answer = QAAnswer.model_validate_json(raw)
            except (ValidationError, ValueError) as error:
                reason = "illegal_output"
                self._reject(reason, str(error).splitlines()[0], raw)
            else:
                try:
                    validate_answer(answer, packet)
                except QARejected as rejected:
                    reason = f"validation_failed:{rejected.check}"
                    self._reject(rejected.check, rejected.detail, raw)
                else:
                    return self._result(
                        packet,
                        question,
                        language,
                        answer,
                        source="model",
                        answerer=self._identity,
                        model_calls=1,
                    )
        return self._result(
            packet,
            question,
            language,
            fallback,
            source="template",
            fallback_reason=reason,
            answerer=self._identity,
            model_calls=1,
        )

    async def aclose(self) -> None:
        if self._answerer is not None:
            await self._answerer.aclose()


def build_qa_service(environ: Mapping[str, str]) -> QAService:
    """Deterministic answers only unless credentials exist and the model path is enabled."""
    api_key = environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key or environ.get(ENABLE_FLAG, "").strip().lower() != "enabled":
        return QAService()
    model = environ.get("DEEPSEEK_MODEL") or DEFAULT_DEEPSEEK_MODEL
    client = build_openai_intake_client(
        api_key=api_key,
        base_url=environ.get("DEEPSEEK_BASE_URL") or DEFAULT_DEEPSEEK_BASE_URL,
    )
    return QAService(
        RealLLMAnswerer(client=client, model=model),
        identity=AnswererIdentity(provider="deepseek", model=model),
    )


__all__ = [
    "ENABLE_FLAG",
    "AnswererIdentity",
    "QARejection",
    "QARejectionSink",
    "QAResult",
    "QAService",
    "QAStatus",
    "build_qa_service",
    "qa_payload",
]
