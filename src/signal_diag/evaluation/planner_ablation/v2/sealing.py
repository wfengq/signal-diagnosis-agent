"""V2 planner-ablation protocol sealing and verified-input construction.

Study-only. Temporary fixtures may generate seals under pytest tmp paths.
Generation refuses any existing destination (including empty directories).
Verification is read-only and recomputes referenced input/code bindings.
Never regenerates ``study_s1_planner_ablation_dev_1``.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
from hashlib import sha256
from importlib import metadata
from pathlib import Path
from typing import Any

from signal_diag.evaluation.planner_ablation.v2.campaign import inspect_limits
from signal_diag.evaluation.planner_ablation.v2.labels import validate_labels
from signal_diag.evaluation.planner_ablation.v2.models import (
    DEFAULT_STUDY_QUESTION,
    SCORING_IDENTITY_V2,
    SCORING_VERSION_V2,
    SLOT_COUNT_V2,
    STUDY_ID_V2,
    BudgetAssessment,
    CandidateManifestV2,
    CodeBindingsV2,
    EffectiveConfiguration,
    EnvironmentBindingV2,
    LabelReviewResult,
    Schedule,
    SealedCanonicalRequest,
    StudyProtocolV2,
    VerifiedStudyV2,
)
from signal_diag.evaluation.planner_ablation.v2.population import (
    build_schedule,
    canonical_json,
    compute_request_key,
    load_proposed_scenarios,
    normalize_question,
)
from signal_diag.evaluation.planner_ablation.v2.resource_models import (
    ResourceCandidateValidation,
)

_CHECKSUM_LINE = "{digest}  {name}\n"
_DEV1_STUDY_ID = "study_s1_planner_ablation_dev_1"
_PACKAGE_REL = Path("src/signal_diag")
_PRODUCT_PACKAGE_DIRS = (
    "signal",
    "dsp",
    "tools",
    "rules",
    "knowledge",
    "agent",
    "app",
)
_STUDY_PACKAGE_DIRS = (
    "evaluation/planner_ablation",
)
_ENTRY_SCRIPTS = (
    "scripts/run_planner_ablation_v2.py",
    "scripts/seal_planner_ablation_v2.py",
)
_PROMPT_MODULE = "src/signal_diag/agent/prompts_v03.py"
_PROMPT_VERSION = "v0.3-s1-planner-9.11"
_PROFILE_RELS = (
    "src/signal_diag/rules/profiles/s1_distortion_v1.yaml",
    "src/signal_diag/rules/profiles/s1_contextual_comparison_v1.yaml",
    "src/signal_diag/rules/profiles/s1_contextual_comparison_v9_10.yaml",
)
_CORPUS_DIR = "src/signal_diag/knowledge/corpus"
_DEPENDENCY_NAMES = (
    "numpy",
    "pydantic",
    "PyYAML",
    "fastapi",
    "httpx",
    "openai",
)
_EXCLUDED_SUFFIXES = frozenset({".pyc", ".pyo"})
_EXCLUDED_NAME_PARTS = ("__pycache__", ".git")
_REAL_EVIDENCE_MARKERS = (
    "study_s1_planner_ablation_dev_2",
    "protocol_seal",
)


def _sha256_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical_payload(payload: object) -> bytes:
    return canonical_json(payload).encode("utf-8")


def _digest_payload(payload: object) -> str:
    return _sha256_bytes(_canonical_payload(payload))


def resolve_under_root(root: Path, relative: str, *, label: str) -> Path:
    """Resolve ``relative`` under ``root``; reject traversal and symlink escape."""
    if not relative or relative.startswith(("/", "\\")):
        raise ValueError(f"{label} path must be relative: {relative!r}")
    parts = Path(relative).parts
    if ".." in parts:
        raise ValueError(f"{label} path traversal is forbidden: {relative!r}")
    root_resolved = root.resolve()
    candidate = (root_resolved / relative).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(
            f"{label} path escapes declared root {root_resolved}: {relative!r}"
        ) from exc
    # Reject any symlink component that would escape after resolution.
    probe = root_resolved
    for part in Path(relative).parts:
        probe = probe / part
        if probe.is_symlink():
            target = probe.resolve()
            try:
                target.relative_to(root_resolved)
            except ValueError as exc:
                raise ValueError(
                    f"{label} symlink escapes declared root: {relative!r}"
                ) from exc
    return candidate


def _iter_package_files(package_root: Path, relative_dir: str) -> list[str]:
    base = package_root / relative_dir
    if not base.is_dir():
        raise FileNotFoundError(f"required package directory missing: {relative_dir}")
    paths: list[str] = []
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix in _EXCLUDED_SUFFIXES:
            continue
        if any(part in _EXCLUDED_NAME_PARTS for part in path.parts):
            continue
        if path.suffix not in {".py", ".yaml", ".yml", ".md", ".json", ".toml"}:
            continue
        rel = path.relative_to(package_root.parent.parent)
        paths.append(str(rel).replace("\\", "/"))
    return paths


def list_bound_relative_paths(repository_root: Path) -> tuple[str, ...]:
    """Explicit coverage of runtime-loaded product/study code (not an informal shortlist)."""
    root = repository_root.resolve()
    package_root = root / _PACKAGE_REL
    if not package_root.is_dir():
        raise FileNotFoundError(f"package root missing: {package_root}")
    paths: list[str] = []
    for directory in _PRODUCT_PACKAGE_DIRS:
        paths.extend(_iter_package_files(package_root, directory))
    for directory in _STUDY_PACKAGE_DIRS:
        paths.extend(_iter_package_files(package_root, directory))
    for script in _ENTRY_SCRIPTS:
        script_path = resolve_under_root(root, script, label="entry_script")
        if not script_path.is_file():
            raise FileNotFoundError(f"entry script missing: {script}")
        paths.append(script)
    # Profiles and corpus are also covered via package walk; keep explicit anchors.
    for profile in _PROFILE_RELS:
        resolve_under_root(root, profile, label="profile")
        if profile not in paths:
            paths.append(profile)
    corpus_root = resolve_under_root(root, _CORPUS_DIR, label="corpus")
    if corpus_root.is_dir():
        for path in sorted(corpus_root.rglob("*")):
            if path.is_file() and path.suffix == ".md":
                rel = str(path.relative_to(root)).replace("\\", "/")
                if rel not in paths:
                    paths.append(rel)
    # Stable unique order.
    return tuple(sorted(dict.fromkeys(paths)))


def _git_stdout(repository_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout.strip()


def _implementation_commit(repository_root: Path) -> str:
    return _git_stdout(repository_root, "rev-parse", "HEAD")


def _path_dirty(repository_root: Path, relative: str) -> bool:
    status = _git_stdout(
        repository_root,
        "status",
        "--porcelain",
        "--",
        relative,
    )
    return bool(status.strip())


def _commit_blob_digest(repository_root: Path, commit: str, relative: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{commit}:{relative}"],
        cwd=repository_root,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git show {commit}:{relative} failed: "
            f"{result.stderr.decode('utf-8', errors='replace').strip()}"
        )
    return _sha256_bytes(result.stdout)


def _dependency_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for name in _DEPENDENCY_NAMES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = "missing"
    return versions


def collect_code_bindings(repository_root: Path) -> CodeBindingsV2:
    """Hash bound runtime code against the working tree and pin HEAD commit."""
    root = repository_root.resolve()
    commit = _implementation_commit(root)
    bound_paths = list_bound_relative_paths(root)
    digests: dict[str, str] = {}
    dirty: list[str] = []
    for relative in bound_paths:
        path = resolve_under_root(root, relative, label="code")
        if not path.is_file():
            raise FileNotFoundError(f"bound code file missing: {relative}")
        working = _sha256_file(path)
        committed = _commit_blob_digest(root, commit, relative)
        if working != committed or _path_dirty(root, relative):
            dirty.append(relative)
        digests[relative] = working
    if dirty:
        raise ValueError(
            "dirty relevant code blocks sealing; clean or revise bindings: "
            + ", ".join(dirty[:8])
            + ("..." if len(dirty) > 8 else "")
        )
    entry_digests = {script: digests[script] for script in _ENTRY_SCRIPTS}
    prompt_path = resolve_under_root(root, _PROMPT_MODULE, label="prompt")
    prompt_digest = _sha256_file(prompt_path)
    profile_digests = {
        rel: digests[rel] if rel in digests else _sha256_file(resolve_under_root(root, rel, label="profile"))
        for rel in _PROFILE_RELS
    }
    corpus_digests = {
        rel: digests[rel]
        for rel in digests
        if rel.startswith(_CORPUS_DIR + "/")
    }
    aggregate = _digest_payload(
        {
            "bound_file_digests": digests,
            "entry_script_digests": entry_digests,
            "implementation_commit": commit,
        }
    )
    return CodeBindingsV2(
        implementation_commit=commit,
        aggregate_code_identity=aggregate,
        bound_file_digests=digests,
        entry_script_digests=entry_digests,
        prompt_module_digest=prompt_digest,
        prompt_version=_PROMPT_VERSION,
        profile_digests=profile_digests,
        corpus_digests=corpus_digests,
        dependency_versions=_dependency_versions(),
        python_version=platform.python_version(),
    )


def _label_review_digest_payload(review: LabelReviewResult) -> dict[str, object]:
    payload = review.model_dump(mode="json")
    for key in (
        "upgrade_population",
        "conditional_population",
        "guidance_population",
    ):
        values = payload.get(key, [])
        payload[key] = sorted(values)
    return payload


def _code_bindings_digest_payload(bindings: CodeBindingsV2) -> dict[str, object]:
    payload = bindings.model_dump(mode="json")
    payload["bound_file_digests"] = dict(sorted(payload["bound_file_digests"].items()))
    payload["entry_script_digests"] = dict(
        sorted(payload["entry_script_digests"].items())
    )
    payload["profile_digests"] = dict(sorted(payload["profile_digests"].items()))
    payload["corpus_digests"] = dict(sorted(payload["corpus_digests"].items()))
    payload["dependency_versions"] = dict(
        sorted(payload["dependency_versions"].items())
    )
    return payload


def _candidate_digest_payload(
    *,
    protocol: StudyProtocolV2,
    scenarios: tuple[Any, ...],
    schedule_digest: str,
    scenario_aliases: dict[str, str],
    slots: tuple[Any, ...],
    sealed_requests: tuple[SealedCanonicalRequest, ...],
    label_review: LabelReviewResult,
    input_identity: str,
    bindings: CodeBindingsV2,
    environment: EnvironmentBindingV2,
    operator_authorization_references: tuple[str, ...],
    effective_configuration: EffectiveConfiguration | None,
    budget: BudgetAssessment | None,
    question: str,
) -> dict[str, object]:
    return {
        "budget_assessment": None if budget is None else budget.model_dump(mode="json"),
        "channel": "mixdown",
        "code_bindings": _code_bindings_digest_payload(bindings),
        "code_identity": bindings.aggregate_code_identity,
        "effective_configuration": (
            None
            if effective_configuration is None
            else effective_configuration.model_dump(mode="json")
        ),
        "environment": environment.model_dump(mode="json"),
        "input_identity": input_identity,
        "label_review": _label_review_digest_payload(label_review),
        "operator_authorization_references": list(operator_authorization_references),
        "protocol": protocol.model_dump(mode="json"),
        "question": question,
        "scenario_aliases": dict(sorted(scenario_aliases.items())),
        "scenarios": [s.model_dump(mode="json") for s in scenarios],
        "schedule_digest": schedule_digest,
        "scoring_identity": SCORING_IDENTITY_V2,
        "scoring_version": SCORING_VERSION_V2,
        "sealed_requests": [r.model_dump(mode="json") for r in sealed_requests],
        "segment_policy": "full_signal",
        "slots": [s.model_dump(mode="json") for s in slots],
        "study_id": STUDY_ID_V2,
    }


def _input_identity_from_scenarios(scenarios: tuple[Any, ...]) -> str:
    rows = [
        {
            "reference_wav_relpath": scenario.reference_wav_relpath,
            "reference_wav_sha256": scenario.reference_wav_sha256,
            "scenario_id": scenario.scenario_id,
            "test_wav_relpath": scenario.test_wav_relpath,
            "test_wav_sha256": scenario.test_wav_sha256,
        }
        for scenario in scenarios
    ]
    return _digest_payload(rows)


def _seal_requests_from_schedule(schedule: Schedule) -> tuple[SealedCanonicalRequest, ...]:
    sealed: list[SealedCanonicalRequest] = []
    for req in schedule.canonical_requests:
        byte_req = req.byte_request
        sealed.append(
            SealedCanonicalRequest(
                request_key=req.request_key,
                mode=req.mode,
                representative_scenario_id=req.representative_scenario_id,
                test_wav_sha256=_sha256_bytes(byte_req.test_wav_bytes),
                reference_wav_sha256=(
                    None
                    if byte_req.reference_wav_bytes is None
                    else _sha256_bytes(byte_req.reference_wav_bytes)
                ),
                question=byte_req.question,
                channel=byte_req.channel,
                segment_policy=byte_req.segment_policy,
            )
        )
    return tuple(sealed)


def compute_seal_readiness(
    budget: BudgetAssessment | None,
    *,
    label_review_errors: tuple[str, ...] = (),
) -> bool:
    """Complete effective limits are required before a candidate is seal-ready."""
    if label_review_errors:
        return False
    if budget is None:
        return False
    if budget.execution_blocked or budget.blockers:
        return False
    if budget.worst_case_requests is None:
        return False
    return not (budget.worst_case_input_tokens is None or budget.worst_case_output_tokens is None)


def make_complete_budget_assessment(
    *,
    planner_calls_per_slot_bound: int,
    transport_attempts_per_call_bound: int,
    input_token_bound_per_call: int,
    output_token_bound_per_call: int,
    audited_agent_limits: dict[str, int | None] | None = None,
    temperature: float = 0.0,
    thinking_disabled: bool = True,
) -> BudgetAssessment:
    """Construct a complete budget that can mark a temporary candidate seal-ready.

    Production ``inspect_limits`` still reports unknown product request/token
    bounds as blockers; those remain real seal blockers until known.
    """
    from signal_diag.evaluation.planner_ablation.v2.models import (
        AUDITED_AGENT_LIMIT_DEFAULTS,
        PRODUCT_SLOT_COUNT_V2,
    )

    audited = audited_agent_limits or dict(AUDITED_AGENT_LIMIT_DEFAULTS)
    worst_case_requests = (
        PRODUCT_SLOT_COUNT_V2
        * planner_calls_per_slot_bound
        * transport_attempts_per_call_bound
    )
    budget = BudgetAssessment(
        product_slot_count=PRODUCT_SLOT_COUNT_V2,
        planner_calls_per_slot_bound=planner_calls_per_slot_bound,
        transport_attempts_per_call_bound=transport_attempts_per_call_bound,
        worst_case_requests=worst_case_requests,
        worst_case_input_tokens=worst_case_requests * input_token_bound_per_call,
        worst_case_output_tokens=worst_case_requests * output_token_bound_per_call,
        audited_agent_limits=audited,
        temperature=temperature,
        thinking_disabled=thinking_disabled,
        blockers=(),
        execution_blocked=False,
        seal_ready=True,
    )
    if not compute_seal_readiness(budget):
        raise ValueError("constructed budget is not seal-ready")
    return budget


def build_candidate_manifest(
    *,
    repository_root: Path,
    input_root: Path,
    protocol: StudyProtocolV2 | None = None,
    question: str = DEFAULT_STUDY_QUESTION,
    effective_configuration: EffectiveConfiguration | None = None,
    budget_assessment: BudgetAssessment | None = None,
    operator_authorization_references: tuple[str, ...] = (),
    environment_notes: tuple[str, ...] = (),
    code_bindings: CodeBindingsV2 | None = None,
) -> CandidateManifestV2:
    """Assemble a candidate from verified inputs under the declared roots."""
    repo = repository_root.resolve()
    inputs = input_root.resolve()
    protocol = protocol or StudyProtocolV2()
    if protocol.study_id != STUDY_ID_V2:
        raise ValueError(f"foreign protocol study_id: {protocol.study_id}")
    if protocol.scoring_identity != SCORING_IDENTITY_V2:
        raise ValueError("foreign scoring_identity")
    if protocol.scoring_version != SCORING_VERSION_V2:
        raise ValueError("foreign scoring_version")

    scenarios = load_proposed_scenarios(inputs)
    schedule = build_schedule(
        scenarios,
        protocol,
        repository_root=inputs,
        question=question,
    )
    label_review = validate_labels(scenarios, schedule)
    bindings = code_bindings if code_bindings is not None else collect_code_bindings(repo)
    input_identity = _input_identity_from_scenarios(scenarios)
    sealed_requests = _seal_requests_from_schedule(schedule)
    budget = budget_assessment
    if budget is None and effective_configuration is not None:
        assessed = inspect_limits(effective_configuration)
        budget = assessed.model_copy(
            update={"seal_ready": compute_seal_readiness(assessed)}
        )
    seal_ready = compute_seal_readiness(
        budget,
        label_review_errors=label_review.errors,
    )

    environment = EnvironmentBindingV2(
        platform=platform.platform(),
        measurement_policy="encoded_bytes_to_terminal_v1_wall_clock",
        notes=environment_notes,
    )
    normalized_question = normalize_question(question)
    candidate_digest = _digest_payload(
        _candidate_digest_payload(
            protocol=protocol,
            scenarios=scenarios,
            schedule_digest=schedule.schedule_digest,
            scenario_aliases=schedule.scenario_aliases,
            slots=schedule.slots,
            sealed_requests=sealed_requests,
            label_review=label_review,
            input_identity=input_identity,
            bindings=bindings,
            environment=environment,
            operator_authorization_references=operator_authorization_references,
            effective_configuration=effective_configuration,
            budget=budget,
            question=normalized_question,
        )
    )
    return CandidateManifestV2(
        protocol=protocol,
        scenarios=scenarios,
        schedule_digest=schedule.schedule_digest,
        scenario_aliases=dict(sorted(schedule.scenario_aliases.items())),
        sealed_requests=sealed_requests,
        slots=schedule.slots,
        label_review=label_review,
        input_identity=input_identity,
        code_identity=bindings.aggregate_code_identity,
        code_bindings=bindings,
        environment=environment,
        operator_authorization_references=operator_authorization_references,
        effective_configuration=effective_configuration,
        budget_assessment=budget,
        question=normalized_question,
        seal_ready=seal_ready,
        candidate_digest=candidate_digest,
    )


def _refuse_dev1_destination(destination: Path) -> None:
    text = str(destination.resolve()).replace("\\", "/")
    if "study_s1_planner_ablation_dev_1" in text:
        raise ValueError(
            "refusing generate against study_s1_planner_ablation_dev_1 under any mode"
        )


def _require_seal_grant_for_real_evidence(destination: Path) -> None:
    text = str(destination.resolve()).replace("\\", "/")
    if (
        all(marker in text for marker in _REAL_EVIDENCE_MARKERS)
        and os.environ.get("PLANNER_ABLATION_V2_SEAL_GRANT") != "1"
    ):
        raise PermissionError(
            "real evidence-root seal requires a later seal grant "
            "(set PLANNER_ABLATION_V2_SEAL_GRANT=1 only under that grant)"
        )


def generate_seal(candidate: CandidateManifestV2, destination: Path) -> Path:
    """Write a new seal directory exclusively. Never deletes or replaces."""
    _refuse_dev1_destination(destination)
    _require_seal_grant_for_real_evidence(destination)
    if candidate.study_id != STUDY_ID_V2:
        raise ValueError("foreign study_id")
    if candidate.scoring_identity != SCORING_IDENTITY_V2:
        raise ValueError("foreign scoring_identity")
    if candidate.scoring_version != SCORING_VERSION_V2:
        raise ValueError("foreign scoring_version")
    if candidate.study_id == _DEV1_STUDY_ID:
        raise ValueError("foreign v1 identity")
    if not candidate.seal_ready:
        raise ValueError(
            "candidate is not seal-ready; complete effective limits and clear blockers"
        )
    if len(candidate.slots) != SLOT_COUNT_V2:
        raise ValueError("candidate slot count drift")
    if destination.exists():
        raise FileExistsError(
            f"seal destination already exists: {destination}; "
            "refuse overwrite even for an empty directory"
        )
    # Exclusive directory creation: exist_ok=False is the race-safe create.
    destination.mkdir(parents=True, exist_ok=False)

    manifest_payload = candidate.model_dump(mode="json")
    meta = {
        "study_id": candidate.study_id,
        "scoring_identity": candidate.scoring_identity,
        "scoring_version": candidate.scoring_version,
        "candidate_digest": candidate.candidate_digest,
        "schedule_digest": candidate.schedule_digest,
        "input_identity": candidate.input_identity,
        "code_identity": candidate.code_identity,
        "implementation_commit": candidate.code_bindings.implementation_commit,
        "slot_count": len(candidate.slots),
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest_payload, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    (destination / "seal_meta.json").write_text(
        json.dumps(meta, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    lines: list[str] = []
    for name in sorted(path.name for path in destination.iterdir() if path.is_file()):
        lines.append(
            _CHECKSUM_LINE.format(digest=_sha256_file(destination / name), name=name)
        )
    if not lines:
        raise ValueError("seal checksum index must not be empty")
    (destination / "seal.sha256").write_text("".join(lines), encoding="utf-8")
    return destination


def _load_manifest(seal_dir: Path) -> dict[str, Any]:
    manifest_path = seal_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"missing manifest.json under {seal_dir}")
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError("manifest.json must be an object")
    return raw


def _verify_seal_index(seal_dir: Path) -> None:
    seal_path = seal_dir / "seal.sha256"
    if not seal_path.is_file():
        raise FileNotFoundError("missing seal.sha256")
    records: dict[str, str] = {}
    for raw in seal_path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        digest, name = raw.split("  ", 1)
        if name in records:
            raise ValueError(f"duplicate seal checksum entry: {name}")
        records[name] = digest
    if not {"manifest.json", "seal_meta.json"}.issubset(records.keys()):
        missing = sorted({"manifest.json", "seal_meta.json"} - records.keys())
        raise ValueError(f"seal checksum index missing required entries: {missing}")
    for name, expected in sorted(records.items()):
        path = seal_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"sealed artifact missing on disk: {name}")
        if _sha256_file(path) != expected:
            raise ValueError(f"seal hash mismatch for {name}")


def _recompute_code_bindings(
    repository_root: Path,
    declared: CodeBindingsV2,
) -> None:
    root = repository_root.resolve()
    # Working bytes must match declared digests.
    for relative, expected in sorted(declared.bound_file_digests.items()):
        path = resolve_under_root(root, relative, label="code")
        if not path.is_file():
            raise FileNotFoundError(f"bound code file missing during verify: {relative}")
        actual = _sha256_file(path)
        if actual != expected:
            raise ValueError(f"code binding hash mismatch for {relative}")
        if _path_dirty(root, relative):
            raise ValueError(f"dirty relevant code during verify: {relative}")
        committed = _commit_blob_digest(root, declared.implementation_commit, relative)
        if committed != expected:
            raise ValueError(
                f"code binding diverges from implementation commit for {relative}"
            )
    # Entry scripts are mandatory.
    for script, expected in declared.entry_script_digests.items():
        if declared.bound_file_digests.get(script) != expected:
            raise ValueError(f"entry script digest inconsistency: {script}")
    prompt_actual = _sha256_file(resolve_under_root(root, _PROMPT_MODULE, label="prompt"))
    if prompt_actual != declared.prompt_module_digest:
        raise ValueError("prompt module digest mismatch")
    for relative, expected in declared.profile_digests.items():
        actual = _sha256_file(resolve_under_root(root, relative, label="profile"))
        if actual != expected:
            raise ValueError(f"profile digest mismatch for {relative}")
    for relative, expected in declared.corpus_digests.items():
        actual = _sha256_file(resolve_under_root(root, relative, label="corpus"))
        if actual != expected:
            raise ValueError(f"corpus digest mismatch for {relative}")
    live_deps = _dependency_versions()
    if live_deps != declared.dependency_versions:
        raise ValueError("dependency identity mismatch")
    live_aggregate = _digest_payload(
        {
            "bound_file_digests": declared.bound_file_digests,
            "entry_script_digests": declared.entry_script_digests,
            "implementation_commit": declared.implementation_commit,
        }
    )
    if live_aggregate != declared.aggregate_code_identity:
        raise ValueError("aggregate code identity mismatch")


def _verify_inputs_and_schedule(
    candidate: CandidateManifestV2,
    *,
    input_root: Path,
) -> Schedule:
    root = input_root.resolve()
    # Re-read WAV bytes and reject digest drift.
    for scenario in candidate.scenarios:
        test_path = resolve_under_root(root, scenario.test_wav_relpath, label="wav")
        ref_path = resolve_under_root(root, scenario.reference_wav_relpath, label="wav")
        if not test_path.is_file() or not ref_path.is_file():
            raise FileNotFoundError(
                f"missing WAV inputs for {scenario.scenario_id}"
            )
        test_digest = _sha256_file(test_path)
        ref_digest = _sha256_file(ref_path)
        if test_digest != scenario.test_wav_sha256:
            raise ValueError(f"WAV byte digest mismatch for {scenario.scenario_id} test")
        if ref_digest != scenario.reference_wav_sha256:
            raise ValueError(
                f"WAV byte digest mismatch for {scenario.scenario_id} reference"
            )

    rebuilt = build_schedule(
        candidate.scenarios,
        candidate.protocol,
        repository_root=root,
        question=candidate.question,
    )
    if rebuilt.schedule_digest != candidate.schedule_digest:
        raise ValueError("reconstructed schedule digest mismatch")
    if dict(sorted(rebuilt.scenario_aliases.items())) != dict(
        sorted(candidate.scenario_aliases.items())
    ):
        raise ValueError("alias mapping mismatch")
    if rebuilt.slots != candidate.slots:
        raise ValueError("frozen slot identity/order mismatch")
    if len(rebuilt.slots) != SLOT_COUNT_V2:
        raise ValueError("slot count drift")

    sealed_live = _seal_requests_from_schedule(rebuilt)
    if sealed_live != candidate.sealed_requests:
        raise ValueError("sealed request identity mismatch")

    # Channel / question / segment policy must match sealed requests.
    for sealed, live in zip(candidate.sealed_requests, sealed_live, strict=True):
        if sealed.channel != candidate.channel:
            raise ValueError("channel policy mismatch")
        if sealed.segment_policy != candidate.segment_policy:
            raise ValueError("segment policy mismatch")
        if sealed.question != candidate.question:
            raise ValueError("question policy mismatch")
        key = compute_request_key(
            mode=live.mode,
            test_wav_bytes=next(
                r.byte_request.test_wav_bytes
                for r in rebuilt.canonical_requests
                if r.request_key == live.request_key
            ),
            reference_wav_bytes=next(
                r.byte_request.reference_wav_bytes
                for r in rebuilt.canonical_requests
                if r.request_key == live.request_key
            ),
            question=candidate.question,
            channel=candidate.channel,
            segment_policy=candidate.segment_policy,
        )
        if key != sealed.request_key:
            raise ValueError("request key recomputation mismatch")

    live_input_identity = _input_identity_from_scenarios(candidate.scenarios)
    if live_input_identity != candidate.input_identity:
        raise ValueError("input_identity mismatch")

    label_review = validate_labels(candidate.scenarios, rebuilt)
    if label_review.errors != candidate.label_review.errors:
        raise ValueError("label review consistency mismatch")
    if (
        label_review.upgrade_population != candidate.label_review.upgrade_population
        or label_review.conditional_population
        != candidate.label_review.conditional_population
        or label_review.guidance_population != candidate.label_review.guidance_population
    ):
        raise ValueError("U/C/G population mismatch")
    return rebuilt


def verify_manifest(
    path: Path,
    *,
    repository_root: Path,
    input_root: Path,
) -> VerifiedStudyV2:
    """Production constructor for Task 4 verified input. Read-only."""
    seal_dir = path.resolve()
    if not seal_dir.is_dir():
        raise FileNotFoundError(f"seal directory missing: {seal_dir}")
    _verify_seal_index(seal_dir)
    raw = _load_manifest(seal_dir)
    try:
        candidate = CandidateManifestV2.model_validate(raw)
    except Exception as exc:
        raise ValueError(f"malformed or foreign manifest schema: {exc}") from exc

    if candidate.study_id != STUDY_ID_V2:
        raise ValueError("foreign study identity")
    if candidate.scoring_identity != SCORING_IDENTITY_V2:
        raise ValueError("foreign scoring_identity")
    if candidate.scoring_version != SCORING_VERSION_V2:
        raise ValueError("foreign scoring_version")
    if candidate.study_id == _DEV1_STUDY_ID:
        raise ValueError("foreign v1 identity")

    # Canonical digest over the sealed payload (excluding candidate_digest itself).
    recomputed = _digest_payload(
        _candidate_digest_payload(
            protocol=candidate.protocol,
            scenarios=candidate.scenarios,
            schedule_digest=candidate.schedule_digest,
            scenario_aliases=candidate.scenario_aliases,
            slots=candidate.slots,
            sealed_requests=candidate.sealed_requests,
            label_review=candidate.label_review,
            input_identity=candidate.input_identity,
            bindings=candidate.code_bindings,
            environment=candidate.environment,
            operator_authorization_references=candidate.operator_authorization_references,
            effective_configuration=candidate.effective_configuration,
            budget=candidate.budget_assessment,
            question=candidate.question,
        )
    )
    if recomputed != candidate.candidate_digest:
        raise ValueError("canonical manifest digest mismatch")

    meta = json.loads((seal_dir / "seal_meta.json").read_text(encoding="utf-8"))
    if meta.get("candidate_digest") != candidate.candidate_digest:
        raise ValueError("seal_meta candidate_digest mismatch")
    if meta.get("study_id") != STUDY_ID_V2:
        raise ValueError("seal_meta foreign study identity")

    _recompute_code_bindings(repository_root, candidate.code_bindings)
    if candidate.code_identity != candidate.code_bindings.aggregate_code_identity:
        raise ValueError("code_identity field mismatch")
    schedule = _verify_inputs_and_schedule(candidate, input_root=input_root)

    verified_identity = _digest_payload(
        {
            "candidate_digest": candidate.candidate_digest,
            "code_identity": candidate.code_identity,
            "construction_path": "verify_manifest",
            "input_identity": candidate.input_identity,
            "schedule_digest": schedule.schedule_digest,
            "study_id": STUDY_ID_V2,
        }
    )
    return VerifiedStudyV2(
        protocol=candidate.protocol,
        schedule=schedule,
        scenarios=candidate.scenarios,
        label_review=candidate.label_review,
        verified_identity=verified_identity,
        input_identity=candidate.input_identity,
        code_identity=candidate.code_identity,
        construction_path="verify_manifest",
        pinned_causal_policy="v9_11_mode_aware_no_fault_recovery",
        resource_policy=(
            str(candidate.resource_extension.get("resource_policy"))
            if isinstance(candidate.resource_extension, dict)
            and candidate.resource_extension.get("resource_policy")
            else None
        ),
        resource_extension=candidate.resource_extension,
    )


def validate_resource_candidate(
    candidate: CandidateManifestV2,
    *,
    repository_root: Path,
) -> ResourceCandidateValidation:
    """Recompute resource proofs/readiness without SDK client construction or seal writes."""
    from signal_diag.evaluation.planner_ablation.v2.resource_budget import (
        assess_resource_budget,
    )
    from signal_diag.evaluation.planner_ablation.v2.resource_models import (
        ResourceCandidateExtension,
    )

    reasons: list[str] = []
    extension_raw = candidate.resource_extension
    if extension_raw is None:
        return ResourceCandidateValidation(
            ready=False,
            reasons=("missing_resource_extension",),
            assessment=None,
            recomputed_extension_digest=None,
            fixture_only=True,
        )
    try:
        extension = ResourceCandidateExtension.model_validate(extension_raw)
    except Exception as error:  # noqa: BLE001
        return ResourceCandidateValidation(
            ready=False,
            reasons=(f"invalid_resource_extension:{type(error).__name__}",),
            assessment=None,
            recomputed_extension_digest=None,
            fixture_only=True,
        )

    if extension.resource_policy != "planner_ablation_resource_v1":
        reasons.append("resource_policy_mismatch")
    if extension.telemetry_schema != "planner_ablation_telemetry_v1":
        reasons.append("telemetry_schema_mismatch")
    if extension.fixture_only:
        reasons.append("fixture_only_resource_extension")

    # Label review must bind approved population; caller booleans are insufficient.
    if not candidate.label_review.approved:
        reasons.append("label_review_not_approved")
    label_digest = _digest_payload(candidate.label_review.model_dump(mode="json"))
    if label_digest != extension.label_review_digest:
        reasons.append("label_review_digest_mismatch")

    bindings = collect_code_bindings(repository_root.resolve())
    if bindings.aggregate_code_identity != extension.code_identity:
        reasons.append("code_identity_mismatch")
    if "openai" not in bindings.dependency_versions:
        reasons.append("missing_openai_dependency_binding")
    elif extension.provider_dependency_identity not in {
        f"openai=={bindings.dependency_versions['openai']}",
        bindings.dependency_versions["openai"],
    }:
        reasons.append("provider_dependency_identity_mismatch")

    config = candidate.effective_configuration or EffectiveConfiguration()
    assessment = assess_resource_budget(
        config,
        extension.proofs,
        extension.capability,
    )
    if assessment.execution_blocked:
        reasons.extend(assessment.blockers)
        reasons.append("resource_assessment_blocked")
    if assessment.model_dump(mode="json") != extension.assessment.model_dump(mode="json"):
        reasons.append("assessment_recompute_mismatch")

    recomputed_digest = _digest_payload(
        {
            "resource_policy": extension.resource_policy,
            "telemetry_schema": extension.telemetry_schema,
            "proofs": extension.proofs.model_dump(mode="json"),
            "capability": extension.capability.model_dump(mode="json"),
            "assessment": assessment.model_dump(mode="json"),
            "provider_dependency_identity": extension.provider_dependency_identity,
            "label_review_digest": extension.label_review_digest,
            "label_population_digest": extension.label_population_digest,
            "code_identity": extension.code_identity,
        }
    )
    if recomputed_digest != extension.extension_digest:
        reasons.append("extension_digest_mismatch")

    # Production readiness never trusts make_complete_budget_assessment fixtures.
    if (
        candidate.budget_assessment is not None
        and candidate.budget_assessment.seal_ready
        and candidate.budget_assessment.blockers == ()
    ):
        # Still require resource assessment independently; fixture completeness
        # alone never authorizes production readiness.
        pass

    unique = tuple(dict.fromkeys(reasons))
    ready = len(unique) == 0 and not assessment.execution_blocked
    return ResourceCandidateValidation(
        ready=ready,
        reasons=unique,
        assessment=assessment,
        recomputed_extension_digest=recomputed_digest,
        fixture_only=extension.fixture_only,
    )


def tree_file_digests(root: Path) -> dict[str, str]:
    """Snapshot every regular file under root (for read-only verify proofs)."""
    digests: dict[str, str] = {}
    root = root.resolve()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = str(path.relative_to(root)).replace("\\", "/")
        digests[relative] = _sha256_file(path)
    return digests
