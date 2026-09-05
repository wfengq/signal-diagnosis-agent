# V0.3 v9.9 Paired-Reference Recovery Design

**Status:** approved bounded remediation

## Problem

The frozen v9.8 development confirmation completed 16/20 planner slots and
failed four paired harmonic/combined slots. Their same-run contextual rule
batches contained every required affirmative rule evaluation, but the finish
validator returned only the first missing paired citation without the available
evaluation ID. Later attempts sometimes cited the nominal THD rule instead of
the paired-reference rules.

This is a recovery-feedback defect. It is not a DSP, dataset, profile,
threshold, or infrastructure defect.

## Change

Add causal policy `v9_9_paired_reference_recovery` and prompt identity
`v0.3-s1-planner-9.9`.

For a paired-reference `harmonic_distortion` claim, a rejected finish reports
all missing requirements together and names every available same-run
`evaluation_id`:

1. contextual analysis PASS;
2. contextual F0 compatibility PASS;
3. reference clipping-ratio PASS;
4. reference flat-top PASS;
5. even-harmonic-growth FAIL.

The v9.9 prompt explicitly separates paired-reference recovery from nominal
single-tone recovery. It instructs the planner to repair every listed paired
deficit together and not substitute nominal THD rules.

## Invariants

- No finish requirement is added, removed, weakened, or auto-satisfied.
- Runtime never inserts or rewrites claim references.
- Clipping remains an independent causal claim, including in combined cases.
- Retry and Tool budgets, profiles, thresholds, data, labels, scoring, and
  routing remain unchanged.
- v9.8 prompt bytes, policy behavior, and recorded runs remain immutable.
- The strongest offline conclusion is `v9_9_harness_complete`; real-model
  performance requires a separately authorized append-only campaign.
