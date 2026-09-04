# Octave Ambiguity Detection Specification (V0.3 Workstream A)

**Status:** Phase 1.5 finalized
**Validation artifact:** `octave_ambiguity_validation.json`

## Problem

Naïve comparison of normalized ACF values at lag(F0) and lag(2×F0) false-flags every pure
sinusoid because the 2×-frequency lag sits on a negative trough (ratio ≈ −1), while
subharmonic-lock cases require detecting a competing **upper-octave partner peak**.

## Algorithm: `upper_octave_partner_peak_ratio`

Given normalized autocorrelation `acf`, selected primary lag `L_p`, search bounds
`[min_lag, max_lag]`, and parameters `octave_ambiguity_tolerance` (default **0.95**),
`octave_ratio_tolerance` (default **0.08**):

1. Let `P_p = acf[L_p]`. If `P_p ≤ 0`, no ambiguity.
2. Let `L_u = L_p // 2` (upper-octave / 2×-frequency partner lag).
3. If `L_u` is outside `[min_lag, max_lag]`, no ambiguity.
4. Verify `L_p / L_u ≈ 2` within `octave_ratio_tolerance`.
5. Let `P_u = max(acf[L_u − r : L_u + r])` with `r = 3` samples.
6. **Flag ambiguity** when `P_u / P_p ≥ octave_ambiguity_tolerance`.

**Non-goals enforced:**
- No F0 re-selection or spectral energy ranking
- No fixed 2×F0 lag comparison on the selected estimate alone

## Synthetic validation table (tolerance = 0.95)

| Signal | F0 selected | Expected | Detected |
|--------|-------------|----------|----------|
| pure 200 Hz | 200 Hz | no | no |
| pure 440 Hz | 440 Hz | no | no |
| pure 700 Hz (subharmonic lock) | ~350 Hz | yes | yes |
| two-tone 200+400 Hz | 200 Hz | no | no |
| high-THD 200 Hz (h2 > h1) | 200 Hz | no | no |

## Default parameter

`octave_ambiguity_tolerance = 0.95` — flags 700 Hz subharmonic-lock fixture while all
non-ambiguous synthetics remain unflagged across tolerance sweep [0.90, 0.98].
