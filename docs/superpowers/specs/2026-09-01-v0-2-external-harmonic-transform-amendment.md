# V0.2 External Harmonic Transform Amendment (OQ-012 Option 3)

**Date:** 2026-09-01  
**Status:** Approved and frozen with OQ-012 option 3 on 2026-09-01  
**Baseline design:** `docs/superpowers/specs/2026-09-01-v0-2-real-world-validation-design.md`  
**Contracts:** additive EV-C010A in `docs/EXTERNAL_VALIDATION_CONTRACTS_V0_2.md`  
**Pilot evidence preserved:** `pilot_failure_report.json` (v1), `pilot_failure_report_v2.json` (v2)

## 1. Problem statement

Pilot v2 under transform identity `signal_diag.external_transform` `1.0.0` found 42
eligible clean SMARD periodic windows but zero alpha-pass windows. The even-order
formula scales injected harmonic energy with `alpha * (x^2 - mean(x^2))`, so
low-amplitude real captures produce negligible THD (~0.018%) and occasional
flat-top flags while F0 remains valid. Clipping selection (`q=0.03`) would still
pass. The study cannot materialize harmonic/combined B cases without a revised
transform that preserves validation gates.

## 2. Frozen unchanged

The following remain unchanged by this amendment:

- demonstration thresholds in `profile_s1_distortion` `1.0.0-demo` (1% clipping, 5% THD);
- transform `1.0.0` alpha candidate set `{0.10, 0.15, 0.20}`;
- validation rule: smallest global alpha that on **every** eligible validation master produces reportable order-2, THD > 5%, no flat-top/clipping, and valid F0;
- clipping quantile method, tail candidates `{0.03, 0.05, 0.10}`, and combined order (harmonic then clipping);
- reference analyzer `signal_diag.external_reference` `1.0.0`;
- transform identity `signal_diag.external_transform` `1.0.0` and function `inject_second_harmonic`;
- v1/v2 pilot failure reports and their transform-version references.

## 3. New transform identity

```text
transform_id:      signal_diag.external_transform
transform_version: 1.1.0
kind name:         second_harmonic_amplitude_normalized
```

Public function:

```python
inject_second_harmonic_amplitude_normalized(samples, alpha, post_gain) -> TransformResult
```

`TransformConfig` gains optional fields defaulting to legacy behavior:

```text
transform_id:      signal_diag.external_transform
transform_version: 1.0.0 | 1.1.0
```

New B-group materialization and pilot v3+ use `1.1.0`. Historical references to
`1.0.0` remain valid for v1/v2 failure artifacts.

## 4. Amplitude-normalized formula

Given canonical base samples `x[n]` (mono float32, finite, non-empty):

```text
a_ref = max(abs(x))
u[n]  = x[n] / a_ref
y_pre[n] = x[n] + alpha * a_ref * (u[n]^2 - mean(u^2))
y[n] = y_pre[n] * post_gain
```

Definitions:

- `a_ref` is the peak absolute amplitude of the **input** canonical base before
  harmonic injection; it is not a per-file loudness normalization of the stored
  master (EV-C009 still prohibits per-signal peak normalization of analysis WAVs).
- `u[n]` is a dimensionless normalized coordinate used only inside the transform.
- `post_gain` is the same globally frozen headroom scalar used for 1.0.0 (default
  pilot value `0.8` until validation re-freezes).

Combined transform `1.1.0`:

```text
y = clip_1.0.0( inject_1.1.0(x) )
```

Harmonic first, symmetric hard clipping second, identical to §9.5 ordering.

## 5. Rationale

For a sinusoid `x[n] = A sin(wt)`, the 1.0.0 perturbation scales as `alpha * A^2`,
so THD scales roughly with `alpha * A`. Real SMARD masters at low playback level
therefore fail the 5% THD gate even at `alpha=0.20`.

The 1.1.0 perturbation scales as `alpha * A`, making relative second-harmonic
injection **amplitude-invariant** across masters sharing the same waveform shape.
This preserves the even-order memoryless structure while matching the study intent:
a globally fixed `alpha` should produce comparable harmonic severity on every
eligible validation master.

## 6. Alpha candidates and validation gates

Transform `1.0.0` alpha candidates remain exactly `{0.10, 0.15, 0.20}`.

Transform `1.1.0` alpha candidates were expanded under OQ-012 option 1 on
2026-09-01 (EV-C010B) to exactly `{0.10, 0.15, 0.20, 0.25, 0.50, 0.75, 1.00}`.
No further extension is authorized by this amendment.

For each candidate `alpha`, a validation master passes the harmonic gate when
`analyze_reference` on the transformed window reports:

- `applicable == True` (valid F0 and harmonic analysis);
- `thd_percent > 5.0`;
- `flat_top_detected == False`;
- `clipping_ratio <= 0.01` (demo clipping threshold);
- `order_2_relative_amplitude` is not `None` and `> 0`.

Clean-master eligibility (unchanged from design §9.1) is evaluated on the
attenuated canonical base before injection.

Selection rule (unchanged): choose the **smallest** alpha passing on **every**
eligible validation master.

## 7. Migration from 1.0.0

| artifact | action |
|---|---|
| `inject_second_harmonic` | retain; no behavior change |
| EV-C010 | retain verbatim |
| pilot_failure_report.json / v2 | retain; document `transform_version: 1.0.0` |
| new pilot v3+ | use `1.1.0`; write new failure or success report without overwriting v1/v2 |
| sealed cases (future) | `TransformConfig.transform_version == 1.1.0` and parameters_identity prefix `signal_diag.external_transform/1.1.0/...` |

## 8. Parameters identity strings

```text
1.0.0 harmonic:  signal_diag.external_transform/1.0.0/second_harmonic/a{alpha}/pg{post_gain}
1.1.0 harmonic:  signal_diag.external_transform/1.1.0/second_harmonic_ampnorm/a{alpha}/pg{post_gain}
1.1.0 combined:  signal_diag.external_transform/1.1.0/combined/q{q}/a{alpha}/pg{post_gain}/lower
```

## 9. Stop gate

After implementation, re-run **development pilot only** (SMARD periodic masters,
clean-master gate, validation alpha selection) under `1.1.0`.

- If alpha still fails: write `pilot_failure_report_v3.json` and stop.
- If alpha passes: record selected parameters in this amendment's decision section
  and `source_decision_record.md`; do **not** materialize full 14+10 unless all
  gates pass.

## 11. Pilot v3 outcome (2026-09-01)

Development pilot v3 executed under transform `1.1.0` on frozen SMARD
`sinus_tones_48kHz` master windows (including `master_val_01` ch5 frames
416000–432000). Clean-master gate: **pass**. Alpha selection: **failed** — no
candidate in `{0.10, 0.15, 0.20}` achieves THD > 5% without flat-top/clipping
while keeping F0 valid and reportable order-2 under `external_reference` `1.0.0`.

Evidence: `docs/evaluations/v0_2_external_wav/validation/pilot_failure_report_v3.json`.

Materialization remains blocked at 0/14+0/10. Transform `1.0.0` and v1/v2
failure reports remain preserved.

## 12. Pilot v4 outcome (2026-09-01, OQ-012 option 1)

Development pilot v4 executed under transform `1.1.0` with EV-C010B expanded
alpha candidates `{0.10, 0.15, 0.20, 0.25, 0.50, 0.75, 1.00}` on 42 eligible
SMARD periodic windows (`sinus_tones_48kHz`, `exp_swept_sinus_10Hz_24kHz`;
`harm_sinus_48kHz` still fails clean gate).

Validation master: `master_val_01` (`sinus_tones_48kHz_ch10_ULA_2B.flac`,
frames 320000–336000, clean THD 0.0037%, F0 695.7 Hz).

| alpha | THD % | flat-top | clipping | gate |
|---:|---:|:---:|:---:|---|
| 0.10 | 0.65 | no | 0 | fail |
| 0.15 | 0.98 | no | 0 | fail |
| 0.20 | 1.31 | no | 0 | fail |
| 0.25 | 1.63 | no | 0 | fail |
| **0.50** | **selected** | no | 0 | **pass** |
| 0.75 | — | no | 0 | pass |
| 1.00 | — | no | 0 | pass |

**Alpha selection: passed** at `alpha=0.50` (smallest passing candidate).
Evidence: `docs/evaluations/v0_2_external_wav/validation/pilot_success_report_v4.json`.

Case materialization remains gated on remaining Task 11 checks. v1/v2/v3 failure
reports remain preserved.

## 13. Explicit non-actions

- no `final_external_test` access;
- no real model calls;
- no changes to `profile_s1_distortion`, DSP product paths, or `external_reference`;
- no overwrite of v1/v2 failure reports.
