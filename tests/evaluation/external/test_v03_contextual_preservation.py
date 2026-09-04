"""T-CX001–T-CX003 / T-CX146–T-CX148: preserve frozen identities for contextual work."""

from __future__ import annotations

import hashlib
import re
import subprocess
from collections import Counter
from hashlib import sha256
from pathlib import Path

from signal_diag.agent.prompts import _S1_PROMPT_V8_1
from signal_diag.agent.prompts_v03 import _S1_PROMPT_V9_4, _S1_PROMPT_V9_5

ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = ROOT
S1_PROFILE = ROOT / "src/signal_diag/rules/profiles/s1_distortion_v1.yaml"
DEMO_README = ROOT / "docs/demo/phase5/v0_2_acceptance/README.md"
OFFICIAL_MANIFEST = (
    ROOT
    / "docs/evaluations/phase4_3_1/official"
    / "bench_official_s1_v12_planner8_1_gate5"
    / "benchmark_manifest.json"
)

_TASK13_BASE = (
    "docs/evaluations/v0_3/contextual/development/study_v0_3_contextual_dev_1"
)
TASK13_CONTROL_SHA256: dict[str, str] = {
    f"{_TASK13_BASE}/agent_v9_5_dev_run/AUDIT_CORRECTION.md": (
        "5423259dcd0ec44a94cbc44de8d98f49932fcf925fa812c30122f12166ff5b47"
    ),
    f"{_TASK13_BASE}/agent_v9_5_dev_run/STATUS.md": (
        "516d50d67e68c8689ca55f46969c6dec206a0a7325e234186e5860190037dabd"
    ),
    f"{_TASK13_BASE}/agent_v9_5_dev_diagnostic_continuation_1/STATUS.md": (
        "d08e3e282a339e7c3a7f9b9a2a6661d8173cbd9c0acc29723668cdee5ac6fbfb"
    ),
    f"{_TASK13_BASE}/agent_v9_5_dev_diagnostic_continuation_1/preflight.json": (
        "3b5ecc5b37e3c51c9d14a56e5bc12d7d21a9751f627a9d0bb31f1f95fe53f5ca"
    ),
    f"{_TASK13_BASE}/agent_v9_5_dev_diagnostic_continuation_1/disposition.json": (
        "7458f46e6cba03d3d8928a4643f06a58f2cd33a0640a06dbe2a0ee58e98176c1"
    ),
    f"{_TASK13_BASE}/agent_v9_5_dev_diagnostic_continuation_1/run_summary.json": (
        "9a2992a53f6a11a2a2e85a79036bcbc35923e184aa53e4330bced170f3c70a2f"
    ),
}


def sha256_path(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def test_t_cx001_frozen_prompt_and_profile_bytes_are_preserved() -> None:
    assert sha256(_S1_PROMPT_V8_1.system_prompt.encode()).hexdigest() == (
        "f2f0a81cc8f36f0301ee67c43e692886e86f9aa9136adeea4d592707133423ca"
    )
    assert sha256(_S1_PROMPT_V9_4.system_prompt.encode()).hexdigest() == (
        "a29c9cda17bd4bf1d922880610609e32f0670b3eecb984a1e3afa16671e806af"
    )
    assert sha256_path(S1_PROFILE) == (
        "1e02d0dabe74ae1327fa3418d4ce546c53e8a8d06b175b5c508edb8b512f5ed1"
    )
    assert sha256_path(DEMO_README) == (
        "5771cc72f21123148a1eb16a719189564bd6370f3fffc4bad285aab79da17c55"
    )
    assert sha256_path(OFFICIAL_MANIFEST) == (
        "392a0ccc24ebce3c245a2c5b1a0d859f8a35aa2001ca4245e165a66f983df950"
    )


def test_t_cx002_official_bundle_manifest_path_exists() -> None:
    assert OFFICIAL_MANIFEST.is_file()
    assert DEMO_README.is_file()
    assert S1_PROFILE.is_file()


def test_t_cx003_v0_2_tag_is_unchanged() -> None:
    resolved = subprocess.check_output(
        [
            "git",
            "-c",
            f"safe.directory={ROOT.as_posix()}",
            "rev-parse",
            "v0.2.0^{commit}",
        ],
        cwd=ROOT,
        text=True,
    ).strip()
    assert resolved == "ff16e2a59a2c96b89bcb2b28906ede199eb104dc"


def test_t_cx146_v9_5_prompt_remains_frozen() -> None:
    digest = hashlib.sha256(_S1_PROMPT_V9_5.system_prompt.encode("utf-8")).hexdigest()
    assert digest == "a4f4d260adb45a2af088961c77586b08d8279cd1bc4f3780474c3b0a6bd7cb02"


def test_t_cx147_task13_control_artifacts_are_preserved() -> None:
    for relative, expected_sha256 in TASK13_CONTROL_SHA256.items():
        assert sha256_path(REPO_ROOT / relative) == expected_sha256


def test_t_cx148_v9_6_ids_are_registered_once() -> None:
    registry = (REPO_ROOT / "docs/TEST_PLAN_V0_3_CONTEXTUAL.md").read_text("utf-8")
    # Only ID cells in Markdown registry tables (not range rows or prose).
    table_ids = re.findall(r"^\| (T-CX\d+) \|", registry, flags=re.MULTILINE)
    counts = Counter(table_ids)
    for number in range(146, 166):
        assert counts[f"T-CX{number}"] == 1
