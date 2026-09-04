"""T-CX138: development-only growth threshold calibration."""

from __future__ import annotations

from signal_diag.evaluation.contextual.calibration import (
    CONTEXTUAL_GROWTH_CANDIDATES,
    calibrate_even_growth_threshold,
    contextual_implementation_sha256,
    stable_code_sha,
)
from signal_diag.evaluation.contextual.models import ContextualManifest


def test_t_cx138_selects_largest_passing_candidate(
    validation_manifest: ContextualManifest,
) -> None:
    report = calibrate_even_growth_threshold(
        manifest=validation_manifest,
        control_growth_percents=(0.1, 0.2, 0.3),
        positive_growth_percents=(2.5, 3.0, 4.0, 5.0),
        code_sha256=stable_code_sha("fixture"),
    )
    assert report.calibration_status == "selected"
    assert report.selected_threshold_percent == 2.0
    assert tuple(row.threshold_percent for row in report.candidates) == (
        CONTEXTUAL_GROWTH_CANDIDATES
    )


def test_t_cx138b_blocks_when_no_candidate_qualifies(
    validation_manifest: ContextualManifest,
) -> None:
    report = calibrate_even_growth_threshold(
        manifest=validation_manifest,
        control_growth_percents=(10.0, 11.0),
        positive_growth_percents=(0.1, 0.2),
        code_sha256=stable_code_sha("blocked"),
    )
    assert report.calibration_status == "blocked"
    assert report.selected_threshold_percent is None


def test_t_cx138c_implementation_sha_tracks_package_bytes() -> None:
    digest = contextual_implementation_sha256()
    assert len(digest) == 64
    assert digest != stable_code_sha("signal_diag.evaluation.contextual")
