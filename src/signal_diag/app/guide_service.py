"""Test guide service (D057, §31): questionnaire by default, model draft on request.

The model path needs DeepSeek credentials and ``SIGNAL_DIAG_GUIDE_MODEL=enabled``
(D057 3A: hidden until the real-model acceptance passes). Asking for it while
unavailable is an error; after a call, any failure returns the questionnaire
with the reason recorded.
"""

from __future__ import annotations

import html
import json
from collections.abc import Callable, Mapping
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
    PlanRecord,
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


class GuideRejection(BaseModel):
    """A model draft that was not used: why, and the model's text (evaluation only)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    check: str
    detail: str
    raw: str


GuideRejectionSink = Callable[[GuideRejection], None]


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
    def __init__(
        self,
        guide: Guide | None = None,
        *,
        identity: GuideIdentity | None = None,
        rejection_sink: GuideRejectionSink | None = None,
    ) -> None:
        if (guide is None) != (identity is None):
            raise ValueError("guide and identity go together")
        self._guide = guide
        self._identity = identity
        self._rejection_sink = rejection_sink

    def with_rejection_sink(self, sink: GuideRejectionSink) -> GuideService:
        """The same guide, reporting each rejected draft to ``sink`` (evaluation only)."""
        return GuideService(self._guide, identity=self._identity, rejection_sink=sink)

    def _reject(self, check: str, detail: str, raw: str) -> None:
        if self._rejection_sink is not None:
            self._rejection_sink(GuideRejection(check=check, detail=detail, raw=raw))

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
            except (ValidationError, ValueError) as error:
                reason = "illegal_output"
                self._reject(reason, _first_error(error), raw)
            else:
                try:
                    validate_plan_draft(draft, request)
                except PlanRejected as rejected:
                    reason = f"validation_failed:{rejected.check}"
                    self._reject(rejected.check, rejected.detail, raw)
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


def _first_error(error: Exception) -> str:
    """A short, location-bearing summary of why the model output did not parse."""
    if isinstance(error, ValidationError):
        first = error.errors()[0]
        location = ".".join(str(part) for part in first["loc"]) or "<root>"
        return f"{location}: {first['msg']}"
    return str(error).splitlines()[0] if str(error) else type(error).__name__


def render_plan_html(record: PlanRecord) -> str:
    """Report section for a run started from a confirmed test plan."""
    zh = record.language == "zh"
    title = "测试方案" if zh else "Test plan"
    lines = "".join(f"<li>{html.escape(step)}</li>" for step in record.steps)
    note = (
        f"按测试方案 {record.plan_key}（{record.plan_id}，{record.version}，来源：{record.source}）执行。"
        if zh
        else f"Run from test plan {record.plan_key} ({record.plan_id}, {record.version}, source: {record.source})."
    )
    return (
        f'<section id="test-plan"><h2>{title}</h2><p>{html.escape(note)}</p><ol>{lines}</ol></section>'
    )


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
    "GuideRejection",
    "GuideRejectionSink",
    "GuideResult",
    "GuideService",
    "GuideStatus",
    "build_guide_service",
    "guide_payload",
    "render_plan_html",
]
