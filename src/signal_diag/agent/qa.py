"""Result Q&A answerer (v0.3-s1-qa-1.2, D060 phase C, §33.1–§33.2).

One model call answers one question about a finished run from its explanation
packet. The model sees only the packet and the question (no waveform, spectrum
or file content) and returns JSON that the app layer validates; any failure
falls back to the deterministic answer there. ``ScriptedAnswerer`` is a test
double, never a credential fallback.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from signal_diag.agent.intake import IntakeCallLimits, IntakeChatClient

QA_PROMPT_VERSION = "v0.3-s1-qa-1.2"
QA_LIMITS = IntakeCallLimits(max_output_tokens=800, timeout_s=45.0)

SYSTEM_PROMPT = (
    "You answer an engineer's question about one finished audio distortion test. "
    "The verdict is already decided by deterministic rules; you must not change it. "
    "The user message is JSON with: language (zh or en), question, and packet (the "
    "run's claims, rule evaluations, evidence, knowledge and a next_steps menu; every "
    "item has a ref_id and display values). Return one JSON object with exactly these "
    "keys: declined (true or false), sentences (a list of objects {text, refs}), "
    "suggested_step (null or a step_id from packet.next_steps). Rules: "
    "1. Answer only from the packet. If the packet cannot answer the question, set "
    "declined to true, give at most one sentence saying what this run did measure, "
    "and if a next step on the menu would answer it, put its step_id in suggested_step. "
    "2. Otherwise give 1-4 sentences. Every sentence cites at least one ref_id in refs; "
    "never write ref_ids or other identifiers inside text. refs holds only ref_id values "
    "of packet items; never put a step_id in refs (step_ids go only in suggested_step). "
    "3. Any number you write must be one of the display values of an item that the same "
    "sentence cites, copied exactly or rounded; never compute, convert or invent numbers. "
    "4. Never name hardware components (speaker, driver, amplifier, capacitor, cable, "
    "power supply or similar): the test cannot tell which part causes distortion. "
    "Questions about which part is faulty must be declined. "
    "5. Do not claim a fault that the cited items do not support, and never call an "
    "inconclusive result fine. "
    "6. Call thresholds demonstration values (演示阈值 / demo threshold). Never write "
    "标准, 合格, 达标, 认证, standard, compliant, certified, IEC, AES or SLA, not even to deny "
    "them; say instead that the run only compares measurements with demonstration "
    "thresholds. "
    "7. Describe what this run measured and which checks failed; never say the run "
    "'only' did one check. "
    "8. For a sweep, say at which level distortion starts only when at least two levels "
    "were tested; with one level, say that only that level was tested. "
    "9. Answer in the requested language; each sentence at most 120 characters."
)


class AnswererError(Exception):
    """Transport or provider failure; the app falls back to the deterministic answer."""


@runtime_checkable
class Answerer(Protocol):
    identity: str

    async def answer(self, user_json: str) -> str: ...

    async def aclose(self) -> None: ...


class ScriptedAnswerer:
    """Test double returning fixed text. Never a credential fallback."""

    def __init__(self, response: str | Exception) -> None:
        self._response = response
        self.identity = QA_PROMPT_VERSION
        self.calls: list[str] = []

    async def answer(self, user_json: str) -> str:
        self.calls.append(user_json)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response

    async def aclose(self) -> None:
        return None


class RealLLMAnswerer:
    """One SDK call per question; failures raise ``AnswererError``."""

    def __init__(
        self,
        *,
        client: IntakeChatClient,
        model: str,
        limits: IntakeCallLimits = QA_LIMITS,
    ) -> None:
        if not model.strip():
            raise ValueError("model must be a non-empty string")
        self._client = client
        self._model = model
        self._limits = limits
        self.identity = QA_PROMPT_VERSION
        self.model = model

    async def answer(self, user_json: str) -> str:
        try:
            return await self._client.complete(
                model=self._model,
                system_prompt=SYSTEM_PROMPT,
                user_json=user_json,
                limits=self._limits,
            )
        except Exception as error:
            raise AnswererError("answerer transport failed") from error

    async def aclose(self) -> None:
        await self._client.aclose()


__all__ = [
    "QA_LIMITS",
    "QA_PROMPT_VERSION",
    "SYSTEM_PROMPT",
    "Answerer",
    "AnswererError",
    "RealLLMAnswerer",
    "ScriptedAnswerer",
]
