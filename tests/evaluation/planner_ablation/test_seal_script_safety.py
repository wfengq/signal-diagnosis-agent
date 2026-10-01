"""Seal script safety: verify is read-only; generate refuses an existing seal."""

from __future__ import annotations

import importlib.util
import json
from hashlib import sha256
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "seal_planner_ablation_protocol.py"
_COMMITTED_SEAL = (
    _REPO_ROOT
    / "docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_1/protocol_seal"
)


def _load_seal_script():
    spec = importlib.util.spec_from_file_location(
        "seal_planner_ablation_protocol_under_test", _SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tree_digests(root: Path) -> dict[str, str]:
    digests: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = str(path.relative_to(root)).replace("\\", "/")
        digests[relative] = sha256(path.read_bytes()).hexdigest()
    return digests


def test_committed_seal_verify_is_read_only() -> None:
    script = _load_seal_script()
    before = _tree_digests(_COMMITTED_SEAL)
    assert before, "committed protocol_seal must exist for this safety test"
    result = script.verify_existing_seal(seal_dir=_COMMITTED_SEAL)
    after = _tree_digests(_COMMITTED_SEAL)
    assert after == before
    assert result["status"] == "verify_ok"
    assert result["schedule_keys"] == 20


def test_generate_refuses_existing_committed_seal_without_mutation() -> None:
    script = _load_seal_script()
    before = _tree_digests(_COMMITTED_SEAL)
    with pytest.raises(FileExistsError, match="already exists"):
        script.generate_seal(seal_dir=_COMMITTED_SEAL)
    after = _tree_digests(_COMMITTED_SEAL)
    assert after == before


def test_generate_refuses_existing_empty_directory(tmp_path: Path) -> None:
    """Existing empty dir must be refused; only a missing path may be created."""
    script = _load_seal_script()
    destination = tmp_path / "empty_but_present"
    destination.mkdir()
    assert destination.is_dir()
    assert not any(destination.iterdir())
    with pytest.raises(FileExistsError, match="already exists"):
        script.generate_seal(seal_dir=destination)
    assert destination.is_dir()
    assert not any(destination.iterdir())


def test_generate_writes_only_when_destination_absent(tmp_path: Path) -> None:
    script = _load_seal_script()
    destination = tmp_path / "fresh_protocol_seal"
    assert not destination.exists()
    result = script.generate_seal(seal_dir=destination)
    assert destination.is_dir()
    assert (destination / "manifest.json").is_file()
    assert (destination / "seal.sha256").is_file()
    assert result["status"] == "generated"
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["case_count"] == 10
    assert manifest["scorable_slot_count"] == 40
    # Refuse second generate without deleting the tmp seal.
    with pytest.raises(FileExistsError, match="already exists"):
        script.generate_seal(seal_dir=destination)
