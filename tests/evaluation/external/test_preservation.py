"""Preservation tests for external WAV validity study (EV-T001, EV-T004)."""

from __future__ import annotations

from pathlib import Path

import pytest

from signal_diag.evaluation.external.sealing import verify_protected_assets


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_ev_t001_protected_v02_assets_match_frozen_hashes(repo_root: Path) -> None:
    verify_protected_assets(
        repo_root,
        repo_root
        / "docs/evaluations/v0_2_external_wav/protocol/protected_assets.sha256",
    )


def test_protected_manifest_cannot_omit_a_protected_file(
    repo_root: Path,
    tmp_path: Path,
) -> None:
    source = (
        repo_root
        / "docs/evaluations/v0_2_external_wav/protocol/protected_assets.sha256"
    )
    lines = source.read_text(encoding="utf-8").splitlines()
    omitted = next(
        index
        for index, line in enumerate(lines)
        if "docs/demo/phase5/v0_2_acceptance/" in line
    )
    incomplete = tmp_path / "protected_assets.sha256"
    incomplete.write_text(
        "\n".join(lines[:omitted] + lines[omitted + 1 :]) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing protected asset record"):
        verify_protected_assets(repo_root, incomplete)
