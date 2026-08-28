"""Versioned rule profile and evaluation result models."""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from signal_diag.tools.contracts import ToolName
from signal_diag.tools.evidence import EvidenceValue

RuleComparator = Literal[
    "lt",
    "lte",
    "gt",
    "gte",
    "eq",
    "neq",
]

RuleJudgment = Literal[
    "pass",
    "fail",
    "not_applicable",
]


class RuleDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str = Field(pattern=r"^rule_")
    metric: str = Field(min_length=1)
    source_tool: ToolName
    comparator: RuleComparator
    threshold: EvidenceValue
    unit: str | None = None
    description: str = Field(min_length=1)


class RuleProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    profile_id: str = Field(pattern=r"^profile_")
    version: str = Field(min_length=1)
    description: str = Field(min_length=1)
    rules: tuple[RuleDefinition, ...]

    @model_validator(mode="after")
    def _validate_rules(self) -> RuleProfile:
        if not self.rules:
            raise ValueError("rules must be non-empty")
        seen: set[str] = set()
        for rule in self.rules:
            if rule.rule_id in seen:
                raise ValueError(f"duplicate rule_id: {rule.rule_id}")
            seen.add(rule.rule_id)
        return self


class RuleEvaluation(BaseModel):
    model_config = ConfigDict(frozen=True)

    evaluation_id: str = Field(pattern=r"^ruleval_")
    rule_id: str = Field(pattern=r"^rule_")
    judgment: RuleJudgment
    observed_value: EvidenceValue | None = None
    comparator: RuleComparator
    threshold: EvidenceValue
    profile_id: str = Field(pattern=r"^profile_")
    profile_version: str = Field(min_length=1)
    evidence_refs: tuple[str, ...]
    reason: str | None = None


class RuleEvaluationBatch(BaseModel):
    model_config = ConfigDict(frozen=True)

    batch_id: str = Field(pattern=r"^rulebatch_")
    profile_id: str = Field(pattern=r"^profile_")
    profile_version: str = Field(min_length=1)
    evaluations: tuple[RuleEvaluation, ...]


@runtime_checkable
class RuleProfileLoader(Protocol):
    def load(self, profile_id: str) -> RuleProfile: ...
