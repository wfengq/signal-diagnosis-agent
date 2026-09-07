# Contextual Validation Scoring Correction 1

The campaign execution remains the original, complete 60-slot run. No slot was
rerun and no original campaign artifact was overwritten.

The frozen protocol scores evidence grounding over every claim in completed
diagnoses and unsupported-claim rate over every predicted positive fault claim.
The original implementation instead used the fixed 17-case scoreable
denominator and counted the diagnosis-less behavioral failure as an ungrounded,
unsupported item.

The corrected implementation records claim-level population counts in
`ArmResult`. It resolves each claim's Evidence and rule references against the
same run before counting that claim as grounded. A positive claim is clipping
or harmonic distortion; only an ungrounded positive claim enters the
unsupported numerator. A zero positive-claim denominator remains
`not_evaluated` for gate purposes and blocks `meets_target`.

Offline reconstruction from the preserved `result.json` files gives 21/21
grounded contextual-Agent claims and 0/10 unsupported positive fault claims.
All preregistered aggregate and role hard gates are therefore true, so the
corrected validation verdict is `meets_target`.

The generated `run_summary.json`, `metrics.json`, `audit_report.json` and
`STATUS.md` remain historical raw outputs with their original `below_target`
verdict. `corrected_scoring.json` is the append-only authoritative correction;
it does not erase the scorer defect or the one behavioral failure.
