# v9.6 remediation development confirmation — STATUS

- target_status: `below_target`
- cases_executed: 20 / 20
- head_commit: `55242584e337b9a964e61e757db440cc40ac493e`
- prompt: `v0.3-s1-planner-9.6`
- prompt_sha256: `b9ed17debf9bfd2f086ee0eaa178d83370630a0530ebd02336769e416be1b5eb`
- causal_policy: `v9_6_contextual`
- model: `deepseek-v4-flash`
- scripted_planner_fallback: `false`
- label: v9.6 remediation development confirmation (not a Task 13 fix)

## Gates

- `slots_complete_20`: True
- `unique_cases_20`: True
- `evidence_grounding_100`: True
- `unsupported_claim_rate_0`: True
- `natural_even_harmonic_fp_0`: True
- `claim_refs_resolve`: True
- `scoreable_outcome_accuracy_ge_0_80`: False
- `scoreable_causal_exact_ge_0_75`: False

## Aggregate

- `outcome_accuracy`: `{"numerator": 7, "denominator": 17, "value": 0.4117647058823529}`
- `causal_exact_set_accuracy`: `{"numerator": 12, "denominator": 17, "value": 0.7058823529411765}`
- `evidence_grounding`: `{"numerator": 17, "denominator": 17, "value": 1.0}`
- `unsupported_claim_rate`: `{"numerator": 0, "denominator": 17, "value": 0.0}`
- `natural_even_harmonic_fp`: `0`

## Role metrics

- `clean`: `{"n": 3, "scoreable_n": 3, "outcome_accuracy": 0.0, "causal_exact_accuracy": 1.0, "evidence_refs_complete_rate": 1.0}`
- `clipping`: `{"n": 4, "scoreable_n": 4, "outcome_accuracy": 1.0, "causal_exact_accuracy": 1.0, "evidence_refs_complete_rate": 1.0}`
- `combined`: `{"n": 2, "scoreable_n": 2, "outcome_accuracy": 0.0, "causal_exact_accuracy": 0.0, "evidence_refs_complete_rate": 1.0}`
- `controlled_inconclusive`: `{"n": 1, "scoreable_n": 1, "outcome_accuracy": 1.0, "causal_exact_accuracy": 1.0, "evidence_refs_complete_rate": 1.0}`
- `domain_out_inconclusive`: `{"n": 3, "scoreable_n": 0, "outcome_accuracy": null, "causal_exact_accuracy": null, "evidence_refs_complete_rate": null}`
- `frequency_mismatch`: `{"n": 1, "scoreable_n": 1, "outcome_accuracy": 1.0, "causal_exact_accuracy": 1.0, "evidence_refs_complete_rate": 1.0}`
- `harmonic`: `{"n": 3, "scoreable_n": 3, "outcome_accuracy": 0.0, "causal_exact_accuracy": 0.0, "evidence_refs_complete_rate": 1.0}`
- `invalid_comparison`: `{"n": 1, "scoreable_n": 1, "outcome_accuracy": 1.0, "causal_exact_accuracy": 1.0, "evidence_refs_complete_rate": 1.0}`
- `natural_even_control`: `{"n": 2, "scoreable_n": 2, "outcome_accuracy": 0.0, "causal_exact_accuracy": 1.0, "evidence_refs_complete_rate": 1.0}`

## Descriptive comparison note vs v9.5

- v9.5 Task 13 one-shot: incomplete (`cases_executed=4`), `protocol_deviation=true`, `development_confirmation_valid=false`, `target_status=below_target`.
- v9.5 diagnostic continuation: diagnostic_only on 16 never-run slots; not a development confirmation.
- This run is a new append-only v9.6 remediation confirmation on all 20 development cases under frozen identities above.
