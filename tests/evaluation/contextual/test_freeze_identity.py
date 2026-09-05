"""T-CX138d: active freeze code identity resolves via record or amendment."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from signal_diag.evaluation.contextual.calibration import (
    contextual_implementation_sha256,
    resolve_active_freeze_code_sha256,
)

_ACTIVE_STUDY = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "evaluations"
    / "v0_3"
    / "contextual"
    / "development"
    / "study_v0_3_contextual_dev_1"
)


def test_t_cx138d_active_freeze_identity_resolves_via_record_or_amendment() -> None:
    freeze = json.loads(
        (_ACTIVE_STUDY / "profile_freeze_record.json").read_text(encoding="utf-8")
    )
    recorded = freeze["code_sha256"]
    current = contextual_implementation_sha256()
    resolved = resolve_active_freeze_code_sha256(_ACTIVE_STUDY)
    assert resolved == current
    if recorded != current:
        amendment = json.loads(
            (_ACTIVE_STUDY / "code_identity_amendment.json").read_text(encoding="utf-8")
        )
        rows = amendment if isinstance(amendment, list) else [amendment]
        active = next(
            row
            for row in rows
            if (
                row["original_calibration_code_sha256"] == recorded
                and row["current_implementation_sha256"] == current
            )
        )
        assert active["qualification_recompute_unchanged"] is True
        assert active["calibration_recompute_unchanged"] is True
        original = rows[0]
        assert (
            original["original_calibration_code_sha256"] == recorded
        )
        assert "b339dcf" in original["commits"]["typing_only"]
        assert "def199f" in original["commits"]["rematerialize"]


def test_t_cx138e_missing_amendment_rejects_mismatched_freeze(
    tmp_path: Path,
) -> None:
    freeze = {
        "code_sha256": "0" * 64,
        "selected_threshold_percent": 5.0,
    }
    (tmp_path / "profile_freeze_record.json").write_text(
        json.dumps(freeze), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="amendment"):
        resolve_active_freeze_code_sha256(tmp_path)
