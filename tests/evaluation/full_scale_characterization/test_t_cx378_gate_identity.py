"""T-CX378: tighter validation gate, frozen-value sources in the identity set, round binding.

The gate protects against accidental use; it does not protect against deliberate
code changes (private helpers such as ``pairs._r0_description_records`` exist for
R0 hashing and the A.15 scan).
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from signal_diag.evaluation.full_scale_characterization import gate, reporting
from signal_diag.evaluation.full_scale_characterization import identity as identity_mod
from signal_diag.evaluation.full_scale_characterization.__main__ import main
from signal_diag.evaluation.full_scale_characterization.constants import ROUND_1
from signal_diag.evaluation.full_scale_characterization.executor import (
    direct_reference_counts,
    measure_row,
    row_specs_for_pair,
)
from signal_diag.evaluation.full_scale_characterization.freeze import (
    FreezeRejected,
    authorize_validation,
)
from signal_diag.evaluation.full_scale_characterization.gate import ValidationLocked
from signal_diag.evaluation.full_scale_characterization.groups import (
    enumerate_source_groups,
)
from signal_diag.evaluation.full_scale_characterization.identity import (
    compute_identity,
    identity_comparison_diff,
)
from signal_diag.evaluation.full_scale_characterization.manifest import build_manifest
from signal_diag.evaluation.full_scale_characterization.pairs import (
    enumerate_pair_batches,
    enumerate_pairs,
)
from tests.evaluation.full_scale_characterization.mini_manifest import MINI
from tests.evaluation.full_scale_characterization.test_t_cx378_freeze_store import (
    _frozen,
)
from tests.evaluation.full_scale_characterization.test_t_cx380_end_to_end import (
    E2E,
    _steps,
)


def test_t_cx378_frozen_report_json_is_built_in_the_comparison_set() -> None:
    for fn in (reporting.stage1_report_json, reporting.stage2_report_json):
        assert inspect.getsourcefile(fn).endswith("fitting.py")  # type: ignore[union-attr]
    ident = compute_identity(MINI)
    assert "fitting.py" in ident["comparison"]["package_files"]
    assert "reporting.py" not in ident["comparison"]["package_files"]
    markdown_changed = json.loads(json.dumps(ident))
    markdown_changed["record_only"]["reporting_sha256"] = "0" * 64
    assert identity_comparison_diff(ident, markdown_changed) == []
    fitting_changed = json.loads(json.dumps(ident))
    fitting_changed["comparison"]["package_sha256"] = "0" * 64
    assert identity_comparison_diff(ident, fitting_changed) == ["package_sha256"]


def test_t_cx378_validation_access_issuer_is_private() -> None:
    assert not hasattr(gate, "issue_validation_access")
    with pytest.raises(ValidationLocked):
        gate.ValidationAccess("x" * 64, "mini", _issuer=object())


def test_t_cx378_pair_enumeration_defaults_to_calibration_and_gates_validation() -> None:
    groups = enumerate_source_groups(MINI)
    pairs = enumerate_pairs(groups, MINI)
    assert pairs and {p.side for p in pairs} == {"calibration"}
    batches = list(enumerate_pair_batches(groups, MINI))
    assert {d["side"] for b in batches for d in b} == {"calibration"}
    with pytest.raises(ValidationLocked):
        enumerate_pairs(groups, MINI, side="validation")
    with pytest.raises(ValidationLocked):
        enumerate_pair_batches(groups, MINI, side="validation")


def test_t_cx378_manifest_pairs_hold_calibration_only() -> None:
    manifest = build_manifest(MINI)
    assert manifest.pairs and {p.side for p in manifest.pairs} == {"calibration"}
    assert manifest.planned_pair_counts.by_side["validation"] > 0


def _validation_spec():
    pair = next(p for p in build_manifest(MINI).pairs if p.family == "M2")
    spec = row_specs_for_pair(pair, file_duration_s=MINI.file_duration_s, full_scale_threshold=0.99, m9_layout=None)[0]
    assert spec.side == "calibration"
    return spec.model_copy(update={"side": "validation"})


def test_t_cx378_measure_row_gates_validation_specs() -> None:
    spec = _validation_spec()
    with pytest.raises(ValidationLocked):
        measure_row(spec)
    with pytest.raises(ValidationLocked):
        direct_reference_counts(spec)


def test_t_cx378_full_freeze_unlocks_measure_row(tmp_path: Path) -> None:
    store, _ = _frozen(tmp_path)
    access = authorize_validation(store, constants=MINI)
    row = measure_row(_validation_spec(), validation_access=access)
    assert row.terminal_state == "measured"


def test_t_cx378_manifest_expansion_is_explicit_not_by_round_name() -> None:
    assert ROUND_1.expand_pairs is False
    assert MINI.expand_pairs is True
    renamed = MINI.model_copy(update={"round_id": "round_1"})
    assert build_manifest(renamed).pairs


def test_t_cx378_round_id_must_match_manifest(tmp_path: Path) -> None:
    store, _ = _frozen(tmp_path, manifest_round_id="other_round")
    with pytest.raises((ValidationLocked, FreezeRejected), match="round"):
        authorize_validation(store, constants=MINI)


def test_t_cx378_package_digest_change_blocks_calibrate_and_validate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    constants_path = tmp_path / "constants.json"
    constants_path.write_text(json.dumps(E2E.model_dump(mode="json")), encoding="utf-8")
    steps = _steps(tmp_path / "a", constants_path)
    assert main(steps[0]) == 0
    real = identity_mod._package_sha256
    monkeypatch.setattr(identity_mod, "_package_sha256", lambda files: "0" * 64)
    assert main(steps[1]) != 0
    monkeypatch.setattr(identity_mod, "_package_sha256", real)
    for argv in steps[1:6]:
        assert main(argv) == 0, argv
    monkeypatch.setattr(identity_mod, "_package_sha256", lambda files: "0" * 64)
    assert main(steps[6]) != 0
    monkeypatch.setattr(identity_mod, "_package_sha256", real)
    assert main(steps[6]) == 0


def test_t_cx378_runs_take_frozen_report_json_from_the_comparison_set() -> None:
    """The CLI steps must build stage reports from fitting.py, not the record-only reporting.py."""
    import ast

    from signal_diag.evaluation.full_scale_characterization import runs

    tree = ast.parse(inspect.getsource(runs))
    sources: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                sources.setdefault(alias.name, set()).add(node.module.rsplit(".", 1)[-1])
    for name in ("stage1_report_json", "stage2_report_json"):
        assert sources.get(name) == {"fitting"}, (name, sources.get(name))
