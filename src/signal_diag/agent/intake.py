"""Free-text intake planner (v0.3-s1-intake-1.1).

The product builder constructs ``RealLLMIntakePlanner`` only. ``ScriptedIntakePlanner``
is a test double and is not a credential fallback.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

INTAKE_PLANNER_IDENTITY = "v0.3-s1-intake-1.1"

IntakeMode = Literal["single_signal", "paired_reference", "nominal_single_tone"]
StimulusKind = Literal["single_tone", "unknown"]

_NUMBER_RE = re.compile(
    r"(?P<num>\d+(?:\.\d+)?)(?:\s*(?P<unit>khz|hz))?",
    re.IGNORECASE,
)
_DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
_MODEL_PAYLOAD_KEYS = (
    "text",
    "filenames",
    "file_count",
    "test_file",
    "sample_rates_hz",
)

# 1.1: D1 round 2 returned 12/12 drafts that failed validation; 1.0 named the
# keys but not their allowed values or types.
_SYSTEM_PROMPT = (
    "You propose a context draft for an audio distortion diagnosis. "
    "Return one JSON object with exactly these keys and no others: "
    "mode, nominal_fundamental_hz, reference_file, stimulus_kind, "
    "missing_fields, questions, asked_fields. "
    'mode is one of "single_signal", "paired_reference", "nominal_single_tone": '
    '"paired_reference" when the user names another uploaded file as a reference '
    'or earlier recording; otherwise "nominal_single_tone" when the user writes '
    'the frequency of the test tone; otherwise "single_signal". '
    "nominal_fundamental_hz is null or a number written in the user text. "
    "A trailing kHz multiplies that written number by 1000. "
    "Never use a measured fundamental. "
    "reference_file is null or one of the uploaded filenames, and never the "
    "test file. "
    'stimulus_kind is null, "single_tone" or "unknown": "single_tone" when the '
    "user describes a single tone or sine, null when the text does not say. "
    "missing_fields is a list of key names you left null because the text does "
    "not state them. questions is a list of short question strings for the "
    "user, one per missing field. asked_fields is a list drawn from "
    '"mode", "nominal_fundamental_hz", "reference_file", "stimulus_kind": the '
    "fields your questions ask about. "
    "Never emit thresholds, percentages, or standards. Do not invent files. "
    'Example: {"mode": "paired_reference", "nominal_fundamental_hz": 1000.0, '
    '"reference_file": "old_amp.wav", "stimulus_kind": "single_tone", '
    '"missing_fields": [], "questions": [], "asked_fields": []}'
)


class IntakePlannerError(Exception):
    """Raised when a draft is illegal or transport fails closed."""


class IntakeCredentialsError(IntakePlannerError):
    """Raised when the product intake planner has no API credential."""


def _reject_bool(value: object, *, what: str) -> object:
    if isinstance(value, bool):
        raise TypeError(f"{what} must not be a bool")
    return value


class IntakeCallLimits(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_output_tokens: int = Field(gt=0)
    timeout_s: float

    @field_validator("max_output_tokens", mode="before")
    @classmethod
    def _tokens_not_bool(cls, value: object) -> object:
        return _reject_bool(value, what="max_output_tokens")

    @field_validator("timeout_s", mode="before")
    @classmethod
    def _timeout_not_bool(cls, value: object) -> object:
        return _reject_bool(value, what="timeout_s")


class IntakeRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(min_length=1)
    filenames: tuple[str, ...] = Field(min_length=1)
    test_file: str = Field(min_length=1)
    sample_rates_hz: tuple[float, ...] = ()

    @field_validator("sample_rates_hz", mode="before")
    @classmethod
    def _rates_not_bool(cls, value: object) -> object:
        if isinstance(value, list | tuple):
            for item in value:
                _reject_bool(item, what="sample_rates_hz")
        return value


class ContextDraft(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: IntakeMode
    nominal_fundamental_hz: float | None = None
    reference_file: str | None = None
    stimulus_kind: StimulusKind | None = None
    missing_fields: tuple[str, ...] = ()
    questions: tuple[str, ...] = ()
    asked_fields: tuple[
        Literal["mode", "nominal_fundamental_hz", "reference_file", "stimulus_kind"],
        ...
    ] = ()

    @field_validator("nominal_fundamental_hz", mode="before")
    @classmethod
    def _hz_not_bool(cls, value: object) -> object:
        if value is None:
            return value
        return _reject_bool(value, what="nominal_fundamental_hz")


class ConfirmedContext(BaseModel):
    """User-confirmed fields. This object is the only intake shape that may be submitted."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: IntakeMode
    nominal_fundamental_hz: float | None = None
    reference_file: str | None = None
    stimulus_kind: Literal["single_tone"] | None = None

    @field_validator("nominal_fundamental_hz", mode="before")
    @classmethod
    def _hz_not_bool(cls, value: object) -> object:
        if value is None:
            return value
        return _reject_bool(value, what="nominal_fundamental_hz")


def _same_hz(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=0.0, abs_tol=1e-6)


def numbers_admissible_from_text(text: str) -> tuple[float, ...]:
    """Written numbers, plus the ×1000 value when the same token is marked kHz."""
    found: list[float] = []
    for match in _NUMBER_RE.finditer(text):
        raw = float(match.group("num"))
        found.append(raw)
        unit = (match.group("unit") or "").lower()
        if unit == "khz":
            found.append(raw * 1000.0)
    return tuple(found)


def validate_context_draft(draft: ContextDraft, request: IntakeRequest) -> None:
    """Reject a draft whose numbers, files, or mode contradict the request."""
    if request.test_file not in request.filenames:
        raise IntakePlannerError("test_file must be one of the uploaded filenames")
    if len(request.sample_rates_hz) not in (0, len(request.filenames)):
        raise IntakePlannerError("sample_rates_hz must be empty or parallel to filenames")
    nominal = draft.nominal_fundamental_hz
    if nominal is not None:
        admissible = numbers_admissible_from_text(request.text)
        if not any(_same_hz(nominal, item) for item in admissible):
            raise IntakePlannerError(
                "nominal_fundamental_hz must equal a number written in the text"
            )
    if draft.reference_file is not None:
        if draft.reference_file not in request.filenames:
            raise IntakePlannerError("reference_file must be one of the uploaded filenames")
        if draft.reference_file == request.test_file:
            raise IntakePlannerError("reference_file must not equal the test file")
        if draft.mode != "paired_reference":
            raise IntakePlannerError("reference_file requires mode paired_reference")
    if draft.mode == "paired_reference" and len(request.filenames) != 2:
        raise IntakePlannerError("paired_reference requires two uploaded files")


def intake_model_payload(request: IntakeRequest) -> dict[str, object]:
    return {
        "text": request.text,
        "filenames": list(request.filenames),
        "file_count": len(request.filenames),
        "test_file": request.test_file,
        "sample_rates_hz": list(request.sample_rates_hz),
    }


def to_contextual_submit_kwargs(confirmed: ConfirmedContext) -> dict[str, object]:
    if type(confirmed) is not ConfirmedContext:
        raise TypeError("diagnosis submission requires ConfirmedContext")
    return {
        "mode": confirmed.mode,
        "nominal_fundamental_hz": confirmed.nominal_fundamental_hz,
        "reference_file": confirmed.reference_file,
        "stimulus_kind": confirmed.stimulus_kind,
    }


@runtime_checkable
class IntakeChatClient(Protocol):
    async def complete(
        self,
        *,
        model: str,
        system_prompt: str,
        user_json: str,
        limits: IntakeCallLimits,
    ) -> str: ...

    async def aclose(self) -> None: ...


@runtime_checkable
class IntakePlanner(Protocol):
    async def propose(self, request: IntakeRequest) -> ContextDraft: ...


class ScriptedIntakePlanner:
    """Deterministic test double. Product composition must not construct this."""

    identity = "scripted-intake-test-double"

    def __init__(self, draft: ContextDraft) -> None:
        self._draft = draft

    async def propose(self, request: IntakeRequest) -> ContextDraft:
        validate_context_draft(self._draft, request)
        return self._draft

    async def aclose(self) -> None:
        return None


class OpenAICompatibleIntakeClient:
    """Narrow adapter over an OpenAI-compatible chat client (max_retries=0)."""

    def __init__(self, client: Any) -> None:
        retries = getattr(client, "max_retries", None)
        if not isinstance(retries, int) or isinstance(retries, bool) or retries != 0:
            raise IntakePlannerError("intake SDK client max_retries must be int 0")
        self._client = client

    async def complete(
        self,
        *,
        model: str,
        system_prompt: str,
        user_json: str,
        limits: IntakeCallLimits,
    ) -> str:
        create = self._client.chat.completions.create
        response = await create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_json},
            ],
            max_tokens=limits.max_output_tokens,
            timeout=limits.timeout_s,
            # Same settings as the diagnosis planner. With reasoning on,
            # deepseek-v4-flash can spend max_tokens before writing any draft.
            response_format={"type": "json_object"},
            temperature=0.0,
            extra_body={"thinking": {"type": "disabled"}},
        )
        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as error:
            raise IntakePlannerError("intake SDK response missing message content") from error
        if not isinstance(content, str) or not content.strip():
            raise IntakePlannerError("intake SDK response content must be non-empty text")
        return content

    async def aclose(self) -> None:
        close = getattr(self._client, "close", None)
        if close is None:
            return
        result = close()
        if hasattr(result, "__await__"):
            await result


class RealLLMIntakePlanner:
    """One SDK call. Invalid drafts and missing transport fail closed."""

    def __init__(
        self,
        *,
        client: IntakeChatClient,
        model: str,
        limits: IntakeCallLimits,
    ) -> None:
        if not model.strip():
            raise ValueError("model must be a non-empty string")
        self._client = client
        self._model = model
        self._limits = limits
        self.identity = INTAKE_PLANNER_IDENTITY

    async def propose(self, request: IntakeRequest) -> ContextDraft:
        user_json = json.dumps(
            intake_model_payload(request),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        encoded = json.loads(user_json)
        if tuple(encoded) != tuple(sorted(_MODEL_PAYLOAD_KEYS)):
            raise IntakePlannerError("intake payload keys drifted")
        try:
            raw = await self._client.complete(
                model=self._model,
                system_prompt=_SYSTEM_PROMPT,
                user_json=user_json,
                limits=self._limits,
            )
        except IntakePlannerError:
            raise
        except Exception as error:
            raise IntakePlannerError("intake planner transport failed") from error
        try:
            draft = ContextDraft.model_validate_json(raw)
        except (ValidationError, ValueError) as error:
            raise IntakePlannerError("intake planner returned an illegal draft") from error
        validate_context_draft(draft, request)
        return draft

    async def aclose(self) -> None:
        await self._client.aclose()


def build_openai_intake_client(
    *,
    api_key: str,
    base_url: str | None = None,
    http_client: Any | None = None,
) -> OpenAICompatibleIntakeClient:
    """Construct the locked SDK client with retries disabled."""
    if not api_key.strip():
        raise IntakeCredentialsError("DEEPSEEK_API_KEY is required for intake")
    try:
        from openai import AsyncOpenAI
    except ImportError as error:
        raise IntakePlannerError("Intake planner requires the optional llm dependency") from error
    resolved_base = base_url if base_url is not None else _DEFAULT_OPENAI_BASE_URL
    kwargs: dict[str, Any] = {
        "api_key": api_key,
        "base_url": resolved_base,
        "max_retries": 0,
        "organization": "",
        "project": "",
    }
    if http_client is not None:
        kwargs["http_client"] = http_client
    return OpenAICompatibleIntakeClient(AsyncOpenAI(**kwargs))
