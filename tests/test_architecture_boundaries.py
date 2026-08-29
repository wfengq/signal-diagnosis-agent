"""Architecture boundary verification for Phase 1–4 packages."""

from __future__ import annotations

import ast
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
    },
    "dsp": {
        "signal_diag.tools",
        "signal_diag.agent",
        "signal_diag.rules",
        "signal_diag.knowledge",
        "signal_diag.evaluation",
    },
    "tools": {
        "signal_diag.agent",
        "signal_diag.rules",
        "signal_diag.knowledge",
        "signal_diag.evaluation",
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
}

# app/ remains deferred until Phase 5. evaluation/ is a Phase 4 hard gate (T182).
DEFERRED_PACKAGES = ("app",)

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


@pytest.mark.parametrize("package_name", DEFERRED_PACKAGES)
def test_deferred_packages_are_not_present(package_name: str) -> None:
    package_dir = SRC_ROOT / package_name
    assert not package_dir.exists(), (
        f"Deferred package src/signal_diag/{package_name}/ must not exist yet"
    )


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


def test_t182_evaluation_package_exists() -> None:
    """T182 hard gate: evaluation/ exists once Phase 4 is implemented."""
    assert (SRC_ROOT / "evaluation").is_dir()


def test_t182_evaluation_is_not_deferred() -> None:
    """T182: remove the former deferred-package skip/assert for evaluation/."""
    assert "evaluation" not in DEFERRED_PACKAGES


def test_t182_app_remains_deferred_and_absent() -> None:
    """T182: Phase 5 app/ remains absent."""
    assert "app" in DEFERRED_PACKAGES
    assert not (SRC_ROOT / "app").exists()


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
