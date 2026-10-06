"""T-CX371: full_scale_characterization package layering and product isolation."""

from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = PROJECT_ROOT / "src" / "signal_diag"
PACKAGE_ROOT = SRC_ROOT / "evaluation" / "full_scale_characterization"

_FORBIDDEN_IMPORT_PREFIXES: tuple[str, ...] = (
    "signal_diag.rules",
    "signal_diag.agent",
    "signal_diag.app",
    "signal_diag.knowledge",
)

_PRODUCT_LAYERS: tuple[str, ...] = (
    "signal",
    "dsp",
    "tools",
    "rules",
    "knowledge",
    "agent",
    "app",
)

_MENTION = "full_scale_characterization"


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def _forbidden_hits(modules: set[str]) -> list[str]:
    hits: list[str] = []
    for module in sorted(modules):
        for prefix in _FORBIDDEN_IMPORT_PREFIXES:
            if module == prefix or module.startswith(f"{prefix}."):
                hits.append(module)
                break
    return hits


def test_t_cx371_package_does_not_import_rules_agent_app_or_knowledge() -> None:
    """T-CX371: characterization code stays below rules/agent/app/knowledge."""
    assert PACKAGE_ROOT.is_dir(), "full_scale_characterization package must exist"
    violations: list[str] = []
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        for module in _forbidden_hits(_imported_modules(path)):
            violations.append(f"{path.relative_to(PROJECT_ROOT)} imports {module}")
    assert not violations, "Forbidden imports in characterization package:\n" + "\n".join(
        violations
    )


def test_t_cx371_product_layers_do_not_mention_characterization_package() -> None:
    """T-CX371: product tree must not reference the evaluation-only package."""
    hits: list[str] = []
    for layer in _PRODUCT_LAYERS:
        root = SRC_ROOT / layer
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix not in {".py", ".yaml", ".yml", ".json", ".md", ".toml", ".txt"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if _MENTION in text:
                hits.append(str(path.relative_to(PROJECT_ROOT)))
    assert not hits, (
        "Product layers must not mention full_scale_characterization:\n"
        + "\n".join(hits)
    )


def test_t_cx371_product_layers_do_not_import_characterization_package() -> None:
    """T-CX371 empty-registry clause superseded by D044 / T-CX386."""
    from signal_diag.rules.full_scale_check import PRODUCT_APPROVED_FULL_SCALE_FLOORS

    assert len(PRODUCT_APPROVED_FULL_SCALE_FLOORS) == 1
    assert PRODUCT_APPROVED_FULL_SCALE_FLOORS[0].floor_id == (
        "s1_full_scale_floor_round_1"
    )
