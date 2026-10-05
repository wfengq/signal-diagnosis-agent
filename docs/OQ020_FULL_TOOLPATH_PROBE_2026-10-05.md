# OQ-020 full tool-path clipping probe (2026-10-05)

**Status:** read-only reproduction probe. Not layer-1 characterization approval. No floor
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

Also: white noise (RMS 0.5, seed 0, hard-limited to ±1.0) and optional sub-full-scale
`generate_clipped_sine` at clip levels 0.5 / 0.9 / 0.98 (440 Hz, amplitude 0.9, 48 kHz).

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

440 Hz, amplitude 0.9, 48 kHz, `generate_clipped_sine`:

| Clip level | `clipping_ratio` (direct & PCM32 tool) | `clipping_mechanism` | `full_scale_sample_count` |
|------------|----------------------------------------|----------------------|---------------------------|
| 0.5 | 0.625 | false | 0 |
| 0.9 | 0.0 | false | 0 |
| 0.98 | 0.0 | false | 0 |

Clip 0.5 shows strong flat-top ratio without full-scale mechanism (same flag pattern as
clean-sine false plateaus). Levels 0.9 / 0.98 with input amplitude 0.9 do not produce a
reportable flat-top ratio here (peak at 0.9; no hard clipping below peak).

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
