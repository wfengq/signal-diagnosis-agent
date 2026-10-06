"""Free-text intake product flow: confirmed fields -> contextual submission (D047).

The draft is a user claim. Only fields the user confirmed reach diagnosis, and a
mode whose required fields are unconfirmed falls back to ``single_signal`` with
an explicit reason. ``static/intake_flow.js`` mirrors ``assemble_intake_submission``;
both run the shared table in ``tests/app/fixtures/intake_assembly_cases.json``.
"""

from __future__ import annotations

import math
import struct
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, cast

from signal_diag.agent.intake import ConfirmedContext, ContextDraft
from signal_diag.app.errors import InvalidRequestError
from signal_diag.app.models import AppErrorDetail

IntakeModeName = Literal["single_signal", "paired_reference", "nominal_single_tone"]
ContextOrigin = Literal["intake_confirmed"]

# §25: the description is not sent to the diagnosis planner (decision 1A).
INTAKE_DIAGNOSIS_QUESTION = "Why does this signal sound distorted?"
CONTEXT_ORIGIN_INTAKE: ContextOrigin = "intake_confirmed"
MAX_INTAKE_FILES = 2

_MODES: tuple[IntakeModeName, ...] = (
    "single_signal",
    "paired_reference",
    "nominal_single_tone",
)


@dataclass(frozen=True, slots=True)
class IntakeAssembly:
    confirmed: ConfirmedContext
    downgraded_from: IntakeModeName | None
    unconfirmed_fields: tuple[str, ...]


def _invalid(message: str) -> InvalidRequestError:
    return InvalidRequestError(AppErrorDetail(code="invalid_request", message=message))


def _check_hz(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise _invalid("nominal_fundamental_hz must be a finite positive number")
    hz = float(value)
    if not math.isfinite(hz) or hz <= 0.0:
        raise _invalid("nominal_fundamental_hz must be a finite positive number")
    return hz


def assemble_intake_submission(
    *,
    mode: object,
    reference_file: object,
    nominal_fundamental_hz: object,
    stimulus_kind: object,
    filenames: Sequence[str],
    test_file: str,
) -> IntakeAssembly:
    """Build the contextual submission from user-confirmed fields.

    ``None`` means "not confirmed". Fields the confirmed mode does not use are
    dropped. Invalid values raise ``invalid_request``; they never downgrade.
    """
    names = tuple(filenames)
    if not names or len(names) > MAX_INTAKE_FILES:
        raise _invalid(f"intake accepts 1 to {MAX_INTAKE_FILES} WAV files")
    if len(set(names)) != len(names):
        raise _invalid("intake filenames must be distinct")
    if test_file not in names:
        raise _invalid("test_file must be one of the uploaded files")
    if mode is not None and mode not in _MODES:
        raise _invalid(f"unsupported contextual mode: {mode}")
    if reference_file is not None:
        if not isinstance(reference_file, str) or reference_file not in names:
            raise _invalid("reference_file must be one of the uploaded files")
        if reference_file == test_file:
            raise _invalid("reference_file must not be the test file")
    if stimulus_kind not in (None, "single_tone"):
        raise _invalid("stimulus_kind must be single_tone when confirmed")
    hz = _check_hz(nominal_fundamental_hz)
    kind = cast(Literal["single_tone"] | None, stimulus_kind)
    ref = cast(str | None, reference_file)

    if mode is None:
        return IntakeAssembly(
            confirmed=ConfirmedContext(mode="single_signal"),
            downgraded_from=None,
            unconfirmed_fields=("mode",),
        )
    if mode == "paired_reference":
        if ref is None:
            return IntakeAssembly(
                confirmed=ConfirmedContext(mode="single_signal"),
                downgraded_from="paired_reference",
                unconfirmed_fields=("reference_file",),
            )
        both = hz is not None and kind is not None
        return IntakeAssembly(
            confirmed=ConfirmedContext(
                mode="paired_reference",
                reference_file=ref,
                nominal_fundamental_hz=hz if both else None,
                stimulus_kind=kind if both else None,
            ),
            downgraded_from=None,
            unconfirmed_fields=(),
        )
    if mode == "nominal_single_tone":
        missing = tuple(
            name
            for name, value in (("nominal_fundamental_hz", hz), ("stimulus_kind", kind))
            if value is None
        )
        if missing:
            return IntakeAssembly(
                confirmed=ConfirmedContext(mode="single_signal"),
                downgraded_from="nominal_single_tone",
                unconfirmed_fields=missing,
            )
        return IntakeAssembly(
            confirmed=ConfirmedContext(
                mode="nominal_single_tone",
                nominal_fundamental_hz=hz,
                stimulus_kind=kind,
            ),
            downgraded_from=None,
            unconfirmed_fields=(),
        )
    return IntakeAssembly(
        confirmed=ConfirmedContext(mode="single_signal"),
        downgraded_from=None,
        unconfirmed_fields=(),
    )


def draft_confirmed_by_yes(draft: ContextDraft) -> dict[str, object]:
    """Fields ``--yes`` accepts: draft values the model neither left missing nor asked about."""
    doubtful = set(draft.missing_fields) | set(draft.asked_fields)
    values: dict[str, object] = {
        "mode": draft.mode,
        "reference_file": draft.reference_file,
        "nominal_fundamental_hz": draft.nominal_fundamental_hz,
        "stimulus_kind": draft.stimulus_kind if draft.stimulus_kind == "single_tone" else None,
    }
    return {name: (None if name in doubtful else values[name]) for name in values}


def downgrade_message(assembly: IntakeAssembly) -> str | None:
    if assembly.downgraded_from is None and assembly.unconfirmed_fields == ("mode",):
        return "mode is not confirmed; diagnosing as single_signal"
    if assembly.downgraded_from is None:
        return None
    fields = " and ".join(assembly.unconfirmed_fields)
    verb = "is" if len(assembly.unconfirmed_fields) == 1 else "are"
    return (
        f"{assembly.downgraded_from} needs {fields}, which {verb} not confirmed; "
        "diagnosing as single_signal"
    )


def wav_header_sample_rate(data: bytes) -> float | None:
    """Read the sample rate from a RIFF/WAVE ``fmt `` chunk; ``None`` if absent."""
    if len(data) < 12 or data[0:4] != b"RIFF" or data[8:12] != b"WAVE":
        return None
    offset = 12
    while offset + 8 <= len(data):
        chunk_id = data[offset : offset + 4]
        (size,) = struct.unpack_from("<I", data, offset + 4)
        if chunk_id == b"fmt ":
            if size < 8 or offset + 16 > len(data):
                return None
            (rate,) = struct.unpack_from("<I", data, offset + 12)
            return float(rate) if rate > 0 else None
        offset += 8 + size + (size % 2)
    return None


__all__ = [
    "CONTEXT_ORIGIN_INTAKE",
    "INTAKE_DIAGNOSIS_QUESTION",
    "MAX_INTAKE_FILES",
    "ContextDraft",
    "ContextOrigin",
    "IntakeAssembly",
    "assemble_intake_submission",
    "downgrade_message",
    "draft_confirmed_by_yes",
    "wav_header_sample_rate",
]
