# V0.3 v9.11 Mode-Aware No-Fault Recovery Design

**Status:** approved for offline TDD and replay; real-model execution is not authorized

## Purpose

Repair the three `max_planner_retries` failures retained in v9.10 development
confirmation 4. Two paired-reference natural-even controls had complete
same-run no-fault evidence available but recovery named only a missing field
without its available ID. One single-signal clean case was incorrectly required
to cite the contextual-only `test_clipping_mechanism=false` metric.

## Minimal behavior change

Add prompt `v0.3-s1-planner-9.11` and causal policy
`v9_11_mode_aware_no_fault_recovery`, inheriting v9.10 behavior except for
`no_supported_fault` validation and recovery.

- `single_signal` requires the legacy clean family:
  `clipping_mechanism=false`, legacy clipping-ratio PASS, legacy flat-top PASS,
  harmonic-analysis-valid PASS, and THD PASS.
- `paired_reference` and `nominal_single_tone` require the contextual test clean
  family: `test_clipping_mechanism=false`, test clipping-ratio PASS, test
  flat-top PASS, plus the existing mode-specific contextual/harmonic PASS rules.
- A rejected no-fault finish reports every missing requirement together. When a
  matching same-run Evidence or rule-evaluation ID exists, the error names that
  ID so the next finish can cite the complete set in one attempt.

Runtime remains a validator and never inserts or rewrites claims or references.
The prompt only explains the mode split and the all-deficits recovery rule.

## Offline proof

T-CX250 through T-CX255 preserve v9.10, exercise the two clean evidence
families, prove complete ID-bearing deficit recovery, freeze product identity,
and replay all three retained v9.10 failure shapes from structured
Evidence/rule fixtures. RED-GREEN tests and replay are local and deterministic.

## Non-goals

No DSP, Tool output, profile, threshold, WAV, dataset, label, scoring, retry
budget, validation seal, or historical artifact changes. No model call,
validation/final-test access, commit, push, or performance claim is authorized.
