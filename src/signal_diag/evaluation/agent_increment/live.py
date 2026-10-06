"""Live agent arm. Every HTTP send reserves a ledger slot first.

The product default planner stays on v9.11. This runner constructs a v9.12
subclass and never substitutes a scripted planner.
"""

from __future__ import annotations

import os
from importlib.resources import files
from pathlib import Path
from typing import Any

from signal_diag.agent.intake import (
    INTAKE_PLANNER_IDENTITY,
    ContextDraft,
    IntakeCallLimits,
    IntakeRequest,
    OpenAICompatibleIntakeClient,
    RealLLMIntakePlanner,
)
from signal_diag.agent.planner import PlannerOutputError, RealLLMPlanner
from signal_diag.agent.prompts_v03 import _S1_PROMPT_V9_12
from signal_diag.agent.runtime import DistortionDiagnosisRuntime
from signal_diag.evaluation.agent_increment.budget import CallLedger
from signal_diag.evaluation.agent_increment.models import Family
from signal_diag.evaluation.agent_increment.simulated_user import (
    confirm_proposed_fields,
)
from signal_diag.knowledge.index import KnowledgeIndex
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal.context import StimulusContext
from signal_diag.signal.repository import SignalRepository
from signal_diag.tools.service import SignalToolService

_MISSING_CREDENTIALS = (
    "RealLLMPlanner is not configured: set DEEPSEEK_API_KEY in the "
    "environment before running real-model evaluation. "
    "This command does not fall back to ScriptedPlanner."
)


class AgentIncrementV912Planner(RealLLMPlanner):
    """Study planner. The product class remains on v9.11."""

    _prompt_spec = _S1_PROMPT_V9_12


class ReservingChatClient:
    """SDK-shaped client. ``reserve`` runs before the wrapped ``create``."""

    def __init__(self, inner: Any, ledger: CallLedger, case_id: str) -> None:
        retries = getattr(inner, "max_retries", None)
        if retries != 0:
            raise PlannerOutputError("live SDK client max_retries must be int 0")
        self._inner = inner
        self._ledger = ledger
        self._case_id = case_id
        self.max_retries = 0
        self.chat = self
        self.completions = self

    async def create(self, **kwargs: Any) -> Any:
        self._ledger.reserve(self._case_id)
        return await self._inner.create(**kwargs)

    async def aclose(self) -> None:
        close = getattr(self._inner, "close", None)
        if close is None:
            return
        result = close()
        if hasattr(result, "__await__"):
            await result


def require_live_credentials(api_key: str | None) -> str:
    resolved = api_key if api_key is not None else os.environ.get("DEEPSEEK_API_KEY")
    if resolved is None or not str(resolved).strip():
        raise PlannerOutputError(_MISSING_CREDENTIALS)
    return str(resolved).strip()


def _profile_path(name: str) -> Path:
    return Path(str(files("signal_diag").joinpath("rules", "profiles", name)))


def _runtime(
    *,
    repository: SignalRepository,
    planner: RealLLMPlanner,
) -> DistortionDiagnosisRuntime:
    loader = YamlRuleProfileLoader(
        {
            "profile_s1_distortion": _profile_path("s1_distortion_v1.yaml"),
            "profile_s1_contextual_comparison_v9_10": _profile_path(
                "s1_contextual_comparison_v9_10.yaml"
            ),
            "profile_s1_segment_evidence": _profile_path("s1_segment_evidence_v1.yaml"),
        }
    )
    corpus = Path(str(files("signal_diag").joinpath("knowledge", "corpus")))
    return DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=planner,
        rule_engine=RuleEngine(),
        rule_profile_loader=loader,
        knowledge_index=KnowledgeIndex(corpus),
        causal_policy_version="v9_11_mode_aware_no_fault_recovery",
    )


def _stimulus(
    *,
    signal_id: str,
    reference_signal_id: str | None,
    confirmed_mode: str,
    nominal_fundamental_hz: float | None,
    stimulus_kind: str | None,
) -> StimulusContext:
    reference = reference_signal_id if confirmed_mode == "paired_reference" else None
    nominal = nominal_fundamental_hz if confirmed_mode != "single_signal" else None
    kind = stimulus_kind if confirmed_mode != "single_signal" else None
    return StimulusContext(
        mode=confirmed_mode,  # type: ignore[arg-type]
        test_signal_id=signal_id,
        reference_signal_id=reference,
        nominal_fundamental_hz=nominal,
        stimulus_kind=kind,  # type: ignore[arg-type]
        assertion_source="evaluation_manifest",
    )


async def run_live_agent(
    *,
    family: Family,
    case_id: str,
    ledger: CallLedger,
    api_key: str | None,
    repository: SignalRepository,
    signal_id: str,
    user_text: str,
    truth: ContextDraft | None,
    filenames: tuple[str, ...],
    test_file: str,
    client: Any,
    base_url: str | None = "https://api.deepseek.com",
    model: str = "deepseek-v4-flash",
    reference_signal_id: str | None = None,
) -> object:
    """Run the agent arm. ``client`` is the raw SDK. This function reserves."""
    key = require_live_credentials(api_key)
    guarded = ReservingChatClient(client, ledger, case_id)
    if family == "T1":
        if truth is None:
            raise ValueError("T1 live run requires a truth draft")
        intake = RealLLMIntakePlanner(
            client=OpenAICompatibleIntakeClient(guarded),
            model=model,
            limits=IntakeCallLimits(max_output_tokens=800, timeout_s=60.0),
        )
        if intake.identity != INTAKE_PLANNER_IDENTITY:
            raise PlannerOutputError("intake identity drifted")
        draft = await intake.propose(
            IntakeRequest(
                text=user_text,
                filenames=filenames,
                test_file=test_file,
            )
        )
        confirmation = confirm_proposed_fields(draft, truth)
        confirmed = confirmation.confirmed
        stimulus = _stimulus(
            signal_id=signal_id,
            reference_signal_id=reference_signal_id,
            confirmed_mode=confirmed.mode,
            nominal_fundamental_hz=confirmed.nominal_fundamental_hz,
            stimulus_kind=confirmed.stimulus_kind,
        )
    else:
        stimulus = StimulusContext(
            mode="single_signal",
            test_signal_id=signal_id,
            assertion_source="evaluation_manifest",
        )
    planner = AgentIncrementV912Planner(
        provider="deepseek",
        api_key=key,
        base_url=base_url,
        model=model,
        client=guarded,
    )
    if planner.prompt_version != "v0.3-s1-planner-9.12":
        raise PlannerOutputError("live diagnosis planner must be v9.12")
    if RealLLMPlanner._prompt_spec.version != "v0.3-s1-planner-9.11":
        raise PlannerOutputError("product default prompt drifted")
    runtime = _runtime(repository=repository, planner=planner)
    return await runtime.run(
        signal_id=signal_id,
        user_request=user_text,
        stimulus_context=stimulus,
    )
