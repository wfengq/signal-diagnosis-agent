# External WAV Label Manual 1.0

This manual applies only to the additive V0.2 external WAV validity study. It
does not amend the accepted V0.2 contracts, prompts, scoring, rule profile, or
historical evaluation and Demo evidence.

## Confidence labels

- `strong_ground_truth` — deterministic intervention, complete transform
  provenance, and independent reference confirmation.
- `reference_supported` — source/control metadata plus independent measurement
  or review support, without complete causal control.
- `weak_observation` — a plausible observation without enough causal support.
- `unknown` — no reliable S1 truth.

Only `strong_ground_truth` and `reference_supported` enter correctness and
causal-label metrics. The other two levels remain available for conservatism,
unsupported-claim, false-positive, inconclusive, and failure-case analysis.

## Delayed blinded self-review

Round 1 records outcome, exact causal set, confidence, applicability, reason
codes, provenance evidence, and frozen reference measurements before Agent
results are available. Round 2 starts at least 14 complete days later and shows
only a fresh alias, neutral audio path, the analysis audio, the frozen reference
summary, and the common form. It excludes source names, original filenames,
split, parent identity, transform kind/parameters, Round 1 labels, and Agent
outputs.

Disagreement never upgrades confidence. A transform-proven B label may remain
strong only when its input/output digests, intended transform, and applicable
reference check agree. Unresolved A/C disagreement is downgraded to
`weak_observation` or `unknown`. No disagreement is resolved by consulting an
Agent response.

## Review record

For every case and round, record: review alias, opaque case ID, round number,
outcome, exact causal set, confidence, applicability, reason codes, and a UTC
timestamp. Preserve both rounds and all disagreements. Do not claim a second
reviewer, inter-rater reliability, industrial validation, or production
fitness.
