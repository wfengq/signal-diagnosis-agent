"""T-CX400–T-CX404: batch driver for the live agent-increment stages.

Every test uses a fake SDK; nothing opens a network connection.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from signal_diag.agent.intake import ConfirmedContext
from signal_diag.agent.models import (
    AgentRunResult,
    DiagnosisClaim,
    StructuredDiagnosis,
)
from signal_diag.evaluation.agent_increment import __main__ as increment_main
from signal_diag.evaluation.agent_increment import live_campaign
from signal_diag.evaluation.agent_increment.live import (
    LiveAgentResult,
    ReservingChatClient,
    confirmed_stimulus,
)
from signal_diag.evaluation.agent_increment.live_campaign import (
    CampaignRefused,
    check_heldout_preconditions,
    cited_supports,
    freeze_prompts,
    live_outcome,
    predicted_conclusion,
    run_campaign,
)
from signal_diag.evaluation.agent_increment.models import IncrementCase
from signal_diag.evaluation.agent_increment.offline import load_study_cases
from signal_diag.signal.models import TimeRange
from signal_diag.tools.evidence import Evidence

REPO_ROOT = Path(__file__).resolve().parents[3]
STUDY_REL = Path("docs/evaluations/v0_3/agent_increment/study_s1_agent_increment_1")
STUDY = REPO_ROOT / STUDY_REL

_INTAKE_DRAFT = {
    "mode": "single_signal",
    "nominal_fundamental_hz": None,
    "reference_file": None,
    "stimulus_kind": None,
    "missing_fields": [],
    "questions": [],
}
_TOOL = {
    "decision_type": "call_tool",
    "task_assessment": {"task_type": "distortion_analysis", "objective": "inspect clipping"},
    "call": {"tool_name": "detect_clipping", "args": {}},
    "purpose": "check clipping evidence",
}
_FINISH = {
    "decision_type": "finish",
    "task_assessment": {"task_type": "distortion_analysis", "objective": "diagnose"},
    "outcome": "inconclusive",
    "claims": [],
    "confidence_label": "low",
    "limitations": ["fake sdk"],
}


class _Message:
    def __init__(self, content: str) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str) -> None:
        self.message = _Message(content)


class _Response:
    def __init__(self, content: str) -> None:
        self.choices = [_Choice(content)]


class _Completions:
    def __init__(self, sdk: FakeSDK) -> None:
        self._sdk = sdk

    async def create(self, **kwargs: Any) -> _Response:
        return await self._sdk.reply(**kwargs)


class _Chat:
    def __init__(self, sdk: FakeSDK) -> None:
        self.completions = _Completions(sdk)


class FakeSDK:
    """Shaped like the real SDK: ``create`` lives only at chat.completions."""

    max_retries = 0

    def __init__(self, *, fail_after: int | None = None) -> None:
        self.chat = _Chat(self)
        self.sends = 0
        self.fail_after = fail_after
        self.planner_turns: dict[int, int] = {}
        self.closed = False

    async def reply(self, **kwargs: Any) -> _Response:
        self.sends += 1
        if self.fail_after is not None and self.sends > self.fail_after:
            raise ConnectionError("fake transport down")
        system = str(kwargs["messages"][0]["content"])
        if "v0.3-s1-planner" not in system:
            return _Response(json.dumps(_INTAKE_DRAFT))
        # One tool call, then an inconclusive finish, per diagnosis run.
        key = id(kwargs["messages"])
        turn = self.planner_turns.get(key, 0)
        self.planner_turns[key] = turn + 1
        user = str(kwargs["messages"][-1]["content"])
        if '"tool_history":[]' in user.replace(" ", ""):
            return _Response(json.dumps(_TOOL))
        return _Response(json.dumps(_FINISH))

    async def close(self) -> None:
        self.closed = True


def _mini_study(tmp_path: Path, count_per_family: int = 1, split: str = "dev") -> Path:
    """Copy a few manifest cases and their WAVs under a tmp repo root."""
    cases = load_study_cases(STUDY)
    chosen: list[IncrementCase] = []
    for family in ("T1", "T2"):
        picked = [c for c in cases if c.family == family and c.split == split]
        chosen.extend(picked[:count_per_family])
    root = tmp_path / "repo"
    study = root / STUDY_REL
    study.mkdir(parents=True)
    for case in chosen:
        for rel in case.files:
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO_ROOT / rel, target)
    (study / "manifest.json").write_text(
        json.dumps({"cases": [c.model_dump(mode="json") for c in chosen]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (study / "manifest.sha256").write_text("0" * 64 + "\n", encoding="utf-8")
    return study


def _all_text(directory: Path) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(directory.rglob("*.json"))
    )


# ---------------------------------------------------------------------------
# T-CX400


def _evidence(evidence_id: str, *, start: float | None, channel: str = "mixdown") -> Evidence:
    span = None if start is None else TimeRange(start_s=start, end_s=start + 0.25)
    return Evidence.model_construct(
        evidence_id=evidence_id,
        source_tool="detect_clipping",
        call_id="call_x",
        metric="clipping_ratio",
        value=0.2,
        time_range=span,
        channel=channel,
    )


def _run(outcome: str, claims: list[DiagnosisClaim], evidence: list[Evidence]) -> AgentRunResult:
    diagnosis = StructuredDiagnosis.model_construct(
        run_id="run_x",
        outcome=outcome,
        claims=tuple(claims),
        termination_reason="planner_finished",
    )
    return AgentRunResult.model_construct(
        run_id="run_x",
        status="success",
        diagnosis=diagnosis,
        observations=(),
        evidence=tuple(evidence),
        tool_history=(),
        termination_reason="planner_finished",
        rule_evaluation_batches=(),
    )


def _claim(fault: str, refs: tuple[str, ...]) -> DiagnosisClaim:
    return DiagnosisClaim.model_construct(
        claim_id="claim_x",
        fault_type=fault,
        statement="s",
        evidence_refs=refs,
        rule_refs=(),
        knowledge_refs=(),
    )


def test_t_cx400_predicted_conclusion_maps_claims() -> None:
    both = _run(
        "supported_fault",
        [_claim("clipping", ("ev_a",)), _claim("harmonic_distortion", ("ev_a",))],
        [_evidence("ev_a", start=0.0)],
    )
    assert predicted_conclusion(both) == "combined"
    assert predicted_conclusion(_run("no_supported_fault", [], [])) == "no_supported_fault"
    failed = AgentRunResult.model_construct(diagnosis=None)
    assert predicted_conclusion(failed) == "failed"


def test_t_cx400_t2_location_comes_from_cited_evidence() -> None:
    case = next(
        c
        for c in load_study_cases(STUDY)
        if c.family == "T2" and c.truth.fault_spans and c.truth.conclusion == "clipping"
    )
    span = case.truth.fault_spans[0]
    inside = _run(
        "supported_fault",
        [_claim("clipping", ("ev_in",))],
        [_evidence("ev_in", start=span.start_s, channel=span.channel)],
    )
    whole_file = _run(
        "supported_fault",
        [_claim("clipping", ("ev_all",))],
        [_evidence("ev_all", start=None, channel=span.channel)],
    )
    for run, located in ((inside, True), (whole_file, False)):
        result = LiveAgentResult.model_construct(family="T2", run=run, correction_count=0)
        row = live_outcome(case, result)
        assert row.conclusion_correct is True
        assert row.localization_correct is located
    assert cited_supports(inside)[0].time_range is not None


def test_t_cx400_failed_intake_scores_as_wrong_without_unsupported_claim() -> None:
    case = next(c for c in load_study_cases(STUDY) if c.family == "T1")
    row = live_outcome(case, None)
    assert row.conclusion_correct is False
    assert row.draft_all_correct is False
    assert row.unsupported_positive is False
    assert row.context_fields_graded == 4


def test_t_cx400_reference_only_from_confirmed_upload() -> None:
    names = {"test.wav": "sig_t", "ref.wav": "sig_r"}
    paired = ConfirmedContext(mode="paired_reference", reference_file="ref.wav")
    stimulus, downgraded = confirmed_stimulus(
        signal_id="sig_t", confirmed=paired, signal_ids_by_filename=names
    )
    assert stimulus.reference_signal_id == "sig_r" and downgraded is False
    unconfirmed = ConfirmedContext(mode="paired_reference", reference_file=None)
    stimulus, downgraded = confirmed_stimulus(
        signal_id="sig_t", confirmed=unconfirmed, signal_ids_by_filename=names
    )
    assert stimulus.mode == "single_signal" and downgraded is True
    nominal_missing = ConfirmedContext(mode="nominal_single_tone", stimulus_kind="single_tone")
    stimulus, downgraded = confirmed_stimulus(
        signal_id="sig_t", confirmed=nominal_missing, signal_ids_by_filename=names
    )
    assert stimulus.mode == "single_signal" and downgraded is True


@pytest.mark.asyncio
async def test_t_cx400_reserving_client_calls_sdk_chat_completions() -> None:
    from signal_diag.evaluation.agent_increment.budget import CallLedger

    sdk = FakeSDK()
    ledger = CallLedger(stage_cap=5, output_dir=Path("/tmp/unused-ledger-dir-t-cx400"))
    guarded = ReservingChatClient(sdk, ledger, "case")
    await guarded.chat.completions.create(
        model="m", messages=[{"role": "system", "content": "x"}, {"role": "user", "content": "y"}]
    )
    assert sdk.sends == 1 and ledger.total == 1


# ---------------------------------------------------------------------------
# T-CX401


@pytest.mark.asyncio
async def test_t_cx404_mini_dev_stage_runs_all_arms_and_writes_once(tmp_path: Path) -> None:
    study = _mini_study(tmp_path)
    out = study / "runs" / "dev_test"
    sdk = FakeSDK()
    payload = await run_campaign(
        split="dev",
        study_dir=study,
        output_dir=out,
        api_key="sk-test",
        client_factory=lambda: sdk,
    )
    assert payload["incomplete"] is False
    assert payload["cases_completed"] == payload["cases_planned"] == 2
    assert payload["http_calls"] == sdk.sends > 0
    assert sdk.closed is True
    ledger = json.loads((out / "ledger.json").read_text(encoding="utf-8"))
    assert ledger["total"] == sdk.sends
    for case_file in sorted((out / "cases").glob("*.json")):
        record = json.loads(case_file.read_text(encoding="utf-8"))
        assert {row["arm"] for row in record["arms"]} == {"agent", "strong_fixed", "weak_fixed"}
        assert record["http_calls"] >= 1
    identity = json.loads((out / "identity.json").read_text(encoding="utf-8"))
    assert identity["planner_prompt_version"] == "v0.3-s1-planner-9.12"
    assert identity["scripted_stand_in"] is False
    text = _all_text(out)
    assert "sk-test" not in text
    assert "RIFF" not in text
    assert "messages" not in text
    with pytest.raises(CampaignRefused, match="not empty"):
        await run_campaign(
            split="dev",
            study_dir=study,
            output_dir=out,
            api_key="sk-test",
            client_factory=FakeSDK,
        )


@pytest.mark.asyncio
async def test_t_cx401_stage_cap_stops_whole_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    study = _mini_study(tmp_path)
    monkeypatch.setattr(live_campaign, "DEV_STAGE_CAP", 2)
    out = study / "runs" / "dev_cap"
    sdk = FakeSDK()
    payload = await run_campaign(
        split="dev", study_dir=study, output_dir=out, api_key="sk-test", client_factory=lambda: sdk
    )
    assert payload["incomplete"] is True
    assert payload["stop"]["reason"] == "stage_cap"
    assert sdk.sends == 2
    assert payload["cases_completed"] == 0
    stop = json.loads((out / "stop_record.json").read_text(encoding="utf-8"))
    assert stop["reason"] == "stage_cap"
    assert not (out / "cases").exists()


@pytest.mark.asyncio
async def test_t_cx401_cap_hit_during_intake_is_a_cap_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    study = _mini_study(tmp_path, count_per_family=2)
    monkeypatch.setattr(live_campaign, "DEV_STAGE_CAP", 3)
    out = study / "runs" / "dev_cap_intake"
    sdk = FakeSDK()
    payload = await run_campaign(
        split="dev", study_dir=study, output_dir=out, api_key="sk-test", client_factory=lambda: sdk
    )
    # dev-t1-00 uses 3 sends; the next case (T1) hits the cap at its intake call.
    assert payload["cases_completed"] == 1
    assert payload["stop"] == {"reason": "stage_cap", "case_id": "dev-t1-01"}
    assert sdk.sends == 3


@pytest.mark.asyncio
async def test_t_cx401_transport_failure_stops_instead_of_scoring(tmp_path: Path) -> None:
    study = _mini_study(tmp_path)
    out = study / "runs" / "dev_down"
    sdk = FakeSDK(fail_after=0)
    payload = await run_campaign(
        split="dev", study_dir=study, output_dir=out, api_key="sk-test", client_factory=lambda: sdk
    )
    assert payload["incomplete"] is True
    assert payload["cases_completed"] == 0
    assert payload["stop"]["reason"] == "infrastructure_error"
    assert payload["stop"]["error_type"] == "ConnectionError"
    assert not (out / "cases").exists()
    stop = json.loads((out / "stop_record.json").read_text(encoding="utf-8"))
    assert stop["reason"] == "infrastructure_error"


@pytest.mark.asyncio
async def test_t_cx401_invalid_intake_draft_is_scored_not_stopped(tmp_path: Path) -> None:
    study = _mini_study(tmp_path)
    out = study / "runs" / "dev_bad_draft"

    class BadDraftSDK(FakeSDK):
        async def reply(self, **kwargs: Any) -> _Response:
            system = str(kwargs["messages"][0]["content"])
            if "v0.3-s1-planner" not in system:
                self.sends += 1
                # 999 Hz is not written in any case text: validation must reject it.
                bad = dict(_INTAKE_DRAFT, mode="nominal_single_tone", nominal_fundamental_hz=999.0)
                return _Response(json.dumps(bad))
            return await super().reply(**kwargs)

    sdk = BadDraftSDK()
    payload = await run_campaign(
        split="dev", study_dir=study, output_dir=out, api_key="sk-test", client_factory=lambda: sdk
    )
    assert payload["stop"] is None and payload["incomplete"] is False
    t1 = next(
        json.loads(path.read_text(encoding="utf-8"))
        for path in (out / "cases").glob("*.json")
        if json.loads(path.read_text(encoding="utf-8"))["family"] == "T1"
    )
    assert t1["agent_error"].startswith("intake_failed")
    agent = next(row for row in t1["arms"] if row["arm"] == "agent")
    assert agent["conclusion_correct"] is False and agent["draft_all_correct"] is False


# ---------------------------------------------------------------------------
# T-CX402


def test_t_cx402_heldout_requires_matching_freeze_and_runs_once(tmp_path: Path) -> None:
    study = _mini_study(tmp_path, split="heldout")
    out = study / "runs" / "heldout_a"
    with pytest.raises(CampaignRefused, match="prompt_freeze_record"):
        check_heldout_preconditions(study, out)
    freeze_prompts(study, approved_by="tester", approved_at="2026-10-06")
    with pytest.raises(CampaignRefused, match="overwrite"):
        freeze_prompts(study, approved_by="tester", approved_at="2026-10-06")
    check_heldout_preconditions(study, out)
    with pytest.raises(CampaignRefused, match="runs/heldout_"):
        check_heldout_preconditions(study, tmp_path / "elsewhere")
    (study / "runs" / "heldout_earlier").mkdir(parents=True)
    with pytest.raises(CampaignRefused, match="runs once"):
        check_heldout_preconditions(study, out)


def test_t_cx402_freeze_mismatch_is_refused(tmp_path: Path) -> None:
    study = _mini_study(tmp_path, split="heldout")
    path = freeze_prompts(study, approved_by="tester", approved_at="2026-10-06")
    record = json.loads(path.read_text(encoding="utf-8"))
    record["planner_prompt_sha256"] = "0" * 64
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(CampaignRefused, match="planner_prompt_sha256"):
        check_heldout_preconditions(study, study / "runs" / "heldout_a")


# ---------------------------------------------------------------------------
# T-CX403


def test_t_cx403_run_requires_credentials_and_dry_run_is_unchanged(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(Exception, match="does not fall back to ScriptedPlanner"):
        increment_main.main(["--run", "--split", "dev", "--out", str(tmp_path / "o")])
    assert not (tmp_path / "o").exists()
    assert increment_main.main(["--dry-run", "--split", "dev", "--cases", "24"]) == 0
    assert json.loads(capsys.readouterr().out)["max_calls"] == 504
    with pytest.raises(SystemExit):
        increment_main.main(["--dry-run", "--run", "--split", "dev", "--cases", "24"])
