"""CLI gates for the external WAV validity study harness."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from signal_diag.evaluation.external.__main__ import build_parser, main
from signal_diag.evaluation.external.models import SourceCatalog
from tests.evaluation.external.test_reporting import _make_external_study_report

_PYTHON = sys.executable
_MODULE = "signal_diag.evaluation.external"
_REPO_ROOT = Path(__file__).resolve().parents[3]
_PHASE4_DEFAULT_FRAGMENT = "phase4_3_1"
_PHASE5_DEFAULT_FRAGMENT = "v0_2_acceptance"


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_REPO_ROOT / "src")
    return subprocess.run(
        [_PYTHON, "-m", _MODULE, *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=_REPO_ROOT,
    )


def test_cli_help_lists_required_subcommands() -> None:
    parser = build_parser()
    help_text = parser.format_help()
    for command in (
        "validate-source-catalog",
        "acquire",
        "derive",
        "reference",
        "validate-manifest",
        "build-review-package",
        "score-review",
        "seal-final",
        "run-baseline",
        "run-agent",
        "write-report",
        "verify-bundle",
        "verify-preservation",
    ):
        assert command in help_text


def test_cli_defaults_do_not_point_into_protected_phase4_or_phase5_dirs() -> None:
    help_text = build_parser().format_help()
    lowered = help_text.lower()
    assert _PHASE4_DEFAULT_FRAGMENT not in lowered
    assert _PHASE5_DEFAULT_FRAGMENT not in lowered


def test_acquire_fails_without_allow_network(tmp_path: Path) -> None:
    catalog = SourceCatalog(
        catalog_id="test-catalog",
        version="1.0.0",
        sources=(),
    )
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(
        json.dumps(catalog.model_dump(mode="json"), sort_keys=True),
        encoding="utf-8",
    )
    assert (
        main(
            [
                "acquire",
                "--catalog",
                str(catalog_path),
                "--destination",
                str(tmp_path / "downloads"),
            ]
        )
        == 2
    )


def test_run_agent_fails_without_authorize_real_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    assert (
        main(
            [
                "run-agent",
                "--seal",
                str(tmp_path / "missing-seal"),
                "--asset-root",
                str(tmp_path / "assets"),
                "--output",
                str(tmp_path / "agent-output"),
            ]
        )
        == 2
    )


def test_run_agent_fails_without_credentials_before_output_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    output = tmp_path / "agent-output"
    assert (
        main(
            [
                "run-agent",
                "--authorize-real-model",
                "--seal",
                str(tmp_path / "missing-seal"),
                "--asset-root",
                str(tmp_path / "assets"),
                "--output",
                str(output),
            ]
        )
        == 2
    )
    assert not output.exists()


def test_write_report_requires_explicit_paths(tmp_path: Path) -> None:
    report = _make_external_study_report()
    input_path = tmp_path / "report.json"
    input_path.write_text(
        json.dumps(report.model_dump(mode="json"), sort_keys=True),
        encoding="utf-8",
    )
    destination = tmp_path / "bundle"
    assert main(["write-report", "--input", str(input_path), "--destination", str(destination)]) == 0
    assert (destination / "checksums.sha256").is_file()


def test_verify_bundle_command(tmp_path: Path) -> None:
    report = _make_external_study_report()
    report_path = tmp_path / "report.json"
    report_path.write_text(
        json.dumps(report.model_dump(mode="json"), sort_keys=True),
        encoding="utf-8",
    )
    destination = tmp_path / "bundle"
    assert (
        main(["write-report", "--input", str(report_path), "--destination", str(destination)])
        == 0
    )
    assert main(["verify-bundle", "--bundle", str(destination)]) == 0
