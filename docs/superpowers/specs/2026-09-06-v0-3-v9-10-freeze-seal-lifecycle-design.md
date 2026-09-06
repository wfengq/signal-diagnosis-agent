# V0.3 v9.10 freeze and seal lifecycle design

Status: approved by user on 2026-09-06.

## Objective

Close the two identity guards exposed by the v9.10 offline gate without
rewriting any historical dataset, seal, campaign result, prompt, threshold, or
score. This work authorizes no model call and no final-test access.

## Development freeze

The frozen development manifest and selected 5% even-growth threshold remain
unchanged. Re-run qualification and calibration into a disposable audit
location. Only if their semantic results match the frozen reports may one new
row be appended to `code_identity_amendment.json`. The row must identify v9.10
as a behavior-bearing product increment, not a typing-only or provenance-only
change, and must record the current implementation SHA plus recomputation
evidence hashes.

The amendment means only that the existing development data and calibration
remain usable for a new v9.10 development confirmation. It does not validate
v9.10 behavior and does not authorize a model run.

## Historical v9.9 validation seal

`validation_seal_v3` belongs exclusively to v9.9. Its original campaign ran
47/60 slots and stopped on infrastructure; a separate diagnostic continuation
ran the remaining 13 no-context slots. The continuation cannot repair the
one-shot protocol, so the original validation remains incomplete and must not
be described as passed or completed.

Do not rename, delete, edit, or bridge the v3 seal to v9.10. Append lifecycle
metadata to `VALIDATION_SEAL_SUPERSESSION.json` that records v3 as historical,
partially executed, and followed by diagnostic-only continuation. Set the
active seal state to none pending v9.10 development confirmation. A v9.10
validation seal can be designed only after a successful, separately authorized
development confirmation.

## Fail-closed behavior

Validation preflight must reject a historical seal before executor creation or
model access. Existing v3 artifacts remain verifiable as historical bytes, but
they are not executable under the active product identity.

## Acceptance

- T-CX241: the append-only development amendment resolves the current
  implementation SHA and contains matching recomputation evidence.
- T-CX242: v3 lifecycle metadata records 47 original terminal slots, 13
  diagnostic-only slots, and no active validation seal.
- T-CX243: preflight rejects historical v3 without creating output or requiring
  a provider call.
- T-CX244: T-CX241 through T-CX244 are registered exactly once.

Passing these gates permits the label `v9_10_harness_complete` only after the
full offline suite, wheel smoke, and Python 3.11/3.12 matrix pass. It does not
permit `development_confirmed`, validation success, performance-improvement,
or final-test claims.
