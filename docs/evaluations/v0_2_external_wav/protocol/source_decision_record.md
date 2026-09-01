# Source Decision Record — Phase B/C Pilot (Task 11)

**Study:** `v0.2-external-wav-validity-1`
**Catalog:** `v0.2-external-wav-dev-validation-pilot-1` `1.0.2`
**Recorded:** 2026-09-01T13:30:00Z (pilot v2)
**Scope:** development + validation pilot only (no `final_external_test`)

## Production host policy (OQ-012 option 1 — approved 2026-09-01)

SMARD raw configuration archives are served from `shares01.portal.aau.dk`, not
`www.es.aau.dk`. OQ-012 option 1 approves this host for production catalog
`1.0.2` with:

- authoritative AAU source page:
  https://www.es.aau.dk/research/audio-analysis-lab/smard/download
- production download URL:
  https://shares01.portal.aau.dk/smard/data/0010.zip
- recorded SHA-256, byte size, and acquisition time in the table below
- `research-use-no-redistribution`; local cache only under `private/external_wav/`
- no redistribution of original SMARD assets

`shares01.portal.aau.dk` is listed in `source.py` `_APPROVED_HOSTS`.

## Sources selected (pre-acquire estimates)

| source_id | URL | est./max bytes | license/terms | redistribution |
|---|---|---:|---|---|
| `smard_cfg_0010_raw` | https://shares01.portal.aau.dk/smard/data/0010.zip | 378 MB / 450 MB | research-use (SMARD download page) | no redistribution; local cache only |
| `pyramic_fq_sample0`–`4` | GitHub raw preview WAVs | ~100 KB each / 512 KB | CC BY 4.0 | reference + derived PCM24 allowed |
| `esc10_*` (5 clips) | GitHub raw ESC-50 audio | ~441 KB each / 1 MiB | CC BY (ESC-10 subset) | derived PCM24 allowed with attribution |
| `nsynth_test_jsonwav_archive` | GCS `nsynth-test.jsonwav.tar.gz` | 349 MB / 400 MB | CC BY 4.0 | extract selected notes locally only |

**Excluded from this pilot:** all `final_external_test` material; full 18 GiB SMARD tree;
Pyramic Zenodo archives (host `zenodo.org` not approved); ESC-50 non-ESC-10 rows.

## Observed acquisition (2026-09-01)

All files acquired via `acquire_assets(..., allow_network=True)` into
`private/external_wav/acquired/` (gitignored). Index:
`private/external_wav/acquired/acquired_index.json`.

| source_id | SHA-256 | bytes | acquired evidence |
|---|---|---:|---|
| `smard_cfg_0010_raw` | `4c9c5afcbd07771ca0a8afc98ae61aa766a831d8668d535b1d31ee91b22345bb` | 378,277,705 | `acquire` stdout + index |
| `pyramic_fq_sample0` | `421a9f164b0e85c504b22ae36e7d652a92897b8c719b4130e81a98bc171871ed` | 127,020 | index |
| `pyramic_fq_sample1` | `7461143fe86efee696ce7a64fa8655d77e1fe76362cca0e851867497dd805607` | 102,036 | index |
| `pyramic_fq_sample2` | `d16d8a235063b53149631880f520989dd66d776b50d7d68cb977114ff062352f` | 71,110 | index |
| `pyramic_fq_sample3` | `980d38abaccf1e0ccf595d9ffbac2d0636018e4c947f4e99ae28e7aa89795a76` | 75,616 | index |
| `pyramic_fq_sample4` | `7bea85fd9555e7a2af79879235cd52d53ee1997803cfdcfd980244e879074e45` | 101,012 | index |
| `esc10_100032_a0` | `f40a849a2375c8c63312a73dd2dd6c74007301fcc21b4be2ece29a642831e3d8` | 441,044 | index |
| `esc10_100038_a14` | `2faa39d8e59e8f292dfbdbe72bd8a00294f9535714b3c19b39904c2c17e14675` | 441,044 | index |
| `esc10_101336_a30` | `e738266e395e378102f74e0920b05ff5937543788420d5b2a6b8d3df8bdb3910` | 441,044 | index |
| `esc10_28135_a11` | `4d04b84d490c4d9ab28a52c4c96d1b14c2f8b132fc4be38166197ae814920742` | 441,044 | index |
| `esc10_17367_a10` | `d732acd2e0c7c40405968010f49f250740c86998fc416eff2ed5330fc8c89dea` | 441,044 | index |
| `nsynth_test_jsonwav_archive` | `0f9ba5d62beba9ec4612f918d19f5e87a681822f1c566124f05fe8b27a51934c` | 349,501,546 | index |

**Total acquired (pilot):** ~728.5 MiB (within 5 GiB campaign cap).

### Terms snapshot SHA-256

Recorded in `source_catalog.json` per `terms_url` fetch on 2026-09-01 (GitHub pages,
SMARD download page, Magenta NSynth page).

## Derivation / reference pilot results

### Pilot v1 (stepped sinus — blocked)

| parent_master_id | member | stable window | F0 band | clean THD % | notes |
|---|---|---|---|---:|---|
| `master_dev_01` | `sinus_tones_48kHz_ch1_ULA_1A.flac` | frames 320000–336000 @ 48 kHz | 400–1000 Hz | 0.034 | eligible clean master |
| `master_dev_02` | `sinus_tones_48kHz_ch2_ULA_2A.flac` | frames 400000–416000 @ 48 kHz | 1200–3000 Hz | 0.018 | eligible clean master |
| `master_val_01` | `sinus_tones_48kHz_ch5_ULA_5A.flac` | scanned eligible | 400–1000 Hz | 0.019 | eligible clean master |

Alpha selection failed on all three (injected THD remained ~0.018% with flat-top flags).

### Pilot v2 (OQ-012 options 1+2 — periodic re-scan, blocked)

Material classes scanned in SMARD cfg `0010` archive (independent clean-master gate
per window; filenames do not establish causal truth):

| material class | eligible clean windows | alpha-pass windows | notes |
|---|---:|---:|---|
| `harm_sinus_48kHz` | 0 | 0 | natural THD 141–356%; reportable order-2 present; fails THD < 5% clean gate |
| `sinus_tones_48kHz` | 22 | 0 | clean THD 0.004–0.28%; alpha injection still ~0.018% THD with flat-top |
| `exp_swept_sinus_10Hz_24kHz` | 20 | 0 | clean THD 0.018–0.28%; alpha injection fails same as v1 |

**Total eligible periodic windows:** 42. **Alpha-pass windows:** 0.

Representative validation candidate (lowest clean THD among sinus_tones):

| parent_master_id | member | F0 Hz | clean THD % |
|---|---|---:|---:|
| `master_val_01` | `sinus_tones_48kHz_ch5_ULA_5A.flac` | 905.7 | 0.019 |

### Global transform selection (validation rule)

| parameter | candidates tested | result |
|---|---|---|
| clipping `q` | 0.03, 0.05, 0.10 | **Would select `q=0.03`** on validation master (flat-top + clipping ratio > 1% demo threshold) |
| harmonic `alpha` | 0.10, 0.15, 0.20 | **FAILED** — no eligible periodic master passes alpha gate under frozen `signal_diag.external_reference` 1.0.0 |
| `post_gain` | 0.8 (frozen) | unchanged |
| `attenuation` | 0.85 (frozen) | unchanged |

### Pyramic speech stress (A/C probe)

Voiced windows in `fq_sample0/1/2` reach `applicable=True` but natural THD is 52–199%,
failing B-master cleanliness rules. GitHub preview float sweeps/noise are IEEE float
(format tag 3) and are excluded by the integer-PCM loader boundary.

## Pilot stop gate (Task 11 Step 4/8)

**Status: BLOCKED — pilot v2 failed alpha selection; OQ-012 reopened.**

Per spec/plan and user decision: when no `alpha` candidate satisfies validation rules,
retain the pilot failure and stop (do not fabricate harmonic/combined
`strong_ground_truth` cases). Option 3 (transform revision) was not authorized.

Failure reports:

- `validation/pilot_failure_report.json` (v1)
- `validation/pilot_failure_report_v2.json` (v2)

## Pilot v3 (OQ-012 option 3 — blocked)

Transform `signal_diag.external_transform` `1.1.0` implemented and pilot v3
re-ran on the same SMARD sinus_tones validation master window as v1/v2.

| parameter | candidates | result |
|---|---|---|
| harmonic `alpha` | 0.10, 0.15, 0.20 | **FAILED** under 1.1.0 — THD remains 0.30–0.59% on validation master (flat-top at 0.10) |
| transform version | 1.1.0 | amplitude-normalized even-order (additive) |
| `post_gain` | 0.8 | unchanged |

Failure report: `validation/pilot_failure_report_v3.json` (does not overwrite v1/v2).

Extrapolation: THD > 5% would require alpha ~0.9, outside frozen candidate set {0.10, 0.15, 0.20}.

**Status: BLOCKED — pilot v3 failed alpha selection under transform 1.1.0.**

## Pilot v4 (OQ-012 option 1 — alpha selected)

Transform `1.1.0` with EV-C010B expanded alpha candidates
`{0.10, 0.15, 0.20, 0.25, 0.50, 0.75, 1.00}` re-ran on 42 eligible SMARD
periodic windows. Validation master `master_val_01`
(`sinus_tones_48kHz_ch10_ULA_2B`, frames 320000–336000).

| parameter | candidates | result |
|---|---|---|
| harmonic `alpha` | 0.10–1.00 (7 candidates) | **PASSED at `alpha=0.50`** — smallest candidate passing every gate |
| transform version | 1.1.0 | amplitude-normalized even-order (additive) |
| `post_gain` | 0.8 | unchanged |

Success report: `validation/pilot_success_report_v4.json` (does not overwrite v1/v2/v3).

Candidates 0.10–0.25 fail THD > 5% on the validation master; 0.50–1.00 pass.

**Status: alpha gate cleared — 14 development + 10 validation cases materialized (2026-09-01).**

### Frozen global transform configuration (materialized)

| parameter | value |
|---|---|
| `transform_id` | `signal_diag.external_transform` |
| `transform_version` | `1.1.0` |
| harmonic `alpha` | `0.50` |
| clipping `q` | `0.03` |
| `post_gain` | `0.8` |
| `attenuation` | `0.85` |
| `quantile_method` | `lower` |

Recorded in `validation/study_v0_2_external_wav_validation_1/transform_config.json`.

### Materialized study bundles

| stage | path | cases |
|---|---|---:|
| development | `development/study_v0_2_external_wav_dev_1/` | 14 |
| validation | `validation/study_v0_2_external_wav_validation_1/` | 10 validation-only (+ 14 dev copy in manifest) |

B-group: 2 development masters × 4 variants + 1 validation master × 4 variants (clean/clipping/harmonic/combined). Group isolation preserved per EV contracts.

Deterministic gates passed: manifest validation (development + validation), external pytest (128), fixed-pipeline baseline harness, preservation checksums.

## Explicit non-actions

- No `final_external_test` download, manifest, or audio inspection.
- No `run-agent` / `RealLLMPlanner` calls.
- No fabricated cases beyond approved transform provenance.

## Round 1 review / blind package

Generated under `validation/study_v0_2_external_wav_validation_1/` (`round1_review.json`, `blind_review_package.json`).

### Protocol amendment (2026-09-01)

User authorization supersedes the mandatory 14-day Round 2 gate. The study adopts
`single_reviewer_provenance_audit` mode per
`docs/superpowers/specs/2026-09-01-v0-2-external-single-reviewer-amendment.md`.
Round 1 labels remain authoritative; inter-rater agreement and Cohen kappa are
`not_evaluated`. Historical blind package artifacts are retained for audit only.

## Commit recommendation

Materialization complete; commit authorized when gates pass.

Raw audio remains in `private/external_wav/` (gitignored).
