# Signal Diagnosis Agent — Additive External Validation Contracts V0.2

**Document:** `EXTERNAL_VALIDATION_CONTRACTS_V0_2.md`
**Contract version:** `external-validation-0.2`
**Status:** Approved for Phase A protocol freeze on branch
`codex/v0.2-real-world-validation`
**Scope:** Additive contracts for the V0.2 external WAV validity study only
**Design:** `docs/superpowers/specs/2026-09-01-v0-2-real-world-validation-design.md`
**Baseline:** Git commit `605c8a8`; release tag `v0.2.0` on peeled commit `ff16e2a`

---

## 1. Contract Policy

These contracts define the additive public surface for the external WAV validity
study. They extend — but do not amend — frozen `docs/CONTRACTS_V0_2.md`.

If a conflict appears between this document and `CONTRACTS_V0_2.md`, the frozen
V0.2 product contract wins. External study behavior must consume, not rewrite,
accepted V0.2 interfaces.

Implementation must not silently rename modules, functions, arguments, study
identities, checksum policies, or preservation paths defined here.

If a genuine defect is found:

1. do not silently work around the contract;
2. record the issue in `docs/OPEN_QUESTIONS.md`;
3. propose the smallest additive correction and its test impact;
4. obtain explicit approval before changing the external public surface.

Private helpers inside `signal_diag.evaluation.external` remain implementation
details unless exported from `__init__.py`.

---

## 2. Immutable V0.2 Assets, Identities, Paths, and Tag

### EV-C001 — Protected historical asset directories

The following tracked directories are immutable study inputs, not study outputs:

- `docs/evaluations/phase4_3_1/development/`
- `docs/evaluations/phase4_3_1/official/`
- `docs/demo/phase5/v0_2_acceptance/`

The external study may read and audit these paths but must not overwrite,
rewrite, relabel, rerun, or repackage their contents.

### EV-C002 — Frozen product identity files

The following single-file identities are immutable:

- `src/signal_diag/agent/prompts.py`, including prompt identity
  `v0.2-s1-planner-8.1` and SHA-256
  `f2f0a81cc8f36f0301ee67c43e692886e86f9aa9136adeea4d592707133423ca`;
- `src/signal_diag/evaluation/scoring.py`, including scoring identity
  `signal_diag.scoring` `2.0.0`;
- `src/signal_diag/rules/profiles/s1_distortion_v1.yaml`, including
  `profile_s1_distortion` `1.0.0-demo` with 1% clipping and 5% THD
  demonstration thresholds.

The external study must not modify these files or describe their demonstration
thresholds as industry standards or SLAs.

### EV-C003 — Preservation audit path and record format

The canonical preservation audit lives at:

```text
docs/evaluations/v0_2_external_wav/protocol/protected_assets.sha256
```

Each record is one line:

```text
<64 lowercase hex SHA-256>  <forward-slash repo-relative path>
```

Records are sorted ordinally by path using forward slashes. File records cover
every tracked file under EV-C001 and EV-C002. Tag records use separate logical
paths:

```text
git/tag/v0.2.0
git/commit/v0.2.0
```

where `git/tag/v0.2.0` is the annotated tag object hash and
`git/commit/v0.2.0` is the peeled commit hash.

### EV-C004 — Release tag immutability

Tag `v0.2.0` must remain on peeled commit `ff16e2a`. The external study must
not move, replace, or rewrite the tag. Any preservation audit must verify both
the tag object hash and the peeled commit hash through EV-C003 records.

---

## 3. Source Terms, Provenance, Checksums, and Redistribution

### EV-C005 — Authoritative source requirement

Every selected public source must have an official project page, institutional
repository, authoritative code/data repository, or original paper. A convenience
mirror alone is insufficient. Approved host policy is frozen in the source
catalog; adding a host requires a design amendment and catalog version change.

### EV-C006 — Complete provenance record

Every study case requires a provenance record with at least:

- opaque `case_id` that reveals no source or truth to the Planner;
- `split`: `development`, `validation`, or `final_external_test`;
- `source_group`: `A`, `B`, or `C`;
- official source name, version/record ID, URL, citation, and access timestamp;
- license or terms classification and redistribution decision;
- upstream asset ID and upstream source-recording/group ID;
- original filename stored evaluator-side only;
- original file SHA-256 and byte count;
- source sample rate, bit depth, channel count, frames, and duration;
- derivation tool identity, parameters, channel selection, crop interval, and
  derived SHA-256;
- capture configuration identifiers available from the source;
- `parent_master_id` for every B asset;
- transformation identity and parameters for B assets;
- label confidence, eligible metric families, review references, and
  adjudication result;
- attribution and repository redistribution permission.

### EV-C007 — Checksum and digest immutability

Original and derived SHA-256 digests remain in provenance even when the
original audio cannot be redistributed. After write-once sealing, digests,
labels, confidence, scoreability, transforms, and targets are immutable. A data
or scoring defect invalidates the campaign identity; the invalid bundle is
retained rather than silently corrected.

### EV-C008 — Redistribution and repository policy

Third-party audio is committed only when its license clearly permits the
intended redistribution; otherwise the repository keeps provenance and
deterministic reconstruction instructions. SMARD original audio is not committed
by default. Raw downloads, caches, and ambiguous-license audio live under
`private/external_wav/`, which is ignored by Git. Credentials, authorization
headers, provider bodies, and local user paths never enter manifests or bundles.

---

## 4. PCM Derivation, Pairing, Transforms, and Reference Analysis

### EV-C009 — Bounded WAV derivation boundary

Analysis WAVs must satisfy the frozen V0.2 loader:

- little-endian RIFF/WAVE;
- integer PCM or supported extensible PCM;
- mono preferred;
- 8/16/24/32 bit;
- 8 kHz–192 kHz;
- no more than 20 MiB, 2,000,000 frames, or 30 seconds.

Permitted derivations are deterministic channel selection, deterministic crop,
lossless integer-PCM recontainerization when needed, one documented sample-rate
conversion only when the original is unsupported, and B-group transforms defined
in EV-C010. Prohibited derivations include per-signal peak normalization,
loudness normalization, denoising, declipping, EQ, compression, enhancement, and
post-Agent channel or interval selection.

### EV-C010 — Frozen semi-real transform identity

B-group transforms use a globally fixed canonical base, optional globally fixed
attenuation, and frozen validation-selected clipping proportion and harmonic
alpha/post-gain. Clipping uses symmetric hard clipping with a frozen quantile
method. Second-harmonic injection uses:

```text
y_pre[n] = x[n] + alpha * (x[n]^2 - mean(x^2))
```

Combined assets apply harmonic first and clipping second. Development candidates
for clipping tail proportions are exactly `0.03`, `0.05`, and `0.10`; alpha
candidates are exactly `0.10`, `0.15`, and `0.20`. Final values come only from
the frozen validation selection rule.

Transform identity for EV-C010:

```text
transform_id:      signal_diag.external_transform
transform_version: 1.0.0
```

Public function: `inject_second_harmonic(samples, alpha, post_gain)`.

### EV-C010A — Additive amplitude-normalized harmonic transform (OQ-012 option 3)

Approved 2026-09-01. This section is additive; EV-C010 and transform `1.0.0`
remain frozen and must not be rewritten.

B-group harmonic and combined assets materialized after pilot v3 authorization use:

```text
transform_id:      signal_diag.external_transform
transform_version: 1.1.0
```

Amplitude-normalized second-harmonic injection:

```text
a_ref = max(abs(x))
u[n]  = x[n] / a_ref
y_pre[n] = x[n] + alpha * a_ref * (u[n]^2 - mean(u^2))
y[n] = y_pre[n] * post_gain
```

Combined `1.1.0` applies harmonic `1.1.0` first and EV-C010 clipping second.
Under EV-C010A alone, alpha candidates remain `{0.10, 0.15, 0.20}`. Validation
gates (THD > 5%, valid F0, reportable order-2, no flat-top/clipping), clipping
tail candidates, globally fixed `post_gain`, and `signal_diag.external_reference`
`1.0.0` are unchanged from the baseline design.

Public function: `inject_second_harmonic_amplitude_normalized(samples, alpha, post_gain)`.

Pilot failure reports referencing transform `1.0.0` (`pilot_failure_report.json`,
`pilot_failure_report_v2.json`) remain immutable evidence and must not be
overwritten when recording pilot v3+ outcomes.

Design authority: `docs/superpowers/specs/2026-09-01-v0-2-external-harmonic-transform-amendment.md`.

### EV-C010B — Expanded alpha candidates for transform 1.1.0 only (OQ-012 option 1)

Approved 2026-09-01. This section is additive; EV-C010, EV-C010A, and transform
`1.0.0` remain frozen and must not be rewritten.

Transform `1.1.0` harmonic alpha candidates for development validation and
materialization after pilot v4 authorization are exactly:

```text
{0.10, 0.15, 0.20, 0.25, 0.50, 0.75, 1.00}
```

Transform `1.0.0` alpha candidates remain exactly `{0.10, 0.15, 0.20}`. The
amplitude-normalized formula, validation gates, clipping tail candidates,
globally fixed `post_gain` (`0.8`), attenuation bounds, and
`signal_diag.external_reference` `1.0.0` are unchanged.

Selection rule (unchanged): choose the **smallest** alpha in the version-specific
candidate set passing on **every** eligible validation master. Pilot v4 evidence
records full per-candidate reference metrics for each validation master regardless
of pass/fail.

Pilot v4 outcome (2026-09-01): selected `alpha=0.50` under transform `1.1.0` on
SMARD validation master `master_val_01`. Evidence:
`docs/evaluations/v0_2_external_wav/validation/pilot_success_report_v4.json`.

Pilot failure reports v1/v2/v3 remain immutable and must not be overwritten.

### EV-C011 — Parent-master pairing

Each B master produces exactly four variants: clean/base, clipping, second
harmonic, and combined. All four variants inherit one `parent_master_id`, one
split, and one source configuration group. The original source asset remains
unchanged. Failure before split sealing rejects the entire four-variant family.

### EV-C012 — Evaluator-only reference analysis

Independent reference analysis is a versioned deterministic measurement with
identity `signal_diag.external_reference` `1.0.0`. It receives only the analysis
WAV and sealed provenance, reports applicability, flat-top/clipped proportion,
F0 validity, order amplitudes, and THD, and must not import Agent, planner,
runner, scoring, or reporting modules.

---

## 5. Confidence, Scoreability, Delayed Review, and Disagreement

### EV-C013 — Four-level label confidence

Every case has exactly one confidence:

- `strong_ground_truth`
- `reference_supported`
- `weak_observation`
- `unknown`

Only `strong_ground_truth` and `reference_supported` may enter outcome accuracy,
causal exact-set accuracy, causal macro-F1, positive-class precision/recall, or
correctness assertions. All cases may enter structural measures that do not
require causal truth.

### EV-C014 — Scoreability mask

The final campaign requires exactly 28 Agent slots and 24 outcome-scoreable
slots when sealing succeeds. Unknown and weak cases retain traces and attempts
but store `None` for correctness booleans. Positive causal claims on weak or
unknown cases are conservatism observations, not false-positive rates.

### EV-C015 — Single-reviewer delayed blinded re-review

Round 1 records source/provenance review, independent measurements, confidence,
eligible outcome, causal set, and reason codes before any Agent result is
available. Round 2 begins only after at least 14 complete days. The blind package
excludes source names, original filenames, transform names/parameters, split,
prior labels, and all Agent output.

### EV-C016 — Disagreement downgrade policy

Disagreement never upgrades confidence. Transform-proven B labels may remain
strong only when deterministic provenance and independent reference checks pass;
all other unresolved disagreement is downgraded to weak or unknown. Final review
outputs and the scoreability mask are frozen before any final Agent call.

### EV-C025 — Single-reviewer provenance audit mode (2026-09-01 amendment)

Approved 2026-09-01. This section is additive; EV-C015 delayed blind review
remains frozen for preservation tests and historical bundles.

`review_mode` is either `delayed_blind_review` or
`single_reviewer_provenance_audit`.

Under `single_reviewer_provenance_audit`:

- Round 1 review records are required for every manifest case before sealing;
- Round 2 and the 14-day delay are **not** mandatory sealing gates;
- `audit_single_reviewer_provenance(manifest, round1)` validates label
  provenance and returns `ReviewAgreement` with
  `evaluation_status=not_evaluated`;
- B `strong_ground_truth` requires deterministic clean/degraded pairing:
  transform identity, parameters, `input_sha256` matching the clean parent
  master, and `output_sha256` matching `wav_sha256`;
- A and C must never be `strong_ground_truth`; insufficient reference keeps
  `weak_observation` or `unknown`;
- `raw_outcome_agreement`, causal-set agreement, and Cohen kappa fields are
  `null` with `evaluation_status=not_evaluated`; fabricating agreement
  statistics is forbidden;
- append-only `report.md` must disclose single-reviewer limitation and that
  inter-rater agreement was not evaluated.

`seal_final_external_test` accepts `review_mode=single_reviewer_provenance_audit`
without Round 2. Agreement targets apply only when
`evaluation_status=evaluated`.

---

## 6. Grouped Splits, Final Sealing, Attempt Consumption, and No Fallback

### EV-C017 — Group-isolated split policy

Files are never randomly split in isolation. Minimum split units are:

- SMARD: capture configuration including loudspeaker, microphone/array, position,
  and available session identity;
- Pyramic: upstream sample, speaker, and angle/configuration family;
- ESC-50: `src_file`;
- NSynth: `instrument`;
- B: `parent_master_id` and all four variants.

No group key, original digest, derived digest, or parent/child lineage may
cross splits.

### EV-C018 — Write-once final sealing

Final sealing requires final-preflight validity, 28 final cases, 24 scoreable
labels, protected-asset validity, absent destination, and no existing run
output. Under `delayed_blind_review`, sealing also requires elapsed review
delay and review-target agreement. Under
`single_reviewer_provenance_audit`, provenance audit passes instead of delayed
review agreement. Sealed outputs use create-new semantics. After sealing, cases
are not replaced or relabeled based on Agent output.

### EV-C019 — One consumed attempt per final slot

Final execution schedules one Agent slot and one fixed-pipeline slot for each of
28 final cases. An attempted provider call is a consumed slot. There is no
rerun after timeout, provider error, wrong outcome, or poor score. Max
concurrency for real-model calls is one.

### EV-C020 — No ScriptedPlanner fallback

Final Agent slots use `RealLLMPlanner` only. Missing credentials leave final
pending. Provider or behavior failure never authorizes `ScriptedPlanner`,
model substitution, or silent fallback. Every failed, unscored, or below-target
final attempt remains in the bundle.

---

## 7. External Scoring, Bundle Immutability, Status, and Public Claims

### EV-C021 — Additive external scoring identity

External scoring uses identity `signal_diag.external_scoring` `1.0.0`. It scores
external traces against sealed external cases without importing or changing
private functions in `evaluation/scoring.py`. Historical Phase 4.3.1 scoring
identity `signal_diag.scoring` `2.0.0` remains unchanged.

### EV-C022 — Append-only external bundle immutability

External bundles are write-once and append-only at the study level. Required
bundle members include `study_manifest.json`, `provenance.jsonl`,
`reference_summaries.jsonl`, `review_agreement.json`, `attempts.jsonl`,
`runs.jsonl`, `metrics.json`, `strata.csv`, `report.md`,
`protected_assets.json`, and `checksums.sha256`. Bundles must not nest inside
historical Phase 4 or Phase 5 accepted bundles. The word `official` is
deliberately absent from external study identities.

### EV-C023 — Three distinct completion statuses

The study exposes three separate statuses:

- `external_validation_harness_completed` — deterministic integrity only;
- `external_validation_completed` — one sealed final campaign with all attempts
  retained;
- `external_validation_meets_target` — completed campaign plus frozen
  demonstration thresholds from the design spec.

A completed campaign that misses targets is retained as
`external_validation_completed/below_target` and is not rewritten to cross the
threshold.

### EV-C024 — Public claims boundary

Permitted public claims after a completed study describe a small external-validity
study using public real loudspeaker-room-microphone recordings, controlled paired
distortions on real-recording masters, and licensed out-of-domain audio, with
source-level isolation, delayed blinded re-review, and immutable failure
retention. Prohibited claims include industrial validation, production readiness,
industry-standard clipping or THD limits, self-recorded phone/device coverage,
precise real-chain THD causality for A, mapping public machine/environment labels
to S1 causal truth, and population-wide accuracy from a 28-case study.

---

## 8. Frozen Study Identities

```text
dataset:              s1-distortion-external-wav 1.0.0
study:                v0.2-external-wav-validity-1
development bundle:   study_v0_2_external_wav_dev_1
validation bundle:    study_v0_2_external_wav_validation_1
final bundle:         study_v0_2_external_wav_final_1
external scoring:     signal_diag.external_scoring 1.0.0
reference analyzer:   signal_diag.external_reference 1.0.0
external transform:   signal_diag.external_transform 1.0.0 (legacy even-order)
                      signal_diag.external_transform 1.1.0 (amplitude-normalized; OQ-012 option 3)
```

Public analysis filenames are truth-free:

```text
extwav_<split>_<opaque_case_id>.wav
```

Neutral default request:

```text
Why does this signal sound distorted? Check only the supported S1 causes and
state clearly when the evidence is insufficient or the analysis is not
applicable.
```

---

## 9. Public Python Surface (Phase A)

Phase A introduces:

```python
def verify_protected_assets(repo_root: Path, checksum_file: Path) -> None: ...
```

in `signal_diag.evaluation.external.sealing`. Later phases add the remaining
external package surface under separate contract sections and test IDs.

---

## 10. Relationship to Frozen V0.2 Contracts

These EV-C contracts are additive. They do not modify §§1–64 of
`CONTRACTS_V0_2.md`, any accepted Phase 4.3.1 bundle, Phase 5 Demo artifact,
prompt hash, scoring identity, or rule profile threshold. External study code may
depend on frozen V0.2 modules but must not edit them except through a separately
authorized V0.3 change process.

---

## 11. Historical V0.3 prerequisite IDs (EV-C026+, OQ-018)

The following IDs appear in V0.3 prerequisite reports, DSP comments, and
contextual designs. They are recorded here so the ID space is not orphaned.
They are **not** normative gates for the sealed V0.2 external-WAV study
(EV-C001–EV-C025) and do not authorize re-running or rewriting sealed bundles.

### EV-C026 — Fundamental relative energy (FRE)

Historical Workstream A/B definition: fraction of positive-frequency spectral
energy at the estimated fundamental, exposed on `HarmonicAnalysis` as
`fundamental_relative_energy`. Used by V0.3 DSP validity gates; not an
external-WAV sealing requirement.

### EV-C027 — FRE validity gate

When FRE is below the configured threshold, harmonic analysis is
`valid=false` with
`invalid_reason=fundamental_bin_energy_below_reliability_threshold`.

### EV-C028 — Named FRE threshold parameter

Optional `min_fundamental_relative_energy` (engineering default documented in
DSP as 0.15). Thresholds remain code/profile owned; this ID names the
parameter only.

### EV-C029 — Octave ambiguity indicator (revised)

`F0Estimate.octave_ambiguity_detected` may flag octave risk without
re-selecting F0 by energy ranking.

### EV-C036 — Single-WAV validation draft (superseded / never executed)

Draft acceptance-target pre-registration for a single-WAV V0.3 validation
protocol. Superseded by the contextual paired/nominal validation path; must
not be executed as if it were an active gate. See
`docs/evaluations/v0_3/validation/SUPERSESSION_NOTICE.md`.
