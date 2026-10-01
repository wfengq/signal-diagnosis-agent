"""T-CX294 / T-CX301 / T-CX302: full offline schedule acceptance (dev_2).

Study-only. Executes the 114-slot schedule through Scripted service + fixed
adapters with a fail-on-call provider spy. Does not create a protocol seal,
does not call RealLLM providers, and does not claim live-run readiness.
Synthetic ControlledClock values are harness metadata only — never RealLLM
latency evidence.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from signal_diag.agent.models import (
    AgentDecision,
    FinishDecision,
    PlannerContext,
    TaskAssessment,
)
from signal_diag.agent.planner import PROMPT_VERSION, RealLLMPlanner
from signal_diag.app.models import PlannerIdentity
from signal_diag.app.planner_ablation_v2_adapter import (
    build_fixed_arm_session,
    build_product_arm_session,
)
from signal_diag.app.service import ApplicationDependencies, DiagnosisApplicationService
from signal_diag.evaluation.planner_ablation.v2.campaign import (
    inspect_limits,
    run_schedule,
    snapshot_effective_configuration,
)
from signal_diag.evaluation.planner_ablation.v2.labels import validate_labels
from signal_diag.evaluation.planner_ablation.v2.models import (
    SLOT_COUNT_V2,
    STUDY_ID_V2,
    CampaignRecord,
    ScenarioDefinition,
    SlotKey,
    StudyProtocolV2,
)
from signal_diag.evaluation.planner_ablation.v2.population import (
    build_schedule,
    load_proposed_scenarios,
)
from signal_diag.evaluation.planner_ablation.v2.provenance import (
    ProvenanceRejection,
    assert_harness_only_provenance,
    campaign_bundle_digest,
    reject_relabeled_harness_terminal,
    terminal_to_scored_record,
    validate_scored_product_ingestion,
    verify_campaign_bundle_binding,
)
from signal_diag.evaluation.planner_ablation.v2.timing import ControlledClock
from signal_diag.knowledge.index import KnowledgeIndex
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal import InMemorySignalRepository

REPO_ROOT = Path(__file__).resolve().parents[4]
PROFILE_PATH = REPO_ROOT / "src/signal_diag/rules/profiles/s1_distortion_v1.yaml"
CONTEXTUAL_PROFILE_PATH = (
    REPO_ROOT / "src/signal_diag/rules/profiles/s1_contextual_comparison_v9_10.yaml"
)
CORPUS_PATH = REPO_ROOT / "src/signal_diag/knowledge/corpus"
NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
_ASSESSMENT = TaskAssessment(
    task_type="distortion_analysis",
    objective="determine why the signal sounds distorted",
    hypotheses=("clipping", "harmonic_distortion"),
)
_PHASE_ADVANCES = {"decode": 0.001, "execution": 0.001, "guidance": 0.001}
_INCONCLUSIVE = FinishDecision(
    task_assessment=_ASSESSMENT,
    outcome="inconclusive",
    claims=(),
    confidence_label="low",
    limitations=("offline harness Scripted finish",),
)


class FailOnCallProvider:
    """Actual provider-boundary spy: any chat call fails the offline gate."""

    def __init__(self) -> None:
        self.calls = 0

    async def chat(self, *args: object, **kwargs: object) -> object:
        del args, kwargs
        self.calls += 1
        raise AssertionError("provider must not be called during offline acceptance")


class ScriptedFinishPlanner:
    """Harness Scripted-equivalent planner; never touches the provider."""

    def __init__(self, provider: FailOnCallProvider) -> None:
        self._provider = provider

    async def decide(self, context: PlannerContext) -> AgentDecision:
        del context
        assert self._provider.calls == 0
        return _INCONCLUSIVE


class _LegacyTrapService(DiagnosisApplicationService):
    async def submit_wav(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("offline acceptance must not call submit_wav")

    async def wait_for_terminal(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("offline acceptance must not call wait_for_terminal")


def _profile_loader() -> YamlRuleProfileLoader:
    return YamlRuleProfileLoader(
        {
            "profile_s1_distortion": PROFILE_PATH,
            "profile_s1_contextual_comparison_v9_10": CONTEXTUAL_PROFILE_PATH,
        }
    )


def _scripted_service(provider: FailOnCallProvider) -> _LegacyTrapService:
    return _LegacyTrapService(
        ApplicationDependencies(
            repository=InMemorySignalRepository(),
            planner_factory=lambda: ScriptedFinishPlanner(provider),
            planner_identity=PlannerIdentity(
                provider="deepseek",
                model="deepseek-v4-flash",
                prompt_version=PROMPT_VERSION,
                phase4_certified_default=True,
            ),
            planner_configured=True,
            rule_engine=RuleEngine(),
            rule_profile_loader=_profile_loader(),
            knowledge_index=KnowledgeIndex(CORPUS_PATH),
            causal_policy_version="v9_11_mode_aware_no_fault_recovery",
        ),
        clock=lambda: NOW,
    )


async def _run_full_offline_schedule(
    tmp_path: Path,
    provider: FailOnCallProvider,
) -> tuple[CampaignRecord, StudyProtocolV2, object, object]:
    """Execute the entire 114-slot schedule via real Scripted + fixed adapters."""
    protocol = StudyProtocolV2()
    scenarios = load_proposed_scenarios(REPO_ROOT)
    schedule = build_schedule(scenarios, protocol, repository_root=REPO_ROOT)
    assert len(schedule.slots) == SLOT_COUNT_V2

    clock = ControlledClock(start=10.0)
    service = _scripted_service(provider)
    output_dir = tmp_path / "offline_harness_out"
    seen_paths: set[tuple[str, str]] = set()

    async def session_factory(slot: SlotKey) -> Any:
        # Fresh empty container per slot; shared ControlledClock is harness metadata.
        if slot.arm == "product_agent":
            session = build_product_arm_session(
                service,
                clock=clock,
                phase_advances=dict(_PHASE_ADVANCES),
                offline_session=True,
            )
        else:
            session = build_fixed_arm_session(
                profile_loader=_profile_loader(),
                clock=clock,
                phase_advances=dict(_PHASE_ADVANCES),
                offline_session=True,
            )
        # Capture mode via first execute for path accounting — filled after run.
        return session

    # Wrap factory to record arm/mode after we know the request.
    requests = {req.request_key: req for req in schedule.canonical_requests}
    original_factory = session_factory

    async def tracking_factory(slot: SlotKey) -> Any:
        session = await original_factory(slot)
        request = requests[slot.request_key]
        seen_paths.add((slot.arm, request.mode))
        return session

    record = await run_schedule(
        schedule,
        protocol,
        tracking_factory,
        execution_mode="offline",
        clock=clock,
        output_dir=output_dir,
        wall_timeout=False,
    )
    await service.aclose()
    return record, protocol, scenarios, seen_paths


@pytest.fixture
def provider_spy() -> FailOnCallProvider:
    return FailOnCallProvider()


@pytest.fixture(scope="module")
def provider_spy_module() -> FailOnCallProvider:
    return FailOnCallProvider()


@pytest.fixture(scope="module")
async def full_offline_dry_run(
    tmp_path_factory: pytest.TempPathFactory,
    provider_spy_module: FailOnCallProvider,
) -> tuple[
    CampaignRecord,
    StudyProtocolV2,
    tuple[ScenarioDefinition, ...],
    set[tuple[str, str]],
    FailOnCallProvider,
    Path,
]:
    """One shared 114-slot dry-run for offline acceptance assertions."""
    tmp_path = tmp_path_factory.mktemp("offline_acceptance")
    record, protocol, scenarios, seen_paths = await _run_full_offline_schedule(
        tmp_path, provider_spy_module
    )
    return record, protocol, scenarios, seen_paths, provider_spy_module, tmp_path


@pytest.mark.asyncio
async def test_complete_harness_schedule_has_no_provider_calls(
    full_offline_dry_run: tuple[
        CampaignRecord,
        StudyProtocolV2,
        tuple[ScenarioDefinition, ...],
        set[tuple[str, str]],
        FailOnCallProvider,
        Path,
    ],
) -> None:
    record, protocol, scenarios, seen_paths, provider_spy, tmp_path = full_offline_dry_run

    assert record.planned_slot_count == SLOT_COUNT_V2
    assert len(record.slot_records) == SLOT_COUNT_V2
    assert record.status == "completed"
    assert record.unstarted_slot_count == 0
    assert record.attempted_slot_count == SLOT_COUNT_V2
    assert record.execution_mode == "offline"
    assert record.study_id == STUDY_ID_V2
    assert record.campaign_retry_policy == "forbidden"
    assert record.schedule_order_preserved is True

    product = [r for r in record.slot_records if r.slot_key.arm == "product_agent"]
    fixed = [r for r in record.slot_records if r.slot_key.arm == "fixed_pipeline"]
    assert len(product) == 57
    assert len(fixed) == 57

    # All four arm/mode paths exercised.
    assert seen_paths == {
        ("product_agent", "single_signal"),
        ("product_agent", "paired_reference"),
        ("fixed_pipeline", "single_signal"),
        ("fixed_pipeline", "paired_reference"),
    }

    # Population accounting from construction labels (truth-free arms).
    review = validate_labels(scenarios, build_schedule(scenarios, protocol, repository_root=REPO_ROOT))
    assert len(review.upgrade_population) == 7
    assert len(review.conditional_population) == 6
    assert len(review.guidance_population) == 4
    assert review.review_status == "pending"
    assert review.approved is False

    # Timing: every completed/failed attempted slot carries outer timing; clocks
    # are harness metadata only (ControlledClock), never RealLLM latency evidence.
    elapsed_samples: list[float] = []
    for item in record.slot_records:
        assert item.attempt_count == 1
        assert item.terminal is not None
        terminal = item.terminal
        assert_harness_only_provenance(terminal.provenance)
        assert terminal.provenance.offline_session is True
        assert terminal.timing is not None
        assert terminal.timing.timing_contract == "encoded_bytes_to_terminal_v1"
        assert terminal.timing.elapsed_s > 0.0
        elapsed_samples.append(terminal.timing.elapsed_s)
        if item.slot_key.arm == "product_agent":
            assert terminal.provenance.planner_class == "ScriptedFinishPlanner"
        else:
            assert (
                terminal.provenance.planner_class
                == "PlannerAblationFixedPipelineBaseline"
            )

    assert len(elapsed_samples) == SLOT_COUNT_V2
    assert all(sample > 0.0 for sample in elapsed_samples)

    # Fail-on-call spy at provider boundary: zero provider calls.
    assert provider_spy.calls == 0

    # Bundle written under temporary output only — no real seal.
    ledger = tmp_path / "offline_harness_out" / "campaign_record.json"
    assert ledger.is_file()
    payload = json.loads(ledger.read_text(encoding="utf-8"))
    assert payload["planned_slot_count"] == SLOT_COUNT_V2
    assert not (
        REPO_ROOT
        / "docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_2/protocol_seal"
    ).exists()

    # Configuration / budget blockers remain explicit (Task 5 inspect_limits).
    budget = inspect_limits(snapshot_effective_configuration())
    assert budget.execution_blocked is True
    assert "unknown_max_tokens_bound" in budget.blockers
    assert "unknown_provider_request_timeout" in budget.blockers
    assert budget.seal_ready is False


@pytest.mark.asyncio
async def test_relabelled_harness_bundle_is_not_scored_product(
    full_offline_dry_run: tuple[
        CampaignRecord,
        StudyProtocolV2,
        tuple[ScenarioDefinition, ...],
        set[tuple[str, str]],
        FailOnCallProvider,
        Path,
    ],
) -> None:
    record, _protocol, _scenarios, _paths, provider_spy, _tmp_path = full_offline_dry_run
    digest = campaign_bundle_digest(record)
    verify_campaign_bundle_binding(record, digest)

    # Take a real dry-run product terminal and rewrite only arm/class labels.
    product_terminal = next(
        item.terminal
        for item in record.slot_records
        if item.slot_key.arm == "product_agent" and item.terminal is not None
    )
    assert product_terminal.provenance.execution_identity == "harness_only"

    with pytest.raises(ProvenanceRejection, match="harness_only"):
        reject_relabeled_harness_terminal(
            product_terminal,
            rewrite={
                "arm": "product_agent",
                "planner_class": "RealLLMPlanner",
            },
        )

    # Even rewriting execution_identity fails without verified online context.
    with pytest.raises(ProvenanceRejection, match="offline_session|verified_online"):
        reject_relabeled_harness_terminal(
            product_terminal,
            rewrite={
                "arm": "product_agent",
                "planner_class": "RealLLMPlanner",
                "execution_identity": "product_campaign",
                "offline_session": True,
                "verified_online_context": False,
            },
        )

    # Fake-client RealLLMPlanner variant remains harness_only.
    fake_service = _LegacyTrapService(
        ApplicationDependencies(
            repository=InMemorySignalRepository(),
            planner_factory=lambda: RealLLMPlanner(
                provider="deepseek",
                api_key="unused",
                model="deepseek-v4-flash",
                client=provider_spy,  # type: ignore[arg-type]
            ),
            planner_identity=PlannerIdentity(
                provider="deepseek",
                model="deepseek-v4-flash",
                prompt_version=PROMPT_VERSION,
                phase4_certified_default=True,
            ),
            planner_configured=True,
            rule_engine=RuleEngine(),
            rule_profile_loader=_profile_loader(),
            knowledge_index=KnowledgeIndex(CORPUS_PATH),
            causal_policy_version="v9_11_mode_aware_no_fault_recovery",
        ),
        clock=lambda: NOW,
    )
    clock = ControlledClock(start=100.0)
    fake_session = build_product_arm_session(
        fake_service,
        clock=clock,
        phase_advances=dict(_PHASE_ADVANCES),
        offline_session=True,
    )
    preview = fake_session.provenance_preview()
    assert preview.execution_identity == "harness_only"
    assert preview.planner_class == "RealLLMPlanner"
    assert preview.provider_client_bound is True
    assert_harness_only_provenance(preview)

    # RealLLMPlanner.decide would call the spy; construction provenance alone
    # proves fake-client sessions stay harness_only and are rejected for scoring.
    fake_record = {
        "arm": "product_agent",
        "execution_identity": "product_campaign",  # relabel attempt
        "planner_class": "RealLLMPlanner",
        "study_id": STUDY_ID_V2,
        "scoring_identity": "signal_diag.planner_ablation_scoring",
        "offline_session": True,
        "provider_client_bound": True,
        "verified_online_context": True,  # fabricated claim
    }
    with pytest.raises(ProvenanceRejection, match="offline_session|fake-client|harness"):
        validate_scored_product_ingestion(fake_record)

    # Altered stored provenance invalidates bundle binding.
    mutated_slots = []
    for item in record.slot_records:
        if item.terminal is None:
            mutated_slots.append(item)
            continue
        rewritten = item.terminal.model_copy(
            update={
                "provenance": item.terminal.provenance.model_copy(
                    update={
                        "execution_identity": "product_campaign",
                        "planner_class": "RealLLMPlanner",
                    }
                )
            }
        )
        mutated_slots.append(item.model_copy(update={"terminal": rewritten}))
    mutated = record.model_copy(update={"slot_records": tuple(mutated_slots)})
    with pytest.raises(ProvenanceRejection, match="binding digest mismatch"):
        verify_campaign_bundle_binding(mutated, digest)

    # Unaltered binding still verifies; harness terminals remain rejected.
    verify_campaign_bundle_binding(record, digest)
    scored = terminal_to_scored_record(product_terminal)
    with pytest.raises(ProvenanceRejection, match="harness_only"):
        validate_scored_product_ingestion(scored)

    await fake_session.aclose()
    await fake_service.aclose()
    assert provider_spy.calls == 0


@pytest.mark.asyncio
async def test_offline_acceptance_review_status_stays_pending(
    full_offline_dry_run: tuple[
        CampaignRecord,
        StudyProtocolV2,
        tuple[ScenarioDefinition, ...],
        set[tuple[str, str]],
        FailOnCallProvider,
        Path,
    ],
) -> None:
    """T-CX302: label review remains pending; no formal seal during acceptance."""
    _record, protocol, scenarios, _, provider_spy, _tmp = full_offline_dry_run
    schedule = build_schedule(scenarios, protocol, repository_root=REPO_ROOT)
    review = validate_labels(scenarios, schedule)
    assert review.review_status == "pending"
    assert review.approved is False
    assert any("independent_offline_review" in note for note in review.review_provenance)
    assert provider_spy.calls == 0


@pytest.mark.asyncio
async def test_full_schedule_resource_path_is_harness_only(
    tmp_path: Path,
    provider_spy: FailOnCallProvider,
) -> None:
    """114-slot resource-policy path: real service + observers; remain harness-only.

    Uses ScriptedFinishPlanner under the product service (canonical RealLLM remains
    the public builder) with resource ledgers. Does not claim SDK capability or
    clear honest resource blockers. Zero real provider calls.
    """
    from dataclasses import replace

    from signal_diag.app.planner_ablation_v2_adapter import StudyResourceObserver
    from signal_diag.evaluation.planner_ablation.v2.resource_models import (
        ResourceAssessment,
    )
    from signal_diag.evaluation.recording import RecordingPlanner

    protocol = StudyProtocolV2()
    scenarios = load_proposed_scenarios(REPO_ROOT)
    schedule = build_schedule(scenarios, protocol, repository_root=REPO_ROOT)
    assert len(schedule.slots) == SLOT_COUNT_V2
    clock = ControlledClock(start=10.0)
    service = _scripted_service(provider_spy)
    deps = service._dependencies
    inner_factory = deps.planner_factory

    def recording_factory():
        return RecordingPlanner(inner_factory())

    service._dependencies = replace(deps, planner_factory=recording_factory)
    assessment = ResourceAssessment(
        planner_turn_ceiling=28,
        sdk_attempt_factor=3,
        sdk_attempt_ceiling_per_slot=84,
        sdk_attempt_ceiling=57 * 84,
        blockers=(
            "unaccepted_provider_model_mapping",
            "unproved_http_send_bound",
            "unknown_input_token_bound",
            "unknown_output_token_bound",
        ),
        execution_blocked=True,
        seal_ready=False,
        fixture_only=True,
    )
    digests: set[str] = set()

    async def factory(slot: SlotKey):
        digest = f"{slot.request_key}:{slot.arm}:{slot.round_index}"
        observer = StudyResourceObserver(slot_id=digest)
        if slot.arm == "product_agent":
            session = build_product_arm_session(
                service,
                clock=clock,
                phase_advances=dict(_PHASE_ADVANCES),
                offline_session=True,
                observer=observer,
            )
        else:
            session = build_fixed_arm_session(
                profile_loader=_profile_loader(),
                clock=clock,
                phase_advances=dict(_PHASE_ADVANCES),
                offline_session=True,
                observer=observer,
            )
        digests.add(digest)
        return session

    record = await run_schedule(
        schedule,
        protocol,
        factory,
        execution_mode="offline",
        clock=clock,
        output_dir=tmp_path / "resource_harness_out",
        wall_timeout=False,
        resource_policy="planner_ablation_resource_v1",
        resource_assessment=assessment,
    )
    await service.aclose()
    assert provider_spy.calls == 0
    assert record.planned_slot_count == SLOT_COUNT_V2
    # Honest assessment blockers stop the resource path; no silent green.
    assert record.status == "resource_stopped"
    assert record.accepted_conclusion_available is False
    assert len(digests) >= 1
    attempted = [r for r in record.slot_records if r.attempt_count == 1]
    assert attempted
    seen = {
        (r.resource_ledger or {}).get("slot_key_digest")
        for r in attempted
        if r.resource_ledger is not None
    }
    assert None not in seen
    assert len(seen) == len(attempted)
