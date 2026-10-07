"""Explanation service (D055, §30): template by default, model on request.

The template is always available. The model path needs DeepSeek credentials
and ``SIGNAL_DIAG_EXPLAIN_MODEL=enabled`` (D055 4A: off until the real-model
acceptance passes). A request for the model path when it is unavailable is an
error, never a silent template; a model failure after the call falls back to
the template with the reason recorded.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from signal_diag.agent.explain import (
    EXPLAIN_PROMPT_VERSION,
    Explainer,
    ExplainerError,
    RealLLMExplainer,
)
from signal_diag.agent.intake import IntakePlannerError, build_openai_intake_client
from signal_diag.app.composition import (
    DEFAULT_DEEPSEEK_BASE_URL,
    DEFAULT_DEEPSEEK_MODEL,
)
from signal_diag.app.errors import ApplicationError
from signal_diag.app.explanation import (
    PACKET_VERSION,
    TEMPLATE_VERSION,
    ExplanationDraft,
    ExplanationPacket,
    ExplanationRejected,
    Language,
    template_explanation,
    validate_explanation,
)
from signal_diag.app.models import AppErrorDetail

ENABLE_FLAG = "SIGNAL_DIAG_EXPLAIN_MODEL"


class ExplainerIdentity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: Literal["deepseek", "scripted"]
    model: str
    prompt_version: str = EXPLAIN_PROMPT_VERSION


class ExplanationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: Literal["model", "template"]
    fallback_reason: str | None = None
    language: Language
    packet_version: str = PACKET_VERSION
    packet_digest: str
    template_version: str = TEMPLATE_VERSION
    explainer: ExplainerIdentity | None = None
    model_calls: int = 0
    draft: ExplanationDraft


class ExplanationStatus(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    template_available: bool = True
    model_available: bool
    prompt_version: str = EXPLAIN_PROMPT_VERSION


def model_payload(packet: ExplanationPacket, language: Language) -> str:
    baseline = template_explanation(packet, language)
    return json.dumps(
        {
            "language": language,
            "packet": packet.model_dump(mode="json"),
            "baseline": baseline.model_dump(mode="json"),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


class ExplanationService:
    def __init__(
        self,
        explainer: Explainer | None = None,
        *,
        identity: ExplainerIdentity | None = None,
    ) -> None:
        if (explainer is None) != (identity is None):
            raise ValueError("explainer and identity go together")
        self._explainer = explainer
        self._identity = identity

    def status(self) -> ExplanationStatus:
        return ExplanationStatus(model_available=self._explainer is not None)

    async def explain(
        self, packet: ExplanationPacket, *, language: Language = "zh", use_model: bool = False
    ) -> ExplanationResult:
        template = template_explanation(packet, language)
        digest = packet.digest()
        if not use_model:
            return ExplanationResult(
                source="template", draft=template, language=language, packet_digest=digest
            )
        if self._explainer is None:
            raise ApplicationError(
                AppErrorDetail(
                    code="planner_not_configured",
                    message="AI explanation is not enabled; the template explanation is available",
                )
            )
        identity = self._identity
        try:
            raw = await self._explainer.explain(model_payload(packet, language))
        except (ExplainerError, IntakePlannerError):
            reason = "provider_error"
        else:
            try:
                draft = ExplanationDraft.model_validate_json(raw)
            except (ValidationError, ValueError):
                reason = "illegal_output"
            else:
                try:
                    validate_explanation(draft, packet)
                except ExplanationRejected as rejected:
                    reason = f"validation_failed:{rejected.check}"
                else:
                    return ExplanationResult(
                        source="model",
                        draft=draft,
                        explainer=identity,
                        model_calls=1,
                        language=language,
                        packet_digest=digest,
                    )
        return ExplanationResult(
            source="template",
            fallback_reason=reason,
            draft=template,
            explainer=identity,
            model_calls=1,
            language=language,
            packet_digest=digest,
        )

    async def aclose(self) -> None:
        if self._explainer is not None:
            await self._explainer.aclose()


def build_explanation_service(environ: Mapping[str, str]) -> ExplanationService:
    """Template only unless credentials exist and the model path is enabled."""
    api_key = environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key or environ.get(ENABLE_FLAG, "").strip().lower() != "enabled":
        return ExplanationService()
    model = environ.get("DEEPSEEK_MODEL") or DEFAULT_DEEPSEEK_MODEL
    client = build_openai_intake_client(
        api_key=api_key,
        base_url=environ.get("DEEPSEEK_BASE_URL") or DEFAULT_DEEPSEEK_BASE_URL,
    )
    return ExplanationService(
        RealLLMExplainer(client=client, model=model),
        identity=ExplainerIdentity(provider="deepseek", model=model),
    )


__all__ = [
    "ENABLE_FLAG",
    "ExplainerIdentity",
    "ExplanationResult",
    "ExplanationService",
    "ExplanationStatus",
    "build_explanation_service",
    "model_payload",
]
