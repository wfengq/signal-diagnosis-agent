"""EV-C032 — reference harmonic validator independence from production DSP."""

from __future__ import annotations

import ast
from pathlib import Path

_FORBIDDEN_PRODUCTION_MODULES = frozenset(
    {
        "signal_diag.dsp.harmonics",
        "signal_diag.dsp.pitch",
        "signal_diag.tools",
    }
)


def _collect_imports(module_path: Path) -> set[str]:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    return imported


def test_ev_c032_reference_harmonics_has_no_production_detector_imports() -> None:
    external_root = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "signal_diag"
        / "evaluation"
        / "external"
    )
    module_paths = [
        external_root / "reference.py",
        external_root / "reference_harmonics.py",
    ]
    violations: set[str] = set()
    for module_path in module_paths:
        for imported in _collect_imports(module_path):
            if any(
                imported == forbidden or imported.startswith(f"{forbidden}.")
                for forbidden in _FORBIDDEN_PRODUCTION_MODULES
            ):
                violations.add(f"{module_path.name}: {imported}")
    assert violations == set()


def test_ev_c032_reference_harmonics_not_transitive_through_other_dsp_wrappers() -> None:
    """reference_harmonics must remain a leaf independent implementation."""
    module_path = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "signal_diag"
        / "evaluation"
        / "external"
        / "reference_harmonics.py"
    )
    imported = _collect_imports(module_path)
    signal_diag = sorted(
        name
        for name in imported
        if name.startswith("signal_diag.") and not name.startswith(
            "signal_diag.evaluation.external.reference_models"
        )
    )
    assert signal_diag == []


def test_ev_c032_v03_reference_analyzer_version_is_1_1_0() -> None:
    from signal_diag.evaluation.external.reference import analyze_reference_v03
    from signal_diag.signal import extract_segment, generate_sine

    case = generate_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.05,
        amplitude=0.5,
    )
    samples = extract_segment(case.record)
    summary = analyze_reference_v03(samples, 48_000, fmin_hz=50.0, fmax_hz=1000.0)
    assert summary.reference_analyzer_id == "signal_diag.external_reference"
    assert summary.reference_analyzer_version == "1.1.0"
