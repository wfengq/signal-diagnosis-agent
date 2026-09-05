"""Three-arm contextual evaluation execution helpers."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from signal_diag.evaluation.contextual.baseline import require_baseline_request
from signal_diag.evaluation.contextual.models import (
    ArmKind,
    ArmResult,
    ContextualBaselineRequest,
    ContextualCase,
    ContextualManifest,
)
from signal_diag.evaluation.models import BaselineRunResult

CaseOracle = Callable[[ContextualCase, ArmKind], ArmResult]


async def run_fixed_pipeline_case(
    request: ContextualBaselineRequest,
    *,
    baseline: object | None = None,
) -> BaselineRunResult:
    """Execute one truth-free deterministic baseline slot."""
    request = require_baseline_request(request)
    run = getattr(baseline, "run", None)
    if run is None:
        raise TypeError("baseline must provide an async run method")
    result = await run(request)
    if not isinstance(result, BaselineRunResult):
        raise TypeError("baseline run must return BaselineRunResult")
    return result


def run_contextual_arms(
    manifest: ContextualManifest,
    *,
    oracle: CaseOracle | None = None,
    execute_once: bool = True,
) -> Mapping[ArmKind, tuple[ArmResult, ...]]:
    """Execute all three arms once per case under a shared seal boundary."""
    if not execute_once:
        raise ValueError("contextual validation requires single execution")
    if oracle is None:
        raise ValueError("three-arm execution requires an explicit runtime oracle")
    resolver = oracle
    buckets: dict[ArmKind, list[ArmResult]] = {
        "contextual_agent": [],
        "fixed_pipeline": [],
        "no_context_ablation": [],
    }
    for case in manifest.cases:
        for arm in ("contextual_agent", "fixed_pipeline", "no_context_ablation"):
            buckets[arm].append(resolver(case, arm))  # type: ignore[arg-type]
    return {key: tuple(value) for key, value in buckets.items()}
