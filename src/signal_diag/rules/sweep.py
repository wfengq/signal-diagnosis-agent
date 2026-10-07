"""Versioned rules for the sweep stimulus test (D054, §29).

Thresholds live only in the YAML profile (``profile_s1_sweep``); they are
demonstration values, not industry standards.
"""

from __future__ import annotations

import hashlib
import json
from importlib.resources import files
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from signal_diag.rules.models import RuleComparator, RuleJudgment
from signal_diag.tools.sweep import FactValue, SweepFact, SweepMeasurement

SWEEP_PROFILE_ID = "profile_s1_sweep"
RuleRole = Literal["validity", "clipping", "harmonic"]


class SweepRule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str = Field(pattern=r"^rule_sweep_")
    metric: str = Field(min_length=1)
    role: RuleRole
    comparator: RuleComparator
    threshold: FactValue
    unit: str | None = None
    description: str = Field(min_length=1)


class SweepRuleProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    profile_id: str = Field(pattern=r"^profile_")
    version: str = Field(min_length=1)
    description: str = Field(min_length=1)
    rules: tuple[SweepRule, ...]

    @model_validator(mode="after")
    def _unique(self) -> SweepRuleProfile:
        ids = [rule.rule_id for rule in self.rules]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError("rules must be non-empty and unique")
        return self


class SweepRuleEvaluation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    evaluation_id: str = Field(pattern=r"^swr_")
    rule_id: str
    role: RuleRole
    judgment: RuleJudgment
    observed_value: FactValue | None
    comparator: RuleComparator
    threshold: FactValue
    profile_id: str
    profile_version: str
    fact_refs: tuple[str, ...]
    band_hz: float | None = None


def load_sweep_profile(path: Path | None = None) -> SweepRuleProfile:
    source = path or Path(
        str(files("signal_diag").joinpath("rules", "profiles", "s1_sweep_v1.yaml"))
    )
    payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    return SweepRuleProfile.model_validate(payload)


def _compare(
    value: FactValue, comparator: RuleComparator, threshold: FactValue
) -> bool:
    if comparator == "eq":
        return value == threshold
    if comparator == "neq":
        return value != threshold
    numeric = (int, float)
    if (
        isinstance(value, bool)
        or isinstance(threshold, bool)
        or not isinstance(value, numeric)
        or not isinstance(threshold, numeric)
    ):
        raise TypeError(f"comparator {comparator} needs numbers")
    return {
        "lt": value < threshold,
        "lte": value <= threshold,
        "gt": value > threshold,
        "gte": value >= threshold,
    }[comparator]


def _evaluation(
    profile: SweepRuleProfile,
    rule: SweepRule,
    fact: SweepFact | None,
    measurement_id: str,
) -> SweepRuleEvaluation:
    band = fact.band_hz if fact is not None else None
    if fact is None or fact.validity != "valid":
        judgment: RuleJudgment = "not_applicable"
        observed: FactValue | None = None
    else:
        judgment = (
            "pass" if _compare(fact.value, rule.comparator, rule.threshold) else "fail"
        )
        observed = fact.value
    payload = json.dumps(
        [measurement_id, profile.profile_id, profile.version, rule.rule_id, band]
    )
    return SweepRuleEvaluation(
        evaluation_id="swr_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24],
        rule_id=rule.rule_id,
        role=rule.role,
        judgment=judgment,
        observed_value=observed,
        comparator=rule.comparator,
        threshold=rule.threshold,
        profile_id=profile.profile_id,
        profile_version=profile.version,
        fact_refs=(fact.fact_id,) if fact is not None else (),
        band_hz=band,
    )


def evaluate_sweep(
    profile: SweepRuleProfile, measurement: SweepMeasurement
) -> tuple[SweepRuleEvaluation, ...]:
    """One evaluation per rule and matching fact (per band for band metrics)."""
    evaluations: list[SweepRuleEvaluation] = []
    for rule in profile.rules:
        matches = [fact for fact in measurement.facts if fact.metric == rule.metric]
        if not matches:
            evaluations.append(
                _evaluation(profile, rule, None, measurement.measurement_id)
            )
        for fact in matches:
            evaluations.append(
                _evaluation(profile, rule, fact, measurement.measurement_id)
            )
    return tuple(evaluations)


__all__ = [
    "SWEEP_PROFILE_ID",
    "SweepRule",
    "SweepRuleEvaluation",
    "SweepRuleProfile",
    "evaluate_sweep",
    "load_sweep_profile",
]
