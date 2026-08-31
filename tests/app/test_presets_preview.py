"""Checkpoint V — isolated Demo presets and visualization preview (T234–T238)."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest

from signal_diag.app import (
    AppErrorDetail,
    DemoPresetId,
    build_demo_preset,
    build_waveform_preview,
    list_demo_presets,
)
from signal_diag.app.errors import InvalidRequestError, UnknownPresetError
from signal_diag.signal import InMemorySignalRepository
from signal_diag.signal.synthetic import generate_white_noise

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRESET_MODULE_PATH = PROJECT_ROOT / "src" / "signal_diag" / "app" / "presets.py"
PREVIEW_MODULE_PATH = PROJECT_ROOT / "src" / "signal_diag" / "app" / "preview.py"
PRESET_IDS: tuple[DemoPresetId, ...] = (
    "clean_periodic",
    "clipping",
    "harmonic_distortion",
    "combined_distortion",
    "noise_inconclusive",
)
EXPECTED_LABELS = {
    "clean_periodic": "Clean periodic",
    "clipping": "Clipping",
    "harmonic_distortion": "Harmonic distortion",
    "combined_distortion": "Combined distortion",
    "noise_inconclusive": "Inconclusive noise",
}
OPAQUE_SIGNAL_ID = re.compile(r"^sig_[0-9a-f]{32}$")
FORBIDDEN_ID_FRAGMENTS = ("clipping", "harmonic", "noise", "combined")
CASE_ID_MARKERS = ("case_v12_", "held-out", "held_out", "heldout")


def test_t234_catalog_is_exact() -> None:
    catalog = list_demo_presets()

    assert [item.preset_id for item in catalog] == [
        "clean_periodic",
        "clipping",
        "harmonic_distortion",
        "combined_distortion",
        "noise_inconclusive",
    ]
    assert len(catalog) == 5
    for item in catalog:
        assert item.channels == 1
        assert item.sample_rate_hz == 48_000
        assert item.duration_s == 1.0
        assert item.label == EXPECTED_LABELS[item.preset_id]
        assert item.label.strip()
        assert item.description.strip()
        assert "case_v12_" not in item.label
        assert "case_v12_" not in item.description


def test_t235_preset_modules_do_not_import_evaluation() -> None:
    for path in (PRESET_MODULE_PATH, PREVIEW_MODULE_PATH):
        source = path.read_text(encoding="utf-8")
        assert "signal_diag.evaluation" not in source
        lowered = source.lower()
        for marker in CASE_ID_MARKERS:
            assert marker not in source and marker not in lowered
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                modules = [node.module]
            else:
                continue
            for module in modules:
                assert module != "signal_diag.evaluation"
                assert not module.startswith("signal_diag.evaluation.")

    import signal_diag.app.presets as presets_mod

    module = sys.modules["signal_diag.app.presets"]
    assert module is presets_mod
    for name, value in vars(module).items():
        assert "evaluation" not in name.lower()
        if isinstance(value, ModuleType):
            assert "evaluation" not in (value.__name__ or "")


def test_t236_materialization_is_deterministic_but_ids_are_fresh() -> None:
    first = build_demo_preset("noise_inconclusive")
    second = build_demo_preset("noise_inconclusive")
    assert first.samples.tobytes() == second.samples.tobytes()
    assert first.meta.signal_id != second.meta.signal_id
    assert "noise" not in first.meta.signal_id

    seeded = generate_white_noise(
        sample_rate_hz=48_000,
        duration_s=1.0,
        rms=0.1,
        seed=5001,
    )
    np.testing.assert_array_equal(first.samples, seeded.record.samples)

    for preset_id in PRESET_IDS:
        left = build_demo_preset(preset_id)
        right = build_demo_preset(preset_id)
        assert left.samples.tobytes() == right.samples.tobytes()
        assert left.meta.signal_id != right.meta.signal_id
        for record in (left, right):
            assert OPAQUE_SIGNAL_ID.fullmatch(record.meta.signal_id)
            assert preset_id not in record.meta.signal_id
            lowered = record.meta.signal_id.lower()
            for fragment in FORBIDDEN_ID_FRAGMENTS:
                assert fragment not in lowered


def test_t237_presets_register_as_canonical_generated_records() -> None:
    repository = InMemorySignalRepository()
    for preset_id in PRESET_IDS:
        record = build_demo_preset(preset_id)
        assert record.samples.dtype == np.float32
        assert record.samples.flags.c_contiguous
        assert np.isfinite(record.samples).all()
        assert record.meta.source_type == "generated"
        assert record.meta.channels == 1
        assert record.meta.sample_rate_hz == 48_000
        assert record.meta.num_samples == 48_000

        original = np.array(record.samples, copy=True)
        repository.put(record)
        record.samples[0, 0] = 0.75
        retrieved = repository.get(record.meta.signal_id)
        np.testing.assert_array_equal(retrieved.samples, original)
        assert not np.shares_memory(retrieved.samples, record.samples)


def test_t238_preview_is_deterministic_visualization_only(monkeypatch: pytest.MonkeyPatch) -> None:
    def _forbid_tool_use(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("preview must not call Tool registry or execute a Tool")

    monkeypatch.setattr(
        "signal_diag.tools.registry.get_tool_descriptors",
        _forbid_tool_use,
    )
    monkeypatch.setattr(
        "signal_diag.tools.service.SignalToolService._run_tool",
        _forbid_tool_use,
    )
    monkeypatch.setattr(
        "signal_diag.tools.service.SignalToolService.detect_clipping",
        _forbid_tool_use,
    )

    short = np.array([0.10, -0.20, 0.30, -0.40], dtype=np.float32)
    short_preview = build_waveform_preview(short, sample_rate_hz=48_000)
    assert short_preview.label == "visualization_only"
    assert short_preview.sample_rate_hz == 48_000
    assert short_preview.original_num_samples == 4
    assert len(short_preview.points) == 4
    assert [point.sample_index for point in short_preview.points] == [0, 1, 2, 3]
    assert [point.amplitude for point in short_preview.points] == [
        float(value) for value in short
    ]
    for point in short_preview.points:
        assert point.time_s == pytest.approx(point.sample_index / 48_000)

    long_samples = np.linspace(-0.25, 0.25, 2_000, dtype=np.float32)
    long_samples[137] = -8.0
    long_samples[911] = 7.5
    long_preview = build_waveform_preview(long_samples, sample_rate_hz=48_000)
    assert long_preview.label == "visualization_only"
    assert long_preview.original_num_samples == 2_000
    assert 1 <= len(long_preview.points) <= 1_000
    long_indices = [point.sample_index for point in long_preview.points]
    assert long_indices == sorted(set(long_indices))
    assert 137 in long_indices
    assert 911 in long_indices
    for point in long_preview.points:
        assert point.time_s == pytest.approx(point.sample_index / 48_000)
        assert point.amplitude == float(long_samples[point.sample_index])

    max_before_min = np.array([1.0, 0.25, -1.0, 0.0], dtype=np.float32)
    ordered = build_waveform_preview(
        max_before_min,
        sample_rate_hz=48_000,
        max_points=2,
    )
    assert [point.sample_index for point in ordered.points] == [0, 2]
    assert ordered.points[0].amplitude == 1.0
    assert ordered.points[1].amplitude == -1.0

    for invalid_max_points in (0, 1, 1_001):
        with pytest.raises(InvalidRequestError) as exc_info:
            build_waveform_preview(
                short,
                sample_rate_hz=48_000,
                max_points=invalid_max_points,
            )
        assert exc_info.value.detail.code == "invalid_request"

    with pytest.raises(InvalidRequestError) as shape_info:
        build_waveform_preview(
            np.zeros((4, 1), dtype=np.float32),
            sample_rate_hz=48_000,
        )
    assert shape_info.value.detail.code == "invalid_request"


def test_unknown_preset_raises_unknown_preset_error() -> None:
    with pytest.raises(UnknownPresetError) as exc_info:
        build_demo_preset("not_a_preset")  # type: ignore[arg-type]
    assert exc_info.value.detail.code == "unknown_preset"
    assert isinstance(exc_info.value.detail, AppErrorDetail)
    assert exc_info.value.detail.message
