"""Write-once study report and dry-run call estimate."""

from __future__ import annotations

import json
from pathlib import Path

from signal_diag.evaluation.agent_increment.budget import PER_CASE_CAP

ARMS = ("agent", "strong_fixed", "weak_fixed")


class WriteOnceError(FileExistsError):
    """The campaign directory already holds a report."""


def dry_run_summary(*, case_count: int, stage_cap: int) -> dict[str, object]:
    """Estimate the agent-arm HTTP ceiling. Fixed arms do not call the model."""
    return {
        "cases": case_count,
        "arms": list(ARMS),
        "per_case_cap": PER_CASE_CAP,
        "stage_cap": stage_cap,
        "max_calls": min(stage_cap, case_count * PER_CASE_CAP),
    }


def write_report(output_dir: Path, payload: dict[str, object]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "report.json"
    if path.exists():
        raise WriteOnceError(f"refusing to overwrite {path}")
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return path
