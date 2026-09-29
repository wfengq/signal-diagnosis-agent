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
    "abe05496f3dee2d369173552cc8613856f821b782126fea46cc7c1f1f1eb1751",
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
        "5e6676ba8512bbd246482d299cadc082644a205ef5c306ea75735da3ff6029d5",
    ),
}

PRESERVED_FILE_SHA256 = {
    DEVELOPMENT_BUNDLE / "audit_report.json": (
        "c29f4041cebbb177ff7cc3f1340d5fb3d642ae89d647b522eb10816d8818f6ed"
    ),
    DEVELOPMENT_BUNDLE / "INDEPENDENT_AUDIT.json": (
        "5d1116cc30cb646f934b7192396a84d2de7954966c8a20248c12666d75038653"
    ),
    DEVELOPMENT_BUNDLE / "preflight.json": (
        "288c8b49b223b8b0b96ab5ad0d448c0bd0dd976f13227b26d0e3e1d4fcc660c6"
    ),
    DEVELOPMENT_BUNDLE / "run_summary.json": (
        "7558d2c54e92da0e8b047014a23d795b094c6b4efb466c14cb1589711117526a"
    ),
    DEVELOPMENT_BUNDLE / "STATUS.md": (
        "30f1c4e70a03dc727a15d2ba8ce3a58147f06bbffa962782369bc02eee01574b"
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
        "19e0ea87abb8c200660b0aa83c7e10f9a6ac635d87c4aa9ea31c08bf9e840288"
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
