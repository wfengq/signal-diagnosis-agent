"""T-CX231: preserve v9.9 identities/evidence and register v9.10 contracts."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import get_args

from signal_diag.agent.diagnosis import _CONTEXTUAL_CAUSAL_POLICIES, CausalPolicyVersion
from signal_diag.agent.prompts_v03 import _S1_PROMPT_V9_9
from signal_diag.agent.rule_closure import required_rule_profile
from signal_diag.signal.context import StimulusContext

ROOT = Path(__file__).resolve().parents[3]
CONTEXTUAL_PROFILE = (
    ROOT / "src/signal_diag/rules/profiles/s1_contextual_comparison_v1.yaml"
)
DEVELOPMENT_BUNDLE = (
    ROOT
    / "docs/evaluations/v0_3/contextual/development"
    / "study_v0_3_contextual_dev_1/agent_v9_9_dev_confirmation_1"
)
VALIDATION_ROOT = (
    ROOT
    / "docs/evaluations/v0_3/contextual/validation"
    / "study_v0_3_contextual_validation_1"
)
VALIDATION_RUN = VALIDATION_ROOT / "agent_v9_9_validation_run_1"
VALIDATION_DIAGNOSTIC_CONTINUATION = (
    VALIDATION_ROOT / "agent_v9_9_validation_diagnostic_continuation_1"
)
VALIDATION_SEAL_V3 = VALIDATION_ROOT / "validation_seal_v3"
DEVELOPMENT_BUNDLE_TREE_IDENTITY = (
    92,
    "a0ce31cc068a5e113d90454beae62a7549ea24581e824693c9c4a9d5c4d7cb75",
)
VALIDATION_TREE_IDENTITIES = {
    VALIDATION_RUN: (
        191,
        "2945c83b2d9b0aeca06832fbda4fabe2bb0c45216ac115b911157e328a93ba23",
    ),
    VALIDATION_DIAGNOSTIC_CONTINUATION: (
        57,
        "b3ccf3996c776e278adf5515a4c7d586f248a499246f4f3c256fb04fd1b9007a",
    ),
    VALIDATION_SEAL_V3: (
        8,
        "cd843691e040c9a6e27b95ef290cf0bfbb12eb9ecea6823bb95ae04682fbe50e",
    ),
}

PRESERVED_FILE_SHA256 = {
    DEVELOPMENT_BUNDLE / "audit_report.json": (
        "1708bed047b9168d89997cac549f5eb3a5cc43c036cf013e81d808def90370fa"
    ),
    DEVELOPMENT_BUNDLE / "INDEPENDENT_AUDIT.json": (
        "b2ef7ffb44e8b2004633ee992bc7de644a67cf5fa098f6fd77fac2827b789781"
    ),
    DEVELOPMENT_BUNDLE / "preflight.json": (
        "fdd3cf776f9bb7a5a452a60154fbe65f6ccc605cdcf17582317e8b059c95450c"
    ),
    DEVELOPMENT_BUNDLE / "run_summary.json": (
        "92994fd675aab681feb81e8d654b1b9e4b5026f20d951d7a117216854da00cca"
    ),
    DEVELOPMENT_BUNDLE / "STATUS.md": (
        "860c51a506ce66652f0b605d787ed7e5604842d54a0a809ea7ca097b9f9c1707"
    ),
    DEVELOPMENT_BUNDLE / "TOOL_USE_ADJUDICATION.json": (
        "216839a09e819ec6d122eaf69307767280be27df692392ffaa2046caebaf5d6a"
    ),
    VALIDATION_ROOT / "agent_v9_9_validation_run_1/execution_ledger.json": (
        "d2190c9725320d8534f85e9723e0fbb58dba24fc901b852ee02df281bdbc525a"
    ),
    VALIDATION_ROOT
    / "agent_v9_9_validation_diagnostic_continuation_1/execution_ledger.json": (
        "df6b025f098b1af12242517fab686f675a4afb06c49c9db712bef7a64fd9c3b6"
    ),
    VALIDATION_ROOT
    / "agent_v9_9_validation_diagnostic_continuation_1/DIAGNOSTIC_RECONSTRUCTION.json": (
        "4289a3ecede096b5567e564d2d76ba557fc9bca12353451c60ead2b931e72707"
    ),
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_tree_identity(root: Path) -> tuple[int, str]:
    files = sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    digest = hashlib.sha256()
    for path in files:
        relative_path = path.relative_to(root).as_posix()
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
        digest.update(b"\0")
    return len(files), digest.hexdigest()


def test_t_cx231_preserves_v9_9_identities_and_recorded_evidence() -> None:
    assert _S1_PROMPT_V9_9.version == "v0.3-s1-planner-9.9"
    assert _sha256_bytes(_S1_PROMPT_V9_9.system_prompt.encode("utf-8")) == (
        "27a9315ad85a035c9cc9cbfe5f15ea26c49383d7fb23207989315ae0adb78dc9"
    )
    assert _sha256_bytes(CONTEXTUAL_PROFILE.read_bytes()) == (
        "c79865caf913b2a1a5f6f50fccd8c37d6f2828e72feb1f80d9c9c7b4b7d9eb58"
    )
    for path, expected_sha256 in PRESERVED_FILE_SHA256.items():
        assert _sha256_bytes(path.read_bytes()) == expected_sha256
    assert _canonical_tree_identity(DEVELOPMENT_BUNDLE) == (
        DEVELOPMENT_BUNDLE_TREE_IDENTITY
    )
    for root, expected_identity in VALIDATION_TREE_IDENTITIES.items():
        assert _canonical_tree_identity(root) == expected_identity


def test_t_cx231_preserves_v9_9_policy_and_contextual_profile_routing() -> None:
    policy = "v9_9_paired_reference_recovery"
    assert policy in get_args(CausalPolicyVersion)
    assert policy in _CONTEXTUAL_CAUSAL_POLICIES

    contexts = (
        StimulusContext(
            mode="paired_reference",
            test_signal_id="sig_test",
            reference_signal_id="sig_reference",
            assertion_source="user_supplied",
        ),
        StimulusContext(
            mode="nominal_single_tone",
            test_signal_id="sig_test",
            nominal_fundamental_hz=440.0,
            stimulus_kind="single_tone",
            assertion_source="user_supplied",
        ),
    )
    for context in contexts:
        assert required_rule_profile(
            causal_policy_version=policy,
            stimulus_context=context,
            tool_name="analyze_contextual_distortion",
        ) == "profile_s1_contextual_comparison"


def test_t_cx231_registers_v9_10_contract_and_test_ids_once() -> None:
    contract = (ROOT / "docs/CONTRACTS_V0_3_CONTEXTUAL.md").read_text("utf-8")
    required_contract_text = (
        "v9_10_contextual_clipping_recovery",
        "profile_s1_contextual_comparison_v9_10",
        "test_clipping_mechanism",
        "coherent clipping family",
        "supported-subset recovery",
        "v9_10_harness_complete",
    )
    for text in required_contract_text:
        assert text in contract

    test_plan = (ROOT / "docs/TEST_PLAN_V0_3_CONTEXTUAL.md").read_text("utf-8")
    rows = re.findall(r"^\| (T-CX\d+) \|", test_plan, flags=re.MULTILINE)
    for number in range(231, 241):
        assert rows.count(f"T-CX{number}") == 1
