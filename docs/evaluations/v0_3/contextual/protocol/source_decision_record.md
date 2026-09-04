# Source Decision Record — V0.3 Contextual Development (Task 11 remediation)

**Study:** `study_v0_3_contextual_dev_1` (rematerialized)

**Catalog:** `v0.3-contextual-dev-1` `1.1.0-remediation`

**Recorded:** 2026-09-04

**Scope:** contextual development only (no validation / final test; no real-model run)

**Prior attempt:** preserved under
`development/study_v0_3_contextual_dev_1_attempt1_rejected_2026-09-04/`
(do not treat as frozen success).

## Remediation checklist

| Finding | Fix |
|---|---|
| P1 clipping_mechanism | Full-scale hard clip (`peak_target=1.5` → limit ±0.99); qualification requires `clipping_mechanism=true` **and** substantial ratio/flat FAIL |
| P1 non-ESC-10 | Replaced with `1-17367-A-10` (rain) and `1-28135-A-11` (sea_waves); both `esc10=True` / CC BY 3.0 |
| P1 natural-even | Adjacent sustain windows of organ notes with reference THD ≈11.8% / 10.6% and growth ≪1% |
| P2 code_sha256 | `contextual_implementation_sha256()` hashes contextual package + DSP/profile bytes |
| P2 provenance | Catalog entries for every `source_id`; `case_build_record` stores dual-master lineage, crops, noise/transform params |

## Selected sources

| source_id | license | S1 role |
|---|---|---|
| NSynth note masters (5 clean + 2 rich) | CC BY 4.0 | clean / transform / natural-even |
| `esc10_100032_a0` dog | CC BY 3.0 (ESC-10) | domain-out |
| `esc10_17367_a10` rain | CC BY 3.0 (ESC-10) | domain-out |
| `esc10_28135_a11` sea_waves | CC BY 3.0 (ESC-10) | domain-out |

Rejected for committed development: SMARD (no redistribution), Pyramic speech, ESC-50 non-ESC-10 (CC BY-NC).

## Qualification / calibration (remediation)

- Prefreeze + frozen qualification: **20/20** gates including `clipping_mechanism=true` on all six clipping/combined positives.
- Calibration once: candidates `(0.5,1.0,2.0,3.0,5.0)`; selected **5.0%** (largest with 100% specificity on rich no-growth controls and ≥90% sensitivity).
- Profile freeze: `1.0.0`, growth **5.0%**, SHA `c79865caf913b2a1a5f6f50fccd8c37d6f2828e72feb1f80d9c9c7b4b7d9eb58`.

## Code-identity amendment (provenance-only)

Append-only file:
`development/study_v0_3_contextual_dev_1/code_identity_amendment.json`.

- Original calibration `code_sha256`: `da72a8e856712af019a4bdd8fbdf7c3c20be59d6593793fb3e91f0f49b2a5ea9`
- Bridges to current implementation tree after `def199f` rematerialize, `b339dcf` typing-only fix, and the freeze-identity resolver
- Qualification/calibration recomputes unchanged; threshold not reselected
- Attempt-1 ESC-50 non-ESC-10 assets corrected to **CC BY-NC 3.0** with attribution in
  `study_v0_3_contextual_dev_1_attempt1_rejected_2026-09-04/LICENSE_CORRECTION.md`

## Forbidden actions

No real-model run; no ScriptedPlanner campaign; no validation construction; V0.2 1%/5% distortion profile untouched.
