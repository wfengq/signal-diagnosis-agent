# S1 planner-ablation protocol revision design

**Status:** design approved by the operator on 2026-10-01; implementation and seal not authorized.
**Date:** 2026-10-01
**Authority for this document:** operator requested a revised experiment design,
with no new campaign and no product changes.
**Source baseline:** PR #17 merge `8962747ade7052584f3ddcd25e50ad42992273cc`.

## 1. Purpose and scope

Answer whether the current product execution path provides enough quality or
usefulness benefit over the study fixed pipeline to justify its measured
request latency on a named development population. Preserve D037 conservative
single-file behavior and the D038 matching obligations.

This document proposes one follow-up study that repairs timing, oracle, and
population definitions together. It authorizes no implementation, contract/test
definition edits, input generation, seal, model calls, commits, or push. The
operator approved its contents on 2026-10-01 ("审阅通过"). Numerical choices
below are accepted design proposals, not frozen protocol values. The next
authorized document is an implementation plan; implementation requires a
separate grant.

The old study remains `study_s1_planner_ablation_dev_1`. Its machine enum
`fixed_pipeline_dominance` and campaign remain immutable evidence. Formal
dominance was not accepted. This document neither rescales its scores nor
relabels its oracle.

Proposed follow-up identities:

- study: `study_s1_planner_ablation_dev_2`
- scorer: `signal_diag.planner_ablation_scoring`, version `2.0.0-dev.1`
- evidence root: `docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_2/`
- scored arms: `product_agent` and `fixed_pipeline`
- modes: `single_signal` and `paired_reference`

These are proposed names. A later definitions phase must register them without
changing the dev_1 identity validator or interpreting old artifacts as dev_2.

## 2. Alternatives and recommendation

| Approach | Benefit | Limitation | Decision |
|---|---|---|---|
| Repair timing only on the old protocol | Smallest measurement change | Keeps conflicting single oracles and undefined upgrade populations | Reject |
| Repair timing, oracle and populations in one new protocol | Produces an interpretable development comparison with bounded scope | Needs a revised scorer and offline acceptance before sealing | Recommend |
| Replace the product planner now | Removes live planning cost immediately | Existing experiment did not establish an accepted dominance result; changes product behavior | Out of scope |

Reusing development WAV bytes is allowed as declared calibration material.
Their outcomes have been inspected, including during PR #17. A new study ID
does not turn those inputs into held-out evidence. No claim about unseen inputs,
general product reliability, market fit, or production service latency follows
from this follow-up alone.

## 3. What the prior review established

At the source baseline, dev_1 has matching recorded quality 17/20, usefulness
15/20 and completion 20/20 for both arms. Its wall-clock comparison has different
boundaries. Its three single-mode misses contain oracle defects:

- `825a759a0ea47bb7` and `163185980dc8f7a4` have identical test bytes but conflicting
  single oracles. The bad paired reference is absent in single mode.
- `393940e92c58cf0b` and `04f4068ec91d2621` have valid harmonic measurements whose
  THD fails the existing demonstration profile. Without context, conservative
  inconclusive is consistent with the single-file gates.
- The four-case upgrade subset in Wave 5 is descriptive and selected after the
  campaign. It supplies no preregistered upgrade-success estimate.

Evidence paths, pinned to the source baseline:

- `docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_1/WAVE5_PROTOCOL_DEVIATION_REVIEW.md`
- `docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_1/protocol_seal/manifest.json`
- `scripts/run_planner_ablation_realllm_campaign.py`, product timer around
  `execute_product_slot`; fixed timer around `baseline.run` after WAV decoding
- `src/signal_diag/app/service.py`, `submit_contextual_wav` and contextual waiter
- `src/signal_diag/evaluation/planner_ablation/baseline.py`, single no-fault gates
- `docs/CONTRACTS_V0_3_CONTEXTUAL.md` sections 16, 17 and 19
- D038 design `2026-09-30-s1-planner-ablation-utility-study-design.md`

## 4. Common request timing contract

The primary endpoint is request latency from encoded WAV bytes in memory to a
terminal study result with deterministic guidance materialized. The executable
contract must name two events: `request_start` and `terminal_result_ready`.

### 4.1 Start, end and lifecycle

Before either arm's timer: validate the frozen manifest and input hashes, read
encoded WAV files into memory, and prepare a fresh empty execution container.
Imports and immutable profile/corpus loading may occur here for both arms.
Preparing a container must not decode this slot's WAV, analyze its signal, call
the provider, construct a diagnosis, or populate a result cache.

Start the monotonic timer immediately before dispatching the truth-free request
to the arm adapter. Inside the timer, both arms must perform:

1. WAV decoding and identical channel/segment selection;
2. analysis-record creation, repository insertion and context construction;
3. diagnosis execution with the pinned profiles and finish gates;
4. required deterministic postprocessing and context guidance;
5. construction of the complete study terminal result.

Stop only when that result or a classified terminal failure exists. Serialize
artifacts, calculate metrics and write checksums after stopping on both arms.
Container teardown is outside request latency; record teardown failures and
duration separately. No overlapping requests or queued competing work are
permitted. Each measured slot gets a fresh empty container; transport warm-up
calls to the model are forbidden.

The fixed adapter must receive encoded bytes, not pre-decoded signal IDs from
the campaign loop. It must include both test/reference decoding in paired mode
and guidance construction before its terminal marker. The product adapter keeps
the complete contextual submission and contextual waiter, including D037's
single-file path. Use the same requested channel, filenames without role labels,
and user request on both arms.

### 4.2 Attribution and observable output

The common terminal view includes diagnosis or explicit failure, claim/evidence
and rule references, guidance reason codes and required inputs, tool-action
counts, and arm provenance. The product service also performs application work
such as preview/event projection. Record such residual work explicitly; do not
remove it by post-hoc time subtraction or silently change the product path.

This supports a request-level system comparison of two matched diagnosis paths.
It does not isolate the causal duration of LLM reasoning from runtime, queue,
validation or application overhead. Every report must carry that qualification.
If pure planner-only attribution is required later, it needs a separate design.

Emit phase markers for input handling, execution and postprocessing where the
existing boundaries permit observation. Do not fabricate missing phase durations.
The outer common interval is authoritative; partial phase timings are diagnostic.

### 4.3 Proving the boundary before any model run

Offline tests must inject observable delays independently into decoding,
execution and guidance. The outer interval must include each injected delay on
both arms. Delays in serialization after terminal readiness must be excluded.
Prefer a controlled clock and ordered event assertions to flaky timing limits.
Exercise success, correct inconclusive and diagnosis-less failure paths.

The campaign must reject absent/out-of-order timing markers, the wrong timing
contract version, and pre-decoded fixed inputs. `matched_comparison` is derived
from these checks and the gate/report matching proofs, never assigned a constant
true value. A mismatch blocks an accepted comparison even if metrics look good.

## 5. Oracle and population proposal

Retain the ten named development scenarios as a transparent, known-input
calibration population. Evaluate the same physical inputs under both arms.
Record source/master relationships; these scenarios have seven parent masters,
not ten independent sources. No fresh-source generalization is claimed.

### 5.1 Mode-specific proposed oracle

The table is a proposal for dev_2 only. Empty fault sets accompany no-fault and
inconclusive outcomes. Positive sets are exact sets.

| Scenario ID | Single oracle | Paired oracle |
|---|---|---|
| `825a759a0ea47bb7` | no_supported_fault | no_supported_fault |
| `857fac53e4d2e57e` | supported_fault: clipping | supported_fault: clipping |
| `abd9010438d4ad93` | supported_fault: clipping | supported_fault: clipping |
| `a4a0853be9983f8c` | inconclusive | supported_fault: harmonic_distortion |
| `2be730b9113701de` | inconclusive | supported_fault: harmonic_distortion |
| `6fb80bbda391c26c` | supported_fault: clipping | supported_fault: clipping + harmonic_distortion |
| `aa9b4a91b0253c33` | supported_fault: clipping | supported_fault: clipping + harmonic_distortion |
| `393940e92c58cf0b` | inconclusive | no_supported_fault |
| `04f4068ec91d2621` | inconclusive | no_supported_fault |
| `163185980dc8f7a4` | no_supported_fault | inconclusive |

Labels require a recorded rationale from source transformations, stimulus
context, deterministic measurement validity and the versioned gates. Neither
the new product output nor the study baseline's diagnosis can serve as oracle.
Prior outputs motivated this redesign; that exposure must stay disclosed.

An independent offline label review checks all rows before sealing. If a
proposed label disagrees with those facts, revise the unsealed proposal with a
reason. Do not adjust DSP thresholds or finish gates to make a label pass.
The 1% clipping and 5% THD values remain demonstration thresholds.

### 5.2 Observable identity and duplicate weighting

Define a request identity from mode, test-byte hash, reference-byte hash when
present, nominal context when present, channel/segment policy and normalized
user request. Scenario IDs, role names, filenames and hidden truth labels do
not distinguish otherwise identical analysis requests. Execution filenames are
constant `input.wav` and `reference.wav`.

Equal request identities must have equal oracle outcome/fault sets. This
invariant catches the clean/invalid-reference collision before execution.
Single requests for `825a...` and `1631...` share one execution and one scored
unit, represented by `825a...`; an explicit alias maps `1631...` to that result.
Their paired requests remain distinct because their reference bytes differ.

The proposed schedule therefore has 9 unique single requests and 10 paired
requests: 19 keys per arm per repetition. Scenario-oriented tables may show
both aliases but must not count the shared result twice in primary metrics.
Completion and quality use the frozen unique-request schedule, including
behavioral failures. Any unexpected collision or absent mapping blocks sealing.

### 5.3 Upgrade populations frozen before execution

Register an explicit seven-scenario upgrade population U:

| Members | Count | Context obtainable | Valid | Sufficient | Purpose |
|---|---:|---|---|---|---|
| `a4a0853be9983f8c`, `2be730b9113701de` | 2 | true | true | true | Harmonic attribution |
| `6fb80bbda391c26c`, `aa9b4a91b0253c33` | 2 | true | true | true | Additional causal coverage beyond clipping |
| `393940e92c58cf0b`, `04f4068ec91d2621` | 2 | true | true | true | Resolve natural harmonic ambiguity |
| `163185980dc8f7a4` | 1 | true | false | false | Invalid-reference negative control |

These labels are proposed from input construction and need the offline review
above. `obtainable` means available within this protocol, not obtainable by an
ordinary user. No execution arm receives these labels or this population table.

Define C as members of U whose supplied context is obtainable, valid and
sufficient. Proposed sizes are |U|=7 and |C|=6. C is fixed independently of
guidance emission, initial diagnosis, execution completion and final success.

For each arm/repetition, S counts members of C with a completed paired result
matching the paired oracle, valid claim support and the specified target
resolution/additional coverage. Report S/7 and S/6 side by side. Report the
negative control's correct abstention separately. It remains a non-resolution
in S/7; correct abstention is not a planner correctness error. Thus the maximum
full-population resolution rate is 6/7 by construction, which must be visible.
Any zero conditional population is not evaluable, never 100% success.

Also report each scenario's observed single-to-paired transition. If single
already delivers the target, do not call paired correctness an incremental
gain. That observation does not remove the case from U or C. Combined scenarios
can gain causal coverage despite already delivering useful clipping.

The proposed guidance-eligible single population G is the two harmonic and two
natural-even scenarios, subject to offline confirmation of section 17 emission
rules. Report emitted-and-correct guidance over all four scheduled G requests,
including failures, plus conditional template conformance among emitted
guidance. Missing guidance must not disappear from the first denominator.
Guidance is deterministic product behavior, never planner skill.

## 6. Repetitions, order and resource controls

Propose three repetitions of each unique request on each arm: 19 x 2 x 3 = 114
scheduled executions, including 57 product executions. Repetitions are fixed
in advance and include unsuccessful runs. They are not retries or independent
new sources. Three runs offer a small descriptive variability check, not a
model-stability certification or a population confidence claim.

Use canonical request-key order from the frozen schedule. For key index i and
repetition r, execute product then fixed when (i+r) is even, fixed then product
otherwise. Execute pairs sequentially, with repetition as the outer loop. Seal
the complete expanded slot list; do not dynamically reorder after an error.
This supersedes dev_1 arm-major order only for dev_2.

Each scheduled slot has one campaign attempt. Product-internal repair and
provider-transport retries retain their pinned product configuration; record
their exact effective limits, actual counts, elapsed time and token usage.
Changing those limits is not a campaign-level retry policy. Fixed uses the same
applicable deterministic rule/tool budgets. No best-of-three selection.

Propose a 120-second common outer slot deadline. Infrastructure failures,
including provider authentication/transport exhaustion, persistence failure or
deadline expiry without a valid terminal result, stop the campaign. Preserve
started and unstarted schedule slots; no accepted conclusion is available from
a truncated campaign. Product behavioral failures already represented by the
runtime, including exhausted diagnosis/repair budgets, continue and remain
failures in their denominators. Classification must use typed causes rather
than treating every non-success as infrastructure failure.

Before seal, record the exact product runtime limits, request timeout, provider
retry policy, model/prompt/settings and token limits supported by that provider
path. Before a RealLLM grant, present a numerical worst-case request/token budget
derived from those limits and the 57 scheduled product executions. Unknown
limits, unavailable retry telemetry or an unbounded request configuration block
execution. No model prices or total-ownership-cost claims are assumed here.

## 7. Metrics and decision rules proposed for review

For each mode and repetition report:

- outcome accuracy and exact outcome-plus-causal-set accuracy over every unique
  scheduled request; missing diagnosis scores zero;
- useful-terminal rate: completed, oracle-compatible supported fault or justified
  no-supported-fault; incorrect confident output is not useful;
- completion including a valid inconclusive diagnosis;
- unsupported positive claims over positive claims, and grounding over all
  completed-diagnosis claims, with explicit counts and zero-denominator states;
- shared-boundary mean, median, nearest-rank p95 and maximum latency including
  behavioral failure time; zero/negative/non-finite timing is invalid;
- actual tool calls including repeats/failed calls, rule evaluations, planner
  calls, runtime repairs, transport retries and available token usage;
- upgrade and guidance metrics from the fixed populations above.

Per-arm denominators are 9 single and 10 paired per repetition, or 27 and 30
across repetitions. Total execution count 114 is never a per-arm denominator.
Use equal mode weighting for a descriptive aggregate; mode/round tables remain
authoritative. Related scenarios and repetitions do not create independent
samples. No p-values or generalization intervals are proposed for this small,
previously inspected development set.

Claim safety requires both valid same-run references and evidence/rule support
for the declared fault under that mode. Reference existence alone is not a
semantic safety proof. Each arm/mode/round must have an evaluable positive-claim
population; zero claims or missing claim data block a positive study conclusion.
No supported fault may be added solely because it exists in source ground truth.

Proposed accepted decision conditions:

1. All identity, timing, oracle, report-parity and matching prerequisites pass;
   the entire planned campaign completes; both arms pass safety. Otherwise the
   accepted conclusion is `insufficient_evidence`, with explicit reason codes.
2. `fixed_pipeline_dominance` requires zero accepted quality, usefulness,
   completion, upgrade or guidance regression in every mode/round. The proposed
   non-inferiority margin is exactly zero. It also requires at least 20% mean
   latency reduction and 100 ms absolute mean saving in each mode/round. Fixed
   p95 and mean tool-action count must not regress. These are engineering
   decision bands, not statistical non-inferiority claims.
3. `planner_advantage` uses quality as the sole primary superiority endpoint:
   at least one additional correctly diagnosed unique request in the same mode
   in each round, with no quality regression in the other mode and no
   usefulness/completion/upgrade/guidance regression. A utility-only improvement
   is reported as secondary evidence rather than changing endpoints after runs.
4. Other complete comparisons yield `insufficient_evidence`. Equal performance
   alone does not establish equivalence outside the frozen development band.

Zero tolerated loss is proposed because this known population is small and no
user-backed quality-loss allowance has been established. A nonzero allowance
would need an explicit rationale in the reviewed protocol. Do not encode zero
as a tiny epsilon to bypass the current protocol model's `gt=0` field.

The scorer must independently derive matched status and constrained regressions
from verified records; callers cannot assert them with default booleans. Always
retain machine metrics, prerequisite results and accepted review status as
distinct fields. No enum authorizes product replacement.

## 8. Versioning, seal and architecture

The existing dev_1 identity validator is hard-coded to its study; its decision
model forbids a zero gap and its score entry has no repetition/alias or complete
timing contract. It is not an executable dev_2 protocol. A later authorized
implementation must add explicit version dispatch or a separate v2 model/scorer
while preserving the old study's reproducer and foreign-identity rejection.

Keep `evaluation` independent of `app`. App-owned study adapters map byte
requests through the product service or fixed pipeline to study-owned fields.
Evaluation owns schedules, oracle/eligibility labels, verified population
identities, pure metrics and decision logic. Do not add a fixed product route,
change product composition, or change the historical contextual baseline.

The new sealed manifest must bind:

- explicit unique-request schedule, aliases, scenario/source/master relations;
- every mode oracle, rationale, U/C/G membership and offline label-review record;
- timing boundary, lifecycle, order, repetitions, limits and decision bands;
- original WAV byte hashes and canonical request hashes;
- immutable implementation commit, product/prompt/profile/corpus hashes, study
  scorer/adapter hashes, and the actual campaign and sealing script hashes;
- relevant dependency/runtime versions and environment measurement policy;
- authorization references identifying the operator's actual grants.

Preflight recomputes file/input/code hashes rather than trusting stored strings.
Record the verified seal digest and effective configuration in every campaign.
Scoring constructs its input from that verified manifest and requires every
scheduled record exactly once. Aliases, missing slots, unexpected retries and
cross-study records cannot silently change populations.

Generation refuses any existing destination, including an empty directory;
verification is read-only and verifies referenced input/code bindings as well
as the manifest index. Tests may generate temporary fixtures only after an
offline implementation grant. No tool may regenerate dev_1 as a migration step.

## 9. Offline acceptance required before a new seal

The later plan must map these obligations to new available test IDs after
checking the merged registry. This design does not register or execute tests.

| Obligation | Required falsification before sealing |
|---|---|
| Common timing boundary | Decode/guidance delays excluded on either arm must fail; artifact-write delay inclusion must fail |
| Oracle consistency | Identical single requests with conflicting labels fail; a bad withheld reference cannot alter a single oracle |
| Existing product gates | Natural controls remain inconclusive without context; no threshold relaxation; clipping and paired five-rule matching remain covered |
| Source and alias accounting | Duplicate single request executes/scores once; both logical scenario links survive; 19 keys/arm/round derived from content |
| Upgrade eligibility | Guidance absence, behavioral failure or a lucky initial answer cannot shrink U/C; invalid reference stays outside C; zero C is not success |
| Full terminal populations | Correct inconclusive completes; failed/no-diagnosis slots stay in all required quality/completion denominators |
| Safety and utility | Grounded but mode-unsupported fault fails safety; incorrect no-fault cannot gain usefulness; zero positive claims blocks a positive conclusion |
| Decision integrity | Mode/round regression cannot hide in a pooled mean; equal completion may still allow dominance; timing defects force insufficient evidence |
| Provenance | Actual Scripted dry-run artifacts relabeled product are rejected; fail-on-call provider spies record zero calls in offline acceptance |
| Identity and preservation | Altered WAV, prompt, runner, scorer, labels, aliases or schedule fail; dev_1 still reproduces; verify leaves files unchanged; generate refuses existing targets |
| Failure accounting | Injected infrastructure stop preserves full schedule and blocks conclusion; behavioral failure continues without a replacement attempt |

Run repository-required focused/cumulative tests, Ruff, mypy, architecture
checks and diff checks in that later implementation stage. Offline validation
must neither score historical RealLLM outputs under the revised oracle as new
study evidence nor call a provider to test connectivity.

## 10. Handoff and bounded next steps

1. Review this design, including the known-input scope, 19-key alias scheme,
   seven-scenario upgrade population, three repetitions and zero-loss proposal.
2. If approved, write an implementation plan identifying additive definitions,
   new test IDs and bounded study-only code changes. No execution follows from
   written-spec approval alone.
3. Under a later implementation grant, implement and pass the offline acceptance
   matrix. Do not create the real protocol seal during harness acceptance.
4. Obtain a seal grant on the concrete candidate manifest, label review, schedule,
   numeric bands and budgets. Create an additive dev_2 seal and verify it.
5. Present the exact sealed identity and execution budget for a separate RealLLM
   grant. A successful campaign then gets its own result review.
6. Any product planner change requires a separate product design, contracts,
   tests and operator implementation authorization.

Current stop: this design document only. No campaign, product edit, protocol
seal, contract/test definition edit, commit or push is part of this work.
