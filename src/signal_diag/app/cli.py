"""Direct-service argparse CLI for local diagnosis and serving."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

from signal_diag.agent.intake import IntakeRequest
from signal_diag.app.composition import build_product_service
from signal_diag.app.contextual_models import ContextualDiagnosisReport
from signal_diag.app.contextual_reporting import (
    build_contextual_diagnosis_report,
    render_contextual_report_html,
    render_contextual_report_json,
)
from signal_diag.app.errors import ApplicationError, sanitize_application_error
from signal_diag.app.models import AppErrorDetail, DiagnosisReport
from signal_diag.app.reporting import (
    build_diagnosis_report,
    render_report_html,
    render_report_json,
)
from signal_diag.app.service import DiagnosisApplicationService
from signal_diag.signal import WavLoadLimits

_DEFAULT_QUESTION = "Why does this signal sound distorted?"
_SERVE_WARNING = (
    "Warning: local single-user/no-auth service. "
    "Do not expose this server to an untrusted network."
)
_USAGE_OR_CONFIG_CODES = frozenset(
    {
        "invalid_request",
        "payload_too_large",
        "unsupported_wav",
        "invalid_wav",
        "signal_limit_exceeded",
        "unknown_preset",
        "planner_not_configured",
    }
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="signal-diag")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    subparsers.add_parser("presets")

    intake = subparsers.add_parser("intake")
    intake_commands = intake.add_subparsers(dest="intake_command", required=True)
    intake_draft = intake_commands.add_parser("draft")
    intake_draft.add_argument("--text", required=True)
    intake_draft.add_argument("--file", dest="files", action="append", required=True)
    intake_draft.add_argument("--test-file", required=True)
    intake_draft.add_argument("--sample-rate-hz", dest="sample_rates_hz", action="append", type=float)

    diagnose_options = argparse.ArgumentParser(add_help=False)
    diagnose_options.add_argument("--question", default=_DEFAULT_QUESTION)
    diagnose_options.add_argument(
        "--channel",
        choices=("left", "right", "mixdown"),
        default="mixdown",
    )
    diagnose_options.add_argument(
        "--output",
        choices=("text", "json"),
        default="text",
    )
    diagnose_options.add_argument("--html-output", type=Path, default=None)

    diagnose = subparsers.add_parser("diagnose")
    sources = diagnose.add_subparsers(dest="source_kind", required=True)
    wav = sources.add_parser("wav", parents=[diagnose_options])
    wav.add_argument("path", type=Path)
    synthetic = sources.add_parser("synthetic", parents=[diagnose_options])
    synthetic.add_argument("preset_id")
    contextual = sources.add_parser("contextual", parents=[diagnose_options])
    contextual.add_argument("path", type=Path)
    contextual.add_argument(
        "--mode",
        required=True,
        choices=("single_signal", "nominal_single_tone", "paired_reference"),
    )
    contextual.add_argument("--reference", type=Path, default=None)
    contextual.add_argument("--nominal-fundamental-hz", type=float, default=None)
    contextual.add_argument(
        "--stimulus-kind",
        choices=("single_tone",),
        default=None,
    )
    return parser


def _read_wav_path(path: Path, max_bytes: int) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ApplicationError(
            AppErrorDetail(
                code="payload_too_large",
                message=f"WAV exceeds {max_bytes} bytes",
            )
        )
    return data


def _print_error(code: str, message: str) -> None:
    print(f"error: {code}: {message}", file=sys.stderr)


def _exit_for_application_error(error: ApplicationError) -> int:
    return 2 if error.detail.code in _USAGE_OR_CONFIG_CODES else 1


def _validate_contextual_args(args: argparse.Namespace) -> None:
    if args.mode == "single_signal":
        if args.reference is not None:
            raise ApplicationError(
                AppErrorDetail(
                    code="invalid_request",
                    message="single_signal rejects --reference",
                )
            )
        if args.stimulus_kind is not None or args.nominal_fundamental_hz is not None:
            raise ApplicationError(
                AppErrorDetail(
                    code="invalid_request",
                    message="single_signal rejects nominal stimulus fields",
                )
            )
        return

    if args.mode == "nominal_single_tone":
        if args.reference is not None:
            raise ApplicationError(
                AppErrorDetail(
                    code="invalid_request",
                    message="nominal_single_tone rejects --reference",
                )
            )
        if args.stimulus_kind != "single_tone":
            raise ApplicationError(
                AppErrorDetail(
                    code="invalid_request",
                    message="nominal_single_tone requires --stimulus-kind single_tone",
                )
            )
        if args.nominal_fundamental_hz is None:
            raise ApplicationError(
                AppErrorDetail(
                    code="invalid_request",
                    message="nominal_single_tone requires --nominal-fundamental-hz",
                )
            )
        if not (
            args.nominal_fundamental_hz > 0.0
            and args.nominal_fundamental_hz == args.nominal_fundamental_hz
            and args.nominal_fundamental_hz
            not in (float("inf"), float("-inf"))
        ):
            raise ApplicationError(
                AppErrorDetail(
                    code="invalid_request",
                    message="nominal_fundamental_hz must be a finite positive number",
                )
            )
        return

    if args.reference is None:
        raise ApplicationError(
            AppErrorDetail(
                code="invalid_request",
                message="paired_reference requires --reference",
            )
        )
    if args.stimulus_kind == "single_tone" and args.nominal_fundamental_hz is None:
        raise ApplicationError(
            AppErrorDetail(
                code="invalid_request",
                message=(
                    "paired_reference with --stimulus-kind single_tone requires "
                    "--nominal-fundamental-hz"
                ),
            )
        )
    if args.nominal_fundamental_hz is not None and not (
        args.nominal_fundamental_hz > 0.0
        and args.nominal_fundamental_hz == args.nominal_fundamental_hz
        and args.nominal_fundamental_hz not in (float("inf"), float("-inf"))
    ):
        raise ApplicationError(
            AppErrorDetail(
                code="invalid_request",
                message="nominal_fundamental_hz must be a finite positive number",
            )
        )


def _print_text_report(report: DiagnosisReport) -> None:
    result = report.result
    diagnosis = result.diagnosis
    if diagnosis is None:
        print(f"outcome: {result.status}")
        print("confidence: n/a")
        print(f"termination: {result.termination_reason}")
        for item in result.errors:
            print(f"error: {item}")
        return
    print(f"outcome: {diagnosis.outcome}")
    print(f"confidence: {diagnosis.confidence_label}")
    print(f"termination: {diagnosis.termination_reason}")
    for claim in diagnosis.claims:
        print(f"claim {claim.claim_id}: {claim.statement}")
        print(f"  evidence: {', '.join(claim.evidence_refs)}")
        print(f"  rules: {', '.join(claim.rule_refs)}")
        print(f"  knowledge: {', '.join(claim.knowledge_refs)}")


def _print_contextual_text_report(report: ContextualDiagnosisReport) -> None:
    context = report.stimulus_context
    print(f"mode: {context.mode}")
    print(f"assertion_source: {context.assertion_source}")
    if context.nominal_fundamental_hz is not None:
        print(f"nominal_fundamental_hz: {context.nominal_fundamental_hz}")
    if context.stimulus_kind is not None:
        print(f"stimulus_kind: {context.stimulus_kind}")
    result = report.result
    diagnosis = result.diagnosis
    if diagnosis is None:
        print(f"outcome: {result.status}")
        print("confidence: n/a")
        print(f"termination: {result.termination_reason}")
        for item in result.errors:
            print(f"error: {item}")
        return
    print(f"outcome: {diagnosis.outcome}")
    print(f"confidence: {diagnosis.confidence_label}")
    print(f"termination: {diagnosis.termination_reason}")
    for claim in diagnosis.claims:
        print(f"claim {claim.claim_id}: {claim.statement}")
        print(f"  evidence: {', '.join(claim.evidence_refs)}")
        print(f"  rules: {', '.join(claim.rule_refs)}")
        print(f"  knowledge: {', '.join(claim.knowledge_refs)}")
    for limitation in diagnosis.limitations:
        print(f"limitation: {limitation}")
    guidance = report.context_guidance
    if guidance is not None:
        print(f"context_guidance: {guidance.summary}")
        print(f"  reason_codes: {', '.join(guidance.reason_codes)}")
        print(f"  unlockable_modes: {', '.join(guidance.unlockable_modes)}")
        for fact in guidance.observed_facts:
            unit_suffix = ""
            if fact.unit not in (None, ""):
                unit_suffix = f" {fact.unit}"
            print(
                f"  observed_fact: {fact.evidence_id} {fact.metric}="
                f"{fact.value}{unit_suffix}"
            )


def _emit_outputs(args: argparse.Namespace, report: DiagnosisReport) -> None:
    if args.output == "json":
        sys.stdout.write(render_report_json(report))
    else:
        _print_text_report(report)
    if args.html_output is not None:
        Path(args.html_output).write_bytes(render_report_html(report).encode("utf-8"))


def _emit_contextual_outputs(
    args: argparse.Namespace, report: ContextualDiagnosisReport
) -> None:
    if args.output == "json":
        sys.stdout.write(render_contextual_report_json(report))
    else:
        _print_contextual_text_report(report)
    if args.html_output is not None:
        Path(args.html_output).write_bytes(
            render_contextual_report_html(report).encode("utf-8")
        )


def _serve(args: argparse.Namespace) -> int:
    print(_SERVE_WARNING, file=sys.stderr)
    import uvicorn

    from signal_diag.app.api import create_app

    uvicorn.run(
        create_app(),
        host=args.host,
        port=args.port,
        log_level="info",
    )
    return 0


async def _presets(
    service_factory: Callable[[], DiagnosisApplicationService],
) -> int:
    service = service_factory()
    try:
        for item in service.list_presets():
            print(item.preset_id)
        return 0
    finally:
        await service.aclose()


async def _diagnose(
    args: argparse.Namespace,
    service_factory: Callable[[], DiagnosisApplicationService],
) -> int:
    if args.source_kind == "contextual":
        try:
            _validate_contextual_args(args)
        except ApplicationError as error:
            _print_error(error.detail.code, error.detail.message)
            return _exit_for_application_error(error)

    wav_bytes: bytes | None = None
    reference_bytes: bytes | None = None
    max_bytes = WavLoadLimits().max_upload_bytes
    if args.source_kind in {"wav", "contextual"}:
        try:
            wav_bytes = _read_wav_path(Path(args.path), max_bytes)
            if args.source_kind == "contextual" and args.reference is not None:
                reference_bytes = _read_wav_path(Path(args.reference), max_bytes)
        except ApplicationError as error:
            _print_error(error.detail.code, error.detail.message)
            return _exit_for_application_error(error)
        except OSError as error:
            _print_error("invalid_request", str(error))
            return 2

    service = service_factory()
    try:
        if args.source_kind == "wav":
            if wav_bytes is None:
                raise ApplicationError(
                    AppErrorDetail(
                        code="invalid_request",
                        message="WAV path produced no bytes",
                    )
                )
            submission = await service.submit_wav(
                wav_bytes,
                filename=Path(args.path).name,
                user_request=args.question,
                channel=args.channel,
            )
            snapshot = await service.wait_for_terminal(submission.run_id)
            if snapshot.status == "completed":
                report = build_diagnosis_report(
                    snapshot, generated_at=datetime.now(UTC)
                )
                _emit_outputs(args, report)
                if snapshot.result is not None and snapshot.result.status == "error":
                    return 1
                return 0
            if snapshot.application_error is not None:
                _print_error(
                    snapshot.application_error.code,
                    snapshot.application_error.message,
                )
            else:
                _print_error("internal_error", "diagnosis execution failed")
            return 1

        if args.source_kind == "contextual":
            if wav_bytes is None:
                raise ApplicationError(
                    AppErrorDetail(
                        code="invalid_request",
                        message="WAV path produced no bytes",
                    )
                )
            contextual_submission = await service.submit_contextual_wav(
                wav_bytes,
                test_filename=Path(args.path).name,
                mode=args.mode,
                reference_data=reference_bytes,
                reference_filename=(
                    Path(args.reference).name if args.reference is not None else None
                ),
                nominal_fundamental_hz=args.nominal_fundamental_hz,
                stimulus_kind=args.stimulus_kind,
                user_request=args.question,
                channel=args.channel,
            )
            contextual_snapshot = await service.wait_for_contextual_terminal(
                contextual_submission.run_id
            )
            if contextual_snapshot.status == "completed":
                contextual_report = build_contextual_diagnosis_report(
                    contextual_snapshot, generated_at=datetime.now(UTC)
                )
                _emit_contextual_outputs(args, contextual_report)
                if (
                    contextual_snapshot.result is not None
                    and contextual_snapshot.result.status == "error"
                ):
                    return 1
                return 0
            if contextual_snapshot.application_error is not None:
                _print_error(
                    contextual_snapshot.application_error.code,
                    contextual_snapshot.application_error.message,
                )
            else:
                _print_error("internal_error", "diagnosis execution failed")
            return 1

        submission = await service.submit_synthetic(
            args.preset_id,
            user_request=args.question,
            channel=args.channel,
        )
        snapshot = await service.wait_for_terminal(submission.run_id)
        if snapshot.status == "completed":
            report = build_diagnosis_report(
                snapshot, generated_at=datetime.now(UTC)
            )
            _emit_outputs(args, report)
            if snapshot.result is not None and snapshot.result.status == "error":
                return 1
            return 0
        if snapshot.application_error is not None:
            _print_error(
                snapshot.application_error.code,
                snapshot.application_error.message,
            )
        else:
            _print_error("internal_error", "diagnosis execution failed")
        return 1
    except ApplicationError as error:
        _print_error(error.detail.code, error.detail.message)
        return _exit_for_application_error(error)
    except Exception as error:  # noqa: BLE001
        detail = sanitize_application_error(error)
        _print_error(detail.code, detail.message)
        return 1
    finally:
        await service.aclose()


async def _intake_draft(
    args: argparse.Namespace,
    service_factory: Callable[[], DiagnosisApplicationService],
) -> int:
    service = service_factory()
    try:
        rates = tuple(args.sample_rates_hz or ())
        request = IntakeRequest(
            text=args.text,
            filenames=tuple(args.files),
            test_file=args.test_file,
            sample_rates_hz=rates,
        )
        draft = await service.draft_intake(request)
    except ApplicationError as error:
        _print_error(error.detail.code, error.detail.message)
        return _exit_for_application_error(error)
    else:
        sys.stdout.write(draft.model_dump_json() + "\n")
        return 0
    finally:
        await service.aclose()


def main(
    argv: Sequence[str] | None = None,
    *,
    service_factory: Callable[[], DiagnosisApplicationService] = build_product_service,
) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(None if argv is None else list(argv))
    except SystemExit as exc:
        if exc.code in (0, None):
            return 0
        return 2
    if args.command == "serve":
        return _serve(args)
    if args.command == "presets":
        return asyncio.run(_presets(service_factory))
    if args.command == "diagnose":
        return asyncio.run(_diagnose(args, service_factory))
    if args.command == "intake" and args.intake_command == "draft":
        return asyncio.run(_intake_draft(args, service_factory))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
