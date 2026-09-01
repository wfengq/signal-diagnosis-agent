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

Phase A — protocol and preservation freeze. Artifacts here define additive
contracts, test IDs, and the protected V0.2 asset audit in
`protocol/protected_assets.sha256`.

Later phases add write-once bundles under `development/`, `validation/`, and
`final_external_test/`. Raw downloads remain outside Git under
`private/external_wav/`.

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
