"""Checkpoint F — evaluator-only reference analysis (EV-T027–EV-T030)."""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

from signal_diag.dsp import (
    analyze_clipping,
    analyze_harmonic_distortion,
    estimate_f0_autocorrelation,
)
from signal_diag.evaluation.external.reference import analyze_reference
from signal_diag.signal import (
    SyntheticCase,
    extract_segment,
    generate_clipped_sine,
    generate_sine,
    generate_white_noise,
)

_SAMPLE_RATE_HZ = 48_000
_FMIN_HZ = 50.0
_FMAX_HZ = 1000.0


def _digest(samples: np.ndarray) -> str:
    import hashlib

    contiguous = np.ascontiguousarray(samples, dtype=np.float32)
    return hashlib.sha256(contiguous.tobytes()).hexdigest()


def _canonical_sine() -> np.ndarray:
    case = generate_sine(
        frequency_hz=200.0,
        sample_rate_hz=_SAMPLE_RATE_HZ,
        duration_s=0.05,
        amplitude=0.5,
    )
    return extract_segment(case.record)


def test_ev_t027_reference_analyzer_identity() -> None:
    summary = analyze_reference(
        _canonical_sine(),
        _SAMPLE_RATE_HZ,
        fmin_hz=_FMIN_HZ,
        fmax_hz=_FMAX_HZ,
    )

    assert summary.reference_analyzer_id == "signal_diag.external_reference"
    assert summary.reference_analyzer_version == "1.0.0"
    assert summary.input_sha256 == _digest(_canonical_sine())


def test_ev_t028_clean_periodic_fixture_reports_valid_f0_and_low_distortion(
    sine_case: SyntheticCase,
) -> None:
    samples = extract_segment(sine_case.record)
    summary = analyze_reference(
        samples,
        _SAMPLE_RATE_HZ,
        fmin_hz=_FMIN_HZ,
        fmax_hz=_FMAX_HZ,
    )

    assert summary.applicable is True
    assert summary.f0_hz == pytest.approx(200.0, abs=2.0)
    assert summary.thd_percent is not None
    assert summary.thd_percent < 1.0
    assert summary.clipping_ratio == pytest.approx(0.0, abs=1e-6)
    assert summary.flat_top_detected is False


def test_ev_t029_clipped_and_harmonic_fixtures_match_deterministic_expectations() -> (
    None
):
    clipped_case = generate_clipped_sine(
        frequency_hz=200.0,
        sample_rate_hz=_SAMPLE_RATE_HZ,
        duration_s=0.05,
        amplitude=0.9,
        clip_level=0.5,
    )
    clipped_samples = extract_segment(clipped_case.record)
    clipped_summary = analyze_reference(
        clipped_samples,
        _SAMPLE_RATE_HZ,
        fmin_hz=_FMIN_HZ,
        fmax_hz=_FMAX_HZ,
    )
    expected_clipping = analyze_clipping(clipped_samples)
    assert clipped_summary.applicable is True
    assert clipped_summary.clipping_ratio == pytest.approx(
        expected_clipping.clipping_ratio,
        rel=0.0,
        abs=1e-6,
    )
    assert clipped_summary.flat_top_detected is expected_clipping.flat_top_detected

    from signal_diag.evaluation.external.transforms import inject_second_harmonic

    harmonic_samples = inject_second_harmonic(
        _canonical_sine(),
        alpha=0.15,
        post_gain=0.8,
    ).samples
    harmonic_summary = analyze_reference(
        harmonic_samples,
        _SAMPLE_RATE_HZ,
        fmin_hz=_FMIN_HZ,
        fmax_hz=_FMAX_HZ,
    )
    expected_harmonic = analyze_harmonic_distortion(
        harmonic_samples,
        _SAMPLE_RATE_HZ,
        fmin_hz=_FMIN_HZ,
        fmax_hz=_FMAX_HZ,
    )
    assert harmonic_summary.applicable is True
    assert harmonic_summary.thd_percent == pytest.approx(
        expected_harmonic.thd_percent,
        rel=0.0,
        abs=1e-4,
    )
    order_2 = next(
        component.relative_amplitude
        for component in expected_harmonic.components
        if component.order == 2
    )
    assert harmonic_summary.order_2_relative_amplitude == pytest.approx(
        order_2,
        rel=0.0,
        abs=1e-6,
    )


def test_ev_t029_combined_fixture_reports_both_clipping_and_harmonics() -> None:
    from signal_diag.evaluation.external.models import TransformConfig
    from signal_diag.evaluation.external.transforms import apply_combined

    combined_samples = apply_combined(
        _canonical_sine(),
        TransformConfig(
            kind="combined",
            tail_proportion=0.05,
            alpha=0.15,
            post_gain=0.8,
            input_sha256=_digest(_canonical_sine()),
            output_sha256="d" * 64,
            parameters_identity="combined_test",
        ),
    ).samples
    summary = analyze_reference(
        combined_samples,
        _SAMPLE_RATE_HZ,
        fmin_hz=_FMIN_HZ,
        fmax_hz=_FMAX_HZ,
    )

    assert summary.applicable is True
    assert summary.clipping_ratio is not None
    assert summary.clipping_ratio > 0.0
    assert summary.order_2_relative_amplitude is not None
    assert summary.order_2_relative_amplitude > 0.0
    assert summary.thd_percent is not None


def test_ev_t029_unvoiced_fixture_is_not_applicable() -> None:
    noise_case = generate_white_noise(
        sample_rate_hz=_SAMPLE_RATE_HZ,
        duration_s=0.05,
        rms=0.1,
        seed=1234,
    )
    samples = extract_segment(noise_case.record)
    summary = analyze_reference(
        samples,
        _SAMPLE_RATE_HZ,
        fmin_hz=_FMIN_HZ,
        fmax_hz=_FMAX_HZ,
    )
    f0 = estimate_f0_autocorrelation(
        samples,
        _SAMPLE_RATE_HZ,
        fmin_hz=_FMIN_HZ,
        fmax_hz=_FMAX_HZ,
    )

    assert f0.voiced is False
    assert summary.applicable is False
    assert summary.f0_hz is None
    assert summary.thd_percent is None


_FORBIDDEN_REFERENCE_MODULES = frozenset(
    {
        "signal_diag.agent",
        "signal_diag.evaluation.scoring",
        "signal_diag.evaluation.runner",
        "signal_diag.evaluation.reporting",
    },
)


def test_ev_t030_reference_module_has_no_forbidden_imports() -> None:
    module_path = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "signal_diag"
        / "evaluation"
        / "external"
        / "reference.py"
    )
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_roots.add(node.module)

    violations = sorted(
        module
        for module in imported_roots
        if any(
            module == forbidden or module.startswith(f"{forbidden}.")
            for forbidden in _FORBIDDEN_REFERENCE_MODULES
        )
    )
    assert violations == []


def test_ev_t030_reference_import_has_no_transitive_agent_dependency() -> None:
    external_root = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "signal_diag"
        / "evaluation"
        / "external"
    )
    pending = [external_root / "reference.py"]
    visited: set[Path] = set()
    violations: set[str] = set()
    while pending:
        module_path = pending.pop()
        if module_path in visited:
            continue
        visited.add(module_path)
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            module = node.module
            if any(
                module == forbidden or module.startswith(f"{forbidden}.")
                for forbidden in _FORBIDDEN_REFERENCE_MODULES
            ):
                violations.add(module)
            prefix = "signal_diag.evaluation.external."
            if module.startswith(prefix):
                local = external_root / f"{module.removeprefix(prefix)}.py"
                if local.is_file():
                    pending.append(local)
    assert sorted(violations) == []
