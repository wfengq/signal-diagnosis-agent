# OQ-020 full tool-path clipping probe (2026-10-05)

**Status:** read-only reproduction probe, extended in design review (near-threshold and
one-step sections; sub-full-scale rows corrected). Not layer-1 characterization approval. No floor
values. V0.3 §23 implementation remains unauthorized.

**Branch context:** `cursor/oq020-full-toolpath-probe-8b52` from `e659170`.

**Script:** `scripts/probe_oq020_clipping_toolpath.py`

**Machine-readable summary:** `docs/OQ020_FULL_TOOLPATH_PROBE_2026-10-05.json`

## What was measured

The OQ-020 grid (60 cells = 2 sample rates × 6 frequencies × 5 amplitudes; four start
phases per cell; 2.0 s duration) was exercised two ways:

1. **Direct DSP baseline** — `analyze_clipping` on `generate_sine` float samples before
   any WAV step (same as the original fb38314 probe).
2. **Full regression workbench path** — float sine → integer PCM WAV (16 / 24 / 32-bit,
   full-scale encode, no peak normalize) → `load_wav_bytes` → `InMemorySignalRepository`
   → `MeasurementSelection` (clipping + harmonic, left channel, shared `TimeRange`) →
   `measure_output` → clipping `ToolResult` fields.

Per cell we aggregate across phases: any `clipping_ratio > 0`, max ratio, flags, and
**full-scale sample count** on decoded mono (`|x| ≥ 0.99` in runs of length ≥ 2, same
criterion as §23 design).

Also: white noise (RMS 0.5, seed 0, hard-limited to ±1.0); sub-full-scale
`generate_clipped_sine` at clip levels 0.5 / 0.9 / 0.98 (440 Hz, pre-clip amplitude 1.2,
48 kHz); and, added in review, clean sines with peak near the threshold and a one-step
16-bit sweep (sections below).

## Headline counts (clean sines)

| Path | Nonzero cells (any phase `clipping_ratio > 0`) | Cells differing from direct (aggregate) |
|------|-----------------------------------------------|----------------------------------------|
| Direct DSP | **29 / 60** | — |
| Tool path PCM32 | **29 / 60** | **0** |
| Tool path PCM24 | **29 / 60** | **1** |
| Tool path PCM16 | **31 / 60** | **25** |

**OQ-020 claim reproduced:** yes — direct DSP is **29 / 60**, matching OPEN_QUESTIONS.md
and the independent review cited there.

**WAV quantization:**

- **32-bit:** tool-path cell counts and per-cell max ratios match direct DSP on this grid
  (bit-identical clipping metrics after round-trip).
- **24-bit:** same 29 / 60 nonzero pattern; one cell differs slightly in max ratio
  (`48000_997.0_0.01`: direct max ≈ 0.022000, tool ≈ 0.021875).
- **16-bit:** two cells flip from “all phases zero” to nonzero (`44100_100.0_0.9`,
  `44100_220.0_0.2`); many low-amplitude / low-frequency cells show materially different
  max ratios (quantization widens or narrows flat-top plateaus).

## Example cells (direct vs tool path)

### 100 Hz, amplitude 0.01, 48 kHz (`clipping_ratio` by phase)

| Phase (rad) | Direct DSP | PCM32 tool | PCM16 tool |
|-------------|------------|------------|------------|
| 0.0 | 0.554167 | 0.554167 | 0.520833 |
| 0.1 | 0.558333 | 0.558333 | 0.520833 |
| 1.0 | 0.558094 | 0.558094 | 0.516458 |
| 2.0 | 0.557969 | 0.557969 | 0.541323 |

OQ-020 cited ≈ 0.55 at this cell; all paths show large false flat-top ratios with
`flat_top_detected=true`, `clipping_mechanism=false`.

### 100 Hz, amplitude 0.9, 48 kHz (phase sensitivity)

| Phase (rad) | Direct `clipping_ratio` |
|-------------|-------------------------|
| 0.0 | **0.0125** |
| 0.1 | 0.0 |
| 1.0 | 0.0 |
| 2.0 | 0.0 |

Matches the OQ-020 note (0.0125 at phase 0 only). PCM32 tool path matches these values;
PCM16 can introduce nonzero ratios at other phases on 44.1 kHz cells.

### 50 Hz, amplitude 0.9, 48 kHz

Direct max across phases ≈ **0.01458** (phases 0.1–2.0 at 0.0125; phase 0.0 slightly
higher), consistent with OQ-020’s 0.0125–0.0146 range.

## White noise (RMS 0.5, seed 0, limited to full scale)

| Path | `clipping_ratio` | `clipping_mechanism` | `full_scale_sample_count` |
|------|------------------|----------------------|---------------------------|
| Direct DSP | **0.004375** | true | 420 |
| Tool PCM16/24/32 | **0.004375** | true | 420 |

Matches OQ-020’s ≈ 0.004; valid ratio on non-periodic input (no N/A path).

## §23 design assumption: full-scale count on clean sines

On **all 60 clean-sine cells**, `max_full_scale_sample_count` across phases is **0** for
direct DSP and for **each** tool-path bit depth (16 / 24 / 32).
`full_scale_detected` stays false on clean sines; false positives are flat-top only.

## Sub-full-scale clipped sine (mechanism / full-scale flags)

440 Hz, 48 kHz, `generate_clipped_sine` with pre-clip amplitude **1.2**, so every row is
genuinely clipped. (The first version of this probe used amplitude 0.9, for which clip
levels 0.9 and 0.98 do not clip at all; those two rows were not a test and are replaced.)

| Clip level | `clipping_ratio` (direct & PCM32 tool) | `flat_top_detected` | `clipping_mechanism` | `full_scale_sample_count` |
|------------|----------------------------------------|---------------------|----------------------|---------------------------|
| 0.5 | 0.725 | true | false | 0 |
| 0.9 | 0.4617 | true | false | 0 |
| 0.98 | 0.3917 | true | false | 0 |

Genuine clipping below the threshold has the same flag pattern as clean-sine false
plateaus (`flat_top_detected=true`, `clipping_mechanism=false`) and a full-scale count of
0. It is invisible to the §23 full-scale fact, as D043 records.

## Clean sines with peak near the threshold (added in review)

The 60-cell grid stops at amplitude 0.9, so a full-scale count of 0 there says nothing
about §23. This section runs unclipped sines with peaks 0.985–1.0 at 48 kHz through the
tool path at 16 / 24 / 32-bit, four start phases each. Counted = samples at or above 0.99
in runs of at least 2; uncounted = at or above 0.99 in shorter runs.

| Frequency | Peak | Counted by phase (PCM16) | Counted (PCM24 = PCM32 unless noted) | Uncounted (PCM32) |
|-----------|------|--------------------------|--------------------------------------|-------------------|
| 100 Hz | ≤ 0.99 | 0 | 0 | 0, except peak 0.99: 400 at phase 0 |
| 100 Hz | 0.9905 | 2000 / 1600 / 1600 / 2000 | 2000 at all phases | 0 |
| 100 Hz | 0.992 | 3600 / 4000 / 4000 / 4000 | same | 0 |
| 100 Hz | 0.995 | 6000 / 6000 / 6400 / 6000 | 6000 / 6400 / 6400 / 6000 | 0 |
| 997 Hz | 0.9905, 0.992 | 0 | 0 | about 1940 and 3884 |
| 997 Hz | 0.9925 | 640 at all phases | 704 / 704 / 696 / 704 | about 3636 |
| 997 Hz | 0.995 | 4240 at all phases | 4288 / 4288 / 4280 / 4288 | about 1844 |
| 2000 Hz | 0.9905–1.0 | 0 | 0 | 0 or 8000 depending on phase |

What this shows:

- An unclipped sine with peak above 0.99 is counted. The fact measures level reaching the
  threshold, not flattening.
- The peak at which the state turns to "yes" moves with frequency: just above 0.99 at
  100 Hz, between 0.992 and 0.9925 at 997 Hz, and never up to peak 1.0 at 2 kHz on these
  four phases (24 samples per period; over-threshold samples are isolated).
- The count moves with start phase alone by up to 400 samples (one sample per peak), and
  with bit depth (997 Hz, peak 0.9925: 640 at 16-bit, about 704 at 24/32-bit).
- 24-bit and 32-bit agree on counted samples in every row. 16-bit differs near the
  threshold; the loader scales 16-bit codes by 1/32768.
- On these four phases no cell changed state with phase alone. That is a property of this
  small grid, not evidence that phase cannot flip the state.
- In every row the tool's `full_scale_detected` equals "counted > 0".

## One 16-bit step across the threshold (added in review)

100 Hz, 48 kHz, start phase π/480, 2 s, 41 amplitudes from 0.98990 to 0.99030 in steps of
0.00001, plus 0.990011. For each: the sine rounded to int16, every sample moved one code
away from zero, and every sample moved one code toward zero; each written as 16-bit WAV
and measured through the tool path.

| Amplitude | Baseline counted / peak | One step away from zero | One step toward zero |
|-----------|-------------------------|-------------------------|----------------------|
| 0.990030, 0.990040, 0.990050 | 0 / 0.9899902 | **800** / 0.9900208 | 0 |
| 0.990060, 0.990070, 0.990080 | counted (state yes) | counted | **0** |
| 0.990011 | 0 / 0.9899597 | 0 / 0.9899902 | 0 |

A difference of one quantization step, which §23.4 tolerates, moves the state across the
boundary in both directions for baselines whose peak is within one step of the threshold.
In the no → yes rows the baseline has peak below the threshold and no over-threshold
sample at all, so only the §23.4 fixed minimum (`peak_abs >= threshold - step`,
0.9899695 at 16-bit) puts it inside the critical zone. The baseline peak 0.9899902
satisfies that minimum, so §23 as registered would not report a regression here.

Correction to the design record: design §13 cites amplitude 0.990011 for this effect
(0 → 800). Through the real tool path that amplitude does not flip; the cited figure came
from a simulated rounding that scaled codes differently from the loader. The effect is
real and appears at 0.990030–0.990050.

## How to re-run

```bash
python3 scripts/probe_oq020_clipping_toolpath.py --out-dir docs
python3 scripts/probe_oq020_clipping_toolpath.py --quick --out-dir /tmp/oq020_smoke
python3 -c "import scripts.probe_oq020_clipping_toolpath"
```

## Disclaimer

This document records a **probe** for regression workbench path fidelity relative to the
original OQ-020 direct-DSP measurements. It does not approve characterization materials,
set comparison floors, or authorize §23 implementation.
