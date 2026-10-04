"""Test-only regression comparison profiles (not product tolerances)."""

from __future__ import annotations

import hashlib
import json

from signal_diag.rules.regression import (
    ComparisonProfile,
    ComparisonRule,
    HarmonicFundamentalApplicability,
)

FIXTURE_PROFILE_ID = "profile_regression_fixture_clipping"
FIXTURE_PROFILE_VERSION = "test-boundary-1"


def _profile_digest(payload: dict[str, object]) -> str:
    body = dict(payload)
    body.pop("digest", None)
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
            "utf-8"
        )
    ).hexdigest()


CLIPPING_BOUNDARY_RULE = ComparisonRule(
    rule_id="rule_fixture_clipping_ratio",
    metric="clipping_ratio",
    source_tool="detect_clipping",
    unit=None,
    difference="signed_absolute",
    allowed_min=-0.001,
    allowed_max=0.001,
    denominator_floor=None,
    applicability_version="fixture-clipping-1",
)

RELATIVE_CLIPPING_RULE = ComparisonRule(
    rule_id="rule_fixture_clipping_relative",
    metric="clipping_ratio",
    source_tool="detect_clipping",
    unit=None,
    difference="relative_increase",
    allowed_min=-0.5,
    allowed_max=0.5,
    denominator_floor=1e-6,
    applicability_version="fixture-clipping-relative-1",
)

THD_RULE = ComparisonRule(
    rule_id="rule_fixture_thd_percent",
    metric="thd_percent",
    source_tool="analyze_harmonic_distortion",
    unit="%",
    difference="signed_absolute",
    allowed_min=-1.0,
    allowed_max=1.0,
    denominator_floor=None,
    applicability_version="fixture-thd-1",
)

HARMONIC_APPLICABILITY = HarmonicFundamentalApplicability(
    max_fundamental_delta_hz=0.5,
)


def build_fixture_clipping_profile() -> ComparisonProfile:
    profile = ComparisonProfile(
        profile_id=FIXTURE_PROFILE_ID,
        version=FIXTURE_PROFILE_VERSION,
        rules=(CLIPPING_BOUNDARY_RULE,),
        harmonic_fundamental_applicability=None,
        digest="0" * 64,
    )
    digest = _profile_digest(profile.model_dump(mode="json"))
    return profile.model_copy(update={"digest": digest})


def build_fixture_relative_profile() -> ComparisonProfile:
    profile = ComparisonProfile(
        profile_id="profile_regression_fixture_relative",
        version="test-relative-1",
        rules=(RELATIVE_CLIPPING_RULE,),
        harmonic_fundamental_applicability=None,
        digest="0" * 64,
    )
    digest = _profile_digest(profile.model_dump(mode="json"))
    return profile.model_copy(update={"digest": digest})


def build_fixture_thd_profile() -> ComparisonProfile:
    profile = ComparisonProfile(
        profile_id="profile_regression_fixture_thd",
        version="test-thd-1",
        rules=(THD_RULE,),
        harmonic_fundamental_applicability=HARMONIC_APPLICABILITY,
        digest="0" * 64,
    )
    digest = _profile_digest(profile.model_dump(mode="json"))
    return profile.model_copy(update={"digest": digest})
