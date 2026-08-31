"""Typed application errors with sanitized messages."""

from __future__ import annotations

import re
from typing import ClassVar

from signal_diag.app.models import AppErrorCode, AppErrorDetail

_SECRET_PATTERN = re.compile(
    r"(?i)(?:api[_-]?key\s*[=:]\s*)\S+"
    r"|(?:authorization\s*[=:]\s*)\S+"
    r"|(?:bearer\s+)\S+"
    r"|\bsk-[A-Za-z0-9]+\b"
)
_MAX_ERROR_MESSAGE_CHARS = 1000


def _sanitize(message: str) -> str:
    redacted = _SECRET_PATTERN.sub("[redacted]", message)
    if len(redacted) > _MAX_ERROR_MESSAGE_CHARS:
        return redacted[:_MAX_ERROR_MESSAGE_CHARS] + "…"
    return redacted


class ApplicationError(Exception):
    _expected_code: ClassVar[AppErrorCode | None] = None

    def __init__(self, detail: AppErrorDetail) -> None:
        expected = type(self)._expected_code
        if expected is not None and detail.code != expected:
            raise ValueError(
                f"{type(self).__name__} requires detail.code {expected!r}, "
                f"got {detail.code!r}"
            )
        sanitized = detail.model_copy(update={"message": _sanitize(detail.message)})
        super().__init__(sanitized.message)
        self.detail = sanitized


class InvalidRequestError(ApplicationError):
    _expected_code = "invalid_request"


class PayloadTooLargeError(ApplicationError):
    _expected_code = "payload_too_large"


class UnknownPresetError(ApplicationError):
    _expected_code = "unknown_preset"


class RunNotFoundError(ApplicationError):
    _expected_code = "run_not_found"


class RunNotTerminalError(ApplicationError):
    _expected_code = "run_not_terminal"


class ReportUnavailableError(ApplicationError):
    _expected_code = "report_unavailable"


class AppCapacityError(ApplicationError):
    _expected_code = "capacity_exceeded"


class PlannerNotConfiguredError(ApplicationError):
    _expected_code = "planner_not_configured"


class TraceIntegrityError(ApplicationError):
    _expected_code = "trace_integrity_error"


def sanitize_application_error(error: Exception) -> AppErrorDetail:
    if isinstance(error, ApplicationError):
        return error.detail
    return AppErrorDetail(code="internal_error", message="diagnosis execution failed")
