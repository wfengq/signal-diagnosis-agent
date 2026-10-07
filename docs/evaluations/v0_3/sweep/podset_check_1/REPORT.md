# pOD-set validation of the sweep test (D056) — result

## Run

- **Data:** pOD-set (Dal Rì, Stefani, Turchet, Conci; Zenodo DOI
  10.5281/zenodo.15389653; CC BY-NC 4.0). Files are listed with their SHA-256
  in `manifest.json`. No audio is committed.
- **Selection:** 486 recordings: 27 pedals × gain indices 0–5 (knob 0–10) ×
  tone index 3 (knob 6) × three levels.
- **Analysis:** `known-sweep-analysis-1.0` (band code of `sweep-analysis-1.1`),
  plus an independent short-time-spectrum cross-check at 1, 2 and 4 kHz.
- **Cost:** no model calls.
- **Regenerate:**

  ```bash
  python -m signal_diag.evaluation.podset fetch --cache DIR
  python -m signal_diag.evaluation.podset run --cache DIR \
    --out docs/evaluations/v0_3/sweep/podset_check_1
  ```

## Criteria

The criteria were fixed in the approved design before the full run.

| # | Criterion | Bar | Result (all pedals) | Without the design pedal | Status |
|---|---|---|---|---|---|
| 1 | Synthetic check on the dataset's dry sweep | ≤ 0.1 pp; identity ≤ 0.05 % | worst 0.009 pp; identity 0.008 % | — | pass |
| 2 | THD does not fall with level | ≥ 95 % | **86.2 %** (2246 comparisons) | 85.7 % | **fail** |
| 3 | THD does not fall with gain | ≥ 90 % | 99.1 % (2811) | 99.1 % | pass |
| 4 | Median THD at minimum gain | < 1 % (reported only) | 0.12 % (median of pedal medians) | 0.13 % | below limit |
| 5 | Short-time-spectrum cross-check at 1–4 kHz | ≥ 90 % | 99.8 % (1182) | 99.8 % | pass |

Criterion 4 is a distribution, not a gate. Five pedals are clearly distorted
at minimum gain: 385 (18 %), Red Llama (23 %), Plumes (15 %), Big Rumble
(12 %) and Mofetta (7.4 %). These are designs whose distortion does not come
from the gain knob alone.

## Why criterion 2 fails

The failure is in the criterion's assumption, not in the measurement. Three
findings support this:

- **The failures are concentrated.** 272 of the 309 failing comparisons come
  from five pedals: Plumes, Big Rumble, Overhive, Mofetta and Wessex. They
  occur at high distortion (median 16 % THD), with drops of 10–23 %.
- **The independent method sees the same drops.** All 170 failing
  comparisons in the cross-checked bands (1–4 kHz) also fall in the
  short-time spectrum, which uses no deconvolution. The deconvolution is not
  creating them.
- **The harmonic energy is not moving to higher orders.** That hypothesis is
  rejected: at 1 kHz, harmonic content through order 9 also falls in 52 of 53
  failing comparisons.

These pedals produce relatively fewer harmonics at a higher input level in
these settings; Big Rumble, for example, goes from 14.9 % to 10.2 % at 1 kHz.
That is plausible for designs with compressing or level-dependent stages, but
the dataset does not let us identify the mechanism. "THD never falls with
level" holds for most pedals (86 %) but is not a physical law for every
overdrive. As decided (D056 4A), the criterion is not changed after the fact.

## Dataset note

The dataset's description gives the sweep levels as −6, −12 and −24 dBFS. The
dry sweep files actually peak at **−4.0, −10.0 and −16.0 dBFS**, in 6 dB
steps. The level labels in `results.json` and `summary.json` keep the
dataset's names. The order, quiet to loud, is unaffected.

## Onset at the demonstration limit (5 % band THD, `profile_s1_sweep` 1.0.0-demo)

Number of pedals by the first level at which any band exceeds the limit:

| Gain index | Never | at −24 | at −12 | at −6 (dataset labels) |
|---|---|---|---|---|
| 0 | 19 | 5 | 1 | 2 |
| 1 | 7 | 10 | 5 | 5 |
| 2 | 4 | 16 | 5 | 2 |
| 3 | 1 | 19 | 4 | 3 |
| 4 | 0 | 24 | 2 | 1 |
| 5 | 0 | 25 | 1 | 1 |

Onset moves toward quieter levels as gain rises, as expected. The 5 % limit is
a demonstration value, not a standard.

## What this shows and does not show

- **Shown:**
  - the band THD of the sweep analysis agrees with an independent
    measurement on 27 real analog devices (99.8 %);
  - it follows the gain control (99.1 %);
  - it is exact on synthetic devices driven by the dataset's own sweep.
- **Not shown:**
  - that every device's THD rises with level; it does not for five of these
    pedals;
  - behaviour on loudspeakers or acoustic recordings, since pOD-set is a
    line-level dataset;
  - behaviour with the product's own synchronized stimulus on real devices.
    The dataset uses its own sweep, analysed with `analyze_known_sweep`.
