"""Phase 4.3 planner v8 additive campaigns (T209, T214)."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from signal_diag.agent.planner import (
    RealLLMPlanner,
    _Phase4V4RealLLMPlanner,
    _Phase4V5RealLLMPlanner,
    _Phase4V6RealLLMPlanner,
    _Phase4V7RealLLMPlanner,
)
from signal_diag.agent.prompts import (
    _S1_PROMPT_V4,
    _S1_PROMPT_V5,
    _S1_PROMPT_V6,
    _S1_PROMPT_V7,
    _S1_PROMPT_V8,
)
from signal_diag.evaluation.dataset import (
    _opaque_evaluation_signal_id,
    load_dataset_manifest,
)
from signal_diag.evaluation.reporting import DATA_FILES
from tests.evaluation.conftest import PHASE4_1_MANIFEST
from tests.evaluation.test_phase4_1_runner import _fingerprint
from tests.evaluation.test_phase4_2_v7_runner import PHASE4_2_MANIFEST
from tests.evaluation.test_runner import FORBIDDEN_CREDENTIAL_TOKENS

_STARTED = datetime(2026, 8, 30, 21, 0, tzinfo=UTC)
_V8_DEV_ID = "bench_phase4_3_dev_v8_v12_gate4"
_V8_OFFICIAL_ID = "bench_official_s1_v12_planner8_gate4"
_V7_DEV_ID = "bench_phase4_2_dev_v7_v12_gate3"
_V6_DEV_ID = "bench_phase4_1_dev_v6_gate2"
_FROZEN_V8_SHA256 = (
    "bf5355ef514574bd2ec4dfda0b3afd2e9810d6031fd1bb9fc13c54fc9fcb8b7e"
)
_FROZEN_V7_SHA256 = (
    "008b0fee78a83ada11140b42596d0f0e1abed27e641d5107e53ba759db6bc82a"
)
_V8_CAMPAIGNS = (
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
_V8_DEV_BUNDLE = Path("docs/evaluations/phase4_3/development") / _V8_DEV_ID
_V7_DEV_BUNDLE = Path("docs/evaluations/phase4_2/development") / _V7_DEV_ID
_IDENTITY_FIELDS = (
    "benchmark_id",
    "prompt_version",
    "prompt_sha256",
    "dataset_id",
    "dataset_version",
    "rule_profile_id",
    "rule_profile_version",
    "provider",
    "model",
    "repetitions",
)


def _v8_hash() -> str:
    return sha256(_S1_PROMPT_V8.system_prompt.encode()).hexdigest()


def _expected_v8_config_fields() -> dict[str, Any]:
    return {
        "benchmark_id": _V8_DEV_ID,
        "prompt_version": "v0.2-s1-planner-8",
        "prompt_sha256": _v8_hash(),
        "dataset_id": "s1-distortion-synthetic",
        "dataset_version": "1.2.0",
        "rule_profile_id": "profile_s1_distortion",
        "rule_profile_version": "1.0.0-demo",
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "repetitions": 5,
    }


def _write_checksums(dest: Path) -> None:
    lines = []
    for name in sorted(DATA_FILES):
        path = dest / name
        if not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {name}\n")
    (dest / "checksums.sha256").write_text("".join(lines), encoding="utf-8")


def _write_v8_gate_bundle(
    path: Path,
    *,
    benchmark_status: str = "completed",
    target_status: str = "meets_target",
    config_overlay: dict[str, Any] | None = None,
    omit_metrics: bool = False,
    omit_manifest: bool = False,
    omit_checksums: bool = False,
    metrics_text: str | None = None,
    manifest_text: str | None = None,
    metrics_bytes: bytes | None = None,
    manifest_bytes: bytes | None = None,
    checksums_text: str | None = None,
    corrupt_checksums: bool = False,
) -> Path:
    dest = path / _V8_DEV_ID
    dest.mkdir(parents=True)
    if not omit_metrics:
        if metrics_bytes is not None:
            (dest / "metrics.json").write_bytes(metrics_bytes)
        else:
            if metrics_text is None:
                metrics_text = (
                    json.dumps(
                        {
                            "benchmark_status": benchmark_status,
                            "target_status": target_status,
                        },
                        indent=2,
                    )
                    + "\n"
                )
            (dest / "metrics.json").write_text(metrics_text, encoding="utf-8")
    if not omit_manifest:
        if manifest_bytes is not None:
            (dest / "benchmark_manifest.json").write_bytes(manifest_bytes)
        else:
            if manifest_text is None:
                recorded = dict(_expected_v8_config_fields())
                if config_overlay:
                    recorded.update(config_overlay)
                manifest_text = json.dumps({"config": recorded}) + "\n"
            (dest / "benchmark_manifest.json").write_text(
                manifest_text, encoding="utf-8"
            )
    (dest / "runs.jsonl").write_text("", encoding="utf-8")
    (dest / "case_summary.csv").write_text("x\n", encoding="utf-8")
    (dest / "report.md").write_text("# report\n", encoding="utf-8")
    if not omit_checksums:
        if checksums_text is not None:
            (dest / "checksums.sha256").write_text(checksums_text, encoding="utf-8")
        else:
            _write_checksums(dest)
            if corrupt_checksums:
                (dest / "checksums.sha256").write_text(
                    "0" * 64 + "  metrics.json\n",
                    encoding="utf-8",
                )
    return dest


def _stub_client() -> object:
    return type(
        "StubClient",
        (),
        {"chat": type("Chat", (), {"completions": object()})()},
    )()


def _campaign_action(parser: argparse.ArgumentParser) -> argparse.Action:
    real = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    ).choices["run-real"]
    return next(
        action for action in real._actions if "--campaign" in action.option_strings
    )


def test_t209_v7_builder_constructs_private_v7_planner() -> None:
    from signal_diag.evaluation.runner import (
        _build_official_planner,
        _build_phase4_1_planner,
        _build_phase4_1_v6_planner,
        _build_phase4_2_v7_planner,
        _official_benchmark_config,
        _phase4_1_benchmark_config,
        _phase4_1_v6_benchmark_config,
        _phase4_2_v7_benchmark_config,
    )

    stub = _stub_client()
    v4 = _build_official_planner(stub)
    v5 = _build_phase4_1_planner(stub)
    v6 = _build_phase4_1_v6_planner(stub)
    v7 = _build_phase4_2_v7_planner(stub)
    assert type(v4) is _Phase4V4RealLLMPlanner
    assert type(v5) is _Phase4V5RealLLMPlanner
    assert type(v6) is _Phase4V6RealLLMPlanner
    assert type(v7) is _Phase4V7RealLLMPlanner
    assert type(v7) is not RealLLMPlanner
    assert v4._prompt_spec is _S1_PROMPT_V4
    assert v5._prompt_spec is _S1_PROMPT_V5
    assert v6._prompt_spec is _S1_PROMPT_V6
    assert v7._prompt_spec is _S1_PROMPT_V7
    assert v7._prompt_spec is not _S1_PROMPT_V8

    v4_config = _official_benchmark_config(
        benchmark_id="bench_phase4_legacy_v4",
        started_at_utc=_STARTED,
    )
    v5_config = _phase4_1_benchmark_config(
        benchmark_id="bench_phase4_1_dev_v5_gate1",
        started_at_utc=_STARTED,
    )
    v6_config = _phase4_1_v6_benchmark_config(
        benchmark_id=_V6_DEV_ID,
        started_at_utc=_STARTED,
    )
    v7_config = _phase4_2_v7_benchmark_config(
        benchmark_id=_V7_DEV_ID,
        started_at_utc=_STARTED,
    )
    assert v4_config.prompt_version == "v0.2-s1-planner-4"
    assert v4_config.dataset_version == "1.0.0"
    assert v5_config.prompt_version == "v0.2-s1-planner-5"
    assert v5_config.dataset_version == "1.1.0"
    assert v6_config.prompt_version == "v0.2-s1-planner-6"
    assert v6_config.dataset_version == "1.1.0"
    assert v7_config.prompt_version == "v0.2-s1-planner-7"
    assert v7_config.dataset_version == "1.2.0"
    assert v7_config.prompt_sha256 == _FROZEN_V7_SHA256
    assert v7_config.prompt_sha256 != _FROZEN_V8_SHA256

    committed = json.loads(
        (_V7_DEV_BUNDLE / "benchmark_manifest.json").read_text(encoding="utf-8")
    )
    assert committed["config"]["prompt_version"] == "v0.2-s1-planner-7"
    assert committed["config"]["prompt_sha256"] == _FROZEN_V7_SHA256
    assert committed["config"]["dataset_version"] == "1.2.0"
    assert committed["config"]["benchmark_id"] == _V7_DEV_ID


def test_t214_campaign_choices_are_additive() -> None:
    from signal_diag.evaluation.__main__ import build_parser

    parser = build_parser()
    campaign = _campaign_action(parser)
    assert tuple(campaign.choices) == _V8_CAMPAIGNS
    assert campaign.default == "phase4"
    help_text = parser.format_help().lower()
    real_help = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    ).choices["run-real"].format_help().lower()
    for token in FORBIDDEN_CREDENTIAL_TOKENS:
        assert token not in help_text
        assert token not in real_help


def test_t214_v8_campaigns_use_single_runner_registration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parser choices, canonical IDs, and CLI dispatch must share one v8 registry."""
    from signal_diag.evaluation import __main__ as cli
    from signal_diag.evaluation import runner as runner_mod
    from signal_diag.evaluation.__main__ import build_parser

    assert not hasattr(cli, "_V8_DEV_ID")
    assert not hasattr(cli, "_V8_OFFICIAL_ID")
    assert not hasattr(cli, "_PHASE4_3_V8_DEV_BENCHMARK_ID")
    assert not hasattr(cli, "_PHASE4_3_V8_OFFICIAL_BENCHMARK_ID")

    registry = runner_mod._PHASE4_3_V8_CAMPAIGNS
    assert dict(registry) and tuple(registry) == (
        "phase4.3-v8-development",
        "phase4.3-v8-official",
    )
    assert {
        name: route.canonical_id for name, route in registry.items()
    } == {
        "phase4.3-v8-development": "bench_phase4_3_dev_v8_v12_gate4",
        "phase4.3-v8-official": "bench_official_s1_v12_planner8_gate4",
    }
    development = registry["phase4.3-v8-development"]
    official = registry["phase4.3-v8-official"]
    assert development.canonical_id == runner_mod._PHASE4_3_V8_DEV_BENCHMARK_ID
    assert official.canonical_id == runner_mod._PHASE4_3_V8_OFFICIAL_BENCHMARK_ID
    assert development.config_builder is runner_mod._phase4_3_v8_benchmark_config
    assert official.config_builder is runner_mod._phase4_3_v8_benchmark_config
    assert development.manifest_path is runner_mod._phase4_2_manifest_path
    assert official.manifest_path is runner_mod._phase4_2_manifest_path
    assert development.score_split == "development"
    assert official.score_split == "held_out"
    assert development.extra_warnings == (runner_mod._PHASE4_1_DEV_WARNING,)
    assert official.extra_warnings == ()
    assert development.require_canonical_id is True
    assert official.require_canonical_id is True
    assert development.runner_name == "_run_phase4_3_v8_development_benchmark"
    assert official.runner_name == "_run_phase4_3_v8_official_benchmark"
    assert getattr(runner_mod, development.runner_name) is (
        runner_mod._run_phase4_3_v8_development_benchmark
    )
    assert getattr(runner_mod, official.runner_name) is (
        runner_mod._run_phase4_3_v8_official_benchmark
    )

    parser = build_parser()
    campaign = _campaign_action(parser)
    assert tuple(campaign.choices)[-2:] == tuple(registry)

    monkeypatch.setitem(registry, "phase4.3-v8-probe", development)
    probe_parser = build_parser()
    probe_campaign = _campaign_action(probe_parser)
    assert "phase4.3-v8-probe" in tuple(probe_campaign.choices)

    captured: dict[str, str] = {}

    async def fake_dev(
        manifest: object,
        config: object,
        output_dir: Path,
        **kwargs: object,
    ) -> object:
        captured["benchmark_id"] = config.benchmark_id  # type: ignore[attr-defined]
        return SimpleNamespace(benchmark_status="pending")

    monkeypatch.setattr(
        runner_mod, "_run_phase4_3_v8_development_benchmark", fake_dev
    )
    monkeypatch.setitem(
        registry,
        "phase4.3-v8-development",
        replace(development, canonical_id="bench_probe_silent_v8_route"),
    )
    assert (
        cli.main(
            [
                "run-real",
                "--campaign",
                "phase4.3-v8-development",
                "--output-dir",
                str(tmp_path / "probe"),
            ]
        )
        == 0
    )
    assert captured["benchmark_id"] == "bench_probe_silent_v8_route"


def test_t214_v8_config_and_canonical_ids() -> None:
    from signal_diag.evaluation.runner import (
        _PHASE4_3_V8_DEV_BUNDLE,
        _build_phase4_3_v8_planner,
        _phase4_3_v8_benchmark_config,
        _phase4_3_v8_prompt_sha256,
        _run_phase4_3_v8_official_benchmark,
        _slot_schedule_for_split,
    )

    expected_hash = _v8_hash()
    assert expected_hash == _FROZEN_V8_SHA256
    development = _phase4_3_v8_benchmark_config(
        benchmark_id=_V8_DEV_ID,
        started_at_utc=_STARTED,
    )
    official = _phase4_3_v8_benchmark_config(
        benchmark_id=_V8_OFFICIAL_ID,
        started_at_utc=datetime(2026, 8, 31, 9, 0, tzinfo=UTC),
    )
    assert development.prompt_version == "v0.2-s1-planner-8"
    assert development.dataset_id == "s1-distortion-synthetic"
    assert development.dataset_version == "1.2.0"
    assert development.rule_profile_id == "profile_s1_distortion"
    assert development.rule_profile_version == "1.0.0-demo"
    assert development.provider == "deepseek"
    assert development.model == "deepseek-v4-flash"
    assert development.repetitions == 5
    assert development.max_concurrency == 1
    assert development.prompt_sha256 == expected_hash
    assert _phase4_3_v8_prompt_sha256() == expected_hash
    assert _fingerprint(development) == _fingerprint(official)
    stub = _stub_client()
    planner = _build_phase4_3_v8_planner(stub)
    assert type(planner) is RealLLMPlanner
    assert type(planner) is not _Phase4V7RealLLMPlanner
    assert planner._prompt_spec is _S1_PROMPT_V8
    assert _PHASE4_3_V8_DEV_BUNDLE == _V8_DEV_BUNDLE
    default = inspect.signature(
        _run_phase4_3_v8_official_benchmark
    ).parameters["development_bundle"].default
    assert default in (None, _V8_DEV_BUNDLE)

    manifest = load_dataset_manifest(PHASE4_2_MANIFEST)
    assert manifest.version == "1.2.0"
    assert len(_slot_schedule_for_split(manifest, development, "development")) == 40
    assert len(_slot_schedule_for_split(manifest, official, "held_out")) == 80


def test_t214_preflight_rejects_dataset_and_profile_mismatch() -> None:
    from signal_diag.evaluation.runner import (
        _phase4_3_v8_benchmark_config,
        _preflight_phase4_3_v8,
        _PreflightFailure,
    )

    manifest = load_dataset_manifest(PHASE4_2_MANIFEST)
    base = _phase4_3_v8_benchmark_config(
        benchmark_id=_V8_DEV_ID,
        started_at_utc=_STARTED,
    )
    for update in (
        {"dataset_id": "other-dataset"},
        {"dataset_version": "1.1.0"},
        {"rule_profile_id": "other_profile"},
        {"rule_profile_version": "9.9.9"},
        {"prompt_sha256": "a" * 64},
        {"prompt_version": "v0.2-s1-planner-7"},
    ):
        mismatched = base.model_copy(update=update)
        with pytest.raises(_PreflightFailure) as caught:
            _preflight_phase4_3_v8(manifest, mismatched, client_factory=object)
        assert caught.value.code == "invalid_configuration"


@pytest.mark.asyncio
async def test_t214_v8_runners_pass_opaque_signal_id_factory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from signal_diag.evaluation import runner as runner_mod

    captured: dict[str, Any] = {}

    async def fake_split(*args: object, **kwargs: object) -> object:
        captured[str(kwargs["score_split"])] = kwargs
        return SimpleNamespace(benchmark_status="pending", attempts=())

    monkeypatch.setattr(runner_mod, "_run_real_benchmark_for_split", fake_split)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    manifest = load_dataset_manifest(PHASE4_2_MANIFEST)
    development = runner_mod._phase4_3_v8_benchmark_config(
        benchmark_id=_V8_DEV_ID,
        started_at_utc=_STARTED,
    )
    official = runner_mod._phase4_3_v8_benchmark_config(
        benchmark_id=_V8_OFFICIAL_ID,
        started_at_utc=_STARTED,
    )
    gate = _write_v8_gate_bundle(tmp_path / "accepted")
    await runner_mod._run_phase4_3_v8_development_benchmark(
        manifest, development, tmp_path / "dev"
    )
    await runner_mod._run_phase4_3_v8_official_benchmark(
        manifest,
        official,
        tmp_path / "official",
        development_bundle=gate,
    )
    for split in ("development", "held_out"):
        kwargs = captured[split]
        assert kwargs["planner_builder"] is runner_mod._build_phase4_3_v8_planner
        factory = kwargs["signal_id_factory"]
        assert factory is not None
        case = next(item for item in manifest.cases if item.split == split)
        assert factory(case) == _opaque_evaluation_signal_id(
            manifest.dataset_id, manifest.version, case.case_id
        )


def test_t214_cli_defaults_canonical_v8_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from signal_diag.evaluation import __main__ as cli
    from signal_diag.evaluation import runner as runner_mod

    captured: dict[str, Any] = {}

    async def fake_dev(
        manifest: object,
        config: object,
        output_dir: Path,
        **kwargs: object,
    ) -> object:
        captured["dev"] = (manifest, config, output_dir)
        return SimpleNamespace(benchmark_status="pending")

    async def fake_official(
        manifest: object,
        config: object,
        output_dir: Path,
        **kwargs: object,
    ) -> object:
        captured["official"] = (manifest, config, output_dir, kwargs)
        return SimpleNamespace(benchmark_status="pending")

    monkeypatch.setattr(
        runner_mod, "_run_phase4_3_v8_development_benchmark", fake_dev
    )
    monkeypatch.setattr(
        runner_mod, "_run_phase4_3_v8_official_benchmark", fake_official
    )
    assert (
        cli.main(
            [
                "run-real",
                "--campaign",
                "phase4.3-v8-development",
                "--output-dir",
                str(tmp_path / "dev"),
            ]
        )
        == 0
    )
    dev_manifest, dev_config, dev_out = captured["dev"]
    assert dev_config.benchmark_id == _V8_DEV_ID
    assert dev_config.dataset_version == "1.2.0"
    assert dev_config.prompt_version == "v0.2-s1-planner-8"
    assert dev_manifest.version == "1.2.0"
    assert dev_out == tmp_path / "dev"

    assert (
        cli.main(
            [
                "run-real",
                "--campaign",
                "phase4.3-v8-official",
                "--output-dir",
                str(tmp_path / "official"),
            ]
        )
        == 0
    )
    official_manifest, official_config, official_out, official_kwargs = captured[
        "official"
    ]
    assert official_config.benchmark_id == _V8_OFFICIAL_ID
    assert official_config.dataset_version == "1.2.0"
    assert official_manifest.version == "1.2.0"
    assert official_out == tmp_path / "official"
    bundle = official_kwargs.get("development_bundle")
    assert bundle in (None, _V8_DEV_BUNDLE)


@pytest.mark.parametrize(
    "campaign", ("phase4.3-v8-development", "phase4.3-v8-official")
)
def test_t214_acceptance_campaigns_reject_non_canonical_benchmark_id(
    campaign: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from signal_diag.evaluation import __main__ as cli
    from signal_diag.evaluation import runner as runner_mod

    called: list[str] = []

    async def fake_dev(*args: object, **kwargs: object) -> object:
        called.append("dev")
        raise AssertionError("non-canonical ID must not schedule development")

    async def fake_official(*args: object, **kwargs: object) -> object:
        called.append("official")
        raise AssertionError("non-canonical ID must not schedule official")

    monkeypatch.setattr(
        runner_mod, "_run_phase4_3_v8_development_benchmark", fake_dev
    )
    monkeypatch.setattr(
        runner_mod, "_run_phase4_3_v8_official_benchmark", fake_official
    )
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    output = tmp_path / campaign
    assert (
        cli.main(
            [
                "run-real",
                "--campaign",
                campaign,
                "--benchmark-id",
                "bench_custom_v8_exploratory",
                "--output-dir",
                str(output),
            ]
        )
        == 0
    )
    assert called == []
    dest = output / "bench_custom_v8_exploratory"
    metrics = json.loads((dest / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["benchmark_status"] == "pending"
    codes: set[str | None] = set()
    for line in (dest / "runs.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        artifact = json.loads(line)
        for attempt in artifact.get("attempts", ()):
            codes.add(attempt.get("error_code"))
    assert codes == {"invalid_configuration"}
    report_text = (dest / "report.md").read_text(encoding="utf-8").lower()
    for token in FORBIDDEN_CREDENTIAL_TOKENS:
        assert token not in report_text


def test_t214_cli_does_not_redirect_v7_onto_v8(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from signal_diag.evaluation import __main__ as cli
    from signal_diag.evaluation import runner as runner_mod

    captured: dict[str, str] = {}

    async def fake_v7_dev(*args: object, **kwargs: object) -> object:
        captured["hit"] = "v7"
        return SimpleNamespace(benchmark_status="pending")

    async def fake_v8_dev(*args: object, **kwargs: object) -> object:
        captured["hit"] = "v8"
        return SimpleNamespace(benchmark_status="pending")

    monkeypatch.setattr(
        runner_mod, "_run_phase4_2_v7_development_benchmark", fake_v7_dev
    )
    monkeypatch.setattr(
        runner_mod, "_run_phase4_3_v8_development_benchmark", fake_v8_dev
    )
    assert (
        cli.main(
            [
                "run-real",
                "--campaign",
                "phase4.2-v7-development",
                "--output-dir",
                str(tmp_path / "v7"),
            ]
        )
        == 0
    )
    assert captured["hit"] == "v7"


def _gate_expected_config():
    from signal_diag.evaluation.runner import _phase4_3_v8_benchmark_config

    return _phase4_3_v8_benchmark_config(
        benchmark_id=_V8_DEV_ID,
        started_at_utc=_STARTED,
    )


_GATE_DEFECTS = (
    "missing_metrics",
    "missing_manifest",
    "unreadable_metrics",
    "unreadable_manifest",
    "invalid_metrics_json",
    "invalid_manifest_json",
    "wrong_status",
    "wrong_target",
    "missing_config",
    "missing_checksums",
    "invalid_checksums",
    "mismatched_checksums",
    "changed_v8_hash",
    *tuple(f"missing_{field}" for field in _IDENTITY_FIELDS),
    *tuple(f"mismatch_{field}" for field in _IDENTITY_FIELDS),
)


def _defect_bundle_kwargs(defect: str) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if defect == "missing_metrics":
        kwargs["omit_metrics"] = True
    elif defect == "missing_manifest":
        kwargs["omit_manifest"] = True
    elif defect == "unreadable_metrics":
        kwargs["metrics_bytes"] = b"\xff\xfe"
    elif defect == "unreadable_manifest":
        kwargs["manifest_bytes"] = b"\xff\xfe"
    elif defect == "invalid_metrics_json":
        kwargs["metrics_text"] = "{"
    elif defect == "invalid_manifest_json":
        kwargs["manifest_text"] = "{"
    elif defect == "wrong_status":
        kwargs["benchmark_status"] = "incomplete"
    elif defect == "wrong_target":
        kwargs["target_status"] = "below_target"
    elif defect == "missing_config":
        kwargs["manifest_text"] = json.dumps({"not_config": {}}) + "\n"
    elif defect == "missing_checksums":
        kwargs["omit_checksums"] = True
    elif defect == "invalid_checksums":
        kwargs["checksums_text"] = "not-a-checksum\n"
    elif defect == "mismatched_checksums":
        kwargs["corrupt_checksums"] = True
    elif defect == "changed_v8_hash":
        kwargs["config_overlay"] = {"prompt_sha256": "a" * 64}
    elif defect.startswith("missing_"):
        field = defect.removeprefix("missing_")
        recorded = dict(_expected_v8_config_fields())
        del recorded[field]
        kwargs["manifest_text"] = json.dumps({"config": recorded}) + "\n"
    elif defect.startswith("mismatch_"):
        field = defect.removeprefix("mismatch_")
        overlay: dict[str, Any] = {
            "benchmark_id": "bench_wrong_identity",
            "prompt_version": "v0.2-s1-planner-7",
            "prompt_sha256": "a" * 64,
            "dataset_id": "other-dataset",
            "dataset_version": "1.1.0",
            "rule_profile_id": "profile_other",
            "rule_profile_version": "9.9.9",
            "provider": "other-provider",
            "model": "other-model",
            "repetitions": 1,
        }
        kwargs["config_overlay"] = {field: overlay[field]}
    return kwargs


@pytest.mark.parametrize("defect", _GATE_DEFECTS)
def test_t214_identity_complete_gate_rejects_defects(
    defect: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from signal_diag.evaluation.runner import (
        _PreflightFailure,
        _require_phase4_3_v8_development_gate,
    )

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    bundle = _write_v8_gate_bundle(tmp_path / defect, **_defect_bundle_kwargs(defect))
    with pytest.raises(_PreflightFailure) as caught:
        _require_phase4_3_v8_development_gate(bundle, _gate_expected_config())
    assert caught.value.code == "invalid_configuration"


@pytest.mark.parametrize("defect", _GATE_DEFECTS)
@pytest.mark.asyncio
async def test_t214_official_rejects_defects_before_credentials(
    defect: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from signal_diag.evaluation import runner as runner_mod

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    import_calls: list[str] = []
    client_calls: list[str] = []
    split_calls: list[str] = []
    lookups: list[str] = []
    gate_finished = False

    def boom_sdk_versions() -> dict[str, str]:
        import_calls.append("openai")
        raise AssertionError("must not import openai before gate failure")

    def boom_import() -> object:
        import_calls.append("openai")
        raise AssertionError("must not import openai before gate failure")

    def boom_client() -> object:
        client_calls.append("client")
        raise AssertionError("must not create client before gate failure")

    original_get = runner_mod.os.environ.get

    def tracing_get(key: str, default: object = None) -> object:
        if key == "DEEPSEEK_API_KEY":
            lookups.append(key)
        return original_get(key, default)

    original_gate = runner_mod._require_phase4_3_v8_development_gate

    def tracing_gate(*args: object, **kwargs: object) -> None:
        nonlocal gate_finished
        try:
            original_gate(*args, **kwargs)
        finally:
            gate_finished = True

    original_schedule = runner_mod._slot_schedule_for_split

    def tracing_schedule(
        manifest: object,
        config: object,
        score_split: object,
    ) -> object:
        if score_split == "held_out" and not gate_finished:
            raise AssertionError(
                "must not build held-out slot schedule before official gate"
            )
        return original_schedule(manifest, config, score_split)

    original_split = runner_mod._run_real_benchmark_for_split

    async def tracing_split(*args: object, **kwargs: object) -> object:
        split_calls.append(str(kwargs.get("score_split")))
        return await original_split(*args, **kwargs)

    monkeypatch.setattr(runner_mod, "_official_sdk_versions", boom_sdk_versions)
    monkeypatch.setattr(runner_mod, "_import_openai", boom_import)
    monkeypatch.setattr(runner_mod.os.environ, "get", tracing_get)
    monkeypatch.setattr(
        runner_mod, "_require_phase4_3_v8_development_gate", tracing_gate
    )
    monkeypatch.setattr(runner_mod, "_slot_schedule_for_split", tracing_schedule)
    monkeypatch.setattr(runner_mod, "_run_real_benchmark_for_split", tracing_split)

    manifest = load_dataset_manifest(PHASE4_2_MANIFEST)
    config = runner_mod._phase4_3_v8_benchmark_config(
        benchmark_id=_V8_OFFICIAL_ID,
        started_at_utc=_STARTED,
    )
    bundle = _write_v8_gate_bundle(tmp_path / defect, **_defect_bundle_kwargs(defect))
    report = await runner_mod._run_phase4_3_v8_official_benchmark(
        manifest,
        config,
        tmp_path / "blocked",
        development_bundle=bundle,
        client_factory=boom_client,
        import_openai=boom_import,
    )
    assert report.benchmark_status == "pending"
    assert {attempt.error_code for attempt in report.attempts} == {
        "invalid_configuration"
    }
    assert all(attempt.execution_path == "agent" for attempt in report.attempts)
    assert lookups == []
    assert import_calls == []
    assert client_calls == []
    assert split_calls == []
    assert gate_finished is True
    assert len(report.attempts) == 80


@pytest.mark.asyncio
async def test_t214_rejects_conflicting_manifest_without_rewrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from signal_diag.evaluation.runner import (
        _phase4_3_v8_benchmark_config,
        _run_phase4_3_v8_development_benchmark,
    )

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    report = await _run_phase4_3_v8_development_benchmark(
        load_dataset_manifest(PHASE4_1_MANIFEST),
        _phase4_3_v8_benchmark_config(
            benchmark_id=_V8_DEV_ID,
            started_at_utc=_STARTED,
        ),
        tmp_path / "conflict",
    )
    assert report.benchmark_status == "pending"
    assert {attempt.error_code for attempt in report.attempts} == {
        "invalid_configuration"
    }
    assert report.config.dataset_version == "1.2.0"
    assert report.config.prompt_version == "v0.2-s1-planner-8"
    assert report.config.benchmark_id == _V8_DEV_ID
