"""V0.3 S1 planner prompt specifications (additive to frozen v8.1 in prompts.py)."""

from __future__ import annotations

from signal_diag.agent.prompts import (
    _S1_SYSTEM_PROMPT_V8_1,
    _PlannerPromptSpec,
)

_V9_THD_CAUSAL_CLARIFICATION = (
    "A rule_thd_acceptable FAIL establishes that harmonic content is elevated "
    "relative to the configured threshold. It does not, by itself, establish "
    "that the cause is S1 harmonic distortion rather than intrinsic signal "
    "harmonic structure. An affirmative harmonic_distortion claim requires "
    "that the evidence supports not merely elevated harmonic content, but a "
    "causal distortion mechanism consistent with the S1 scenario.\n\n"
    "Do not determine whether harmonics are natural or distortion-injected by "
    "inspecting relative harmonic level patterns, THD magnitude, or other numeric "
    "patterns derived from the signal alone without a reference or "
    "distortion-mechanism Evidence. "
    "When causal attribution is uncertain, inconclusive with a traceable "
    "limitation is the correct output."
)

_V9_RETRIEVAL_POLICY = (
    "retrieve_knowledge is optional for every finish path. "
    "Do not call retrieve_knowledge as a mandatory step before finish.\n\n"
    "If you call retrieve_knowledge, query_text must be a non-empty phrase "
    "derived from the current diagnostic context (tool results, limitations, "
    "or open questions in this run). Never copy a fixed template string from "
    "examples or prior turns."
)

_V9_INVALID_HARMONIC_PATH_SECTION = """
9. Representative path — invalid or unreliable harmonic measurement

When analyze_harmonic_distortion returns valid=false, or same-run harmonic Evidence shows the measurement is not applicable or not reliable for causal S1 attribution, and clipping has been assessed or ruled out by same-run Evidence, finish inconclusive directly. Do not call retrieve_knowledge unless you have a specific corpus question that would change the conclusion.

Requirements for this inconclusive finish:
- At least one evidence_refs entry from same-run harmonic or clipping measurement explaining why attribution is insufficient (for example valid=false or not_applicable)
- Non-empty limitations stating that harmonic analysis is invalid or unreliable and causal S1 distortion attribution is not supported
- retrieve_knowledge is optional and NOT required
- Do not emit supported_fault, harmonic_distortion, or clipping as supported causal faults without valid same-run mechanism Evidence

Representative finish:
{
  "decision_type": "finish",
  "outcome": "inconclusive",
  "claims": [
    {
      "claim_id": "claim_invalid_harmonic_no_attribution",
      "fault_type": "inconclusive",
      "statement": "Same-run harmonic measurement is invalid or unreliable; causal S1 distortion attribution is not supported.",
      "evidence_refs": ["ev_harmonic_invalid_001"],
      "rule_refs": []
    }
  ],
  "confidence_label": "low",
  "limitations": [
    "Harmonic distortion analysis is invalid or unreliable on this signal; finish is inconclusive because causal attribution requires valid same-run harmonic Evidence."
  ]
}
"""

_V9_INCONCLUSIVE_PATH_SECTION = """
10. Representative path — valid harmonic measurement, THD rule FAIL, insufficient causal attribution

When analyze_harmonic_distortion returns valid=true, rule_thd_acceptable is FAIL, clipping is absent or ruled out by same-run Evidence, and no other same-run Evidence establishes a distortion mechanism (for example clipping, invalid metrics, or a prior observable reason for S1 distortion), the Agent cannot distinguish elevated harmonic content caused by distortion from elevated harmonic content intrinsic to the signal. In this state, inconclusive is a legitimate finish.

Requirements for this inconclusive finish:
- At least one evidence_refs entry from the same-run harmonic measurement
- At least one rule_refs entry from the same-run THD rule evaluation
- Non-empty limitations explaining that THD FAIL establishes elevated harmonic content but not causal attribution to S1 harmonic distortion
- retrieve_knowledge is optional, not required
- Do not emit harmonic_distortion as a supported causal fault without a traceable distortion mechanism

Representative finish:
{
  "decision_type": "finish",
  "outcome": "inconclusive",
  "claims": [
    {
      "claim_id": "claim_thd_fail_no_mechanism",
      "fault_type": "inconclusive",
      "statement": "Harmonic measurement is valid and the THD rule is FAIL, but no same-run Evidence establishes a causal S1 distortion mechanism.",
      "evidence_refs": ["ev_thd_valid_001"],
      "rule_refs": ["ruleval_thd_fail_001"]
    }
  ],
  "confidence_label": "low",
  "limitations": [
    "THD rule FAIL establishes elevated harmonic content relative to the configured threshold, not causal harmonic_distortion without additional distortion-mechanism Evidence."
  ]
}

11. Output field contract
"""


def _build_s1_system_prompt_v9_1() -> str:
    text = _S1_SYSTEM_PROMPT_V8_1.replace(
        "S1 distortion-diagnosis planner operating policy (v0.2-s1-planner-8.1).",
        "S1 distortion-diagnosis planner operating policy (v0.3-s1-planner-9.1).",
    )
    anchor = (
        "Cite thresholds only from live rule evaluations; never invent DSP numbers.\n\n"
        "no_supported_fault is a final empty-cause-set conclusion."
    )
    replacement = (
        "Cite thresholds only from live rule evaluations; never invent DSP numbers.\n\n"
        f"{_V9_THD_CAUSAL_CLARIFICATION}\n\n"
        f"{_V9_RETRIEVAL_POLICY}\n\n"
        "no_supported_fault is a final empty-cause-set conclusion."
    )
    if anchor not in text:
        msg = "v9.1 prompt build anchor missing"
        raise RuntimeError(msg)
    text = text.replace(anchor, replacement, 1)
    text = text.replace(
        "9. Output field contract",
        (
            _V9_INVALID_HARMONIC_PATH_SECTION.strip()
            + "\n\n"
            + _V9_INCONCLUSIVE_PATH_SECTION.strip()
        ),
        1,
    )
    return text


def _build_s1_system_prompt_v9_0() -> str:
    """Round-1 dev validation prompt (historical identity for iteration log)."""
    text = _S1_SYSTEM_PROMPT_V8_1.replace(
        "S1 distortion-diagnosis planner operating policy (v0.2-s1-planner-8.1).",
        "S1 distortion-diagnosis planner operating policy (v0.3-s1-planner-9.0).",
    )
    anchor = (
        "Cite thresholds only from live rule evaluations; never invent DSP numbers.\n\n"
        "no_supported_fault is a final empty-cause-set conclusion."
    )
    replacement = (
        "Cite thresholds only from live rule evaluations; never invent DSP numbers.\n\n"
        f"{_V9_THD_CAUSAL_CLARIFICATION}\n\n"
        "no_supported_fault is a final empty-cause-set conclusion."
    )
    if anchor not in text:
        msg = "v9.0 prompt build anchor missing"
        raise RuntimeError(msg)
    text = text.replace(anchor, replacement, 1)
    old_section = """
9. Representative path — valid harmonic measurement, THD rule FAIL, insufficient causal attribution

When analyze_harmonic_distortion returns valid=true, rule_thd_acceptable is FAIL, clipping is absent or ruled out by same-run Evidence, and no other same-run Evidence establishes a distortion mechanism (for example clipping, invalid metrics, or a prior observable reason for S1 distortion), the Agent cannot distinguish elevated harmonic content caused by distortion from elevated harmonic content intrinsic to the signal. In this state, inconclusive is a legitimate finish.

Requirements for this inconclusive finish:
- At least one evidence_refs entry from the same-run harmonic measurement
- At least one rule_refs entry from the same-run THD rule evaluation
- Non-empty limitations explaining that THD FAIL establishes elevated harmonic content but not causal attribution to S1 harmonic distortion
- Knowledge retrieval is optional, not required
- Do not emit harmonic_distortion as a supported causal fault without a traceable distortion mechanism

Representative finish:
{
  "decision_type": "finish",
  "outcome": "inconclusive",
  "claims": [
    {
      "claim_id": "claim_thd_fail_no_mechanism",
      "fault_type": "inconclusive",
      "statement": "Harmonic measurement is valid and the THD rule is FAIL, but no same-run Evidence establishes a causal S1 distortion mechanism.",
      "evidence_refs": ["ev_thd_valid_001"],
      "rule_refs": ["ruleval_thd_fail_001"]
    }
  ],
  "confidence_label": "low",
  "limitations": [
    "THD rule FAIL establishes elevated harmonic content relative to the configured threshold, not causal harmonic_distortion without additional distortion-mechanism Evidence."
  ]
}

10. Output field contract
"""
    return text.replace(
        "9. Output field contract",
        old_section.strip(),
        1,
    )


_S1_SYSTEM_PROMPT_V9_0 = _build_s1_system_prompt_v9_0()
_S1_PROMPT_V9_0 = _PlannerPromptSpec(
    version="v0.3-s1-planner-9.0",
    system_prompt=_S1_SYSTEM_PROMPT_V9_0,
)

_S1_SYSTEM_PROMPT_V9_1 = _build_s1_system_prompt_v9_1()
_S1_PROMPT_V9_1 = _PlannerPromptSpec(
    version="v0.3-s1-planner-9.1",
    system_prompt=_S1_SYSTEM_PROMPT_V9_1,
)


_V92_C_POLICY_SECTION = """
12. Conservative C-policy — causal faults require independent mechanism Evidence

THD rule FAIL or elevated harmonic content does not establish causal harmonic_distortion. A supported_fault harmonic_distortion claim must cite same-run series_kind Evidence whose value is injection_mechanism. THD FAIL without injection_mechanism Evidence is inconclusive, not supported_fault. Values native_odd_series, multi_partial, and not_applicable are not a causal harmonic_distortion mechanism. Multi-tone structure, additional periodic components, or mixed-partial periodic content are not that mechanism. Do not emit harmonic_distortion as supported_fault from THD FAIL alone.

Naturally harmonic-rich periodic waveforms (including square-like or odd-harmonic-rich spectra with no injected distortion) are not clipping. A supported_fault clipping claim must cite same-run clipping_mechanism Evidence whose value is true. Clipping requires same-run clipping-mechanism Evidence from detect_clipping (flat-top or full-scale detections). Do not infer clipping from harmonic richness, spectral shape, or a THD rule FAIL.

When analyze_harmonic_distortion returns valid=false, or the harmonic measurement is otherwise unreliable, that harmonic result must not be used as causal Evidence for clipping or harmonic_distortion. Invalid harmonic measurement is not a supported_fault. If detect_clipping does not independently support a clipping mechanism, finish inconclusive.

13. Output field contract
"""


def _build_s1_system_prompt_v9_2() -> str:
    text = _S1_SYSTEM_PROMPT_V9_1.replace(
        "S1 distortion-diagnosis planner operating policy (v0.3-s1-planner-9.1).",
        "S1 distortion-diagnosis planner operating policy (v0.3-s1-planner-9.2).",
    )
    if "11. Output field contract" not in text:
        msg = "v9.2 prompt build anchor missing"
        raise RuntimeError(msg)
    return text.replace("11. Output field contract", _V92_C_POLICY_SECTION.strip(), 1)


_S1_SYSTEM_PROMPT_V9_2 = _build_s1_system_prompt_v9_2()
_S1_PROMPT_V9_2 = _PlannerPromptSpec(
    version="v0.3-s1-planner-9.2",
    system_prompt=_S1_SYSTEM_PROMPT_V9_2,
)

# Historical identity only. Real-model failure evidence remains
# docs/evaluations/v0_3/dev/study_v0_3_dev_1/agent_v9_2_dev_run/ (SHA 8fc065ba...).
# This constant later drifted in the workspace (SHA 4dc97160...) and must not be
# reused as the product planner identity.

_V93_C_POLICY_SECTION = """
12. Conservative C-policy — causal faults require independent mechanism Evidence

THD rule FAIL or elevated harmonic content does not establish causal harmonic_distortion. A supported_fault harmonic_distortion claim must cite same-run series_kind Evidence whose value is injection_mechanism. When same-run series_kind Evidence equals injection_mechanism and the THD rule is FAIL, supported_fault with harmonic_distortion is the correct affirmative path. THD FAIL without injection_mechanism Evidence is inconclusive, not supported_fault. Values native_odd_series, multi_partial, and not_applicable are not a causal harmonic_distortion mechanism. Multi-tone structure, additional periodic components, or mixed-partial periodic content are not that mechanism. Do not emit harmonic_distortion as supported_fault from THD FAIL alone.

Naturally harmonic-rich periodic waveforms (including square-like or odd-harmonic-rich spectra with no injected distortion) are not clipping. A supported_fault clipping claim must cite same-run clipping_mechanism Evidence whose value is true. Clipping requires same-run clipping-mechanism Evidence from detect_clipping (flat-top or full-scale detections). Flat-top alone on a low-amplitude native waveform without clipping_mechanism=true is not causal clipping. Do not infer clipping from harmonic richness, spectral shape, or a THD rule FAIL.

When analyze_harmonic_distortion returns valid=false, or the harmonic measurement is otherwise unreliable, that harmonic result must not be used as causal Evidence for clipping or harmonic_distortion. Invalid harmonic measurement is not a supported_fault and does not automatically negate independent clipping Evidence. If same-run clipping_mechanism Evidence is true, a supported_fault clipping claim may still be emitted. If detect_clipping does not independently support a clipping mechanism, finish inconclusive.

no_supported_fault is a final empty-cause-set conclusion. It is not emitted as an additional cause beside a supported fault. Never emit a sibling no_supported_fault claim together with a positive supported fault such as clipping or harmonic_distortion.

13. Output field contract
"""


def _build_s1_system_prompt_v9_3() -> str:
    text = _S1_SYSTEM_PROMPT_V9_1.replace(
        "S1 distortion-diagnosis planner operating policy (v0.3-s1-planner-9.1).",
        "S1 distortion-diagnosis planner operating policy (v0.3-s1-planner-9.3).",
    )
    if "11. Output field contract" not in text:
        msg = "v9.3 prompt build anchor missing"
        raise RuntimeError(msg)
    return text.replace("11. Output field contract", _V93_C_POLICY_SECTION.strip(), 1)


_S1_SYSTEM_PROMPT_V9_3 = _build_s1_system_prompt_v9_3()
_S1_PROMPT_V9_3 = _PlannerPromptSpec(
    version="v0.3-s1-planner-9.3",
    system_prompt=_S1_SYSTEM_PROMPT_V9_3,
)

# Frozen product identity for the prior remediation step. Do not mutate bytes.
# SHA-256: 9fd0436e57b0d7db57abdfa3e2a87aca4e704d7c1f70adf781b1af967776554a

_V94_C_POLICY_SECTION = """
12. Conservative C-policy — causal faults require independent mechanism Evidence

series_kind labels are operational spectral-structure Evidence inferred from measured harmonic orders. They are not true injection provenance. The label even_order_present means one or more even-order components exceed the presence floor; natural even-order content can produce the same label.

THD rule FAIL or elevated harmonic content does not establish causal harmonic_distortion. A supported_fault harmonic_distortion claim must cite same-run series_kind Evidence whose value is even_order_present. When same-run series_kind Evidence equals even_order_present and the THD rule is FAIL, supported_fault with harmonic_distortion is the affirmative operational path under this contract. THD FAIL without even_order_present Evidence is inconclusive, not supported_fault. Values native_odd_series, multi_partial, and not_applicable are not that operational Evidence. Multi-tone structure, additional periodic components, or mixed-partial periodic content are not that Evidence. Do not emit harmonic_distortion as supported_fault from THD FAIL alone. Do not treat even_order_present as proof of an external injection event.

Naturally harmonic-rich periodic waveforms (including square-like or odd-harmonic-rich spectra with no injected distortion) are not clipping. A supported_fault clipping claim must cite same-run clipping_mechanism Evidence whose value is true and must also cite a same-run substantial clipping rule FAIL (rule_clipping_ratio_acceptable or rule_flat_top_absent). Clipping_mechanism alone is not sufficient: sparse isolated full-scale samples without an unacceptable clipping_ratio or reliable flat-top rule FAIL are not causal clipping. Flat-top alone on a low-amplitude native waveform without clipping_mechanism=true is not causal clipping. Do not infer clipping from harmonic richness, spectral shape, or a THD rule FAIL.

When analyze_harmonic_distortion returns valid=false, or the harmonic measurement is otherwise unreliable, that harmonic result must not be used as causal Evidence for clipping or harmonic_distortion. Invalid harmonic measurement is not a supported_fault and does not automatically negate independent, sufficient clipping Evidence. Sufficient clipping Evidence means clipping_mechanism=true plus a same-run substantial clipping rule FAIL. If detect_clipping does not independently support that sufficient set, finish inconclusive.

no_supported_fault is a final empty-cause-set conclusion. It is not emitted as an additional cause beside a supported fault. Never emit a sibling no_supported_fault claim together with a positive supported fault such as clipping or harmonic_distortion.

13. Output field contract
"""


def _build_s1_system_prompt_v9_4() -> str:
    text = _S1_SYSTEM_PROMPT_V9_1.replace(
        "S1 distortion-diagnosis planner operating policy (v0.3-s1-planner-9.1).",
        "S1 distortion-diagnosis planner operating policy (v0.3-s1-planner-9.4).",
    )
    if "11. Output field contract" not in text:
        msg = "v9.4 prompt build anchor missing"
        raise RuntimeError(msg)
    return text.replace("11. Output field contract", _V94_C_POLICY_SECTION.strip(), 1)


_S1_SYSTEM_PROMPT_V9_4 = _build_s1_system_prompt_v9_4()
_S1_PROMPT_V9_4 = _PlannerPromptSpec(
    version="v0.3-s1-planner-9.4",
    system_prompt=_S1_SYSTEM_PROMPT_V9_4,
)

_V95_CONTEXTUAL_POLICY_SECTION = """
12. Contextual reference diagnosis policy — mode-aware causal gates

StimulusContext is trusted provenance for mode and signal IDs. Never invent or
override test_signal_id or reference_signal_id from planner arguments. Never cite
StimulusContext fields as numerical Evidence.

paired_reference -> use analyze_contextual_distortion; harmonic causality needs
valid comparison Evidence and a same-run harmonic-growth rule FAIL. Absolute THD
FAIL or even_order_present alone is insufficient for causal harmonic_distortion.

nominal_single_tone -> conclusion is conditional on the declaration; measured F0
must match the declared fundamental, and THD/even-order gates must pass with
same-run Evidence. Always include a limitation that the conclusion depends on the
declared single-tone stimulus.

single_signal -> high THD or even-order structure is descriptive only; a causal
harmonic_distortion claim is unavailable. Prefer inconclusive requesting a
reference or declared single-tone context when harmonics are elevated without
clipping support.

clipping -> remains independent of comparison validity and needs
clipping_mechanism=true plus a same-run substantial clipping rule FAIL
(rule_clipping_ratio_acceptable or rule_flat_top_absent).

invalid context -> do not silently downgrade mode; state the limitation and finish
inconclusive when comparison or declaration qualification fails.

no_supported_fault is a final empty-cause-set conclusion. Never emit a sibling
no_supported_fault claim together with a positive supported fault.

13. Output field contract
"""


def _build_s1_system_prompt_v9_5() -> str:
    text = _S1_SYSTEM_PROMPT_V9_4.replace(
        "S1 distortion-diagnosis planner operating policy (v0.3-s1-planner-9.4).",
        "S1 distortion-diagnosis planner operating policy (v0.3-s1-planner-9.5).",
    )
    if "12. Conservative C-policy" not in text:
        msg = "v9.5 prompt build anchor missing"
        raise RuntimeError(msg)
    # Replace the entire v9.4 C-policy block through the output-field heading.
    start = text.index("12. Conservative C-policy")
    end = text.index("13. Output field contract", start)
    return text[:start] + _V95_CONTEXTUAL_POLICY_SECTION.strip() + text[end + len("13. Output field contract") :]


_S1_SYSTEM_PROMPT_V9_5 = _build_s1_system_prompt_v9_5()
_S1_PROMPT_V9_5 = _PlannerPromptSpec(
    version="v0.3-s1-planner-9.5",
    system_prompt=_S1_SYSTEM_PROMPT_V9_5,
)
