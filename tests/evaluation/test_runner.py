"""Checkpoint N — official runner, retry/status, and CLI safety (T175–T181)."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from signal_diag.agent.planner import _SYSTEM_PROMPT, PROMPT_VERSION
from signal_diag.evaluation.models import (
    AttemptErrorCode,
    BenchmarkConfig,
    BenchmarkReport,
    DatasetManifest,
    PlannerDecisionEvent,
)
from signal_diag.evaluation.runner import (
    _baseline_slot_schedule,
    _ContextBoundScriptedPlanner,
    _held_out_slot_schedule,
    _official_benchmark_config,
    _official_prompt_sha256,
    _run_official_benchmark,
    _scripted_benchmark_config,
)
from tests.evaluation.conftest import make_dataset_manifest, make_evaluation_case

_STARTED = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)
_ASSESSMENT = {
    "task_type": "distortion_analysis",
    "objective": "Determine whether clipping or harmonic distortion explains the signal.",
    "hypotheses": ["clipping", "harmonic_distortion"],
}
_RETRYABLE: tuple[AttemptErrorCode, ...] = ("timeout", "rate_limited", "provider_5xx")
FORBIDDEN_CREDENTIAL_TOKENS = ("api-key", "api_key", "apikey")


def _fingerprint(config: BenchmarkConfig) -> str:
    payload = config.model_dump(mode="json", exclude={"benchmark_id", "started_at_utc"})
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _mini_manifest(*case_ids: str) -> DatasetManifest:
    cases = tuple(
        make_evaluation_case(
            "clean",
            case_id=case_id,
            split="held_out",
        )
        for case_id in case_ids
    )
    return make_dataset_manifest(
        cases,
        dataset_id="runner-mini",
        version="1.0.0",
    )


def _mini_config(
    manifest: DatasetManifest,
    *,
    benchmark_id: str = "bench_task10_mini",
    repetitions: int = 1,
) -> BenchmarkConfig:
    official = _official_benchmark_config(
        benchmark_id=benchmark_id,
        started_at_utc=_STARTED,
    )
    return official.model_copy(
        update={
            "dataset_id": manifest.dataset_id,
            "dataset_version": manifest.version,
            "repetitions": repetitions,
        }
    )


class _MarkedError(Exception):
    _signal_diag_provider_error = True


class _TimeoutTransportError(TimeoutError):
    _signal_diag_provider_error = True


class _RateLimitedError(_MarkedError):
    status_code = 429


class _Provider5xxError(_MarkedError):
    status_code = 503


class _ProviderOtherError(_MarkedError):
    status_code = 400


class _AuthenticationError(_MarkedError):
    status_code = 401


@dataclass
class _FakeMessage:
    content: str | None


@dataclass
class _FakeChoice:
    message: _FakeMessage


@dataclass
class _FakeUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass
class _FakeResponse:
    choices: list[_FakeChoice]
    usage: _FakeUsage | None = None


@dataclass
class _FakeCompletions:
    handler: Callable[..., Any]
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        result = self.handler(**kwargs)
        if hasattr(result, "__await__"):
            result = await result
        return result


@dataclass
class _FakeChat:
    completions: _FakeCompletions


@dataclass
class _FakeClient:
    chat: _FakeChat


def _client_from_handler(handler: Callable[..., Any]) -> _FakeClient:
    return _FakeClient(_FakeChat(_FakeCompletions(handler)))


def _json_response(payload: dict[str, Any], *, usage: _FakeUsage | None = None) -> _FakeResponse:
    return _FakeResponse(
        [_FakeChoice(_FakeMessage(json.dumps(payload)))],
        usage=usage,
    )


def _context_from_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    messages = kwargs["messages"]
    user = json.loads(messages[1]["content"])
    return user["planner_context"]


def _adaptive_success_handler(**kwargs: Any) -> _FakeResponse:
    context = _context_from_kwargs(kwargs)
    evidence = context.get("evidence") or []
    batches = context.get("rule_evaluation_batches") or []
    if not evidence:
        return _json_response(
            {
                "decision_type": "call_tool",
                "task_assessment": _ASSESSMENT,
                "call": {"tool_name": "detect_clipping", "args": {}},
                "purpose": "Obtain clipping evidence before further distortion analysis.",
            },
            usage=_FakeUsage(prompt_tokens=9, completion_tokens=4, total_tokens=13),
        )
    if not batches:
        refs = [item["evidence_id"] for item in evidence]
        return _json_response(
            {
                "decision_type": "evaluate_rules",
                "profile_id": "profile_s1_distortion",
                "evidence_refs": refs,
                "purpose": "Apply configured clipping and THD limits.",
            }
        )
    evidence_refs = [item["evidence_id"] for item in evidence]
    rule_refs = [
        item["evaluation_id"]
        for batch in batches
        for item in batch.get("evaluations", [])
    ]
    return _json_response(
        {
            "decision_type": "finish",
            "outcome": "no_supported_fault",
            "claims": [
                {
                    "claim_id": "claim_clean_1",
                    "fault_type": "no_supported_fault",
                    "statement": "Clipping and harmonic metrics show no supported fault.",
                    "evidence_refs": evidence_refs,
                    "rule_refs": rule_refs,
                }
            ],
            "confidence_label": "high",
        }
    )


def _wrong_outcome_handler(**kwargs: Any) -> _FakeResponse:
    context = _context_from_kwargs(kwargs)
    evidence = context.get("evidence") or []
    if not evidence:
        return _adaptive_success_handler(**kwargs)
    return _json_response(
        {
            "decision_type": "finish",
            "task_assessment": _ASSESSMENT,
            "outcome": "inconclusive",
            "claims": [],
            "confidence_label": "low",
            "limitations": ["forced miss for target-status coverage"],
        }
    )


def _invalid_output_handler(**kwargs: Any) -> _FakeResponse:
    return _FakeResponse([_FakeChoice(_FakeMessage("not-json"))])


def _empty_output_handler(**kwargs: Any) -> _FakeResponse:
    return _FakeResponse([_FakeChoice(_FakeMessage(""))])


def _no_progress_handler(**kwargs: Any) -> _FakeResponse:
    return _json_response(
        {
            "decision_type": "call_tool",
            "task_assessment": _ASSESSMENT,
            "call": {"tool_name": "detect_clipping", "args": {}},
            "purpose": "Repeat the same clipping call.",
        }
    )


def _rule_budget_handler(**kwargs: Any) -> _FakeResponse:
    context = _context_from_kwargs(kwargs)
    if not (context.get("evidence") or []):
        return _adaptive_success_handler(**kwargs)
    refs = [item["evidence_id"] for item in context["evidence"]]
    return _json_response(
        {
            "decision_type": "evaluate_rules",
            "task_assessment": _ASSESSMENT,
            "profile_id": "profile_s1_distortion",
            "evidence_refs": refs,
            "purpose": "Repeat rule evaluation until the budget is exhausted.",
        }
    )


class _CountingKnowledgeBudget:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, **kwargs: Any) -> _FakeResponse:
        self.calls += 1
        return _json_response(
            {
                "decision_type": "retrieve_knowledge",
                "task_assessment": _ASSESSMENT,
                "query_text": f"clipping harmonic distortion {self.calls}",
                "tags": ["clipping", f"topic-{self.calls}"],
                "purpose": "Repeat knowledge retrieval until the budget is exhausted.",
            }
        )


def _tool_budget_handler(**kwargs: Any) -> _FakeResponse:
    tools = (
        "detect_clipping",
        "analyze_harmonic_distortion",
        "analyze_spectrum",
        "estimate_fundamental",
    )
    calls = kwargs.get("_call_count", 0)
    tool_name = tools[calls % len(tools)]
    return _json_response(
        {
            "decision_type": "call_tool",
            "task_assessment": _ASSESSMENT,
            "call": {"tool_name": tool_name, "args": {}},
            "purpose": f"Call {tool_name} until a tool budget terminates the run.",
        }
    )


class _CountingToolBudget:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, **kwargs: Any) -> _FakeResponse:
        kwargs["_call_count"] = self.calls
        self.calls += 1
        return _tool_budget_handler(**kwargs)


def _raise_handler(error: BaseException) -> Callable[..., Any]:
    def handler(**kwargs: Any) -> _FakeResponse:
        raise error

    return handler


def _client_factory_for(handler: Callable[..., Any]) -> Callable[[], _FakeClient]:
    def factory() -> _FakeClient:
        return _client_from_handler(handler)

    return factory


@pytest.fixture
def dummy_deepseek_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-not-a-real-key")


def test_t175_official_configuration_fingerprint_records_pins() -> None:
    assert PROMPT_VERSION == "v0.2-s1-planner-4"
    expected_hash = hashlib.sha256(_SYSTEM_PROMPT.encode("utf-8")).hexdigest()
    assert _official_prompt_sha256() == expected_hash
    config = _official_benchmark_config(
        benchmark_id="bench_task10_official",
        started_at_utc=_STARTED,
    )
    assert config.provider == "deepseek"
    assert config.model == "deepseek-v4-flash"
    assert config.prompt_version == "v0.2-s1-planner-4"
    assert config.prompt_sha256 == expected_hash
    assert config.repetitions == 5
    assert config.max_infrastructure_retries == 2
    assert config.max_concurrency == 1
    assert config.model_parameters["temperature"] == 0.0
    assert config.model_parameters["response_format"] == {"type": "json_object"}
    assert config.model_parameters["thinking"] == {"type": "disabled"}
    assert "api_key" not in config.model_dump(mode="json")
    rerun = _official_benchmark_config(
        benchmark_id="bench_task10_official_rerun",
        started_at_utc=datetime(2026, 8, 30, 8, 0, tzinfo=UTC),
    )
    assert _fingerprint(config) == _fingerprint(rerun)
    omitted = config.model_copy(update={"model_parameters": {}})
    assert _fingerprint(omitted) != _fingerprint(config)


def test_t176_held_out_schedule_is_round_robin_then_baseline(
    official_manifest: DatasetManifest,
) -> None:
    config = _official_benchmark_config(
        benchmark_id="bench_task10_schedule",
        started_at_utc=_STARTED,
    )
    held_out = [case for case in official_manifest.cases if case.split == "held_out"]
    assert len(held_out) == 16
    expected_agent = tuple(
        (case.case_id, run_slot)
        for run_slot in range(1, config.repetitions + 1)
        for case in official_manifest.cases
        if case.split == "held_out"
    )
    agent_slots = _held_out_slot_schedule(official_manifest, config)
    assert agent_slots == expected_agent
    assert len(agent_slots) == 80
    assert [slot for _, slot in agent_slots[:16]] == [1] * 16
    assert [slot for _, slot in agent_slots[16:32]] == [2] * 16
    assert agent_slots[0][0] == held_out[0].case_id
    assert agent_slots[16][0] == held_out[0].case_id
    assert config.max_concurrency == 1
    baseline_slots = _baseline_slot_schedule(official_manifest)
    assert baseline_slots == tuple(
        (case.case_id, 1) for case in official_manifest.cases
    )
    assert len(baseline_slots) == 24


@pytest.mark.asyncio
async def test_t176_execution_follows_schedule_order(
    dummy_deepseek_key: None,
    tmp_path: Path,
) -> None:
    manifest = _mini_manifest("case_held_alpha", "case_held_beta")
    config = _mini_config(manifest, repetitions=2)
    report = await _run_official_benchmark(
        manifest,
        config,
        tmp_path,
        client_factory=_client_factory_for(_adaptive_success_handler),
    )
    agent_attempts = [
        attempt
        for attempt in report.attempts
        if attempt.execution_path == "agent" and attempt.status == "behavior_result"
    ]
    assert [
        (attempt.case_id, attempt.run_slot) for attempt in agent_attempts
    ] == [
        ("case_held_alpha", 1),
        ("case_held_beta", 1),
        ("case_held_alpha", 2),
        ("case_held_beta", 2),
    ]
    baseline_attempts = [
        attempt
        for attempt in report.attempts
        if attempt.execution_path == "fixed_pipeline"
    ]
    assert [
        (attempt.case_id, attempt.run_slot) for attempt in baseline_attempts
    ] == [("case_held_alpha", 1), ("case_held_beta", 1)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "code", "status", "attempt_count", "benchmark_status"),
    [
        (_TimeoutTransportError("timed out"), "timeout", "infrastructure_error", 3, "incomplete"),
        (_RateLimitedError("429"), "rate_limited", "infrastructure_error", 3, "incomplete"),
        (_Provider5xxError("503"), "provider_5xx", "infrastructure_error", 3, "incomplete"),
        (_ProviderOtherError("400"), "provider_other", "infrastructure_error", 1, "incomplete"),
        (
            _AuthenticationError("401"),
            "authentication",
            "configuration_error",
            1,
            "pending",
        ),
    ],
)
async def test_t178_infrastructure_retry_policy(
    dummy_deepseek_key: None,
    tmp_path: Path,
    error: BaseException,
    code: str,
    status: str,
    attempt_count: int,
    benchmark_status: str,
) -> None:
    manifest = _mini_manifest("case_held_retry_01")
    config = _mini_config(
        manifest,
        benchmark_id=f"bench_task10_{code}",
    )
    report = await _run_official_benchmark(
        manifest,
        config,
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
    assert all(attempt.case_id == "case_held_retry_01" for attempt in agent_attempts)
    assert all(attempt.status == status for attempt in agent_attempts)
    assert all(attempt.error_code == code for attempt in agent_attempts)
    assert not any(score.execution_path == "agent" for score in report.scores)
    assert report.benchmark_status == benchmark_status
    if code in _RETRYABLE:
        assert attempt_count == 1 + config.max_infrastructure_retries
    else:
        assert attempt_count == 1


@pytest.mark.asyncio
async def test_t178_retryable_timeout_keeps_original_slot_after_success(
    dummy_deepseek_key: None,
    tmp_path: Path,
) -> None:
    remaining = {"timeouts": 2}

    def handler(**kwargs: Any) -> _FakeResponse:
        if remaining["timeouts"] > 0:
            remaining["timeouts"] -= 1
            raise _TimeoutTransportError("temporary timeout")
        return _adaptive_success_handler(**kwargs)

    manifest = _mini_manifest("case_held_retry_ok")
    config = _mini_config(manifest, benchmark_id="bench_task10_retry_ok")
    report = await _run_official_benchmark(
        manifest,
        config,
        tmp_path,
        client_factory=_client_factory_for(handler),
    )
    agent_attempts = [
        attempt
        for attempt in report.attempts
        if attempt.execution_path == "agent"
    ]
    assert [attempt.status for attempt in agent_attempts] == [
        "infrastructure_error",
        "infrastructure_error",
        "behavior_result",
    ]
    assert [attempt.attempt_index for attempt in agent_attempts] == [1, 2, 3]
    assert {attempt.run_slot for attempt in agent_attempts} == {1}
    agent_scores = [score for score in report.scores if score.execution_path == "agent"]
    assert len(agent_scores) == 1
    assert agent_scores[0].run_slot == 1
    assert agent_scores[0].case_id == "case_held_retry_ok"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("handler_factory", "expected_reason"),
    [
        (lambda: _invalid_output_handler, "max_planner_retries"),
        (lambda: _empty_output_handler, "max_planner_retries"),
        (lambda: _no_progress_handler, "no_progress"),
        (lambda: _CountingToolBudget(), {"max_tool_calls", "no_progress"}),
        (lambda: _rule_budget_handler, {"max_rule_evaluations", "no_progress"}),
        (lambda: _CountingKnowledgeBudget(), "max_knowledge_retrievals"),
    ],
    ids=[
        "invalid_model_output",
        "planner_retry_exhaustion",
        "no_progress",
        "tool_budget",
        "rule_budget",
        "knowledge_budget",
    ],
)
async def test_t179_behavioral_failures_keep_original_slot(
    dummy_deepseek_key: None,
    tmp_path: Path,
    handler_factory: Callable[[], Callable[..., Any]],
    expected_reason: str | set[str],
) -> None:
    handler = handler_factory()
    label = expected_reason if isinstance(expected_reason, str) else "tool_budget"
    manifest = _mini_manifest("case_held_behavior_01")
    config = _mini_config(
        manifest,
        benchmark_id=f"bench_task10_behavior_{label}",
    )
    report = await _run_official_benchmark(
        manifest,
        config,
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
    assert agent_traces[0].run_slot == 1
    reason = agent_traces[0].result.termination_reason
    if isinstance(expected_reason, set):
        assert reason in expected_reason
    else:
        assert reason == expected_reason


@pytest.mark.asyncio
async def test_official_trace_keeps_empty_delta_planner_decisions(
    dummy_deepseek_key: None,
    tmp_path: Path,
) -> None:
    manifest = _mini_manifest("case_held_no_progress_keep_01")
    report = await _run_official_benchmark(
        manifest,
        _mini_config(manifest, benchmark_id="bench_fixwave_keep_planner"),
        tmp_path,
        client_factory=_client_factory_for(_no_progress_handler),
    )
    agent_traces = [trace for trace in report.traces if trace.execution_path == "agent"]
    agent_scores = [score for score in report.scores if score.execution_path == "agent"]
    assert len(agent_traces) == 1
    assert len(agent_scores) == 1
    planner_events = [
        event
        for event in agent_traces[0].events
        if isinstance(event, PlannerDecisionEvent)
    ]
    assert len(planner_events) == 3
    assert agent_scores[0].planner_calls == 3
    assert agent_scores[0].tool_actions == 3
    assert agent_scores[0].unnecessary_tool_actions >= 2
    assert agent_traces[0].result.termination_reason == "no_progress"


class _PrivateProviderBodyError(_MarkedError):
    status_code = 500

    def __str__(self) -> str:
        return (
            '{"choices":[{"message":{"content":'
            '"PRIVATE_PROVIDER_BODY_DO_NOT_PERSIST"}}]}'
        )


@pytest.mark.asyncio
async def test_attempt_record_redacts_raw_provider_body(
    dummy_deepseek_key: None,
    tmp_path: Path,
) -> None:
    private = "PRIVATE_PROVIDER_BODY_DO_NOT_PERSIST"
    error = _PrivateProviderBodyError()
    assert private in str(error)
    manifest = _mini_manifest("case_held_redact_01")
    report = await _run_official_benchmark(
        manifest,
        _mini_config(manifest, benchmark_id="bench_fixwave_redact"),
        tmp_path,
        client_factory=_client_factory_for(_raise_handler(error)),
    )
    agent_attempts = [
        attempt
        for attempt in report.attempts
        if attempt.execution_path == "agent"
    ]
    assert agent_attempts
    for attempt in agent_attempts:
        assert attempt.error_message is not None
        assert private not in attempt.error_message
        assert "choices" not in (attempt.error_message or "")
        assert type(error).__name__ in attempt.error_message
        assert "500" in attempt.error_message
    bundle = tmp_path / "bench_fixwave_redact" / "runs.jsonl"
    raw = bundle.read_text(encoding="utf-8")
    assert private not in raw
    assert '"choices"' not in raw or private not in raw


@pytest.mark.asyncio
async def test_markdown_failures_cover_unscored_missing_credentials(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    manifest = _mini_manifest("case_held_md_fail_01")
    report = await _run_official_benchmark(
        manifest,
        _mini_config(manifest, benchmark_id="bench_fixwave_md_failures"),
        tmp_path,
    )
    assert {attempt.error_code for attempt in report.attempts} == {
        "missing_credentials"
    }
    runs = (tmp_path / "bench_fixwave_md_failures" / "runs.jsonl").read_text(
        encoding="utf-8"
    )
    assert "missing_credentials" in runs
    assert "configuration_error" in runs
    markdown = (tmp_path / "bench_fixwave_md_failures" / "report.md").read_text(
        encoding="utf-8"
    )
    failures = markdown.split("## Failures", 1)[1].split("## ", 1)[0]
    body_lines = [line.strip() for line in failures.splitlines() if line.strip()]
    assert body_lines
    assert body_lines != ["none"]
    assert "missing_credentials" in failures or "configuration_error" in failures


@pytest.mark.asyncio
async def test_t180_preflight_failures_are_pending_before_results(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    manifest = _mini_manifest("case_held_pending_01")
    missing_creds = await _run_official_benchmark(
        manifest,
        _mini_config(manifest, benchmark_id="bench_task10_pending_creds"),
        tmp_path / "creds",
    )
    assert missing_creds.benchmark_status == "pending"
    assert missing_creds.target_status == "not_evaluated"
    assert {attempt.error_code for attempt in missing_creds.attempts} == {
        "missing_credentials"
    }
    assert all(
        attempt.status == "configuration_error" for attempt in missing_creds.attempts
    )
    assert not any(score.execution_path == "agent" for score in missing_creds.scores)

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-not-a-real-key")

    def boom_import() -> object:
        raise ImportError("openai missing")

    missing_dep = await _run_official_benchmark(
        manifest,
        _mini_config(manifest, benchmark_id="bench_task10_pending_dep"),
        tmp_path / "dep",
        import_openai=boom_import,
    )
    assert missing_dep.benchmark_status == "pending"
    assert {attempt.error_code for attempt in missing_dep.attempts} == {
        "missing_dependency"
    }

    official = _official_benchmark_config(
        benchmark_id="bench_task10_pending_cfg",
        started_at_utc=_STARTED,
    )
    invalid = official.model_copy(
        update={
            "dataset_id": manifest.dataset_id,
            "dataset_version": manifest.version,
            "prompt_sha256": "ab" * 32,
            "repetitions": 1,
        }
    )
    invalid_cfg = await _run_official_benchmark(
        manifest,
        invalid,
        tmp_path / "cfg",
        client_factory=_client_factory_for(_adaptive_success_handler),
    )
    assert invalid_cfg.benchmark_status == "pending"
    assert {attempt.error_code for attempt in invalid_cfg.attempts} == {
        "invalid_configuration"
    }


@pytest.mark.asyncio
async def test_t180_status_after_results_and_completed_gate(
    dummy_deepseek_key: None,
    tmp_path: Path,
    official_manifest: DatasetManifest,
) -> None:
    official = _official_benchmark_config(
        benchmark_id="bench_task10_completed_gate",
        started_at_utc=_STARTED,
    )
    assert len(_held_out_slot_schedule(official_manifest, official)) == 80

    finished_slots = {"count": 0}

    def handler(**kwargs: Any) -> _FakeResponse:
        if finished_slots["count"] >= 1:
            raise _AuthenticationError("lost credentials after a result")
        response = _adaptive_success_handler(**kwargs)
        payload = json.loads(response.choices[0].message.content or "")
        if payload.get("decision_type") == "finish":
            finished_slots["count"] += 1
        return response

    manifest = _mini_manifest("case_held_alpha", "case_held_beta")
    incomplete = await _run_official_benchmark(
        manifest,
        _mini_config(manifest, benchmark_id="bench_task10_incomplete"),
        tmp_path / "incomplete",
        client_factory=_client_factory_for(handler),
    )
    assert any(
        score.execution_path == "agent" and score.run_slot == 1
        for score in incomplete.scores
    )
    assert incomplete.benchmark_status == "incomplete"
    assert incomplete.target_status == "not_evaluated"

    completed_manifest = _mini_manifest("case_held_complete_01")
    completed = await _run_official_benchmark(
        completed_manifest,
        _mini_config(completed_manifest, benchmark_id="bench_task10_completed"),
        tmp_path / "completed",
        client_factory=_client_factory_for(_adaptive_success_handler),
    )
    assert completed.benchmark_status == "completed"
    assert len([s for s in completed.scores if s.execution_path == "agent"]) == 1

    missed = await _run_official_benchmark(
        completed_manifest,
        _mini_config(completed_manifest, benchmark_id="bench_task10_below_target"),
        tmp_path / "below",
        client_factory=_client_factory_for(_wrong_outcome_handler),
    )
    assert missed.benchmark_status == "completed"
    assert missed.target_status == "below_target"


@pytest.mark.asyncio
async def test_t177_held_out_benchmark_id_is_append_only(
    dummy_deepseek_key: None,
    tmp_path: Path,
) -> None:
    manifest = _mini_manifest("case_held_append_01")
    config = _mini_config(manifest, benchmark_id="bench_task10_append")
    first = await _run_official_benchmark(
        manifest,
        config,
        tmp_path,
        client_factory=_client_factory_for(_adaptive_success_handler),
    )
    assert any(score.execution_path == "agent" for score in first.scores)
    with pytest.raises(FileExistsError):
        await _run_official_benchmark(
            manifest,
            config,
            tmp_path,
            client_factory=_client_factory_for(_adaptive_success_handler),
        )


@pytest.mark.asyncio
async def test_real_runner_injects_real_planner_not_scripted_binder(
    dummy_deepseek_key: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*args: object, **kwargs: object) -> object:
        raise AssertionError(
            "official runner must not wrap RealLLMPlanner with "
            "_ContextBoundScriptedPlanner"
        )

    monkeypatch.setattr(
        "signal_diag.evaluation.runner._ContextBoundScriptedPlanner",
        boom,
    )
    manifest = _mini_manifest("case_held_binder_01")
    report = await _run_official_benchmark(
        manifest,
        _mini_config(manifest, benchmark_id="bench_task10_binder"),
        tmp_path,
        client_factory=_client_factory_for(_adaptive_success_handler),
    )
    assert report.benchmark_status == "completed"
    assert _ContextBoundScriptedPlanner is not boom


def test_t181_cli_and_report_models_have_no_credential_argument() -> None:
    from signal_diag.evaluation.__main__ import build_parser

    parser = build_parser()
    help_text = parser.format_help().lower()
    for token in FORBIDDEN_CREDENTIAL_TOKENS:
        assert token not in help_text
    subparsers = [
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    ]
    assert subparsers
    names = set(subparsers[0].choices)
    assert names == {
        "validate-dataset",
        "run-deterministic",
        "run-real",
        "render-report",
    }
    for name, subparser in subparsers[0].choices.items():
        sub_help = subparser.format_help().lower()
        for token in FORBIDDEN_CREDENTIAL_TOKENS:
            assert token not in sub_help, name
        for action in subparser._actions:
            for option in action.option_strings:
                lowered = option.lower()
                for token in FORBIDDEN_CREDENTIAL_TOKENS:
                    assert token not in lowered, option
    field_names = set(BenchmarkReport.model_fields) | set(BenchmarkConfig.model_fields)
    assert field_names.isdisjoint(
        {"api_key", "apikey", "authorization", "password", "secret", "credentials"}
    )


def test_t181_public_surface_has_no_provider_sdk_type() -> None:
    from signal_diag import evaluation

    dumped = json.dumps(
        {
            name: str(getattr(evaluation, name))
            for name in evaluation.__all__
        }
    ).lower()
    assert "openai" not in dumped
    assert "asyncopenai" not in dumped.replace(" ", "")
    source = Path(evaluation.__file__).read_text(encoding="utf-8").lower()
    assert "openai" not in source
    main_source = (
        Path(evaluation.__file__).with_name("__main__.py").read_text(encoding="utf-8")
    )
    lowered = main_source.lower()
    assert "from openai" not in lowered
    assert "import openai" not in lowered
    assert "--api-key" not in lowered


def test_scripted_benchmark_config_uses_scripted_identity() -> None:
    manifest = make_dataset_manifest(
        (
            make_evaluation_case(
                "clean",
                case_id="case_scripted_identity_01",
                split="held_out",
            ),
        ),
        dataset_id="s1-distortion-synthetic",
        version="1.0.0",
        rule_profile_id="profile_s1_distortion",
        rule_profile_version="1.0.0-demo",
    )
    config = _scripted_benchmark_config(
        manifest,
        benchmark_id="bench_scripted_identity",
        started_at_utc=_STARTED,
    )
    assert config.repetitions == 1
    assert config.provider is None
    assert config.model is None
    assert config.prompt_version is None
    assert config.prompt_sha256 is None
    assert config.model_parameters == {}
    assert config.sdk_versions == {}
    assert config.dataset_id == manifest.dataset_id
    assert config.dataset_version == manifest.version
    assert config.rule_profile_id == manifest.rule_profile_id
    assert config.rule_profile_version == manifest.rule_profile_version


def test_run_deterministic_cli_writes_scripted_identity_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from signal_diag.evaluation import __main__ as cli

    captured: dict[str, BenchmarkConfig] = {}

    async def fake_run(
        manifest: DatasetManifest,
        config: BenchmarkConfig,
        output_dir: Path,
        **kwargs: object,
    ) -> SimpleNamespace:
        captured["config"] = config
        return SimpleNamespace(benchmark_status="completed")

    monkeypatch.setattr(cli, "_run_deterministic_benchmark", fake_run)
    code = cli.main(
        [
            "run-deterministic",
            "--benchmark-id",
            "bench_scripted_cli",
            "--output-dir",
            str(tmp_path),
        ]
    )
    assert code == 0
    config = captured["config"]
    assert config.repetitions == 1
    assert config.provider is None
    assert config.model is None
    assert config.prompt_version is None
    assert config.prompt_sha256 is None
    assert config.dataset_id == "s1-distortion-synthetic"
    assert config.dataset_version == "1.0.0"
