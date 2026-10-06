"""HTTP call caps. The check runs before a send and writes a stop record."""

from __future__ import annotations

import json
from pathlib import Path

PER_CASE_CAP = 21
DEV_STAGE_CAP = 1500
HELD_OUT_STAGE_CAP = 1008


class CallCapStop(RuntimeError):
    """Raised when a case or stage cap is already exhausted."""


class CallLedger:
    def __init__(self, *, stage_cap: int, output_dir: Path) -> None:
        if stage_cap < 1:
            raise ValueError("stage_cap must be positive")
        self.stage_cap = stage_cap
        self.output_dir = output_dir
        self.total = 0
        self.per_case: dict[str, int] = {}
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def reserve(self, case_id: str) -> None:
        used = self.per_case.get(case_id, 0)
        if used >= PER_CASE_CAP:
            self._stop("per_case_cap", case_id)
        if self.total >= self.stage_cap:
            self._stop("stage_cap", case_id)
        self.per_case[case_id] = used + 1
        self.total += 1

    def _stop(self, reason: str, case_id: str) -> None:
        payload = {
            "reason": reason,
            "case_id": case_id,
            "calls_used": self.total,
            "case_calls": self.per_case.get(case_id, 0),
            "per_case_cap": PER_CASE_CAP,
            "stage_cap": self.stage_cap,
        }
        path = self.output_dir / "stop_record.json"
        if not path.exists():
            path.write_text(
                json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
        raise CallCapStop(reason)
