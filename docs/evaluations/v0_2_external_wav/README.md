# V0.2 External WAV Validity Study

This directory holds the additive external-validity study for V0.2 Scenario S1.
It does not replace Phase 4.3.1 official bundles or Phase 5 Demo artifacts.

## Study identity

```text
dataset:   s1-distortion-external-wav 1.0.0
study:     v0.2-external-wav-validity-1
scoring:   signal_diag.external_scoring 1.0.0
reference: signal_diag.external_reference 1.0.0
```

## Current phase

Study **completed** with retained result
`external_validation_completed/below_target` under
`final_external_test/` (prompt identity `v0.2-s1-planner-8.1` at campaign
time). Phase A protocol/preservation freeze artifacts remain under `protocol/`.

This study does not replace Phase 4.3.1 official 79/80 or Phase 5 Demo
artifacts. Later V0.3 contextual work is a separate evidence trail
(`docs/evaluations/v0_3/contextual/`).

Raw downloads remain outside Git under `private/external_wav/`.

## Preservation boundary

The study consumes but never modifies:

- `docs/evaluations/phase4_3_1/development/`
- `docs/evaluations/phase4_3_1/official/`
- `docs/demo/phase5/v0_2_acceptance/`
- frozen prompt, scoring, rule-profile, and tag `v0.2.0` identities

Run the preservation audit with:

```bash
pytest tests/evaluation/external/test_preservation.py -v
```

## Design references

- `docs/superpowers/specs/2026-09-01-v0-2-real-world-validation-design.md`
- `docs/EXTERNAL_VALIDATION_CONTRACTS_V0_2.md`
- `docs/EXTERNAL_VALIDATION_TEST_PLAN_V0_2.md`
