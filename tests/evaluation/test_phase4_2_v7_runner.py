"""Phase 4.2 planner v7 additive campaigns (T207)."""

from __future__ import annotations

import argparse
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
    _Phase4V5RealLLMPlanner,
    _Phase4V6RealLLMPlanner,
    _Phase4V7RealLLMPlanner,
)
from signal_diag.agent.prompts import _S1_PROMPT_V5, _S1_PROMPT_V6, _S1_PROMPT_V7
from signal_diag.evaluation.dataset import (
    _opaque_evaluation_signal_id,
    load_dataset_manifest,
)
from tests.evaluation.conftest import PHASE4_1_MANIFEST
from tests.evaluation.test_phase4_1_runner import _fingerprint
from tests.evaluation.test_runner import FORBIDDEN_CREDENTIAL_TOKENS

_STARTED = datetime(2026, 8, 30, 17, 0, tzinfo=UTC)
_V7_DEV_ID = "bench_phase4_2_dev_v7_v12_gate3"
_V7_OFFICIAL_ID = "bench_official_s1_v12_planner7_gate3"
_V6_DEV_ID = "bench_phase4_1_dev_v6_gate2"
_V6_OFFICIAL_ID = "bench_official_s1_v11_planner6_gate2"
_V7_CAMPAIGNS = (
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
_V7_DEV_BUNDLE = Path("docs/evaluations/phase4_2/development") / _V7_DEV_ID
PHASE4_2_MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "signal_diag"
    / "evaluation"
    / "manifests"
    / "s1_distortion_v1_2.yaml"
)
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


def _v7_hash() -> str:
    return sha256(_S1_PROMPT_V7.system_prompt.encode()).hexdigest()


def _expected_v7_config_fields() -> dict[str, Any]:
    return {
        "benchmark_id": _V7_DEV_ID,
        "prompt_version": "v0.2-s1-planner-7",
        "prompt_sha256": _v7_hash(),
        "dataset_id": "s1-distortion-synthetic",
        "dataset_version": "1.2.0",
        "rule_profile_id": "profile_s1_distortion",
        "rule_profile_version": "1.0.0-demo",
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "repetitions": 5,
    }


def _write_v7_gate_bundle(
    path: Path,
    *,
    benchmark_status: str = "completed",
    target_status: str = "meets_target",
    config_overlay: dict[str, Any] | None = None,
    omit_metrics: bool = False,
    omit_manifest: bool = False,
    metrics_text: str | None = None,
    manifest_text: str | None = None,
) -> Path:
    dest = path / _V7_DEV_ID
    dest.mkdir(parents=True)
    if not omit_metrics:
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
        if manifest_text is None:
            recorded = dict(_expected_v7_config_fields())
            if config_overlay:
                recorded.update(config_overlay)
            manifest_text = json.dumps({"config": recorded}) + "\n"
        (dest / "benchmark_manifest.json").write_text(manifest_text, encoding="utf-8")
    return dest


def _stub_client() -> object:
    return type(
        "StubClient",
        (),
        {"chat": type("Chat", (), {"completions": object()})()},
    )()


def test_t207_campaign_choices_are_additive() -> None:
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
    assert tuple(campaign.choices) == _V7_CAMPAIGNS
    assert campaign.default == "phase4"
    help_text = real.format_help().lower()
    for token in FORBIDDEN_CREDENTIAL_TOKENS:
        assert token not in help_text


def test_t207_v7_campaigns_use_single_runner_registration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parser choices, canonical IDs, and CLI dispatch must share one registry.

    A third silent copy in ``__main__`` (parser literals or ``_V7_*`` aliases)
    would keep using frozen IDs after the runner registry is patched.
    """
    from signal_diag.evaluation import __main__ as cli
    from signal_diag.evaluation import runner as runner_mod
    from signal_diag.evaluation.__main__ import build_parser

    assert not hasattr(cli, "_V7_DEV_ID")
    assert not hasattr(cli, "_V7_OFFICIAL_ID")

    registry = runner_mod._PHASE4_2_V7_CAMPAIGNS
    assert tuple(registry) == (
        "phase4.2-v7-development",
        "phase4.2-v7-official",
    )
    development = registry["phase4.2-v7-development"]
    official = registry["phase4.2-v7-official"]
    assert development.canonical_id == runner_mod._PHASE4_2_V7_DEV_BENCHMARK_ID
    assert official.canonical_id == runner_mod._PHASE4_2_V7_OFFICIAL_BENCHMARK_ID
    assert development.config_builder is runner_mod._phase4_2_v7_benchmark_config
    assert official.config_builder is runner_mod._phase4_2_v7_benchmark_config
    assert development.manifest_path is runner_mod._phase4_2_manifest_path
    assert official.manifest_path is runner_mod._phase4_2_manifest_path
    assert development.score_split == "development"
    assert official.score_split == "held_out"
    assert development.extra_warnings == (runner_mod._PHASE4_1_DEV_WARNING,)
    assert official.extra_warnings == ()
    assert development.require_canonical_id is True
    assert official.require_canonical_id is True
    assert development.runner_name == "_run_phase4_2_v7_development_benchmark"
    assert official.runner_name == "_run_phase4_2_v7_official_benchmark"
    assert getattr(runner_mod, development.runner_name) is (
        runner_mod._run_phase4_2_v7_development_benchmark
    )
    assert getattr(runner_mod, official.runner_name) is (
        runner_mod._run_phase4_2_v7_official_benchmark
    )

    parser = build_parser()
    real = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    ).choices["run-real"]
    campaign = next(
        action for action in real._actions if "--campaign" in action.option_strings
    )
    assert all(name in tuple(campaign.choices) for name in registry)

    monkeypatch.setitem(
        registry,
        "phase4.2-v7-probe",
        development,
    )
    probe_parser = build_parser()
    probe_real = next(
        action
        for action in probe_parser._actions
        if isinstance(action, argparse._SubParsersAction)
    ).choices["run-real"]
    probe_campaign = next(
        action
        for action in probe_real._actions
        if "--campaign" in action.option_strings
    )
    assert "phase4.2-v7-probe" in tuple(probe_campaign.choices)

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
        runner_mod, "_run_phase4_2_v7_development_benchmark", fake_dev
    )
    monkeypatch.setitem(
        registry,
        "phase4.2-v7-development",
        replace(development, canonical_id="bench_probe_silent_route"),
    )
    assert (
        cli.main(
            [
                "run-real",
                "--campaign",
                "phase4.2-v7-development",
                "--output-dir",
                str(tmp_path / "probe"),
            ]
        )
        == 0
    )
    assert captured["benchmark_id"] == "bench_probe_silent_route"


def test_t207_historical_routes_keep_v5_and_v6_identity() -> None:
    from signal_diag.evaluation.runner import (
        _build_phase4_1_planner,
        _build_phase4_1_v6_planner,
        _phase4_1_benchmark_config,
        _phase4_1_v6_benchmark_config,
    )

    v5 = _phase4_1_benchmark_config(
        benchmark_id="bench_phase4_1_dev_v5_gate1",
        started_at_utc=_STARTED,
    )
    v6 = _phase4_1_v6_benchmark_config(
        benchmark_id=_V6_DEV_ID,
        started_at_utc=_STARTED,
    )
    assert v5.prompt_version == "v0.2-s1-planner-5"
    assert v5.dataset_version == "1.1.0"
    assert v5.prompt_sha256 == sha256(_S1_PROMPT_V5.system_prompt.encode()).hexdigest()
    assert v6.prompt_version == "v0.2-s1-planner-6"
    assert v6.dataset_version == "1.1.0"
    assert v6.prompt_sha256 == sha256(_S1_PROMPT_V6.system_prompt.encode()).hexdigest()
    stub = _stub_client()
    v5_planner = _build_phase4_1_planner(stub)
    v6_planner = _build_phase4_1_v6_planner(stub)
    assert type(v5_planner) is _Phase4V5RealLLMPlanner
    assert type(v6_planner) is _Phase4V6RealLLMPlanner
    assert v5_planner._prompt_spec is _S1_PROMPT_V5
    assert v6_planner._prompt_spec is _S1_PROMPT_V6


def test_t207_v7_config_and_canonical_ids() -> None:
    from signal_diag.evaluation.runner import (
        _PHASE4_2_V7_DEV_BUNDLE,
        _build_phase4_2_v7_planner,
        _phase4_2_v7_benchmark_config,
        _phase4_2_v7_prompt_sha256,
        _run_phase4_2_v7_official_benchmark,
        _slot_schedule_for_split,
    )

    expected_hash = _v7_hash()
    development = _phase4_2_v7_benchmark_config(
        benchmark_id=_V7_DEV_ID,
        started_at_utc=_STARTED,
    )
    official = _phase4_2_v7_benchmark_config(
        benchmark_id=_V7_OFFICIAL_ID,
        started_at_utc=datetime(2026, 8, 31, 9, 0, tzinfo=UTC),
    )
    assert development.prompt_version == "v0.2-s1-planner-7"
    assert development.dataset_id == "s1-distortion-synthetic"
    assert development.dataset_version == "1.2.0"
    assert development.rule_profile_id == "profile_s1_distortion"
    assert development.rule_profile_version == "1.0.0-demo"
    assert development.provider == "deepseek"
    assert development.model == "deepseek-v4-flash"
    assert development.repetitions == 5
    assert development.max_concurrency == 1
    assert development.prompt_sha256 == expected_hash
    assert _phase4_2_v7_prompt_sha256() == expected_hash
    assert _fingerprint(development) == _fingerprint(official)
    stub = _stub_client()
    planner = _build_phase4_2_v7_planner(stub)
    assert type(planner) is _Phase4V7RealLLMPlanner
    assert type(planner) is not RealLLMPlanner
    assert type(planner) is not _Phase4V6RealLLMPlanner
    assert type(planner) is not _Phase4V5RealLLMPlanner
    assert planner._prompt_spec is _S1_PROMPT_V7
    assert _PHASE4_2_V7_DEV_BUNDLE == _V7_DEV_BUNDLE
    default = inspect.signature(
        _run_phase4_2_v7_official_benchmark
    ).parameters["development_bundle"].default
    assert default in (None, _V7_DEV_BUNDLE)

    manifest = load_dataset_manifest(PHASE4_2_MANIFEST)
    assert manifest.version == "1.2.0"
    assert len(_slot_schedule_for_split(manifest, development, "development")) == 40
    assert len(_slot_schedule_for_split(manifest, official, "held_out")) == 80


def test_t207_preflight_rejects_dataset_and_profile_mismatch() -> None:
    from signal_diag.evaluation.runner import (
        _phase4_2_v7_benchmark_config,
        _preflight_phase4_2_v7,
        _PreflightFailure,
    )

    manifest = load_dataset_manifest(PHASE4_2_MANIFEST)
    base = _phase4_2_v7_benchmark_config(
        benchmark_id=_V7_DEV_ID,
        started_at_utc=_STARTED,
    )
    for update in (
        {"dataset_id": "other-dataset"},
        {"dataset_version": "1.1.0"},
        {"rule_profile_id": "other_profile"},
        {"rule_profile_version": "9.9.9"},
    ):
        mismatched = base.model_copy(update=update)
        with pytest.raises(_PreflightFailure) as caught:
            _preflight_phase4_2_v7(manifest, mismatched, client_factory=object)
        assert caught.value.code == "invalid_configuration"


@pytest.mark.asyncio
async def test_t207_v7_runners_pass_opaque_signal_id_factory(
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
    development = runner_mod._phase4_2_v7_benchmark_config(
        benchmark_id=_V7_DEV_ID,
        started_at_utc=_STARTED,
    )
    official = runner_mod._phase4_2_v7_benchmark_config(
        benchmark_id=_V7_OFFICIAL_ID,
        started_at_utc=_STARTED,
    )
    gate = _write_v7_gate_bundle(tmp_path / "accepted")
    await runner_mod._run_phase4_2_v7_development_benchmark(
        manifest, development, tmp_path / "dev"
    )
    await runner_mod._run_phase4_2_v7_official_benchmark(
        manifest,
        official,
        tmp_path / "official",
        development_bundle=gate,
    )
    for split in ("development", "held_out"):
        kwargs = captured[split]
        assert kwargs["planner_builder"] is runner_mod._build_phase4_2_v7_planner
        factory = kwargs["signal_id_factory"]
        assert factory is not None
        case = next(item for item in manifest.cases if item.split == split)
        assert factory(case) == _opaque_evaluation_signal_id(
            manifest.dataset_id, manifest.version, case.case_id
        )


def test_t207_cli_defaults_canonical_v7_ids(
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
        runner_mod, "_run_phase4_2_v7_development_benchmark", fake_dev
    )
    monkeypatch.setattr(
        runner_mod, "_run_phase4_2_v7_official_benchmark", fake_official
    )
    assert (
        cli.main(
            [
                "run-real",
                "--campaign",
                "phase4.2-v7-development",
                "--output-dir",
                str(tmp_path / "dev"),
            ]
        )
        == 0
    )
    dev_manifest, dev_config, dev_out = captured["dev"]
    assert dev_config.benchmark_id == _V7_DEV_ID
    assert dev_config.dataset_version == "1.2.0"
    assert dev_config.prompt_version == "v0.2-s1-planner-7"
    assert dev_manifest.version == "1.2.0"
    assert dev_out == tmp_path / "dev"

    assert (
        cli.main(
            [
                "run-real",
                "--campaign",
                "phase4.2-v7-official",
                "--output-dir",
                str(tmp_path / "official"),
            ]
        )
        == 0
    )
    official_manifest, official_config, official_out, official_kwargs = captured[
        "official"
    ]
    assert official_config.benchmark_id == _V7_OFFICIAL_ID
    assert official_config.dataset_version == "1.2.0"
    assert official_manifest.version == "1.2.0"
    assert official_out == tmp_path / "official"
    bundle = official_kwargs.get("development_bundle")
    assert bundle in (None, _V7_DEV_BUNDLE)


@pytest.mark.parametrize("campaign", ("phase4.2-v7-development", "phase4.2-v7-official"))
def test_t207_acceptance_campaigns_reject_non_canonical_benchmark_id(
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
        runner_mod, "_run_phase4_2_v7_development_benchmark", fake_dev
    )
    monkeypatch.setattr(
        runner_mod, "_run_phase4_2_v7_official_benchmark", fake_official
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
                "bench_custom_v7_exploratory",
                "--output-dir",
                str(output),
            ]
        )
        == 0
    )
    assert called == []
    dest = output / "bench_custom_v7_exploratory"
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


def test_t207_cli_does_not_redirect_v6_onto_v7(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from signal_diag.evaluation import __main__ as cli
    from signal_diag.evaluation import runner as runner_mod

    captured: dict[str, str] = {}

    async def fake_v6_dev(*args: object, **kwargs: object) -> object:
        captured["hit"] = "v6"
        return SimpleNamespace(benchmark_status="pending")

    async def fake_v7_dev(*args: object, **kwargs: object) -> object:
        captured["hit"] = "v7"
        return SimpleNamespace(benchmark_status="pending")

    monkeypatch.setattr(cli, "_run_phase4_1_v6_development_benchmark", fake_v6_dev)
    monkeypatch.setattr(
        runner_mod, "_run_phase4_2_v7_development_benchmark", fake_v7_dev
    )
    assert (
        cli.main(
            [
                "run-real",
                "--campaign",
                "phase4.1-v6-development",
                "--output-dir",
                str(tmp_path / "v6"),
            ]
        )
        == 0
    )
    assert captured["hit"] == "v6"


def _gate_expected_config():
    from signal_diag.evaluation.runner import _phase4_2_v7_benchmark_config

    return _phase4_2_v7_benchmark_config(
        benchmark_id=_V7_DEV_ID,
        started_at_utc=_STARTED,
    )


@pytest.mark.parametrize(
    "defect",
    (
        "missing_metrics",
        "missing_manifest",
        "invalid_metrics_json",
        "invalid_manifest_json",
        "wrong_status",
        "wrong_target",
        "missing_config",
        *tuple(f"mismatch_{field}" for field in _IDENTITY_FIELDS),
    ),
)
def test_t207_identity_complete_gate_rejects_defects(
    defect: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from signal_diag.evaluation.runner import (
        _PreflightFailure,
        _require_identity_complete_development_gate,
    )

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    kwargs: dict[str, Any] = {}
    if defect == "missing_metrics":
        kwargs["omit_metrics"] = True
    elif defect == "missing_manifest":
        kwargs["omit_manifest"] = True
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
    elif defect.startswith("mismatch_"):
        field = defect.removeprefix("mismatch_")
        overlay: dict[str, Any] = {
            "benchmark_id": "bench_wrong_identity",
            "prompt_version": "v0.2-s1-planner-6",
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
    bundle = _write_v7_gate_bundle(tmp_path / defect, **kwargs)
    with pytest.raises(_PreflightFailure) as caught:
        _require_identity_complete_development_gate(
            bundle,
            _gate_expected_config(),
        )
    assert caught.value.code == "invalid_configuration"


def test_t207_v6_missing_manifest_is_invalid_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from signal_diag.evaluation.runner import (
        _phase4_1_v6_benchmark_config,
        _PreflightFailure,
        _require_v6_development_gate,
    )

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    dest = tmp_path / _V6_DEV_ID
    dest.mkdir()
    (dest / "metrics.json").write_text(
        json.dumps(
            {
                "benchmark_status": "completed",
                "target_status": "meets_target",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    config = _phase4_1_v6_benchmark_config(
        benchmark_id=_V6_OFFICIAL_ID,
        started_at_utc=_STARTED,
    )
    with pytest.raises(_PreflightFailure) as caught:
        _require_v6_development_gate(dest, config)
    assert caught.value.code == "invalid_configuration"


def test_t207_v6_below_target_remains_ineligible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from signal_diag.evaluation.runner import (
        _phase4_1_v6_benchmark_config,
        _PreflightFailure,
        _require_v6_development_gate,
    )

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    dest = tmp_path / _V6_DEV_ID
    dest.mkdir()
    (dest / "metrics.json").write_text(
        json.dumps(
            {
                "benchmark_status": "completed",
                "target_status": "below_target",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (dest / "benchmark_manifest.json").write_text(
        json.dumps(
            {
                "config": {
                    "benchmark_id": _V6_DEV_ID,
                    "prompt_version": "v0.2-s1-planner-6",
                    "prompt_sha256": "9be518167ec58f3806ae569e48929c37d1e526ac4ae0463a448dd622ec0f1ef1",
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
    config = _phase4_1_v6_benchmark_config(
        benchmark_id=_V6_OFFICIAL_ID,
        started_at_utc=_STARTED,
    )
    with pytest.raises(_PreflightFailure) as caught:
        _require_v6_development_gate(dest, config)
    assert caught.value.code == "invalid_configuration"


@pytest.mark.asyncio
async def test_t207_official_rejects_before_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from signal_diag.evaluation.runner import (
        _phase4_2_v7_benchmark_config,
        _run_phase4_2_v7_official_benchmark,
    )

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    manifest = load_dataset_manifest(PHASE4_2_MANIFEST)
    config = _phase4_2_v7_benchmark_config(
        benchmark_id=_V7_OFFICIAL_ID,
        started_at_utc=_STARTED,
    )
    missing_manifest = _write_v7_gate_bundle(
        tmp_path / "metrics-only",
        omit_manifest=True,
    )
    report = await _run_phase4_2_v7_official_benchmark(
        manifest,
        config,
        tmp_path / "blocked",
        development_bundle=missing_manifest,
    )
    assert report.benchmark_status == "pending"
    assert {attempt.error_code for attempt in report.attempts} == {
        "invalid_configuration"
    }
    assert all(attempt.execution_path == "agent" for attempt in report.attempts)


@pytest.mark.asyncio
async def test_t207_rejects_conflicting_manifest_without_rewrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from signal_diag.evaluation.runner import (
        _phase4_2_v7_benchmark_config,
        _run_phase4_2_v7_development_benchmark,
    )

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    report = await _run_phase4_2_v7_development_benchmark(
        load_dataset_manifest(PHASE4_1_MANIFEST),
        _phase4_2_v7_benchmark_config(
            benchmark_id=_V7_DEV_ID,
            started_at_utc=_STARTED,
        ),
        tmp_path / "conflict",
    )
    assert report.benchmark_status == "pending"
    assert {attempt.error_code for attempt in report.attempts} == {
        "invalid_configuration"
    }
    assert report.config.dataset_version == "1.2.0"
    assert report.config.prompt_version == "v0.2-s1-planner-7"
