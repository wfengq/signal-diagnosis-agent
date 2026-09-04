"""T-CX155–T-CX162: freeze and wire v0.3-s1-planner-9.6."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from signal_diag.agent.prompts_v03 import _S1_PROMPT_V9_5, _S1_PROMPT_V9_6

_FROZEN_V95_SHA256 = (
    "a4f4d260adb45a2af088961c77586b08d8279cd1bc4f3780474c3b0a6bd7cb02"
)
_FROZEN_V96_SHA256 = (
    "b9ed17debf9bfd2f086ee0eaa178d83370630a0530ebd02336769e416be1b5eb"
)

_NUMERIC_THRESHOLD_PATTERN = re.compile(
    r"\b(\d+\.?\d*)\s*%\s*(THD|thd)|h2\s*/\s*h3|1\.0\s*%|5\.0\s*%",
    re.IGNORECASE,
)


def test_t_cx155_product_prompt_version_is_v9_6() -> None:
    assert _S1_PROMPT_V9_6.version == "v0.3-s1-planner-9.6"


def test_t_cx156_v9_5_sha_remains_frozen() -> None:
    digest = hashlib.sha256(_S1_PROMPT_V9_5.system_prompt.encode("utf-8")).hexdigest()
    assert digest == _FROZEN_V95_SHA256


def test_t_cx157_contextual_modes_require_contextual_tool() -> None:
    text = _S1_PROMPT_V9_6.system_prompt.lower()
    assert "analyze_contextual_distortion" in text
    assert "not a substitute" in text or "is not a substitute" in text
    assert "paired_reference" in text
    assert "nominal_single_tone" in text
    assert "analyze_harmonic_distortion" in text


def test_t_cx158_no_fault_names_exact_negative_mechanism_evidence() -> None:
    text = _S1_PROMPT_V9_6.system_prompt
    assert "clipping_mechanism=false" in text
    assert "clipping_detected=false" in text
    lowered = text.lower()
    assert "not a substitute" in lowered
    assert "clipping_detected=false" in text


def test_t_cx159_natural_even_no_growth_closes_no_fault() -> None:
    text = _S1_PROMPT_V9_6.system_prompt.lower()
    assert "no_supported_fault" in text
    assert "relative to" in text and "reference" in text
    assert "natural" in text or "existing harmonic" in text
    assert "does not by itself require inconclusive" in text or (
        "do not finish inconclusive merely because" in text
    )


def test_t_cx160_nominal_mismatch_requires_inconclusive() -> None:
    text = _S1_PROMPT_V9_6.system_prompt.lower()
    assert "inconclusive" in text
    assert "mismatch" in text or "declaration" in text
    assert "do not emit no_supported_fault merely because" in text or (
        "not emit no_supported_fault" in text
    )


def test_t_cx161_combined_requires_two_independent_gates() -> None:
    text = _S1_PROMPT_V9_6.system_prompt.lower()
    assert "combined" in text
    assert "independent" in text
    assert "clipping" in text and "harmonic" in text


def test_t_cx162_composition_wires_v96_without_fallback_or_thresholds() -> None:
    assert _NUMERIC_THRESHOLD_PATTERN.search(_S1_PROMPT_V9_6.system_prompt) is None
    digest = hashlib.sha256(_S1_PROMPT_V9_6.system_prompt.encode("utf-8")).hexdigest()
    assert digest == _FROZEN_V96_SHA256
    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "signal_diag"
        / "app"
        / "composition.py"
    ).read_text(encoding="utf-8")
    assert "ScriptedPlanner" not in source
