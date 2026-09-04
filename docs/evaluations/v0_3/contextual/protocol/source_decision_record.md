# Source Decision Record — V0.3 Contextual Development (Task 11)

**Study:** `study_v0_3_contextual_dev_1`

**Catalog:** `v0.3-contextual-dev-1` `1.0.0`

**Recorded:** 2026-09-04

**Scope:** contextual **development** only (no validation / final test; no real-model run)

## Step 1 review (before acquisition)

| source | license | format / size | S1 role | decision |
|---|---|---|---|---|
| NSynth test JSON+WAV archive | CC BY 4.0 | `.tar.gz` ~349.5 MiB | clean tonal masters + controlled transforms | **approve** |
| ESC-10 clips (`100032`, `100038`, `101336`) | CC BY (ESC-10) | WAV ~441 KiB each | domain-out inconclusive | **approve** |
| SMARD cfg `0010` | research-use, no redistribution | ZIP ~378 MiB | n/a | **reject for committed WAV** |
| Pyramic preview WAVs | CC BY 4.0 | WAV ~70–127 KiB | speech digits | **reject for masters** (speech PII preference) |

Third-party class/instrument labels are **never** mapped to S1 causal truth. Positives use recorded controlled transforms (`hard_clip`, amplitude-normalized second-harmonic injection) on clean NSynth crops.

## Step 2 acquisition

Approved bytes were placed under `private/contextual_wav/acquired/` (gitignored).

| source_id | SHA-256 | bytes | notes |
|---|---|---:|---|
| `nsynth_test_jsonwav_archive` | `0f9ba5d62beba9ec4612f918d19f5e87a681822f1c566124f05fe8b27a51934c` | 349,501,546 | identical to prior approved external acquisition; copied into contextual cache |
| `esc10_100032_a0` | `f40a849a2375c8c63312a73dd2dd6c74007301fcc21b4be2ece29a642831e3d8` | 441,044 | same |
| `esc10_100038_a14` | `2faa39d8e59e8f292dfbdbe72bd8a00294f9535714b3c19b39904c2c17e14675` | 441,044 | same |
| `esc10_101336_a30` | `e738266e395e378102f74e0920b05ff5937543788420d5b2a6b8d3df8bdb3910` | 441,044 | same |

Index: `private/contextual_wav/acquired/acquired_index.json` (not committed).

## Masters used (≥4)

| parent_master_id | upstream note | window | product-DSP clean THD % |
|---|---|---|---:|
| `master_organ_a` | `organ_electronic_028-077-050` | 16000–24000 @16 kHz | ~0.11 |
| `master_bass_a` | `bass_electronic_025-056-075` | 16000–24000 | ~0.14 |
| `master_organ_b` | `organ_electronic_028-067-075` | 16000–24000 | ~0.39 |
| `master_bass_b` | `bass_electronic_025-059-050` | 16000–24000 | ~0.43 |
| `master_guitar_a` | `guitar_acoustic_021-077-050` | 16000–24000 | ~0.47 |

Positive budget: ≤2 positives per parent master (observed: organ_a 2, organ_b 2, bass_b 2, guitar_a 2, bass_a 1).

Natural-even / no-growth controls: adjacent-window pairs of clean masters (near-zero even-harmonic growth). Attempted richer NSynth notes failed `test_fundamental_invalid` under contextual DSP and were not forced.

## Qualification / calibration (once)

- Qualification: all 20 deterministic causal gates passed (`qualification_report.json`).
- Calibration candidates frozen `(0.5, 1.0, 2.0, 3.0, 5.0)` %; selected **largest** with 100% specificity and ≥90% sensitivity → **5.0%**.
- Profile freeze: `1.0.0-dev.1` → `1.0.0`, `rule_even_harmonic_growth_acceptable` threshold **5.0**.

### Profile SHA evidence

| state | version | growth threshold | SHA-256 |
|---|---|---:|---|
| pre-freeze | `1.0.0-dev.1` | 1.0 | `91aa587418c603d2d9da55880abd103d67bf1616d5381a5d2db72e847045afc9` |
| post-freeze | `1.0.0` | 5.0 | `491d2681ced99af1d9e2c2ea2385f23fa611d19063c6711a0e1467d90a687c38` |

## Forbidden actions observed

No real-model run; no ScriptedPlanner campaign; no validation split construction; V0.2 1%/5% distortion profile untouched.
