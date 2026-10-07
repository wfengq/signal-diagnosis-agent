"""Product default composition with the deterministic engine (D053, §28).

``composition.build_product_service`` stays byte-identical (T-CX301, T251); this
module reuses its dependencies and adds the engine as the default diagnosis
path. The LLM planner remains available as ``diagnosis_path="planner"`` and
free-text intake still needs DeepSeek credentials; neither falls back.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from signal_diag.agent.engine import DeterministicDiagnosisEngine
from signal_diag.app.composition import build_product_service
from signal_diag.app.service import DiagnosisApplicationService


def build_engine_service(
    *,
    environ: Mapping[str, str] | None = None,
) -> DiagnosisApplicationService:
    planner_service = build_product_service(environ=environ)
    dependencies = replace(
        planner_service._dependencies,
        engine_factory=DeterministicDiagnosisEngine,
        default_diagnosis_path="engine",
    )
    return DiagnosisApplicationService(dependencies)


__all__ = ["build_engine_service"]
