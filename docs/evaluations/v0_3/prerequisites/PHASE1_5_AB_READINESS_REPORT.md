# Phase 1.5 / A-B Readiness Report

**Date:** 2026-09-02
**Scope:** P0 prerequisites + Workstream A/B production implementation (Workstream C excluded)

---

## 1. Reference validator 独立化结果

**Status: COMPLETE — EV-C032 satisfied**

| Item | Result |
|------|--------|
| New module | `src/signal_diag/evaluation/external/reference_harmonics.py` — numpy-only F0 + harmonic analysis |
| `reference.py` | Routes harmonic measurements through `reference_harmonics`; clipping still uses `dsp.clipping` (allowed) |
| Forbidden imports | No `dsp.harmonics`, `dsp.pitch`, or `tools` |
| Independence tests | `tests/evaluation/external/test_v03_reference_independence.py` (2 tests, GREEN) |
| V0.2 reference tests | `tests/evaluation/external/test_reference.py` — GREEN (EV-T027–030) |

---

## 2. Octave ambiguity 最终算法规格

**Algorithm:** `upper_octave_partner_peak_ratio`
**Spec doc:** `docs/evaluations/v0_3/prerequisites/octave_ambiguity_spec.md`
**Validation JSON:** `docs/evaluations/v0_3/prerequisites/octave_ambiguity_validation.json`

When autocorrelation locks to a **subharmonic** (700 Hz → 350 Hz), the upper-octave partner
at `primary_lag // 2` has a peak height ≥ 95% of the selected peak → flag set, F0 unchanged.

Pure sines do **not** flag because the 2×-frequency partner lag is a negative trough, not a
competing peak.

---

## 3. `octave_ambiguity_tolerance` 及依据

| Parameter | Default | Basis |
|-----------|---------|-------|
| `octave_ambiguity_tolerance` | **0.95** | Synthetic validation table: all 5 fixtures pass at 0.95 |
| `octave_ratio_tolerance` | **0.08** | Allows ±8% lag ratio deviation from exact 2:1 |
| `partner_search_radius` | **3 samples** | Local peak search around partner lag |

---

## 4. `min_fundamental_relative_energy` 最终 default 及依据

| Parameter | Default | Basis |
|-----------|---------|-------|
| `min_fundamental_relative_energy` | **0.15** | V0.3 dev-split calibration (12 synthesized cases) |

**Theoretical reference:** equal-noise floor `2/N ≈ 4.2×10⁻⁵` (N=48000, 1 s frame).

**Dev-split separation:**

| Regime | FRE range |
|--------|-----------|
| Unreliable (700 Hz lock, SNR 0 dB mis-lock) | ~10⁻²⁰ – 2.2×10⁻⁵ |
| High-THD valid (h2 > h1) | **0.171** (minimum reliable in dev) |
| Multi-partial / V0.2 regression | 0.33 – 0.67 |

**0.15** is the highest scanned threshold with **zero false-invalid** and **zero missed-unreliable**
on dev split. Threshold **0.20** falsely invalidates `dev_high_thd_h2_gt_h1` (T-B-002 regression).

**Not derived from V0.2 failure cases.**

Implementation constant: `DEFAULT_MIN_FUNDAMENTAL_RELATIVE_ENERGY` in `spectral_reliability.py`.

---

## 5. Dev calibration results

**Manifest:** `docs/evaluations/v0_3/prerequisites/dev_split_manifest.json`
**Full results:** `docs/evaluations/v0_3/prerequisites/fre_calibration_results.json`

| Threshold | False invalid | Missed unreliable |
|-----------|---------------|-------------------|
| 0.01 – 0.15 | 0 | 0 |
| 0.20 | 1 (`dev_high_thd_h2_gt_h1`) | 0 |

T-B-005 (V0.2 synthetic fixtures) passes at default **0.15**.

---

## 6. T-A / T-B 测试状态

| Suite | Result |
|-------|--------|
| T-A-001 … T-A-005 | **5/5 GREEN** |
| T-B-001 … T-B-008 | **8/8 GREEN** |
| Reference independence | **2/2 GREEN** |
| DSP + external suites | **201/201 GREEN** |

---

## 7. AGENTS.md contract compatibility

| Contract | Status |
|----------|--------|
| EV-C026 `fundamental_relative_energy` | Implemented on `HarmonicAnalysis` |
| EV-C027 FRE gate | `valid=false`, `invalid_reason=fundamental_bin_energy_below_reliability_threshold` |
| EV-C028 named `min_fundamental_relative_energy` | Optional kwarg, documented default 0.15 |
| EV-C029 (revised) octave flag, no F0 re-selection | `octave_ambiguity_detected` on `F0Estimate`; no energy ranking |
| Public function signatures | Unchanged required args; new optional kwargs with defaults only |
| V0.2 sealed artifacts | Not modified |
| Dataclass extensions | `F0Estimate` + `HarmonicAnalysis` new fields with defaults |

---

## 8. Remaining blockers

| Blocker | Status |
|---------|--------|
| Workstream C prompt | **Not authorized** — awaiting separate approval |
| EV-C036 acceptance targets | Deferred until test split unseal |
| V0.3 real WAV dev/test splits | Not yet acquired; calibration used synthesized dev split only |
| Reference analyzer version bump | Still `1.0.0` — algorithm duplicate preserves V0.2 reference numerics |

---

## 9. Workstream A/B production implementation gate

**GATE: SATISFIED — A/B implemented and GREEN**

Production changes:

- `src/signal_diag/dsp/spectral_reliability.py` — FRE, octave detection, defaults
- `src/signal_diag/dsp/pitch.py` — `f0_reliability`, `octave_ambiguity_detected`
- `src/signal_diag/dsp/harmonics.py` — FRE field, reliability gate, ambiguity context
- `src/signal_diag/dsp/models.py` — dataclass extensions

**Stopped after A/B GREEN per authorization. Workstream C not implemented.**

---

## Suggested next steps

1. Review and approve Workstream C authorization (`v0.3-s1-planner-9.0` + T-C-*).
2. Acquire real V0.3 dev WAV split; re-verify FRE default before test-split freeze.
3. Pre-register EV-C036 acceptance targets before test split unseal.
