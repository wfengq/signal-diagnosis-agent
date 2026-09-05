# Contextual Fixed-Pipeline Truth-Free Remediation Design

## Status and scope

This design implements the user-approved repair discovered before the first
validation model call. It changes only the isolated V0.3 contextual evaluation
harness. It does not change product prompts, causal policies, DSP algorithms,
rule profiles, thresholds, labels, WAV assets, historical runs, or V0.2 assets.

## Defect

`run_fixed_pipeline_case()` currently receives `ContextualCase` and derives its
answer from `role`, `expected_outcome`, and `expected_causal_set`. That is a
label oracle, not the preregistered deterministic contextual baseline, and it
conflicts with the protocol rule that no arm receives expected truth.

## Design

Introduce a frozen `ContextualBaselineRequest` containing only `case_id`,
`signal_id`, and `StimulusContext`. The deterministic baseline receives that
request plus repository-backed Tool and rule services. It always runs clipping
analysis. In `single_signal` mode it runs absolute harmonic analysis and the
frozen S1 profile. In paired and nominal modes it runs contextual analysis and
the frozen contextual profile. It maps only same-run Evidence and rule results
to `supported_fault`, `no_supported_fault`, or `inconclusive` using the existing
v9.9 causal requirements.

The fixed pipeline returns a `BaselineRunResult` with real observations,
Evidence, rule batches, claims, references, limitations, and deterministic IDs.
It never receives role, confidence, transform provenance, expected outcome, or
expected causes.

## Leakage prevention

Tests construct requests independently of `ContextualCase`, assert that passing
a case object is rejected, and demonstrate that changing truth metadata outside
the request cannot affect the result. Source inspection guards reject accesses
to expected/role/confidence/provenance fields in the baseline implementation.

## Seal transition

The existing `validation_seal/` remains byte-for-byte unchanged and is marked
as an unexecuted superseded seal in a new append-only record. A new
`validation_seal_v2/` covers the unchanged manifest, WAV checksums, source
decisions, slot plan, profiles, prompt, scoring identity, empty execution
ledger, and the repaired contextual implementation identity. Verification must
pass before any later real-model authorization.

## Verification and stop gate

Run focused baseline/sealing tests, the contextual suite, full pytest, Ruff,
mypy, architecture/preservation tests, and `git diff --check 605c8a8`. No model
or final-test execution is part of this remediation.
