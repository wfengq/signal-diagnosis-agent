"""T-CX397: case proportions and the frozen held-out manifest hash."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from signal_diag.evaluation.agent_increment.cases import (
    HELD_OUT_SEED,
    TEMPLATE_ID,
    build_cases,
    manifest_sha256,
    proportion_report,
)
from signal_diag.evaluation.agent_increment.models import IncrementCase

_MANIFEST_SHA256 = "02590e499a14af67850cb244365042fad1d5b730c03f06901a7a5d44716ff11f"
_STUDY = (
    Path(__file__).resolve().parents[3]
    / "docs/evaluations/v0_3/agent_increment/study_s1_agent_increment_1"
)


def _load(path: Path) -> list[IncrementCase]:
    payload = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    return [IncrementCase.model_validate(item) for item in payload["cases"]]


def test_t_cx397_proportions_and_frozen_held_out_hash() -> None:
    assert HELD_OUT_SEED == 20261006
    assert TEMPLATE_ID == "heldout-templates-1.0"
    committed = _load(_STUDY)
    assert len(committed) == 72
    report = proportion_report(committed)
    for key, count in (
        ("dev:T1", 12),
        ("dev:T2", 12),
        ("heldout:T1", 24),
        ("heldout:T2", 24),
    ):
        bucket = report[key]
        assert bucket["count"] == count
        assert bucket["no_fault"] * 3 >= bucket["count"]
        assert bucket["insufficient"] >= 1
        assert bucket["favors_baseline"] >= 1
    recorded = (_STUDY / "manifest.sha256").read_text(encoding="utf-8").strip()
    assert recorded == _MANIFEST_SHA256
    sums = (_STUDY / "SHA256SUMS").read_text(encoding="utf-8")
    assert sums.startswith(f"{_MANIFEST_SHA256}  manifest.json\n")
    regenerated = manifest_sha256(build_cases(_STUDY / "wav"))
    assert regenerated == _MANIFEST_SHA256
    for path in sorted((_STUDY / "wav").glob("*.wav")):
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        assert f"{file_hash}  wav/{path.name}\n" in sums
