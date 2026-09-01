"""Checkpoint B — external manifest serialization (EV-T009–EV-T010)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from signal_diag.evaluation.external.manifest import (
    canonical_json_bytes,
    load_external_manifest,
    manifest_sha256,
)
from signal_diag.evaluation.external.models import (
    ExternalCase,
    ExternalDatasetManifest,
    TransformConfig,
)
from tests.evaluation.external.conftest import (
    make_external_case,
    make_external_manifest,
)


def test_ev_t009_canonical_manifest_identity() -> None:
    manifest = make_external_manifest()
    assert manifest.dataset_id == "s1-distortion-external-wav"
    assert manifest.version == "1.0.0"
    assert manifest.study_id == "v0.2-external-wav-validity-1"
    assert manifest.external_scoring_id == "signal_diag.external_scoring"
    assert manifest.external_scoring_version == "1.0.0"

    with pytest.raises(ValidationError):
        make_external_manifest(dataset_id="other-dataset")
    with pytest.raises(ValidationError):
        make_external_manifest(study_id="other-study")
    with pytest.raises(ValidationError):
        make_external_manifest(external_scoring_version="2.0.0")


def test_ev_t010_manifest_fingerprint_is_stable(tmp_path: Path) -> None:
    manifest = make_external_manifest(
        cases=(
            make_external_case(case_id="0123456789abcdef"),
            make_external_case(
                case_id="fedcba9876543210",
                split="validation",
                analysis_wav_path="assets/validation/extwav_validation_fedcba9876543210.wav",
                confidence="reference_supported",
                external_class="clean",
                transform=None,
                acceptable_outcomes=("no_supported_fault",),
                causal_faults=(),
            ),
        ),
    )
    first = manifest_sha256(manifest)
    second = manifest_sha256(manifest)
    assert first == second
    assert len(first) == 64

    payload = json.loads(canonical_json_bytes(manifest).decode("utf-8"))
    assert list(payload.keys()) == sorted(payload.keys())
    assert canonical_json_bytes(manifest).endswith(b"\n")


def test_load_external_manifest_round_trip(tmp_path: Path) -> None:
    manifest = make_external_manifest()
    path = tmp_path / "study_manifest.json"
    path.write_bytes(canonical_json_bytes(manifest))
    loaded = load_external_manifest(path)
    assert isinstance(loaded, ExternalDatasetManifest)
    assert manifest_sha256(loaded) == manifest_sha256(manifest)


def test_load_external_manifest_rejects_unknown_schema_version(tmp_path: Path) -> None:
    path = tmp_path / "study_manifest.json"
    payload = json.loads(canonical_json_bytes(make_external_manifest()).decode("utf-8"))
    payload["schema_version"] = "9.9"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_external_manifest(path)


def test_canonical_json_bytes_rejects_nan() -> None:
    case = make_external_case()
    assert case.transform is not None
    bad_transform = TransformConfig.model_construct(
        kind=case.transform.kind,
        tail_proportion=float("nan"),
        alpha=case.transform.alpha,
        post_gain=case.transform.post_gain,
        input_sha256=case.transform.input_sha256,
        output_sha256=case.transform.output_sha256,
        parameters_identity=case.transform.parameters_identity,
    )
    case_data = case.model_dump()
    case_data["transform"] = bad_transform
    corrupted_case = ExternalCase.model_construct(**case_data)
    manifest_data = make_external_manifest().model_dump()
    manifest_data["cases"] = (corrupted_case,)
    corrupted = ExternalDatasetManifest.model_construct(**manifest_data)
    with pytest.raises(ValueError, match="allow_nan=False"):
        canonical_json_bytes(corrupted)


def test_manifest_sha256_matches_manual_hash() -> None:
    manifest = make_external_manifest()
    expected = hashlib.sha256(canonical_json_bytes(manifest)).hexdigest()
    assert manifest_sha256(manifest) == expected
