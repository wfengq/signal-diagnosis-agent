"""Phase 4.1 planner v6 additive campaigns (T199)."""

from __future__ import annotations

import argparse
import inspect
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from signal_diag.agent.planner import (
    RealLLMPlanner,
    _Phase4V5RealLLMPlanner,
    _Phase4V6RealLLMPlanner,
)
from signal_diag.agent.prompts import _S1_PROMPT_V5, _S1_PROMPT_V6
from signal_diag.evaluation.dataset import load_dataset_manifest
from tests.evaluation.conftest import CANONICAL_MANIFEST, PHASE4_1_MANIFEST
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
    "phase4.2-v7-development",
    "phase4.2-v7-official",
    "phase4.3-v8-development",
    "phase4.3-v8-official",
)
_DEV_WARNING = "development split; not official held-out evidence"
_V6_DEV_BUNDLE = Path("docs/evaluations/phase4_1/development") / _V6_DEV_ID
_V6_HASH = "9be518167ec58f3806ae569e48929c37d1e526ac4ae0463a448dd622ec0f1ef1"


def _write_gate_metrics(
    path: Path,
    *,
    benchmark_status: str,
    target_status: str,
    prompt_version: str = "v0.2-s1-planner-6",
    prompt_sha256: str = _V6_HASH,
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
    (dest / "benchmark_manifest.json").write_text(
        json.dumps(
            {
                "config": {
                    "benchmark_id": _V6_DEV_ID,
                    "prompt_version": prompt_version,
                    "prompt_sha256": prompt_sha256,
                    "dataset_id": "s1-distortion-synthetic",
                    "dataset_version": "1.1.0",
                    "rule_profile_id": "profile_s1_distortion",
                    "rule_profile_version": "1.0.0-demo",
                    "provider": "deepseek",
                    "model": "deepseek-v4-flash",
                }
            }
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
    assert development.dataset_id == "s1-distortion-synthetic"
    assert development.dataset_version == "1.1.0"
    assert development.rule_profile_id == "profile_s1_distortion"
    assert development.rule_profile_version == "1.0.0-demo"
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
    assert type(planner) is _Phase4V6RealLLMPlanner
    assert type(planner) is not RealLLMPlanner
    assert type(planner) is not _Phase4V5RealLLMPlanner
    assert planner._prompt_spec is _S1_PROMPT_V6
    from signal_diag.evaluation.runner import (
        _PHASE4_1_V6_DEV_BUNDLE,
        _run_phase4_1_v6_official_benchmark,
    )

    assert expected_hash == _V6_HASH
    assert _PHASE4_1_V6_DEV_BUNDLE == _V6_DEV_BUNDLE
    default = inspect.signature(
        _run_phase4_1_v6_official_benchmark
    ).parameters["development_bundle"].default
    assert default in (None, _V6_DEV_BUNDLE)


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
    assert _DEV_WARNING not in official.warnings
    with pytest.raises(FileExistsError):
        await _run_phase4_1_v6_official_benchmark(
            manifest,
            _phase4_1_v6_benchmark_config(
                benchmark_id=_V6_OFFICIAL_ID,
                started_at_utc=_STARTED,
            ),
            tmp_path / "official",
            development_bundle=gate,
        )


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
    assert report.config.prompt_version == "v0.2-s1-planner-5"

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

    hashed = _write_gate_metrics(
        tmp_path / "hash",
        benchmark_status="completed",
        target_status="meets_target",
        prompt_sha256="a" * 64,
    )
    hash_blocked = await _run_phase4_1_v6_official_benchmark(
        manifest,
        config,
        tmp_path / "hash-blocked",
        development_bundle=hashed,
    )
    assert hash_blocked.benchmark_status == "pending"
    assert {attempt.error_code for attempt in hash_blocked.attempts} == {
        "invalid_configuration"
    }


@pytest.mark.asyncio
async def test_t199_rejects_conflicting_manifest_without_rewrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from signal_diag.evaluation.runner import (
        _phase4_1_v6_benchmark_config,
        _run_phase4_1_v6_development_benchmark,
    )

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    report = await _run_phase4_1_v6_development_benchmark(
        load_dataset_manifest(CANONICAL_MANIFEST),
        _phase4_1_v6_benchmark_config(
            benchmark_id=_V6_DEV_ID,
            started_at_utc=_STARTED,
        ),
        tmp_path / "conflict",
    )
    assert report.benchmark_status == "pending"
    assert {attempt.error_code for attempt in report.attempts} == {
        "invalid_configuration"
    }
    assert report.config.dataset_version == "1.1.0"
    assert report.config.prompt_version == "v0.2-s1-planner-6"


def test_t199_preflight_rejects_dataset_and_profile_mismatch() -> None:
    from signal_diag.evaluation.runner import (
        _phase4_1_v6_benchmark_config,
        _preflight_phase4_1_v6,
        _PreflightFailure,
    )

    manifest = load_dataset_manifest(PHASE4_1_MANIFEST)
    base = _phase4_1_v6_benchmark_config(
        benchmark_id=_V6_DEV_ID,
        started_at_utc=_STARTED,
    )
    for update in (
        {"dataset_id": "other-dataset"},
        {"dataset_version": "1.0.0"},
        {"rule_profile_id": "other_profile"},
        {"rule_profile_version": "9.9.9"},
    ):
        mismatched = base.model_copy(update=update)
        with pytest.raises(_PreflightFailure) as caught:
            _preflight_phase4_1_v6(manifest, mismatched, client_factory=object)
        assert caught.value.code == "invalid_configuration"
        field, value = next(iter(update.items()))
        assert getattr(mismatched, field) == value


def test_t199_cli_defaults_canonical_v6_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from signal_diag.evaluation import __main__ as cli

    captured: dict[str, Any] = {}

    async def fake_dev(
        manifest: object,
        config: object,
        output_dir: Path,
        **kwargs: object,
    ) -> object:
        captured["dev"] = (config, output_dir)
        return SimpleNamespace(benchmark_status="pending")

    async def fake_official(
        manifest: object,
        config: object,
        output_dir: Path,
        **kwargs: object,
    ) -> object:
        captured["official"] = (config, output_dir, kwargs)
        return SimpleNamespace(benchmark_status="pending")

    monkeypatch.setattr(cli, "_run_phase4_1_v6_development_benchmark", fake_dev)
    monkeypatch.setattr(cli, "_run_phase4_1_v6_official_benchmark", fake_official)
    monkeypatch.setattr(
        cli,
        "load_dataset_manifest",
        lambda path: load_dataset_manifest(PHASE4_1_MANIFEST),
    )
    assert (
        cli.main(
            [
                "run-real",
                "--campaign",
                "phase4.1-v6-development",
                "--output-dir",
                str(tmp_path / "dev"),
            ]
        )
        == 0
    )
    dev_config, dev_out = captured["dev"]
    assert dev_config.benchmark_id == _V6_DEV_ID
    assert dev_out == tmp_path / "dev"

    assert (
        cli.main(
            [
                "run-real",
                "--campaign",
                "phase4.1-v6-development",
                "--benchmark-id",
                "bench_custom_v6_dev",
                "--output-dir",
                str(tmp_path / "custom"),
            ]
        )
        == 0
    )
    custom_config, _ = captured["dev"]
    assert custom_config.benchmark_id == "bench_custom_v6_dev"

    assert (
        cli.main(
            [
                "run-real",
                "--campaign",
                "phase4.1-v6-official",
                "--output-dir",
                str(tmp_path / "official"),
            ]
        )
        == 0
    )
    official_config, official_out, official_kwargs = captured["official"]
    assert official_config.benchmark_id == _V6_OFFICIAL_ID
    assert official_out == tmp_path / "official"
    bundle = official_kwargs.get("development_bundle")
    assert bundle in (None, _V6_DEV_BUNDLE)
