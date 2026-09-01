# Task 11 Validation Gate Report

**Study:** `v0.2-external-wav-validity-1`
**Recorded:** 2026-09-01
**Materialization commit:** `7993f0c`
**Gate:** Task 11 Step 8 — stop before `final_external_test`

## Executive summary

Task 11 Phase B/C pilot and Phase C development/validation materialization are
complete. Frozen transform `signal_diag.external_transform` `1.1.0` with
`alpha=0.50`, `q=0.03` produced exactly **14 development** and **10 validation**
cases. All deterministic gates passed (manifest validation, preservation,
fixed-pipeline baseline harness, external pytest 128/128).

**`final_external_test` was NOT accessed.** No new downloads were performed for
this gate. **No real model (`RealLLMPlanner`) was called.** Separate user
authorization is required before Task 12 final-data acquisition,
materialization, or Agent campaign execution.

---

## Selected configuration

| Parameter | Value |
|---|---|
| `transform_id` | `signal_diag.external_transform` |
| `transform_version` | `1.1.0` |
| harmonic `alpha` | `0.50` (smallest EV-C010B candidate passing validation master) |
| clipping `q` | `0.03` |
| `post_gain` | `0.8` |
| `attenuation` | `0.85` |
| `quantile_method` | `lower` |
| `rule_profile` | `profile_s1_distortion` `1.0.0-demo` |
| `external_scoring` | `signal_diag.external_scoring` `1.0.0` |
| `reference_analyzer` | `signal_diag.external_reference` `1.0.0` |

**Alpha selection evidence:** `validation/pilot_success_report_v4.json` (pilot v4
on SMARD validation master `master_val_01`, `sinus_tones_48kHz_ch10_ULA_2B`).

**Frozen transform record:**
`validation/study_v0_2_external_wav_validation_1/transform_config.json`
(frozen_at_utc `2026-09-01T13:34:21.245893+00:00`).

---

## Materialized study bundles

| Stage | Path | Manifest cases | Committed WAVs |
|---|---|---:|---:|
| development | `development/study_v0_2_external_wav_dev_1/` | 14 | 14 |
| validation | `validation/study_v0_2_external_wav_validation_1/` | 24 (14 dev copy + 10 val) | 48 on disk* |

\*Validation study directory also contains 24 WAV files under
`assets/final_external_test/` that reuse development/validation case IDs.
These are **not** `final_external_test` split cases: no `final_external_test`
entries appear in any manifest, no unseen group keys were materialized, and
Task 12 final-data authorization was not granted.

### Case composition (by source group)

**Development (14)**

| Group | Count | Sources | Classes |
|---|---:|---|---|
| A — public real-capture | 3 | Pyramic `fq_sample0/1/2` | clean, inconclusive, weak/ambiguous |
| B — semi-real paired | 8 | SMARD `sinus_tones` ch9 + ch22 | 2 masters × (clean, clipping, harmonic, combined) |
| C — conservatism stress | 3 | ESC-10 (2), Pyramic (1) | inconclusive ×2, unknown/ambiguous ×1 |

**Validation (10)**

| Group | Count | Sources | Classes |
|---|---:|---|---|
| A — public real-capture | 3 | Pyramic `fq_sample3/4` | clean, inconclusive, weak/ambiguous |
| B — semi-real paired | 4 | SMARD `sinus_tones` ch10 | 1 master × (clean, clipping, harmonic, combined) |
| C — conservatism stress | 3 | ESC-10 (2), NSynth guitar | inconclusive ×2, unknown/ambiguous ×1 |

B-group masters:

| `parent_master_id` | Split | SMARD member | F0 band |
|---|---|---|---|
| `master_dev_01` | development | `sinus_tones_48kHz_ch9_ULA_1B` | 400–1000 Hz |
| `master_dev_02` | development | `sinus_tones_48kHz_ch22_ULA_6C` | 400–1000 Hz |
| `master_val_01` | validation | `sinus_tones_48kHz_ch10_ULA_2B` | 400–1000 Hz |

---

## Source / device / environment / F0 coverage

Coverage is computed from manifest `capture_coverage` fields and recorded in
each study's `validation_report.json`. `meets_target=false` means the design
selection target (§5–§9 of the real-world validation design) is not yet met
across the full 24+10 pilot scope; this is expected at the validation gate.

### Development (`validation_report.json`, stage `development`)

| Dimension | Documented values | Unavailable | Meets design target |
|---|---|---|---|
| acoustic_environment | `anechoic` (Group A only) | Groups B, C | no |
| distance | `4m` (Group A only) | Groups B, C | no |
| loudspeaker | `spk_mid` (Group A only) | Groups B, C | no |
| microphone_position | `mic_array` (Group A only) | Groups B, C | no |
| playback_level | `playback_nominal` (Group A only) | Groups B, C | no |
| f0_band | `400-1000` | 1.2–3 kHz band not represented | no |

### Validation (combined 24-case manifest, stage `validation`)

| Dimension | Documented values | Unavailable | Meets design target |
|---|---|---|---|
| acoustic_environment | `anechoic` (Group A only) | Groups B, C | no |
| distance | `4m` (Group A only) | Groups B, C | no |
| loudspeaker | `spk_mid` (Group A only) | Groups B, C | no |
| microphone_position | `mic_array` (Group A only) | Groups B, C | no |
| playback_level | `playback_nominal` (Group A only) | Groups B, C | no |
| f0_band | `100-300`, `400-1000` | 1.2–3 kHz band not represented | no |

### Device / source families (actual)

| Source family | Device / instrument | Splits used | Notes |
|---|---|---|---|
| Pyramic | Pyramic microphone array | dev A, val A | CC BY 4.0; anechoic 4 m capture documented |
| SMARD cfg 0010 | SMARD ULA microphone array | dev B, val B | research-use; position/distance/level unavailable in metadata |
| ESC-10 subset | field recording (device unavailable) | dev C, val C | CC BY; non-periodic conservatism probes |
| NSynth test | synthetic guitar (not a physical device) | val C only | CC BY 4.0; unknown-class stress |

SMARD production host: `shares01.portal.aau.dk` (OQ-012 option 1, catalog
`1.0.2`). Full decision history:
`protocol/source_decision_record.md`.

---

## Disk usage summary

| Location | Files | Approximate size | Git status |
|---|---|---:|---|
| `development/study_v0_2_external_wav_dev_1/` | 16 | ~2.0 MiB | committed |
| `validation/study_v0_2_external_wav_validation_1/` | 82 | ~8.1 MiB | committed |
| `private/external_wav/acquired/` | 12 sources | ~728.5 MiB | gitignored local cache |
| Campaign cap | — | 5 GiB | not exceeded |

Raw SMARD archive and upstream assets remain in `private/external_wav/` only.

---

## License decisions

| Source | License / terms | Redistribution |
|---|---|---|
| SMARD cfg 0010 | research-use-no-redistribution | local cache only; no redistribution of original assets |
| Pyramic previews | CC BY 4.0 | derived mono PCM24 study WAVs committed with provenance |
| ESC-10 subset | CC BY | derived PCM24 allowed with attribution |
| NSynth test archive | CC BY 4.0 | selected notes extracted locally only |

Terms snapshots recorded in `protocol/source_catalog.json` `1.0.2`.

---

## Exclusions and retained failures

**Excluded from pilot materialization**

- all `final_external_test` split sources and unseen group keys (Task 12 gate)
- full 18 GiB SMARD tree beyond cfg `0010`
- `harm_sinus_48kHz` windows (natural THD 141–356%; fail clean-master gate)
- Zenodo Pyramic archives (`zenodo.org` not an approved host)
- non-ESC-10 ESC-50 rows
- GitHub preview IEEE-float sweeps/noise (integer-PCM loader boundary)

**Retained pilot failure evidence (not overwritten)**

- `validation/pilot_failure_report.json` (v1)
- `validation/pilot_failure_report_v2.json` (v2)
- `validation/pilot_failure_report_v3.json` (v3)

Pilot v4 success: `validation/pilot_success_report_v4.json`.

---

## Deterministic gate results

| Gate | Result | Evidence |
|---|---|---|
| Manifest validation (development) | **PASS** (`valid: true`, 14 cases) | `development/study_v0_2_external_wav_dev_1/validation_report.json` |
| Manifest validation (validation) | **PASS** (`valid: true`, 24 cases checked) | `validation/study_v0_2_external_wav_validation_1/validation_report.json` |
| Transform reproducibility | **PASS** (`reproduced_twice: true`) | `validation/study_v0_2_external_wav_validation_1/pilot_reproducibility.json` |
| Fixed-pipeline baseline harness | **PASS** (24 attempts, sealed manifest) | `baseline_runner_report.json`; seal `c52afcea…aed35` |
| External pytest suite | **PASS** (128/128) | `tests/evaluation/external/` (verified 2026-09-01, Python 3.11) |
| Preservation checksums | **PASS** | manifest SHA-256s in `pilot_reproducibility.json` |

---

## Round 1 review and Round 2 blind package

| Artifact | Path |
|---|---|
| Round 1 labels | `validation/study_v0_2_external_wav_validation_1/round1_review.json` |
| Round 2 blind package | `validation/study_v0_2_external_wav_validation_1/blind_review_package.json` |
| Earliest Round 2 timestamp | `2026-09-15T12:00:00+00:00` (`blind_review_earliest_round2.txt`) |

Round 1 completed 2026-09-01 for all 24 manifest cases (14 development +
10 validation). Round 2 may not begin before the 14-day waiting period.

---

## Explicit non-actions (this gate)

- **`final_external_test` NOT accessed** — no download, manifest entry, unseen
  group materialization, or truth-label inspection for final split.
- **No real model calls** — `RealLLMPlanner` / `run-agent` not invoked;
  `ScriptedPlanner` not used as a silent fallback.
- **No new network acquisition** — this gate used committed study bundles and
  existing `private/external_wav/` cache only.
- **No push** — repository push not authorized.

---

## Authorization request (Task 12)

Before proceeding:

1. **Round 1 review** — human review of `round1_review.json` labels.
2. **14-day wait** — earliest Round 2: `2026-09-15T12:00:00+00:00`.
3. **Final-data authorization** — explicit approval to acquire and materialize
   28 unseen `final_external_test` cases from approved unseen group keys.
4. **Real-model authorization** (separate) — required before any Agent campaign
   on sealed final data.
