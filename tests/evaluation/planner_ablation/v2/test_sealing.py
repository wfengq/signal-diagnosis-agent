"""T-CX300: v2 protocol sealing — full binding, readonly verify, refuse existing."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

from signal_diag.evaluation.planner_ablation.v2.models import (
    SLOT_COUNT_V2,
    STUDY_ID_V2,
    CandidateManifestV2,
    EffectiveConfiguration,
    StudyProtocolV2,
)
from signal_diag.evaluation.planner_ablation.v2.sealing import (
    build_candidate_manifest,
    generate_seal,
    list_bound_relative_paths,
    make_complete_budget_assessment,
    resolve_under_root,
    tree_file_digests,
    verify_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
WAV_REL = Path(
    "docs/evaluations/v0_3/contextual/development/study_v0_3_contextual_dev_1/wav"
)
DEV1_SEAL = (
    REPO_ROOT
    / "docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_1/protocol_seal"
)
DEV2_ROOT = (
    REPO_ROOT
    / "docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_2"
)

_PACKAGE_DIRS = (
    "signal",
    "dsp",
    "tools",
    "rules",
    "knowledge",
    "agent",
    "app",
    "evaluation/planner_ablation",
)


def _run_git(cwd: Path, *args: str) -> None:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}"
        )


def _copy_bound_tree(source_repo: Path, dest_repo: Path) -> None:
    package_src = source_repo / "src" / "signal_diag"
    package_dst = dest_repo / "src" / "signal_diag"
    for directory in _PACKAGE_DIRS:
        src = package_src / directory
        dst = package_dst / directory
        shutil.copytree(
            src,
            dst,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
            dirs_exist_ok=True,
        )
    scripts = dest_repo / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    for name in ("run_planner_ablation_v2.py", "seal_planner_ablation_v2.py"):
        shutil.copy2(source_repo / "scripts" / name, scripts / name)


def _copy_wav_inputs(source_repo: Path, dest_root: Path) -> None:
    src = source_repo / WAV_REL
    dst = dest_root / WAV_REL
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, dirs_exist_ok=True)


def _init_fixture_repo(tmp_path: Path) -> tuple[Path, Path]:
    """Temporary git repo + input tree with committed bound code and WAV bytes."""
    repo = tmp_path / "repo"
    inputs = tmp_path / "inputs"
    repo.mkdir()
    inputs.mkdir()
    _copy_bound_tree(REPO_ROOT, repo)
    _copy_wav_inputs(REPO_ROOT, inputs)
    # Also place WAV under the repo so repository_root==input_root works.
    _copy_wav_inputs(REPO_ROOT, repo)
    _run_git(repo, "init")
    _run_git(repo, "config", "user.email", "seal-test@example.com")
    _run_git(repo, "config", "user.name", "Seal Test")
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-m", "fixture seal baseline")
    return repo, inputs


def _complete_budget():
    return make_complete_budget_assessment(
        planner_calls_per_slot_bound=8,
        transport_attempts_per_call_bound=1,
        input_token_bound_per_call=4000,
        output_token_bound_per_call=1000,
    )


def _complete_config() -> EffectiveConfiguration:
    return EffectiveConfiguration(
        max_tool_calls=8,
        max_planner_retries=2,
        max_no_progress=2,
        max_rule_evaluations=4,
        max_knowledge_retrievals=4,
        temperature=0.0,
        thinking_disabled=True,
        max_tokens_explicit=True,
        max_tokens=4096,
        request_timeout_explicit=True,
        request_timeout_s=120.0,
        transport_retry_override_explicit=True,
        transport_retry_override=1,
        transport_attempts_per_call_bound=1,
        planner_calls_per_slot_bound=8,
        input_token_bound_per_call=4000,
        output_token_bound_per_call=1000,
        retry_telemetry_available=True,
        provider_sdk_version="fixture",
    )


def _build_ready_candidate(repo: Path, inputs: Path) -> CandidateManifestV2:
    return build_candidate_manifest(
        repository_root=repo,
        input_root=inputs,
        protocol=StudyProtocolV2(),
        effective_configuration=_complete_config(),
        budget_assessment=_complete_budget(),
        operator_authorization_references=("tmp_fixture_grant",),
    )


def _rewrite_manifest(seal_dir: Path, mutator) -> None:
    path = seal_dir / "manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutator(payload)
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    # Refresh seal index for files other than the intentional logical mutation path
    # when tests want index-valid but binding-invalid manifests.
    lines = []
    for name in sorted(p.name for p in seal_dir.iterdir() if p.is_file() and p.name != "seal.sha256"):
        digest = __import__("hashlib").sha256((seal_dir / name).read_bytes()).hexdigest()
        lines.append(f"{digest}  {name}\n")
    (seal_dir / "seal.sha256").write_text("".join(lines), encoding="utf-8")


@pytest.fixture()
def fixture_roots(tmp_path: Path) -> tuple[Path, Path]:
    return _init_fixture_repo(tmp_path)


@pytest.fixture()
def sealed_bundle(fixture_roots: tuple[Path, Path], tmp_path: Path) -> tuple[Path, Path, Path]:
    repo, inputs = fixture_roots
    destination = tmp_path / "protocol_seal"
    candidate = _build_ready_candidate(repo, inputs)
    assert candidate.seal_ready is True
    generate_seal(candidate, destination, legacy_fixture_seal=True)
    return destination, repo, inputs


def test_t_cx300_round_trip_verify_preserves_114_slots(
    sealed_bundle: tuple[Path, Path, Path],
) -> None:
    seal_dir, repo, inputs = sealed_bundle
    before_seal = tree_file_digests(seal_dir)
    before_inputs = tree_file_digests(inputs)
    study = verify_manifest(seal_dir, repository_root=repo, input_root=inputs)
    assert study.construction_path == "legacy_fixture_seal"
    assert study.protocol.study_id == STUDY_ID_V2
    assert len(study.schedule.slots) == SLOT_COUNT_V2
    assert tree_file_digests(seal_dir) == before_seal
    assert tree_file_digests(inputs) == before_inputs


def test_generate_refuses_existing_populated_and_empty(tmp_path: Path, fixture_roots) -> None:
    repo, inputs = fixture_roots
    candidate = _build_ready_candidate(repo, inputs)
    populated = tmp_path / "populated"
    generate_seal(candidate, populated, legacy_fixture_seal=True)
    with pytest.raises(FileExistsError, match="already exists"):
        generate_seal(candidate, populated, legacy_fixture_seal=True)

    empty = tmp_path / "empty_present"
    empty.mkdir()
    with pytest.raises(FileExistsError, match="already exists"):
        generate_seal(candidate, empty, legacy_fixture_seal=True)
    assert empty.is_dir()
    assert not any(empty.iterdir())


def test_verify_failure_and_success_preserve_input_tree(
    sealed_bundle: tuple[Path, Path, Path],
) -> None:
    seal_dir, repo, inputs = sealed_bundle
    before = tree_file_digests(inputs)
    verify_manifest(seal_dir, repository_root=repo, input_root=inputs)
    assert tree_file_digests(inputs) == before

    # Mutate sealed digest only; verify must fail without touching inputs.
    _rewrite_manifest(seal_dir, lambda payload: payload.__setitem__("question", "mutated?"))
    with pytest.raises(ValueError):
        verify_manifest(seal_dir, repository_root=repo, input_root=inputs)
    assert tree_file_digests(inputs) == before


def test_mutating_wav_bytes_fails_verification(
    sealed_bundle: tuple[Path, Path, Path],
) -> None:
    seal_dir, repo, inputs = sealed_bundle
    wav = next((inputs / WAV_REL).glob("cxdev_*_test.wav"))
    original = wav.read_bytes()
    wav.write_bytes(original + b"\x00")
    try:
        with pytest.raises(ValueError, match="WAV byte digest mismatch"):
            verify_manifest(seal_dir, repository_root=repo, input_root=inputs)
    finally:
        wav.write_bytes(original)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("question", "Totally different question.", "question|digest|request"),
        ("channel", "mixdown", None),  # placeholder replaced below
    ],
)
def test_question_policy_mutation_fails(
    sealed_bundle: tuple[Path, Path, Path],
    field: str,
    value: str,
    match: str | None,
) -> None:
    seal_dir, repo, inputs = sealed_bundle
    if field == "channel":
        # Channel is literal mixdown in schema; mutate sealed request channel text
        # via raw JSON to simulate tampering.
        def mutate(payload: dict) -> None:
            payload["sealed_requests"][0]["channel"] = "left_only"  # invalid / tampered
            payload["channel"] = "left_only"

        _rewrite_manifest(seal_dir, mutate)
        with pytest.raises((ValueError, Exception)):
            verify_manifest(seal_dir, repository_root=repo, input_root=inputs)
        return

    def mutate(payload: dict) -> None:
        payload[field] = value
        for row in payload["sealed_requests"]:
            row[field] = value

    _rewrite_manifest(seal_dir, mutate)
    with pytest.raises(ValueError, match=match):
        verify_manifest(seal_dir, repository_root=repo, input_root=inputs)


def test_alias_oracle_ucg_mutations_fail(sealed_bundle: tuple[Path, Path, Path]) -> None:
    seal_dir, repo, inputs = sealed_bundle

    def mutate_alias(payload: dict) -> None:
        payload["scenario_aliases"] = {"163185980dc8f7a4": "857fac53e4d2e57e"}

    _rewrite_manifest(seal_dir, mutate_alias)
    with pytest.raises(ValueError):
        verify_manifest(seal_dir, repository_root=repo, input_root=inputs)

    # Restore a fresh seal for oracle mutation.
    shutil.rmtree(seal_dir)
    generate_seal(_build_ready_candidate(repo, inputs), seal_dir, legacy_fixture_seal=True)

    def mutate_oracle(payload: dict) -> None:
        for scenario in payload["scenarios"]:
            if scenario["scenario_id"] == "825a759a0ea47bb7":
                scenario["single_oracle"] = {
                    "outcome": "supported_fault",
                    "exact_causal_faults": ["clipping"],
                }

    _rewrite_manifest(seal_dir, mutate_oracle)
    with pytest.raises(ValueError):
        verify_manifest(seal_dir, repository_root=repo, input_root=inputs)

    shutil.rmtree(seal_dir)
    generate_seal(_build_ready_candidate(repo, inputs), seal_dir, legacy_fixture_seal=True)

    def mutate_ucg(payload: dict) -> None:
        for scenario in payload["scenarios"]:
            if scenario["scenario_id"] == "825a759a0ea47bb7":
                scenario["in_upgrade_population"] = True
                scenario["upgrade_target"] = "fabricated"
                scenario["context_obtainable"] = True
                scenario["context_valid"] = True
                scenario["context_sufficient"] = True
                scenario["in_guidance_population"] = True

    _rewrite_manifest(seal_dir, mutate_ucg)
    with pytest.raises(ValueError):
        verify_manifest(seal_dir, repository_root=repo, input_root=inputs)


def test_prompt_profile_corpus_mutation_fails(
    sealed_bundle: tuple[Path, Path, Path],
) -> None:
    seal_dir, repo, inputs = sealed_bundle
    targets = [
        repo / "src/signal_diag/agent/prompts_v03.py",
        repo / "src/signal_diag/rules/profiles/s1_distortion_v1.yaml",
        repo / "src/signal_diag/knowledge/corpus/clipping.md",
    ]
    for path in targets:
        original = path.read_bytes()
        path.write_bytes(original + b"\n# mutated\n")
        try:
            with pytest.raises(ValueError):
                verify_manifest(seal_dir, repository_root=repo, input_root=inputs)
        finally:
            path.write_bytes(original)
            _run_git(repo, "add", "-A")
            # Keep commit identity; working tree restored to committed bytes.


def test_adapter_scorer_campaign_sealing_script_mutation_fails(
    sealed_bundle: tuple[Path, Path, Path],
) -> None:
    seal_dir, repo, inputs = sealed_bundle
    targets = [
        repo / "src/signal_diag/app/planner_ablation_v2_adapter.py",
        repo / "src/signal_diag/evaluation/planner_ablation/v2/scoring.py",
        repo / "src/signal_diag/evaluation/planner_ablation/v2/campaign.py",
        repo / "scripts/run_planner_ablation_v2.py",
        repo / "scripts/seal_planner_ablation_v2.py",
    ]
    for path in targets:
        original = path.read_bytes()
        path.write_bytes(original + b"\n# mutated binding\n")
        try:
            with pytest.raises(ValueError):
                verify_manifest(seal_dir, repository_root=repo, input_root=inputs)
        finally:
            path.write_bytes(original)


def test_dependency_identity_mutation_fails(
    sealed_bundle: tuple[Path, Path, Path],
) -> None:
    seal_dir, repo, inputs = sealed_bundle

    def mutate(payload: dict) -> None:
        payload["code_bindings"]["dependency_versions"]["numpy"] = "0.0.0-fake"

    _rewrite_manifest(seal_dir, mutate)
    with pytest.raises(ValueError, match="dependency identity|canonical manifest digest"):
        verify_manifest(seal_dir, repository_root=repo, input_root=inputs)


def test_foreign_identity_and_malformed_schema_rejected(
    sealed_bundle: tuple[Path, Path, Path],
) -> None:
    seal_dir, repo, inputs = sealed_bundle

    def foreign_v1(payload: dict) -> None:
        payload["study_id"] = "study_s1_planner_ablation_dev_1"
        payload["scoring_version"] = "1.0.0-dev.1"

    _rewrite_manifest(seal_dir, foreign_v1)
    with pytest.raises(ValueError, match="foreign|malformed|schema"):
        verify_manifest(seal_dir, repository_root=repo, input_root=inputs)

    shutil.rmtree(seal_dir)
    generate_seal(_build_ready_candidate(repo, inputs), seal_dir, legacy_fixture_seal=True)

    def malformed(payload: dict) -> None:
        payload["unexpected_full_schema_field"] = {"nested": True}

    _rewrite_manifest(seal_dir, malformed)
    with pytest.raises(ValueError, match="malformed|foreign|schema"):
        verify_manifest(seal_dir, repository_root=repo, input_root=inputs)


def test_canonical_manifest_digest_checked(
    sealed_bundle: tuple[Path, Path, Path],
) -> None:
    seal_dir, repo, inputs = sealed_bundle

    def mutate_digest_only(payload: dict) -> None:
        payload["candidate_digest"] = "a" * 64

    _rewrite_manifest(seal_dir, mutate_digest_only)
    with pytest.raises(ValueError, match="canonical manifest digest"):
        verify_manifest(seal_dir, repository_root=repo, input_root=inputs)


def test_path_traversal_and_symlink_escape_rejected(
    fixture_roots: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    _repo, inputs = fixture_roots
    outside = tmp_path / "outside.txt"
    outside.write_text("secret\n", encoding="utf-8")
    with pytest.raises(ValueError, match="traversal|escapes"):
        resolve_under_root(inputs, "../outside.txt", label="wav")

    link_dir = inputs / "docs" / "evaluations"
    link_dir.mkdir(parents=True, exist_ok=True)
    sneaky = inputs / "docs" / "sneaky.wav"
    sneaky.symlink_to(outside)
    with pytest.raises(ValueError, match="symlink escapes|escapes"):
        # Escape by resolving a symlink whose target is outside input_root.
        resolve_under_root(inputs, "docs/sneaky.wav", label="wav")


def test_race_creating_destination_does_not_overwrite(
    fixture_roots: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    repo, inputs = fixture_roots
    candidate = _build_ready_candidate(repo, inputs)
    destination = tmp_path / "race_seal"
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            generate_seal(candidate, destination, legacy_fixture_seal=True)
        except BaseException as exc:  # noqa: BLE001 - collect race outcomes
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert destination.is_dir()
    assert (destination / "manifest.json").is_file()
    # Exactly one creator succeeds; the other must see FileExistsError.
    assert sum(isinstance(exc, FileExistsError) for exc in errors) == 1
    assert len(errors) == 1


def test_incomplete_limits_block_seal_ready(fixture_roots: tuple[Path, Path]) -> None:
    repo, inputs = fixture_roots
    candidate = build_candidate_manifest(
        repository_root=repo,
        input_root=inputs,
        protocol=StudyProtocolV2(),
        effective_configuration=EffectiveConfiguration(),
        budget_assessment=None,
    )
    assert candidate.seal_ready is False
    with pytest.raises(ValueError, match="seal-ready"):
        generate_seal(candidate, repo / "blocked_seal", legacy_fixture_seal=True)


def test_refuse_generate_against_dev1(fixture_roots: tuple[Path, Path]) -> None:
    repo, inputs = fixture_roots
    candidate = _build_ready_candidate(repo, inputs)
    with pytest.raises(ValueError, match="dev_1"):
        generate_seal(candidate, DEV1_SEAL, legacy_fixture_seal=True)


def test_real_evidence_root_requires_grant(
    fixture_roots: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    repo, inputs = fixture_roots
    candidate = _build_ready_candidate(repo, inputs)
    # Simulate the real evidence path layout under tmp without writing into docs/.
    fake = (
        tmp_path
        / "docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_2/protocol_seal"
    )
    env_before = os.environ.pop("PLANNER_ABLATION_V2_SEAL_GRANT", None)
    try:
        with pytest.raises(PermissionError, match="seal grant"):
            generate_seal(candidate, fake, legacy_fixture_seal=True)
    finally:
        if env_before is not None:
            os.environ["PLANNER_ABLATION_V2_SEAL_GRANT"] = env_before


def test_bound_paths_cover_runtime_code_not_docs(fixture_roots: tuple[Path, Path]) -> None:
    repo, _inputs = fixture_roots
    paths = list_bound_relative_paths(repo)
    joined = "\n".join(paths)
    assert "scripts/run_planner_ablation_v2.py" in paths
    assert "scripts/seal_planner_ablation_v2.py" in paths
    assert "src/signal_diag/evaluation/planner_ablation/v2/scoring.py" in joined
    assert "src/signal_diag/app/planner_ablation_v2_adapter.py" in joined
    assert "src/signal_diag/agent/prompts_v03.py" in joined
    assert "docs/evaluations" not in joined
    assert "design_inputs.md" not in joined


def test_no_real_seal_under_dev2_evidence_root() -> None:
    assert DEV2_ROOT.is_dir()
    assert not (DEV2_ROOT / "protocol_seal").exists()
    names = {path.name for path in DEV2_ROOT.iterdir()}
    assert names <= {
        "design_inputs.md",
        "OFFLINE_ACCEPTANCE.md",
        "LABEL_REVIEW.md",
        "BUDGET_BOUNDS.md",
        "RESOURCE_BOUNDS.md",
        "PRESEAL_BUDGET_STATUS.md",
    }
