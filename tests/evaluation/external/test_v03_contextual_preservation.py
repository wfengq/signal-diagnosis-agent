"""T-CX001–T-CX003: preserve frozen V0.2 / v9.4 identities for contextual work."""

from __future__ import annotations

import subprocess
from hashlib import sha256
from pathlib import Path

from signal_diag.agent.prompts import _S1_PROMPT_V8_1
from signal_diag.agent.prompts_v03 import _S1_PROMPT_V9_4

ROOT = Path(__file__).resolve().parents[3]
S1_PROFILE = ROOT / "src/signal_diag/rules/profiles/s1_distortion_v1.yaml"
DEMO_README = ROOT / "docs/demo/phase5/v0_2_acceptance/README.md"
OFFICIAL_MANIFEST = (
    ROOT
    / "docs/evaluations/phase4_3_1/official"
    / "bench_official_s1_v12_planner8_1_gate5"
    / "benchmark_manifest.json"
)


def sha256_path(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def test_t_cx001_frozen_prompt_and_profile_bytes_are_preserved() -> None:
    assert sha256(_S1_PROMPT_V8_1.system_prompt.encode()).hexdigest() == (
        "f2f0a81cc8f36f0301ee67c43e860886e86f9aa9136adeea4d592707133423ca"
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
