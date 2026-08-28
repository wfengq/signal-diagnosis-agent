"""Acceptance tests for shared DSP preprocessing helpers."""

import numpy as np
import pytest

from signal_diag.dsp import peak_abs, remove_dc, rms


def test_t025_remove_dc_does_not_mutate() -> None:
    x = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    before = x.copy()
    y = remove_dc(x)
    assert np.mean(y) == pytest.approx(0.0, abs=1e-7)
    np.testing.assert_array_equal(x, before)


def test_t026_rms_and_peak_known_values() -> None:
    x = np.array([3.0, 4.0], dtype=np.float32)
    assert rms(x) == pytest.approx(np.sqrt(12.5))
    assert peak_abs(x) == pytest.approx(4.0)


@pytest.mark.parametrize(
    "samples",
    [
        np.array([], dtype=np.float64),
        np.array([np.nan], dtype=np.float64),
        np.array([np.inf], dtype=np.float64),
        np.array([[1.0], [2.0]], dtype=np.float64),
    ],
)
@pytest.mark.parametrize("helper", [remove_dc, rms, peak_abs])
def test_t027_preprocess_validation_rejects_invalid_input(
    samples: np.ndarray,
    helper: object,
) -> None:
    with pytest.raises(ValueError, match="samples must be finite, non-empty, and one-dimensional"):
        helper(samples)
