#!/usr/bin/env python3
"""Installed-wheel smoke for Phase 5. Must run outside the source tree."""

from __future__ import annotations

import asyncio

from signal_diag.app import build_product_service, list_demo_presets
from signal_diag.app.reporting import load_accepted_evaluation_summary
from signal_diag.signal import load_wav_bytes

assert callable(load_wav_bytes)


def main() -> int:
    assert len(list_demo_presets()) == 5
    assert load_accepted_evaluation_summary().agent_slot_count == 80
    service = build_product_service(environ={})
    try:
        assert service.list_presets()
    finally:
        asyncio.run(service.aclose())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
