"""Test guide service (D057, §31): questionnaire by default, model draft on request.

The model path needs DeepSeek credentials and ``SIGNAL_DIAG_GUIDE_MODEL=enabled``
(D057 3A: hidden until the real-model acceptance passes). Asking for it while
unavailable is an error; after a call, any failure returns the questionnaire
with the reason recorded.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from signal_diag.agent.guide import (
    GUIDE_PROMPT_VERSION,
    Guide,
    GuideError,
    RealLLMGuide,
)
from signal_diag.agent.intake import IntakePlannerError, build_openai_intake_client
from signal_diag.app.composition import (
    DEFAULT_DEEPSEEK_BASE_URL,
    DEFAULT_DEEPSEEK_MODEL,
)
from signal_diag.app.errors import ApplicationError
from signal_diag.app.models import AppErrorDetail
from signal_diag.app.test_plan import (
    QUESTIONNAIRE,
    GuideRequest,
    PlanDraft,
    PlanRejected,
    Question,
    validate_plan_draft,
)

ENABLE_FLAG = "SIGNAL_DIAG_GUIDE_MODEL"


class GuideIdentity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: Literal["deepseek", "scripted"]
    model: str
    prompt_version: str = GUIDE_PROMPT_VERSION


class GuideResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: Literal["model", "questionnaire"]
    fallback_reason: str | None = None
    draft: PlanDraft | None = None
    questionnaire: tuple[Question, ...] = QUESTIONNAIRE
    guide: GuideIdentity | None = None
    model_calls: int = 0


class GuideStatus(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    questionnaire_available: bool = True
    model_available: bool
    prompt_version: str = GUIDE_PROMPT_VERSION


def guide_payload(request: GuideRequest) -> str:
    return json.dumps(
        request.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


class GuideService:
    def __init__(self, guide: Guide | None = None, *, identity: GuideIdentity | None = None) -> None:
        if (guide is None) != (identity is None):
            raise ValueError("guide and identity go together")
        self._guide = guide
        self._identity = identity

    def status(self) -> GuideStatus:
        return GuideStatus(model_available=self._guide is not None)

    async def draft(self, request: GuideRequest, *, use_model: bool = False) -> GuideResult:
        if not use_model:
            return GuideResult(source="questionnaire")
        if self._guide is None:
            raise ApplicationError(
                AppErrorDetail(
                    code="planner_not_configured",
                    message="AI test planning is not enabled; the questionnaire is available",
                )
            )
        try:
            raw = await self._guide.draft(guide_payload(request))
        except (GuideError, IntakePlannerError):
            reason = "provider_error"
        else:
            try:
                draft = PlanDraft.model_validate_json(raw)
            except (ValidationError, ValueError):
                reason = "illegal_output"
            else:
                try:
                    validate_plan_draft(draft, request)
                except PlanRejected as rejected:
                    reason = f"validation_failed:{rejected.check}"
                else:
                    return GuideResult(
                        source="model", draft=draft, guide=self._identity, model_calls=1
                    )
        return GuideResult(
            source="questionnaire", fallback_reason=reason, guide=self._identity, model_calls=1
        )

    async def aclose(self) -> None:
        if self._guide is not None:
            await self._guide.aclose()


def build_guide_service(environ: Mapping[str, str]) -> GuideService:
    """Questionnaire only unless credentials exist and the model path is enabled."""
    api_key = environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key or environ.get(ENABLE_FLAG, "").strip().lower() != "enabled":
        return GuideService()
    model = environ.get("DEEPSEEK_MODEL") or DEFAULT_DEEPSEEK_MODEL
    client = build_openai_intake_client(
        api_key=api_key, base_url=environ.get("DEEPSEEK_BASE_URL") or DEFAULT_DEEPSEEK_BASE_URL
    )
    return GuideService(
        RealLLMGuide(client=client, model=model),
        identity=GuideIdentity(provider="deepseek", model=model),
    )


__all__ = [
    "ENABLE_FLAG",
    "GuideIdentity",
    "GuideResult",
    "GuideService",
    "GuideStatus",
    "build_guide_service",
    "guide_payload",
]
