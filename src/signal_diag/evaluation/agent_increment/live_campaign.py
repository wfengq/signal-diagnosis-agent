"""Batch driver for the live agent-increment stages (D1 dev, H1 held-out).

Fixed arms reuse the offline implementation and never call a model. The agent
arm runs ``run_live_agent`` per case under one stage ledger. A cap stop ends the
whole stage; completed cases are kept and the report is marked incomplete.
Nothing here writes audio, credentials or raw provider payloads.
"""

from __future__ import annotations

import hashlib
import json
import platform
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from signal_diag.agent import intake as intake_module
from signal_diag.agent.intake import INTAKE_PLANNER_IDENTITY, IntakePlannerError
from signal_diag.agent.models import AgentRunResult
from signal_diag.agent.prompts_v03 import _S1_PROMPT_V9_12
from signal_diag.evaluation.agent_increment.budget import (
    DEV_STAGE_CAP,
    HELD_OUT_STAGE_CAP,
    PER_CASE_CAP,
    CallCapStop,
    CallLedger,
)
from signal_diag.evaluation.agent_increment.campaign import write_report
from signal_diag.evaluation.agent_increment.cases import STUDY_ID
from signal_diag.evaluation.agent_increment.live import (
    LiveAgentResult,
    require_live_credentials,
    run_live_agent,
)
from signal_diag.evaluation.agent_increment.models import (
    ArmOutcome,
    IncrementCase,
    Split,
)
from signal_diag.evaluation.agent_increment.offline import (
    _context_grade,
    _repo_root,
    _truth_draft,
    fault_localized,
    fixed_arm_outcomes,
    load_study_cases,
)
from signal_diag.evaluation.agent_increment.scoring import FamilyScore, score_family
from signal_diag.evaluation.agent_increment.segment_support import SegmentSupport
from signal_diag.signal.models import TimeRange
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.signal.wav import load_wav_bytes

PROMPT_FREEZE_RECORD = "prompt_freeze_record.json"
RUNS_DIR = "runs"
_POSITIVE = ("clipping", "harmonic_distortion")
_CLEAN = {"no_supported_fault", "inconclusive"}


# Every live diagnosis run gets this one request instead of the case text.
# Case texts correlate with the label (e.g. "整段听着平稳" on every held-out T2
# no-fault case, "听不出失真" on T1 no-fault cases), and the fixed arms never
# read text. The T1 intake still reads the case text: that is the T1 task.
DIAGNOSIS_REQUEST = "请诊断这段测试信号是否存在失真；如有，说明类型，以及出现在哪个时间段和哪个声道。"
T2_NEUTRAL_REQUEST = DIAGNOSIS_REQUEST  # kept for readers of earlier notes


class CampaignRefused(RuntimeError):
    """A precondition for a live stage is not met; nothing was sent."""


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def frozen_prompt_identity() -> dict[str, str]:
    """Versions and full-text hashes of every fixed text a live stage sends."""
    return {
        "planner_prompt_version": _S1_PROMPT_V9_12.version,
        "planner_prompt_sha256": _sha256_text(_S1_PROMPT_V9_12.system_prompt),
        "intake_identity": INTAKE_PLANNER_IDENTITY,
        "intake_prompt_sha256": _sha256_text(intake_module._SYSTEM_PROMPT),
        "diagnosis_request_sha256": _sha256_text(DIAGNOSIS_REQUEST),
    }


# ---------------------------------------------------------------------------
# agent-arm outcome


def predicted_conclusion(run: AgentRunResult) -> str:
    """Map a diagnosis to the study's conclusion labels; ``failed`` if none."""
    diagnosis = run.diagnosis
    if diagnosis is None:
        return "failed"
    supported = {
        claim.fault_type for claim in diagnosis.claims if claim.fault_type in _POSITIVE
    }
    if diagnosis.outcome == "supported_fault":
        if supported == set(_POSITIVE):
            return "combined"
        if len(supported) == 1:
            return next(iter(supported))
        return "inconclusive"
    return diagnosis.outcome


def _traceable(run: AgentRunResult) -> bool:
    if run.diagnosis is None:
        return True
    evidence_ids = {item.evidence_id for item in run.evidence}
    evaluation_ids = {
        evaluation.evaluation_id
        for batch in run.rule_evaluation_batches
        for evaluation in batch.evaluations
    }
    for claim in run.diagnosis.claims:
        if claim.fault_type in _POSITIVE and not claim.evidence_refs:
            return False
        if any(ref not in evidence_ids for ref in claim.evidence_refs):
            return False
        if any(ref not in evaluation_ids for ref in claim.rule_refs):
            return False
    return True


def _covers_whole_file(span: TimeRange | None, duration_s: float | None) -> bool:
    if span is None:
        return True
    if duration_s is None:
        return False
    end = span.end_s if span.end_s is not None else duration_s
    return span.start_s <= 1e-9 and end >= duration_s - 1e-6


def cited_supports(
    run: AgentRunResult, *, duration_s: float | None = None
) -> tuple[SegmentSupport, ...]:
    """Positive claims located by the Evidence they cite (time range, channel).

    Evidence over the whole file (no range, or a range spanning the file) is
    kept with ``time_range=None`` so it never counts as localized.
    """
    if run.diagnosis is None or run.diagnosis.outcome != "supported_fault":
        return ()
    by_id = {item.evidence_id: item for item in run.evidence}
    found: list[SegmentSupport] = []
    for claim in run.diagnosis.claims:
        if claim.fault_type not in _POSITIVE:
            continue
        for ref in claim.evidence_refs:
            evidence = by_id.get(ref)
            if evidence is None:
                continue
            found.append(
                SegmentSupport(
                    fault=claim.fault_type,  # type: ignore[arg-type]
                    time_range=(
                        None
                        if _covers_whole_file(evidence.time_range, duration_s)
                        else evidence.time_range
                    ),
                    channel=evidence.channel,
                    evidence_id=evidence.evidence_id,
                    evaluation_id=claim.rule_refs[0] if claim.rule_refs else "",
                )
            )
    return tuple(found)


def live_outcome(
    case: IncrementCase,
    result: LiveAgentResult | None,
    *,
    duration_s: float | None = None,
) -> ArmOutcome:
    """Agent-arm row. ``result`` is None when the intake draft failed closed.

    Correctness and unsupported-claim rules match the offline rows of the same
    family, so all three arms are scored by one definition.
    """
    run = result.run if result is not None else None
    predicted = predicted_conclusion(run) if run is not None else "failed"
    positive = predicted in {"clipping", "harmonic_distortion", "combined"}
    clean = case.truth.conclusion in _CLEAN
    if case.family == "T1":
        draft = result.draft if result is not None else None
        if draft is not None:
            correct, graded, all_match = _context_grade(draft, case.truth)
        else:
            correct, graded, all_match = 0, 4, False
        return ArmOutcome(
            case_id=case.case_id,
            family="T1",
            arm="agent",
            conclusion_correct=predicted == case.truth.conclusion,
            unsupported_positive=positive and clean,
            evidence_traceable=_traceable(run) if run is not None else True,
            context_fields_correct=correct,
            context_fields_graded=graded,
            correction_count=result.correction_count if result is not None else 0,
            draft_all_correct=all_match,
            localization_correct=None,
            tool_calls=len(run.tool_history) if run is not None else 0,
        )
    supports = cited_supports(run, duration_s=duration_s) if run is not None else ()
    expected = case.truth.conclusion
    if expected in _CLEAN:
        correct_t2 = not supports
    else:
        correct_t2 = any(item.fault == expected for item in supports)
    return ArmOutcome(
        case_id=case.case_id,
        family="T2",
        arm="agent",
        conclusion_correct=correct_t2,
        unsupported_positive=bool(supports) and expected in _CLEAN,
        evidence_traceable=_traceable(run) if run is not None else True,
        localization_correct=fault_localized(supports, case),
        tool_calls=len(run.tool_history) if run is not None else 0,
    )


# ---------------------------------------------------------------------------
# guards


def freeze_prompts(study_dir: Path, *, approved_by: str, approved_at: str) -> Path:
    """Stage F: record the prompt identity H1 must match. Write-once."""
    if not approved_by.strip() or not approved_at.strip():
        raise ValueError("approved_by and approved_at are required")
    path = study_dir / PROMPT_FREEZE_RECORD
    if path.exists():
        raise CampaignRefused(f"refusing to overwrite {path}")
    payload: dict[str, object] = {
        "study_id": STUDY_ID,
        **frozen_prompt_identity(),
        "approved_by": approved_by,
        "approved_at": approved_at,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def check_heldout_preconditions(study_dir: Path, output_dir: Path) -> None:
    """H1 runs once, under frozen prompts, into ``<study>/runs/heldout_*``."""
    record_path = study_dir / PROMPT_FREEZE_RECORD
    if not record_path.exists():
        raise CampaignRefused("held-out run requires prompt_freeze_record.json (stage F)")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    for key, value in frozen_prompt_identity().items():
        if record.get(key) != value:
            raise CampaignRefused(f"prompt freeze record mismatch: {key}")
    runs = study_dir / RUNS_DIR
    if output_dir.resolve().parent != runs.resolve() or not output_dir.name.startswith(
        "heldout_"
    ):
        raise CampaignRefused("held-out output must be <study>/runs/heldout_<label>")
    if runs.exists() and any(
        child.name.startswith("heldout_") for child in runs.iterdir()
    ):
        raise CampaignRefused("a held-out run already exists; H1 runs once")


def _check_output_dir(output_dir: Path) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise CampaignRefused(f"output directory is not empty: {output_dir}")


def default_output_dir(study_dir: Path, split: Split, now: datetime) -> Path:
    stamp = now.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    return study_dir / RUNS_DIR / f"{split}_{stamp}"


# ---------------------------------------------------------------------------
# driver


def _load_case_signals(
    study_dir: Path, case: IncrementCase
) -> tuple[InMemorySignalRepository, str, dict[str, str]]:
    repository = InMemorySignalRepository()
    by_name: dict[str, str] = {}
    root = _repo_root(study_dir)
    for rel in case.files:
        path = root / rel
        record = load_wav_bytes(path.read_bytes(), filename=path.name).record
        repository.put(record)
        by_name[path.name] = record.meta.signal_id
    if case.test_file not in by_name:
        raise ValueError(f"{case.case_id}: test_file is not among the case files")
    return repository, by_name[case.test_file], by_name


def _case_record(
    case: IncrementCase,
    rows: list[ArmOutcome],
    result: LiveAgentResult | None,
    *,
    http_calls: int,
    agent_error: str | None,
    duration_s: float | None = None,
) -> dict[str, object]:
    run = result.run if result is not None else None
    record: dict[str, object] = {
        "case_id": case.case_id,
        "family": case.family,
        "split": case.split,
        "arms": [row.model_dump(mode="json") for row in rows],
        "http_calls": http_calls,
        "agent_error": agent_error,
        "predicted_conclusion": predicted_conclusion(run) if run is not None else "failed",
        "termination_reason": run.termination_reason if run is not None else None,
        "run_status": run.status if run is not None else None,
        "tool_history": (
            [entry.model_dump(mode="json") for entry in run.tool_history]
            if run is not None
            else []
        ),
        "claims": (
            [claim.model_dump(mode="json") for claim in run.diagnosis.claims]
            if run is not None and run.diagnosis is not None
            else []
        ),
        "cited_locations": [
            item.model_dump(mode="json")
            for item in (cited_supports(run, duration_s=duration_s) if run else ())
        ],
    }
    if result is not None and case.family == "T1":
        record["draft"] = result.draft.model_dump(mode="json") if result.draft else None
        record["confirmed"] = (
            result.confirmed.model_dump(mode="json") if result.confirmed else None
        )
        record["correction_count"] = result.correction_count
        record["context_downgraded"] = result.context_downgraded
    return record


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise CampaignRefused(f"refusing to overwrite {path}")
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _identity(study_dir: Path, split: Split, model: str, stage_cap: int) -> dict[str, object]:
    from signal_diag.evaluation.contextual.calibration import (
        contextual_product_tree_sha256,
    )

    manifest_sha = (study_dir / "manifest.sha256").read_text(encoding="utf-8").strip()
    return {
        "study_id": STUDY_ID,
        "split": split,
        "model": model,
        **frozen_prompt_identity(),
        "product_tree_sha256": contextual_product_tree_sha256(),
        "manifest_sha256": manifest_sha,
        "per_case_cap": PER_CASE_CAP,
        "stage_cap": stage_cap,
        "python_version": platform.python_version(),
        "scripted_stand_in": False,
    }


async def _close_client(client: Any) -> None:
    close = getattr(client, "close", None)
    if close is None:
        return
    closed = close()
    if hasattr(closed, "__await__"):
        await closed


# Intake errors without a cause that are not the model's draft: harness faults
# raised before a send, and empty provider content.
_INTAKE_HARNESS_ERRORS = (
    "intake payload keys drifted",
    # Empty content is not a draft: in D1 round 1 it came from the request
    # settings, so scoring it would measure the harness, not the model.
    "intake SDK response content must be non-empty text",
)



def _intake_transport_failure(error: IntakePlannerError) -> bool:
    """True when the intake failed outside the model's answer: an outage or a harness fault.

    Scored as the model's answer: a draft that does not parse (pydantic or value
    error) or fails validation. Everything else stops the stage: a transport or
    malformed-response cause, empty response content, or a harness-side error.
    """
    cause = error.__cause__
    if cause is None:
        return str(error) in _INTAKE_HARNESS_ERRORS
    return not isinstance(cause, (ValidationError, ValueError))


def _report_payload(
    *,
    split: Split,
    stop: dict[str, object] | None,
    cases: list[IncrementCase],
    completed: list[str],
    outcomes: list[ArmOutcome],
    ledger: CallLedger,
    finished_at: str,
) -> dict[str, object]:
    families: list[FamilyScore] = []
    for family in ("T1", "T2"):
        rows = [row for row in outcomes if row.family == family]
        if rows:
            families.append(score_family(rows))
    return {
        "study_id": STUDY_ID,
        "split": split,
        "incomplete": not (stop is None and len(completed) == len(cases)),
        "stop": stop,
        "cases_planned": len(cases),
        "cases_completed": len(completed),
        "http_calls": ledger.total,
        "families": [item.model_dump(mode="json") for item in families],
        "notes": {
            "t1_primary_metric": "first-draft context fields, before any correction",
            "t1_downstream_fixed_arms": (
                "scripted stand-in judge, not the live planner; the downstream "
                "increment mixes intake context with diagnosis engine and is not "
                "a paired comparison"
            ),
            "diagnosis_request": DIAGNOSIS_REQUEST,
            "localization": "whole-file analysis never counts as localized, for every arm",
        },
        "finished_at": finished_at,
    }


class _PreparedCase:
    """Everything a case needs before any send: fixed rows and decoded signals."""

    def __init__(self, study_dir: Path, case: IncrementCase) -> None:
        self.case = case
        self.fixed_rows = fixed_arm_outcomes(study_dir, case)
        self.repository, self.signal_id, self.by_name = _load_case_signals(study_dir, case)
        self.duration_s = self.repository.get(self.signal_id).meta.duration_s


async def run_campaign(
    *,
    split: Split,
    study_dir: Path,
    output_dir: Path,
    api_key: str | None,
    client_factory: Callable[[], Any],
    model: str = "deepseek-v4-flash",
    base_url: str | None = "https://api.deepseek.com",
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> dict[str, object]:
    """Run one live stage. Fixed arms are deterministic; only the agent arm sends.

    Every precondition, every case's decoded audio and fixed-arm rows, the
    identity and the client are settled before the output directory is
    created, so a setup failure leaves nothing behind and cannot use up the
    single held-out run. Once the directory exists, the ledger and a report are
    always written, and a write problem never replaces the original error.
    """
    key = require_live_credentials(api_key)
    if split == "heldout":
        check_heldout_preconditions(study_dir, output_dir)
    elif output_dir.name.startswith("heldout_"):
        raise CampaignRefused("a dev run must not use a heldout_ output name")
    _check_output_dir(output_dir)
    stage_cap = DEV_STAGE_CAP if split == "dev" else HELD_OUT_STAGE_CAP
    cases = [case for case in load_study_cases(study_dir) if case.split == split]
    root = _repo_root(study_dir)
    missing = [rel for case in cases for rel in case.files if not (root / rel).is_file()]
    if missing:
        raise CampaignRefused(f"case files missing before any send: {missing[:3]}")
    prepared = [_PreparedCase(study_dir, case) for case in cases]
    identity = _identity(study_dir, split, model, stage_cap)
    identity["started_at"] = now().isoformat()
    client = client_factory()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        ledger = CallLedger(stage_cap=stage_cap, output_dir=output_dir)
    except BaseException:
        await _close_client(client)
        raise
    outcomes: list[ArmOutcome] = []
    completed: list[str] = []
    stop: dict[str, object] | None = None
    failed = False
    try:
        _write_json(output_dir / "identity.json", identity)
        for item in prepared:
            case = item.case
            result: LiveAgentResult | None = None
            agent_error: str | None = None
            try:
                result = await run_live_agent(
                    family=case.family,
                    case_id=case.case_id,
                    ledger=ledger,
                    api_key=key,
                    repository=item.repository,
                    signal_id=item.signal_id,
                    user_text=case.text,
                    truth=_truth_draft(case.truth) if case.family == "T1" else None,
                    filenames=tuple(item.by_name),
                    test_file=case.test_file,
                    client=client,
                    base_url=base_url,
                    model=model,
                    signal_ids_by_filename=item.by_name,
                    diagnosis_request=DIAGNOSIS_REQUEST,
                )
            except CallCapStop:
                pass
            except IntakePlannerError as error:
                if ledger.stop_reason is not None:
                    pass  # a cap stop wrapped by the intake planner; handled below
                elif _intake_transport_failure(error):
                    cause = error.__cause__
                    stop = {
                        "reason": "infrastructure_error",
                        "case_id": case.case_id,
                        "error_type": type(cause if cause is not None else error).__name__,
                    }
                    break
                else:
                    agent_error = f"intake_failed: {error}"
            except Exception as error:  # noqa: BLE001 - any other failure is an outage: stop, never score it
                if ledger.stop_reason is None:
                    stop = {
                        "reason": "infrastructure_error",
                        "case_id": case.case_id,
                        "error_type": type(error).__name__,
                    }
                    break
                # otherwise a cap stop arrived wrapped in another type; handled below
            if ledger.stop_reason is not None:
                stop = {"reason": ledger.stop_reason, "case_id": case.case_id}
                break
            agent_row = live_outcome(case, result, duration_s=item.duration_s)
            case_rows = [agent_row, *item.fixed_rows]
            outcomes.extend(case_rows)
            completed.append(case.case_id)
            _write_json(
                output_dir / "cases" / f"{case.case_id}.json",
                _case_record(
                    case,
                    case_rows,
                    result,
                    http_calls=ledger.per_case.get(case.case_id, 0),
                    agent_error=agent_error,
                    duration_s=item.duration_s,
                ),
            )
    except BaseException as error:
        failed = True
        if ledger.stop_reason is None:
            stop = {"reason": "aborted", "error_type": type(error).__name__}
        raise
    finally:
        write_error: Exception | None = None
        try:
            await _close_client(client)
        except Exception as error:  # noqa: BLE001 - keep the audit trail; never mask the original error
            write_error = error
        try:
            payload = _report_payload(
                split=split,
                stop=stop,
                cases=cases,
                completed=completed,
                outcomes=outcomes,
                ledger=ledger,
                finished_at=now().isoformat(),
            )
        except Exception as error:  # noqa: BLE001 - fall back to a minimal report
            write_error = write_error or error
            payload = {
                "study_id": STUDY_ID,
                "split": split,
                "incomplete": True,
                "stop": stop,
                "cases_completed": len(completed),
                "http_calls": ledger.total,
                "report_error": type(error).__name__,
            }
        writes: list[tuple[Path, object]] = [
            (
                output_dir / "ledger.json",
                {"total": ledger.total, "per_case": dict(sorted(ledger.per_case.items()))},
            ),
        ]
        stop_path = output_dir / "stop_record.json"
        if stop is not None and not stop_path.exists():
            writes.append((stop_path, stop))
        for path, content in writes:
            try:
                _write_json(path, content)
            except Exception as error:  # noqa: BLE001 - keep writing; never mask the original error
                write_error = write_error or error
        try:
            write_report(output_dir, payload)
        except Exception as error:  # noqa: BLE001 - same as above
            write_error = write_error or error
        if write_error is not None and not failed:
            raise write_error
    return payload


def build_live_sdk_client(*, api_key: str, base_url: str | None) -> Any:
    """Real SDK client for a live stage: retries off so every send is reserved."""
    key = require_live_credentials(api_key)
    from openai import AsyncOpenAI

    return AsyncOpenAI(api_key=key, base_url=base_url, max_retries=0)
