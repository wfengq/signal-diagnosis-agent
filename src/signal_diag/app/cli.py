"""Direct-service argparse CLI for local diagnosis and serving."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from signal_diag.app.contextual_models import ContextualDiagnosisReport
from signal_diag.app.contextual_reporting import (
    build_contextual_diagnosis_report,
    render_contextual_report_html,
    render_contextual_report_json,
)
from signal_diag.app.engine_service import build_engine_service
from signal_diag.app.errors import ApplicationError, sanitize_application_error
from signal_diag.app.explanation import ExplanationPacket
from signal_diag.app.explanation_service import (
    ExplanationResult,
    build_explanation_service,
    contextual_explanation_packet,
    explanation_lines,
    render_explanation_html,
    sweep_explanation_packet,
)
from signal_diag.app.guide_service import GuideResult, build_guide_service
from signal_diag.app.intake_flow import (
    CONTEXT_ORIGIN_INTAKE,
    INTAKE_DIAGNOSIS_QUESTION,
    MAX_INTAKE_FILES,
    ContextDraft,
    assemble_intake_submission,
    downgrade_message,
    draft_confirmed_by_yes,
    wav_header_sample_rate,
)
from signal_diag.app.models import AppErrorDetail, DiagnosisReport
from signal_diag.app.reporting import (
    build_diagnosis_report,
    render_report_html,
    render_report_json,
)
from signal_diag.app.service import DiagnosisApplicationService
from signal_diag.app.sweep import SweepDiagnosis, diagnose_sweep, stimulus_wav
from signal_diag.app.sweep_reporting import (
    THRESHOLD_NOTICE,
    build_sweep_report,
    render_sweep_html,
    render_sweep_json,
)
from signal_diag.app.test_plan import (
    ConfirmRequest,
    GuideRequest,
    PlanRejected,
    confirm_plan,
    questionnaire_draft,
)
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


def _add_explain_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--explain",
        choices=("template", "model"),
        default=None,
        help="add a plain-language explanation (§30): template, or model if enabled",
    )
    parser.add_argument("--explain-language", choices=("zh", "en"), default="zh")


async def _explanation(
    args: argparse.Namespace, packet: ExplanationPacket
) -> ExplanationResult | None:
    mode = getattr(args, "explain", None)
    if mode is None:
        return None
    service = build_explanation_service(os.environ)
    try:
        return await service.explain(
            packet, language=args.explain_language, use_model=mode == "model"
        )
    finally:
        await service.aclose()


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
    intake_diagnose = intake_commands.add_parser("diagnose")
    intake_diagnose.add_argument("--text", required=True)
    intake_diagnose.add_argument("--test-file", type=Path, required=True)
    intake_diagnose.add_argument("--file", dest="files", type=Path, action="append", default=[])
    intake_diagnose.add_argument("--yes", action="store_true")
    intake_diagnose.add_argument(
        "--mode",
        choices=("single_signal", "nominal_single_tone", "paired_reference"),
        default=None,
    )
    intake_diagnose.add_argument("--reference", default=None)
    intake_diagnose.add_argument("--nominal-fundamental-hz", type=float, default=None)
    intake_diagnose.add_argument("--stimulus-kind", choices=("single_tone",), default=None)
    intake_diagnose.add_argument(
        "--channel",
        choices=("left", "right", "mixdown"),
        default="mixdown",
    )
    intake_diagnose.add_argument("--output", choices=("text", "json"), default="text")
    intake_diagnose.add_argument("--html-output", type=Path, default=None)

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
    contextual.add_argument(
        "--diagnosis-path",
        choices=("engine", "planner"),
        default=None,
        help="engine (default, deterministic) or planner (RealLLMPlanner, needs credentials)",
    )
    contextual.add_argument("--nominal-fundamental-hz", type=float, default=None)
    _add_explain_options(contextual)
    contextual.add_argument(
        "--stimulus-kind",
        choices=("single_tone",),
        default=None,
    )

    sweep = subparsers.add_parser("sweep", help="sweep stimulus test (D054)")
    sweep_commands = sweep.add_subparsers(dest="sweep_command", required=True)
    sweep_stimulus = sweep_commands.add_parser("stimulus")
    sweep_stimulus.add_argument(
        "--rate", type=int, choices=(44_100, 48_000), default=48_000
    )
    sweep_stimulus.add_argument("--out", type=Path, required=True)
    sweep_diagnose = sweep_commands.add_parser("diagnose")
    sweep_diagnose.add_argument(
        "recordings", type=Path, nargs="+", help="lowest level first"
    )
    sweep_diagnose.add_argument(
        "--level",
        action="append",
        default=None,
        help="label per recording, in order (default L1, L2, L3)",
    )
    sweep_diagnose.add_argument("--output", choices=("text", "json"), default="text")
    sweep_diagnose.add_argument("--html-output", type=Path, default=None)
    _add_explain_options(sweep_diagnose)

    guide = subparsers.add_parser("guide", help="test guide (D057): choose a test plan")
    guide_commands = guide.add_subparsers(dest="guide_command", required=True)
    guide_draft = guide_commands.add_parser("draft")
    guide_draft.add_argument("text")
    guide_draft.add_argument("--file", dest="files", action="append", default=[])
    guide_draft.add_argument("--model", action="store_true", help="ask for an AI draft")
    guide_questionnaire = guide_commands.add_parser("questionnaire")
    guide_questionnaire.add_argument("--answer", action="append", default=[], help="question=answer")
    guide_questionnaire.add_argument("--language", choices=("zh", "en"), default="zh")
    guide_confirm = guide_commands.add_parser("confirm")
    guide_confirm.add_argument("--plan", required=True)
    guide_confirm.add_argument("--source", choices=("model", "questionnaire"), default="questionnaire")
    guide_confirm.add_argument("--language", choices=("zh", "en"), default="zh")
    guide_confirm.add_argument("--rate", type=int, default=None)
    guide_confirm.add_argument("--level", action="append", default=[])
    guide_confirm.add_argument("--connection", default=None)
    guide_confirm.add_argument("--test-file", default=None)
    guide_confirm.add_argument("--reference-file", default=None)
    guide_confirm.add_argument("--nominal-hz", type=float, default=None)

    session = subparsers.add_parser("session", help="multi-round test session (D060)")
    session_commands = session.add_subparsers(dest="session_command", required=True)
    session_simulate = session_commands.add_parser(
        "simulate", help="run a sandbox scenario with the rule policy (no model)"
    )
    session_simulate.add_argument("case_id")
    session_simulate.add_argument("--cases", choices=("dev", "heldout"), default="dev")
    session_simulate.add_argument("--output", choices=("text", "json"), default="text")
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
    if report.context_origin is not None:
        print(f"context_source: {report.context_origin}")
    identity = report.diagnosis_identity
    if identity is not None and identity.kind == "deterministic_engine":
        print(f"diagnosis: deterministic engine {identity.engine_version}")
    elif report.planner_identity is not None:
        print(f"diagnosis: planner {report.planner_identity.prompt_version}")
    localization = report.fault_localization
    if localization is not None:
        print(f"fault_localization: {localization.scan_version}")
        if localization.harmonic_basis is not None:
            print(f"  harmonic_basis: {localization.harmonic_basis}")
        if localization.windows_not_comparable is not None:
            print(f"  windows_not_comparable: {localization.windows_not_comparable}")
        if localization.harmonic_windows_withheld is not None:
            print(f"  harmonic_windows_withheld: {localization.harmonic_windows_withheld}")
        if not localization.intervals:
            print(
                "  no fault location to list"
                if localization.harmonic_windows_withheld
                else "  no segment rule failed"
            )
        for interval in localization.intervals:
            status = "matches diagnosis" if interval.agrees_with_diagnosis else "review needed"
            print(
                f"  {interval.fault} {interval.channel} "
                f"{interval.start_s:.3f}-{interval.end_s:.3f} s ({status})"
            )
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
    args: argparse.Namespace,
    report: ContextualDiagnosisReport,
    explanation: ExplanationResult | None = None,
) -> None:
    payload = explanation.model_dump(mode="json") if explanation is not None else None
    if args.output == "json":
        sys.stdout.write(render_contextual_report_json(report, explanation=payload))
    else:
        _print_contextual_text_report(report)
        if explanation is not None:
            print("\n".join(explanation_lines(explanation)))
    if args.html_output is not None:
        html_part = render_explanation_html(explanation) if explanation is not None else None
        Path(args.html_output).write_bytes(
            render_contextual_report_html(report, explanation_html=html_part).encode("utf-8")
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


async def _finish_contextual(
    args: argparse.Namespace,
    service: DiagnosisApplicationService,
    run_id: str,
) -> int:
    contextual_snapshot = await service.wait_for_contextual_terminal(run_id)
    if contextual_snapshot.status == "completed":
        contextual_report = build_contextual_diagnosis_report(
            contextual_snapshot, generated_at=datetime.now(UTC)
        )
        explanation = None
        if getattr(args, "explain", None) is not None:
            explanation = await _explanation(
                args, contextual_explanation_packet(contextual_snapshot)
            )
        _emit_contextual_outputs(args, contextual_report, explanation)
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
                **(
                    {"diagnosis_path": args.diagnosis_path}
                    if args.diagnosis_path is not None
                    else {}
                ),
            )
            return await _finish_contextual(args, service, contextual_submission.run_id)

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
        draft = await service.draft_intake_payload(
            {
                "text": args.text,
                "filenames": list(args.files),
                "test_file": args.test_file,
                "sample_rates_hz": list(args.sample_rates_hz or ()),
            }
        )
    except ApplicationError as error:
        _print_error(error.detail.code, error.detail.message)
        return _exit_for_application_error(error)
    else:
        sys.stdout.write(draft.model_dump_json() + "\n")
        return 0
    finally:
        await service.aclose()


_INTAKE_FIELD_FLAGS = ("mode", "reference", "nominal_fundamental_hz", "stimulus_kind")


def _print_draft(draft: ContextDraft) -> None:
    print(f"draft mode: {draft.mode}", file=sys.stderr)
    print(f"draft reference_file: {draft.reference_file}", file=sys.stderr)
    print(
        f"draft nominal_fundamental_hz: {draft.nominal_fundamental_hz}", file=sys.stderr
    )
    print(f"draft stimulus_kind: {draft.stimulus_kind}", file=sys.stderr)
    if draft.missing_fields:
        print(f"draft missing: {', '.join(draft.missing_fields)}", file=sys.stderr)
    aligned = len(draft.asked_fields) == len(draft.questions)
    for index, question in enumerate(draft.questions):
        label = f"question ({draft.asked_fields[index]})" if aligned else "question"
        print(f"{label}: {question}", file=sys.stderr)


def _ask_field(
    name: str,
    current: object,
    parse: Callable[[str], object],
) -> object:
    while True:
        if current is None:
            sys.stderr.write(f"{name} [not set] edit/skip (e/s): ")
        else:
            sys.stderr.write(f"{name} [{current}] keep/edit/skip (k/e/s): ")
        sys.stderr.flush()
        answer = input().strip().lower()
        if answer in ("k", "keep") and current is not None:
            return current
        if answer in ("s", "skip"):
            return None
        if answer in ("e", "edit"):
            sys.stderr.write(f"{name} value: ")
            sys.stderr.flush()
            raw = input().strip()
            try:
                return parse(raw)
            except ValueError as error:
                print(f"invalid {name}: {error}", file=sys.stderr)


def _parse_mode(raw: str) -> str:
    if raw not in ("single_signal", "nominal_single_tone", "paired_reference"):
        raise ValueError("expected single_signal, nominal_single_tone or paired_reference")
    return raw


def _parse_hz(raw: str) -> float:
    value = float(raw)
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError("expected a finite positive number")
    return value


def _parse_stimulus_kind(raw: str) -> str:
    if raw != "single_tone":
        raise ValueError("expected single_tone")
    return raw


def _confirm_interactively(
    draft: ContextDraft, *, filenames: tuple[str, ...], test_file: str
) -> dict[str, object]:
    def parse_reference(raw: str) -> str:
        if raw not in filenames or raw == test_file:
            raise ValueError("expected one of the other uploaded files")
        return raw

    values: dict[str, object] = {
        "mode": _ask_field("mode", draft.mode, _parse_mode),
        "reference_file": None,
        "nominal_fundamental_hz": None,
        "stimulus_kind": None,
    }
    if values["mode"] == "paired_reference":
        values["reference_file"] = _ask_field(
            "reference_file", draft.reference_file, parse_reference
        )
    elif values["mode"] == "nominal_single_tone":
        values["nominal_fundamental_hz"] = _ask_field(
            "nominal_fundamental_hz", draft.nominal_fundamental_hz, _parse_hz
        )
        values["stimulus_kind"] = _ask_field(
            "stimulus_kind",
            draft.stimulus_kind if draft.stimulus_kind == "single_tone" else None,
            _parse_stimulus_kind,
        )
    return values


async def _intake_diagnose(
    args: argparse.Namespace,
    service_factory: Callable[[], DiagnosisApplicationService],
) -> int:
    explicit = any(getattr(args, name) is not None for name in _INTAKE_FIELD_FLAGS)
    if not args.yes and not explicit and not sys.stdin.isatty():
        _print_error(
            "invalid_request",
            "non-interactive intake diagnose needs --yes or explicit context flags",
        )
        return 2
    paths = (Path(args.test_file), *(Path(item) for item in args.files))
    filenames = tuple(path.name for path in paths)
    test_file = filenames[0]
    max_bytes = WavLoadLimits().max_upload_bytes
    try:
        if len(paths) > MAX_INTAKE_FILES or len(set(filenames)) != len(filenames):
            raise ApplicationError(
                AppErrorDetail(
                    code="invalid_request",
                    message=(
                        f"intake accepts 1 to {MAX_INTAKE_FILES} WAV files "
                        "with distinct names"
                    ),
                )
            )
        data = {path.name: _read_wav_path(path, max_bytes) for path in paths}
    except ApplicationError as error:
        _print_error(error.detail.code, error.detail.message)
        return _exit_for_application_error(error)
    except OSError as error:
        _print_error("invalid_request", str(error))
        return 2
    rates = tuple(wav_header_sample_rate(data[name]) for name in filenames)

    service = service_factory()
    try:
        draft = await service.draft_intake_payload(
            {
                "text": args.text,
                "filenames": list(filenames),
                "test_file": test_file,
                "sample_rates_hz": (
                    [] if any(rate is None for rate in rates) else list(rates)
                ),
            }
        )
        _print_draft(draft)
        if args.yes:
            values = draft_confirmed_by_yes(draft)
        elif explicit:
            values = dict.fromkeys(
                ("mode", "reference_file", "nominal_fundamental_hz", "stimulus_kind")
            )
        else:
            try:
                values = _confirm_interactively(
                    draft, filenames=filenames, test_file=test_file
                )
            except EOFError as error:
                raise ApplicationError(
                    AppErrorDetail(
                        code="invalid_request", message="confirmation aborted"
                    )
                ) from error
        overrides = {
            "mode": args.mode,
            "reference_file": args.reference,
            "nominal_fundamental_hz": args.nominal_fundamental_hz,
            "stimulus_kind": args.stimulus_kind,
        }
        values.update({key: value for key, value in overrides.items() if value is not None})
        assembly = assemble_intake_submission(
            **values, filenames=filenames, test_file=test_file
        )
        note = downgrade_message(assembly)
        if note is not None:
            print(f"note: {note}", file=sys.stderr)
        confirmed = assembly.confirmed
        print(f"submitting mode: {confirmed.mode}", file=sys.stderr)
        reference_name = confirmed.reference_file
        submission = await service.submit_contextual_wav(
            data[test_file],
            test_filename=test_file,
            mode=confirmed.mode,
            reference_data=None if reference_name is None else data[reference_name],
            reference_filename=reference_name,
            nominal_fundamental_hz=confirmed.nominal_fundamental_hz,
            stimulus_kind=confirmed.stimulus_kind,
            user_request=INTAKE_DIAGNOSIS_QUESTION,
            channel=args.channel,
            context_origin=CONTEXT_ORIGIN_INTAKE,
        )
        return await _finish_contextual(args, service, submission.run_id)
    except ApplicationError as error:
        _print_error(error.detail.code, error.detail.message)
        return _exit_for_application_error(error)
    except Exception as error:  # noqa: BLE001
        detail = sanitize_application_error(error)
        _print_error(detail.code, detail.message)
        return 1
    finally:
        await service.aclose()


def _print_sweep_text(diagnosis: SweepDiagnosis) -> None:
    print(f"outcome: {diagnosis.outcome}")
    print(f"summary: {diagnosis.summary}")
    print(
        f"engine: {diagnosis.engine_version}; profile: {diagnosis.profile_id} "
        f"{diagnosis.profile_version}; model calls: {diagnosis.model_calls}"
    )
    print(THRESHOLD_NOTICE)
    for level in diagnosis.levels:
        print(f"level {level.level_label}: {level.outcome}")
        for claim in level.claims:
            print(f"  - {claim.fault_type}: {claim.statement}")
        bands = [
            f"{band.center_hz:g} Hz {band.thd_percent:.2f}%"
            for band in level.measurement.bands
            if band.measurable and band.thd_percent is not None
        ]
        print("  band THD: " + ("; ".join(bands) if bands else "no measurable band"))


def _sweep(args: argparse.Namespace) -> int:
    try:
        if args.sweep_command == "stimulus":
            args.out.write_bytes(stimulus_wav(args.rate))
            print(f"wrote {args.out} (sweep-stimulus-1.0, {args.rate} Hz)")
            return 0
        labels = args.level or [
            f"L{index}" for index in range(1, len(args.recordings) + 1)
        ]
        if len(labels) != len(args.recordings):
            raise ApplicationError(
                AppErrorDetail(
                    code="invalid_request",
                    message="give one --level per recording",
                )
            )
        max_bytes = WavLoadLimits().max_upload_bytes
        recordings = [
            (_read_wav_path(path, max_bytes), label)
            for path, label in zip(args.recordings, labels, strict=True)
        ]
        diagnosis = diagnose_sweep(recordings)
    except ApplicationError as error:
        _print_error(error.detail.code, error.detail.message)
        return _exit_for_application_error(error)
    except OSError as error:
        _print_error("invalid_request", str(error))
        return 2
    report = build_sweep_report(diagnosis, generated_at=datetime.now(UTC))
    try:
        explanation = (
            asyncio.run(_explanation(args, sweep_explanation_packet(diagnosis)))
            if args.explain is not None
            else None
        )
    except ApplicationError as error:
        _print_error(error.detail.code, error.detail.message)
        return _exit_for_application_error(error)
    payload = explanation.model_dump(mode="json") if explanation is not None else None
    if args.output == "json":
        sys.stdout.write(render_sweep_json(report, explanation=payload))
    else:
        _print_sweep_text(diagnosis)
        if explanation is not None:
            print("\n".join(explanation_lines(explanation)))
    if args.html_output is not None:
        html_part = render_explanation_html(explanation) if explanation is not None else None
        args.html_output.write_text(
            render_sweep_html(report, explanation_html=html_part), encoding="utf-8"
        )
    return 0


def _print_draft_or_questionnaire(result: GuideResult) -> None:
    if result.draft is not None:
        draft = result.draft
        print(f"plan: {draft.plan_id} (AI draft; confirm every value before use)")
        print("parameters: " + json.dumps(draft.parameters.model_dump(mode="json"), ensure_ascii=False))
        for quote in draft.rationale_quotes:
            print(f"  because you wrote: {quote}")
        for question in draft.questions:
            print(f"  question: {question}")
        return
    if result.fallback_reason:
        print(f"AI draft not used: {result.fallback_reason}")
    print("questionnaire (answer with: signal-diag guide questionnaire --answer id=answer ...):")
    for item in result.questionnaire:
        options = ", ".join(f"{o.answer} ({o.label_zh})" for o in item.options)
        print(f"  {item.question_id}: {item.text_zh} [{options}]")


def _session(args: argparse.Namespace) -> int:
    from signal_diag.app.session_eval import load_cases, run_session, score
    from signal_diag.app.test_session import summary_lines

    cases = {case["case_id"]: case for case in load_cases(args.cases)}
    if args.case_id not in cases:
        print(f"unknown scenario {args.case_id!r}", file=sys.stderr)
        return 2
    state, log = run_session(cases[args.case_id])
    row = score(cases[args.case_id], state)
    if args.output == "json":
        print(json.dumps({"score": row, "steps": log, "summary": list(summary_lines(state))}, ensure_ascii=False, indent=2))
        return 0
    for index, entry in enumerate(log, 1):
        action = entry["action"]
        if action["kind"] == "propose_test":
            fix = f" fix={action['fix']}" if action["fix"] else ""
            print(f"{index}. test {action['levels_db']}{fix} -> {entry.get('result')}")
        elif action["kind"] == "ask_user":
            print(f"{index}. ask {action['field']} -> {entry.get('answer')}")
        else:
            print(f"{index}. finish {action['status']}")
    for line in summary_lines(state):
        print(line)
    print(f"correct: {row['correct']} (expected {row['expected_status']}, onset {row['expected_onset_db']})")
    return 0


def _guide(args: argparse.Namespace) -> int:
    try:
        if args.guide_command == "draft":
            service = build_guide_service(os.environ)
            try:
                result = asyncio.run(
                    service.draft(
                        GuideRequest(text=args.text, filenames=tuple(args.files)),
                        use_model=args.model,
                    )
                )
            finally:
                asyncio.run(service.aclose())
            _print_draft_or_questionnaire(result)
            return 0
        if args.guide_command == "questionnaire":
            answers = dict(item.split("=", 1) for item in args.answer if "=" in item)
            draft = questionnaire_draft(answers, language=args.language)
            print(json.dumps(draft.model_dump(mode="json"), ensure_ascii=False, indent=2))
            return 0
        record = confirm_plan(
            ConfirmRequest(
                plan_id=args.plan,
                source=args.source,
                language=args.language,
                sample_rate_hz=args.rate,
                level_labels=tuple(args.level),
                connection=args.connection,
                test_file=args.test_file,
                reference_file=args.reference_file,
                nominal_fundamental_hz=args.nominal_hz,
            )
        )
    except PlanRejected as rejected:
        _print_error("invalid_request", str(rejected))
        return 2
    except ApplicationError as error:
        _print_error(error.detail.code, error.detail.message)
        return _exit_for_application_error(error)
    except ValidationError as error:
        _print_error("invalid_request", str(error.errors()[0]["msg"]))
        return 2
    print(f"plan {record.plan_key} ({record.plan_id}, {record.version})")
    for index, step in enumerate(record.steps, 1):
        print(f"  {index}. {step}")
    print(f"next page: {record.next_page}")
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    service_factory: Callable[[], DiagnosisApplicationService] = build_engine_service,
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
    if args.command == "intake" and args.intake_command == "diagnose":
        return asyncio.run(_intake_diagnose(args, service_factory))
    if args.command == "sweep":
        return _sweep(args)
    if args.command == "guide":
        return _guide(args)
    if args.command == "session":
        return _session(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
