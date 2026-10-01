# Design inputs: `study_s1_planner_ablation_dev_2`

Unsealed proposal and rationales for the S1 planner-ablation protocol revision.
This document is **not** a protocol seal. No `protocol_seal/` directory is
authorized here. Numerical schedule values remain approved design choices
awaiting a later seal grant.

Source design: `docs/superpowers/specs/2026-10-01-s1-planner-ablation-protocol-revision-design.md` §5.
Source WAV bytes: `docs/evaluations/v0_3/contextual/development/study_v0_3_contextual_dev_1/wav/`
(read-only reuse; seven parent masters, not ten independent sources).
Source/master rows copied from `study_s1_planner_ablation_dev_1/protocol_seal/manifest.json`.

## Prior-output exposure (disclosed)

Prior product and fixed-pipeline outputs from
`study_s1_planner_ablation_dev_1` / Wave 5 review motivated this redesign,
including the clean/invalid-reference single-mode collision and natural-control
single-oracle correction. Those prior outputs **must not** serve as oracle
truth. Labels below are proposed from source transformations, stimulus context,
deterministic measurement validity, and versioned gates only. Independent
offline label review is required before any seal; this file does not fabricate
approval.

## Proposed identities

| Field | Value |
|-------|-------|
| study_id | `study_s1_planner_ablation_dev_2` |
| scoring_identity | `signal_diag.planner_ablation_scoring` |
| scoring_version | `2.0.0-dev.1` |
| timing_contract | `encoded_bytes_to_terminal_v1` |
| rounds | 3 |
| deadline_s | 120 |
| primary_endpoint | `quality` |
| quality_loss_tolerance | 0 (exact zero) |
| material_improvement_ratio | 0.20 |
| material_absolute_saving_s | 0.100 |

## Mode-specific proposed oracle

Empty fault sets accompany `no_supported_fault` and `inconclusive`. Positive
sets are exact sets.

| Scenario ID | Role | Single oracle | Paired oracle |
|-------------|------|---------------|---------------|
| `825a759a0ea47bb7` | clean | no_supported_fault | no_supported_fault |
| `857fac53e4d2e57e` | clipping | supported_fault: clipping | supported_fault: clipping |
| `abd9010438d4ad93` | clipping | supported_fault: clipping | supported_fault: clipping |
| `a4a0853be9983f8c` | harmonic | inconclusive | supported_fault: harmonic_distortion |
| `2be730b9113701de` | harmonic | inconclusive | supported_fault: harmonic_distortion |
| `6fb80bbda391c26c` | combined | supported_fault: clipping | supported_fault: clipping + harmonic_distortion |
| `aa9b4a91b0253c33` | combined | supported_fault: clipping | supported_fault: clipping + harmonic_distortion |
| `393940e92c58cf0b` | natural_even_control | inconclusive | no_supported_fault |
| `04f4068ec91d2621` | natural_even_control | inconclusive | no_supported_fault |
| `163185980dc8f7a4` | invalid_comparison | no_supported_fault | inconclusive |

### Rationales (summary)

- Clean / clipping rows follow construction and mode-aware gates with empty or
  clipping-only causal sets.
- Harmonic rows: single-file gates cannot attribute harmonic distortion without
  paired context → single `inconclusive`; paired exact `{harmonic_distortion}`.
- Combined rows: single supports clipping only; paired exact
  `{clipping, harmonic_distortion}` for additional causal coverage.
- Natural even-controls: single remains conservative `inconclusive` under
  demonstration THD thresholds; paired supports `no_supported_fault`.
- Invalid reference: shares clean organ-a **test** bytes with `825a...`, so
  single oracle equals clean `no_supported_fault`; paired stays `inconclusive`
  because the reference is invalid.

## Alias

Single-mode requests for `163185980dc8f7a4` and `825a759a0ea47bb7` share one
execution and one scored unit, represented by `825a759a0ea47bb7`. Explicit alias:
`163185980dc8f7a4` → `825a759a0ea47bb7`. Paired keys remain distinct because
reference bytes differ.

Proposed unique schedule: **9** single + **10** paired = **19** keys/arm/round;
**3** rounds × **2** arms → **114** slots (**57** product).

## Source / master relationships

| Scenario ID | source_id | parent_master_id |
|-------------|-----------|------------------|
| `825a759a0ea47bb7` | `nsynth_note_master_organ_a` | `master_organ_a` |
| `857fac53e4d2e57e` | `nsynth_note_master_organ_a` | `master_organ_a` |
| `abd9010438d4ad93` | `nsynth_note_master_bass_a` | `master_bass_a` |
| `a4a0853be9983f8c` | `nsynth_note_master_organ_b` | `master_organ_b` |
| `2be730b9113701de` | `nsynth_note_master_bass_b` | `master_bass_b` |
| `6fb80bbda391c26c` | `nsynth_note_master_guitar_a` | `master_guitar_a` |
| `aa9b4a91b0253c33` | `nsynth_note_master_organ_a` | `master_organ_a` |
| `393940e92c58cf0b` | `nsynth_note_master_organ_rich_a` | `master_organ_rich_a` |
| `04f4068ec91d2621` | `nsynth_note_master_organ_rich_b` | `master_organ_rich_b` |
| `163185980dc8f7a4` | `nsynth_note_master_organ_a` | `master_organ_a` |

Seven parent masters. No fresh-source generalization is claimed.

## Fixed U / C / G populations (construction labels)

Registered before execution; arms never receive these labels.

| Population | Members | Count |
|------------|---------|------:|
| U (upgrade) | `a4a0853be9983f8c`, `2be730b9113701de`, `6fb80bbda391c26c`, `aa9b4a91b0253c33`, `393940e92c58cf0b`, `04f4068ec91d2621`, `163185980dc8f7a4` | 7 |
| C (conditional) | all U except `163185980dc8f7a4` (invalid reference: obtainable, not valid/sufficient) | 6 |
| G (guidance-eligible single) | `a4a0853be9983f8c`, `2be730b9113701de`, `393940e92c58cf0b`, `04f4068ec91d2621` | 4 |

### Upgrade targets

| Scenario ID | Upgrade target |
|-------------|----------------|
| `a4a0853be9983f8c`, `2be730b9113701de` | harmonic attribution |
| `6fb80bbda391c26c`, `aa9b4a91b0253c33` | additional harmonic coverage beyond clipping |
| `393940e92c58cf0b`, `04f4068ec91d2621` | supported no-fault for natural controls |
| `163185980dc8f7a4` | **none** (negative control; stays outside C) |

## Review status

| Field | Value |
|-------|-------|
| review_status | `independent_offline_review_complete` |
| approved | `true` |
| note | Independent offline label review recorded below. No construction/gates disagreement found. This approval does **not** create a protocol seal, authorize RealLLM, or relax thresholds. |

### Independent offline label review

| Field | Value |
|-------|-------|
| reviewer | `independent_offline_reviewer` (subagent) |
| reviewed_at | 2026-10-01 |
| independence | Reviewer did **not** implement the harness. Neither `product_agent` nor `fixed_pipeline` diagnosis outputs were used as oracle truth. Prior-output exposure motivating redesign remains disclosed above. |
| sources_checked | `dev_1` seal `protocol_seal/manifest.json` case_sources/oracle; `dev_1` preregistration; contextual `case_build_record.json` / `contextual_manifest.json`; WAV SHA-256 identities; design §5; `CONTRACTS_V0_3_CONTEXTUAL.md` §8/§15/§16 Option C / §17; demonstration profile thresholds 1% clipping / 5% THD / 5% even-harmonic growth; independent DSP re-measure of test WAV clipping/THD and paired contextual growth |
| status | `approved` |
| approved | `true` |
| blockers | none |
| threshold_stance | Do **not** relax DSP thresholds or finish gates. |

#### Per-scenario verdicts

| Scenario ID | Verdict | Rationale (construction / gates) |
|-------------|---------|----------------------------------|
| `825a759a0ea47bb7` | approve | Clean identity transform; test==ref bytes; DSP: no clipping mechanism, ratio 0, THD ≈0.11% ≪ 5%. Single and paired `no_supported_fault` match mode-aware clean gates. |
| `857fac53e4d2e57e` | approve | Hard-clip construction; DSP: mechanism true, ratio ≈23.8% ≫ 1%, flat-top true; paired even-growth ≈0.15% ≪ 5% (no independent harmonic). Exact `{clipping}` both modes. Option C / §8 clipping path satisfied without threshold change. |
| `abd9010438d4ad93` | approve | Hard-clip on bass master; DSP: mechanism true, ratio ≈13.4% ≫ 1%; paired even-growth ≈0.01% ≪ 5%. Exact `{clipping}` both modes. |
| `a4a0853be9983f8c` | approve | Second-harmonic ampnorm construction. Single: THD ≈7.48% > 5% but §8 forbids single-file causal harmonic → `inconclusive`. Paired: valid comparison, even-growth ≈7.23% > 5% → exact `{harmonic_distortion}`. |
| `2be730b9113701de` | approve | Same harmonic transform on bass_b. Single THD ≈10.34% → `inconclusive`; paired even-growth ≈9.91% > 5% → exact `{harmonic_distortion}`. |
| `6fb80bbda391c26c` | approve | Harmonic-then-clip construction. Single: mechanism true, ratio ≈2.56% > 1% → clipping only (harmonic not attributable without context). Paired: clipping plus even-growth ≈8.81% > 5% → exact `{clipping, harmonic_distortion}`. |
| `aa9b4a91b0253c33` | approve | Same combined order on organ_a. Single ratio ≈6.53% → clipping only; paired even-growth ≈6.41% > 5% → exact `{clipping, harmonic_distortion}`. |
| `393940e92c58cf0b` | approve | Adjacent-window natural control; construction growth ≈0.09%. Single THD ≈12.63% > 5% demo gate → cannot finish `no_supported_fault` without context → `inconclusive` (corrects sealed `dev_1` single label). Paired valid, growth ≪ 5% → `no_supported_fault`. |
| `04f4068ec91d2621` | approve | Twin natural control; construction growth ≈0.01%. Single THD ≈8.47% > 5% → `inconclusive`; paired `no_supported_fault`. Same correction vs sealed `dev_1` single. |
| `163185980dc8f7a4` | approve | Invalid cross-master ref (`fundamental_incompatible`). Test SHA-256 identical to clean `825a…` → equal single request identity requires equal oracle → single `no_supported_fault` (corrects sealed `dev_1` single `inconclusive`). Paired stays `inconclusive`. |

#### Alias / mapping / populations

| Item | Verdict | Rationale |
|------|---------|-----------|
| Alias `163185980dc8f7a4` → `825a759a0ea47bb7` (single only) | approve | Identical test-byte hash `ea04bd30…`; paired refs differ (`ea04bd30…` vs `b0c7ea55…`). Schedule 9+10=19 keys/arm/round is consistent. |
| Source/master table (7 parents) | approve | Matches sealed `dev_1` `case_sources` and contextual build record; no fresh-source claim. |
| U (7) / C (6) / G (4) | approve | Matches design §5.3: U = two harmonic + two combined + two natural + invalid negative control; C excludes invalid (obtainable but not valid/sufficient); G = harmonic + natural singles only (guidance-eligible under §17 inconclusive path). |
| Upgrade targets | approve | Harmonic attribution; additional harmonic coverage beyond clipping; supported no-fault for naturals; invalid target **none**. |

Overall: **approved=true**. No revise blockers. Seal remains separately gated.

### Implementer construction/gates self-check (not independent signoff)

| Field | Value |
|-------|-------|
| checker | Task 7 implementer (study offline acceptance) |
| checked_at | 2026-10-01 |
| status | `superseded_by_independent_offline_review` |
| approved | `false` |
| scope | Consistency check of the ten proposed oracle rows, source/master mapping, alias `163185980dc8f7a4`→`825a759a0ea47bb7`, U/C/G membership (7/6/4), and upgrade targets against construction labels and versioned gates — **not** treating either arm's answer as truth. |
| outcome | Rows and populations match the approved design §5 construction proposal and `validate_labels` structural checks. No unresolved construction disagreement found by the implementer. |
| blocker | Historical note only: independent offline label review was still required at self-check time. That review is now recorded above (`approved=true`). Self-check still does **not** substitute for operator seal grant. |
| prior_output_exposure | Disclosed above; prior Wave 5 / `dev_1` product and fixed-pipeline outputs motivated the redesign and must not serve as oracle truth. |

Demonstration thresholds remain 1% clipping and 5% THD; they are not industry
standards or SLAs.
