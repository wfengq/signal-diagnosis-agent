"""Phase 4.1 campaign runners, split aggregation, and CLI (T184/T194)."""

from __future__ import annotations

import argparse
import inspect
import typing
from collections.abc import Callable
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
)
from signal_diag.agent.prompts import _S1_PROMPT_V4, _S1_PROMPT_V5
from signal_diag.evaluation.dataset import load_dataset_manifest
from signal_diag.evaluation.models import (
    BenchmarkConfig,
    BenchmarkReport,
    DatasetManifest,
    EvaluationSplit,
    HarnessStatus,
    TargetBands,
)
from signal_diag.evaluation.runner import (
    _baseline_slot_schedule,
    _ContextBoundScriptedPlanner,
    _held_out_slot_schedule,
    _official_benchmark_config,
    _official_prompt_sha256,
    _run_official_benchmark,
)
from signal_diag.evaluation.scoring import aggregate_benchmark
from tests.evaluation.conftest import (
    CANONICAL_MANIFEST,
    PHASE4_1_MANIFEST,
    make_dataset_manifest,
    make_evaluation_case,
)
from tests.evaluation.test_runner import (
    _RETRYABLE,
    FORBIDDEN_CREDENTIAL_TOKENS,
    _adaptive_success_handler,
    _AuthenticationError,
    _client_factory_for,
    _CountingKnowledgeBudget,
    _CountingToolBudget,
    _fingerprint,
    _invalid_output_handler,
    _no_progress_handler,
    _Provider5xxError,
    _raise_handler,
    _RateLimitedError,
    _rule_budget_handler,
    _TimeoutTransportError,
)
from tests.evaluation.test_scoring import (
    _agg_config,
    _behavior_attempt,
    _bind_run,
    _legal_clipping_trace,
    _legal_harmonic_trace,
)

_STARTED = datetime(2026, 8, 30, 1, 0, tzinfo=UTC)
_DEV_WARNING = "development split; not official held-out evidence"
_PHASE4_1_CAMPAIGNS = (
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
_SUBCOMMANDS = {
    "validate-dataset",
    "run-deterministic",
    "run-real",
    "render-report",
}


def _phase4_1_mini_manifest(
    *rows: tuple[str, EvaluationSplit],
) -> DatasetManifest:
    cases = tuple(
        make_evaluation_case("clean", case_id=case_id, split=split)
        for case_id, split in rows
    )
    return make_dataset_manifest(
        cases,
        dataset_id="runner-mini",
        version="1.1.0",
    )


def _mixed_mini_manifest() -> DatasetManifest:
    return _phase4_1_mini_manifest(
        ("case_dev_alpha", "development"),
        ("case_dev_beta", "development"),
        ("case_held_alpha", "held_out"),
        ("case_held_beta", "held_out"),
    )


def _phase4_1_mini_config(
    manifest: DatasetManifest,
    *,
    benchmark_id: str,
    repetitions: int = 1,
) -> BenchmarkConfig:
    from signal_diag.evaluation.runner import _phase4_1_benchmark_config

    base = _phase4_1_benchmark_config(
        benchmark_id=benchmark_id,
        started_at_utc=_STARTED,
    )
    return base.model_copy(
        update={
            "dataset_id": manifest.dataset_id,
            "dataset_version": manifest.version,
            "repetitions": repetitions,
        }
    )


@pytest.fixture
def dummy_deepseek_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-not-a-real-key")


def test_t184_legacy_official_config_preserves_v4_fingerprint() -> None:
    assert _S1_PROMPT_V4.version == "v0.2-s1-planner-4"
    expected_hash = sha256(_S1_PROMPT_V4.system_prompt.encode()).hexdigest()
    assert _official_prompt_sha256() == expected_hash
    config = _official_benchmark_config(
        benchmark_id="bench_phase4_1_legacy_v4",
        started_at_utc=_STARTED,
    )
    assert config.dataset_version == "1.0.0"
    assert config.provider == "deepseek"
    assert config.model == "deepseek-v4-flash"
    assert config.prompt_version == "v0.2-s1-planner-4"
    assert config.prompt_sha256 == expected_hash
    assert config.repetitions == 5
    assert config.max_infrastructure_retries == 2
    assert config.max_concurrency == 1
    rerun = _official_benchmark_config(
        benchmark_id="bench_phase4_1_legacy_v4_rerun",
        started_at_utc=datetime(2026, 8, 31, 8, 0, tzinfo=UTC),
    )
    assert _fingerprint(config) == _fingerprint(rerun)


def test_t184_phase4_1_config_records_v5_pins() -> None:
    from signal_diag.evaluation.runner import _phase4_1_benchmark_config

    config = _phase4_1_benchmark_config(
        benchmark_id="bench_phase4_1_config",
        started_at_utc=_STARTED,
    )
    assert config.dataset_version == "1.1.0"
    assert config.provider == "deepseek"
    assert config.model == "deepseek-v4-flash"
    assert config.prompt_version == "v0.2-s1-planner-5"
    assert config.prompt_sha256 == sha256(_S1_PROMPT_V5.system_prompt.encode()).hexdigest()
    assert config.repetitions == 5
    assert config.max_infrastructure_retries == 2
    assert config.max_concurrency == 1
    official = _official_benchmark_config(
        benchmark_id="bench_phase4_1_legacy_compare",
        started_at_utc=_STARTED,
    )
    assert _fingerprint(config) != _fingerprint(official)
    assert "split" not in config.model_parameters
    assert "campaign" not in config.model_parameters
    assert "score_split" not in config.model_parameters


def test_t184_development_and_official_share_config_fingerprint() -> None:
    from signal_diag.evaluation.runner import _phase4_1_benchmark_config

    development = _phase4_1_benchmark_config(
        benchmark_id="bench_phase4_1_fp_dev",
        started_at_utc=_STARTED,
    )
    official = _phase4_1_benchmark_config(
        benchmark_id="bench_phase4_1_fp_official",
        started_at_utc=datetime(2026, 8, 31, 9, 0, tzinfo=UTC),
    )
    assert _fingerprint(development) == _fingerprint(official)
    assert not hasattr(development, "split")
    dumped = development.model_dump(mode="json")
    assert "split" not in dumped
    assert dumped["model_parameters"] == official.model_parameters


@pytest.mark.asyncio
async def test_phase4_1_mini_manifest_schedules_2x5_per_split(
    dummy_deepseek_key: None,
    tmp_path: Path,
) -> None:
    from signal_diag.evaluation.runner import (
        _run_phase4_1_development_benchmark,
        _run_phase4_1_official_benchmark,
    )

    manifest = _mixed_mini_manifest()
    development = await _run_phase4_1_development_benchmark(
        manifest,
        _phase4_1_mini_config(
            manifest,
            benchmark_id="bench_phase4_1_mini_dev",
            repetitions=5,
        ),
        tmp_path / "dev",
        client_factory=_client_factory_for(_adaptive_success_handler),
    )
    official = await _run_phase4_1_official_benchmark(
        manifest,
        _phase4_1_mini_config(
            manifest,
            benchmark_id="bench_phase4_1_mini_official",
            repetitions=5,
        ),
        tmp_path / "official",
        client_factory=_client_factory_for(_adaptive_success_handler),
    )
    dev_agent = [
        (attempt.case_id, attempt.run_slot)
        for attempt in development.attempts
        if attempt.execution_path == "agent" and attempt.status == "behavior_result"
    ]
    official_agent = [
        (attempt.case_id, attempt.run_slot)
        for attempt in official.attempts
        if attempt.execution_path == "agent" and attempt.status == "behavior_result"
    ]
    expected_dev = tuple(
        (case_id, slot)
        for slot in range(1, 6)
        for case_id in ("case_dev_alpha", "case_dev_beta")
    )
    expected_held = tuple(
        (case_id, slot)
        for slot in range(1, 6)
        for case_id in ("case_held_alpha", "case_held_beta")
    )
    assert tuple(dev_agent) == expected_dev
    assert len(dev_agent) == 10
    assert tuple(official_agent) == expected_held
    assert len(official_agent) == 10
    assert {case_id for case_id, _ in dev_agent} == {
        "case_dev_alpha",
        "case_dev_beta",
    }
    assert {case_id for case_id, _ in official_agent} == {
        "case_held_alpha",
        "case_held_beta",
    }
    assert [
        attempt.case_id
        for attempt in development.attempts
        if attempt.execution_path == "fixed_pipeline"
    ] == ["case_dev_alpha", "case_dev_beta"]
    assert [
        attempt.case_id
        for attempt in official.attempts
        if attempt.execution_path == "fixed_pipeline"
    ] == [
        "case_dev_alpha",
        "case_dev_beta",
        "case_held_alpha",
        "case_held_beta",
    ]
    assert _DEV_WARNING in development.warnings
    assert _DEV_WARNING not in official.warnings


@pytest.mark.asyncio
async def test_t194_canonical_v11_schedules_40_development_and_80_held_out(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from signal_diag.evaluation.runner import (
        _phase4_1_benchmark_config,
        _run_phase4_1_development_benchmark,
        _run_phase4_1_official_benchmark,
    )

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    manifest = load_dataset_manifest(PHASE4_1_MANIFEST)
    development = await _run_phase4_1_development_benchmark(
        manifest,
        _phase4_1_benchmark_config(
            benchmark_id="bench_t194_dev_schedule",
            started_at_utc=_STARTED,
        ),
        tmp_path / "dev",
    )
    official = await _run_phase4_1_official_benchmark(
        manifest,
        _phase4_1_benchmark_config(
            benchmark_id="bench_t194_official_schedule",
            started_at_utc=_STARTED,
        ),
        tmp_path / "official",
    )
    dev_cases = [case.case_id for case in manifest.cases if case.split == "development"]
    held_cases = [case.case_id for case in manifest.cases if case.split == "held_out"]
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
    assert {attempt.case_id for attempt in dev_agent} == set(dev_cases)
    assert {attempt.case_id for attempt in official_agent} == set(held_cases)
    assert {attempt.error_code for attempt in dev_agent} == {"missing_credentials"}
    assert {attempt.error_code for attempt in official_agent} == {"missing_credentials"}
    official_baseline = [
        attempt.case_id
        for attempt in official.attempts
        if attempt.execution_path == "fixed_pipeline"
    ]
    assert official_baseline == [] or len(_baseline_slot_schedule(manifest)) == 24
    assert len(_held_out_slot_schedule(manifest, official.config)) == 80
    assert official.config.dataset_version == "1.1.0"
    assert official.config.prompt_version == "v0.2-s1-planner-5"
    assert official.config.prompt_sha256 == sha256(
        _S1_PROMPT_V5.system_prompt.encode()
    ).hexdigest()


def test_cli_campaign_choices_preserve_four_subcommands() -> None:
    from signal_diag.evaluation.__main__ import build_parser

    parser = build_parser()
    subparsers = [
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    ]
    assert subparsers
    assert set(subparsers[0].choices) == _SUBCOMMANDS
    real = subparsers[0].choices["run-real"]
    campaign = next(
        action
        for action in real._actions
        if "--campaign" in action.option_strings
    )
    assert tuple(campaign.choices) == _PHASE4_1_CAMPAIGNS
    assert campaign.default == "phase4"
    parsed = parser.parse_args(["run-real"])
    assert parsed.campaign == "phase4"
    help_text = parser.format_help().lower()
    real_help = real.format_help().lower()
    for token in FORBIDDEN_CREDENTIAL_TOKENS:
        assert token not in help_text
        assert token not in real_help
    for name, subparser in subparsers[0].choices.items():
        if name == "run-real":
            continue
        option_strings = [
            option
            for action in subparser._actions
            for option in action.option_strings
        ]
        assert "--campaign" not in option_strings


def test_cli_campaign_routes_and_rejects_conflicting_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from signal_diag.evaluation import __main__ as cli
    from signal_diag.evaluation.runner import _phase4_1_benchmark_config

    captured: dict[str, Any] = {}

    async def fake_official(
        manifest: DatasetManifest,
        config: BenchmarkConfig,
        output_dir: Path,
        **kwargs: object,
    ) -> SimpleNamespace:
        captured["legacy"] = (manifest.version, config.prompt_version, config.dataset_version)
        return SimpleNamespace(benchmark_status="pending")

    async def fake_dev(
        manifest: DatasetManifest,
        config: BenchmarkConfig,
        output_dir: Path,
        **kwargs: object,
    ) -> SimpleNamespace:
        captured["dev"] = (manifest.version, config.prompt_version, config.dataset_version)
        return SimpleNamespace(benchmark_status="pending")

    async def fake_phase41_official(
        manifest: DatasetManifest,
        config: BenchmarkConfig,
        output_dir: Path,
        **kwargs: object,
    ) -> SimpleNamespace:
        captured["p41"] = (manifest.version, config.prompt_version, config.dataset_version)
        return SimpleNamespace(benchmark_status="pending")

    monkeypatch.setattr(cli, "_run_official_benchmark", fake_official)
    monkeypatch.setattr(cli, "_run_phase4_1_development_benchmark", fake_dev)
    monkeypatch.setattr(cli, "_run_phase4_1_official_benchmark", fake_phase41_official)

    assert (
        cli.main(
            [
                "run-real",
                "--output-dir",
                str(tmp_path / "legacy"),
                "--benchmark-id",
                "bench_cli_phase4",
            ]
        )
        == 0
    )
    assert captured["legacy"][0] == "1.0.0"
    assert captured["legacy"][1] == "v0.2-s1-planner-4"
    assert captured["legacy"][2] == "1.0.0"

    assert (
        cli.main(
            [
                "run-real",
                "--campaign",
                "phase4.1-development",
                "--output-dir",
                str(tmp_path / "dev"),
                "--benchmark-id",
                "bench_cli_dev",
            ]
        )
        == 0
    )
    assert captured["dev"] == ("1.1.0", "v0.2-s1-planner-5", "1.1.0")

    assert (
        cli.main(
            [
                "run-real",
                "--campaign",
                "phase4.1-official",
                "--output-dir",
                str(tmp_path / "p41"),
                "--benchmark-id",
                "bench_cli_p41",
            ]
        )
        == 0
    )
    assert captured["p41"] == ("1.1.0", "v0.2-s1-planner-5", "1.1.0")

    conflict_id = "bench_cli_conflict"
    code = cli.main(
        [
            "run-real",
            "--campaign",
            "phase4.1-official",
            "--manifest",
            str(CANONICAL_MANIFEST),
            "--output-dir",
            str(tmp_path / "conflict"),
            "--benchmark-id",
            conflict_id,
        ]
    )
    assert code == 0
    assert "p41" in captured
    bundle = tmp_path / "conflict" / conflict_id / "benchmark_manifest.json"
    payload = bundle.read_text(encoding="utf-8")
    report_config = _phase4_1_benchmark_config(
        benchmark_id=conflict_id,
        started_at_utc=_STARTED,
    )
    assert report_config.dataset_version == "1.1.0"
    assert '"dataset_version":"1.1.0"' in payload
    assert '"prompt_version":"v0.2-s1-planner-5"' in payload
    assert '"dataset_version":"1.0.0"' not in payload
    runs = (tmp_path / "conflict" / conflict_id / "runs.jsonl").read_text(
        encoding="utf-8"
    )
    assert "invalid_configuration" in runs


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "runner_name",
    (
        "_run_phase4_1_development_benchmark",
        "_run_phase4_1_official_benchmark",
    ),
)
@pytest.mark.parametrize(
    ("error", "code", "status", "attempt_count", "benchmark_status"),
    [
        (_TimeoutTransportError("timed out"), "timeout", "infrastructure_error", 3, "incomplete"),
        (_RateLimitedError("429"), "rate_limited", "infrastructure_error", 3, "incomplete"),
        (_Provider5xxError("503"), "provider_5xx", "infrastructure_error", 3, "incomplete"),
        (
            _AuthenticationError("401"),
            "authentication",
            "configuration_error",
            1,
            "pending",
        ),
    ],
)
async def test_phase4_1_wrappers_preserve_frozen_retry_policy(
    dummy_deepseek_key: None,
    tmp_path: Path,
    runner_name: str,
    error: BaseException,
    code: str,
    status: str,
    attempt_count: int,
    benchmark_status: str,
) -> None:
    from signal_diag.evaluation import runner as runner_mod

    runner = getattr(runner_mod, runner_name)
    split: EvaluationSplit = (
        "development"
        if runner_name.endswith("development_benchmark")
        else "held_out"
    )
    case_id = f"case_{split[:3]}_retry_{code}"
    manifest = _phase4_1_mini_manifest((case_id, split))
    report = await runner(
        manifest,
        _phase4_1_mini_config(manifest, benchmark_id=f"bench_p41_{runner_name}_{code}"),
        tmp_path,
        client_factory=_client_factory_for(_raise_handler(error)),
    )
    agent_attempts = [
        attempt
        for attempt in report.attempts
        if attempt.execution_path == "agent"
    ]
    assert len(agent_attempts) == attempt_count
    assert [attempt.attempt_index for attempt in agent_attempts] == list(
        range(1, attempt_count + 1)
    )
    assert all(attempt.run_slot == 1 for attempt in agent_attempts)
    assert all(attempt.case_id == case_id for attempt in agent_attempts)
    assert all(attempt.status == status for attempt in agent_attempts)
    assert all(attempt.error_code == code for attempt in agent_attempts)
    assert not any(score.execution_path == "agent" for score in report.scores)
    assert report.benchmark_status == benchmark_status
    if code in _RETRYABLE:
        assert attempt_count == 1 + report.config.max_infrastructure_retries
    else:
        assert attempt_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "runner_name",
    (
        "_run_phase4_1_development_benchmark",
        "_run_phase4_1_official_benchmark",
    ),
)
@pytest.mark.parametrize(
    ("handler_factory", "expected_reason"),
    [
        (lambda: _invalid_output_handler, "max_planner_retries"),
        (lambda: _no_progress_handler, "no_progress"),
        (lambda: _CountingToolBudget(), {"max_tool_calls", "no_progress"}),
        (lambda: _rule_budget_handler, {"max_rule_evaluations", "no_progress"}),
        (lambda: _CountingKnowledgeBudget(), "max_knowledge_retrievals"),
    ],
    ids=[
        "invalid_model_output",
        "no_progress",
        "tool_budget",
        "rule_budget",
        "knowledge_budget",
    ],
)
async def test_phase4_1_wrappers_preserve_behavioral_no_fallback(
    dummy_deepseek_key: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runner_name: str,
    handler_factory: Callable[[], Callable[..., Any]],
    expected_reason: str | set[str],
) -> None:
    from signal_diag.evaluation import runner as runner_mod

    def boom(*args: object, **kwargs: object) -> object:
        raise AssertionError(
            "Phase 4.1 runner must not wrap RealLLMPlanner with "
            "_ContextBoundScriptedPlanner"
        )

    monkeypatch.setattr(runner_mod, "_ContextBoundScriptedPlanner", boom)
    runner = getattr(runner_mod, runner_name)
    split: EvaluationSplit = (
        "development"
        if runner_name.endswith("development_benchmark")
        else "held_out"
    )
    label = expected_reason if isinstance(expected_reason, str) else "tool_budget"
    case_id = f"case_{split[:3]}_behavior_{label}"
    manifest = _phase4_1_mini_manifest((case_id, split))
    handler = handler_factory()
    report = await runner(
        manifest,
        _phase4_1_mini_config(
            manifest,
            benchmark_id=f"bench_p41_{runner_name}_{label}",
        ),
        tmp_path,
        client_factory=_client_factory_for(handler),
    )
    agent_attempts = [
        attempt
        for attempt in report.attempts
        if attempt.execution_path == "agent"
    ]
    assert len(agent_attempts) == 1
    assert agent_attempts[0].status == "behavior_result"
    assert agent_attempts[0].run_slot == 1
    assert agent_attempts[0].attempt_index == 1
    agent_traces = [trace for trace in report.traces if trace.execution_path == "agent"]
    assert len(agent_traces) == 1
    reason = agent_traces[0].result.termination_reason
    if isinstance(expected_reason, set):
        assert reason in expected_reason
    else:
        assert reason == expected_reason
    assert _ContextBoundScriptedPlanner is not boom


def test_build_phase4_1_planner_is_active_real_llm() -> None:
    from signal_diag.evaluation.runner import _build_phase4_1_planner
    from tests.evaluation.test_runner import _client_from_handler

    planner = _build_phase4_1_planner(
        _client_from_handler(_adaptive_success_handler)
    )
    assert type(planner) is _Phase4V5RealLLMPlanner
    assert isinstance(planner, RealLLMPlanner)
    assert type(planner) is not _Phase4V4RealLLMPlanner
    assert planner.prompt_version == "v0.2-s1-planner-5"


def test_aggregate_benchmark_for_split_signature() -> None:
    from signal_diag.evaluation.scoring import _aggregate_benchmark_for_split

    public = inspect.signature(aggregate_benchmark)
    private = inspect.signature(_aggregate_benchmark_for_split)
    public_params = list(public.parameters)
    private_params = list(private.parameters)
    assert public_params[:6] == [
        "manifest",
        "traces",
        "scores",
        "attempts",
        "config",
        "targets",
    ]
    assert private_params[:6] == public_params[:6]
    assert public_params == [
        "manifest",
        "traces",
        "scores",
        "attempts",
        "config",
        "targets",
        "harness_status",
    ]
    assert public.parameters["harness_status"].kind is inspect.Parameter.KEYWORD_ONLY
    assert "score_split" not in public.parameters
    assert "extra_warnings" not in public.parameters
    assert private.parameters["harness_status"].kind is inspect.Parameter.KEYWORD_ONLY
    assert private.parameters["score_split"].kind is inspect.Parameter.KEYWORD_ONLY
    assert private.parameters["extra_warnings"].kind is inspect.Parameter.KEYWORD_ONLY
    hints = typing.get_type_hints(_aggregate_benchmark_for_split)
    assert hints["harness_status"] is HarnessStatus
    assert hints["score_split"] is EvaluationSplit
    assert hints["return"] is BenchmarkReport
    assert private.parameters["extra_warnings"].default == ()


def test_public_aggregate_benchmark_still_scores_held_out_only() -> None:
    config = _agg_config(repetitions=1)
    clip_case, clip_trace = _legal_clipping_trace()
    harm_case, harm_trace = _legal_harmonic_trace()
    held_clip = _bind_run(
        clip_case, clip_trace, config, case_id="case_agg_held_clip_01"
    )
    held_harm = _bind_run(
        harm_case, harm_trace, config, case_id="case_agg_held_harm_01"
    )
    dev_clip = _bind_run(
        clip_case,
        clip_trace,
        config,
        case_id="case_agg_dev_clip_01",
        split="development",
    )
    original_splits = tuple(case.split for case in (held_clip[0], held_harm[0], dev_clip[0]))
    cases = (held_clip[0], held_harm[0], dev_clip[0])
    traces = (held_clip[1], held_harm[1], dev_clip[1])
    scores = (held_clip[2], held_harm[2], dev_clip[2])
    attempts = tuple(_behavior_attempt(trace, latency_ms=10.0) for trace in traces)
    manifest = make_dataset_manifest(
        cases,
        dataset_id=config.dataset_id,
        version=config.dataset_version,
        rule_profile_id=config.rule_profile_id,
        rule_profile_version=config.rule_profile_version,
    )
    report = aggregate_benchmark(
        manifest,
        traces,
        scores,
        attempts,
        config,
        TargetBands(),
        harness_status="accepted",
    )
    assert report.agent_metrics is not None
    assert report.agent_metrics.run_count == 2
    assert {score.case_id for score in report.scores} == {
        "case_agg_held_clip_01",
        "case_agg_held_harm_01",
        "case_agg_dev_clip_01",
    }
    assert _DEV_WARNING not in report.warnings
    assert tuple(case.split for case in manifest.cases) == original_splits
    assert report.benchmark_status == "completed"


def test_aggregate_benchmark_for_split_scores_development_without_mutation() -> None:
    from signal_diag.evaluation.scoring import _aggregate_benchmark_for_split

    config = _agg_config(dataset_version="1.1.0", repetitions=1)
    clip_case, clip_trace = _legal_clipping_trace()
    harm_case, harm_trace = _legal_harmonic_trace()
    held_clip = _bind_run(
        clip_case, clip_trace, config, case_id="case_split_held_clip_01"
    )
    dev_clip = _bind_run(
        clip_case,
        clip_trace,
        config,
        case_id="case_split_dev_clip_01",
        split="development",
    )
    dev_harm = _bind_run(
        harm_case,
        harm_trace,
        config,
        case_id="case_split_dev_harm_01",
        split="development",
    )
    cases = (held_clip[0], dev_clip[0], dev_harm[0])
    original_splits = tuple(case.split for case in cases)
    original_ids = tuple(case.case_id for case in cases)
    traces = (held_clip[1], dev_clip[1], dev_harm[1])
    scores = (held_clip[2], dev_clip[2], dev_harm[2])
    attempts = tuple(_behavior_attempt(trace, latency_ms=10.0) for trace in traces)
    manifest = make_dataset_manifest(
        cases,
        dataset_id=config.dataset_id,
        version=config.dataset_version,
        rule_profile_id=config.rule_profile_id,
        rule_profile_version=config.rule_profile_version,
    )
    report = _aggregate_benchmark_for_split(
        manifest,
        traces,
        scores,
        attempts,
        config,
        TargetBands(),
        harness_status="accepted",
        score_split="development",
        extra_warnings=(_DEV_WARNING,),
    )
    assert report.agent_metrics is not None
    assert report.agent_metrics.run_count == 2
    assert {score.case_id for score in report.scores if score.execution_path == "agent"} >= {
        "case_split_dev_clip_01",
        "case_split_dev_harm_01",
        "case_split_held_clip_01",
    }
    assert _DEV_WARNING in report.warnings
    assert tuple(case.split for case in manifest.cases) == original_splits
    assert tuple(case.case_id for case in manifest.cases) == original_ids
    assert report.benchmark_status == "completed"
    public = aggregate_benchmark(
        manifest,
        traces,
        scores,
        attempts,
        config,
        TargetBands(),
        harness_status="accepted",
    )
    assert public.agent_metrics is not None
    assert public.agent_metrics.run_count == 1
    assert _DEV_WARNING not in public.warnings


def test_complete_40_slot_development_report_may_meet_target() -> None:
    from signal_diag.evaluation.scoring import _aggregate_benchmark_for_split

    config = _agg_config(dataset_version="1.1.0", repetitions=5)
    clip_case, clip_trace = _legal_clipping_trace()
    harm_case, harm_trace = _legal_harmonic_trace()
    runs = []
    for index in range(4):
        clip_id = f"case_dev40_clip_{index + 1:02d}"
        harm_id = f"case_dev40_harm_{index + 1:02d}"
        for slot in range(1, 6):
            runs.append(
                _bind_run(
                    clip_case,
                    clip_trace,
                    config,
                    case_id=clip_id,
                    split="development",
                    run_slot=slot,
                )
            )
            runs.append(
                _bind_run(
                    harm_case,
                    harm_trace,
                    config,
                    case_id=harm_id,
                    split="development",
                    run_slot=slot,
                )
            )
    cases_by_id = {run[0].case_id: run[0] for run in runs}
    traces = tuple(run[1] for run in runs)
    scores = tuple(run[2] for run in runs)
    attempts = tuple(_behavior_attempt(trace, latency_ms=10.0) for trace in traces)
    manifest = make_dataset_manifest(
        tuple(cases_by_id.values()),
        dataset_id=config.dataset_id,
        version=config.dataset_version,
        rule_profile_id=config.rule_profile_id,
        rule_profile_version=config.rule_profile_version,
    )
    complete = _aggregate_benchmark_for_split(
        manifest,
        traces,
        scores,
        attempts,
        config,
        TargetBands(),
        harness_status="accepted",
        score_split="development",
        extra_warnings=(_DEV_WARNING,),
    )
    assert len([score for score in complete.scores if score.execution_path == "agent"]) == 40
    assert complete.benchmark_status == "completed"
    assert complete.target_status == "meets_target"
    assert _DEV_WARNING in complete.warnings

    incomplete = _aggregate_benchmark_for_split(
        manifest,
        traces[:-1],
        scores[:-1],
        attempts[:-1],
        config,
        TargetBands(),
        harness_status="accepted",
        score_split="development",
        extra_warnings=(_DEV_WARNING,),
    )
    assert incomplete.benchmark_status == "incomplete"
    assert incomplete.target_status == "not_evaluated"


def test_official_split_keeps_frozen_status_semantics() -> None:
    from signal_diag.evaluation.scoring import _aggregate_benchmark_for_split

    config = _agg_config(repetitions=1)
    clip_case, clip_trace = _legal_clipping_trace()
    harm_case, harm_trace = _legal_harmonic_trace()
    held_clip = _bind_run(
        clip_case, clip_trace, config, case_id="case_status_held_clip_01"
    )
    held_harm = _bind_run(
        harm_case, harm_trace, config, case_id="case_status_held_harm_01"
    )
    cases = (held_clip[0], held_harm[0])
    traces = (held_clip[1], held_harm[1])
    scores = (held_clip[2], held_harm[2])
    attempts = tuple(_behavior_attempt(trace, latency_ms=10.0) for trace in traces)
    manifest = make_dataset_manifest(
        cases,
        dataset_id=config.dataset_id,
        version=config.dataset_version,
        rule_profile_id=config.rule_profile_id,
        rule_profile_version=config.rule_profile_version,
    )
    completed = _aggregate_benchmark_for_split(
        manifest,
        traces,
        scores,
        attempts,
        config,
        TargetBands(),
        harness_status="accepted",
        score_split="held_out",
    )
    assert completed.benchmark_status == "completed"
    assert _DEV_WARNING not in completed.warnings
    public = aggregate_benchmark(
        manifest,
        traces,
        scores,
        attempts,
        config,
        TargetBands(),
        harness_status="accepted",
    )
    assert public.benchmark_status == completed.benchmark_status
    assert public.target_status == completed.target_status
    assert public.agent_metrics is not None
    assert completed.agent_metrics is not None
    assert public.agent_metrics.run_count == completed.agent_metrics.run_count

    pending_attempt = attempts[0].model_copy(
        update={
            "status": "configuration_error",
            "error_code": "missing_credentials",
            "error_message": "credentials unavailable",
        }
    )
    pending = _aggregate_benchmark_for_split(
        manifest,
        (),
        (),
        (pending_attempt, attempts[1].model_copy(update={"status": "configuration_error", "error_code": "missing_credentials"})),
        config,
        TargetBands(),
        harness_status="pending",
        score_split="held_out",
    )
    assert pending.benchmark_status == "pending"
    assert pending.target_status == "not_evaluated"

    incomplete = _aggregate_benchmark_for_split(
        manifest,
        (traces[0],),
        (scores[0],),
        (attempts[0],),
        config,
        TargetBands(),
        harness_status="accepted",
        score_split="held_out",
    )
    assert incomplete.benchmark_status == "incomplete"


@pytest.mark.asyncio
async def test_phase4_1_wrappers_keep_legacy_official_runner(
    dummy_deepseek_key: None,
    tmp_path: Path,
) -> None:
    from tests.evaluation.test_runner import _mini_config, _mini_manifest

    manifest = _mini_manifest("case_held_legacy_01")
    report = await _run_official_benchmark(
        manifest,
        _mini_config(manifest, benchmark_id="bench_phase4_1_legacy_wrapper"),
        tmp_path,
        client_factory=_client_factory_for(_adaptive_success_handler),
    )
    assert report.benchmark_status == "completed"
    assert report.config.prompt_version == "v0.2-s1-planner-4"
    assert report.config.dataset_version == "1.0.0"
    assert _DEV_WARNING not in report.warnings
