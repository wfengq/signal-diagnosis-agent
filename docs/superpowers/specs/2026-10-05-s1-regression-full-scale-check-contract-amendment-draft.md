# S1 regression workbench: full-scale check — contract amendment draft

Date: 2026-10-05, Asia/Shanghai.
Status: **draft for operator review, revision 2. Not applied.** Nothing in this
file is in force. `CONTRACTS_V0_3_CONTEXTUAL.md`, `DECISIONS.md` and
`TEST_PLAN_V0_3_CONTEXTUAL.md` are unchanged by this file.

Basis: OQ-020; operator-approved design
`2026-10-05-s1-regression-clipping-comparison-semantics-design.md` §12–§13 and
`2026-10-05-s1-regression-layer1-characterization-materials-scoring-design.md`
§10–§11. Baseline checked: `codex/v0.2-real-world-validation` tip `fb38314`
(§22 is the last contract section, D042 the last decision, T-CX348 the last
test ID; an independent review confirmed §23, D043 and T-CX349 onward are
free). Numbers must be re-checked at the time of application.

Revision 2 incorporates an independent read-only review of revision 1 and four
operator decisions of 2026-10-05 (section E). Revision 2 itself has not been
reviewed.

This draft does not authorize an implementation plan, implementation,
characterization runs, any floor value, RealLLM, seal, or merge.

## A. What kind of change this is

This is an explicit amendment of contract meaning, not a purely additive
clause. Existing sentences whose meaning changes:

| Existing text | Change |
| --- | --- |
| §22.2 "First-phase numeric compare metrics are only: `clipping_ratio`, `thd_percent`" | Read as constraining the metrics inside `ComparisonRecord`. It does not forbid a separate record type that judges a different fact. |
| §22.3 "Bool/int/str must not substitute for float" and the `ComparisonRule` shape | Read as governing `ComparisonRule` / `MetricComparison`. The full-scale sample count is an integer fact in a different object. |
| §22.3: a future approved profile may carry a rule for any first-phase metric | Withdrawn for `clipping_ratio`. |
| §22.3 / §22.4 overall pass of `ComparisonRecord` | Text unchanged, but because `required_checks` still contains `clipping_ratio` and that metric can never have a rule, the overall pass of a `ComparisonRecord` can never be true under any future product profile. The field is retained and is effectively dead. |
| §22 preamble, §22.6 item 5 and D042: product comparison tolerances and pass/fail are not authorized | Partly superseded. §23.4 states one tolerance decision (what a floor record tolerates) and §23.5 defines a product judgment path. No tolerance *value* is authorized, and no judged product status is reachable until a floor record is approved. |
| §22.4 submit fingerprint coverage | Extended to cover `FullScaleDeclarations`. Fingerprints are held in memory for the session only, so no stored value is invalidated. |
| §22.4 listings of `ComparisonUpload` and `RegressionCaseSnapshot`; report schema | Each gains fields (declarations; facts and check records). These models are strict (`extra="forbid"`), so this is a schema change. |

Unchanged: `ComparisonRecord` content and validation, `required_checks`,
`MeasurementBundle` and its digest, `MEASUREMENT_VERSION`, `InputIdentity`,
`RetestLink`, the 16-submit quota, product `profile=None`; frozen V0.2
§§1–64; the single-file diagnosis detector, thresholds, v9.11 prompt and
causal policy; D037/D039.

## B. Proposed contract text — new §23

> ## 23. Regression full-scale check (D043; amends the reading of §22)
>
> Separate judgment surface for one comparison fact: samples reaching the
> full-scale threshold. It adds new objects next to §22. Design:
> `docs/superpowers/specs/2026-10-05-s1-regression-clipping-comparison-semantics-design.md`
> §12–§13. It does not authorize any count floor, critical-zone boundary or
> approved-domain limit; those come only from a reviewed floor record (§23.4).
>
> ### 23.1 Scope clarification of §22
>
> The word "only" in §22.2 constrains metrics carried by `ComparisonRecord`.
> The §22.3 float-only rule shape governs `ComparisonRule`. Neither governs
> `FullScaleCheckRecord`.
>
> `clipping_ratio` remains displayed and is descriptive only, with the fixed
> notice of §23.6. A `ComparisonProfile` containing a rule whose metric is
> `clipping_ratio` must be rejected where the product service is constructed.
> Profiles defined under `tests/` for fixture purposes are exempt and remain
> unloadable by product builders, as §22.3 already requires. As a consequence
> the overall pass of a `ComparisonRecord` can never be true on the product
> path; reports must not present it as a pending result.
>
> ### 23.2 Full-scale facts
>
> ```text
> FullScaleFacts =
>   side: ComparisonSide
>   run_id: str
>   bundle_digest: str                   # the side's MeasurementBundle
>   full_scale_threshold: float          # from the ClippingInput snapshot
>   min_consecutive_samples: int         # fixed 2; the DSP default, recorded
>   counted_samples: int                 # |x| >= threshold, in runs >= min
>   over_threshold_uncounted: int        # |x| >= threshold, in shorter runs
>   state: "yes" | "no"                  # yes iff counted_samples > 0
>   peak_abs: float
>   analyzed_samples: int
>   pcm_bit_depth: int                   # bits per sample from the WAV header
>   facts_version: str
>   digest: str                          # canonical JSON, as §22.2
> ```
>
> Layering. Counting is a deterministic function in `dsp/`. A `tools/` adapter
> calls it during `measure_output`, in the same repository lifetime and on the
> same samples, resolved range and channel as the side's clipping measurement;
> samples are not available afterwards. The facts are stored beside the
> bundle, not inside it; `MeasurementBundle`, its digest and
> `measurement_version` are unchanged. `app/` passes the bit depth it already
> holds from the WAV loader. Judgment is a pure function in `rules/`;
> orchestration and record keeping are in `app/`. New files in frozen-path
> packages are appended to the architecture allowlist (T-CX346 practice).
>
> The counting criterion must equal the existing full-scale mechanism of
> `detect_clipping` sample for sample. No flat-top result contributes. Frozen
> `ClippingOutput` gains no field. `ratio = counted_samples /
> analyzed_samples` is display only. An LLM never produces or alters these
> values.
>
> If a side's clipping tool result is `error` or carries no output, no facts
> exist for that side and every check using it is `not_comparable`.
>
> ### 23.3 Declarations
>
> ```text
> FullScaleDeclarations =
>   periodic_test_signal: "yes" | "no" | "unknown"
>   baseline_independent_render: "yes" | "no" | "unknown"
>   candidate_independent_render: "yes" | "no" | "unknown"
> ```
>
> Optional on each submit, carried next to `ComparisonConditions` and covered
> by the submit fingerprint. Omission is `unknown`, never `yes`. The nominal
> fundamental is the existing `ComparisonConditions.nominal_fundamental_hz`.
>
> `periodic_test_signal` is read from the anchor submit only. The two
> independence declarations are read from repeat submits only and are ignored
> on the anchor. To repeat one side, the user resubmits the other side's
> original file and declares it `no`.
>
> All of these are user declarations. The system does not detect periodicity,
> does not check the fundamental against the signal, and has no evidence that
> a file came from a separate render. Reports say "declared", not "verified".
>
> ### 23.4 Floor record
>
> ```text
> FullScaleMethodFloor =
>   floor_id, version, digest
>   facts_version
>   full_scale_threshold, min_consecutive_samples
>   min_samples_per_period: float
>   min_periods_in_range: float
>   critical_zone: reviewed boundary form and values
>   count_floor: reviewed form and values
>   tolerated_difference: str                 # fixed identifier, see below
> ```
>
> Shipped with the product from reviewed configuration only. Clients cannot
> upload it or assert approval. A record applies only when `facts_version`,
> `full_scale_threshold` and `min_consecutive_samples` equal those of both
> sides' facts. With no applicable record, no check reaches a judged status
> (it is `descriptive_only` or `not_comparable`). The product ships with none
> until a characterization package is reviewed and approved.
>
> Tolerance decision. A floor record tolerates sample-wise differences of at
> most one quantization step of the coarser of the two bit depths, taken in
> the one-sided worst case (every sample moved one step in the same
> direction), plus bit-depth conversion. Time offset, start phase, added noise
> and larger gain differences are not tolerated.
>
> Critical zone. The reviewed `critical_zone` applies to a side in either
> state. It must contain every signal that a tolerated difference can move
> across the yes/no boundary. As a fixed minimum, independent of any record, a
> side in state `no` is inside the critical zone when
> `peak_abs >= full_scale_threshold - step`, where `step` is one quantization
> step of the coarser of the two files' bit depths. (For a `no` side,
> "peak at or above threshold" and "has over-threshold uncounted samples" are
> the same condition; both are covered by this minimum.)
>
> ### 23.5 Check record
>
> ```text
> FullScaleCheck.status =
>   "not_comparable" | "descriptive_only"
>   | "regression_detected" | "no_regression_detected"
>
> FullScaleCheckRecord =
>   check_id
>   anchor_comparison_id, anchor_digest
>   repeat_comparison_ids: tuple[str, ...]
>   uncounted_repeats: tuple[(comparison_id, side, reason), ...]
>   declarations per submit
>   baseline_renders, candidate_renders: tuple[FullScaleFacts, ...]
>   counted_baseline_repeats, counted_candidate_repeats: int
>   floor identity or None
>   status, transition
>   unmet_conditions: tuple[str, ...]
>   unevaluated_conditions: tuple[str, ...]
>   supersedes: check_id | None
>   digest
> ```
>
> Anchor. A completed comparison with no link, or with a `repair` or
> `recommendation` link, is its own anchor. A completed comparison with a
> `repeat` link belongs to the anchor reached by following
> `parent_comparison_id` through `repeat` links. `RetestLink` is unchanged.
>
> Production. One record is produced after every completed comparison, for
> that comparison's anchor. A failed submit produces none. An idempotent
> replay of a `request_id` produces none. Producing a record does not consume
> the 16-submit quota. Records are immutable; a later record for the same
> anchor names the one it supersedes, and reports show the latest as current
> and earlier ones as superseded history. The subject of the judgment is
> always the anchor pair. The record has its own summary and inherits nothing
> from the anchor's `required_checks`.
>
> Counted renders. All eligibility conditions that read declarations or
> versions read the anchor submit. A repeat file counts toward a side only
> when all hold:
>
> - its side is declared independent (`yes`) on that repeat submit;
> - the repeat's `MeasurementSelection`, resolved start and end sample,
>   sample rate, channel and both version strings equal the anchor's;
> - the repeat's own §22 declarations do not block;
> - facts exist for that file.
>
> Any other repeat file is shown with its reason in `uncounted_repeats`, is
> not counted, and cannot create a contradiction. A counted repeat whose bytes
> equal the anchor file's is counted and marked byte-identical.
>
> Eligibility. All must hold for a judged status:
>
> | # | Condition | If not |
> | --- | --- | --- |
> | 1 | facts exist for both anchor files | `not_comparable` |
> | 2 | the anchor's §22 declarations do not block (`repeatability = declared_deterministic` included; existing blocking semantics unchanged) | `not_comparable` |
> | 3 | each side has at least 1 counted repeat | `descriptive_only` |
> | 4 | within each side, `counted_samples` and `state` are identical across the anchor file and all counted repeats | `not_comparable`, contradiction with the declaration shown |
> | 5 | `baseline_version != candidate_version` | `descriptive_only` |
> | 6 | `periodic_test_signal = "yes"` | `descriptive_only` |
> | 7 | both files have `pcm_bit_depth >= 16` | `descriptive_only` |
> | 8 | an applicable floor record exists | `descriptive_only` |
> | 9 | `nominal_fundamental_hz` is declared, and samples per period (`sample_rate_hz / nominal_fundamental_hz`) and periods in range are both at or above the floor record's limits | `descriptive_only` |
> | 10 | both sides are outside the critical zone (§23.4) | `descriptive_only` |
>
> Every unmet condition is listed. Where the existing declaration check
> reports only its first blocking field, condition 2 is listed once with that
> field. The fixed-minimum part of condition 10 is always evaluated. When
> condition 8 fails, condition 9's limits and the reviewed part of condition
> 10 cannot be evaluated and are listed in `unevaluated_conditions`.
> `not_comparable` takes precedence over `descriptive_only`.
>
> On the product path the anchor's `ComparisonRecord` keeps its own status
> (`descriptive_only` with no profile) even when the check record is
> `not_comparable`; reports show both and do not reconcile them.
>
> Judgment when eligible:
>
> | Baseline → candidate | Status |
> | --- | --- |
> | no → no | `no_regression_detected` |
> | no → yes | `regression_detected`, by state, no numeric floor |
> | yes → yes, increase above `count_floor` | `regression_detected` |
> | yes → yes, increase at or below `count_floor`, or equal | `no_regression_detected` |
> | yes → no, or yes → yes with fewer samples | `no_regression_detected` |
>
> Every judged or unjudged record shows both sides' `counted_samples`,
> `peak_abs` and counted-repeat numbers; a yes → yes record also shows the
> difference and the floor.
>
> The repeat requirement is a gate on the determinism declaration. It supplies
> no number to the boundary. How observed variation composes with the floor is
> deferred with the `observed_variable` block.
>
> Validation. `validate_full_scale_check_record(record)` runs at report build
> and parse boundaries and raises `ValueError` on failure. It recomputes
> anchor resolution, counted-render selection, eligibility, status and all
> digests from the stored facts, declarations and floor record. It
> cross-checks each `FullScaleFacts` against its bundle: `bundle_digest`,
> `state == "yes"` iff `ClippingOutput.full_scale_detected`, `peak_abs`,
> `analyzed_samples`, threshold. `counted_samples` and
> `over_threshold_uncounted` cannot be recomputed after the submit because
> samples are not retained; they are protected by the facts digest only.
>
> ### 23.6 Fixed wording
>
> Judgment and notice text for this check uses fixed templates and never the
> words "clipping" or "no clipping". It states that samples reaching the
> full-scale threshold increased, did not increase, or decreased.
>
> - `regression_detected` carries, on the same screen: the difference may come
>   from export settings (bit depth, dither, gain, start point) and not
>   necessarily from the version.
> - A decrease or disappearance carries, on the same screen, a notice that
>   such samples decreased, with both values, and no stated cause.
> - Every report showing this check lists, on the same screen, that THD is not
>   covered and that `clipping_ratio` is descriptive only.
> - `clipping_ratio` carries: the ratio includes flat-top detection results
>   and may be non-zero on unclipped low-frequency or low-level input.
> - Every judged record states: the declarations are declared, not verified;
>   the fundamental is declared and unchecked, and if it is wrong the
>   approved-domain limits do not apply; the number of consistent renders per
>   side the judgment rests on.
>
> The check never enters `StructuredDiagnosis` and never changes the diagnosis
> causal gate.
>
> ### 23.7 Staged authority
>
> 1. Definitions in this section and T-CX349–T-CX370.
> 2. Implementation of facts, declarations, record and gates under an explicit
>    grant. With no floor record, product output has no judged status.
> 3. Layer-1 characterization run under a separate grant, through the full tool
>    path, after step 2.
> 4. Review and approval of a floor record under a separate grant. Only then
>    can a product check reach a judged status.
> 5. Sub-full-scale flat-top judgment, any change to the `observed_variable`
>    block, THD judgment, RealLLM, seal and merge remain external gates.

## C. Proposed decision record — D043

> ## D043 — Regression full-scale check as a separate judged record (OQ-020)
>
> **Decision (operator, date of approval):** Register V0.3 §23 and
> T-CX349–T-CX370. Regression comparison judges a comparison-specific
> full-scale sample count and state in a separate immutable record, gated by
> user declarations and a reviewed floor record. `clipping_ratio` is
> permanently descriptive in comparison and no product profile may carry a
> rule for it.
>
> **This is an explicit amendment.** It narrows the reading of §22.2 "only"
> and of the §22.3 rule shape; withdraws the possibility of a `clipping_ratio`
> rule, which leaves `ComparisonRecord` overall pass permanently not true on
> the product path; partly supersedes the D042 / §22.6 statement that product
> tolerances and pass/fail are not authorized, by fixing what a floor record
> tolerates and defining a judgment path, while authorizing no value; and
> extends the §22.4 submit fingerprint, upload and snapshot shapes.
>
> **Constraints preserved:** frozen V0.2 §§1–64; `ComparisonRecord` and its
> validation; `MeasurementBundle` and `measurement_version`; `RetestLink`;
> product `profile=None`; the single-file clipping detector, thresholds, v9.11
> prompt and causal policy; D037/D039; the §22 block on `observed_variable`.
>
> **Not authorized by this decision:** any floor, critical-zone or
> approved-domain value; a characterization run; a judged product status;
> sub-full-scale flat-top judgment; THD judgment; RealLLM; seal; merge.
>
> **Known limits recorded with the decision:** the fact counts samples at the
> threshold and does not tell a flattened waveform from a high unclipped level;
> sub-full-scale clipping is invisible to it; all gating declarations are
> unverifiable; 8-bit files and chains with any render-to-render variation get
> no judgment; sample counts cannot be recomputed at validation.

On approval, OQ-020 moves to `approved` with a pointer to D043.

## D. Proposed test IDs

Definitions only; CS numbers refer to the design's tracking list.

| ID | Behavior | Ref |
| --- | --- | --- |
| T-CX349 | Count equals the existing full-scale mechanism sample for sample; isolated single samples go to `over_threshold_uncounted`; facts use the bundle's range and channel | CS02 |
| T-CX350 | Clean-sine cells with non-zero `clipping_ratio` have `counted_samples = 0`; a ratio difference never changes the check status | CS01 |
| T-CX351 | `ClippingOutput`, `MeasurementBundle` digest, `ComparisonRecord` content, `required_checks`, overall pass and validation are unchanged | CS03, CS14 |
| T-CX352 | no → yes is `regression_detected` when eligible, and has no judged status when any gate is missing, however large the change | CS04 |
| T-CX353 | yes → yes: above floor is regression; at or below floor and equal are not | CS05 |
| T-CX354 | Decrease and disappearance are `no_regression_detected` with the same-screen notice; missing notice fails | CS06 |
| T-CX355 | Templates contain neither "clipping" nor "no clipping"; regression carries the export-settings notice; THD and ratio coverage lines present; "declared, not verified", unchecked-fundamental and render-count lines present; required values shown | CS07 |
| T-CX356 | `periodic_test_signal` omitted, `unknown` or `no` gives `descriptive_only`; read from the anchor only | CS08 |
| T-CX357 | Critical zone: either side inside gives `descriptive_only` naming the side; fixed minimum for a `no` side within one coarser-depth step below threshold; a one-step difference on such a baseline does not yield `regression_detected` | CS09 |
| T-CX358 | Counted-repeat rules: declared independent, same selection/range/rate/channel/versions, own declarations not blocking; others listed with reason and create no contradiction; byte-identical counted repeats are marked; independence declarations ignored on the anchor | CS10 |
| T-CX359 | No counted repeat on a side gives `descriptive_only`; inconsistent counted renders give `not_comparable` with the contradiction | CS11 |
| T-CX360 | Service construction rejects a profile with a `clipping_ratio` rule; test fixtures exempt; ratio stays descriptive with its notice; overall pass not presented as pending | CS12 |
| T-CX361 | Sub-full-scale clipped pair gets no judgment beyond the full-scale state; auxiliary facts visible | CS13 |
| T-CX362 | Equal versions, missing fundamental, out-of-domain samples per period or periods in range, and bit depth below 16 each give `descriptive_only` with the reason | §23.5 |
| T-CX363 | No floor record, or one whose identity fields mismatch, gives no judged status; unevaluable conditions are listed as unevaluated; clients cannot upload a floor or approval flag | §23.4 |
| T-CX364 | Record lifecycle: one per completed comparison, none for failed submits or idempotent replays, no quota use, immutable, superseding pointer | §23.5 |
| T-CX365 | Anchor resolution: repeat of repeat reaches the root; `repair` and `recommendation` comparisons are their own anchors | §23.5 |
| T-CX366 | Blocking anchor declarations and missing facts (tool error) give `not_comparable`; `not_comparable` precedes `descriptive_only`; all unmet conditions listed | §23.5 |
| T-CX367 | Validation recomputes selection, eligibility, status and digests; cross-checks state, peak, length and threshold against the bundle; tampering raises | §23.5 |
| T-CX368 | The check never enters `StructuredDiagnosis` or the causal gate; legacy diagnosis paths unchanged | §23.6 |
| T-CX369 | Layering: counting in `dsp/`, adapter in `tools/`, judgment in `rules/`; allowlist appended; `rules/` imports no `app/` | §23.2 |
| T-CX370 | Submit fingerprint covers `FullScaleDeclarations`; strict models reject unknown fields; omission equals `unknown` | §23.3 |

## E. Operator decisions recorded in this draft (2026-10-05)

Placement:

1. The three new declarations live in a new `FullScaleDeclarations` object
   next to `ComparisonConditions`; §22.1 is untouched.
2. `MeasurementBundle`, its digest and `MEASUREMENT_VERSION` are unchanged.
   Refined after review: the facts cannot be computed after measurement, so
   counting is a `dsp/` function called by a `tools/` adapter at measurement
   time, with the facts stored beside the bundle.
3. Bit depth is a field of `FullScaleFacts`; `InputIdentity` is unchanged.

After independent review:

4. A repeat must share selection, resolved range, sample rate, channel and
   versions with its anchor to be counted; eligibility reads the anchor.
5. The reviewed critical zone applies to both states, with a fixed minimum of
   one coarser-depth step below the threshold for a `no` side.
6. Section A lists every existing sentence whose meaning changes, including
   the tolerance-authority statement and the dead overall-pass field.

Not verified: the full tool path with a real WAV encode and decode; 24- and
32-bit behavior (float32 storage against threshold 0.99); whether existing
tests pin snapshot or report JSON shape; `app/regression_reporting.py`,
`app/multipart.py` and the static page were not read. No tests were run.
