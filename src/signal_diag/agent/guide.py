"""Test guide drafter (v0.3-s1-guide-1.0, D057).

One model call maps a user's description to a plan from the fixed catalog. The
model sees only the description, file names and sample rates (no audio) and
returns JSON that the app layer validates; any failure falls back to the
questionnaire there. ``ScriptedGuide`` is a test double, never a fallback.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from signal_diag.agent.intake import IntakeCallLimits, IntakeChatClient

GUIDE_PROMPT_VERSION = "v0.3-s1-guide-1.0"
GUIDE_LIMITS = IntakeCallLimits(max_output_tokens=800, timeout_s=45.0)

SYSTEM_PROMPT = (
    "You help an engineer choose how to test an audio device. You do not diagnose "
    "and you never predict whether the device distorts. The user message is JSON "
    "with text (the user's description), filenames (uploaded files) and "
    "sample_rates_hz. Return one JSON object with exactly these keys: plan_id, "
    "parameters, missing_fields, questions, rationale_quotes. "
    'plan_id is one of "sweep_levels" (the user can play a test file through the '
    "device and record its output), \"existing_recording\" (only an existing "
    'recording, no re-test), "paired_reference" (a good and a bad recording of the '
    'same signal, two files), "nominal_tone" (a recording of a single tone of a '
    "known frequency). parameters has keys sample_rate_hz (44100, 48000 or null), "
    "level_labels (0-3 short strings, only for sweep_levels, quiet to loud), "
    'connection (null or one of "line_loopback", "acoustic_mic", '
    '"digital_capture"; only for sweep_levels), test_file and reference_file '
    "(null or an uploaded file name), nominal_fundamental_hz (null or a number the "
    "user wrote), defaults (names of parameters you filled with a default instead "
    "of the user's words). Use 48000 and the labels 低于平时, 平时音量, 出问题的音量 "
    "(or below normal, normal, problem level) only as marked defaults. Never invent "
    "a number: every number must be written by the user or be a marked default. "
    "missing_fields lists parameter names you need and could not fill; questions "
    "has one short question per missing field, at most 4. rationale_quotes lists "
    "1-3 exact substrings of the user's text that justify the plan. If the user says "
    "the device cannot be re-tested or only one recording exists, do not choose "
    "sweep_levels. Never mention standards, thresholds, percentages or pass/fail."
)


class GuideError(Exception):
    """Transport or provider failure; the app falls back to the questionnaire."""


@runtime_checkable
class Guide(Protocol):
    identity: str

    async def draft(self, user_json: str) -> str: ...

    async def aclose(self) -> None: ...


class ScriptedGuide:
    """Test double returning fixed text. Never a credential fallback."""

    def __init__(self, response: str | Exception) -> None:
        self._response = response
        self.identity = GUIDE_PROMPT_VERSION
        self.calls: list[str] = []

    async def draft(self, user_json: str) -> str:
        self.calls.append(user_json)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response

    async def aclose(self) -> None:
        return None


class RealLLMGuide:
    """One SDK call per draft; failures raise ``GuideError``."""

    def __init__(
        self, *, client: IntakeChatClient, model: str, limits: IntakeCallLimits = GUIDE_LIMITS
    ) -> None:
        if not model.strip():
            raise ValueError("model must be a non-empty string")
        self._client = client
        self._model = model
        self._limits = limits
        self.identity = GUIDE_PROMPT_VERSION
        self.model = model

    async def draft(self, user_json: str) -> str:
        try:
            return await self._client.complete(
                model=self._model,
                system_prompt=SYSTEM_PROMPT,
                user_json=user_json,
                limits=self._limits,
            )
        except Exception as error:
            raise GuideError("guide transport failed") from error

    async def aclose(self) -> None:
        await self._client.aclose()


__all__ = [
    "GUIDE_LIMITS",
    "GUIDE_PROMPT_VERSION",
    "SYSTEM_PROMPT",
    "Guide",
    "GuideError",
    "RealLLMGuide",
    "ScriptedGuide",
]
