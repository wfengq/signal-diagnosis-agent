"""``identity.json`` for a characterization round (plan D; T-CX378).

``comparison`` items are checked before calibration and validation runs; any
difference refuses the run (a change requires a new round).  ``record_only``
items are informational and never block.
"""

from __future__ import annotations

import hashlib
import inspect
import platform
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

from signal_diag.dsp.clipping import analyze_clipping
from signal_diag.evaluation.full_scale_characterization.constants import (
    ROUND_1,
    CharacterizationConstants,
)
from signal_diag.tools.regression_full_scale import (
    FULL_SCALE_FACTS_VERSION,
    FULL_SCALE_MIN_CONSECUTIVE_SAMPLES,
)
from signal_diag.tools.regression_measurement import MEASUREMENT_VERSION

_PRODUCT_ROOT = Path(__file__).resolve().parents[2]
_PACKAGE_ROOT = Path(__file__).resolve().parent

MEASUREMENT_CLOSURE: tuple[str, ...] = (
    "dsp/full_scale.py",
    "dsp/clipping.py",
    "dsp/preprocess.py",
    "tools/regression_full_scale.py",
    "tools/regression_measurement.py",
    "tools/service.py",
    "tools/contracts.py",
    "tools/results.py",
    "signal/wav.py",
    "signal/factory.py",
    "signal/segment.py",
    "signal/models.py",
)
RECORD_ONLY_PACKAGE_FILES: tuple[str, ...] = ("reporting.py", "__main__.py")


class IdentityMismatch(Exception):
    """Comparison items of ``identity.json`` differ from the current environment."""


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _closure_digests() -> dict[str, str]:
    return {rel: _file_sha256(_PRODUCT_ROOT / rel) for rel in MEASUREMENT_CLOSURE}


def _package_files() -> list[str]:
    return sorted(
        p.name
        for p in _PACKAGE_ROOT.glob("*.py")
        if p.name not in RECORD_ONLY_PACKAGE_FILES
    )


def _package_sha256(files: list[str]) -> str:
    digest = hashlib.sha256()
    for name in files:
        digest.update(f"{name}\0{_file_sha256(_PACKAGE_ROOT / name)}\n".encode())
    return digest.hexdigest()


def _analyze_clipping_defaults() -> dict[str, Any]:
    params = inspect.signature(analyze_clipping).parameters
    return {
        name: param.default
        for name, param in params.items()
        if param.default is not inspect.Parameter.empty
    }


def _python_version() -> str:
    return platform.python_version()


def _numpy_version() -> str:
    return str(np.__version__)


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_PACKAGE_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    commit = result.stdout.strip()
    return commit if result.returncode == 0 and commit else None


def _product_tree_sha256() -> str:
    # Imported lazily: record-only, and kept off this package's import path.
    from signal_diag.evaluation.contextual.calibration import (
        contextual_product_tree_sha256,
    )

    return contextual_product_tree_sha256()


def compute_identity(constants: CharacterizationConstants = ROUND_1) -> dict[str, Any]:
    files = _package_files()
    return {
        "comparison": {
            "measurement_version": MEASUREMENT_VERSION,
            "full_scale_facts_version": FULL_SCALE_FACTS_VERSION,
            "full_scale_threshold": constants.full_scale_threshold,
            "min_consecutive_samples": FULL_SCALE_MIN_CONSECUTIVE_SAMPLES,
            "analyze_clipping_defaults": _analyze_clipping_defaults(),
            "measurement_closure_sha256": _closure_digests(),
            "package_files": files,
            "package_sha256": _package_sha256(files),
            "python_version": _python_version(),
            "numpy_version": _numpy_version(),
        },
        "record_only": {
            "git_commit": _git_commit(),
            "contextual_product_tree_sha256": _product_tree_sha256(),
            "reporting_sha256": _file_sha256(_PACKAGE_ROOT / "reporting.py"),
            "main_sha256": _file_sha256(_PACKAGE_ROOT / "__main__.py"),
        },
    }


def _flatten(prefix: str, value: Any, out: dict[str, Any]) -> None:
    if isinstance(value, dict):
        for key in sorted(value):
            _flatten(f"{prefix}.{key}" if prefix else str(key), value[key], out)
    else:
        out[prefix] = value


def identity_comparison_diff(recorded: dict[str, Any], current: dict[str, Any]) -> list[str]:
    """Keys whose comparison values differ (record-only items are ignored)."""
    a: dict[str, Any] = {}
    b: dict[str, Any] = {}
    _flatten("", recorded.get("comparison", {}), a)
    _flatten("", current.get("comparison", {}), b)
    return sorted(k for k in set(a) | set(b) if a.get(k, None) != b.get(k, None) or (k in a) != (k in b))


def assert_identity_matches(recorded: dict[str, Any], current: dict[str, Any]) -> None:
    diff = identity_comparison_diff(recorded, current)
    if diff:
        raise IdentityMismatch(
            "identity comparison items differ (start a new round): " + ", ".join(diff)
        )
