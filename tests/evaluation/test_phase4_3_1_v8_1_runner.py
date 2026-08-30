"""Phase 4.3.1 planner v8.1 private runner identity (Task 5 / T216 runner)."""

from __future__ import annotations

import json
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
from tests.evaluation.conftest import PHASE4_1_MANIFEST
from tests.evaluation.test_phase4_2_v7_runner import PHASE4_2_MANIFEST
from tests.evaluation.test_runner import _fingerprint

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
        _phase4_1_benchmark_config,
        _phase4_1_v6_benchmark_config,
        _phase4_2_v7_benchmark_config,
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
    assert type(planner) is RealLLMPlanner
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
