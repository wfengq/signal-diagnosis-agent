"""Explicit YAML rule profile loading."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import yaml

from signal_diag.rules.models import RuleProfile


class YamlRuleProfileLoader:
    def __init__(self, profile_paths: Mapping[str, Path]) -> None:
        self._profile_paths = dict(profile_paths)

    def load(self, profile_id: str) -> RuleProfile:
        try:
            path = self._profile_paths[profile_id]
        except KeyError as error:
            raise KeyError(f"unknown rule profile: {profile_id}") from error
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        profile = RuleProfile.model_validate(payload)
        if profile.profile_id != profile_id:
            raise ValueError("loaded profile_id does not match requested profile_id")
        return profile
