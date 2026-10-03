"""Installed SDK identity for evaluation. Evaluation does not import openai."""

from __future__ import annotations

from signal_diag.agent.provider_telemetry import build_audited_sdk_observation_profile
from signal_diag.evaluation.planner_ablation.v2.resource_models import (
    InstalledSdkIdentity,
)


def read_installed_sdk_identity() -> InstalledSdkIdentity:
    """Read the installed SDK profile into the evaluation identity model."""
    profile = build_audited_sdk_observation_profile()
    return InstalledSdkIdentity(
        openai_version=profile.openai_version,
        openai_source_digest=profile.openai_source_digest,
        native_http_family=profile.native_http_family,
        native_http_version=profile.native_http_version,
        httpcore_version=profile.httpcore_version,
        source_file_digests=dict(profile.source_file_digests),
        supported=profile.supported,
        blockers=tuple(profile.blockers),
    )
