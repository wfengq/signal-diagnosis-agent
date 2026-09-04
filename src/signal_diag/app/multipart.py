"""Bounded in-memory streaming multipart decoder for WAV uploads."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import python_multipart as multipart
from fastapi import Request
from python_multipart.exceptions import FormParserError, MultipartParseError
from python_multipart.multipart import parse_options_header

from signal_diag.app.errors import (
    ApplicationError,
    InvalidRequestError,
    PayloadTooLargeError,
)
from signal_diag.app.models import AppErrorDetail
from signal_diag.signal.models import ChannelMode

_ALLOWED_FIELDS = frozenset({"file", "user_request", "channel"})
_CHANNEL_VALUES = frozenset({"left", "right", "mixdown"})
_MAX_FIELD_BYTES = 8 * 1024
_TOTAL_OVERHEAD_BYTES = 64 * 1024


def _payload_too_large_detail() -> AppErrorDetail:
    return AppErrorDetail(code="payload_too_large", message="WAV upload exceeds 20 MiB")


def _invalid(message: str) -> InvalidRequestError:
    return InvalidRequestError(AppErrorDetail(code="invalid_request", message=message))


@dataclass
class _ParseState:
    is_file: bool = False
    file_bytes: bytearray = field(default_factory=bytearray)
    field_bytes: bytearray = field(default_factory=bytearray)
    filename: str | None = None
    user_request: bytes | None = None
    channel: bytes | None = None
    seen: set[str] = field(default_factory=set)
    current_name: str | None = None
    header_field: bytearray = field(default_factory=bytearray)
    header_value: bytearray = field(default_factory=bytearray)
    headers: dict[bytes, bytes] = field(default_factory=dict)
    ended: bool = False


@dataclass(frozen=True, slots=True)
class ParsedWavUpload:
    data: bytes
    filename: str | None
    user_request: str
    channel: ChannelMode


def _decode_utf8(value: bytes, *, what: str) -> str:
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError as error:
        raise _invalid(f"{what} is not valid UTF-8") from error


async def parse_wav_upload(request: Request, *, max_file_bytes: int) -> ParsedWavUpload:
    content_type = request.headers.get("content-type")
    if not content_type:
        raise _invalid("multipart Content-Type is required")
    content_type_value, options = parse_options_header(content_type)
    if content_type_value != b"multipart/form-data":
        raise _invalid("WAV upload requires multipart/form-data")
    boundary = options.get(b"boundary")
    if not boundary:
        raise _invalid("multipart boundary is required")

    max_total = max_file_bytes + _TOTAL_OVERHEAD_BYTES
    state = _ParseState()

    def on_part_begin() -> None:
        state.is_file = False
        state.current_name = None
        state.field_bytes = bytearray()
        state.header_field = bytearray()
        state.header_value = bytearray()
        state.headers = {}

    def on_header_field(data: bytes, start: int, end: int) -> None:
        state.header_field.extend(data[start:end])

    def on_header_value(data: bytes, start: int, end: int) -> None:
        state.header_value.extend(data[start:end])

    def on_header_end() -> None:
        name = bytes(state.header_field).strip().lower()
        value = bytes(state.header_value).strip()
        if name:
            state.headers[name] = value
        state.header_field = bytearray()
        state.header_value = bytearray()

    def on_headers_finished() -> None:
        disposition = state.headers.get(b"content-disposition")
        if not disposition:
            raise _invalid("multipart part is missing Content-Disposition")
        _disposition_type, params = parse_options_header(disposition)
        raw_name = params.get(b"name")
        if raw_name is None:
            raise _invalid("multipart part is missing Content-Disposition name")
        name = _decode_utf8(raw_name, what="multipart field name")
        if name not in _ALLOWED_FIELDS:
            raise _invalid(f"unknown multipart field: {name}")
        if name in state.seen:
            raise _invalid(f"duplicate multipart field: {name}")
        state.seen.add(name)
        state.current_name = name
        state.is_file = name == "file"
        if state.is_file:
            raw_filename = params.get(b"filename")
            if raw_filename is not None:
                state.filename = raw_filename.decode("latin-1")

    def on_part_data(data: bytes, start: int, end: int) -> None:
        piece = data[start:end]
        if state.is_file and len(state.file_bytes) + len(piece) > max_file_bytes:
            raise PayloadTooLargeError(_payload_too_large_detail())
        if not state.is_file and len(state.field_bytes) + len(piece) > _MAX_FIELD_BYTES:
            raise _invalid("multipart text field exceeds 8 KiB")
        target = state.file_bytes if state.is_file else state.field_bytes
        target.extend(piece)

    def on_part_end() -> None:
        name = state.current_name
        if name is None:
            raise _invalid("multipart part is missing Content-Disposition")
        if name == "user_request":
            state.user_request = bytes(state.field_bytes)
        elif name == "channel":
            state.channel = bytes(state.field_bytes)

    def on_end() -> None:
        state.ended = True

    parser = multipart.MultipartParser(
        boundary,
        {
            "on_part_begin": on_part_begin,
            "on_header_field": on_header_field,
            "on_header_value": on_header_value,
            "on_header_end": on_header_end,
            "on_headers_finished": on_headers_finished,
            "on_part_data": on_part_data,
            "on_part_end": on_part_end,
            "on_end": on_end,
        },
    )
    total = 0
    try:
        async for chunk in request.stream():
            if not chunk:
                continue
            total += len(chunk)
            if total > max_total:
                raise PayloadTooLargeError(_payload_too_large_detail())
            parser.write(chunk)
        parser.finalize()
    except ApplicationError:
        state.file_bytes.clear()
        raise
    except (MultipartParseError, FormParserError) as error:
        state.file_bytes.clear()
        raise _invalid("malformed multipart body") from error

    if not state.ended:
        raise _invalid("malformed multipart termination")
    if state.seen != _ALLOWED_FIELDS:
        raise _invalid("WAV upload requires file, user_request, and channel")
    if state.user_request is None or state.channel is None:
        raise _invalid("WAV upload requires file, user_request, and channel")

    user_request = _decode_utf8(state.user_request, what="user_request")
    channel_text = _decode_utf8(state.channel, what="channel").strip()
    if channel_text not in _CHANNEL_VALUES:
        raise _invalid(f"unsupported channel mode: {channel_text}")
    return ParsedWavUpload(
        data=bytes(state.file_bytes),
        filename=state.filename,
        user_request=user_request,
        channel=channel_text,  # type: ignore[arg-type]
    )


_CONTEXTUAL_ALLOWED_FIELDS = frozenset(
    {
        "test_file",
        "reference_file",
        "mode",
        "nominal_fundamental_hz",
        "stimulus_kind",
        "user_request",
        "channel",
    }
)
_CONTEXTUAL_REQUIRED_FIELDS = frozenset(
    {"test_file", "mode", "user_request", "channel"}
)
_CONTEXTUAL_MODES = frozenset({"nominal_single_tone", "paired_reference"})
_CONTEXTUAL_FILE_FIELDS = frozenset({"test_file", "reference_file"})


@dataclass
class _ContextualParseState:
    is_file: bool = False
    current_file_field: str | None = None
    test_bytes: bytearray = field(default_factory=bytearray)
    reference_bytes: bytearray = field(default_factory=bytearray)
    field_bytes: bytearray = field(default_factory=bytearray)
    test_filename: str | None = None
    reference_filename: str | None = None
    mode: bytes | None = None
    nominal_fundamental_hz: bytes | None = None
    stimulus_kind: bytes | None = None
    user_request: bytes | None = None
    channel: bytes | None = None
    seen: set[str] = field(default_factory=set)
    current_name: str | None = None
    header_field: bytearray = field(default_factory=bytearray)
    header_value: bytearray = field(default_factory=bytearray)
    headers: dict[bytes, bytes] = field(default_factory=dict)
    ended: bool = False


@dataclass(frozen=True, slots=True)
class ParsedContextualWavUpload:
    test_data: bytes
    test_filename: str | None
    reference_data: bytes | None
    reference_filename: str | None
    mode: str
    nominal_fundamental_hz: float | None
    stimulus_kind: str | None
    user_request: str
    channel: ChannelMode


def _parse_nominal_hz(raw: bytes) -> float:
    text = _decode_utf8(raw, what="nominal_fundamental_hz").strip()
    try:
        value = float(text)
    except ValueError as error:
        raise _invalid("nominal_fundamental_hz must be a finite positive number") from error
    if not math.isfinite(value) or value <= 0.0:
        raise _invalid("nominal_fundamental_hz must be a finite positive number")
    return value


async def parse_contextual_wav_upload(
    request: Request,
    *,
    max_file_bytes: int,
) -> ParsedContextualWavUpload:
    content_type = request.headers.get("content-type")
    if not content_type:
        raise _invalid("multipart Content-Type is required")
    content_type_value, options = parse_options_header(content_type)
    if content_type_value != b"multipart/form-data":
        raise _invalid("WAV upload requires multipart/form-data")
    boundary = options.get(b"boundary")
    if not boundary:
        raise _invalid("multipart boundary is required")

    max_total = (2 * max_file_bytes) + _TOTAL_OVERHEAD_BYTES
    state = _ContextualParseState()

    def _file_target() -> bytearray:
        if state.current_file_field == "reference_file":
            return state.reference_bytes
        return state.test_bytes

    def on_part_begin() -> None:
        state.is_file = False
        state.current_file_field = None
        state.current_name = None
        state.field_bytes = bytearray()
        state.header_field = bytearray()
        state.header_value = bytearray()
        state.headers = {}

    def on_header_field(data: bytes, start: int, end: int) -> None:
        state.header_field.extend(data[start:end])

    def on_header_value(data: bytes, start: int, end: int) -> None:
        state.header_value.extend(data[start:end])

    def on_header_end() -> None:
        name = bytes(state.header_field).strip().lower()
        value = bytes(state.header_value).strip()
        if name:
            state.headers[name] = value
        state.header_field = bytearray()
        state.header_value = bytearray()

    def on_headers_finished() -> None:
        disposition = state.headers.get(b"content-disposition")
        if not disposition:
            raise _invalid("multipart part is missing Content-Disposition")
        _disposition_type, params = parse_options_header(disposition)
        raw_name = params.get(b"name")
        if raw_name is None:
            raise _invalid("multipart part is missing Content-Disposition name")
        name = _decode_utf8(raw_name, what="multipart field name")
        if name not in _CONTEXTUAL_ALLOWED_FIELDS:
            raise _invalid(f"unknown multipart field: {name}")
        if name in state.seen:
            raise _invalid(f"duplicate multipart field: {name}")
        state.seen.add(name)
        state.current_name = name
        state.is_file = name in _CONTEXTUAL_FILE_FIELDS
        state.current_file_field = name if state.is_file else None
        if state.is_file:
            raw_filename = params.get(b"filename")
            if raw_filename is not None:
                decoded = raw_filename.decode("latin-1")
                if name == "reference_file":
                    state.reference_filename = decoded
                else:
                    state.test_filename = decoded

    def on_part_data(data: bytes, start: int, end: int) -> None:
        piece = data[start:end]
        if state.is_file:
            target = _file_target()
            if len(target) + len(piece) > max_file_bytes:
                raise PayloadTooLargeError(_payload_too_large_detail())
            target.extend(piece)
            return
        if len(state.field_bytes) + len(piece) > _MAX_FIELD_BYTES:
            raise _invalid("multipart text field exceeds 8 KiB")
        state.field_bytes.extend(piece)

    def on_part_end() -> None:
        name = state.current_name
        if name is None:
            raise _invalid("multipart part is missing Content-Disposition")
        if name in _CONTEXTUAL_FILE_FIELDS:
            return
        payload = bytes(state.field_bytes)
        if name == "mode":
            state.mode = payload
        elif name == "nominal_fundamental_hz":
            state.nominal_fundamental_hz = payload
        elif name == "stimulus_kind":
            state.stimulus_kind = payload
        elif name == "user_request":
            state.user_request = payload
        elif name == "channel":
            state.channel = payload

    def on_end() -> None:
        state.ended = True

    parser = multipart.MultipartParser(
        boundary,
        {
            "on_part_begin": on_part_begin,
            "on_header_field": on_header_field,
            "on_header_value": on_header_value,
            "on_header_end": on_header_end,
            "on_headers_finished": on_headers_finished,
            "on_part_data": on_part_data,
            "on_part_end": on_part_end,
            "on_end": on_end,
        },
    )
    total = 0
    try:
        async for chunk in request.stream():
            if not chunk:
                continue
            total += len(chunk)
            if total > max_total:
                raise PayloadTooLargeError(_payload_too_large_detail())
            parser.write(chunk)
        parser.finalize()
    except ApplicationError:
        state.test_bytes.clear()
        state.reference_bytes.clear()
        raise
    except (MultipartParseError, FormParserError) as error:
        state.test_bytes.clear()
        state.reference_bytes.clear()
        raise _invalid("malformed multipart body") from error

    if not state.ended:
        raise _invalid("malformed multipart termination")
    if not _CONTEXTUAL_REQUIRED_FIELDS <= state.seen:
        raise _invalid(
            "contextual WAV upload requires test_file, mode, user_request, and channel"
        )
    if state.mode is None or state.user_request is None or state.channel is None:
        raise _invalid(
            "contextual WAV upload requires test_file, mode, user_request, and channel"
        )
    if not state.test_bytes and "test_file" not in state.seen:
        raise _invalid(
            "contextual WAV upload requires test_file, mode, user_request, and channel"
        )

    mode_text = _decode_utf8(state.mode, what="mode").strip()
    if mode_text not in _CONTEXTUAL_MODES:
        raise _invalid(f"unsupported contextual mode: {mode_text}")
    user_request = _decode_utf8(state.user_request, what="user_request")
    channel_text = _decode_utf8(state.channel, what="channel").strip()
    if channel_text not in _CHANNEL_VALUES:
        raise _invalid(f"unsupported channel mode: {channel_text}")

    stimulus_kind: str | None = None
    if state.stimulus_kind is not None:
        stimulus_kind = _decode_utf8(state.stimulus_kind, what="stimulus_kind").strip()
        if stimulus_kind != "single_tone":
            raise _invalid("stimulus_kind must be single_tone when provided")

    nominal_fundamental_hz: float | None = None
    if state.nominal_fundamental_hz is not None:
        nominal_fundamental_hz = _parse_nominal_hz(state.nominal_fundamental_hz)

    reference_data: bytes | None = None
    if "reference_file" in state.seen:
        reference_data = bytes(state.reference_bytes)

    return ParsedContextualWavUpload(
        test_data=bytes(state.test_bytes),
        test_filename=state.test_filename,
        reference_data=reference_data,
        reference_filename=state.reference_filename,
        mode=mode_text,
        nominal_fundamental_hz=nominal_fundamental_hz,
        stimulus_kind=stimulus_kind,
        user_request=user_request,
        channel=channel_text,  # type: ignore[arg-type]
    )
