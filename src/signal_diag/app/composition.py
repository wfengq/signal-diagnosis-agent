"""Product composition for the diagnosis application service.

If ``environ`` is None, credentials are read from a copy of ``os.environ``.
Tests pass ``environ={}`` to prove missing credentials without reading the
process environment.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import replace
from importlib.resources import files
from pathlib import Path

from signal_diag.agent.engine import DeterministicDiagnosisEngine
from signal_diag.agent.planner import (
    DEFAULT_DEEPSEEK_BASE_URL,
    DEFAULT_DEEPSEEK_MODEL,
    PROMPT_VERSION,
    PlannerModel,
    RealLLMPlanner,
)
from signal_diag.app.models import PlannerIdentity
from signal_diag.app.service import (
    ApplicationDependencies,
    DiagnosisApplicationService,
)
from signal_diag.knowledge.index import KnowledgeIndex
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal.repository import InMemorySignalRepository

_PROFILE_ID = "profile_s1_distortion"
_CONTEXTUAL_PROFILE_ID = "profile_s1_contextual_comparison_v9_10"
_LEGACY_CONTEXTUAL_PROFILE_ID = "profile_s1_contextual_comparison"
_CERTIFIED_PROMPT_VERSION = "v0.2-s1-planner-8.1"


def _packaged_path(*parts: str) -> Path:
    current = files("signal_diag")
    for part in parts:
        current = current.joinpath(part)
    return Path(str(current))


def _profile_path() -> Path:
    return _packaged_path("rules", "profiles", "s1_distortion_v1.yaml")


def _contextual_profile_path() -> Path:
    return _packaged_path(
        "rules", "profiles", "s1_contextual_comparison_v9_10.yaml"
    )


def _corpus_path() -> Path:
    return _packaged_path("knowledge", "corpus")


def build_engine_service(
    *,
    environ: Mapping[str, str] | None = None,
) -> DiagnosisApplicationService:
    """Product default (D053): the deterministic engine decides contextual verdicts.

    The LLM planner stays available as an explicit ``diagnosis_path="planner"``
    and free-text intake still needs DeepSeek credentials; neither falls back.
    """
    dependencies = replace(
        _product_dependencies(environ),
        engine_factory=DeterministicDiagnosisEngine,
        default_diagnosis_path="engine",
    )
    return DiagnosisApplicationService(dependencies)


def build_product_service(
    *,
    environ: Mapping[str, str] | None = None,
) -> DiagnosisApplicationService:
    return DiagnosisApplicationService(_product_dependencies(environ))


def _product_dependencies(environ: Mapping[str, str] | None) -> ApplicationDependencies:
    env = dict(os.environ) if environ is None else dict(environ)
    api_key = env.get("DEEPSEEK_API_KEY")
    base_url = env.get("DEEPSEEK_BASE_URL") or DEFAULT_DEEPSEEK_BASE_URL
    model = env.get("DEEPSEEK_MODEL") or DEFAULT_DEEPSEEK_MODEL
    planner_configured = bool(api_key)

    def planner_factory() -> PlannerModel:
        return RealLLMPlanner(
            provider="deepseek",
            api_key=api_key,
            base_url=base_url,
            model=model,
        )

    identity = PlannerIdentity(
        provider="deepseek",
        model=model,
        prompt_version=PROMPT_VERSION,
        phase4_certified_default=(
            model == DEFAULT_DEEPSEEK_MODEL and PROMPT_VERSION == _CERTIFIED_PROMPT_VERSION
        ),
    )
    repository = InMemorySignalRepository()
    dependencies = ApplicationDependencies(
        repository=repository,
        planner_factory=planner_factory,
        planner_identity=identity,
        planner_configured=planner_configured,
        rule_engine=RuleEngine(),
        rule_profile_loader=YamlRuleProfileLoader(
            {
                _PROFILE_ID: _profile_path(),
                _LEGACY_CONTEXTUAL_PROFILE_ID: _packaged_path(
                    "rules", "profiles", "s1_contextual_comparison_v1.yaml"
                ),
                _CONTEXTUAL_PROFILE_ID: _contextual_profile_path(),
            }
        ),
        knowledge_index=KnowledgeIndex(_corpus_path()),
        causal_policy_version="v9_11_mode_aware_no_fault_recovery",
    )
    return dependencies
