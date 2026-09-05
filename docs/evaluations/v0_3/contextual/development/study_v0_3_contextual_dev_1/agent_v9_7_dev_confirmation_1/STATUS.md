# v9.7 development confirmation — STATUS

- target_status: `below_target`
- cases_executed: 20 / 20
- head_commit: `e28c4e4c9f2e16e86fad6342d842db4016da765a`
- prompt: `v0.3-s1-planner-9.7`
- prompt_sha256: `fc50d82fc7b5701388f5d35c7f50a157ed1c88f050e6057cd8f11caf280b982a`
- causal_policy: `v9_7_deterministic_rule_closure`
- model: `deepseek-v4-flash`
- scripted_planner_fallback: `false`
- scoring_method: `failure_as_incorrect`
- label: v9.7 development confirmation (append-only; prior runs preserved)

## Gates

- `slots_complete_20`: True
- `unique_cases_20`: True
- `planner_completion_ge_0_95`: True
- `evidence_grounding_100`: False
- `unsupported_claim_rate_0`: True
- `natural_even_harmonic_fp_0`: True
- `claim_refs_resolve`: True
- `scoreable_outcome_accuracy_ge_0_80`: True
- `scoreable_causal_exact_ge_0_75`: True
- `inconclusive_appropriateness_1_00`: True

## Planner completion

- `planner_completion`: `{"numerator": 19, "denominator": 20, "value": 0.95}`

## Aggregate (failure-as-incorrect)

- `outcome_accuracy`: `{"numerator": 16, "denominator": 17, "value": 0.9411764705882353}`
- `causal_exact_set_accuracy`: `{"numerator": 16, "denominator": 17, "value": 0.9411764705882353}`
- `evidence_grounding`: `{"numerator": 16, "denominator": 17, "value": 0.9411764705882353}`
- `unsupported_claim_rate`: `{"numerator": 0, "denominator": 17, "value": 0.0}`
- `inconclusive_appropriateness`: `{"numerator": 6, "denominator": 6, "value": 1.0}`
- `natural_even_harmonic_fp`: `0`
- `harmonic_precision`: `{"numerator": 4, "denominator": 4, "value": 1.0}`
- `harmonic_recall`: `{"numerator": 4, "denominator": 4, "value": 1.0}`
- `clipping_precision`: `{"numerator": 6, "denominator": 6, "value": 1.0}`
- `clipping_recall`: `{"numerator": 6, "denominator": 6, "value": 1.0}`

## Descriptive full-population recall

- `harmonic_recall`: `{"numerator": 4, "denominator": 5, "value": 0.8}`
- `clipping_recall`: `{"numerator": 6, "denominator": 6, "value": 1.0}`

## Role metrics

- `clean`: `{"n": 3, "scoreable_n": 3, "outcome_accuracy": 1.0, "causal_exact_accuracy": 1.0, "evidence_refs_complete_rate": 1.0}`
- `clipping`: `{"n": 4, "scoreable_n": 4, "outcome_accuracy": 1.0, "causal_exact_accuracy": 1.0, "evidence_refs_complete_rate": 1.0}`
- `combined`: `{"n": 2, "scoreable_n": 2, "outcome_accuracy": 1.0, "causal_exact_accuracy": 1.0, "evidence_refs_complete_rate": 1.0}`
- `controlled_inconclusive`: `{"n": 1, "scoreable_n": 1, "outcome_accuracy": 1.0, "causal_exact_accuracy": 1.0, "evidence_refs_complete_rate": 1.0}`
- `domain_out_inconclusive`: `{"n": 3, "scoreable_n": 0, "outcome_accuracy": null, "causal_exact_accuracy": null, "evidence_refs_complete_rate": null}`
- `frequency_mismatch`: `{"n": 1, "scoreable_n": 1, "outcome_accuracy": 1.0, "causal_exact_accuracy": 1.0, "evidence_refs_complete_rate": 1.0}`
- `harmonic`: `{"n": 3, "scoreable_n": 3, "outcome_accuracy": 0.6666666666666666, "causal_exact_accuracy": 0.6666666666666666, "evidence_refs_complete_rate": 1.0}`
- `invalid_comparison`: `{"n": 1, "scoreable_n": 1, "outcome_accuracy": 1.0, "causal_exact_accuracy": 1.0, "evidence_refs_complete_rate": 1.0}`
- `natural_even_control`: `{"n": 2, "scoreable_n": 2, "outcome_accuracy": 1.0, "causal_exact_accuracy": 1.0, "evidence_refs_complete_rate": 1.0}`

## Descriptive comparison note

- Prior v9.5/v9.6 directories are preserved unchanged.
- This run is a new append-only v9.7 confirmation on all 20 development cases under frozen identities above.
- Primary scoring uses failure-as-incorrect.
