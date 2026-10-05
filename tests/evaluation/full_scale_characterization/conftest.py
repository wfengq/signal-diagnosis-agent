"""Shared fixtures for characterization manifest tests."""

from __future__ import annotations

import time

import pytest

from signal_diag.evaluation.full_scale_characterization.constants import ROUND_1
from signal_diag.evaluation.full_scale_characterization.manifest import build_manifest
from signal_diag.evaluation.full_scale_characterization.models import Manifest

ROUND_1_WALL_BUDGET_S = 60.0

_ROUND_1_MANIFEST: Manifest | None = None
_ROUND_1_BUILD_ELAPSED_S: float | None = None


@pytest.fixture(scope="session")
def round_1_manifest() -> Manifest:
    """Build ROUND_1 once per session; enforce the 60s wall budget on that cold build."""
    global _ROUND_1_MANIFEST, _ROUND_1_BUILD_ELAPSED_S
    if _ROUND_1_MANIFEST is None:
        start = time.monotonic()
        _ROUND_1_MANIFEST = build_manifest(ROUND_1)
        _ROUND_1_BUILD_ELAPSED_S = time.monotonic() - start
        assert _ROUND_1_BUILD_ELAPSED_S < ROUND_1_WALL_BUDGET_S, (
            f"BLOCKED: ROUND_1 build took {_ROUND_1_BUILD_ELAPSED_S:.1f}s"
        )
    return _ROUND_1_MANIFEST


@pytest.fixture(scope="session")
def round_1_build_elapsed_s(round_1_manifest: Manifest) -> float:
    assert _ROUND_1_BUILD_ELAPSED_S is not None
    return _ROUND_1_BUILD_ELAPSED_S
