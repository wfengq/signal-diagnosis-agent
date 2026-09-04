"""Phase 4.3.1 planner v8.1 runner identity and gate5 campaigns (T216, T222)."""

from __future__ import annotations

import argparse
import hashlib
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
    _Phase4V8_1RealLLMPlanner,
    _Phase4V8RealLLMPlanner,
)
from signal_diag.agent.prompts import (
    _S1_PROMPT_V4,
    _S1_PROMPT_V5,
    _S1_PROMPT_V6,
    _S1_PROMPT_V7,
    _S1_PROMPT_V8,
    _S1_PROMPT_V8_1,
)
from signal_diag.evaluation.dataset import (
    _opaque_evaluation_signal_id,
    load_dataset_manifest,
)
from signal_diag.evaluation.reporting import DATA_FILES
from tests.evaluation.conftest import PHASE4_1_MANIFEST
from tests.evaluation.test_phase4_2_v7_runner import PHASE4_2_MANIFEST
from tests.evaluation.test_runner import FORBIDDEN_CREDENTIAL_TOKENS, _fingerprint

_STARTED = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
_V8_DEV_ID = "bench_phase4_3_dev_v8_v12_gate4"
_V8_OFFICIAL_ID = "bench_official_s1_v12_planner8_gate4"
_V81_DEV_ID = "bench_phase4_3_1_dev_v8_1_v12_gate5"
_V81_OFFICIAL_ID = "bench_official_s1_v12_planner8_1_gate5"
_FROZEN_V8_SHA256 = (
    "bf5355ef514574bd2ec4dfda0b3afd2e9810d6031fd1bb9fc13c54fc9fcb8b7e"
)
_FROZEN_V81_SHA256 = (
    "f2f0a81cc8f36f0301ee67c43e692886e86f9aa9136adeea4d592707133423ca"
)
_V81_DEV_BUNDLE = (
    Path("docs/evaluations/phase4_3_1/development") / _V81_DEV_ID
)
_V81_CAMPAIGNS = (
    "phase4",
    "phase4.1-development",
    "phase4.1-official",
    "phase4.1-v6-development",
    "phase4.1-v6-official",
    "phase4.2-v7-development",
    "phase4.2-v7-official",
    "phase4.3-v8-development",
    "phase4.3-v8-official",
    "phase4.3.1-v8.1-development",
    "phase4.3.1-v8.1-official",
)
_V81_IDENTITY_FIELDS = (
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
    "sdk_versions",
)


def _v8_hash() -> str:
    return sha256(_S1_PROMPT_V8.system_prompt.encode()).hexdigest()


def _v81_hash() -> str:
    return sha256(_S1_PROMPT_V8_1.system_prompt.encode()).hexdigest()


def _stub_client() -> object:
    return type(
        "StubClient",
        (),
        {"chat": type("Chat", (), {"completions": object()})()},
    )()


def test_t216_historical_builders_keep_private_planners() -> None:
    from signal_diag.evaluation.runner import (
        _build_official_planner,
        _build_phase4_1_planner,
        _build_phase4_1_v6_planner,
        _build_phase4_2_v7_planner,
        _build_phase4_3_v8_planner,
        _official_benchmark_config,
        _phase4_3_v8_benchmark_config,
        _phase4_3_v8_prompt_sha256,
    )

    stub = _stub_client()
    v4 = _build_official_planner(stub)
    v5 = _build_phase4_1_planner(stub)
    v6 = _build_phase4_1_v6_planner(stub)
    v7 = _build_phase4_2_v7_planner(stub)
    v8 = _build_phase4_3_v8_planner(stub)
    assert type(v4) is _Phase4V4RealLLMPlanner
    assert type(v5) is _Phase4V5RealLLMPlanner
    assert type(v6) is _Phase4V6RealLLMPlanner
    assert type(v7) is _Phase4V7RealLLMPlanner
    assert type(v8) is _Phase4V8RealLLMPlanner
    assert type(v8) is not RealLLMPlanner
    assert v8._prompt_spec is _S1_PROMPT_V8
    assert v4._prompt_spec is _S1_PROMPT_V4
    assert v5._prompt_spec is _S1_PROMPT_V5
    assert v6._prompt_spec is _S1_PROMPT_V6
    assert v7._prompt_spec is _S1_PROMPT_V7

    v8_config = _phase4_3_v8_benchmark_config(
        benchmark_id=_V8_DEV_ID,
        started_at_utc=_STARTED,
    )
    assert v8_config.prompt_version == "v0.2-s1-planner-8"
    assert v8_config.prompt_sha256 == _FROZEN_V8_SHA256
    assert v8_config.prompt_sha256 == _phase4_3_v8_prompt_sha256()
    assert v8_config.sdk_versions == {}
    assert v8_config.dataset_version == "1.2.0"
    assert v8_config.repetitions == 5
    assert v8_config.max_concurrency == 1

    v4_config = _official_benchmark_config(
        benchmark_id="bench_phase4_legacy_v4",
        started_at_utc=_STARTED,
    )
    assert v4_config.prompt_version == "v0.2-s1-planner-4"
    assert v4_config.dataset_version == "1.0.0"


def test_v81_identity_config_fields_and_slots() -> None:
    from signal_diag.evaluation.runner import (
        _PHASE4_3_1_DEV_BENCHMARK_ID,
        _PHASE4_3_1_DEV_BUNDLE,
        _PHASE4_3_1_OFFICIAL_BENCHMARK_ID,
        _build_phase4_3_1_v8_1_planner,
        _phase4_3_1_v8_1_benchmark_config,
        _phase4_3_1_v8_1_prompt_sha256,
        _slot_schedule_for_split,
    )

    expected_hash = _v81_hash()
    assert expected_hash == _FROZEN_V81_SHA256
    development = _phase4_3_1_v8_1_benchmark_config(
        benchmark_id=_V81_DEV_ID,
        started_at_utc=_STARTED,
    )
    official = _phase4_3_1_v8_1_benchmark_config(
        benchmark_id=_V81_OFFICIAL_ID,
        started_at_utc=datetime(2026, 8, 31, 13, 0, tzinfo=UTC),
    )
    assert development.dataset_id == "s1-distortion-synthetic"
    assert development.dataset_version == "1.2.0"
    assert development.rule_profile_id == "profile_s1_distortion"
    assert development.rule_profile_version == "1.0.0-demo"
    assert development.provider == "deepseek"
    assert development.model == "deepseek-v4-flash"
    assert development.prompt_version == "v0.2-s1-planner-8.1"
    assert development.sdk_versions == {"signal_diag.scoring": "2.0.0"}
    assert development.repetitions == 5
    assert development.max_concurrency == 1
    assert development.prompt_sha256 == expected_hash
    assert _phase4_3_1_v8_1_prompt_sha256() == expected_hash
    assert _fingerprint(development) == _fingerprint(official)
    assert _PHASE4_3_1_DEV_BENCHMARK_ID == _V81_DEV_ID
    assert _PHASE4_3_1_OFFICIAL_BENCHMARK_ID == _V81_OFFICIAL_ID
    assert _PHASE4_3_1_DEV_BUNDLE == _V81_DEV_BUNDLE

    stub = _stub_client()
    planner = _build_phase4_3_1_v8_1_planner(stub)
    assert type(planner) is _Phase4V8_1RealLLMPlanner
    assert type(planner) is not RealLLMPlanner
    assert type(planner) is not _Phase4V8RealLLMPlanner
    assert planner._prompt_spec is _S1_PROMPT_V8_1

    manifest = load_dataset_manifest(PHASE4_2_MANIFEST)
    assert len(_slot_schedule_for_split(manifest, development, "development")) == 40
    assert len(_slot_schedule_for_split(manifest, official, "held_out")) == 80


@pytest.mark.parametrize(
    "update",
    (
        {"prompt_sha256": "a" * 64},
        {"prompt_version": "v0.2-s1-planner-8"},
        {"dataset_id": "other-dataset"},
        {"dataset_version": "1.1.0"},
        {"rule_profile_id": "other_profile"},
        {"rule_profile_version": "9.9.9"},
        {"provider": "other-provider"},
        {"model": "other-model"},
        {"repetitions": 1},
        {"max_concurrency": 2},
        {"sdk_versions": {}},
        {"sdk_versions": {"signal_diag.scoring": "1.0.0"}},
        {"sdk_versions": {"signal_diag.scoring": "2.0.0", "openai": "1.0.0"}},
        {"sdk_versions": {"other": "2.0.0"}},
    ),
    ids=(
        "wrong_hash",
        "wrong_prompt_version",
        "wrong_dataset_id",
        "wrong_dataset_version",
        "wrong_rule_profile_id",
        "wrong_rule_profile_version",
        "wrong_provider",
        "wrong_model",
        "wrong_repetitions",
        "wrong_concurrency",
        "missing_scoring",
        "unknown_scoring_version",
        "additional_sdk_key",
        "mismatched_scoring_key",
    ),
)
def test_v81_preflight_rejects_configuration_before_credentials(
    update: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from signal_diag.evaluation.runner import (
        _phase4_3_1_v8_1_benchmark_config,
        _preflight_phase4_3_1_v8_1,
        _PreflightFailure,
    )

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    import_calls: list[str] = []
    client_calls: list[str] = []
    credential_lookups: list[str] = []

    def boom_import() -> object:
        import_calls.append("openai")
        raise AssertionError("must not import openai before configuration rejection")

    def boom_client() -> object:
        client_calls.append("client")
        raise AssertionError("must not create client before configuration rejection")

    original_get = __import__("os").environ.get

    def tracing_get(key: str, default: object = None) -> object:
        if key == "DEEPSEEK_API_KEY":
            credential_lookups.append(key)
        return original_get(key, default)

    monkeypatch.setattr(
        "signal_diag.evaluation.runner.os.environ.get",
        tracing_get,
    )

    manifest = load_dataset_manifest(PHASE4_2_MANIFEST)
    base = _phase4_3_1_v8_1_benchmark_config(
        benchmark_id=_V81_DEV_ID,
        started_at_utc=_STARTED,
    )
    mismatched = base.model_copy(update=update)
    with pytest.raises(_PreflightFailure) as caught:
        _preflight_phase4_3_1_v8_1(
            manifest,
            mismatched,
            client_factory=boom_client,
            import_openai=boom_import,
        )
    assert caught.value.code == "invalid_configuration"
    assert credential_lookups == []
    assert import_calls == []
    assert client_calls == []


def test_v81_preflight_rejects_manifest_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from signal_diag.evaluation.runner import (
        _phase4_3_1_v8_1_benchmark_config,
        _preflight_phase4_3_1_v8_1,
        _PreflightFailure,
    )

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    manifest = load_dataset_manifest(PHASE4_1_MANIFEST)
    config = _phase4_3_1_v8_1_benchmark_config(
        benchmark_id=_V81_DEV_ID,
        started_at_utc=_STARTED,
    )
    with pytest.raises(_PreflightFailure) as caught:
        _preflight_phase4_3_1_v8_1(
            manifest,
            config,
            client_factory=object,
        )
    assert caught.value.code == "invalid_configuration"


@pytest.mark.asyncio
async def test_v81_runners_pass_opaque_signal_id_factory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from signal_diag.evaluation import runner as runner_mod
    from signal_diag.evaluation.reporting import DATA_FILES

    captured: dict[str, Any] = {}

    async def fake_split(*args: object, **kwargs: object) -> object:
        captured[str(kwargs["score_split"])] = kwargs
        return SimpleNamespace(benchmark_status="pending", attempts=())

    def write_gate_bundle(path: Path) -> Path:
        dest = path / _V81_DEV_ID
        dest.mkdir(parents=True)
        config = runner_mod._phase4_3_1_v8_1_benchmark_config(
            benchmark_id=_V81_DEV_ID,
            started_at_utc=_STARTED,
        )
        recorded = {
            "benchmark_id": _V81_DEV_ID,
            "prompt_version": config.prompt_version,
            "prompt_sha256": config.prompt_sha256,
            "dataset_id": config.dataset_id,
            "dataset_version": config.dataset_version,
            "rule_profile_id": config.rule_profile_id,
            "rule_profile_version": config.rule_profile_version,
            "provider": config.provider,
            "model": config.model,
            "repetitions": config.repetitions,
            "sdk_versions": config.sdk_versions,
        }
        (dest / "metrics.json").write_text(
            json.dumps(
                {"benchmark_status": "completed", "target_status": "meets_target"},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (dest / "benchmark_manifest.json").write_text(
            json.dumps({"config": recorded}) + "\n",
            encoding="utf-8",
        )
        (dest / "runs.jsonl").write_text("", encoding="utf-8")
        (dest / "case_summary.csv").write_text("x\n", encoding="utf-8")
        (dest / "report.md").write_text("# report\n", encoding="utf-8")
        lines = []
        for name in sorted(DATA_FILES):
            digest = __import__("hashlib").sha256(
                (dest / name).read_bytes()
            ).hexdigest()
            lines.append(f"{digest}  {name}\n")
        (dest / "checksums.sha256").write_text("".join(lines), encoding="utf-8")
        return dest

    monkeypatch.setattr(runner_mod, "_run_real_benchmark_for_split", fake_split)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    manifest = load_dataset_manifest(PHASE4_2_MANIFEST)
    development = runner_mod._phase4_3_1_v8_1_benchmark_config(
        benchmark_id=_V81_DEV_ID,
        started_at_utc=_STARTED,
    )
    official = runner_mod._phase4_3_1_v8_1_benchmark_config(
        benchmark_id=_V81_OFFICIAL_ID,
        started_at_utc=_STARTED,
    )
    gate = write_gate_bundle(tmp_path / "accepted")
    await runner_mod._run_phase4_3_1_v8_1_development_benchmark(
        manifest, development, tmp_path / "dev"
    )
    await runner_mod._run_phase4_3_1_v8_1_official_benchmark(
        manifest,
        official,
        tmp_path / "official",
        development_bundle=gate,
    )
    for split in ("development", "held_out"):
        kwargs = captured[split]
        assert kwargs["planner_builder"] is runner_mod._build_phase4_3_1_v8_1_planner
        factory = kwargs["signal_id_factory"]
        assert factory is not None
        case = next(item for item in manifest.cases if item.split == split)
        assert factory(case) == _opaque_evaluation_signal_id(
            manifest.dataset_id, manifest.version, case.case_id
        )


def _campaign_action(parser: argparse.ArgumentParser) -> argparse.Action:
    real = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    ).choices["run-real"]
    return next(
        action for action in real._actions if "--campaign" in action.option_strings
    )


def _expected_v81_config_fields() -> dict[str, Any]:
    return {
        "benchmark_id": _V81_DEV_ID,
        "prompt_version": "v0.2-s1-planner-8.1",
        "prompt_sha256": _v81_hash(),
        "dataset_id": "s1-distortion-synthetic",
        "dataset_version": "1.2.0",
        "rule_profile_id": "profile_s1_distortion",
        "rule_profile_version": "1.0.0-demo",
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "repetitions": 5,
        "sdk_versions": {"signal_diag.scoring": "2.0.0"},
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


def _write_v81_gate_bundle(
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
    dest = path / _V81_DEV_ID
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
                recorded = dict(_expected_v81_config_fields())
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


def _gate_expected_config():
    from signal_diag.evaluation.runner import _phase4_3_1_v8_1_benchmark_config

    return _phase4_3_1_v8_1_benchmark_config(
        benchmark_id=_V81_DEV_ID,
        started_at_utc=_STARTED,
    )


def test_t222_v81_campaigns_use_single_runner_registration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from signal_diag.evaluation import __main__ as cli
    from signal_diag.evaluation import runner as runner_mod
    from signal_diag.evaluation.__main__ import build_parser

    assert not hasattr(cli, "_V81_DEV_ID")
    assert not hasattr(cli, "_V81_OFFICIAL_ID")
    assert not hasattr(cli, "_PHASE4_3_1_DEV_BENCHMARK_ID")
    assert not hasattr(cli, "_PHASE4_3_1_OFFICIAL_BENCHMARK_ID")

    registry = runner_mod._PHASE4_3_1_V8_1_CAMPAIGNS
    assert dict(registry) and tuple(registry) == (
        "phase4.3.1-v8.1-development",
        "phase4.3.1-v8.1-official",
    )
    assert {
        name: route.canonical_id for name, route in registry.items()
    } == {
        "phase4.3.1-v8.1-development": "bench_phase4_3_1_dev_v8_1_v12_gate5",
        "phase4.3.1-v8.1-official": "bench_official_s1_v12_planner8_1_gate5",
    }
    development = registry["phase4.3.1-v8.1-development"]
    official = registry["phase4.3.1-v8.1-official"]
    assert development.canonical_id == runner_mod._PHASE4_3_1_DEV_BENCHMARK_ID
    assert official.canonical_id == runner_mod._PHASE4_3_1_OFFICIAL_BENCHMARK_ID
    assert development.config_builder is runner_mod._phase4_3_1_v8_1_benchmark_config
    assert official.config_builder is runner_mod._phase4_3_1_v8_1_benchmark_config
    assert development.manifest_path is runner_mod._phase4_2_manifest_path
    assert official.manifest_path is runner_mod._phase4_2_manifest_path
    assert development.score_split == "development"
    assert official.score_split == "held_out"
    assert development.extra_warnings == (runner_mod._PHASE4_1_DEV_WARNING,)
    assert official.extra_warnings == ()
    assert development.require_canonical_id is True
    assert official.require_canonical_id is True
    assert development.runner_name == "_run_phase4_3_1_v8_1_development_benchmark"
    assert official.runner_name == "_run_phase4_3_1_v8_1_official_benchmark"
    assert getattr(runner_mod, development.runner_name) is (
        runner_mod._run_phase4_3_1_v8_1_development_benchmark
    )
    assert getattr(runner_mod, official.runner_name) is (
        runner_mod._run_phase4_3_1_v8_1_official_benchmark
    )

    parser = build_parser()
    campaign = _campaign_action(parser)
    assert tuple(campaign.choices) == _V81_CAMPAIGNS
    assert campaign.default == "phase4"
    assert tuple(campaign.choices)[-2:] == tuple(registry)
    help_text = parser.format_help().lower()
    real_help = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    ).choices["run-real"].format_help().lower()
    for token in FORBIDDEN_CREDENTIAL_TOKENS:
        assert token not in help_text
        assert token not in real_help

    monkeypatch.setitem(registry, "phase4.3.1-v8.1-probe", development)
    probe_parser = build_parser()
    probe_campaign = _campaign_action(probe_parser)
    assert "phase4.3.1-v8.1-probe" in tuple(probe_campaign.choices)

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
        runner_mod, "_run_phase4_3_1_v8_1_development_benchmark", fake_dev
    )
    monkeypatch.setitem(
        registry,
        "phase4.3.1-v8.1-development",
        replace(development, canonical_id="bench_probe_silent_v81_route"),
    )
    assert (
        cli.main(
            [
                "run-real",
                "--campaign",
                "phase4.3.1-v8.1-development",
                "--output-dir",
                str(tmp_path / "probe"),
            ]
        )
        == 0
    )
    assert captured["benchmark_id"] == "bench_probe_silent_v81_route"


@pytest.mark.asyncio
async def test_t222_rejects_non_canonical_benchmark_id_and_conflicting_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from signal_diag.evaluation import runner as runner_mod

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    report = await runner_mod._run_phase4_3_1_v8_1_campaign(
        "phase4.3.1-v8.1-development",
        benchmark_id="bench_noncanonical_v81",
        manifest_path=None,
        output_dir=tmp_path / "noncanonical",
        started_at_utc=_STARTED,
    )
    assert report.benchmark_status == "pending"
    assert {attempt.error_code for attempt in report.attempts} == {
        "invalid_configuration"
    }
    assert report.config.benchmark_id == "bench_noncanonical_v81"

    conflict = await runner_mod._run_phase4_3_1_v8_1_campaign(
        "phase4.3.1-v8.1-development",
        benchmark_id=_V81_DEV_ID,
        manifest_path=PHASE4_1_MANIFEST,
        output_dir=tmp_path / "conflict",
        started_at_utc=_STARTED,
    )
    assert conflict.benchmark_status == "pending"
    assert {attempt.error_code for attempt in conflict.attempts} == {
        "invalid_configuration"
    }
    assert conflict.config.dataset_version == "1.2.0"
    assert conflict.config.prompt_version == "v0.2-s1-planner-8.1"
    assert conflict.config.sdk_versions == {"signal_diag.scoring": "2.0.0"}


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
    "changed_v81_hash",
    *tuple(f"missing_{field}" for field in _V81_IDENTITY_FIELDS),
    *tuple(f"mismatch_{field}" for field in _V81_IDENTITY_FIELDS),
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
    elif defect == "changed_v81_hash":
        kwargs["config_overlay"] = {"prompt_sha256": "a" * 64}
    elif defect.startswith("missing_"):
        field = defect.removeprefix("missing_")
        recorded = dict(_expected_v81_config_fields())
        del recorded[field]
        kwargs["manifest_text"] = json.dumps({"config": recorded}) + "\n"
    elif defect.startswith("mismatch_"):
        field = defect.removeprefix("mismatch_")
        overlay: dict[str, Any] = {
            "benchmark_id": "bench_wrong_identity",
            "prompt_version": "v0.2-s1-planner-8",
            "prompt_sha256": "a" * 64,
            "dataset_id": "other-dataset",
            "dataset_version": "1.1.0",
            "rule_profile_id": "profile_other",
            "rule_profile_version": "9.9.9",
            "provider": "other-provider",
            "model": "other-model",
            "repetitions": 1,
            "sdk_versions": {"signal_diag.scoring": "1.0.0"},
        }
        kwargs["config_overlay"] = {field: overlay[field]}
    return kwargs


@pytest.mark.parametrize("defect", _GATE_DEFECTS)
def test_t222_identity_complete_gate_rejects_defects(
    defect: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from signal_diag.evaluation.runner import (
        _PreflightFailure,
        _require_phase4_3_1_v8_1_development_gate,
    )

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    bundle = _write_v81_gate_bundle(tmp_path / defect, **_defect_bundle_kwargs(defect))
    with pytest.raises(_PreflightFailure) as caught:
        _require_phase4_3_1_v8_1_development_gate(bundle, _gate_expected_config())
    assert caught.value.code == "invalid_configuration"


@pytest.mark.parametrize("defect", _GATE_DEFECTS)
@pytest.mark.asyncio
async def test_t222_official_rejects_defects_before_credentials(
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

    original_gate = runner_mod._require_phase4_3_1_v8_1_development_gate

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
        runner_mod, "_require_phase4_3_1_v8_1_development_gate", tracing_gate
    )
    monkeypatch.setattr(runner_mod, "_slot_schedule_for_split", tracing_schedule)
    monkeypatch.setattr(runner_mod, "_run_real_benchmark_for_split", tracing_split)

    manifest = load_dataset_manifest(PHASE4_2_MANIFEST)
    config = runner_mod._phase4_3_1_v8_1_benchmark_config(
        benchmark_id=_V81_OFFICIAL_ID,
        started_at_utc=_STARTED,
    )
    bundle = _write_v81_gate_bundle(tmp_path / defect, **_defect_bundle_kwargs(defect))
    report = await runner_mod._run_phase4_3_1_v8_1_official_benchmark(
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
async def test_t222_rejects_existing_official_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from signal_diag.evaluation.runner import (
        _phase4_3_1_v8_1_benchmark_config,
        _run_phase4_3_1_v8_1_official_benchmark,
    )

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    manifest = load_dataset_manifest(PHASE4_2_MANIFEST)
    config = _phase4_3_1_v8_1_benchmark_config(
        benchmark_id=_V81_OFFICIAL_ID,
        started_at_utc=_STARTED,
    )
    gate = _write_v81_gate_bundle(tmp_path / "gate")
    output_dir = tmp_path / "official"
    first = await _run_phase4_3_1_v8_1_official_benchmark(
        manifest,
        config,
        output_dir,
        development_bundle=gate,
    )
    assert first.benchmark_status == "pending"
    with pytest.raises(FileExistsError):
        await _run_phase4_3_1_v8_1_official_benchmark(
            manifest,
            config,
            output_dir,
            development_bundle=gate,
        )
