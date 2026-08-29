"""Unit-check Phase 3 real-model runner without network calls."""

from __future__ import annotations

import importlib.util
import inspect
import io
import os
import subprocess
import sys
from contextlib import redirect_stderr
from pathlib import Path
from types import ModuleType

import pytest

from signal_diag.agent.planner import RealLLMPlanner, ScriptedPlanner
from signal_diag.knowledge.index import KnowledgeIndex
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal import InMemorySignalRepository

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = PROJECT_ROOT / "scripts" / "run_phase3_real_model_eval.py"
PHASE2_RUNNER_PATH = PROJECT_ROOT / "scripts" / "run_real_model_eval.py"
S1_PROFILE_PATH = (
    PROJECT_ROOT
    / "src"
    / "signal_diag"
    / "rules"
    / "profiles"
    / "s1_distortion_v1.yaml"
)
CORPUS_PATH = PROJECT_ROOT / "src" / "signal_diag" / "knowledge" / "corpus"

PHASE2_CASE_IDS = (
    "S1-CLIP-SUBFS",
    "S1-HARM",
    "S1-CLEAN",
    "S1-NOISE",
)


def _load_runner() -> ModuleType:
    assert RUNNER_PATH.is_file(), f"missing Phase 3 runner: {RUNNER_PATH}"
    spec = importlib.util.spec_from_file_location(
        "run_phase3_real_model_eval",
        RUNNER_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_help_exits_zero_without_network() -> None:
    runner = _load_runner()
    with pytest.raises(SystemExit) as exited:
        runner.main(["--help"])
    assert exited.value.code == 0


def test_cli_help_uses_worktree_package_without_network() -> None:
    result = subprocess.run(
        [sys.executable, str(RUNNER_PATH), "--help"],
        check=False,
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        env={key: value for key, value in os.environ.items() if key != "DEEPSEEK_API_KEY"},
    )
    assert result.returncode == 0
    assert "No module named" not in result.stderr
    assert "RuleEngine" in result.stdout or "KnowledgeIndex" in result.stdout


def test_missing_credentials_exits_nonzero_and_does_not_use_scripted_planner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _load_runner()
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    stderr = io.StringIO()
    with redirect_stderr(stderr):
        code = runner.main(["--output-dir", "real_model_eval_output/phase3"])
    assert code != 0
    message = stderr.getvalue()
    assert "DEEPSEEK_API_KEY" in message
    assert "does not fall back to ScriptedPlanner" in message
    assert "ScriptedPlanner" not in inspect.getsource(runner.build_planner)
    assert "ScriptedPlanner" not in inspect.getsource(runner.build_phase3_runtime)


def test_runtime_injects_explicit_rule_and_knowledge_dependencies() -> None:
    runner = _load_runner()
    repository = InMemorySignalRepository()
    planner = runner.build_planner()
    runtime = runner.build_phase3_runtime(
        repository=repository,
        planner=planner,
    )
    assert isinstance(planner, RealLLMPlanner)
    assert not isinstance(planner, ScriptedPlanner)
    assert isinstance(runtime._planner, RealLLMPlanner)
    assert isinstance(runtime._rule_engine, RuleEngine)
    assert isinstance(runtime._rule_profile_loader, YamlRuleProfileLoader)
    assert runtime._rule_profile_loader._profile_paths == {
        "profile_s1_distortion": S1_PROFILE_PATH
    }
    assert isinstance(runtime._knowledge_index, KnowledgeIndex)
    assert runtime._knowledge_index._corpus_root == CORPUS_PATH


def test_eval_cases_reuse_phase2_s1_definitions() -> None:
    runner = _load_runner()
    case_ids = tuple(item.case_id for item in runner.EVAL_CASES)
    assert case_ids == PHASE2_CASE_IDS
    phase2_source = PHASE2_RUNNER_PATH.read_text(encoding="utf-8")
    for case_id in PHASE2_CASE_IDS:
        assert case_id in phase2_source


def test_default_output_dir_is_phase3() -> None:
    runner = _load_runner()
    parser = runner.build_arg_parser()
    args = parser.parse_args([])
    assert Path(args.output_dir) == Path("real_model_eval_output/phase3")


def test_trace_safety_rejects_full_fft_arrays() -> None:
    runner = _load_runner()
    with pytest.raises(RuntimeError, match="full FFT"):
        runner.assert_trace_is_safe({"spectrum": {"frequencies_hz": [0.0, 1.0]}})
    with pytest.raises(RuntimeError, match="full FFT"):
        runner.assert_trace_is_safe({"spectrum": {"magnitude_db": [0.0]}})


def test_summarize_case_records_rule_knowledge_and_refs() -> None:
    runner = _load_runner()
    summary = runner.summarize_case(
        case_id="S1-CLEAN",
        ground_truth="no supported fault",
        planner=runner.build_planner(),
        elapsed_s=0.0,
        result=_offline_result_stub(),
        provider_usage=None,
    )
    required = {
        "case_id",
        "ground_truth",
        "model_id",
        "prompt_version",
        "elapsed_s",
        "action_sequence",
        "rule_evaluation_count",
        "knowledge_retrieval_count",
        "diagnosis_refs",
        "provider_usage",
        "trace",
    }
    assert required <= set(summary)


def _offline_result_stub() -> object:
    from signal_diag.agent.models import AgentRunResult

    return AgentRunResult(
        run_id="run_offline_stub",
        status="success",
        diagnosis=None,
        observations=(),
        evidence=(),
        tool_history=(),
        termination_reason="planner_finished",
        rule_evaluation_batches=(),
        knowledge_retrievals=(),
    )
