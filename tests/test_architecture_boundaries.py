"""Architecture boundary verification for Phase 1 packages."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

FORBIDDEN = {
    "signal": {"signal_diag.dsp", "signal_diag.tools", "signal_diag.agent"},
    "dsp": {"signal_diag.tools", "signal_diag.agent"},
    "tools": {"signal_diag.agent"},
}

DEFERRED_PACKAGES = ("agent", "rules", "knowledge", "evaluation", "app")

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
    return sorted(layer_dir.glob("*.py"))


@pytest.mark.parametrize("layer", sorted(FORBIDDEN))
def test_phase1_layers_do_not_import_forbidden_modules(layer: str) -> None:
    violations: list[str] = []
    for path in _layer_source_files(layer):
        source = path.read_text(encoding="utf-8")
        for module in find_forbidden_imports(layer, source, str(path)):
            violations.append(f"{path.relative_to(PROJECT_ROOT)} imports {module}")
    assert not violations, "Forbidden imports detected:\n" + "\n".join(violations)


@pytest.mark.parametrize("package_name", DEFERRED_PACKAGES)
def test_deferred_packages_are_not_present(package_name: str) -> None:
    package_dir = SRC_ROOT / package_name
    assert not package_dir.exists(), (
        f"Phase 1 must not create src/signal_diag/{package_name}/ yet"
    )


def test_boundary_helper_detects_forbidden_import_in_memory() -> None:
    source = "from signal_diag.dsp import analyze_clipping\n"
    violations = find_forbidden_imports("signal", source, "fake_signal_module.py")
    assert violations == ["signal_diag.dsp"]
