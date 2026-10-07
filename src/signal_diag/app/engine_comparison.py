"""Offline engine-versus-recorded-planner comparison (D053 §4, T-CX449, T-CX452).

Runs the deterministic engine over every recorded study case with ground truth
and reports per-set correctness next to the recorded planner results. No model
is called. ``python -m signal_diag.app.engine_comparison --out <report.json>``
regenerates the committed report.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from signal_diag.agent.engine import (
    ENGINE_LIMITS,
    ENGINE_VERSION,
    DeterministicDiagnosisEngine,
)
from signal_diag.agent.models import AgentRunResult
from signal_diag.agent.runtime import DistortionDiagnosisRuntime
from signal_diag.app.composition import build_product_service
from signal_diag.app.guarded_tools import GuardedSignalToolService
from signal_diag.evaluation.dataset import _generate, load_dataset_manifest
from signal_diag.signal import InMemorySignalRepository, load_wav_bytes
from signal_diag.signal.context import DiagnosticMode, StimulusContext
from signal_diag.signal.models import SignalRecord

REPORT_SCHEMA = "engine_phase1_comparison/1"
QUESTION = "Why does this signal sound distorted?"
_CONTEXTUAL = Path("docs/evaluations/v0_3/contextual")
_INCREMENT = Path("docs/evaluations/v0_3/agent_increment/study_s1_agent_increment_1")
_V02_MANIFESTS = Path("src/signal_diag/evaluation/manifests")
# Accepted by the operator 2026-10-07 (D053): in nominal mode, clipping creates
# even harmonics that the rules cannot separate from harmonic distortion.
KNOWN_LIMITATIONS = {
    "dff3ebd9dffee874": (
        "nominal_single_tone clipping case also meets the harmonic gate; clipping "
        "creates even harmonics the rules cannot separate (sweep stimulus, phase 2)"
    ),
}
_V02_NOTE = (
    "Truth labels predate D037: single-file mode never attributes harmonic distortion, "
    "and invalid-noise cases are labelled no fault. Used for stability (no errors) "
    "only; not comparable with the accepted V0.2 79/80, which used another path."
)
_CONTEXTUAL_STUDIES = {
    "contextual_dev": "development/study_v0_3_contextual_dev_1",
    "contextual_validation": "validation/study_v0_3_contextual_validation_1",
}


@dataclass(frozen=True)
class EngineCase:
    group: str
    case_id: str
    mode: DiagnosticMode
    nominal_fundamental_hz: float | None
    truth_outcome: str
    truth_causal: tuple[str, ...]
    scoreable: bool
    load_test: Callable[[], SignalRecord]
    load_reference: Callable[[], SignalRecord] | None


def _wav(root: Path, relative: str) -> Callable[[], SignalRecord]:
    path = root / relative.replace("\\", "/")

    def load() -> SignalRecord:
        return load_wav_bytes(path.read_bytes(), filename=path.name).record

    return load


def engine_cases(root: Path) -> Iterator[EngineCase]:
    """Every recorded case with ground truth, in a fixed order."""
    for group, study in _CONTEXTUAL_STUDIES.items():
        base = root / _CONTEXTUAL / study
        manifest = json.loads((base / "contextual_manifest.json").read_text(encoding="utf-8"))
        scoreable = {case["case_id"] for case in manifest["cases"] if case["scoreable"]}
        records = json.loads((base / "case_build_record.json").read_text(encoding="utf-8"))
        for record in records:
            yield EngineCase(
                group=group,
                case_id=record["case_id"],
                mode=record["mode"],
                nominal_fundamental_hz=record.get("nominal_hz"),
                truth_outcome=record["outcome"],
                truth_causal=tuple(sorted(record["causal"])),
                scoreable=record["case_id"] in scoreable,
                load_test=_wav(base, record["test_path"]),
                load_reference=_wav(base, record["ref_path"]) if record.get("ref_path") else None,
            )
    manifest = json.loads((root / _INCREMENT / "manifest.json").read_text(encoding="utf-8"))
    for case in manifest["cases"]:
        truth = case["truth"]
        if case["split"] != "heldout" or truth["insufficient"]:
            continue
        test = next(path for path in case["files"] if path.endswith(case["test_file"]))
        reference = (
            next(path for path in case["files"] if path.endswith(truth["reference_file"]))
            if truth["reference_file"]
            else None
        )
        outcome = truth["conclusion"]
        yield EngineCase(
            group=f"increment_heldout_{case['family'].lower()}",
            case_id=case["case_id"],
            mode=truth["mode"],
            nominal_fundamental_hz=truth["nominal_fundamental_hz"],
            truth_outcome=(
                outcome if outcome in ("no_supported_fault", "inconclusive") else "supported_fault"
            ),
            truth_causal=tuple(sorted(truth["cause_set"])),
            scoreable=True,
            load_test=_wav(root, test),
            load_reference=_wav(root, reference) if reference else None,
        )
    for path in sorted((root / _V02_MANIFESTS).glob("s1_distortion_v1*.yaml")):
        for v02 in load_dataset_manifest(path).cases:
            causal = tuple(sorted(getattr(v02, "causal_faults", ()) or ()))

            def load(case: Any = v02) -> SignalRecord:
                return _generate(case).record

            yield EngineCase(
                group=f"v02_{path.stem}",
                case_id=v02.case_id,
                mode="single_signal",
                nominal_fundamental_hz=None,
                truth_outcome="supported_fault" if causal else "no_supported_fault",
                truth_causal=causal,
                scoreable=True,
                load_test=load,
                load_reference=None,
            )


async def run_engine(
    test: SignalRecord,
    reference: SignalRecord | None,
    *,
    mode: DiagnosticMode,
    nominal_fundamental_hz: float | None,
) -> AgentRunResult:
    """One engine run on the product's rules, knowledge and guarded tools."""
    dependencies = build_product_service(environ={})._dependencies
    repository = InMemorySignalRepository()
    repository.put(test)
    if reference is not None:
        repository.put(reference)
    context = StimulusContext(
        mode=mode,
        test_signal_id=test.meta.signal_id,
        reference_signal_id=reference.meta.signal_id if reference is not None else None,
        nominal_fundamental_hz=nominal_fundamental_hz,
        stimulus_kind="single_tone" if mode == "nominal_single_tone" else None,
        assertion_source="user_supplied",
    )
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=GuardedSignalToolService(repository),
        planner=DeterministicDiagnosisEngine(),
        limits=ENGINE_LIMITS,
        rule_engine=dependencies.rule_engine,
        rule_profile_loader=dependencies.rule_profile_loader,
        knowledge_index=dependencies.knowledge_index,
        causal_policy_version=dependencies.causal_policy_version,
    )
    return await runtime.run(
        signal_id=test.meta.signal_id, user_request=QUESTION, stimulus_context=context
    )


def _faults(result: AgentRunResult) -> tuple[str, ...]:
    diagnosis = result.diagnosis
    if diagnosis is None:
        return ()
    return tuple(
        sorted(
            {
                claim.fault_type
                for claim in diagnosis.claims
                if claim.fault_type in ("clipping", "harmonic_distortion")
            }
        )
    )


def correct(case: EngineCase, outcome: str | None, faults: tuple[str, ...]) -> bool:
    if outcome != case.truth_outcome:
        return False
    return case.truth_outcome != "supported_fault" or faults == case.truth_causal


def _recorded_planner(root: Path) -> dict[str, dict[str, Any]]:
    """Recorded planner results on the same scoreable cases (read-only)."""
    dev = json.loads(
        (
            root
            / _CONTEXTUAL
            / _CONTEXTUAL_STUDIES["contextual_dev"]
            / "agent_v9_11_dev_confirmation_2/run_summary.json"
        ).read_text(encoding="utf-8")
    )
    dev_correct = [
        row["case_id"]
        for row in dev["per_case_table"]
        if row.get("correct_outcome") and row.get("correct_causal")
    ]
    validation = json.loads(
        (
            root
            / _CONTEXTUAL
            / _CONTEXTUAL_STUDIES["contextual_validation"]
            / "agent_v9_11_validation_run_1/corrected_scoring.json"
        ).read_text(encoding="utf-8")
    )
    exact = validation["contextual_agent"]["causal_exact_set_accuracy"]
    recorded: dict[str, dict[str, Any]] = {
        "contextual_dev": {
            "source": "agent_v9_11_dev_confirmation_2 (prompt v0.3-s1-planner-9.11)",
            "correct_case_ids": sorted(dev_correct),
        },
        "contextual_validation": {
            "source": "agent_v9_11_validation_run_1 corrected scoring (prompt v9.11)",
            "correct": exact["numerator"],
            "scored": exact["denominator"],
        },
    }
    for family in ("t1", "t2"):
        ids: list[str] = []
        for path in sorted((root / _INCREMENT / "runs/heldout_h1/cases").glob(f"held-{family}-*.json")):
            row = json.loads(path.read_text(encoding="utf-8"))
            agent = next(arm for arm in row["arms"] if arm["arm"] == "agent")
            if agent["conclusion_correct"]:
                ids.append(row["case_id"])
        recorded[f"increment_heldout_{family}"] = {
            "source": "study_s1_agent_increment_1 runs/heldout_h1 agent arm (prompt v9.15)",
            "correct_case_ids": sorted(ids),
        }
    return recorded


async def build_report(root: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for case in engine_cases(root):
        result = await run_engine(
            case.load_test(),
            case.load_reference() if case.load_reference else None,
            mode=case.mode,
            nominal_fundamental_hz=case.nominal_fundamental_hz,
        )
        outcome = result.diagnosis.outcome if result.diagnosis else None
        faults = _faults(result)
        rows.append(
            {
                "group": case.group,
                "case_id": case.case_id,
                "mode": case.mode,
                "scoreable": case.scoreable,
                "status": result.status,
                "termination_reason": result.termination_reason,
                "truth_outcome": case.truth_outcome,
                "truth_causal": list(case.truth_causal),
                "engine_outcome": outcome,
                "engine_faults": list(faults),
                "engine_correct": correct(case, outcome, faults),
            }
        )
    recorded = _recorded_planner(root)
    sets: dict[str, dict[str, Any]] = {}
    for group in dict.fromkeys(row["group"] for row in rows):
        scored = [row for row in rows if row["group"] == group and row["scoreable"]]
        entry: dict[str, Any] = {
            "scored": len(scored),
            "engine_correct": sum(row["engine_correct"] for row in scored),
            "runs": sum(1 for row in rows if row["group"] == group),
            "errors": sum(
                1 for row in rows if row["group"] == group and row["engine_outcome"] is None
            ),
        }
        planner = recorded.get(group)
        if planner is not None:
            entry["planner_source"] = planner["source"]
            if "correct_case_ids" in planner:
                ids = set(planner["correct_case_ids"])
                entry["planner_correct"] = sum(row["case_id"] in ids for row in scored)
                entry["engine_only_wrong"] = sorted(
                    row["case_id"]
                    for row in scored
                    if not row["engine_correct"] and row["case_id"] in ids
                )
                entry["planner_only_wrong"] = sorted(
                    row["case_id"]
                    for row in scored
                    if row["engine_correct"] and row["case_id"] not in ids
                )
            else:
                entry["planner_correct"] = planner["correct"]
            entry["engine_not_worse"] = entry["engine_correct"] >= entry["planner_correct"]
        if group.startswith("v02_"):
            entry["note"] = _V02_NOTE
        sets[group] = entry
    return {
        "schema": REPORT_SCHEMA,
        "engine_version": ENGINE_VERSION,
        "model_calls": 0,
        "known_limitations": KNOWN_LIMITATIONS,
        "sets": sets,
        "rows": rows,
    }


def render(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    report = asyncio.run(build_report(args.root))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(report), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["KNOWN_LIMITATIONS", "EngineCase", "build_report", "correct", "engine_cases", "main", "render", "run_engine"]
