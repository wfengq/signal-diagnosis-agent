# Preregistration: `study_s1_planner_ablation_dev_1`

Wave 3 protocol seal for the S1 planner-ablation utility study.
Tip baseline for seal generation: `67d721b` Wave 2 harness acceptance.
This record freezes executable protocol content. It does not authorize RealLLM
execution.

## Identities

| Field | Value |
|-------|-------|
| study_id | `study_s1_planner_ablation_dev_1` |
| scoring_identity | `signal_diag.planner_ablation_scoring` |
| scoring_version | `1.0.0-dev.1` |
| denominator_derivation (completion family) | `completion_slots` |
| evidence_root | `docs/evaluations/v0_3/planner_ablation/` |
| protocol_seal | `protocol_seal/` (additive; checksummed) |
| source development material | `docs/evaluations/v0_3/contextual/development/study_v0_3_contextual_dev_1/` (read-only reuse of WAV bytes; not a rescore of sealed contextual campaigns) |

Bound digests (must match `protocol_seal/manifest.json`):

| Identity | Digest |
|----------|--------|
| population_identity | `c69db6c69d3dd285c2bd572e6013625f7eb2ae761d736a38a55008fdee13f8b6` |
| oracle_identity | `87a1896b27429e3904360e1567b78baae673073e8177e22886a734a9b85f25e8` |
| input_identity | `7f17a945a77e637675b0ab0a30c0009f71c23fb6652326cb13685da6e2afafe3` |
| code_identity | `850de5b5fefb5aceafcffd4358d699ae804c75ac313245df7da05df6b7f4e0d4` |

`population_identity` / `oracle_identity` are content digests of the frozen
schedule and oracle rows. `input_identity` digests the ordered case WAV path and
byte digests. `code_identity` digests the product diagnosis tree plus
`evaluation/planner_ablation` and `app/planner_ablation_adapter.py`.

## Seal blocker approvals

### 1. Meaning of N

Approved. `n_unit = scorable_slots`. Frozen band size is **40** scored slots
(`10` cases × `2` modes × `2` arms). `non_inferiority_max_gap = 1/40 = 0.025`.

Forty slots are not forty independent sources. Cases that share `source_id` or
`parent_master_id` are dependent evidence. Mode-level bands must be reported so
default-path (`single_signal`) regression cannot hide in aggregates.

Plan draft "12 cases / 48 slots" is superseded. Only ten development cases
provide both test and reference WAVs required for each case ×
`{single_signal, paired_reference}` without inventing audio.

### 2. Inference scope and uncertainty

Approved. This seal authorizes a frozen development-set descriptive comparison
only. One LLM attempt per `product_agent` slot. No campaign retry. One run cannot
support multi-run model-stability claims. Results must not be labeled as
population inference beyond this frozen set.

### 3. Non-inferiority rationale

Approved. Fixed pipeline may be at most one scorable slot worse than product on
primary quality and usefulness (`gap = 0.025`). Equal completion does not block
`fixed_pipeline_dominance` when quality, safety, usefulness, and completion are
non-inferior and material latency improvement holds. Mode-level reporting is
mandatory.

### 4. Safety and zero denominators

Approved.

- Unsupported positive claim rate must be `0` when the positive-claim population
  is evaluable.
- Zero positive-claim population is **not evaluable** and blocks
  `planner_advantage` / `fixed_pipeline_dominance`.
- Evidence grounding uses every claim on completed diagnoses; zero claim
  population is not evaluable.
- Diagnosis-less behavioral failures remain in completion and primary-quality
  denominators and count as incorrect for primary quality.
- Correct `inconclusive` with a completed diagnosis is not a planner
  correctness defect when the oracle expects inconclusive.

### 5. Full resource comparison

Approved.

- Shared wall-clock timing boundary per slot for both arms.
- Material improvement threshold: relative latency reduction
  `material_improvement_ratio = 0.20` on fixed versus product.
- Tool-action counts are reported.
- Campaign attempt retries are forbidden. Model-internal retries are out of
  band and must not be conflated with campaign retries.
- Infrastructure failure stops the campaign. Behavioral failure continues and
  occupies denominators.
- Token or model bill metrics must not be labeled total ownership cost.

### 6. Evaluable population and identity

Approved. Frozen case list, schedule, oracle, stop rules, and digests are in
`protocol_seal/manifest.json`. Formal scoring must construct study input only
via `study_input_from_verified_manifest` on that verified manifest. Missing
evaluable population, unmatched arms, incomplete protocol, or safety
not-evaluable yields `insufficient_evidence` / fail closed.

## Frozen case list (10)

| case_id | role | paired oracle | single_signal oracle |
|---------|------|---------------|----------------------|
| `825a759a0ea47bb7` | clean | no_supported_fault | no_supported_fault |
| `857fac53e4d2e57e` | clipping | supported_fault {clipping} | supported_fault {clipping} |
| `abd9010438d4ad93` | clipping | supported_fault {clipping} | supported_fault {clipping} |
| `a4a0853be9983f8c` | harmonic | supported_fault {harmonic_distortion} | inconclusive |
| `2be730b9113701de` | harmonic | supported_fault {harmonic_distortion} | inconclusive |
| `6fb80bbda391c26c` | combined | supported_fault {clipping, harmonic_distortion} | supported_fault {clipping} |
| `aa9b4a91b0253c33` | combined | supported_fault {clipping, harmonic_distortion} | supported_fault {clipping} |
| `393940e92c58cf0b` | natural_even_control | no_supported_fault | no_supported_fault |
| `04f4068ec91d2621` | natural_even_control | no_supported_fault | no_supported_fault |
| `163185980dc8f7a4` | invalid_comparison | inconclusive | inconclusive |

WAV paths and byte digests are recorded under `case_sources` in the sealed
manifest. Digests were recomputed from on-disk WAV bytes and checked against
`contextual_manifest.json`.

## Schedule and arms

- Modes: `single_signal`, `paired_reference` (each case).
- Schedule keys: 20 (`case_id` × mode).
- Arms: `product_agent`, `fixed_pipeline`.
- Arm order: all `product_agent` slots, then all `fixed_pipeline` slots.
- LLM repetitions: 1 per product slot.
- Harness-only Scripted dry-runs are never scored.

## Decision protocol

```text
study_id: study_s1_planner_ablation_dev_1
scoring_identity: signal_diag.planner_ablation_scoring
n_unit: scorable_slots
non_inferiority_max_gap: 0.025
material_improvement_ratio: 0.20
advantage_endpoint: quality
```

Usefulness remains a dominance non-inferiority constraint even when the
advantage endpoint is quality.

## Oracle construction rules

1. `paired_reference` rows copy `expected_outcome` /
   `expected_causal_set` from the development contextual manifest for the
   frozen case ids.
2. `single_signal` rows follow mode-aware HEAD matching:
   - clean / natural_even_control → `no_supported_fault`
   - clipping → `supported_fault` with `clipping`
   - combined → `supported_fault` with `clipping` only (harmonic not supported
     without paired contextual gates)
   - harmonic / invalid_comparison → `inconclusive`
3. Wave 4 must not invent replacement labels after seeing results.

## Stop and retry rules

- Infrastructure failure: stop campaign.
- Behavioral failure: continue; occupy completion and primary-quality
  denominators.
- Campaign retry: forbidden.
- Post-hoc extra runs after seeing results: forbidden.

## Seal verification

Regenerate or verify with:

```bash
PYTHONPATH=src python3 scripts/seal_planner_ablation_protocol.py
PYTHONPATH=src python3 -m pytest tests/evaluation/planner_ablation/test_protocol_seal_bundle.py -q
```

Formal scoring entry for this study must use:

```python
study_input_from_verified_manifest(manifest_dict_from_protocol_seal)
```

## Authorization boundary

Authorized by operator phrase `授权 planner-ablation protocol seal`.
Not authorized by this seal: RealLLM campaign execution, product planner
replacement, frozen V0.2 contract edits, mutation of historical sealed
contextual or V0.2 bundles.
