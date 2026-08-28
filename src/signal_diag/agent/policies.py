"""Runtime policy limits and call-equivalence helpers."""

from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict, Field

from signal_diag.tools.contracts import ToolName

from .models import ToolHistoryEntry, ToolInvocation
from .state import DiagnosisState


class AgentLimits(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_tool_calls: int = Field(default=8, ge=1)
    max_planner_retries: int = Field(default=2, ge=0)
    max_no_progress: int = Field(default=2, ge=1)


def normalize_tool_arguments(call: ToolInvocation) -> dict[str, object]:
    """Return JSON-serializable normalized arguments from a typed Tool call."""
    return call.args.model_dump(mode="json")


def canonical_call_key(
    tool_name: ToolName,
    normalized_arguments: dict[str, object],
) -> str:
    """Canonical serialized key for equivalent-call detection."""
    payload = {"tool_name": tool_name, "args": normalized_arguments}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def is_equivalent_call(
    tool_name: ToolName,
    normalized_arguments: dict[str, object],
    history: tuple[ToolHistoryEntry, ...],
) -> bool:
    """Return True when an identical Tool call already appears in history."""
    key = canonical_call_key(tool_name, normalized_arguments)
    return any(
        canonical_call_key(entry.tool_name, entry.normalized_arguments) == key
        for entry in history
    )


def reset_progress(state: DiagnosisState) -> None:
    """Reset consecutive no-progress count after meaningful iteration."""
    state["no_progress_count"] = 0


def record_no_progress(state: DiagnosisState) -> None:
    """Increment consecutive no-progress count."""
    state["no_progress_count"] += 1


def should_terminate_no_progress(
    state: DiagnosisState,
    limits: AgentLimits,
) -> bool:
    """Return True when no-progress limit is reached."""
    return state["no_progress_count"] >= limits.max_no_progress
