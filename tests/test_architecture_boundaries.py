"""Architecture boundary verification for Phase 1–4 packages."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

FORBIDDEN = {
    "signal": {
        "signal_diag.dsp",
        "signal_diag.tools",
        "signal_diag.agent",
        "signal_diag.rules",
        "signal_diag.knowledge",
        "signal_diag.evaluation",
        "signal_diag.app",
    },
    "dsp": {
        "signal_diag.tools",
        "signal_diag.agent",
        "signal_diag.rules",
        "signal_diag.knowledge",
        "signal_diag.evaluation",
        "signal_diag.app",
    },
    "tools": {
        "signal_diag.agent",
        "signal_diag.rules",
        "signal_diag.knowledge",
        "signal_diag.evaluation",
        "signal_diag.app",
    },
    "rules": {
        "signal_diag.agent",
        "signal_diag.dsp",
        "signal_diag.knowledge",
        "signal_diag.evaluation",
        "signal_diag.app",
    },
    "knowledge": {
        "signal_diag.agent",
        "signal_diag.rules",
        "signal_diag.dsp",
        "signal_diag.tools",
        "signal_diag.evaluation",
        "signal_diag.app",
    },
    "agent": {
        "signal_diag.evaluation",
        "signal_diag.app",
    },
    "evaluation": {
        "signal_diag.app",
    },
}

# evaluation/ and app/ are implemented. No remaining deferred product packages.
DEFERRED_PACKAGES: tuple[str, ...] = ()

# rules/ and knowledge/ are authorized by the approved Phase 3 contract (OQ-001).
# Pre-implementation: absence is valid. Post-implementation: dependency direction
# is enforced by test_phase3_package_dependency_direction_when_present (T093).
PHASE3_PACKAGES = ("rules", "knowledge")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src" / "signal_diag"


def _imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def find_forbidden_imports(
    layer: str,
    source: str,
    filename: str = "<source>",
) -> list[str]:
    """Return forbidden import module names found in *source* for *layer*."""
    forbidden_prefixes = FORBIDDEN[layer]
    tree = ast.parse(source, filename=filename)
    violations: list[str] = []
    for module in sorted(_imported_modules(tree)):
        for prefix in forbidden_prefixes:
            if module == prefix or module.startswith(f"{prefix}."):
                violations.append(module)
                break
    return violations


def _layer_source_files(layer: str) -> list[Path]:
    layer_dir = SRC_ROOT / layer
    if not layer_dir.exists():
        return []
    return sorted(path for path in layer_dir.rglob("*.py") if path.is_file())


def _collect_layer_violations(layer: str) -> list[str]:
    violations: list[str] = []
    for path in _layer_source_files(layer):
        source = path.read_text(encoding="utf-8")
        for module in find_forbidden_imports(layer, source, str(path)):
            violations.append(f"{path.relative_to(PROJECT_ROOT)} imports {module}")
    return violations


@pytest.mark.parametrize("layer", sorted(FORBIDDEN))
def test_layers_do_not_import_forbidden_modules(layer: str) -> None:
    if layer in PHASE3_PACKAGES and not (SRC_ROOT / layer).exists():
        pytest.skip(f"Phase 3 package {layer}/ not created yet")
    violations = _collect_layer_violations(layer)
    assert not violations, "Forbidden imports detected:\n" + "\n".join(violations)


def test_deferred_packages_are_not_present() -> None:
    """T283: app left deferred packages; no remaining deferred product packages."""
    assert "app" not in DEFERRED_PACKAGES
    assert DEFERRED_PACKAGES == ()


@pytest.mark.parametrize("package_name", PHASE3_PACKAGES)
def test_phase3_package_dependency_direction_when_present(package_name: str) -> None:
    """T093 gate: when rules/ or knowledge/ exist, enforce dependency direction."""
    package_dir = SRC_ROOT / package_name
    if not package_dir.exists():
        pytest.skip(f"Phase 3 package {package_name}/ not created yet")
    violations = _collect_layer_violations(package_name)
    assert not violations, "Forbidden imports detected:\n" + "\n".join(violations)


def test_phase3_packages_are_not_deferred() -> None:
    """Document gate: rules/ and knowledge/ are no longer Phase 1–2 deferred packages."""
    assert "rules" not in DEFERRED_PACKAGES
    assert "knowledge" not in DEFERRED_PACKAGES


def test_agent_may_import_phase3_packages() -> None:
    """Phase 3 runtime integration: agent may depend on rules/ and knowledge/."""
    forbidden = FORBIDDEN["agent"]
    assert "signal_diag.rules" not in forbidden
    assert "signal_diag.knowledge" not in forbidden


def test_t093_forbidden_edges_include_phase3_reverse_deps() -> None:
    """CONTRACTS §37: signal/dsp/tools ↛ rules/knowledge; rules ↛ dsp/knowledge."""
    for layer in ("signal", "dsp", "tools"):
        assert "signal_diag.rules" in FORBIDDEN[layer]
        assert "signal_diag.knowledge" in FORBIDDEN[layer]
    assert "signal_diag.dsp" in FORBIDDEN["rules"]
    assert "signal_diag.knowledge" in FORBIDDEN["rules"]


def test_boundary_helper_detects_forbidden_import_in_memory() -> None:
    source = "from signal_diag.dsp import analyze_clipping\n"
    violations = find_forbidden_imports("signal", source, "fake_signal_module.py")
    assert violations == ["signal_diag.dsp"]


def test_boundary_helper_detects_phase3_reverse_imports_in_memory() -> None:
    assert find_forbidden_imports(
        "signal",
        "from signal_diag.rules import RuleEngine\n",
        "fake_signal_module.py",
    ) == ["signal_diag.rules"]
    assert find_forbidden_imports(
        "dsp",
        "from signal_diag.knowledge import KnowledgeIndex\n",
        "fake_dsp_module.py",
    ) == ["signal_diag.knowledge"]
    assert find_forbidden_imports(
        "tools",
        "import signal_diag.rules.engine\n",
        "fake_tools_module.py",
    ) == ["signal_diag.rules.engine"]
    assert find_forbidden_imports(
        "rules",
        "from signal_diag.dsp import thd\n",
        "fake_rules_module.py",
    ) == ["signal_diag.dsp"]
    assert find_forbidden_imports(
        "rules",
        "from signal_diag.knowledge import KnowledgeIndex\n",
        "fake_rules_module.py",
    ) == ["signal_diag.knowledge"]


PHASE4_UPSTREAM_LAYERS = ("signal", "dsp", "tools", "rules", "knowledge", "agent")
PHASE1_3_PACKAGES = (
    "signal_diag.signal",
    "signal_diag.dsp",
    "signal_diag.tools",
    "signal_diag.rules",
    "signal_diag.knowledge",
    "signal_diag.agent",
)
EVALUATION_PREFIX = "signal_diag.evaluation"
APP_PREFIX = "signal_diag.app"
_PHASE4_3_1_MERGED_BASELINE = "36ae7c9"
WAV_FORBIDDEN_PREFIXES = (
    "signal_diag.app",
    "signal_diag.evaluation",
    "signal_diag.agent",
    "fastapi",
    "openai",
    "langchain",
    "langgraph",
)
ADAPTER_FORBIDDEN_PREFIXES = (
    "signal_diag.dsp",
    "signal_diag.tools",
    "signal_diag.rules",
    "signal_diag.knowledge",
    "signal_diag.agent",
)
STATIC_FORBIDDEN_TOKENS = (
    "detect_clipping",
    "analyze_harmonic_distortion",
    "analyze_spectrum",
    "estimate_fundamental",
    "numpy.fft",
    "autocorrelation",
    "RuleEngine",
    "KnowledgeIndex",
    "DistortionDiagnosisRuntime",
)


def _python_files_under(layer: str) -> list[Path]:
    return _layer_source_files(layer)


def _modules_imported_from(path: Path) -> set[str]:
    return _imported_modules(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))


def _imports_evaluation(modules: set[str]) -> list[str]:
    return sorted(
        module
        for module in modules
        if module == EVALUATION_PREFIX or module.startswith(f"{EVALUATION_PREFIX}.")
    )


def _imports_app(modules: set[str]) -> list[str]:
    return sorted(
        module
        for module in modules
        if module == APP_PREFIX or module.startswith(f"{APP_PREFIX}.")
    )


def _modules_match_prefixes(modules: set[str], prefixes: tuple[str, ...]) -> list[str]:
    hits: list[str] = []
    for module in sorted(modules):
        for prefix in prefixes:
            if module == prefix or module.startswith(f"{prefix}."):
                hits.append(module)
                break
    return hits


def test_t182_evaluation_package_exists() -> None:
    """T182 hard gate: evaluation/ exists once Phase 4 is implemented."""
    assert (SRC_ROOT / "evaluation").is_dir()


def test_t182_evaluation_is_not_deferred() -> None:
    """T182: remove the former deferred-package skip/assert for evaluation/."""
    assert "evaluation" not in DEFERRED_PACKAGES


def test_t182_app_is_not_deferred_and_present() -> None:
    """T182 retarget / T283: Phase 5 app/ exists and is no longer deferred."""
    assert "app" not in DEFERRED_PACKAGES
    assert (SRC_ROOT / "app").is_dir()


def test_t182_upstream_layers_forbid_evaluation() -> None:
    """T182: signal/dsp/tools/rules/knowledge/agent never import evaluation."""
    for layer in PHASE4_UPSTREAM_LAYERS:
        assert "signal_diag.evaluation" in FORBIDDEN[layer]


def test_t182_evaluation_may_import_phase1_3_packages() -> None:
    """T182: evaluation may import accepted Phase 1–3 packages."""
    if "evaluation" in FORBIDDEN:
        for module in PHASE1_3_PACKAGES:
            assert module not in FORBIDDEN["evaluation"]
    imported: set[str] = set()
    for path in _python_files_under("evaluation"):
        imported.update(_modules_imported_from(path))
    assert any(
        module == prefix or module.startswith(f"{prefix}.")
        for module in imported
        for prefix in PHASE1_3_PACKAGES
    )


def test_t182_upstream_sources_do_not_import_evaluation() -> None:
    """T182: parse imports under src/signal_diag; no reverse evaluation deps."""
    violations: list[str] = []
    for layer in PHASE4_UPSTREAM_LAYERS:
        for path in _python_files_under(layer):
            hits = _imports_evaluation(_modules_imported_from(path))
            violations.extend(
                f"{path.relative_to(PROJECT_ROOT)} imports {module}" for module in hits
            )
    assert not violations, "Forbidden evaluation imports detected:\n" + "\n".join(
        violations
    )


def test_boundary_helper_detects_evaluation_reverse_imports_in_memory() -> None:
    source = "from signal_diag.evaluation import score_evaluation_trace\n"
    for layer in PHASE4_UPSTREAM_LAYERS:
        assert find_forbidden_imports(layer, source, f"fake_{layer}_module.py") == [
            "signal_diag.evaluation"
        ]


_PHASE4_DESIGN_BASELINE = "9bd01f2"


def test_t183_diff_check_against_phase4_design_baseline() -> None:
    """T183 quality gate is git diff --check 9bd01f2..HEAD, not unstaged-only."""
    result = subprocess.run(
        ["git", "diff", "--check", f"{_PHASE4_DESIGN_BASELINE}"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


_PHASE4_1_BASELINE = "b68ec5e"
_PHASE4_1_V6_BASELINE = "f9392c2"
_PHASE4_1_V6_ALLOWED_PREFIXES = (
    "AGENTS.md",
    "docs/",
    "src/signal_diag/agent/",
    "src/signal_diag/evaluation/",
    "tests/",
)
_PHASE4_1_V6_FROZEN_PATHS = (
    "src/signal_diag/agent/runtime.py",
    "src/signal_diag/dsp",
    "src/signal_diag/rules",
    "src/signal_diag/knowledge",
    "src/signal_diag/tools",
    "src/signal_diag/signal",
)


def test_t195_diff_check_against_phase4_1_baseline() -> None:
    result = subprocess.run(
        ["git", "diff", "--check", f"{_PHASE4_1_BASELINE}..HEAD"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_t200_diff_check_against_v6_baseline() -> None:
    """T200 quality gate is git diff --check f9392c2..HEAD."""
    result = subprocess.run(
        ["git", "diff", "--check", f"{_PHASE4_1_V6_BASELINE}..HEAD"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_t200_v6_changes_stay_inside_agent_evaluation_tests_docs() -> None:
    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            f"{_PHASE4_1_V6_BASELINE}..{_PHASE4_3_1_MERGED_BASELINE}",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    forbidden = [
        path
        for path in result.stdout.splitlines()
        if path and not path.startswith(_PHASE4_1_V6_ALLOWED_PREFIXES)
    ]
    assert not forbidden, "v6 changes escaped allowed boundaries:\n" + "\n".join(
        forbidden
    )
    app_root = PROJECT_ROOT / "src" / "signal_diag" / "app"
    assert app_root.is_dir()
    frozen = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            f"{_PHASE4_1_V6_BASELINE}..{_PHASE4_3_1_MERGED_BASELINE}",
            "--",
            *_PHASE4_1_V6_FROZEN_PATHS,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert frozen.returncode == 0, frozen.stderr
    assert frozen.stdout.strip() == ""


_PHASE4_2_BASELINE = "aefccba"
_PHASE4_2_ALLOWED_PREFIXES = (
    "AGENTS.md",
    "docs/",
    "src/signal_diag/agent/",
    "src/signal_diag/evaluation/",
    "tests/",
)
_PHASE4_2_FROZEN_PATHS = (
    "src/signal_diag/agent/runtime.py",
    "src/signal_diag/dsp",
    "src/signal_diag/rules",
    "src/signal_diag/knowledge",
    "src/signal_diag/tools",
    "src/signal_diag/signal",
)
_PHASE4_2_REQUIRED_TEST_IDS = tuple(f"T20{index}" for index in range(1, 9))
_PHASE4_2_REQUIRED_T208_TESTS = (
    "test_t208_diff_check_against_phase4_2_baseline",
    "test_t208_phase4_2_changes_stay_inside_allowed_boundaries",
    "test_t208_dependency_direction_forbids_app_and_reverse_evaluation",
    "test_t208_runtime_does_not_construct_forced_actions",
    "test_t208_product_path_does_not_fall_back_to_scripted_planner",
    "test_t208_target_bands_are_not_reduced",
    "test_t208_required_test_ids_are_present",
)
_PHASE4_2_FORCED_ACTION_CTORS = (
    "CallToolDecision",
    "EvaluateRulesDecision",
    "RetrieveKnowledgeDecision",
)
_PHASE4_2_V7_PRODUCT_BUILDERS = (
    "_build_phase4_2_v7_planner",
    "_run_phase4_2_v7_development_benchmark",
    "_run_phase4_2_v7_official_benchmark",
)
_PHASE4_2_TARGET_DEFAULTS = (
    "causal_macro_f1_min: float = 0.80",
    "first_tool_selection_min: float = 0.80",
    "observation_driven_replan_min: float = 0.80",
    "evidence_grounding_min: float = 1.00",
    "unsupported_claim_rate_max: float = 0.05",
    "unnecessary_tool_action_rate_max: float = 0.20",
    "timely_stopping_min: float = 0.80",
    "applicable_rule_usage_min: float = 0.80",
    "required_knowledge_usage_min: float = 0.80",
    "knowledge_citation_utilization_min: float = 1.00",
    "unnecessary_knowledge_retrieval_rate_max: float = 0.20",
)


def _collect_test_function_names() -> set[str]:
    names: set[str] = set()
    tests_root = PROJECT_ROOT / "tests"
    for path in sorted(tests_root.rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name.startswith("test_")
            ):
                names.add(node.name)
    return names


def _module_function_defs(path: Path) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _call_func_names(function: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            names.add(func.id)
        elif isinstance(func, ast.Attribute):
            names.add(func.attr)
    return names


def _name_ids(function: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    return {node.id for node in ast.walk(function) if isinstance(node, ast.Name)}


def _git_name_only(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "diff", "--name-only", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_t208_diff_check_against_phase4_2_baseline() -> None:
    """T208 quality gate is git diff --check aefccba..HEAD."""
    result = subprocess.run(
        ["git", "diff", "--check", f"{_PHASE4_2_BASELINE}..HEAD"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_t208_phase4_2_changes_stay_inside_allowed_boundaries() -> None:
    result = _git_name_only(f"{_PHASE4_2_BASELINE}..{_PHASE4_3_1_MERGED_BASELINE}")
    assert result.returncode == 0, result.stderr
    forbidden = [
        path
        for path in result.stdout.splitlines()
        if path and not path.startswith(_PHASE4_2_ALLOWED_PREFIXES)
    ]
    assert not forbidden, "Phase 4.2 changes escaped allowed boundaries:\n" + "\n".join(
        forbidden
    )
    assert (SRC_ROOT / "app").is_dir()
    frozen = _git_name_only(
        f"{_PHASE4_2_BASELINE}..{_PHASE4_3_1_MERGED_BASELINE}",
        "--",
        *_PHASE4_2_FROZEN_PATHS,
    )
    assert frozen.returncode == 0, frozen.stderr
    assert frozen.stdout.strip() == ""


def test_t208_dependency_direction_forbids_app_and_reverse_evaluation() -> None:
    """T208: signal -> dsp -> tools -> rules/knowledge -> agent -> evaluation."""
    assert PHASE4_UPSTREAM_LAYERS == (
        "signal",
        "dsp",
        "tools",
        "rules",
        "knowledge",
        "agent",
    )
    for layer in PHASE4_UPSTREAM_LAYERS:
        assert "signal_diag.evaluation" in FORBIDDEN[layer]
        assert "signal_diag.app" in FORBIDDEN[layer]
    assert "app" not in DEFERRED_PACKAGES
    assert (SRC_ROOT / "app").is_dir()
    violations: list[str] = []
    for layer in PHASE4_UPSTREAM_LAYERS:
        violations.extend(_collect_layer_violations(layer))
        for path in _python_files_under(layer):
            hits = _imports_evaluation(_modules_imported_from(path))
            violations.extend(
                f"{path.relative_to(PROJECT_ROOT)} imports {module}" for module in hits
            )
            app_hits = _imports_app(_modules_imported_from(path))
            violations.extend(
                f"{path.relative_to(PROJECT_ROOT)} imports {module}"
                for module in app_hits
            )
    assert not violations, "Forbidden architecture edges detected:\n" + "\n".join(
        violations
    )


def test_t208_runtime_does_not_construct_forced_actions() -> None:
    runtime_path = SRC_ROOT / "agent" / "runtime.py"
    tree = ast.parse(runtime_path.read_text(encoding="utf-8"), filename=str(runtime_path))
    constructed: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name: str | None = None
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        if name in _PHASE4_2_FORCED_ACTION_CTORS:
            constructed.append(name)
    assert not constructed, "runtime constructs controller-forced actions: " + ", ".join(
        constructed
    )


def test_t208_product_path_does_not_fall_back_to_scripted_planner() -> None:
    planner_source = (SRC_ROOT / "agent" / "planner.py").read_text(encoding="utf-8")
    assert "This command does not fall back to ScriptedPlanner." in planner_source
    functions = _module_function_defs(SRC_ROOT / "evaluation" / "runner.py")
    builder = functions["_build_phase4_2_v7_planner"]
    builder_calls = _call_func_names(builder)
    assert "_Phase4V7RealLLMPlanner" in builder_calls
    assert "ScriptedPlanner" not in builder_calls
    assert "ScriptedPlanner" not in _name_ids(builder)
    for name in _PHASE4_2_V7_PRODUCT_BUILDERS:
        used = _name_ids(functions[name])
        assert "ScriptedPlanner" not in used
        assert "_ContextBoundScriptedPlanner" not in used
    for runner_name in (
        "_run_phase4_2_v7_development_benchmark",
        "_run_phase4_2_v7_official_benchmark",
    ):
        used = _name_ids(functions[runner_name])
        assert "_build_phase4_2_v7_planner" in used


def test_t208_target_bands_are_not_reduced() -> None:
    source = (SRC_ROOT / "evaluation" / "models.py").read_text(encoding="utf-8")
    missing = [line for line in _PHASE4_2_TARGET_DEFAULTS if line not in source]
    assert not missing, "TargetBands defaults drifted:\n" + "\n".join(missing)


def test_t208_required_test_ids_are_present() -> None:
    """T208: T201–T208 tests exist; T208 architecture names are present."""
    names = _collect_test_function_names()
    missing_ids = [
        test_id
        for test_id in _PHASE4_2_REQUIRED_TEST_IDS
        if not any(name.startswith(f"test_{test_id.lower()}_") for name in names)
    ]
    assert not missing_ids, "missing required Phase 4.2 tests: " + ", ".join(
        missing_ids
    )
    missing_t208 = [
        name for name in _PHASE4_2_REQUIRED_T208_TESTS if name not in names
    ]
    assert not missing_t208, "missing T208 architecture tests:\n" + "\n".join(
        missing_t208
    )


_PHASE4_3_BASELINE = "eb47237"
_PHASE4_3_1_IMPLEMENTATION_BASELINE = "1b94194"
_PHASE4_3_ALLOWED_PREFIXES = (
    "AGENTS.md",
    "docs/",
    "src/signal_diag/agent/",
    "src/signal_diag/evaluation/",
    "tests/",
)
_PHASE4_3_FROZEN_PATHS = (
    "src/signal_diag/agent/runtime.py",
    "src/signal_diag/evaluation/models.py",
    "src/signal_diag/evaluation/scoring.py",
    "src/signal_diag/evaluation/dataset.py",
    "src/signal_diag/evaluation/manifests",
    "src/signal_diag/dsp",
    "src/signal_diag/rules",
    "src/signal_diag/knowledge",
    "src/signal_diag/tools",
    "src/signal_diag/signal",
)
_PHASE4_3_REQUIRED_TEST_IDS = tuple(f"T{index}" for index in range(209, 216))
_PHASE4_3_REQUIRED_T213_TESTS = (
    "test_t213_runtime_does_not_construct_forced_actions",
    "test_t213_runtime_does_not_branch_on_prompt_case_split_or_targets",
    "test_t213_v8_product_builders_use_real_llm_planner",
    "test_t213_no_universal_pipeline_or_scripted_fallback",
    "test_t213_existing_controller_semantics_tests_remain",
)
_PHASE4_3_REQUIRED_T215_TESTS = (
    "test_t215_diff_check_against_phase4_3_baseline",
    "test_t215_phase4_3_changes_stay_inside_allowed_boundaries",
    "test_t215_dependency_direction_forbids_app_and_reverse_evaluation",
    "test_t215_target_bands_are_not_reduced",
    "test_t215_required_test_ids_are_present",
)
_PHASE4_3_FORCED_ACTION_CTORS = (
    "CallToolDecision",
    "EvaluateRulesDecision",
    "RetrieveKnowledgeDecision",
    "FinishDecision",
)
_PHASE4_3_V8_PRODUCT_BUILDERS = (
    "_build_phase4_3_v8_planner",
    "_run_phase4_3_v8_development_benchmark",
    "_run_phase4_3_v8_official_benchmark",
)
_PHASE4_3_FORBIDDEN_RUNTIME_NAMES = frozenset(
    {
        "prompt_version",
        "planner_version",
        "prompt_id",
        "case_id",
        "case_identity",
        "split",
        "TargetBands",
        "target_bands",
        "scoring_targets",
        "causal_truth",
        "generator_truth",
        "acceptable_tools",
        "category",
    }
)
_PHASE4_3_S1_TOOL_NAMES = frozenset(
    {
        "detect_clipping",
        "analyze_harmonic_distortion",
        "analyze_spectrum",
        "estimate_fundamental",
    }
)
_PHASE4_3_REQUIRED_CONTROLLER_TESTS = (
    "test_t075_invalid_observation_allows_replan",
    "test_t077_planner_output_error_is_retried_within_budget",
    "test_t078_planner_retry_exhaustion_terminates",
    "test_t079_tool_call_limit_is_enforced",
    "test_t080_equivalent_call_is_rejected_and_counts_no_progress",
    "test_t081_no_progress_termination",
    "test_t083_unknown_evidence_reference_follows_retry_policy",
    "test_t085_real_planner_failure_never_invokes_scripted_planner",
)
_PHASE4_3_TARGET_DEFAULTS = _PHASE4_2_TARGET_DEFAULTS


def _constructed_call_names(tree: ast.AST) -> list[str]:
    constructed: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name: str | None = None
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        if name is not None:
            constructed.append(name)
    return constructed


def test_t213_runtime_does_not_construct_forced_actions() -> None:
    runtime_path = SRC_ROOT / "agent" / "runtime.py"
    tree = ast.parse(runtime_path.read_text(encoding="utf-8"), filename=str(runtime_path))
    constructed = [
        name
        for name in _constructed_call_names(tree)
        if name in _PHASE4_3_FORCED_ACTION_CTORS
    ]
    assert not constructed, "runtime constructs controller-forced actions: " + ", ".join(
        constructed
    )


def test_t213_runtime_does_not_branch_on_prompt_case_split_or_targets() -> None:
    runtime_path = SRC_ROOT / "agent" / "runtime.py"
    tree = ast.parse(runtime_path.read_text(encoding="utf-8"), filename=str(runtime_path))
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in _PHASE4_3_FORBIDDEN_RUNTIME_NAMES:
            hits.append(node.id)
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value in _PHASE4_3_FORBIDDEN_RUNTIME_NAMES
        ):
            hits.append(node.value)
    assert not hits, "runtime branches on forbidden evaluation identity: " + ", ".join(
        sorted(set(hits))
    )


def test_t213_v8_product_builders_use_real_llm_planner() -> None:
    functions = _module_function_defs(SRC_ROOT / "evaluation" / "runner.py")
    builder = functions["_build_phase4_3_v8_planner"]
    builder_calls = _call_func_names(builder)
    assert "_Phase4V8RealLLMPlanner" in builder_calls
    assert "_Phase4V7RealLLMPlanner" not in builder_calls
    assert "ScriptedPlanner" not in builder_calls
    assert "ScriptedPlanner" not in _name_ids(builder)
    for name in _PHASE4_3_V8_PRODUCT_BUILDERS:
        used = _name_ids(functions[name])
        assert "ScriptedPlanner" not in used
        assert "_ContextBoundScriptedPlanner" not in used
    for runner_name in (
        "_run_phase4_3_v8_development_benchmark",
        "_run_phase4_3_v8_official_benchmark",
    ):
        used = _name_ids(functions[runner_name])
        assert "_build_phase4_3_v8_planner" in used


def test_t213_no_universal_pipeline_or_scripted_fallback() -> None:
    planner_source = (SRC_ROOT / "agent" / "planner.py").read_text(encoding="utf-8")
    assert "This command does not fall back to ScriptedPlanner." in planner_source
    runtime_path = SRC_ROOT / "agent" / "runtime.py"
    tree = ast.parse(runtime_path.read_text(encoding="utf-8"), filename=str(runtime_path))
    pipelines: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.List, ast.Tuple)):
            continue
        values = [
            elt.value
            for elt in node.elts
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
        ]
        if len(values) >= 3 and _PHASE4_3_S1_TOOL_NAMES <= set(values):
            pipelines.append(", ".join(values))
    assert not pipelines, "runtime encodes a universal Tool pipeline: " + "; ".join(
        pipelines
    )


def test_t213_existing_controller_semantics_tests_remain() -> None:
    names = _collect_test_function_names()
    missing = [
        name for name in _PHASE4_3_REQUIRED_CONTROLLER_TESTS if name not in names
    ]
    assert not missing, "missing required controller semantics tests:\n" + "\n".join(
        missing
    )


def test_t215_diff_check_against_phase4_3_baseline() -> None:
    """T215 quality gate is git diff --check eb47237..HEAD."""
    result = subprocess.run(
        ["git", "diff", "--check", f"{_PHASE4_3_BASELINE}..HEAD"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_t215_phase4_3_changes_stay_inside_allowed_boundaries() -> None:
    result = _git_name_only(f"{_PHASE4_3_BASELINE}..{_PHASE4_3_1_MERGED_BASELINE}")
    assert result.returncode == 0, result.stderr
    forbidden = [
        path
        for path in result.stdout.splitlines()
        if path and not path.startswith(_PHASE4_3_ALLOWED_PREFIXES)
    ]
    assert not forbidden, "Phase 4.3 changes escaped allowed boundaries:\n" + "\n".join(
        forbidden
    )
    assert (SRC_ROOT / "app").is_dir()
    frozen = _git_name_only(
        f"{_PHASE4_3_BASELINE}..{_PHASE4_3_1_IMPLEMENTATION_BASELINE}",
        "--",
        *_PHASE4_3_FROZEN_PATHS,
    )
    assert frozen.returncode == 0, frozen.stderr
    assert frozen.stdout.strip() == ""


def test_t215_dependency_direction_forbids_app_and_reverse_evaluation() -> None:
    """T215: signal -> dsp -> tools -> rules/knowledge -> agent -> evaluation."""
    assert PHASE4_UPSTREAM_LAYERS == (
        "signal",
        "dsp",
        "tools",
        "rules",
        "knowledge",
        "agent",
    )
    for layer in PHASE4_UPSTREAM_LAYERS:
        assert "signal_diag.evaluation" in FORBIDDEN[layer]
        assert "signal_diag.app" in FORBIDDEN[layer]
    assert "app" not in DEFERRED_PACKAGES
    assert (SRC_ROOT / "app").is_dir()
    violations: list[str] = []
    for layer in PHASE4_UPSTREAM_LAYERS:
        violations.extend(_collect_layer_violations(layer))
        for path in _python_files_under(layer):
            hits = _imports_evaluation(_modules_imported_from(path))
            violations.extend(
                f"{path.relative_to(PROJECT_ROOT)} imports {module}" for module in hits
            )
            app_hits = _imports_app(_modules_imported_from(path))
            violations.extend(
                f"{path.relative_to(PROJECT_ROOT)} imports {module}"
                for module in app_hits
            )
    assert not violations, "Forbidden architecture edges detected:\n" + "\n".join(
        violations
    )


def test_t215_target_bands_are_not_reduced() -> None:
    source = (SRC_ROOT / "evaluation" / "models.py").read_text(encoding="utf-8")
    missing = [line for line in _PHASE4_3_TARGET_DEFAULTS if line not in source]
    assert not missing, "TargetBands defaults drifted:\n" + "\n".join(missing)


def test_t215_required_test_ids_are_present() -> None:
    """T215: T209–T215 tests exist; T213/T215 architecture names are present."""
    names = _collect_test_function_names()
    missing_ids = [
        test_id
        for test_id in _PHASE4_3_REQUIRED_TEST_IDS
        if not any(name.startswith(f"test_{test_id.lower()}_") for name in names)
    ]
    assert not missing_ids, "missing required Phase 4.3 tests: " + ", ".join(
        missing_ids
    )
    missing_named = [
        name
        for name in _PHASE4_3_REQUIRED_T213_TESTS + _PHASE4_3_REQUIRED_T215_TESTS
        if name not in names
    ]
    assert not missing_named, "missing T213/T215 architecture tests:\n" + "\n".join(
        missing_named
    )


_PHASE4_3_1_BASELINE = _PHASE4_3_1_IMPLEMENTATION_BASELINE
_PHASE4_3_1_ALLOWED_PREFIXES = _PHASE4_3_ALLOWED_PREFIXES
_PHASE4_3_1_FROZEN_PATHS = (
    "src/signal_diag/agent/runtime.py",
    "src/signal_diag/evaluation/models.py",
    "src/signal_diag/evaluation/dataset.py",
    "src/signal_diag/evaluation/manifests",
    "src/signal_diag/dsp",
    "src/signal_diag/rules",
    "src/signal_diag/knowledge",
    "src/signal_diag/tools",
    "src/signal_diag/signal",
)
_PHASE4_3_1_PERMITTED_EVALUATION_CHANGES = ("src/signal_diag/evaluation/scoring.py",)
_PHASE4_3_1_REQUIRED_TEST_IDS = tuple(f"T{index}" for index in range(216, 224))
_PHASE4_3_1_REQUIRED_T223_TESTS = (
    "test_t223_diff_check_against_phase4_3_1_baseline",
    "test_t223_phase4_3_1_changes_stay_inside_allowed_boundaries",
    "test_t223_dependency_direction_forbids_app_and_reverse_evaluation",
    "test_t223_runtime_does_not_construct_forced_actions",
    "test_t223_runtime_does_not_branch_on_prompt_case_split_or_targets",
    "test_t223_v8_1_product_builders_use_real_llm_planner",
    "test_t223_no_universal_pipeline_or_scripted_fallback",
    "test_t223_scoring_py_is_only_authorized_evaluation_exception",
    "test_t223_target_bands_are_not_reduced",
    "test_t223_required_test_ids_are_present",
)
_PHASE4_3_1_V81_PRODUCT_BUILDERS = (
    "_build_phase4_3_1_v8_1_planner",
    "_run_phase4_3_1_v8_1_development_benchmark",
    "_run_phase4_3_1_v8_1_official_benchmark",
)


def test_t223_diff_check_against_phase4_3_1_baseline() -> None:
    """T223 quality gate is git diff --check 1b94194..HEAD."""
    result = subprocess.run(
        ["git", "diff", "--check", f"{_PHASE4_3_1_BASELINE}..HEAD"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_t223_phase4_3_1_changes_stay_inside_allowed_boundaries() -> None:
    result = _git_name_only(f"{_PHASE4_3_1_BASELINE}..{_PHASE4_3_1_MERGED_BASELINE}")
    assert result.returncode == 0, result.stderr
    forbidden = [
        path
        for path in result.stdout.splitlines()
        if path and not path.startswith(_PHASE4_3_1_ALLOWED_PREFIXES)
    ]
    assert not forbidden, (
        "Phase 4.3.1 changes escaped allowed boundaries:\n" + "\n".join(forbidden)
    )
    assert (SRC_ROOT / "app").is_dir()
    frozen = _git_name_only(
        f"{_PHASE4_3_1_BASELINE}..{_PHASE4_3_1_MERGED_BASELINE}",
        "--",
        *_PHASE4_3_1_FROZEN_PATHS,
    )
    assert frozen.returncode == 0, frozen.stderr
    assert frozen.stdout.strip() == ""


def test_t223_scoring_py_is_only_authorized_evaluation_exception() -> None:
    """§54.4 permits only evaluation/scoring.py among Phase 4.3 evaluation freezes."""
    result = _git_name_only(
        f"{_PHASE4_3_1_BASELINE}..HEAD",
        "--",
        "src/signal_diag/evaluation/models.py",
        "src/signal_diag/evaluation/scoring.py",
        "src/signal_diag/evaluation/dataset.py",
        "src/signal_diag/evaluation/manifests",
    )
    assert result.returncode == 0, result.stderr
    changed = [line for line in result.stdout.splitlines() if line]
    assert changed == ["src/signal_diag/evaluation/scoring.py"]


def test_t223_dependency_direction_forbids_app_and_reverse_evaluation() -> None:
    """T223: signal -> dsp -> tools -> rules/knowledge -> agent -> evaluation."""
    assert PHASE4_UPSTREAM_LAYERS == (
        "signal",
        "dsp",
        "tools",
        "rules",
        "knowledge",
        "agent",
    )
    for layer in PHASE4_UPSTREAM_LAYERS:
        assert "signal_diag.evaluation" in FORBIDDEN[layer]
        assert "signal_diag.app" in FORBIDDEN[layer]
    assert "app" not in DEFERRED_PACKAGES
    assert (SRC_ROOT / "app").is_dir()
    violations: list[str] = []
    for layer in PHASE4_UPSTREAM_LAYERS:
        violations.extend(_collect_layer_violations(layer))
        for path in _python_files_under(layer):
            hits = _imports_evaluation(_modules_imported_from(path))
            violations.extend(
                f"{path.relative_to(PROJECT_ROOT)} imports {module}" for module in hits
            )
            app_hits = _imports_app(_modules_imported_from(path))
            violations.extend(
                f"{path.relative_to(PROJECT_ROOT)} imports {module}"
                for module in app_hits
            )
    assert not violations, "Forbidden architecture edges detected:\n" + "\n".join(
        violations
    )


def test_t223_runtime_does_not_construct_forced_actions() -> None:
    runtime_path = SRC_ROOT / "agent" / "runtime.py"
    tree = ast.parse(runtime_path.read_text(encoding="utf-8"), filename=str(runtime_path))
    constructed = [
        name
        for name in _constructed_call_names(tree)
        if name in _PHASE4_3_FORCED_ACTION_CTORS
    ]
    assert not constructed, "runtime constructs controller-forced actions: " + ", ".join(
        constructed
    )


def test_t223_runtime_does_not_branch_on_prompt_case_split_or_targets() -> None:
    runtime_path = SRC_ROOT / "agent" / "runtime.py"
    tree = ast.parse(runtime_path.read_text(encoding="utf-8"), filename=str(runtime_path))
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in _PHASE4_3_FORBIDDEN_RUNTIME_NAMES:
            hits.append(node.id)
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value in _PHASE4_3_FORBIDDEN_RUNTIME_NAMES
        ):
            hits.append(node.value)
    assert not hits, "runtime branches on forbidden evaluation identity: " + ", ".join(
        sorted(set(hits))
    )


def test_t223_v8_1_product_builders_use_real_llm_planner() -> None:
    functions = _module_function_defs(SRC_ROOT / "evaluation" / "runner.py")
    builder = functions["_build_phase4_3_1_v8_1_planner"]
    builder_calls = _call_func_names(builder)
    assert "RealLLMPlanner" not in builder_calls
    assert "_Phase4V8_1RealLLMPlanner" in builder_calls
    assert "_Phase4V8RealLLMPlanner" not in builder_calls
    assert "ScriptedPlanner" not in builder_calls
    assert "ScriptedPlanner" not in _name_ids(builder)
    for name in _PHASE4_3_1_V81_PRODUCT_BUILDERS:
        used = _name_ids(functions[name])
        assert "ScriptedPlanner" not in used
        assert "_ContextBoundScriptedPlanner" not in used
    for runner_name in (
        "_run_phase4_3_1_v8_1_development_benchmark",
        "_run_phase4_3_1_v8_1_official_benchmark",
    ):
        used = _name_ids(functions[runner_name])
        assert "_build_phase4_3_1_v8_1_planner" in used


def test_t223_no_universal_pipeline_or_scripted_fallback() -> None:
    planner_source = (SRC_ROOT / "agent" / "planner.py").read_text(encoding="utf-8")
    assert "This command does not fall back to ScriptedPlanner." in planner_source
    runtime_path = SRC_ROOT / "agent" / "runtime.py"
    tree = ast.parse(runtime_path.read_text(encoding="utf-8"), filename=str(runtime_path))
    pipelines: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.List, ast.Tuple)):
            continue
        values = [
            elt.value
            for elt in node.elts
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
        ]
        if len(values) >= 3 and _PHASE4_3_S1_TOOL_NAMES <= set(values):
            pipelines.append(", ".join(values))
    assert not pipelines, "runtime encodes a universal Tool pipeline: " + "; ".join(
        pipelines
    )


def test_t223_target_bands_are_not_reduced() -> None:
    source = (SRC_ROOT / "evaluation" / "models.py").read_text(encoding="utf-8")
    missing = [line for line in _PHASE4_3_TARGET_DEFAULTS if line not in source]
    assert not missing, "TargetBands defaults drifted:\n" + "\n".join(missing)


def test_t223_required_test_ids_are_present() -> None:
    """T223: T216–T223 tests exist; T223 architecture names are present."""
    names = _collect_test_function_names()
    missing_ids = [
        test_id
        for test_id in _PHASE4_3_1_REQUIRED_TEST_IDS
        if not any(name.startswith(f"test_{test_id.lower()}_") for name in names)
    ]
    assert not missing_ids, "missing required Phase 4.3.1 tests: " + ", ".join(
        missing_ids
    )
    missing_named = [
        name for name in _PHASE4_3_1_REQUIRED_T223_TESTS if name not in names
    ]
    assert not missing_named, "missing T223 architecture tests:\n" + "\n".join(
        missing_named
    )


def test_t283_app_exists_and_is_bounded() -> None:
    """T283: app/ exists, is not deferred, and evaluation may not import it."""
    assert "app" not in DEFERRED_PACKAGES
    assert DEFERRED_PACKAGES == ()
    assert (SRC_ROOT / "app").is_dir()
    assert "evaluation" in FORBIDDEN
    assert "signal_diag.app" in FORBIDDEN["evaluation"]
    for layer in PHASE4_UPSTREAM_LAYERS:
        assert "signal_diag.app" in FORBIDDEN[layer]
        assert "signal_diag.evaluation" in FORBIDDEN[layer]


def test_t283_upstream_sources_do_not_import_app() -> None:
    violations: list[str] = []
    for layer in PHASE4_UPSTREAM_LAYERS:
        for path in _python_files_under(layer):
            hits = _imports_app(_modules_imported_from(path))
            violations.extend(
                f"{path.relative_to(PROJECT_ROOT)} imports {module}" for module in hits
            )
    for path in _python_files_under("evaluation"):
        hits = _imports_app(_modules_imported_from(path))
        violations.extend(
            f"{path.relative_to(PROJECT_ROOT)} imports {module}" for module in hits
        )
    assert not violations, "Forbidden app imports detected:\n" + "\n".join(violations)


def test_t283_wav_imports_no_app_evaluation_agent_or_llm() -> None:
    wav_path = SRC_ROOT / "signal" / "wav.py"
    assert wav_path.is_file()
    modules = _modules_imported_from(wav_path)
    hits = _modules_match_prefixes(modules, WAV_FORBIDDEN_PREFIXES)
    assert not hits, "signal.wav imports forbidden modules: " + ", ".join(hits)


def test_t283_api_cli_static_contain_no_dsp_rule_or_diagnosis_impl() -> None:
    adapter_py = (
        SRC_ROOT / "app" / "api.py",
        SRC_ROOT / "app" / "cli.py",
    )
    violations: list[str] = []
    for path in adapter_py:
        modules = _modules_imported_from(path)
        hits = _modules_match_prefixes(modules, ADAPTER_FORBIDDEN_PREFIXES)
        violations.extend(
            f"{path.relative_to(PROJECT_ROOT)} imports {module}" for module in hits
        )
    static_dir = SRC_ROOT / "app" / "static"
    for path in sorted(static_dir.glob("*")):
        if path.suffix not in {".html", ".css", ".js"}:
            continue
        text = path.read_text(encoding="utf-8")
        for token in STATIC_FORBIDDEN_TOKENS:
            if token in text:
                violations.append(f"{path.relative_to(PROJECT_ROOT)} contains {token}")
    assert not violations, "Adapters implement lower-layer logic:\n" + "\n".join(
        violations
    )


def test_boundary_helper_detects_app_reverse_imports_in_memory() -> None:
    source = "from signal_diag.app import build_product_service\n"
    for layer in PHASE4_UPSTREAM_LAYERS:
        assert find_forbidden_imports(layer, source, f"fake_{layer}_module.py") == [
            "signal_diag.app"
        ]
    assert find_forbidden_imports(
        "evaluation",
        source,
        "fake_evaluation_module.py",
    ) == ["signal_diag.app"]


REPO_ROOT = PROJECT_ROOT
_PHASE5_CHECKPOINT_FILES = (
    "tests/signal/test_wav.py",
    "tests/app/test_presets_preview.py",
    "tests/app/test_models.py",
    "tests/app/test_runs.py",
    "tests/app/test_service.py",
    "tests/evaluation/test_recording.py",
    "tests/app/test_reporting.py",
    "tests/app/test_api.py",
    "tests/app/test_ui.py",
    "tests/app/test_cli.py",
    "tests/app/test_packaging.py",
    "tests/test_architecture_boundaries.py",
    ".github/workflows/ci.yml",
    "scripts/verify_phase5_local_matrix.py",
)
_PHASE5_OFFICIAL_SUMMARY = (
    SRC_ROOT / "evaluation" / "assets" / "phase4_3_1_official_summary.json"
)
_PHASE5_OFFICIAL_BUNDLE = (
    PROJECT_ROOT
    / "docs"
    / "evaluations"
    / "phase4_3_1"
    / "official"
    / "bench_official_s1_v12_planner8_1_gate5"
)
_PHASE5_OFFICIAL_CHECKSUMS = {
    "benchmark_manifest.json": (
        "355fc75eab5d4580606fb3eb31a71566cc4b2a8303d412aa309df5b3c9ae71a7"
    ),
    "case_summary.csv": (
        "3699061f726cf8de1b8d6eff9bcf3bd8487431d64f23944dbf0c95ce87bcaeae"
    ),
    "metrics.json": (
        "e60aa63de6f030bf88fd7154cd0f7b72fd7bf36589ad769a234ee02fd6e956d0"
    ),
    "report.md": "8f2f47e34731254ae45987445076e041f8675da17f56cc0463530c412ec1b4f0",
    "runs.jsonl": "cff5a41ea8ed6f7838cc72e25b678d7b11eb97976e27a039e80d877d781ac35d",
}
_PHASE5_ALLOWED_UPSTREAM_PATHS = {
    "src/signal_diag/signal/__init__.py",
    "src/signal_diag/signal/wav.py",
    "src/signal_diag/evaluation/__init__.py",
    "src/signal_diag/evaluation/recording.py",
    "src/signal_diag/evaluation/assets/__init__.py",
    "src/signal_diag/evaluation/assets/phase4_3_1_official_summary.json",
}
# Additive V0.3 authorized packages (external validity study + Workstreams A/B/C).
# Prefix match only; does not weaken V0.2 frozen dsp/agent paths outside this list.
_V03_ADDITIVE_PATH_PREFIXES: tuple[str, ...] = (
    "src/signal_diag/evaluation/external/",
    "src/signal_diag/evaluation/contextual/",
)
_V03_ADDITIVE_EXACT_PATHS = frozenset(
    {
        "src/signal_diag/agent/prompts_v03.py",
        "src/signal_diag/agent/planner.py",
        "src/signal_diag/agent/models.py",
        "src/signal_diag/agent/state.py",
        "src/signal_diag/app/composition.py",
        "src/signal_diag/dsp/__init__.py",
        "src/signal_diag/dsp/contextual.py",
        "src/signal_diag/dsp/spectral_reliability.py",
        "src/signal_diag/dsp/pitch.py",
        "src/signal_diag/dsp/harmonics.py",
        "src/signal_diag/dsp/models.py",
        "src/signal_diag/evaluation/runner.py",
        "src/signal_diag/evaluation/external/reference_harmonics.py",
        "src/signal_diag/dsp/clipping.py",
        "src/signal_diag/tools/contracts.py",
        "src/signal_diag/tools/service.py",
        "src/signal_diag/tools/__init__.py",
        "src/signal_diag/tools/contextual.py",
        "src/signal_diag/tools/registry.py",
        "src/signal_diag/agent/diagnosis.py",
        "src/signal_diag/agent/runtime.py",
        "src/signal_diag/evaluation/external/reference.py",
        "src/signal_diag/evaluation/external/reference_models.py",
        "src/signal_diag/rules/profiles/s1_contextual_comparison_v1.yaml",
        "src/signal_diag/signal/context.py",
    }
)
_PHASE3_SKIP_TEMPLATES = frozenset({"Phase 3 package {}/ not created yet"})
_PHASE3_SKIP_SOURCE_SNIPPETS = (
    'pytest.skip(f"Phase 3 package {layer}/ not created yet")',
    'pytest.skip(f"Phase 3 package {package_name}/ not created yet")',
)


def _test_python_files() -> list[Path]:
    tests_root = PROJECT_ROOT / "tests"
    return sorted(path for path in tests_root.rglob("*.py") if path.is_file())


def _call_attr_name(func: ast.AST) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _joined_string_template(node: ast.JoinedStr) -> str:
    parts: list[str] = []
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            parts.append(value.value)
        elif isinstance(value, ast.FormattedValue):
            parts.append("{}")
    return "".join(parts)


def _skip_call_template(call: ast.Call) -> str:
    if not call.args:
        return ""
    argument = call.args[0]
    if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
        return argument.value
    if isinstance(argument, ast.JoinedStr):
        return _joined_string_template(argument)
    return ""


def _pytest_skip_xfail_kind(node: ast.AST) -> str | None:
    target = node.func if isinstance(node, ast.Call) else node
    if not isinstance(target, ast.Attribute):
        return None
    if target.attr not in {"skip", "xfail", "skipif", "importorskip"}:
        return None
    value = target.value
    if isinstance(value, ast.Name) and value.id == "pytest":
        return f"pytest.{target.attr}"
    if (
        isinstance(value, ast.Attribute)
        and value.attr == "mark"
        and isinstance(value.value, ast.Name)
        and value.value.id == "pytest"
    ):
        return f"pytest.mark.{target.attr}"
    return None


def _is_empty_collection(node: ast.AST) -> bool:
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)) and not node.elts:
        return True
    if isinstance(node, ast.Dict) and not node.keys:
        return True
    if isinstance(node, ast.Call) and _call_attr_name(node.func) in {
        "list",
        "tuple",
        "set",
        "frozenset",
        "dict",
    }:
        return not node.args and not node.keywords
    return False


def _module_assign_map(tree: ast.AST) -> dict[str, ast.AST]:
    values: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    values[target.id] = node.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.value is not None
        ):
            values[node.target.id] = node.value
    return values


def _parametrize_values_node(call: ast.Call) -> ast.AST | None:
    if len(call.args) >= 2:
        return call.args[1]
    for keyword in call.keywords:
        if keyword.arg in {"argvalues", "values"}:
            return keyword.value
    return None


def _is_blank_constant(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and not node.value


def _is_openai_module(name: str) -> bool:
    return name == "openai" or name.startswith("openai.")


def _planner_ctor_has_live_credentials(call: ast.Call) -> bool:
    keywords = {kw.arg: kw.value for kw in call.keywords if kw.arg is not None}
    if "client" in keywords:
        return False
    provider = keywords.get("provider")
    api_key = keywords.get("api_key")
    if provider is None or api_key is None:
        return False
    return not _is_blank_constant(provider) and not _is_blank_constant(api_key)


def test_t285_phase5_cumulative_contract_is_registered() -> None:
    test_plan = (REPO_ROOT / "docs" / "TEST_PLAN_V0_2.md").read_text("utf-8")
    for number in range(224, 286):
        assert f"| T{number} |" in test_plan
    assert "presentation_harness_accepted" in test_plan
    assert "real_demo_completed" in test_plan

    for relative in _PHASE5_CHECKPOINT_FILES:
        path = PROJECT_ROOT / relative
        assert path.is_file(), f"missing Phase 5 checkpoint file: {relative}"

    names = _collect_test_function_names()
    missing_ids = [
        f"T{number}"
        for number in range(224, 286)
        if not any(name.startswith(f"test_t{number}_") for name in names)
    ]
    assert not missing_ids, "missing Phase 5 test ids: " + ", ".join(missing_ids)

    summary = json.loads(_PHASE5_OFFICIAL_SUMMARY.read_text(encoding="utf-8"))
    assert summary["benchmark_id"] == "bench_official_s1_v12_planner8_1_gate5"
    assert summary["scoring_version"] == "2.0.0"
    assert summary["agent_slot_count"] == 80
    assert summary["behavioral_failure_slot_count"] == 2
    assert summary["outcome_error_slot_count"] == 1
    assert summary["source_bundle_relative_path"] == (
        "docs/evaluations/phase4_3_1/official/bench_official_s1_v12_planner8_1_gate5"
    )
    assert summary["source_checksums_sha256"] == _PHASE5_OFFICIAL_CHECKSUMS
    for name, digest in _PHASE5_OFFICIAL_CHECKSUMS.items():
        payload = (_PHASE5_OFFICIAL_BUNDLE / name).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(payload).hexdigest() == digest

    architecture_source = Path(__file__).read_text(encoding="utf-8")
    for snippet in _PHASE3_SKIP_SOURCE_SNIPPETS:
        assert snippet in architecture_source
    assert PHASE3_PACKAGES == ("rules", "knowledge")
    for package_name in PHASE3_PACKAGES:
        package_dir = SRC_ROOT / package_name
        assert package_dir.is_dir(), f"Phase 3 skip would fire: missing {package_name}/"

    skip_hits: list[str] = []
    empty_parametrize: list[str] = []
    network_hits: list[str] = []
    openai_imports: list[str] = []
    for path in _test_python_files():
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        relative = str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
        assignments = _module_assign_map(tree)
        candidates: list[ast.AST] = [
            node for node in ast.walk(tree) if isinstance(node, ast.Call)
        ]
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Attribute):
                    candidates.append(decorator)
        for node in candidates:
            kind = _pytest_skip_xfail_kind(node)
            if kind is None:
                continue
            if (
                kind == "pytest.skip"
                and isinstance(node, ast.Call)
                and relative == "tests/test_architecture_boundaries.py"
                and _skip_call_template(node) in _PHASE3_SKIP_TEMPLATES
            ):
                continue
            skip_hits.append(f"{relative}: {kind}")
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _call_attr_name(node.func) != "parametrize":
                continue
            values = _parametrize_values_node(node)
            if values is None:
                continue
            resolved = values
            if isinstance(values, ast.Name) and values.id in assignments:
                resolved = assignments[values.id]
            if _is_empty_collection(resolved):
                empty_parametrize.append(relative)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_openai_module(alias.name):
                        openai_imports.append(f"{relative} imports {alias.name}")
            elif (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and _is_openai_module(node.module)
            ):
                openai_imports.append(f"{relative} imports {node.module}")
            if not isinstance(node, ast.Call):
                continue
            if _call_attr_name(node.func) == "_create_async_openai_client":
                network_hits.append(f"{relative} calls _create_async_openai_client")
            if (
                _call_attr_name(node.func).endswith("RealLLMPlanner")
                and _planner_ctor_has_live_credentials(node)
            ):
                network_hits.append(
                    f"{relative} constructs RealLLMPlanner with live credentials and no client"
                )
    assert not skip_hits, "required tests must not skip/xfail:\n" + "\n".join(skip_hits)
    assert not empty_parametrize, "empty parametrize would skip:\n" + "\n".join(
        empty_parametrize
    )
    assert not openai_imports, "required tests import openai:\n" + "\n".join(
        openai_imports
    )
    assert not network_hits, "required tests open a RealLLMPlanner network path:\n" + "\n".join(
        network_hits
    )

    matrix = (PROJECT_ROOT / "scripts" / "verify_phase5_local_matrix.py").read_text(
        encoding="utf-8"
    )
    assert "--python-3.11" in matrix
    assert "--python-3.12" in matrix
    assert "[app,llm,dev]" in matrix or ".[app,llm,dev]" in matrix
    assert "python -m pytest -q -rxXs -p no:cacheprovider" in matrix
    assert "DEEPSEEK_API_KEY=" not in matrix
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8")
    assert "3.11" in workflow
    assert "3.12" in workflow
    assert "DEEPSEEK_API_KEY" not in workflow

    diff_check = subprocess.run(
        ["git", "diff", "--check", f"{_PHASE4_3_1_MERGED_BASELINE}..HEAD"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr

    changed = _git_name_only(f"{_PHASE4_3_1_MERGED_BASELINE}..HEAD")
    assert changed.returncode == 0, changed.stderr
    frozen_hits: list[str] = []
    for path in changed.stdout.splitlines():
        if path.startswith("docs/evaluations/phase4_3_1/"):
            frozen_hits.append(path)
        if not path.startswith("src/signal_diag/"):
            continue
        if path.startswith("src/signal_diag/app/"):
            continue
        if path in _PHASE5_ALLOWED_UPSTREAM_PATHS:
            continue
        if path in _V03_ADDITIVE_EXACT_PATHS:
            continue
        if any(path.startswith(prefix) for prefix in _V03_ADDITIVE_PATH_PREFIXES):
            continue
        frozen_hits.append(path)
    assert not frozen_hits, "frozen Phase 1–4.3.1 paths drifted:\n" + "\n".join(
        frozen_hits
    )
