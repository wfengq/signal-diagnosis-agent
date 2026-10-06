"""Deterministic B1 intake parser. The rule table is frozen with the study."""

from __future__ import annotations

import re

from signal_diag.agent.intake import (
    ContextDraft,
    IntakeMode,
    IntakeRequest,
    StimulusKind,
    validate_context_draft,
)

B1_RULE_TABLE_ID = "b1-intake-1.0"

B1_RULE_TABLE: dict[str, object] = {
    "id": B1_RULE_TABLE_ID,
    "reference_markers": (
        "参考",
        "旧",
        "之前",
        "原来",
        "原先",
        "reference",
        "old",
        "previous",
        "prior",
    ),
    "frequency_pattern": r"(\d+(?:\.\d+)?)\s*(k?Hz)",
    "stimulus_markers": ("正弦", "测试音", "单音", "sine", "test tone"),
    "window_s": None,
}

_FREQUENCY = re.compile(str(B1_RULE_TABLE["frequency_pattern"]), re.IGNORECASE)


def _markers(kind: str) -> tuple[str, ...]:
    value = B1_RULE_TABLE[kind]
    if not isinstance(value, tuple):
        raise TypeError(f"{kind} must be a tuple")
    return tuple(str(item) for item in value)


def _has_marker(text: str, kind: str) -> bool:
    lowered = text.lower()
    return any(marker.lower() in lowered for marker in _markers(kind))


def _frequency_hz(text: str) -> float | None:
    match = _FREQUENCY.search(text)
    if match is None:
        return None
    value = float(match.group(1))
    unit = match.group(2).lower()
    if unit == "khz":
        return value * 1000.0
    return value


def _reference_file(request: IntakeRequest) -> str | None:
    if not _has_marker(request.text, "reference_markers"):
        return None
    if len(request.filenames) != 2:
        return None
    for name in request.filenames:
        if name != request.test_file and name in request.text:
            return name
    others = [name for name in request.filenames if name != request.test_file]
    if len(others) == 1:
        return others[0]
    return None


def parse_b1(request: IntakeRequest) -> ContextDraft:
    """Apply the frozen keyword and regex table, then the shared draft validator."""
    nominal = _frequency_hz(request.text)
    stimulus: StimulusKind | None = (
        "single_tone" if _has_marker(request.text, "stimulus_markers") else None
    )
    reference = _reference_file(request)
    missing: list[str] = []
    questions: list[str] = []
    mode: IntakeMode
    if reference is not None:
        mode = "paired_reference"
    elif nominal is not None and len(request.filenames) == 1:
        mode = "nominal_single_tone"
        if stimulus is None:
            missing.append("stimulus_kind")
            questions.append("stimulus_kind")
    else:
        mode = "single_signal"
        nominal = None
        if _frequency_hz(request.text) is not None:
            missing.append("nominal_fundamental_hz")
            questions.append("nominal_fundamental_hz")
    if nominal is None and mode != "single_signal":
        missing.append("nominal_fundamental_hz")
        questions.append("nominal_fundamental_hz")
    if (
        mode == "single_signal"
        and nominal is None
        and "nominal_fundamental_hz" not in missing
        and not _has_marker(request.text, "reference_markers")
    ):
        missing.append("nominal_fundamental_hz")
        questions.append("nominal_fundamental_hz")
    draft = ContextDraft(
        mode=mode,
        nominal_fundamental_hz=nominal,
        reference_file=reference,
        stimulus_kind=stimulus,
        missing_fields=tuple(missing),
        questions=tuple(questions),
        asked_fields=tuple(missing),  # type: ignore[arg-type]
    )
    validate_context_draft(draft, request)
    return draft
