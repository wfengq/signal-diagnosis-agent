"""T-CX001–T-CX003 / T-CX146–T-CX148 / T-CX166: preserve frozen identities."""

from __future__ import annotations

import hashlib
import re
import subprocess
from collections import Counter
from hashlib import sha256
from pathlib import Path

from signal_diag.agent.prompts import _S1_PROMPT_V8_1
from signal_diag.agent.prompts_v03 import (
    _S1_PROMPT_V9_4,
    _S1_PROMPT_V9_5,
    _S1_PROMPT_V9_6,
    _S1_PROMPT_V9_7,
    _S1_PROMPT_V9_8,
)

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
        "1e7bce0d5895c64637a3f1928e660b304ee19d9d68928a8fbbbecf4985a935e1"
    ),
    f"{_TASK13_BASE}/agent_v9_5_dev_diagnostic_continuation_1/preflight.json": (
        "8e2ba81dc218a836a643be7383a0d30fed19e6d660b3a65ace63725313320305"
    ),
    f"{_TASK13_BASE}/agent_v9_5_dev_diagnostic_continuation_1/disposition.json": (
        "dccf026a926833baa16f14a115b32a0a737b68d8ca454f1238589deafe838f81"
    ),
    f"{_TASK13_BASE}/agent_v9_5_dev_diagnostic_continuation_1/run_summary.json": (
        "661489206b92ee8cdd4a80695b31ddd86a8871216f74052e331163ace6df6ee6"
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
        "33108d74673ee9674658abe0f3e92433511312f9bb74432362ee2792c4596213"
    )
    assert sha256_path(DEMO_README) == (
        "9e0665214163fd0599cfa723bcc47c46fb03e3c2d82ce417a38a7facd8d42412"
    )
    assert sha256_path(OFFICIAL_MANIFEST) == (
        "355fc75eab5d4580606fb3eb31a71566cc4b2a8303d412aa309df5b3c9ae71a7"
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


V96_CONTROL_SHA256 = {
    f"{_TASK13_BASE}/agent_v9_6_dev_confirmation_1/run_summary.json": (
        "7e4f721b597a5d053f17b0076ec2a2c8b9cd8bf82617c7422e9b68757995c87c"
    ),
    f"{_TASK13_BASE}/agent_v9_6_dev_confirmation_1/audit_report.json": (
        "47823a9159545663c791a5eda5cb2f34ac050c1b69fa0ca6257c9af171e10bb9"
    ),
    f"{_TASK13_BASE}/agent_v9_6_dev_confirmation_1/STATUS.md": (
        "0476d9b961a53cc103f669c27309e1d0f26acc3f50613e0906f3bcc06f429da0"
    ),
    f"{_TASK13_BASE}/agent_v9_6_dev_confirmation_1/AUDIT_CORRECTION.md": (
        "76518206967c8381694bf947bea3cc3c9b06e0efa5a56f961be53feff06c1c95"
    ),
    f"{_TASK13_BASE}/agent_v9_6_dev_confirmation_1/corrected_scoring.json": (
        "8def27314976ef806627649e5d294fbdf9c89383294be82f79f0d4a98e29a902"
    ),
}


def test_t_cx166_v9_6_prompt_run_and_v9_7_registry_are_preserved() -> None:
    digest = hashlib.sha256(_S1_PROMPT_V9_6.system_prompt.encode("utf-8")).hexdigest()
    assert digest == (
        "b9ed17debf9bfd2f086ee0eaa178d83370630a0530ebd02336769e416be1b5eb"
    )
    for relative, expected in V96_CONTROL_SHA256.items():
        assert sha256_path(REPO_ROOT / relative) == expected
    registry = (REPO_ROOT / "docs/TEST_PLAN_V0_3_CONTEXTUAL.md").read_text("utf-8")
    table_ids = re.findall(r"^\| (T-CX\d+) \|", registry, flags=re.MULTILINE)
    counts = Counter(table_ids)
    for number in range(166, 186):
        assert counts[f"T-CX{number}"] == 1


def test_t_cx186_v9_7_prompt_and_v9_8_registry_are_preserved() -> None:
    digest = hashlib.sha256(_S1_PROMPT_V9_7.system_prompt.encode("utf-8")).hexdigest()
    assert digest == (
        "fc50d82fc7b5701388f5d35c7f50a157ed1c88f050e6057cd8f11caf280b982a"
    )
    registry = (REPO_ROOT / "docs/TEST_PLAN_V0_3_CONTEXTUAL.md").read_text("utf-8")
    table_ids = re.findall(r"^\| (T-CX\d+) \|", registry, flags=re.MULTILINE)
    counts = Counter(table_ids)
    for number in range(186, 191):
        assert counts[f"T-CX{number}"] == 1


def test_t_cx191_v9_8_prompt_campaign_and_v9_9_registry_are_preserved() -> None:
    digest = hashlib.sha256(_S1_PROMPT_V9_8.system_prompt.encode("utf-8")).hexdigest()
    assert digest == (
        "6d7e18dae4bc1b7e19e3430a9266e7d2c10496df194d3571390df025c6f7bf41"
    )
    campaign = (
        REPO_ROOT
        / "docs/evaluations/v0_3/contextual/development"
        / "study_v0_3_contextual_dev_1/agent_v9_8_dev_confirmation_1"
    )
    expected = {
        "run_summary.json": (
            "f726f4da7b498d8c879407294e67bd337921bf0001757142533a69cab0f19c8f"
        ),
        "audit_report.json": (
            "e12bdbb7fb135dbf47836928b07d77dac83f9ff8970d777997e160d36beeeba0"
        ),
        "STATUS.md": (
            "6d46bf0c5f8ce91101ba6da1ca6c299739a09a7820b4a1fa237ebcfeb5a83f4f"
        ),
    }
    for filename, expected_digest in expected.items():
        assert sha256_path(campaign / filename) == expected_digest
    registry = (REPO_ROOT / "docs/TEST_PLAN_V0_3_CONTEXTUAL.md").read_text("utf-8")
    table_ids = re.findall(r"^\| (T-CX\d+) \|", registry, flags=re.MULTILINE)
    counts = Counter(table_ids)
    for number in range(191, 197):
        assert counts[f"T-CX{number}"] == 1
