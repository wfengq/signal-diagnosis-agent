import json

import pytest
from pydantic import ValidationError

from signal_diag.tools.contracts import (
    ClippingInput,
    ClippingOutput,
    ContextualDistortionInput,
    FundamentalInput,
    HarmonicDistortionInput,
    SpectrumInput,
    ToolName,
)
from signal_diag.tools.evidence import Evidence
from signal_diag.tools.registry import get_tool_descriptors
from signal_diag.tools.results import ToolResult

VALID_OUTPUT = ClippingOutput(
    detected=False,
    clipping_ratio=0.0,
    clipped_samples=0,
    clipping_events=0,
    longest_event_samples=0,
    peak_abs=0.5,
    full_scale_detected=False,
    flat_top_detected=False,
)

VALID_EVIDENCE = Evidence(
    evidence_id="ev_detected",
    source_tool="detect_clipping",
    call_id="call_example",
    metric="clipping_detected",
    value=False,
    channel="mixdown",
)

EXPECTED_TOOL_NAMES: frozenset[ToolName] = frozenset(
    {
        "detect_clipping",
        "analyze_spectrum",
        "estimate_fundamental",
        "analyze_harmonic_distortion",
        "analyze_contextual_distortion",
    }
)


@pytest.mark.parametrize(
    "status,result,evidence_items,warnings,error_message",
    [
        ("success", None, (), (), None),
        ("invalid", None, (), (), None),
        ("error", VALID_OUTPUT, (), (), "failed"),
        ("error", None, (VALID_EVIDENCE,), (), "failed"),
        ("success", VALID_OUTPUT, (), (), "unexpected"),
    ],
)
def test_t062_tool_result_rejects_invalid_status_combinations(
    status: str,
    result: ClippingOutput | None,
    evidence_items: tuple[Evidence, ...],
    warnings: tuple[str, ...],
    error_message: str | None,
) -> None:
    with pytest.raises(ValidationError):
        ToolResult[ClippingOutput](
            call_id="call_example",
            tool_name="detect_clipping",
            status=status,  # type: ignore[arg-type]
            result=result,
            evidence=evidence_items,
            warnings=warnings,
            error_message=error_message,
        )


@pytest.mark.parametrize(
    "status,result,evidence_items,warnings,error_message",
    [
        ("success", VALID_OUTPUT, (VALID_EVIDENCE,), (), None),
        ("invalid", VALID_OUTPUT, (), ("metric not applicable",), None),
        ("error", None, (), (), "signal not found"),
    ],
)
def test_t062_tool_result_accepts_valid_status_combinations(
    status: str,
    result: ClippingOutput | None,
    evidence_items: tuple[Evidence, ...],
    warnings: tuple[str, ...],
    error_message: str | None,
) -> None:
    parsed = ToolResult[ClippingOutput](
        call_id="call_example",
        tool_name="detect_clipping",
        status=status,  # type: ignore[arg-type]
        result=result,
        evidence=evidence_items,
        warnings=warnings,
        error_message=error_message,
    )
    assert parsed.status == status


def test_t063_get_tool_descriptors_exact_set_and_json_schemas() -> None:
    descriptors = get_tool_descriptors()

    assert len(descriptors) == 5
    assert {descriptor.name for descriptor in descriptors} == EXPECTED_TOOL_NAMES

    for descriptor in descriptors:
        json.dumps(descriptor.input_schema)

    assert "call_order" not in json.dumps(
        {descriptor.name: descriptor.model_dump() for descriptor in descriptors}
    ).lower()


def test_fundamental_input_rejects_non_increasing_frequency_band() -> None:
    with pytest.raises(ValidationError):
        FundamentalInput(fmin_hz=500.0, fmax_hz=100.0)


def test_harmonic_distortion_input_rejects_non_increasing_frequency_band() -> None:
    with pytest.raises(ValidationError):
        HarmonicDistortionInput(fmin_hz=500.0, fmax_hz=100.0)


def test_registry_input_schemas_match_pydantic_models() -> None:
    schema_by_tool = {
        descriptor.name: descriptor.input_schema
        for descriptor in get_tool_descriptors()
    }

    assert schema_by_tool["detect_clipping"] == ClippingInput.model_json_schema()
    assert schema_by_tool["analyze_spectrum"] == SpectrumInput.model_json_schema()
    assert (
        schema_by_tool["estimate_fundamental"] == FundamentalInput.model_json_schema()
    )
    assert (
        schema_by_tool["analyze_harmonic_distortion"]
        == HarmonicDistortionInput.model_json_schema()
    )
    assert (
        schema_by_tool["analyze_contextual_distortion"]
        == ContextualDistortionInput.model_json_schema()
    )
