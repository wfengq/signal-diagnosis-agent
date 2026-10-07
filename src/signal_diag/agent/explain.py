"""Explanation writer (v0.3-s1-explain-1.0, D055).

One model call rewrites the deterministic template of a finished run in plain
language. The model sees only the explanation packet (no waveform, spectrum or
file content) and returns JSON that the app layer validates; any failure falls
back to the template there. ``ScriptedExplainer`` is a test double, never a
credential fallback.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from signal_diag.agent.intake import IntakeCallLimits, IntakeChatClient

EXPLAIN_PROMPT_VERSION = "v0.3-s1-explain-1.0"
EXPLAIN_LIMITS = IntakeCallLimits(max_output_tokens=1_600, timeout_s=60.0)

SYSTEM_PROMPT = (
    "You explain the result of an audio distortion test to an engineer. "
    "The verdict is already decided by deterministic rules; you must not change it. "
    "The user message is JSON with: language (zh or en), packet (the run's claims, "
    "rule evaluations, evidence, knowledge and a next_steps menu; every item has a "
    "ref_id and display values), and baseline (a correct but stiff explanation). "
    "Rewrite the baseline so it reads naturally in the requested language. "
    "Return one JSON object with exactly one key, sections: a list of four objects "
    'in this order with kind "conclusion", "evidence", "meaning", "next_steps". '
    "Each of the first three has sentences: a list of at most 4 objects "
    "{text, refs}; next_steps has steps: a list of at most 4 objects "
    "{step_id, text, refs}. Rules: "
    "1. Every sentence cites at least one ref_id from the packet in refs; never "
    "write ref_ids or other identifiers inside text. "
    "2. The conclusion cites every claim and states exactly the verdict of the "
    "claims it cites; never call an inconclusive result fine or fault-free. "
    "3. Any number you write must be one of the display values of an item that "
    "the same sentence cites, copied exactly or rounded; never compute, convert "
    "or invent numbers. "
    "4. Call thresholds demonstration values (演示阈值 / demo threshold). Never "
    "mention standards, certification, compliance, pass/fail grades, IEC or AES. "
    "5. next_steps uses only step_ids from packet.next_steps and cites that "
    "step's trigger_refs. "
    "6. meaning may only restate the cited knowledge items. "
    "7. Each sentence at most 120 characters."
)


class ExplainerError(Exception):
    """Transport or provider failure; the app falls back to the template."""


@runtime_checkable
class Explainer(Protocol):
    identity: str

    async def explain(self, user_json: str) -> str: ...

    async def aclose(self) -> None: ...


class ScriptedExplainer:
    """Test double returning fixed text. Never a credential fallback."""

    def __init__(self, response: str | Exception) -> None:
        self._response = response
        self.identity = EXPLAIN_PROMPT_VERSION
        self.calls: list[str] = []

    async def explain(self, user_json: str) -> str:
        self.calls.append(user_json)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response

    async def aclose(self) -> None:
        return None


class RealLLMExplainer:
    """One SDK call per explanation; failures raise ``ExplainerError``."""

    def __init__(
        self,
        *,
        client: IntakeChatClient,
        model: str,
        limits: IntakeCallLimits = EXPLAIN_LIMITS,
    ) -> None:
        if not model.strip():
            raise ValueError("model must be a non-empty string")
        self._client = client
        self._model = model
        self._limits = limits
        self.identity = EXPLAIN_PROMPT_VERSION
        self.model = model

    async def explain(self, user_json: str) -> str:
        try:
            return await self._client.complete(
                model=self._model,
                system_prompt=SYSTEM_PROMPT,
                user_json=user_json,
                limits=self._limits,
            )
        except Exception as error:
            raise ExplainerError("explanation transport failed") from error

    async def aclose(self) -> None:
        await self._client.aclose()


__all__ = [
    "EXPLAIN_LIMITS",
    "EXPLAIN_PROMPT_VERSION",
    "SYSTEM_PROMPT",
    "Explainer",
    "ExplainerError",
    "RealLLMExplainer",
    "ScriptedExplainer",
]
