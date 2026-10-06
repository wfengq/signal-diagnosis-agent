"""Simulated user: confirm or correct only fields the draft already proposed."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from signal_diag.agent.intake import ConfirmedContext, ContextDraft

_FIELDS = (
    "mode",
    "nominal_fundamental_hz",
    "reference_file",
    "stimulus_kind",
)


class FieldConfirmation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    confirmed: ConfirmedContext
    correction_count: int


def _truth_value(truth: ContextDraft, field: str) -> object:
    return getattr(truth, field)


def _proposed(draft: ContextDraft, field: str) -> bool:
    if getattr(draft, field) is not None:
        return True
    return any(field in question for question in draft.questions)


def confirm_proposed_fields(draft: ContextDraft, truth: ContextDraft) -> FieldConfirmation:
    """Fill asked or already-set fields from truth. Leave everything else empty."""
    values: dict[str, object] = {
        "mode": None,
        "nominal_fundamental_hz": None,
        "reference_file": None,
        "stimulus_kind": None,
    }
    corrections = 0
    for field in _FIELDS:
        if not _proposed(draft, field):
            continue
        current = getattr(draft, field)
        target = _truth_value(truth, field)
        if target == "unknown":
            target = None
        if current is not None and current != target:
            corrections += 1
        values[field] = target
    if values["mode"] is None:
        values["mode"] = "single_signal"
    if values["stimulus_kind"] not in (None, "single_tone"):
        values["stimulus_kind"] = None
    confirmed = ConfirmedContext(
        mode=values["mode"],  # type: ignore[arg-type]
        nominal_fundamental_hz=values["nominal_fundamental_hz"],  # type: ignore[arg-type]
        reference_file=values["reference_file"],  # type: ignore[arg-type]
        stimulus_kind=values["stimulus_kind"],  # type: ignore[arg-type]
    )
    return FieldConfirmation(confirmed=confirmed, correction_count=corrections)
