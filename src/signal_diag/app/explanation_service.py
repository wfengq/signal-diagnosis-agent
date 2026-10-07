"""Explanation service (D055, §30): template by default, model on request.

The template is always available. The model path needs DeepSeek credentials
and ``SIGNAL_DIAG_EXPLAIN_MODEL=enabled`` (D055 4A: off until the real-model
acceptance passes). A request for the model path when it is unavailable is an
error, never a silent template; a model failure after the call falls back to
the template with the reason recorded.
"""

from __future__ import annotations

import html
import json
from collections import OrderedDict
from collections.abc import Mapping
from functools import cache
from importlib.resources import files
from pathlib import Path
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
from signal_diag.app.contextual_models import ContextualAppRunSnapshot
from signal_diag.app.errors import ApplicationError
from signal_diag.app.explanation import (
    PACKET_VERSION,
    TEMPLATE_VERSION,
    ExplanationDraft,
    ExplanationPacket,
    ExplanationRejected,
    Language,
    contextual_packet,
    sweep_packet,
    template_explanation,
    validate_explanation,
)
from signal_diag.app.models import AppErrorDetail
from signal_diag.app.sweep import SweepDiagnosis
from signal_diag.knowledge import KnowledgeIndex

ENABLE_FLAG = "SIGNAL_DIAG_EXPLAIN_MODEL"
_REMEMBERED = 64
_SECTION_TITLES = {
    "zh": {"conclusion": "结论", "evidence": "依据", "meaning": "含义", "next_steps": "下一步"},
    "en": {
        "conclusion": "Conclusion",
        "evidence": "Basis",
        "meaning": "What it means",
        "next_steps": "Next steps",
    },
}


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
        self._latest: OrderedDict[str, ExplanationResult] = OrderedDict()

    def latest(self, run_id: str) -> ExplanationResult | None:
        """The most recent explanation produced for a run, if any."""
        return self._latest.get(run_id)

    def _remember(self, run_id: str, result: ExplanationResult) -> ExplanationResult:
        self._latest[run_id] = result
        self._latest.move_to_end(run_id)
        while len(self._latest) > _REMEMBERED:
            self._latest.popitem(last=False)
        return result

    def status(self) -> ExplanationStatus:
        return ExplanationStatus(model_available=self._explainer is not None)

    async def explain(
        self, packet: ExplanationPacket, *, language: Language = "zh", use_model: bool = False
    ) -> ExplanationResult:
        return self._remember(
            packet.run_id, await self._explain(packet, language=language, use_model=use_model)
        )

    async def _explain(
        self, packet: ExplanationPacket, *, language: Language, use_model: bool
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


@cache
def _knowledge() -> KnowledgeIndex:
    return KnowledgeIndex(Path(str(files("signal_diag").joinpath("knowledge", "corpus"))))


def contextual_explanation_packet(snapshot: ContextualAppRunSnapshot) -> ExplanationPacket:
    """Packet for a finished contextual run; report_unavailable otherwise."""
    if snapshot.result is None or snapshot.result.diagnosis is None:
        raise ApplicationError(
            AppErrorDetail(code="report_unavailable", message="run has no diagnosis to explain")
        )
    packet = contextual_packet(
        snapshot.result,
        mode=snapshot.stimulus_context.mode,
        fault_localization=snapshot.fault_localization,
    )
    # Keyed by the application run id, which reports and the API use.
    return packet.model_copy(update={"run_id": snapshot.run_id})


def sweep_explanation_packet(diagnosis: SweepDiagnosis) -> ExplanationPacket:
    return sweep_packet(diagnosis, _knowledge())


def explanation_lines(result: ExplanationResult) -> list[str]:
    """Plain-text rendering for the CLI."""
    titles = _SECTION_TITLES[result.language]
    lines = [_source_line(result)]
    for section in result.draft.sections:
        texts = [s.text for s in section.sentences] + [s.text for s in section.steps]
        if texts:
            lines.append(f"{titles[section.kind]}:")
            lines.extend(f"  - {text}" for text in texts)
    return lines


def _source_line(result: ExplanationResult) -> str:
    zh = result.language == "zh"
    if result.source == "model" and result.explainer is not None:
        return (
            f"由 AI（{result.explainer.model}，{result.explainer.prompt_version}）根据本次证据撰写；结论来自确定性引擎。"
            if zh
            else f"Written by AI ({result.explainer.model}, {result.explainer.prompt_version}) "
            "from this run's evidence; the verdict comes from the deterministic engine."
        )
    note = f"（AI 改写未采用：{result.fallback_reason}）" if zh else f" (AI rewrite not used: {result.fallback_reason})"
    base = "模板解释，由代码根据本次证据生成。" if zh else "Template explanation generated from this run's evidence."
    return base + (note if result.fallback_reason else "")


def render_explanation_html(result: ExplanationResult) -> str:
    """A self-contained HTML section; all text is escaped."""
    titles = _SECTION_TITLES[result.language]
    parts = [
        '<section id="explanation">',
        f"<h2>{'解释' if result.language == 'zh' else 'Explanation'}</h2>",
        f'<p class="muted">{html.escape(_source_line(result))}</p>',
    ]
    for section in result.draft.sections:
        texts = [s.text for s in section.sentences] + [s.text for s in section.steps]
        if not texts:
            continue
        parts.append(f"<h3>{titles[section.kind]}</h3><ul>")
        parts.extend(f"<li>{html.escape(text)}</li>" for text in texts)
        parts.append("</ul>")
    parts.append("</section>")
    return "".join(parts)


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
    "contextual_explanation_packet",
    "explanation_lines",
    "model_payload",
    "render_explanation_html",
    "sweep_explanation_packet",
]
