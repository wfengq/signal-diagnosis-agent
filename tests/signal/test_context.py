"""T-CX004–T-CX010: StimulusContext and EffectiveCapabilities contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from signal_diag.signal.context import EffectiveCapabilities, StimulusContext


def test_t_cx004_single_signal_accepts_minimal_context() -> None:
    ctx = StimulusContext(
        mode="single_signal",
        test_signal_id="sig_test",
        assertion_source="user_supplied",
    )
    assert ctx.mode == "single_signal"
    assert ctx.reference_signal_id is None


def test_t_cx005_single_signal_rejects_reference() -> None:
    with pytest.raises(ValidationError):
        StimulusContext(
            mode="single_signal",
            test_signal_id="sig_test",
            reference_signal_id="sig_ref",
            assertion_source="user_supplied",
        )


def test_t_cx006_nominal_tone_requires_frequency() -> None:
    with pytest.raises(ValidationError):
        StimulusContext(
            mode="nominal_single_tone",
            test_signal_id="sig_test",
            assertion_source="user_supplied",
            stimulus_kind="single_tone",
        )


def test_t_cx007_paired_reference_requires_distinct_reference() -> None:
    with pytest.raises(ValidationError):
        StimulusContext(
            mode="paired_reference",
            test_signal_id="sig_same",
            reference_signal_id="sig_same",
            assertion_source="user_supplied",
        )


def test_t_cx008_nominal_tone_accepts_valid_declaration() -> None:
    ctx = StimulusContext(
        mode="nominal_single_tone",
        test_signal_id="sig_test",
        assertion_source="evaluation_manifest",
        stimulus_kind="single_tone",
        nominal_fundamental_hz=440.0,
    )
    assert ctx.nominal_fundamental_hz == 440.0


def test_t_cx009_nominal_frequency_must_be_finite_positive() -> None:
    with pytest.raises(ValidationError):
        StimulusContext(
            mode="nominal_single_tone",
            test_signal_id="sig_test",
            assertion_source="user_supplied",
            stimulus_kind="single_tone",
            nominal_fundamental_hz=float("nan"),
        )
    with pytest.raises(ValidationError):
        StimulusContext(
            mode="nominal_single_tone",
            test_signal_id="sig_test",
            assertion_source="user_supplied",
            stimulus_kind="single_tone",
            nominal_fundamental_hz=-1.0,
        )


def test_t_cx010_models_are_frozen() -> None:
    ctx = StimulusContext(
        mode="paired_reference",
        test_signal_id="sig_test",
        reference_signal_id="sig_ref",
        assertion_source="user_supplied",
    )
    caps = EffectiveCapabilities(paired_harmonic_attribution=True)
    with pytest.raises(ValidationError):
        ctx.mode = "single_signal"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        caps.clipping = False  # type: ignore[misc]
