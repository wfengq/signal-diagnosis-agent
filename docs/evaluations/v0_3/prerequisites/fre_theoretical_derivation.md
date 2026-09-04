# FRE Default Theoretical Derivation (V0.3)

**Parameter:** `min_fundamental_relative_energy`  
**Production default:** `0.15` (`DEFAULT_MIN_FUNDAMENTAL_RELATIVE_ENERGY`)  
**Status:** Engineering default for V0.3 Workstream B; not derived from V0.2 failure observations.

---

## 1. Definition (EV-C026)

For Hann-windowed RFFT with estimated fundamental frequency \(f_0\):

\[
\mathrm{FRE} = \frac{|X[k_{f_0}]|^2}{\sum_{k=1}^{N/2} |X[k]|^2}
\]

where \(k_{f_0}\) is the nearest positive-frequency bin to the estimated \(f_0\).

Implementation: `fundamental_relative_energy()` in `src/signal_diag/dsp/spectral_reliability.py`.

---

## 2. Theoretical bounds

| Regime | Expected FRE | Basis |
|--------|--------------|-------|
| Equal white noise across bins | \(\approx 2/N\) | Single-bin share of total positive-frequency energy |
| Pure sine (finite window) | \(\approx 0.60\text{–}0.67\) | Hann leakage spreads energy; not ≈1.0 |
| Two equal partials | \(\approx 0.33\) | Energy shared across two dominant bins |
| Unreliable F0 lock | \(\ll 10^{-4}\) | Numerator bin has negligible energy at mis-estimated \(f_0\) |

For \(N=48000\): \(2/N \approx 4.2\times 10^{-5}\).

---

## 3. Why 0.15 is the default

Selection rule (Phase 1.5 + Round 1 real dev):

1. Must exceed unreliable synthesized regime (\(<10^{-4}\)) with margin.
2. Must remain below reliable pure-sine cluster (minimum observed \(\approx 0.33\) on multi-partial; pure sines \(\approx 0.63+\)).
3. On synthesized 12-case dev split: **zero missed-unreliable** at 0.15.
4. On real dev WAV (Round 1): **zero missed-unreliable** at 0.15; threshold scan 0.05–0.25 showed zero missed-unreliable on FRE-bearing cases.

**0.15** is the highest round-1 scan value with zero missed-unreliable on synthesized dev while staying well below the multi-partial minimum (~0.33). It is **not** tuned on V0.2 sealed final set or V0.2 failure F0 values (350 Hz / 905 Hz).

---

## 4. Traceability

| Artifact | Role |
|----------|------|
| `docs/evaluations/v0_3/prerequisites/fre_calibration_results.json` | Synthesized threshold scan |
| `docs/evaluations/v0_3/dev/study_v0_3_dev_1/ab_dsp_metrics.json` | Real WAV Round 1 metrics |
| `docs/evaluations/v0_3/prerequisites/octave_ambiguity_spec.md` | Separate octave parameter (0.95) |

---

## 5. EV-C036 note

Acceptance targets for test split remain **pre-registration only** until test split unseal. This document satisfies the val-freeze gate requirement for formula basis and non-V0.2-tuning justification.
