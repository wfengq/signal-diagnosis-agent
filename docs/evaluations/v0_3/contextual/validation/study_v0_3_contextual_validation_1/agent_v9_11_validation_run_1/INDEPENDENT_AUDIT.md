# v9.11 contextual validation independent audit

Date: 2026-09-07 (Asia/Shanghai)

## Disposition

`campaign_execution_complete_scoring_correction_required`

The one-shot execution is valid and complete: all 60 frozen slots reached a
terminal state once in the exact arm-major order. There was no infrastructure
stop or campaign retry. The recorded `below_target` verdict is not accepted as
the final validation verdict because the frozen grounding and unsupported-claim
populations were implemented incorrectly by the scorer.

No provider slot may be rerun. Corrective work must preserve every file listed
under "Frozen original outputs" and must be limited to an append-only scoring
correction produced from the retained results.

## Finding

The frozen protocol defines:

- evidence grounding over all claims on completed diagnoses;
- unsupported-claim rate over all predicted positive fault claims.

The scorer instead uses the fixed 17-case scoreable denominator for both
metrics. Case `675073735bc06f76` ended with `max_planner_retries`, has no
diagnosis and no accepted claim, but its `evidence_refs_complete=false` value
was counted as both an ungrounded item and an unsupported positive claim. This
produced the recorded `16/17` grounding and `1/17` unsupported rate.

The retained contextual-Agent artifacts contain 19 completed diagnoses, 21
claims, 10 predicted positive fault claims, and no completed claim with empty
required references. A corrected scorer must independently resolve all cited
same-run references before emitting corrected metrics and a final verdict.

## Independent checks

- 60 unique terminal slots equal the frozen slot plan in exact order;
- 60 attempt files record one campaign attempt each;
- fixed pipeline has no provider call; both Agent arms use the frozen real
  planner identity;
- v9.11 prompt, causal policy, product tree, evaluation harness and seal hashes
  match `validation_seal_v4`;
- truth was loaded only after all 60 executions completed;
- no raw WAV/audio, waveform, credential, expected outcome or truth label was
  persisted in provider-facing execution artifacts;
- historical seals and campaigns were not modified;
- the sole contextual-Agent behavior failure is the strong-ground-truth
  clipping case `675073735bc06f76`; the runtime rejected three finishes that
  retained an unsupported harmonic sibling and then terminated at the frozen
  planner retry limit.

## Frozen original outputs

- `run_summary.json`: `1fc4d2eaa1a4a265e42333f6d24701d0f0ddfdf650d812eb18e937d0e4c622ec`
- `metrics.json`: `5d438040e9084ef07852a80c763cf9a2b1bccfcc153c402eed5a83b1ec2dd7f4`
- `audit_report.json`: `d77c331c10b18799e536ed04f45a300102f468d7562f7db0ccedee34b71110a6`
- `STATUS.md`: `0828f74c6cf22b3a1561da5a5e0a66e8e454ea8a57498c5fc7dbfcd87dd241c2`
- `execution_ledger.json`: `99a937b01238e3feabbfb56bd0b3ef0485582b7160710050e2d5596e89b4e7d3`

The original `below_target` files are retained as generated evidence. They must
not be overwritten, silently edited or presented as the corrected verdict.
