# Contextual Validation Campaign Runner Design

**Status:** approved

**Scope:** evaluation-only orchestration for
`study_v0_3_contextual_validation_1`; no product behavior change and no model
execution in this implementation phase.

## 1. Purpose

Provide the missing auditable runner required to execute the frozen three-arm
contextual validation. The runner must preserve the preregistered case order,
arm order, one-attempt policy, infrastructure stop rule, truth separation, and
append-only evidence requirements.

The implementation phase ends after a new zero-execution `validation_seal_v3`
is created and verified. It does not authorize any provider call.

## 2. Chosen architecture

Add an evaluation-only campaign module under
`signal_diag.evaluation.contextual`. It composes existing product services and
the truth-free deterministic baseline but does not change either one.

The campaign has four isolated responsibilities:

1. **Preflight:** verify the active seal, frozen identities, manifest and WAV
   checksums, exact 20-case/60-arm plan, empty ledger, absent destination,
   canonical active-seal record, live product/harness/profile/prompt/scoring
   identity, provider/model/base-URL/planner/policy identity, credential
   presence, and truth-free outbound boundary.
2. **Arm execution:** run all 20 `contextual_agent` slots, then all 20
   `fixed_pipeline` slots, then all 20 `no_context_ablation` slots.
3. **Append-only recording:** create one directory per arm/case with attempt,
   trace, result, and summary records; update the campaign ledger through
   atomic file replacement without modifying sealed inputs.
4. **Finalization:** only after 60 terminal results, convert results to frozen
   `ArmResult` values, score the contextual and comparison arms, apply the
   preregistered target gates, and write an immutable audit summary.

The CLI exposes separate `preflight-validation` and `run-validation` commands.
The run command requires an explicit authorization flag and refuses historical
or unverified seals.

## 3. Truth and payload boundaries

Execution requests contain only:

- case and arm identity;
- local test/reference signal identifiers;
- `StimulusContext` needed by the selected mode;
- deterministic same-run Evidence and rule evaluations produced through the
  existing runtime.

The executor must not read or receive `role`, `expected_outcome`,
`expected_causal_set`, `confidence_tier`, `scoreable`, source labels, license
labels, or transform provenance. Those fields enter only the offline scoring
step after execution is complete.

Raw WAV bytes, waveform samples, full FFT arrays, credentials, and validation
truth are never placed in the planner payload or persisted provider request.
WAV decoding and deterministic DSP remain local.

## 4. Execution semantics

- Arm order is arm-major and exact: contextual Agent, fixed pipeline, ablation.
- Case order within every arm matches the sealed manifest.
- Each Agent slot receives one campaign attempt. Planner turns inside that
  attempt follow the existing runtime budgets and are not campaign retries.
- A behavioral terminal result is recorded and execution continues.
- The first infrastructure failure is recorded, the campaign is marked
  `infrastructure_stopped`, and no later slot is started.
- Existing output paths, repeated slot identities, non-empty ledgers, or seal
  drift fail before provider construction.
- `ScriptedPlanner` and test oracles are rejected from the real campaign path.
- Fixed-pipeline execution uses `ContextualBaselineRequest` only.

## 5. Persistence and audit artifacts

The output is a new append-only directory containing:

- `preflight.json`;
- a copied seal-identity record, not copied WAV payloads;
- `execution_ledger.json` with planned, started, and terminal slot identities;
- `arms/<arm>/<case_id>/attempts.json`;
- `arms/<arm>/<case_id>/trace.json`;
- `arms/<arm>/<case_id>/result.json`;
- `arms/<arm>/<case_id>/case_summary.json`;
- `run_summary.json`, `audit_report.json`, and `STATUS.md` after finalization.

Temporary files use a sibling `.tmp` name and are atomically replaced. A
campaign never overwrites an existing terminal artifact.

## 6. Error classification

Application/runtime terminal statuses such as planner retry exhaustion are
behavioral failures. Provider connection, authentication, timeout, rate-limit,
or provider-server failures are infrastructure failures. Unknown exceptions are
sanitized, recorded as infrastructure failures, and stop the campaign; raw
provider bodies and credentials are not persisted.

If execution stops early, no aggregate pass claim is produced. Status remains
`infrastructure_stopped`, and continuation requires new written authorization.

## 7. Scoring and gates

Scoring reuses `signal_diag.contextual_scoring@1.0.0-dev.1` without changing
its denominators. The runner evaluates the preregistered aggregate thresholds,
role hard gates, evidence grounding, unsupported-claim rate, unnecessary-tool
rate, natural-even false-positive gate, and paired-ablation delta.

Only a complete 60-slot campaign can receive `meets_target` or
`below_target`. Partial campaigns are not evaluated as complete validation.

## 8. TDD coverage

New tests will prove:

- preflight rejects seal, identity, plan, ledger, destination, and credential
  defects before provider construction;
- execution views exclude every truth/provenance field;
- exact arm-major order and one-attempt behavior;
- behavioral failure continuation and infrastructure failure stop;
- truth-free fixed-pipeline integration;
- append-only/atomic artifact behavior and credential sanitization;
- full-run scoring and partial-run non-evaluation;
- CLI authorization gates and rejection of `ScriptedPlanner`;
- v2 remains byte-identical and zero-execution while v3 binds the new harness
  SHA with unchanged study/product/prompt/profile/scoring identities.

Test IDs will be added after T-CX207 without changing existing meanings.

## 9. Seal supersession

After all deterministic gates pass:

1. preserve `validation_seal_v2` byte-for-byte;
2. append a supersession record marking it
   `superseded_unexecuted_historical_seal` with zero attempts/model calls;
3. append the new evaluation-harness identity amendment;
4. create and verify `validation_seal_v3` from unchanged manifest, WAV
   checksums, slot plan, product code, prompt, profiles, and scoring identity;
5. record 20 planned cases, 60 planned arms, and zero executed arms;
6. stop without running a model, entering final test, committing, or pushing.

## 10. Explicit non-goals

- No product prompt, runtime policy, DSP, Tool, rule, threshold, label, dataset,
  scoring-definition, or application behavior change.
- No validation performance claim.
- No final-test access.
- No automatic continuation after infrastructure failure.
- No replacement or deletion of historical evidence.
