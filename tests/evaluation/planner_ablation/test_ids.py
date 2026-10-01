"""T-CX276–T-CX288 registration in TEST_PLAN (Wave 2)."""

from __future__ import annotations

import re
from pathlib import Path


def test_t_cx276_through_t_cx288_registered_once() -> None:
    repo = Path(__file__).resolve().parents[3]
    text = (repo / "docs" / "TEST_PLAN_V0_3_CONTEXTUAL.md").read_text(encoding="utf-8")
    ids = re.findall(r"^\| (T-CX\d+) \|", text, flags=re.MULTILINE)
    for number in range(276, 289):
        test_id = f"T-CX{number}"
        assert ids.count(test_id) == 1, f"{test_id} must appear exactly once"


def test_t_cx281_planner_ablation_package_does_not_import_app() -> None:
    root = Path(__file__).resolve().parents[3] / "src" / "signal_diag" / "evaluation" / "planner_ablation"
    violations: list[str] = []
    for path in root.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        if "signal_diag.app" in source:
            violations.append(path.name)
    assert not violations, "planner_ablation must not import app: " + ", ".join(violations)
