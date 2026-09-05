"""Isolated V0.3 contextual evaluation harness."""

from .baseline import ContextualFixedPipelineBaseline
from .calibration import (
    CONTEXTUAL_GROWTH_CANDIDATES,
    CalibrationReport,
    calibrate_even_growth_threshold,
)
from .manifest import (
    build_slot_plan,
    canonical_json_bytes,
    load_contextual_manifest,
    manifest_sha256,
    validate_contextual_manifest,
)
from .models import (
    CONTEXTUAL_SCORING_ID,
    CONTEXTUAL_SCORING_VERSION,
    ArmKind,
    ArmPlan,
    ArmResult,
    ConfidenceTier,
    ContextualAggregate,
    ContextualBaselineRequest,
    ContextualCase,
    ContextualManifest,
    ContextualRole,
    ContextualRunScore,
    DiagnosticMode,
    PairedHarmonicSlot,
)
from .runner import run_contextual_arms, run_fixed_pipeline_case
from .scoring import score_contextual_run
from .sealing import seal_contextual_bundle, verify_contextual_bundle

__all__ = [
    "CONTEXTUAL_GROWTH_CANDIDATES",
    "CONTEXTUAL_SCORING_ID",
    "CONTEXTUAL_SCORING_VERSION",
    "ArmKind",
    "ArmPlan",
    "ArmResult",
    "CalibrationReport",
    "ConfidenceTier",
    "ContextualAggregate",
    "ContextualBaselineRequest",
    "ContextualCase",
    "ContextualFixedPipelineBaseline",
    "ContextualManifest",
    "ContextualRole",
    "ContextualRunScore",
    "DiagnosticMode",
    "PairedHarmonicSlot",
    "build_slot_plan",
    "calibrate_even_growth_threshold",
    "canonical_json_bytes",
    "load_contextual_manifest",
    "manifest_sha256",
    "run_contextual_arms",
    "run_fixed_pipeline_case",
    "score_contextual_run",
    "seal_contextual_bundle",
    "validate_contextual_manifest",
    "verify_contextual_bundle",
]
