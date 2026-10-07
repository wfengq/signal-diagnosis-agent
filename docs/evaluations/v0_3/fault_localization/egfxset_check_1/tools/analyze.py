"""Deterministic D051 check on the fixed EGFxSet sample (no model calls).

Usage: PYTHONPATH=src python analyze.py <data_dir> <results.json>
"""
import json, sys
from pathlib import Path

import numpy as np

from signal_diag.app.fault_localization import (
    COMPARISON_OVERLAP, COMPARISON_PROFILE_ID, SEGMENT_PROFILE_ID, _PAIRED_GATE, _PAIRED_GROWTH,
    _packaged_profile, localize_faults, scan_windows,
)
from signal_diag.app.guarded_tools import GuardedSignalToolService
from signal_diag.rules.engine import RuleEngine
from signal_diag.signal import InMemorySignalRepository, load_wav_bytes
from signal_diag.signal.context import StimulusContext
from signal_diag.signal.wav import InvalidWavError
from signal_diag.tools.contracts import ClippingInput, ContextualDistortionInput

EFFECTS = ("Clean", "TubeScreamer", "RAT", "BluesDriver", "Chorus", "Phaser")
CLIP_RULES = ("rule_clipping_detected_absent", "rule_clipping_ratio_acceptable", "rule_flat_top_absent")
data = Path(sys.argv[1])
paired_profile = _packaged_profile(COMPARISON_PROFILE_ID, "s1_contextual_comparison_v9_10.yaml")
segment_profile = _packaged_profile(SEGMENT_PROFILE_ID, "s1_segment_evidence_v1.yaml")
engine = RuleEngine()


def load(path):
    return load_wav_bytes(path.read_bytes(), filename=path.name).record


def whole_file(test, ref):
    repo = InMemorySignalRepository(); repo.put(test); repo.put(ref)
    tools = GuardedSignalToolService(repo)
    context = StimulusContext(mode="paired_reference", test_signal_id=test.meta.signal_id,
                              reference_signal_id=ref.meta.signal_id, assertion_source="user_supplied")
    result = tools.analyze_contextual_distortion(context, ContextualDistortionInput(channel="mixdown"))
    judged = {e.rule_id: e.judgment for e in engine.evaluate_profile(paired_profile, result.evidence).evaluations}
    if any(judged.get(rule) != "pass" for rule in _PAIRED_GATE):
        verdict = "not_comparable"
    else:
        verdict = "harmonic_growth" if judged.get(_PAIRED_GROWTH) == "fail" else "no_growth"
    clip = tools.detect_clipping(test.meta.signal_id, ClippingInput(channel="mixdown"))
    clip_judged = {e.rule_id: e.judgment for e in engine.evaluate_profile(segment_profile, clip.evidence).evaluations}
    return verdict, any(clip_judged.get(rule) == "fail" for rule in CLIP_RULES)


rows = []
for effect in EFFECTS:
    for test_path in sorted((data / effect).glob("*.wav")):
        row = {"effect": effect, "note": test_path.stem}
        try:
            ref = load(data / "Clean" / test_path.name)
            test = load(test_path)
        except InvalidWavError as error:
            row["rejected"] = str(error)
            rows.append(row)
            continue
        shown = localize_faults(test, mode="paired_reference", nominal_fundamental_hz=None,
                                diagnosed_faults=frozenset({"harmonic_distortion"}), reference=ref)
        withheld = localize_faults(test, mode="paired_reference", nominal_fundamental_hz=None,
                                   diagnosed_faults=frozenset(), reference=ref)
        single = localize_faults(test, mode="single_signal", nominal_fundamental_hz=None,
                                 diagnosed_faults=frozenset())
        harmonic = [i for i in shown.intervals if i.fault == "harmonic_distortion"]
        verdict, whole_clipping = whole_file(test, ref)
        row.update({
            "peak_abs": round(float(np.max(np.abs(test.samples))), 4),
            "comparison_windows": len(scan_windows(test, overlap=COMPARISON_OVERLAP)) * len(shown.channels),
            "windows_not_comparable": shown.windows_not_comparable,
            "scan_harmonic_intervals": [[i.channel, round(i.start_s, 3), round(i.end_s, 3)] for i in harmonic],
            "scan_harmonic_seconds": round(sum(i.end_s - i.start_s for i in harmonic), 3),
            "withheld_without_harmonic_diagnosis": withheld.harmonic_windows_withheld,
            "shown_without_harmonic_diagnosis": len([i for i in withheld.intervals if i.fault == "harmonic_distortion"]),
            "single_signal_clipping_intervals": len([i for i in single.intervals if i.fault == "clipping"]),
            "whole_file_paired": verdict,
            "whole_file_clipping_fail": whole_clipping,
        })
        rows.append(row)
Path(sys.argv[2]).write_text(json.dumps(rows, indent=1) + "\n")
summary = {}
for effect in EFFECTS:
    rs = [r for r in rows if r["effect"] == effect and "rejected" not in r]
    summary[effect] = {
        "notes": len(rs),
        "scan_any_harmonic": sum(bool(r["scan_harmonic_intervals"]) for r in rs),
        "whole_file_harmonic_growth": sum(r["whole_file_paired"] == "harmonic_growth" for r in rs),
        "whole_file_not_comparable": sum(r["whole_file_paired"] == "not_comparable" for r in rs),
        "single_signal_any_clipping": sum(r["single_signal_clipping_intervals"] > 0 for r in rs),
        "shown_without_harmonic_diagnosis": sum(r["shown_without_harmonic_diagnosis"] for r in rs),
    }
print(json.dumps(summary, indent=1))
