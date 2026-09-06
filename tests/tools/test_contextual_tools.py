"""T-CX031–T-CX045: contextual Tool contracts and Evidence."""

from __future__ import annotations

import json

import numpy as np
import pytest
from pydantic import ValidationError

from signal_diag.signal import InMemorySignalRepository, StimulusContext
from signal_diag.signal.synthetic import (
    generate_clipped_sine,
    generate_harmonic_sine,
    generate_sine,
)
from signal_diag.tools.contracts import ContextualDistortionInput
from signal_diag.tools.registry import get_tool_descriptors
from signal_diag.tools.service import SignalToolService


def _put_pair(
    repository: InMemorySignalRepository,
    *,
    h2_alpha: float | None = None,
) -> StimulusContext:
    reference = generate_sine(
        sample_rate_hz=48_000,
        duration_s=1.0,
        frequency_hz=440.0,
        amplitude=0.5,
    )
    if h2_alpha is None:
        test = generate_sine(
            sample_rate_hz=48_000,
            duration_s=1.0,
            frequency_hz=440.0,
            amplitude=0.5,
        )
    else:
        test = generate_harmonic_sine(
            sample_rate_hz=48_000,
            duration_s=1.0,
            fundamental_hz=440.0,
            fundamental_amplitude=0.5,
            harmonic_ratios={2: h2_alpha},
        )
    repository.put(reference.record)
    repository.put(test.record)
    return StimulusContext(
        mode="paired_reference",
        test_signal_id=test.record.meta.signal_id,
        reference_signal_id=reference.record.meta.signal_id,
        assertion_source="user_supplied",
    )


def test_t_cx031_contextual_input_accepts_selection_only() -> None:
    parsed = ContextualDistortionInput(max_harmonic_order=5, window="hann")
    assert parsed.max_harmonic_order == 5
    assert parsed.window == "hann"
    assert parsed.channel == "mixdown"


def test_t_cx032_contextual_input_rejects_bad_window() -> None:
    with pytest.raises(ValidationError):
        ContextualDistortionInput(window="hamming")  # type: ignore[arg-type]


def test_t_cx033_contextual_input_rejects_bad_order() -> None:
    with pytest.raises(ValidationError):
        ContextualDistortionInput(max_harmonic_order=1)


def test_t_cx034_contextual_tool_args_cannot_choose_signal_ids() -> None:
    schema = ContextualDistortionInput.model_json_schema()
    properties = schema.get("properties", {})
    assert "signal_id" not in properties
    assert "reference_signal_id" not in properties
    assert "test_signal_id" not in properties


def test_t_cx035_paired_tool_resolves_ids_from_context(
    repository: InMemorySignalRepository,
) -> None:
    context = _put_pair(repository, h2_alpha=0.3)
    service = SignalToolService(repository)
    result = service.analyze_contextual_distortion(
        context,
        ContextualDistortionInput(),
    )
    assert result.status == "success"
    assert result.result is not None
    assert result.result.valid is True
    assert result.result.mode == "paired_reference"
    assert result.result.even_harmonic_growth_percent is not None
    assert result.result.even_harmonic_growth_percent > 5.0


def test_t_cx036_nominal_tool_uses_declared_fundamental(
    repository: InMemorySignalRepository,
) -> None:
    case = generate_sine(
        sample_rate_hz=48_000,
        duration_s=1.0,
        frequency_hz=440.0,
        amplitude=0.5,
    )
    repository.put(case.record)
    context = StimulusContext(
        mode="nominal_single_tone",
        test_signal_id=case.record.meta.signal_id,
        nominal_fundamental_hz=440.0,
        stimulus_kind="single_tone",
        assertion_source="user_supplied",
    )
    service = SignalToolService(repository)
    result = service.analyze_contextual_distortion(
        context,
        ContextualDistortionInput(),
    )
    assert result.status == "success"
    assert result.result is not None
    assert result.result.valid is True
    assert result.result.comparison_f0_hz == pytest.approx(440.0)


def test_t_cx037_single_signal_mode_rejects_contextual_tool(
    repository: InMemorySignalRepository,
) -> None:
    case = generate_sine(
        sample_rate_hz=48_000,
        duration_s=1.0,
        frequency_hz=440.0,
        amplitude=0.5,
    )
    repository.put(case.record)
    context = StimulusContext(
        mode="single_signal",
        test_signal_id=case.record.meta.signal_id,
        assertion_source="user_supplied",
    )
    service = SignalToolService(repository)
    result = service.analyze_contextual_distortion(
        context,
        ContextualDistortionInput(),
    )
    assert result.status == "error"
    assert result.result is None
    assert result.evidence == ()
    assert result.error_message is not None
    assert "single_signal" in result.error_message


def test_t_cx038_missing_reference_is_error(
    repository: InMemorySignalRepository,
) -> None:
    test = generate_sine(
        sample_rate_hz=48_000,
        duration_s=1.0,
        frequency_hz=440.0,
        amplitude=0.5,
    )
    repository.put(test.record)
    context = StimulusContext(
        mode="paired_reference",
        test_signal_id=test.record.meta.signal_id,
        reference_signal_id="sig_absent_reference",
        assertion_source="user_supplied",
    )
    service = SignalToolService(repository)
    result = service.analyze_contextual_distortion(
        context,
        ContextualDistortionInput(),
    )
    assert result.status == "error"
    assert result.evidence == ()


def test_t_cx039_invalid_comparison_emits_context_valid_false(
    repository: InMemorySignalRepository,
) -> None:
    reference = generate_sine(
        sample_rate_hz=48_000,
        duration_s=1.0,
        frequency_hz=440.0,
        amplitude=0.5,
    )
    test = generate_sine(
        sample_rate_hz=44_100,
        duration_s=1.0,
        frequency_hz=440.0,
        amplitude=0.5,
    )
    repository.put(reference.record)
    repository.put(test.record)
    context = StimulusContext(
        mode="paired_reference",
        test_signal_id=test.record.meta.signal_id,
        reference_signal_id=reference.record.meta.signal_id,
        assertion_source="user_supplied",
    )
    service = SignalToolService(repository)
    result = service.analyze_contextual_distortion(
        context,
        ContextualDistortionInput(),
    )
    assert result.status == "invalid"
    assert result.result is not None
    assert result.result.valid is False
    metrics = {item.metric: item for item in result.evidence}
    assert metrics["context_valid"].value is False
    assert metrics["context_valid"].validity == "valid"
    assert metrics["invalid_reason"].value == "sample_rate_mismatch"


def test_t_cx040_output_json_contains_no_raw_arrays(
    repository: InMemorySignalRepository,
) -> None:
    context = _put_pair(repository, h2_alpha=0.2)
    service = SignalToolService(repository)
    result = service.analyze_contextual_distortion(
        context,
        ContextualDistortionInput(),
    )
    payload = result.model_dump_json().lower()
    assert '"samples"' not in payload
    assert "fft" not in payload
    tree = json.loads(result.model_dump_json())

    def _walk(value: object) -> None:
        if isinstance(value, np.ndarray):
            pytest.fail("ndarray leaked into ToolResult JSON")
        if isinstance(value, dict):
            assert "samples" not in value
            assert "frequencies_hz" not in value
            assert "magnitude_db" not in value
            for item in value.values():
                _walk(item)
        elif isinstance(value, list):
            for item in value:
                _walk(item)

    _walk(tree)


def test_t_cx041_evidence_ids_are_deterministic(
    repository: InMemorySignalRepository,
) -> None:
    context = _put_pair(repository)
    service = SignalToolService(repository)
    first = service.analyze_contextual_distortion(
        context,
        ContextualDistortionInput(),
    )
    second_service = SignalToolService(repository)
    second = second_service.analyze_contextual_distortion(
        context,
        ContextualDistortionInput(),
    )
    assert [item.evidence_id for item in first.evidence] == [
        item.evidence_id for item in second.evidence
    ]
    assert first.call_id == second.call_id


def test_t_cx042_success_evidence_includes_growth_metrics(
    repository: InMemorySignalRepository,
) -> None:
    context = _put_pair(repository, h2_alpha=0.25)
    service = SignalToolService(repository)
    result = service.analyze_contextual_distortion(
        context,
        ContextualDistortionInput(),
    )
    metrics = {item.metric for item in result.evidence}
    assert "context_valid" in metrics
    assert "mode" in metrics
    assert "algorithm_version" in metrics
    assert "even_harmonic_growth_percent" in metrics
    assert "test_thd_percent" in metrics
    assert "f0_relative_delta" in metrics
    assert "test_series_kind" in metrics
    growth = next(
        item for item in result.evidence if item.metric == "even_harmonic_growth_percent"
    )
    assert growth.unit == "%"
    assert growth.source_tool == "analyze_contextual_distortion"


def test_t_cx043_components_are_compact_scalars(
    repository: InMemorySignalRepository,
) -> None:
    context = _put_pair(repository, h2_alpha=0.2)
    service = SignalToolService(repository)
    result = service.analyze_contextual_distortion(
        context,
        ContextualDistortionInput(),
    )
    assert result.result is not None
    assert result.result.components
    for component in result.result.components:
        assert component.order >= 2
        assert component.positive_growth >= 0.0


def test_t_cx044_not_applicable_numeric_on_invalid(
    repository: InMemorySignalRepository,
) -> None:
    reference = generate_sine(
        sample_rate_hz=48_000,
        duration_s=1.0,
        frequency_hz=440.0,
        amplitude=0.5,
    )
    test = generate_sine(
        sample_rate_hz=44_100,
        duration_s=1.0,
        frequency_hz=440.0,
        amplitude=0.5,
    )
    repository.put(reference.record)
    repository.put(test.record)
    context = StimulusContext(
        mode="paired_reference",
        test_signal_id=test.record.meta.signal_id,
        reference_signal_id=reference.record.meta.signal_id,
        assertion_source="user_supplied",
    )
    result = SignalToolService(repository).analyze_contextual_distortion(
        context,
        ContextualDistortionInput(),
    )
    growth = next(
        (
            item
            for item in result.evidence
            if item.metric == "even_harmonic_growth_percent"
        ),
        None,
    )
    assert growth is not None
    assert growth.validity == "not_applicable"


def test_t_cx045_registry_includes_contextual_tool() -> None:
    names = {descriptor.name for descriptor in get_tool_descriptors()}
    assert "analyze_contextual_distortion" in names
    descriptor = next(
        item
        for item in get_tool_descriptors()
        if item.name == "analyze_contextual_distortion"
    )
    assert "signal_id" not in descriptor.input_schema.get("properties", {})


@pytest.mark.parametrize(
    ("test_sample_rate_hz", "clipped", "expected_status", "expected_mechanism"),
    [
        (48_000, True, "success", True),
        (48_000, False, "success", False),
        (44_100, True, "invalid", True),
    ],
)
def test_t_cx233_emits_one_compact_test_clipping_mechanism_item(
    repository: InMemorySignalRepository,
    test_sample_rate_hz: int,
    clipped: bool,
    expected_status: str,
    expected_mechanism: bool,
) -> None:
    reference = generate_sine(
        sample_rate_hz=48_000,
        duration_s=1.0,
        frequency_hz=440.0,
        amplitude=0.4,
    )
    if clipped:
        test = generate_clipped_sine(
            sample_rate_hz=test_sample_rate_hz,
            duration_s=1.0,
            frequency_hz=440.0,
            amplitude=1.2,
            clip_level=0.99,
        )
    else:
        test = generate_sine(
            sample_rate_hz=test_sample_rate_hz,
            duration_s=1.0,
            frequency_hz=440.0,
            amplitude=0.4,
        )
    repository.put(reference.record)
    repository.put(test.record)
    context = StimulusContext(
        mode="paired_reference",
        test_signal_id=test.record.meta.signal_id,
        reference_signal_id=reference.record.meta.signal_id,
        assertion_source="user_supplied",
    )

    result = SignalToolService(repository).analyze_contextual_distortion(
        context,
        ContextualDistortionInput(),
    )

    assert result.status == expected_status
    assert result.result is not None
    assert result.result.test_clipping_mechanism is expected_mechanism
    items = [
        item for item in result.evidence if item.metric == "test_clipping_mechanism"
    ]
    assert len(items) == 1
    assert items[0].source_tool == "analyze_contextual_distortion"
    assert items[0].validity == "valid"
    assert items[0].value is expected_mechanism
    payload = result.model_dump_json().lower()
    assert '"samples"' not in payload
    assert "fft" not in payload


def test_t_cx233_preserves_existing_clipping_evidence_ordinals(
    repository: InMemorySignalRepository,
) -> None:
    context = _put_pair(repository)
    result = SignalToolService(repository).analyze_contextual_distortion(
        context,
        ContextualDistortionInput(),
    )
    by_metric = {item.metric: item.evidence_id for item in result.evidence}

    assert by_metric["test_clipping_ratio"].endswith("_016")
    assert by_metric["test_flat_top_detected"].endswith("_017")
    assert by_metric["test_clipping_mechanism"].endswith("_018")
