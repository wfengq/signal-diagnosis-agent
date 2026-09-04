"""T-CX140: contextual evaluation CLI."""

from __future__ import annotations

import json
from pathlib import Path

from signal_diag.evaluation.contextual.__main__ import main
from signal_diag.evaluation.contextual.manifest import canonical_json_bytes
from signal_diag.evaluation.contextual.models import ContextualManifest


def test_t_cx140_validate_manifest_cli(
    validation_manifest: ContextualManifest,
    tmp_path: Path,
) -> None:
    path = tmp_path / "manifest.json"
    path.write_bytes(canonical_json_bytes(validation_manifest))
    assert main(["validate-manifest", "--manifest", str(path)]) == 0


def test_t_cx140b_calibrate_cli(
    validation_manifest: ContextualManifest,
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_bytes(canonical_json_bytes(validation_manifest))
    controls = tmp_path / "controls.json"
    positives = tmp_path / "positives.json"
    controls.write_text(json.dumps([0.1, 0.2]), encoding="utf-8")
    positives.write_text(json.dumps([2.5, 3.0, 4.0]), encoding="utf-8")
    output = tmp_path / "calibration.json"
    code = main(
        [
            "calibrate",
            "--manifest",
            str(manifest_path),
            "--controls-json",
            str(controls),
            "--positives-json",
            str(positives),
            "--output",
            str(output),
        ]
    )
    assert code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["calibration_status"] == "selected"
