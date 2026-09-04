"""Checkpoint AA — direct-service argparse CLI (T271–T275)."""

from __future__ import annotations

import ast
import json
import struct
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from signal_diag.agent.models import (
    AgentDecision,
    FinishDecision,
    PlannerContext,
    TaskAssessment,
)
from signal_diag.app.cli import _read_wav_path, build_parser, main
from signal_diag.app.contextual_models import (
    ContextualAppRunSnapshot,
    ContextualRunSubmission,
)
from signal_diag.app.errors import (
    ApplicationError,
    PlannerNotConfiguredError,
)
from signal_diag.app.models import (
    AppErrorDetail,
    AppRunSnapshot,
    DemoPresetId,
    DiagnosisReport,
    PlannerIdentity,
    RunSubmission,
    SourceSummary,
    WaveformPoint,
    WaveformPreview,
)
from signal_diag.app.presets import list_demo_presets
from signal_diag.app.reporting import render_report_html, render_report_json
from signal_diag.app.service import ApplicationDependencies, DiagnosisApplicationService
from signal_diag.knowledge.index import KnowledgeIndex
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal import InMemorySignalRepository, WavLoadLimits
from signal_diag.signal.context import EffectiveCapabilities, StimulusContext
from tests.app.test_reporting import _completed_snapshot

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLI_PATH = PROJECT_ROOT / "src" / "signal_diag" / "app" / "cli.py"
PROFILE_PATH = (
    PROJECT_ROOT / "src" / "signal_diag" / "rules" / "profiles" / "s1_distortion_v1.yaml"
)
CORPUS_PATH = PROJECT_ROOT / "src" / "signal_diag" / "knowledge" / "corpus"
QUESTION = "Why does this signal sound distorted?"
PRESET_IDS: tuple[DemoPresetId, ...] = (
    "clean_periodic",
    "clipping",
    "harmonic_distortion",
    "combined_distortion",
    "noise_inconclusive",
)
FORBIDDEN_HTTP = ("httpx", "requests", "urllib.request", "http.client")
FORBIDDEN_PLANNER_TOKENS = (
    "preset_id",
    "combined_distortion",
    "fault_labels",
    "ground_truth",
    "acceptable_first_tools",
    "target_status",
)
_ASSESSMENT = TaskAssessment(
    task_type="distortion_analysis",
    objective="determine why the signal sounds distorted",
    hypotheses=("clipping", "harmonic_distortion"),
)
_FINISH_DECISION = FinishDecision(
    task_assessment=_ASSESSMENT,
    outcome="inconclusive",
    claims=(),
    confidence_label="low",
    limitations=("deterministic test finish without additional tools",),
)
NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
STARTED = datetime(2026, 8, 31, 12, 1, tzinfo=UTC)
FINISHED = datetime(2026, 8, 31, 12, 2, tzinfo=UTC)
RUN_ID = "run_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


class _ImmediateFinishPlanner:
    def __init__(self) -> None:
        self.contexts: list[PlannerContext] = []

    async def decide(self, context: PlannerContext) -> AgentDecision:
        self.contexts.append(context)
        return _FINISH_DECISION


class _FakeService:
    def __init__(
        self,
        *,
        snapshot: AppRunSnapshot | None = None,
        contextual_snapshot: ContextualAppRunSnapshot | None = None,
        submit_error: Exception | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.contextual_snapshot = contextual_snapshot
        self.submit_error = submit_error
        self.submit_wav_calls: list[dict[str, Any]] = []
        self.submit_synthetic_calls: list[dict[str, Any]] = []
        self.submit_contextual_calls: list[dict[str, Any]] = []
        self.wait_calls: list[str] = []
        self.wait_contextual_calls: list[str] = []
        self.closed = False
        self.run_id = snapshot.run_id if snapshot is not None else RUN_ID
        if contextual_snapshot is not None:
            self.run_id = contextual_snapshot.run_id

    async def submit_wav(
        self,
        data: bytes,
        *,
        filename: str | None,
        user_request: str,
        channel: str = "mixdown",
    ) -> RunSubmission:
        if self.submit_error is not None:
            raise self.submit_error
        self.submit_wav_calls.append(
            {
                "data": data,
                "filename": filename,
                "user_request": user_request,
                "channel": channel,
            }
        )
        return RunSubmission(run_id=self.run_id, status="queued")

    async def submit_synthetic(
        self,
        preset_id: DemoPresetId,
        *,
        user_request: str,
        channel: str = "mixdown",
    ) -> RunSubmission:
        if self.submit_error is not None:
            raise self.submit_error
        self.submit_synthetic_calls.append(
            {
                "preset_id": preset_id,
                "user_request": user_request,
                "channel": channel,
            }
        )
        return RunSubmission(run_id=self.run_id, status="queued")

    async def submit_contextual_wav(
        self,
        test_data: bytes,
        *,
        test_filename: str | None,
        mode: str,
        reference_data: bytes | None,
        reference_filename: str | None,
        nominal_fundamental_hz: float | None,
        stimulus_kind: str | None,
        user_request: str,
        channel: str = "mixdown",
    ) -> ContextualRunSubmission:
        if self.submit_error is not None:
            raise self.submit_error
        self.submit_contextual_calls.append(
            {
                "test_data": test_data,
                "test_filename": test_filename,
                "mode": mode,
                "reference_data": reference_data,
                "reference_filename": reference_filename,
                "nominal_fundamental_hz": nominal_fundamental_hz,
                "stimulus_kind": stimulus_kind,
                "user_request": user_request,
                "channel": channel,
            }
        )
        return ContextualRunSubmission(run_id=self.run_id, status="queued")

    async def wait_for_terminal(
        self,
        run_id: str,
        *,
        timeout_s: float | None = None,
    ) -> AppRunSnapshot:
        del timeout_s
        self.wait_calls.append(run_id)
        assert self.snapshot is not None
        return self.snapshot

    async def wait_for_contextual_terminal(
        self,
        run_id: str,
        *,
        timeout_s: float | None = None,
    ) -> ContextualAppRunSnapshot:
        del timeout_s
        self.wait_contextual_calls.append(run_id)
        assert self.contextual_snapshot is not None
        return self.contextual_snapshot

    def list_presets(self) -> tuple[Any, ...]:
        return list_demo_presets()

    async def aclose(self) -> None:
        self.closed = True


def _run(argv: Sequence[str], *, service_factory: Any | None = None) -> int:
    kwargs: dict[str, Any] = {}
    if service_factory is not None:
        kwargs["service_factory"] = service_factory
    try:
        result = main(list(argv), **kwargs)
    except SystemExit as exc:
        if exc.code in (0, None):
            return 0
        return int(exc.code)
    if result is None:
        return 0
    return int(result)


def _json_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        keys.update(str(item) for item in value)
        for nested in value.values():
            keys.update(_json_keys(nested))
    elif isinstance(value, list):
        for nested in value:
            keys.update(_json_keys(nested))
    return keys


def _identity() -> PlannerIdentity:
    return PlannerIdentity(
        provider="deepseek",
        model="deepseek-v4-flash",
        prompt_version="v0.2-s1-planner-8.1",
        phase4_certified_default=True,
    )


def _make_service(planner_factory: Any) -> DiagnosisApplicationService:
    dependencies = ApplicationDependencies(
        repository=InMemorySignalRepository(),
        planner_factory=planner_factory,
        planner_identity=_identity(),
        planner_configured=True,
        rule_engine=RuleEngine(),
        rule_profile_loader=YamlRuleProfileLoader(
            {"profile_s1_distortion": PROFILE_PATH}
        ),
        knowledge_index=KnowledgeIndex(CORPUS_PATH),
    )
    return DiagnosisApplicationService(dependencies, clock=lambda: NOW)


def _riff_wave(*, fmt_payload: bytes, data: bytes) -> bytes:
    chunks = [b"fmt " + struct.pack("<I", len(fmt_payload)) + fmt_payload]
    chunks.append(b"data" + struct.pack("<I", len(data)) + data)
    body = b"WAVE" + b"".join(
        chunk + (b"\x00" if len(chunk) % 2 else b"") for chunk in chunks
    )
    return b"RIFF" + struct.pack("<I", len(body)) + body


def _pcm_fmt(*, channels: int, rate: int, bits: int) -> bytes:
    block_align = channels * bits // 8
    return struct.pack(
        "<HHIIHH", 1, channels, rate, rate * block_align, block_align, bits
    )


def _mono_extrema_wav(*, rate: int = 8_000) -> bytes:
    pcm = struct.pack("<hhh", -32768, 0, 32767)
    return _riff_wave(fmt_payload=_pcm_fmt(channels=1, rate=rate, bits=16), data=pcm)


def _failed_snapshot() -> AppRunSnapshot:
    return AppRunSnapshot(
        run_id=RUN_ID,
        status="failed",
        created_at=NOW,
        started_at=STARTED,
        finished_at=FINISHED,
        user_request=QUESTION,
        analyzed_channel="mixdown",
        source=SourceSummary(
            source_kind="synthetic",
            display_name="clipping",
            sample_rate_hz=48_000,
            channels=1,
            num_frames=48_000,
            duration_s=1.0,
            preset_id="clipping",
        ),
        planner_identity=_identity(),
        waveform_preview=WaveformPreview(
            sample_rate_hz=48_000,
            original_num_samples=1,
            points=(WaveformPoint(sample_index=0, time_s=0.0, amplitude=0.0),),
        ),
        application_error=AppErrorDetail(
            code="internal_error",
            message="diagnosis execution failed",
        ),
    )


def _cli_source() -> str:
    return CLI_PATH.read_text(encoding="utf-8")


def _module_level_import_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    assert isinstance(tree, ast.Module)
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".", 1)[0])
            names.add(node.module)
    return names


def test_t271_parser_defaults() -> None:
    args = build_parser().parse_args(["diagnose", "synthetic", "clipping"])
    assert args.question == "Why does this signal sound distorted?"
    assert args.channel == "mixdown"
    assert args.output == "text"
    assert args.html_output is None


def test_t271_command_grammar_and_usage_errors(capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()
    wav = parser.parse_args(["diagnose", "wav", "demo.wav"])
    assert wav.source_kind == "wav"
    assert Path(wav.path) == Path("demo.wav")
    synth = parser.parse_args(
        [
            "diagnose",
            "synthetic",
            "harmonic_distortion",
            "--question",
            "custom question",
            "--channel",
            "left",
            "--output",
            "json",
            "--html-output",
            "out.html",
        ]
    )
    assert synth.source_kind == "synthetic"
    assert synth.preset_id == "harmonic_distortion"
    assert synth.question == "custom question"
    assert synth.channel == "left"
    assert synth.output == "json"
    assert Path(synth.html_output) == Path("out.html")
    serve = parser.parse_args(["serve"])
    assert serve.host == "127.0.0.1"
    assert serve.port == 8000
    explicit = parser.parse_args(["serve", "--host", "0.0.0.0", "--port", "9001"])
    assert explicit.host == "0.0.0.0"
    assert explicit.port == 9001
    for channel in ("left", "right", "mixdown"):
        parsed = parser.parse_args(["diagnose", "synthetic", "clipping", "--channel", channel])
        assert parsed.channel == channel

    usage_argv = (
        [],
        ["diagnose"],
        ["diagnose", "wav"],
        ["diagnose", "synthetic"],
        ["diagnose", "synthetic", "clipping", "--channel", "stereo"],
        ["diagnose", "synthetic", "clipping", "--output", "xml"],
        ["serve", "--port", "not-a-port"],
        ["serve", "--question", QUESTION],
        ["presets", "--output", "json"],
        ["diagnose", "wav", "demo.wav", "extra"],
    )
    for argv in usage_argv:
        with pytest.raises(SystemExit) as exc:
            parser.parse_args(argv)
        assert exc.value.code == 2
        capsys.readouterr()
        assert _run(argv) == 2
        capsys.readouterr()

    service = _FakeService()
    code = _run(["presets"], service_factory=lambda: service)
    captured = capsys.readouterr()
    assert code == 0
    for preset_id in PRESET_IDS:
        assert preset_id in captured.out
    assert service.closed is True


def test_t272_wav_bounded_direct_service_no_http(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    wav_bytes = _mono_extrema_wav()
    wav_path = tmp_path / "demo.wav"
    wav_path.write_bytes(wav_bytes)
    snapshot = _completed_snapshot()
    service = _FakeService(snapshot=snapshot)
    code = _run(
        ["diagnose", "wav", str(wav_path), "--output", "json"],
        service_factory=lambda: service,
    )
    capsys.readouterr()
    assert code == 0
    assert len(service.submit_wav_calls) == 1
    call = service.submit_wav_calls[0]
    assert call["data"] == wav_bytes
    assert call["filename"] == "demo.wav"
    assert call["user_request"] == QUESTION
    assert call["channel"] == "mixdown"
    assert service.submit_synthetic_calls == []
    assert service.wait_calls == [snapshot.run_id]
    assert service.closed is True

    bounded = _read_wav_path(wav_path, max_bytes=len(wav_bytes))
    assert bounded == wav_bytes
    with pytest.raises(ApplicationError) as too_large:
        _read_wav_path(wav_path, max_bytes=len(wav_bytes) - 1)
    assert too_large.value.detail.code == "payload_too_large"
    assert "WAV exceeds" in too_large.value.detail.message

    huge = tmp_path / "huge.wav"
    huge.write_bytes(b"A" * (WavLoadLimits().max_upload_bytes + 1))

    def boom_factory() -> DiagnosisApplicationService:
        raise AssertionError("oversized WAV must not construct a service")

    code = _run(["diagnose", "wav", str(huge)], service_factory=boom_factory)
    captured = capsys.readouterr()
    assert code == 2
    assert "payload_too_large" in captured.err or "exceeds" in captured.err

    missing = tmp_path / "missing.wav"
    code = _run(["diagnose", "wav", str(missing)], service_factory=boom_factory)
    capsys.readouterr()
    assert code == 2

    source = _cli_source()
    tree = ast.parse(source, filename=str(CLI_PATH))
    assert "Path.read_bytes()" not in source
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            assert node.attr != "read_bytes"
    module_imports = _module_level_import_names(tree)
    for token in FORBIDDEN_HTTP:
        assert token not in source
        assert token.split(".", 1)[0] not in module_imports
    assert "fastapi" not in module_imports
    assert "uvicorn" not in module_imports
    assert "httpx" not in module_imports


def test_t273_synthetic_uses_catalog_without_truth_leak(
    capsys: pytest.CaptureFixture[str],
) -> None:
    planner = _ImmediateFinishPlanner()
    service = _make_service(lambda: planner)
    code = _run(
        [
            "diagnose",
            "synthetic",
            "combined_distortion",
            "--question",
            QUESTION,
            "--channel",
            "mixdown",
            "--output",
            "text",
        ],
        service_factory=lambda: service,
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "inconclusive" in captured.out
    assert planner.contexts
    for context in planner.contexts:
        blob = json.dumps(context.model_dump(mode="json"))
        assert context.user_request.startswith(QUESTION)
        assert "Analyzed channel: mixdown." in context.user_request
        for token in FORBIDDEN_PLANNER_TOKENS:
            assert token not in context.user_request
            if token != "preset_id":
                assert token not in blob
        keys = _json_keys(json.loads(blob))
        assert "preset_id" not in keys
        assert "fault_labels" not in keys
        assert "ground_truth" not in keys


def test_t274_output_reports_and_exit_codes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    snapshot = _completed_snapshot()
    assert snapshot.result is not None
    assert snapshot.result.diagnosis is not None
    html_path = tmp_path / "report.html"

    service = _FakeService(snapshot=snapshot)
    code = _run(
        [
            "diagnose",
            "synthetic",
            "clipping",
            "--output",
            "json",
            "--html-output",
            str(html_path),
        ],
        service_factory=lambda: service,
    )
    captured = capsys.readouterr()
    assert code == 0
    report = DiagnosisReport.model_validate_json(captured.out)
    assert captured.out == render_report_json(report)
    assert report.result == snapshot.result
    assert html_path.read_bytes() == render_report_html(report).encode("utf-8")
    assert html_path.read_text(encoding="utf-8") == render_report_html(report)
    assert "<html" not in captured.out.lower()
    assert service.closed is True

    text_service = _FakeService(snapshot=snapshot)
    code = _run(
        ["diagnose", "synthetic", "clipping", "--output", "text"],
        service_factory=lambda: text_service,
    )
    text_out = capsys.readouterr().out
    assert code == 0
    diagnosis = snapshot.result.diagnosis
    assert diagnosis.outcome in text_out
    assert diagnosis.confidence_label in text_out
    assert diagnosis.termination_reason in text_out
    claim = diagnosis.claims[0]
    assert claim.claim_id in text_out
    assert claim.statement in text_out
    for ref in claim.evidence_refs + claim.rule_refs + claim.knowledge_refs:
        assert ref in text_out

    for outcome in ("supported_fault", "no_supported_fault", "inconclusive"):
        diagnosis_copy = diagnosis.model_copy(update={"outcome": outcome})
        result_copy = snapshot.result.model_copy(update={"diagnosis": diagnosis_copy})
        variant = snapshot.model_copy(update={"result": result_copy})
        code = _run(
            ["diagnose", "synthetic", "clipping"],
            service_factory=lambda snap=variant: _FakeService(snapshot=snap),
        )
        capsys.readouterr()
        assert code == 0

    nested = snapshot.result.model_copy(update={"status": "error"})
    nested_snapshot = snapshot.model_copy(update={"result": nested})
    nested_html = tmp_path / "nested.html"
    nested_service = _FakeService(snapshot=nested_snapshot)
    code = _run(
        [
            "diagnose",
            "synthetic",
            "clipping",
            "--output",
            "json",
            "--html-output",
            str(nested_html),
        ],
        service_factory=lambda: nested_service,
    )
    nested_out = capsys.readouterr().out
    assert code == 1
    nested_report = DiagnosisReport.model_validate_json(nested_out)
    assert nested_report.result.status == "error"
    assert nested_out == render_report_json(nested_report)
    assert nested_html.exists()

    failed_service = _FakeService(snapshot=_failed_snapshot())
    code = _run(
        ["diagnose", "synthetic", "clipping"],
        service_factory=lambda: failed_service,
    )
    failed_captured = capsys.readouterr()
    assert code == 1
    assert "internal_error" in failed_captured.err or "execution failed" in failed_captured.err
    assert failed_service.closed is True

    unconfigured = _FakeService(
        submit_error=PlannerNotConfiguredError(
            AppErrorDetail(
                code="planner_not_configured",
                message="RealLLMPlanner is not configured",
            )
        )
    )
    code = _run(
        ["diagnose", "synthetic", "clipping"],
        service_factory=lambda: unconfigured,
    )
    unconfigured_captured = capsys.readouterr()
    assert code == 2
    assert "planner_not_configured" in unconfigured_captured.err
    assert unconfigured.closed is True

    unknown = _FakeService(
        submit_error=ApplicationError(
            AppErrorDetail(code="unknown_preset", message="Unknown demo preset: nope")
        )
    )
    code = _run(
        ["diagnose", "synthetic", "clipping"],
        service_factory=lambda: unknown,
    )
    unknown_captured = capsys.readouterr()
    assert code == 2
    assert "unknown_preset" in unknown_captured.err
    assert unknown.closed is True

    invalid_wav = _FakeService(
        submit_error=ApplicationError(
            AppErrorDetail(code="invalid_wav", message="truncated WAV")
        )
    )
    wav_path = tmp_path / "bad.wav"
    wav_path.write_bytes(_mono_extrema_wav())
    code = _run(
        ["diagnose", "wav", str(wav_path)],
        service_factory=lambda: invalid_wav,
    )
    invalid_captured = capsys.readouterr()
    assert code == 2
    assert "invalid_wav" in invalid_captured.err


def test_t275_serve_defaults_no_scripted_switch(capsys: pytest.CaptureFixture[str]) -> None:
    args = build_parser().parse_args(["serve"])
    assert args.host == "127.0.0.1"
    assert args.port == 8000
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["serve", "--scripted"])
    assert exc.value.code == 2
    capsys.readouterr()
    with pytest.raises(SystemExit):
        build_parser().parse_args(["diagnose", "synthetic", "clipping", "--planner", "scripted"])
    capsys.readouterr()

    fake_app = object()
    with (
        patch("signal_diag.app.api.create_app", return_value=fake_app) as create,
        patch("uvicorn.run") as run,
    ):
        code = _run(["serve"])
        default_out = capsys.readouterr()
        assert code == 0
        create.assert_called_once_with()
        run.assert_called_once()
        assert run.call_args.args[0] is fake_app
        assert run.call_args.kwargs["host"] == "127.0.0.1"
        assert run.call_args.kwargs["port"] == 8000
        assert run.call_args.kwargs["log_level"] == "info"
        warning = (default_out.out + default_out.err).lower()
        assert "no-auth" in warning or "no auth" in warning
        assert "local" in warning or "127.0.0.1" in warning or "untrusted" in warning

        code = _run(["serve", "--host", "0.0.0.0", "--port", "9001"])
        capsys.readouterr()
        assert code == 0
        assert run.call_args.kwargs["host"] == "0.0.0.0"
        assert run.call_args.kwargs["port"] == 9001

    source = _cli_source()
    tree = ast.parse(source, filename=str(CLI_PATH))
    assert "ScriptedPlanner" not in source
    module_imports = _module_level_import_names(tree)
    assert "fastapi" not in module_imports
    assert "uvicorn" not in module_imports
    create_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == "create_app")
            or (isinstance(node.func, ast.Attribute) and node.func.attr == "create_app")
        )
    ]
    assert create_calls
    for call in create_calls:
        assert call.args == []
        assert call.keywords == []
    uvicorn_runs = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "uvicorn"
    ]
    assert uvicorn_runs


def _contextual_completed_snapshot() -> ContextualAppRunSnapshot:
    from signal_diag.agent.models import AgentRunResult, StructuredDiagnosis

    return ContextualAppRunSnapshot(
        run_id=RUN_ID,
        status="completed",
        created_at=NOW,
        started_at=STARTED,
        finished_at=FINISHED,
        user_request=QUESTION,
        analyzed_channel="mixdown",
        test_source=SourceSummary(
            source_kind="wav",
            display_name="test.wav",
            sample_rate_hz=8_000,
            channels=1,
            num_frames=3,
            duration_s=3 / 8_000,
            bits_per_sample=16,
        ),
        reference_source=SourceSummary(
            source_kind="wav",
            display_name="ref.wav",
            sample_rate_hz=8_000,
            channels=1,
            num_frames=3,
            duration_s=3 / 8_000,
            bits_per_sample=16,
        ),
        stimulus_context=StimulusContext(
            mode="paired_reference",
            test_signal_id="sig_test",
            reference_signal_id="sig_ref",
            assertion_source="user_supplied",
        ),
        effective_capabilities=EffectiveCapabilities(clipping=True),
        test_preview=WaveformPreview(
            sample_rate_hz=8_000,
            original_num_samples=1,
            points=(WaveformPoint(sample_index=0, time_s=0.0, amplitude=0.0),),
        ),
        planner_identity=_identity(),
        result=AgentRunResult(
            run_id="run_agent",
            status="success",
            diagnosis=StructuredDiagnosis(
                run_id="run_agent",
                task_type="distortion_analysis",
                outcome="inconclusive",
                claims=(),
                confidence_label="low",
                limitations=("comparison_invalid",),
                termination_reason="planner_finished",
                tool_call_count=0,
            ),
            observations=(),
            evidence=(),
            tool_history=(),
            termination_reason="planner_finished",
        ),
    )


def test_t_cx113_contextual_cli_parser_matrix() -> None:
    parser = build_parser()
    paired = parser.parse_args(
        [
            "diagnose",
            "contextual",
            "test.wav",
            "--mode",
            "paired_reference",
            "--reference",
            "ref.wav",
        ]
    )
    assert paired.source_kind == "contextual"
    assert Path(paired.path) == Path("test.wav")
    assert paired.mode == "paired_reference"
    assert Path(paired.reference) == Path("ref.wav")

    nominal = parser.parse_args(
        [
            "diagnose",
            "contextual",
            "tone.wav",
            "--mode",
            "nominal_single_tone",
            "--stimulus-kind",
            "single_tone",
            "--nominal-fundamental-hz",
            "440",
        ]
    )
    assert nominal.source_kind == "contextual"
    assert nominal.mode == "nominal_single_tone"
    assert nominal.stimulus_kind == "single_tone"
    assert nominal.nominal_fundamental_hz == 440.0
    assert nominal.reference is None


def test_t_cx114_contextual_cli_rejects_invalid_flag_matrix(
    capsys: pytest.CaptureFixture[str],
) -> None:
    invalid = (
        [
            "diagnose",
            "contextual",
            "test.wav",
            "--mode",
            "nominal_single_tone",
            "--reference",
            "ref.wav",
            "--stimulus-kind",
            "single_tone",
            "--nominal-fundamental-hz",
            "440",
        ],
        [
            "diagnose",
            "contextual",
            "test.wav",
            "--mode",
            "nominal_single_tone",
            "--stimulus-kind",
            "single_tone",
        ],
        [
            "diagnose",
            "contextual",
            "test.wav",
            "--mode",
            "paired_reference",
        ],
        [
            "diagnose",
            "contextual",
            "test.wav",
            "--mode",
            "single_signal",
        ],
    )
    for argv in invalid:
        code = _run(argv, service_factory=lambda: (_ for _ in ()).throw(AssertionError()))
        captured = capsys.readouterr()
        assert code == 2
        assert "error:" in captured.err.casefold() or "invalid" in captured.err.casefold()


def test_t_cx115_contextual_cli_submits_and_renders(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    test_wav = tmp_path / "test.wav"
    ref_wav = tmp_path / "ref.wav"
    payload = _mono_extrema_wav()
    test_wav.write_bytes(payload)
    ref_wav.write_bytes(payload)
    snapshot = _contextual_completed_snapshot()
    service = _FakeService(contextual_snapshot=snapshot)
    code = _run(
        [
            "diagnose",
            "contextual",
            str(test_wav),
            "--mode",
            "paired_reference",
            "--reference",
            str(ref_wav),
            "--output",
            "json",
        ],
        service_factory=lambda: service,
    )
    capsys.readouterr()
    assert code == 0
    assert len(service.submit_contextual_calls) == 1
    call = service.submit_contextual_calls[0]
    assert call["test_data"] == payload
    assert call["reference_data"] == payload
    assert call["mode"] == "paired_reference"
    assert call["test_filename"] == "test.wav"
    assert call["reference_filename"] == "ref.wav"
    assert service.submit_wav_calls == []
    assert service.wait_contextual_calls == [snapshot.run_id]
    assert service.wait_calls == []
    assert service.closed is True


def test_t_cx116_diagnose_wav_behavior_unchanged(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    wav_path = tmp_path / "demo.wav"
    wav_path.write_bytes(_mono_extrema_wav())
    snapshot = _completed_snapshot()
    service = _FakeService(snapshot=snapshot)
    code = _run(
        ["diagnose", "wav", str(wav_path), "--output", "json"],
        service_factory=lambda: service,
    )
    capsys.readouterr()
    assert code == 0
    assert len(service.submit_wav_calls) == 1
    assert service.submit_contextual_calls == []
    assert service.wait_calls == [snapshot.run_id]
    assert service.wait_contextual_calls == []
    source = _cli_source()
    assert "diagnose contextual" in source or 'sources.add_parser("contextual"' in source
    assert "submit_wav" in source
    assert "ScriptedPlanner" not in source
