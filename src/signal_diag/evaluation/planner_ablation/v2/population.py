"""Canonical request identity, aliases, and schedule construction (dev_2)."""

from __future__ import annotations

import json
import unicodedata
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path

from signal_diag.evaluation.planner_ablation.v2.models import (
    DEFAULT_STUDY_QUESTION,
    STUDY_ID_V2,
    ByteRequest,
    CanonicalRequest,
    OracleLabel,
    ScenarioDefinition,
    Schedule,
    ScoredArm,
    SlotKey,
    StudyMode,
    StudyProtocolV2,
)

_WAV_ROOT = Path(
    "docs/evaluations/v0_3/contextual/development/study_v0_3_contextual_dev_1/wav"
)

# Source/master relationships copied from study_s1_planner_ablation_dev_1 seal.
_CASE_SOURCES: tuple[dict[str, str], ...] = (
    {
        "scenario_id": "825a759a0ea47bb7",
        "role": "clean",
        "source_id": "nsynth_note_master_organ_a",
        "parent_master_id": "master_organ_a",
        "license_id": "CC-BY-4.0",
    },
    {
        "scenario_id": "857fac53e4d2e57e",
        "role": "clipping",
        "source_id": "nsynth_note_master_organ_a",
        "parent_master_id": "master_organ_a",
        "license_id": "CC-BY-4.0",
    },
    {
        "scenario_id": "abd9010438d4ad93",
        "role": "clipping",
        "source_id": "nsynth_note_master_bass_a",
        "parent_master_id": "master_bass_a",
        "license_id": "CC-BY-4.0",
    },
    {
        "scenario_id": "a4a0853be9983f8c",
        "role": "harmonic",
        "source_id": "nsynth_note_master_organ_b",
        "parent_master_id": "master_organ_b",
        "license_id": "CC-BY-4.0",
    },
    {
        "scenario_id": "2be730b9113701de",
        "role": "harmonic",
        "source_id": "nsynth_note_master_bass_b",
        "parent_master_id": "master_bass_b",
        "license_id": "CC-BY-4.0",
    },
    {
        "scenario_id": "6fb80bbda391c26c",
        "role": "combined",
        "source_id": "nsynth_note_master_guitar_a",
        "parent_master_id": "master_guitar_a",
        "license_id": "CC-BY-4.0",
    },
    {
        "scenario_id": "aa9b4a91b0253c33",
        "role": "combined",
        "source_id": "nsynth_note_master_organ_a",
        "parent_master_id": "master_organ_a",
        "license_id": "CC-BY-4.0",
    },
    {
        "scenario_id": "393940e92c58cf0b",
        "role": "natural_even_control",
        "source_id": "nsynth_note_master_organ_rich_a",
        "parent_master_id": "master_organ_rich_a",
        "license_id": "CC-BY-4.0",
    },
    {
        "scenario_id": "04f4068ec91d2621",
        "role": "natural_even_control",
        "source_id": "nsynth_note_master_organ_rich_b",
        "parent_master_id": "master_organ_rich_b",
        "license_id": "CC-BY-4.0",
    },
    {
        "scenario_id": "163185980dc8f7a4",
        "role": "invalid_comparison",
        "source_id": "nsynth_note_master_organ_a",
        "parent_master_id": "master_organ_a",
        "license_id": "CC-BY-4.0",
    },
)

# Design §5.1 mode-specific proposed oracle (exact causal sets).
_ORACLES: Mapping[str, tuple[OracleLabel, OracleLabel]] = {
    "825a759a0ea47bb7": (
        OracleLabel(outcome="no_supported_fault", exact_causal_faults=()),
        OracleLabel(outcome="no_supported_fault", exact_causal_faults=()),
    ),
    "857fac53e4d2e57e": (
        OracleLabel(outcome="supported_fault", exact_causal_faults=("clipping",)),
        OracleLabel(outcome="supported_fault", exact_causal_faults=("clipping",)),
    ),
    "abd9010438d4ad93": (
        OracleLabel(outcome="supported_fault", exact_causal_faults=("clipping",)),
        OracleLabel(outcome="supported_fault", exact_causal_faults=("clipping",)),
    ),
    "a4a0853be9983f8c": (
        OracleLabel(outcome="inconclusive", exact_causal_faults=()),
        OracleLabel(
            outcome="supported_fault",
            exact_causal_faults=("harmonic_distortion",),
        ),
    ),
    "2be730b9113701de": (
        OracleLabel(outcome="inconclusive", exact_causal_faults=()),
        OracleLabel(
            outcome="supported_fault",
            exact_causal_faults=("harmonic_distortion",),
        ),
    ),
    "6fb80bbda391c26c": (
        OracleLabel(outcome="supported_fault", exact_causal_faults=("clipping",)),
        OracleLabel(
            outcome="supported_fault",
            exact_causal_faults=("clipping", "harmonic_distortion"),
        ),
    ),
    "aa9b4a91b0253c33": (
        OracleLabel(outcome="supported_fault", exact_causal_faults=("clipping",)),
        OracleLabel(
            outcome="supported_fault",
            exact_causal_faults=("clipping", "harmonic_distortion"),
        ),
    ),
    "393940e92c58cf0b": (
        OracleLabel(outcome="inconclusive", exact_causal_faults=()),
        OracleLabel(outcome="no_supported_fault", exact_causal_faults=()),
    ),
    "04f4068ec91d2621": (
        OracleLabel(outcome="inconclusive", exact_causal_faults=()),
        OracleLabel(outcome="no_supported_fault", exact_causal_faults=()),
    ),
    "163185980dc8f7a4": (
        OracleLabel(outcome="no_supported_fault", exact_causal_faults=()),
        OracleLabel(outcome="inconclusive", exact_causal_faults=()),
    ),
}

_UPGRADE_TARGETS: Mapping[str, str | None] = {
    "a4a0853be9983f8c": "harmonic_attribution",
    "2be730b9113701de": "harmonic_attribution",
    "6fb80bbda391c26c": "additional_harmonic_coverage",
    "aa9b4a91b0253c33": "additional_harmonic_coverage",
    "393940e92c58cf0b": "supported_no_fault_natural_control",
    "04f4068ec91d2621": "supported_no_fault_natural_control",
    "163185980dc8f7a4": None,
}

_GUIDANCE_IDS = frozenset(
    {
        "a4a0853be9983f8c",
        "2be730b9113701de",
        "393940e92c58cf0b",
        "04f4068ec91d2621",
    }
)

_RATIONALES: Mapping[str, str] = {
    "825a759a0ea47bb7": (
        "Clean paired replica of the organ-a master. Single and paired gates "
        "support no_supported_fault; empty causal set."
    ),
    "857fac53e4d2e57e": (
        "Clipping transform of organ-a. Single and paired support clipping only."
    ),
    "abd9010438d4ad93": (
        "Clipping transform of bass-a. Single and paired support clipping only."
    ),
    "a4a0853be9983f8c": (
        "Harmonic transform of organ-b. Single-file gates cannot attribute the "
        "harmonic fault without paired context (inconclusive). Paired supports "
        "exact {harmonic_distortion}."
    ),
    "2be730b9113701de": (
        "Harmonic transform of bass-b. Same single inconclusive / paired "
        "harmonic_distortion construction as organ-b harmonic."
    ),
    "6fb80bbda391c26c": (
        "Combined clipping+harmonic of guitar-a. Single supports clipping only; "
        "paired exact set is {clipping, harmonic_distortion}."
    ),
    "aa9b4a91b0253c33": (
        "Combined clipping+harmonic of organ-a. Same single/paired causal split "
        "as the guitar-a combined case."
    ),
    "393940e92c58cf0b": (
        "Natural even-control organ-rich-a. Single remains conservative "
        "inconclusive under demonstration THD gates; paired supports "
        "no_supported_fault once context is valid."
    ),
    "04f4068ec91d2621": (
        "Natural even-control organ-rich-b. Same single inconclusive / paired "
        "no_supported_fault construction as organ-rich-a."
    ),
    "163185980dc8f7a4": (
        "Invalid-reference negative control sharing clean organ-a test bytes. "
        "Single oracle follows the clean identical input (no_supported_fault). "
        "Paired remains inconclusive because the reference is invalid."
    ),
}


def normalize_question(question: str) -> str:
    """Unicode NFC plus CRLF/CR→LF. Preserve case and interior whitespace."""
    normalized = unicodedata.normalize("NFC", question)
    return normalized.replace("\r\n", "\n").replace("\r", "\n")


def _sha256_hex(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def compute_request_key(
    *,
    mode: StudyMode,
    test_wav_bytes: bytes,
    reference_wav_bytes: bytes | None,
    question: str,
    channel: str = "mixdown",
    segment_policy: str = "full_signal",
) -> str:
    """Lowercase SHA-256 of canonical public request metadata."""
    if mode == "single_signal" and reference_wav_bytes is not None:
        raise ValueError("single_signal request key rejects a supplied reference")
    if mode == "paired_reference" and reference_wav_bytes is None:
        raise ValueError("paired_reference request key requires reference bytes")
    metadata: dict[str, object] = {
        "channel": channel,
        "mode": mode,
        "question": normalize_question(question),
        "segment_policy": segment_policy,
        "test_wav_sha256": _sha256_hex(test_wav_bytes),
    }
    if reference_wav_bytes is not None:
        metadata["reference_wav_sha256"] = _sha256_hex(reference_wav_bytes)
    return _sha256_hex(canonical_json(metadata).encode("utf-8"))


def _wav_relpath(scenario_id: str, kind: str) -> str:
    return str(_WAV_ROOT / f"cxdev_{scenario_id}_{kind}.wav")


def load_proposed_scenarios(repository_root: Path) -> tuple[ScenarioDefinition, ...]:
    """Load the unsealed design proposal from existing development WAV bytes."""
    root = repository_root.resolve()
    scenarios: list[ScenarioDefinition] = []
    for row in _CASE_SOURCES:
        scenario_id = row["scenario_id"]
        test_rel = _wav_relpath(scenario_id, "test")
        ref_rel = _wav_relpath(scenario_id, "ref")
        test_path = root / test_rel
        ref_path = root / ref_rel
        if not test_path.is_file() or not ref_path.is_file():
            raise FileNotFoundError(
                f"missing study WAV inputs for {scenario_id}: {test_rel}, {ref_rel}"
            )
        test_bytes = test_path.read_bytes()
        ref_bytes = ref_path.read_bytes()
        single_oracle, paired_oracle = _ORACLES[scenario_id]
        in_upgrade = scenario_id in _UPGRADE_TARGETS
        if scenario_id == "163185980dc8f7a4":
            obtainable, valid, sufficient = True, False, False
        elif in_upgrade:
            obtainable, valid, sufficient = True, True, True
        else:
            obtainable, valid, sufficient = False, False, False
        scenarios.append(
            ScenarioDefinition(
                scenario_id=scenario_id,
                source_id=row["source_id"],
                parent_master_id=row["parent_master_id"],
                role=row["role"],
                license_id=row["license_id"],
                test_wav_relpath=test_rel,
                test_wav_sha256=_sha256_hex(test_bytes),
                reference_wav_relpath=ref_rel,
                reference_wav_sha256=_sha256_hex(ref_bytes),
                single_oracle=single_oracle,
                paired_oracle=paired_oracle,
                rationale=_RATIONALES[scenario_id],
                upgrade_target=_UPGRADE_TARGETS.get(scenario_id),
                in_upgrade_population=in_upgrade,
                context_obtainable=obtainable,
                context_valid=valid,
                context_sufficient=sufficient,
                in_guidance_population=scenario_id in _GUIDANCE_IDS,
            )
        )
    return tuple(scenarios)


def build_schedule(
    scenarios: Sequence[ScenarioDefinition],
    protocol: StudyProtocolV2,
    *,
    repository_root: Path | None = None,
    question: str = DEFAULT_STUDY_QUESTION,
) -> Schedule:
    """Build the unique-request schedule with aliases and expanded slots."""
    if protocol.study_id != STUDY_ID_V2:
        raise ValueError(f"foreign protocol study_id: {protocol.study_id}")
    if not scenarios:
        raise ValueError("empty population")

    root = (repository_root or Path.cwd()).resolve()
    normalized_question = normalize_question(question)
    # request_key -> (mode, oracle, representative_id, byte_request)
    unique: dict[str, tuple[StudyMode, OracleLabel, str, ByteRequest]] = {}
    aliases: dict[str, str] = {}
    seen_ids: set[str] = set()

    for scenario in scenarios:
        if scenario.scenario_id in seen_ids:
            raise ValueError(f"duplicate scenario_id: {scenario.scenario_id}")
        seen_ids.add(scenario.scenario_id)
        test_path = root / scenario.test_wav_relpath
        ref_path = root / scenario.reference_wav_relpath
        test_bytes = test_path.read_bytes()
        ref_bytes = ref_path.read_bytes()
        if _sha256_hex(test_bytes) != scenario.test_wav_sha256:
            raise ValueError(f"test WAV hash mismatch for {scenario.scenario_id}")
        if _sha256_hex(ref_bytes) != scenario.reference_wav_sha256:
            raise ValueError(f"reference WAV hash mismatch for {scenario.scenario_id}")

        mode_rows: tuple[tuple[StudyMode, OracleLabel, bytes | None], ...] = (
            ("single_signal", scenario.single_oracle, None),
            ("paired_reference", scenario.paired_oracle, ref_bytes),
        )
        for mode, oracle, reference in mode_rows:
            request = ByteRequest(
                mode=mode,
                test_wav_bytes=test_bytes,
                reference_wav_bytes=reference,
                question=normalized_question,
            )
            key = compute_request_key(
                mode=mode,
                test_wav_bytes=test_bytes,
                reference_wav_bytes=reference,
                question=normalized_question,
            )
            existing = unique.get(key)
            if existing is None:
                unique[key] = (mode, oracle, scenario.scenario_id, request)
                continue
            existing_mode, existing_oracle, representative_id, _existing_request = existing
            if existing_mode != mode:
                raise ValueError(f"unexpected cross-mode request-key collision: {key}")
            if existing_oracle.fingerprint() != oracle.fingerprint():
                raise ValueError(
                    "conflicting equal-input oracle labels for "
                    f"{representative_id} and {scenario.scenario_id}"
                )
            if representative_id == scenario.scenario_id:
                continue
            # First occurrence remains the scored representative; later logical
            # scenarios alias to it (design: 1631 single -> 825a).
            if mode == "single_signal":
                prior = aliases.get(scenario.scenario_id)
                if prior is not None and prior != representative_id:
                    raise ValueError(
                        f"inconsistent alias for {scenario.scenario_id}: "
                        f"{prior} vs {representative_id}"
                    )
                aliases[scenario.scenario_id] = representative_id
            else:
                raise ValueError(
                    "unexpected paired-mode request-key collision between "
                    f"{representative_id} and {scenario.scenario_id}"
                )

    ordered_keys = sorted(unique)
    canonical_requests = tuple(
        CanonicalRequest(
            request_key=key,
            mode=unique[key][0],
            representative_scenario_id=unique[key][2],
            byte_request=unique[key][3],
        )
        for key in ordered_keys
    )

    slots: list[SlotKey] = []
    for round_index in range(int(protocol.rounds)):
        for key_index, request_key in enumerate(ordered_keys):
            arm_order: tuple[ScoredArm, ScoredArm]
            if (key_index + round_index) % 2 == 0:
                arm_order = ("product_agent", "fixed_pipeline")
            else:
                arm_order = ("fixed_pipeline", "product_agent")
            for arm in arm_order:
                slots.append(
                    SlotKey(
                        request_key=request_key,
                        arm=arm,
                        round_index=round_index,
                    )
                )

    digest_payload = {
        "aliases": dict(sorted(aliases.items())),
        "requests": [
            {
                "mode": req.mode,
                "representative_scenario_id": req.representative_scenario_id,
                "request_key": req.request_key,
            }
            for req in canonical_requests
        ],
        "rounds": int(protocol.rounds),
        "slots": [
            {
                "arm": slot.arm,
                "request_key": slot.request_key,
                "round_index": slot.round_index,
            }
            for slot in slots
        ],
        "study_id": protocol.study_id,
    }
    return Schedule(
        canonical_requests=canonical_requests,
        scenario_aliases=dict(sorted(aliases.items())),
        slots=tuple(slots),
        schedule_digest=_sha256_hex(canonical_json(digest_payload).encode("utf-8")),
    )
