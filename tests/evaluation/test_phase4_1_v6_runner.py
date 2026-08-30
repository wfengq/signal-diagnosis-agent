"""Phase 4.1 planner v6 additive campaigns (T199)."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from signal_diag.agent.planner import RealLLMPlanner, _Phase4V5RealLLMPlanner
from signal_diag.agent.prompts import _S1_PROMPT_V5, _S1_PROMPT_V6
from signal_diag.evaluation.dataset import load_dataset_manifest
from tests.evaluation.conftest import PHASE4_1_MANIFEST
from tests.evaluation.test_phase4_1_runner import _fingerprint
from tests.evaluation.test_runner import FORBIDDEN_CREDENTIAL_TOKENS

_STARTED = datetime(2026, 8, 30, 5, 0, tzinfo=UTC)
_V6_DEV_ID = "bench_phase4_1_dev_v6_gate2"
_V6_OFFICIAL_ID = "bench_official_s1_v11_planner6_gate2"
_V6_CAMPAIGNS = (
    "phase4",
    "phase4.1-development",
    "phase4.1-official",
    "phase4.1-v6-development",
    "phase4.1-v6-official",
)
_DEV_WARNING = "development split; not official held-out evidence"


def _write_gate_metrics(
    path: Path,
    *,
    benchmark_status: str,
    target_status: str,
) -> Path:
    dest = path / _V6_DEV_ID
    dest.mkdir(parents=True)
    (dest / "metrics.json").write_text(
        json.dumps(
            {
                "benchmark_status": benchmark_status,
                "target_status": target_status,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return dest


def test_t199_v5_campaign_choices_remain_and_v6_are_additive() -> None:
    from signal_diag.evaluation.__main__ import build_parser

    parser = build_parser()
    real = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    ).choices["run-real"]
    campaign = next(
        action for action in real._actions if "--campaign" in action.option_strings
    )
    assert tuple(campaign.choices) == _V6_CAMPAIGNS
    assert campaign.default == "phase4"
    help_text = real.format_help().lower()
    for token in FORBIDDEN_CREDENTIAL_TOKENS:
        assert token not in help_text


def test_t199_v5_routes_keep_v5_identity() -> None:
    from signal_diag.evaluation.runner import (
        _build_phase4_1_planner,
        _phase4_1_benchmark_config,
        _phase4_1_prompt_sha256,
    )

    config = _phase4_1_benchmark_config(
        benchmark_id="bench_phase4_1_dev_v5_gate1",
        started_at_utc=_STARTED,
    )
    assert config.prompt_version == "v0.2-s1-planner-5"
    assert config.prompt_sha256 == sha256(
        _S1_PROMPT_V5.system_prompt.encode()
    ).hexdigest()
    assert _phase4_1_prompt_sha256() == config.prompt_sha256
    stub = type(
        "StubClient",
        (),
        {"chat": type("Chat", (), {"completions": object()})()},
    )()
    planner = _build_phase4_1_planner(stub)
    assert type(planner) is _Phase4V5RealLLMPlanner
    assert planner._prompt_spec is _S1_PROMPT_V5


def test_t199_v6_config_and_canonical_ids() -> None:
    from signal_diag.evaluation.runner import (
        _build_phase4_1_v6_planner,
        _phase4_1_v6_benchmark_config,
        _phase4_1_v6_prompt_sha256,
    )

    expected_hash = sha256(_S1_PROMPT_V6.system_prompt.encode()).hexdigest()
    development = _phase4_1_v6_benchmark_config(
        benchmark_id=_V6_DEV_ID,
        started_at_utc=_STARTED,
    )
    official = _phase4_1_v6_benchmark_config(
        benchmark_id=_V6_OFFICIAL_ID,
        started_at_utc=datetime(2026, 8, 31, 9, 0, tzinfo=UTC),
    )
    assert development.prompt_version == "v0.2-s1-planner-6"
    assert development.dataset_version == "1.1.0"
    assert development.provider == "deepseek"
    assert development.model == "deepseek-v4-flash"
    assert development.repetitions == 5
    assert development.max_concurrency == 1
    assert development.prompt_sha256 == expected_hash
    assert _phase4_1_v6_prompt_sha256() == expected_hash
    assert _fingerprint(development) == _fingerprint(official)
    stub = type(
        "StubClient",
        (),
        {"chat": type("Chat", (), {"completions": object()})()},
    )()
    planner = _build_phase4_1_v6_planner(stub)
    assert type(planner) is RealLLMPlanner
    assert planner._prompt_spec is _S1_PROMPT_V6


@pytest.mark.asyncio
async def test_t199_v6_schedules_40_development_and_80_held_out(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from signal_diag.evaluation.runner import (
        _phase4_1_v6_benchmark_config,
        _run_phase4_1_v6_development_benchmark,
        _run_phase4_1_v6_official_benchmark,
    )

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    manifest = load_dataset_manifest(PHASE4_1_MANIFEST)
    development = await _run_phase4_1_v6_development_benchmark(
        manifest,
        _phase4_1_v6_benchmark_config(
            benchmark_id=_V6_DEV_ID,
            started_at_utc=_STARTED,
        ),
        tmp_path / "dev",
    )
    gate = _write_gate_metrics(
        tmp_path / "accepted",
        benchmark_status="completed",
        target_status="meets_target",
    )
    official = await _run_phase4_1_v6_official_benchmark(
        manifest,
        _phase4_1_v6_benchmark_config(
            benchmark_id=_V6_OFFICIAL_ID,
            started_at_utc=_STARTED,
        ),
        tmp_path / "official",
        development_bundle=gate,
    )
    dev_cases = {case.case_id for case in manifest.cases if case.split == "development"}
    held_cases = {case.case_id for case in manifest.cases if case.split == "held_out"}
    assert len(dev_cases) == 8
    assert len(held_cases) == 16
    dev_agent = [
        attempt
        for attempt in development.attempts
        if attempt.execution_path == "agent"
    ]
    official_agent = [
        attempt
        for attempt in official.attempts
        if attempt.execution_path == "agent"
    ]
    assert len(dev_agent) == 40
    assert len(official_agent) == 80
    assert {attempt.case_id for attempt in dev_agent} == dev_cases
    assert {attempt.case_id for attempt in official_agent} == held_cases
    assert {attempt.error_code for attempt in dev_agent} == {"missing_credentials"}
    assert {attempt.error_code for attempt in official_agent} == {"missing_credentials"}
    assert _DEV_WARNING in development.warnings
    assert development.config.prompt_version == "v0.2-s1-planner-6"
    assert official.config.prompt_version == "v0.2-s1-planner-6"


@pytest.mark.asyncio
async def test_t199_rejects_mismatched_identity_and_existing_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from signal_diag.evaluation.runner import (
        _phase4_1_v6_benchmark_config,
        _run_phase4_1_v6_development_benchmark,
    )

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    manifest = load_dataset_manifest(PHASE4_1_MANIFEST)
    mismatched = _phase4_1_v6_benchmark_config(
        benchmark_id=_V6_DEV_ID,
        started_at_utc=_STARTED,
    ).model_copy(update={"prompt_version": "v0.2-s1-planner-5"})
    report = await _run_phase4_1_v6_development_benchmark(
        manifest,
        mismatched,
        tmp_path / "mismatch",
    )
    assert report.benchmark_status == "pending"
    assert {attempt.error_code for attempt in report.attempts} == {
        "invalid_configuration"
    }

    dest_parent = tmp_path / "exists"
    first = await _run_phase4_1_v6_development_benchmark(
        manifest,
        _phase4_1_v6_benchmark_config(
            benchmark_id=_V6_DEV_ID,
            started_at_utc=_STARTED,
        ),
        dest_parent,
    )
    assert first.config.benchmark_id == _V6_DEV_ID
    with pytest.raises(FileExistsError):
        await _run_phase4_1_v6_development_benchmark(
            manifest,
            _phase4_1_v6_benchmark_config(
                benchmark_id=_V6_DEV_ID,
                started_at_utc=_STARTED,
            ),
            dest_parent,
        )


@pytest.mark.asyncio
async def test_t199_official_requires_completed_meets_target_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from signal_diag.evaluation.runner import (
        _phase4_1_v6_benchmark_config,
        _run_phase4_1_v6_official_benchmark,
    )

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    manifest = load_dataset_manifest(PHASE4_1_MANIFEST)
    config = _phase4_1_v6_benchmark_config(
        benchmark_id=_V6_OFFICIAL_ID,
        started_at_utc=_STARTED,
    )
    missing = await _run_phase4_1_v6_official_benchmark(
        manifest,
        config,
        tmp_path / "missing",
        development_bundle=tmp_path / "no-such-bundle",
    )
    assert missing.benchmark_status == "pending"
    assert {attempt.error_code for attempt in missing.attempts} == {
        "invalid_configuration"
    }
    assert all(attempt.execution_path == "agent" for attempt in missing.attempts)

    below = _write_gate_metrics(
        tmp_path / "below",
        benchmark_status="completed",
        target_status="below_target",
    )
    blocked = await _run_phase4_1_v6_official_benchmark(
        manifest,
        config,
        tmp_path / "blocked",
        development_bundle=below,
    )
    assert blocked.benchmark_status == "pending"
    assert {attempt.error_code for attempt in blocked.attempts} == {
        "invalid_configuration"
    }


def test_t199_cli_defaults_canonical_v6_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from signal_diag.evaluation import __main__ as cli

    captured: dict[str, Any] = {}

    async def fake_dev(manifest: object, config: object, output_dir: Path) -> object:
        captured["dev"] = (manifest, config, output_dir)
        return type("R", (), {"benchmark_status": "pending"})()

    monkeypatch.setattr(cli, "_run_phase4_1_v6_development_benchmark", fake_dev)
    monkeypatch.setattr(
        cli,
        "load_dataset_manifest",
        lambda path: load_dataset_manifest(PHASE4_1_MANIFEST),
    )
    code = cli.main(
        [
            "run-real",
            "--campaign",
            "phase4.1-v6-development",
            "--output-dir",
            str(tmp_path),
        ]
    )
    assert code == 0
    _manifest, config, output_dir = captured["dev"]
    assert config.benchmark_id == _V6_DEV_ID
    assert output_dir == tmp_path
