"""Shared fixtures for characterization manifest tests."""

from __future__ import annotations

import pytest

from signal_diag.evaluation.full_scale_characterization.constants import ROUND_1
from signal_diag.evaluation.full_scale_characterization.manifest import build_manifest
from signal_diag.evaluation.full_scale_characterization.models import Manifest

_ROUND_1_MANIFEST: Manifest | None = None


@pytest.fixture(scope="session")
def round_1_manifest() -> Manifest:
    global _ROUND_1_MANIFEST
    if _ROUND_1_MANIFEST is None:
        _ROUND_1_MANIFEST = build_manifest(ROUND_1)
    return _ROUND_1_MANIFEST
