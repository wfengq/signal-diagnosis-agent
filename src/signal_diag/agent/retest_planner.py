"""Independent retest planner protocol (v0.3-s1-retest-1.0, unqualified)."""

from __future__ import annotations

import json
import math
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from signal_diag.rules.regression import ComparisonRecord

RETEST_PLANNER_IDENTITY = "v0.3-s1-retest-1.0"

_RetestKind = Literal[
    "complete_conditions",
    "repeat_conditions",
    "lower_both_inputs",
]

AbstainReasonCode = Literal[
    "no_eligible_options",
    "insufficient_basis",
    "ambiguous_options",
    "planner_abstain",
]

_ABSTAIN_REASON_CODES: frozenset[str] = frozenset(
    {
        "no_eligible_options",
        "insufficient_basis",
        "ambiguous_options",
        "planner_abstain",
    }
)

_ABSTAIN_USER_TEXT: dict[str, str] = {
    "no_eligible_options": "no eligible retest options",
    "insufficient_basis": "insufficient supporting findings",
    "ambiguous_options": "eligible options are ambiguous",
    "planner_abstain": "planner abstained",
}

_OPTION_COMPLETE = "opt_complete_conditions"
_OPTION_REPEAT = "opt_repeat_conditions"
_OPTION_LOWER = "opt_lower_both_inputs"

_COMPLETE_TEMPLATE = (
    "Complete the missing declared test conditions before attributing the difference."
)
_REPEAT_TEMPLATE = (
    "Repeat the comparison under the same declared conditions to observe repeatability."
)
_LOWER_TEMPLATE = (
    "Lower both baseline and candidate input levels with an approved level parameter."
)

_DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"


def _reject_bool(value: object, *, what: str) -> object:
    if isinstance(value, bool):
        raise TypeError(f"{what} must not be a bool")
    return value


class RetestCallLimits(BaseModel):
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

    @model_validator(mode="after")
    def _finite_positive_timeout(self) -> RetestCallLimits:
        if not isinstance(self.timeout_s, float) or isinstance(self.timeout_s, bool):
            raise TypeError("timeout_s must be a finite positive float")
        if not math.isfinite(self.timeout_s) or self.timeout_s <= 0.0:
            raise ValueError("timeout_s must be a finite positive float")
        return self


class RetestOption(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    option_id: str = Field(min_length=1)
    kind: _RetestKind
    required_inputs: tuple[str, ...] = ()
    keep_conditions: tuple[str, ...] = ()
    explanation_template: str = Field(min_length=1)
    approved_parameter_bindings: tuple[tuple[str, str], ...] = ()


class CompactFinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str = Field(min_length=1)
    kind: Literal["metric", "coverage", "declaration"]
    code: str = Field(min_length=1)
    detail: str | None = None


class RetestContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    comparison_id: str = Field(min_length=1)
    comparison_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    compact_findings: tuple[CompactFinding, ...]
    eligible_options: tuple[RetestOption, ...]


class RetestSelection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    option_id: str | None = None
    basis_refs: tuple[str, ...] = ()
    abstain_reason_code: AbstainReasonCode | None = None

    @model_validator(mode="after")
    def _selection_shape(self) -> RetestSelection:
        if self.option_id is None:
            if self.abstain_reason_code is None:
                raise ValueError("abstain_reason_code is required when option_id is None")
            if self.abstain_reason_code not in _ABSTAIN_REASON_CODES:
                raise ValueError("abstain_reason_code is not an approved closed code")
            if self.basis_refs:
                raise ValueError("basis_refs must be empty when abstaining")
        else:
            if self.abstain_reason_code is not None:
                raise ValueError("abstain_reason_code must be None when option_id is set")
            if not self.basis_refs:
                raise ValueError("basis_refs are required when option_id is set")
        return self


class RetestPlannerError(Exception):
    """Raised when planner output or transport fails closed."""


@runtime_checkable
class RetestChatClient(Protocol):
    async def complete(
        self,
        *,
        model: str,
        system_prompt: str,
        user_json: str,
        limits: RetestCallLimits,
    ) -> str: ...

    async def aclose(self) -> None: ...


@runtime_checkable
class RetestPlanner(Protocol):
    async def choose(self, context: RetestContext) -> RetestSelection: ...


def build_compact_findings(record: ComparisonRecord) -> tuple[CompactFinding, ...]:
    findings: list[CompactFinding] = []
    conditions = record.conditions
    for name in ("same_input", "parameters_unchanged", "aligned_ranges"):
        value = getattr(conditions, name)
        if value != "yes":
            findings.append(
                CompactFinding(
                    finding_id=f"decl_{name}",
                    kind="declaration",
                    code=f"{name}={value}",
                    detail=None,
                )
            )
    if conditions.repeatability != "declared_deterministic":
        findings.append(
            CompactFinding(
                finding_id="decl_repeatability",
                kind="declaration",
                code=f"repeatability={conditions.repeatability}",
                detail=None,
            )
        )
    for row in record.metric_comparisons:
        findings.append(
            CompactFinding(
                finding_id=f"metric_{row.metric}",
                kind="metric",
                code=row.status,
                detail=",".join(row.reason_codes) if row.reason_codes else None,
            )
        )
    for entry in record.coverage:
        findings.append(
            CompactFinding(
                finding_id=f"coverage_{entry.check_id}",
                kind="coverage",
                code=entry.status,
                detail=entry.detail,
            )
        )
    return tuple(findings)


def eligible_retests(record: ComparisonRecord) -> tuple[RetestOption, ...]:
    """Deterministic catalog filter. Clients cannot inject options or parameters."""
    options: list[RetestOption] = []
    conditions = record.conditions
    # Plan: complete_conditions only when declared info is missing (unknown).
    missing_declarations = any(
        getattr(conditions, name) == "unknown"
        for name in ("same_input", "parameters_unchanged", "aligned_ranges")
    )
    if missing_declarations:
        options.append(
            RetestOption(
                option_id=_OPTION_COMPLETE,
                kind="complete_conditions",
                required_inputs=("declared_conditions",),
                keep_conditions=("baseline_version", "candidate_version"),
                explanation_template=_COMPLETE_TEMPLATE,
            )
        )
    if conditions.repeatability == "unknown":
        options.append(
            RetestOption(
                option_id=_OPTION_REPEAT,
                kind="repeat_conditions",
                required_inputs=("baseline_wav", "candidate_wav"),
                keep_conditions=(
                    "stimulus_key",
                    "parameters_key",
                    "same_input",
                    "parameters_unchanged",
                    "aligned_ranges",
                ),
                explanation_template=_REPEAT_TEMPLATE,
            )
        )
    approved_level_bindings: tuple[tuple[str, str], ...] = ()
    if approved_level_bindings:
        options.append(
            RetestOption(
                option_id=_OPTION_LOWER,
                kind="lower_both_inputs",
                required_inputs=("baseline_wav", "candidate_wav", "level_parameter"),
                keep_conditions=("stimulus_key", "parameters_key"),
                explanation_template=_LOWER_TEMPLATE,
                approved_parameter_bindings=approved_level_bindings,
            )
        )
    return tuple(options)


def build_retest_context(record: ComparisonRecord) -> RetestContext:
    return RetestContext(
        comparison_id=record.comparison_id,
        comparison_digest=record.digest,
        compact_findings=build_compact_findings(record),
        eligible_options=eligible_retests(record),
    )


def parse_retest_selection(
    raw_text: str,
    *,
    context: RetestContext,
) -> RetestSelection:
    """Strictly parse planner JSON; reject overreach and unknown options."""
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as error:
        raise RetestPlannerError("retest planner returned invalid JSON") from error
    if not isinstance(payload, dict):
        raise RetestPlannerError("retest planner JSON must be an object")
    if "options" in payload or "option_ids" in payload:
        raise RetestPlannerError("retest planner must select at most one option")
    forbidden = {"gain", "threshold", "fault", "fault_claim", "shell", "command"}
    extras = set(payload) - {"option_id", "basis_refs", "abstain_reason_code"}
    if extras & forbidden:
        raise RetestPlannerError("retest planner output contains forbidden fields")
    if extras:
        raise RetestPlannerError("retest planner output contains unknown fields")
    try:
        selection = RetestSelection.model_validate(payload)
    except Exception as error:
        raise RetestPlannerError("retest planner selection failed validation") from error
    return validate_selection_against_context(selection, context=context)


def validate_selection_against_context(
    selection: RetestSelection,
    *,
    context: RetestContext,
) -> RetestSelection:
    allowed_ids = {option.option_id for option in context.eligible_options}
    finding_ids = {finding.finding_id for finding in context.compact_findings}
    if selection.option_id is None:
        if selection.abstain_reason_code not in _ABSTAIN_REASON_CODES:
            raise RetestPlannerError("abstain_reason_code is not an approved closed code")
        return selection
    if selection.option_id not in allowed_ids:
        raise RetestPlannerError("selected option_id is not in the eligible catalog")
    if not selection.basis_refs:
        raise RetestPlannerError("basis_refs are required when option_id is set")
    if len(selection.basis_refs) != len(set(selection.basis_refs)):
        raise RetestPlannerError("basis_refs must not contain duplicates")
    for ref in selection.basis_refs:
        if ref not in finding_ids:
            raise RetestPlannerError("basis_refs must resolve to compact findings")
    return selection


def render_recommendation_detail(
    selection: RetestSelection,
    *,
    context: RetestContext,
) -> str:
    if selection.option_id is None:
        code = selection.abstain_reason_code or "planner_abstain"
        reason = _ABSTAIN_USER_TEXT.get(code, _ABSTAIN_USER_TEXT["planner_abstain"])
        return f"No retest recommendation ({reason})."
    option = next(
        (
            item
            for item in context.eligible_options
            if item.option_id == selection.option_id
        ),
        None,
    )
    if option is None:
        raise RetestPlannerError("selected option_id is not in the eligible catalog")
    basis = ", ".join(selection.basis_refs)
    return f"{option.explanation_template} Basis: {basis}."


_SYSTEM_PROMPT = (
    "You are the independent retest planner "
    f"{RETEST_PLANNER_IDENTITY}. "
    "Choose at most one option_id from eligible_options or abstain. "
    "Return JSON only with keys option_id, basis_refs, abstain_reason_code. "
    "abstain_reason_code must be one of: "
    + ", ".join(sorted(_ABSTAIN_REASON_CODES))
    + ". "
    "Do not invent thresholds, gains, faults, or shell commands."
)


class OpenAICompatibleRetestClient:
    """Narrow adapter over an OpenAI-compatible chat client (max_retries=0)."""

    def __init__(self, client: Any) -> None:
        retries = getattr(client, "max_retries", None)
        if not isinstance(retries, int) or isinstance(retries, bool) or retries != 0:
            raise RetestPlannerError("retest SDK client max_retries must be int 0")
        self._client = client

    async def complete(
        self,
        *,
        model: str,
        system_prompt: str,
        user_json: str,
        limits: RetestCallLimits,
    ) -> str:
        create = self._client.chat.completions.create
        # Explicit limits only; do not read environment defaults for token/timeout.
        response = await create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_json},
            ],
            max_tokens=limits.max_output_tokens,
            timeout=limits.timeout_s,
        )
        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as error:
            raise RetestPlannerError("retest SDK response missing message content") from error
        if not isinstance(content, str) or not content.strip():
            raise RetestPlannerError("retest SDK response content must be non-empty text")
        return content

    async def aclose(self) -> None:
        close = getattr(self._client, "close", None)
        if close is None:
            return
        result = close()
        if hasattr(result, "__await__"):
            await result


class RealLLMRetestPlanner:
    """Constrained retest planner: one SDK call, strict catalog admission."""

    def __init__(
        self,
        *,
        client: RetestChatClient,
        model: str,
        limits: RetestCallLimits,
    ) -> None:
        if not model.strip():
            raise ValueError("model must be a non-empty string")
        self._client = client
        self._model = model
        self._limits = limits
        self.identity = RETEST_PLANNER_IDENTITY

    async def choose(self, context: RetestContext) -> RetestSelection:
        if not context.eligible_options:
            return RetestSelection(
                option_id=None,
                basis_refs=(),
                abstain_reason_code="no_eligible_options",
            )
        user_json = json.dumps(
            context.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        try:
            raw = await self._client.complete(
                model=self._model,
                system_prompt=_SYSTEM_PROMPT,
                user_json=user_json,
                limits=self._limits,
            )
        except RetestPlannerError:
            raise
        except Exception as error:
            raise RetestPlannerError("retest planner transport failed") from error
        return parse_retest_selection(raw, context=context)

    async def aclose(self) -> None:
        await self._client.aclose()


def build_openai_retest_client(
    *,
    api_key: str,
    base_url: str | None = None,
    http_client: Any | None = None,
) -> OpenAICompatibleRetestClient:
    """Construct the locked SDK client with retries disabled."""
    try:
        from openai import AsyncOpenAI
    except ImportError as error:
        raise RetestPlannerError(
            "Retest planner requires the optional llm dependency"
        ) from error
    # Pin base_url and blank org/project so ambient OPENAI_* env cannot redirect
    # or attach unintended tenant headers to the locked offline adapter path.
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
    return OpenAICompatibleRetestClient(AsyncOpenAI(**kwargs))
