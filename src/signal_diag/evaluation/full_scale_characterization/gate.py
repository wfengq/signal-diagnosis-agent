"""Validation-side gate (T-CX378).

Validation-side materials may not be generated, measured or written before a
complete, verified two-part freeze record exists.  A :class:`ValidationAccess`
is issued only by ``freeze.authorize_validation`` and is required by every
validation-side entry point (pair expansion, row expansion/measurement, sanity
checks, validation artifacts in the store).
"""

from __future__ import annotations

from typing import Any

_ISSUER = object()


class ValidationLocked(Exception):
    """Validation-side work attempted without a complete, verified freeze record."""


class ValidationAccess:
    """Proof that a complete freeze record was verified for this round."""

    __slots__ = ("freeze_digest", "round_id")

    def __init__(self, freeze_digest: str, round_id: str, *, _issuer: Any) -> None:
        if _issuer is not _ISSUER:
            raise ValidationLocked("ValidationAccess is issued only by authorize_validation")
        self.freeze_digest = freeze_digest
        self.round_id = round_id

    def __repr__(self) -> str:
        return f"ValidationAccess(round_id={self.round_id!r}, freeze_digest={self.freeze_digest!r})"


def _issue_validation_access(freeze_digest: str, round_id: str) -> ValidationAccess:
    """Private: only ``freeze.authorize_validation`` issues access, after full verification."""
    return ValidationAccess(freeze_digest, round_id, _issuer=_ISSUER)


def require_validation_access(access: object, *, what: str) -> None:
    if not isinstance(access, ValidationAccess):
        raise ValidationLocked(
            f"{what}: validation side is locked until a complete freeze record is verified"
        )
