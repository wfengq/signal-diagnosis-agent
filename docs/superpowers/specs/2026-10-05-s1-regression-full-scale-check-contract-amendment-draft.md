# S1 regression workbench: full-scale check — contract amendment draft

Date: 2026-10-05, Asia/Shanghai.
Status: **draft for operator review. Not applied.** Nothing in this file is in
force. `CONTRACTS_V0_3_CONTEXTUAL.md`, `DECISIONS.md` and
`TEST_PLAN_V0_3_CONTEXTUAL.md` are unchanged by this file.

Basis: OQ-020; operator-approved design
`2026-10-05-s1-regression-clipping-comparison-semantics-design.md` §12 and
`2026-10-05-s1-regression-layer1-characterization-materials-scoring-design.md`
§10. Baseline checked: `codex/v0.2-real-world-validation` tip `fb38314`
(§22 is the last contract section, D042 the last decision, T-CX348 the last
test ID). Section, decision and test numbers below are proposals and must be
re-checked for free numbers on the baseline at the time of application.

This draft does not authorize an implementation plan, implementation,
characterization runs, any tolerance value, RealLLM, seal, or merge.

## A. What kind of change this is

This is an explicit amendment of contract meaning, not a purely additive
clause. Two existing sentences are narrowed in scope by clarification:

| Existing text | Clarified reading |
| --- | --- |
| §22.2 "First-phase numeric compare metrics are only: `clipping_ratio`, `thd_percent`" | Constrains the metrics inside `ComparisonRecord`. It does not forbid a separate record type that judges a different fact. |
| §22.3 "Bool/int/str must not substitute for float" and the `ComparisonRule` shape | Governs `ComparisonRule` / `MetricComparison`. The full-scale sample count is an integer fact in a different object and is not a `ComparisonRule` metric. |

One existing permission is withdrawn: under §22.3 a future approved profile
could have carried a rule for `clipping_ratio`. After this amendment it cannot.

Unchanged: the text of §22.1–§22.6; `ComparisonRecord`, its `required_checks`,
coverage and overall-pass logic; `validate_comparison_record`; product
`profile=None`; frozen V0.2 §§1–64; the single-file diagnosis detector,
thresholds, v9.11 prompt and causal policy; D037/D039.

## B. Proposed contract text — new §23

> ## 23. Regression full-scale check (D043; amends the reading of §22.2–§22.3)
>
> Separate judgment surface for one comparison fact: samples reaching the
> full-scale threshold. It adds new objects next to §22 and does not edit §22
> text. Design:
> `docs/superpowers/specs/2026-10-05-s1-regression-clipping-comparison-semantics-design.md`
> §12. It does not authorize any numeric floor, critical-zone boundary or
> approved-domain limit; those come only from a reviewed layer-1 record (§23.4).
>
> ### 23.1 Scope clarification of §22
>
> The word "only" in §22.2 constrains metrics carried by `ComparisonRecord`.
> The §22.3 float-only rule shape governs `ComparisonRule`. Neither governs
> `FullScaleCheckRecord`. No product `ComparisonProfile` may contain a rule
> whose metric is `clipping_ratio`; product builders must reject such a
> profile. `clipping_ratio` remains displayed, descriptive only, with the
> fixed notice of §23.6.
>
> ### 23.2 Full-scale facts
>
> ```text
> FullScaleFacts =
>   side: ComparisonSide
>   run_id: str
>   bundle_digest: str
>   full_scale_threshold: float          # from the clipping tool snapshot
>   min_consecutive_samples: int         # 2 in the first phase
>   counted_samples: int                 # |x| >= threshold, in runs >= min
>   over_threshold_uncounted: int        # |x| >= threshold, in shorter runs
>   state: "yes" | "no"                  # yes iff counted_samples > 0
>   peak_abs: float
>   analyzed_samples: int
>   pcm_bit_depth: int                   # observed from the WAV header
>   facts_version: str
>   code_digest: str
> ```
>
> Computed by deterministic code on the same samples, range and channel as the
> side's `MeasurementBundle`. The counting criterion must equal the existing
> full-scale mechanism of `detect_clipping` sample for sample. No flat-top
> result contributes. Frozen `ClippingOutput` gains no field. `ratio =
> counted_samples / analyzed_samples` is display only. An LLM never produces
> or alters these values.
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
> Supplied by the user with each submit. Omission is `unknown`, never `yes`.
> The nominal fundamental is the existing
> `ComparisonConditions.nominal_fundamental_hz`. All of these are user
> declarations: the system does not detect periodicity, does not check the
> fundamental against the signal, and has no evidence that a file came from a
> separate render. Reports must say "declared", not "verified".
>
> ### 23.4 Layer-1 record
>
> ```text
> FullScaleMethodFloor =
>   floor_id, version, digest
>   facts_version, code_digest
>   full_scale_threshold, min_consecutive_samples
>   min_pcm_bit_depth: int                    # 16 in the first phase
>   min_samples_per_period: float
>   min_periods_in_range: float
>   critical_zone: reviewed boundary form and values
>   count_floor: reviewed form and values
>   tolerated_difference: str                 # fixed identifier, see below
> ```
>
> Shipped with the product from reviewed configuration only. Clients cannot
> upload it or assert approval. With no record whose identity fields match the
> measurement, every check is `descriptive_only`. The product ships with none
> until a characterization package is reviewed and approved.
>
> The tolerated difference is a stated tolerance decision: sample-wise
> differences of at most one quantization step of the coarser of the two bit
> depths, taken in the one-sided worst case, plus bit-depth conversion. Time
> offset, start phase, added noise and larger gain differences are not
> tolerated.
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
>   declarations per submit
>   baseline_renders, candidate_renders: tuple[FullScaleFacts, ...]
>   counted_baseline_renders, counted_candidate_renders: int
>   floor identity or None
>   status, transition, unmet_conditions: tuple[str, ...]
>   supersedes: check_id | None
>   digest
> ```
>
> One record is produced after every accepted submit that is the anchor or is
> linked to it by `RetestLink.kind = "repeat"`. Producing it does not consume
> the 16-submit quota. Records are immutable; a later record names the one it
> supersedes, and reports show the latest as current and earlier ones as
> superseded history. The subject of the judgment is always the anchor pair.
> The anchor is the comparison with no `repeat` link that is reached by
> following `RetestLink.parent_comparison_id` through `repeat` links; a repeat
> whose parent is itself a repeat belongs to the same anchor. `RetestLink` is
> unchanged.
> The record has its own summary and inherits nothing from the anchor's
> `required_checks`.
>
> A render counts toward a side when it is the anchor file of that side, or a
> repeat file of that side declared `independent_render = "yes"`. Other repeat
> files are shown and not counted, and cannot create a contradiction.
>
> Eligibility. All must hold for a judged status:
>
> | # | Condition | If not |
> | --- | --- | --- |
> | 1 | §22 declarations do not block (`_declarations_block` semantics unchanged) | `not_comparable` |
> | 2 | `repeatability = declared_deterministic` | `not_comparable` (by 1) |
> | 3 | each side has at least 1 counted repeat render | `descriptive_only` |
> | 4 | within each side, `counted_samples` and `state` are identical across counted renders | `not_comparable`, contradiction shown |
> | 5 | `baseline_version != candidate_version` | `descriptive_only` |
> | 6 | `periodic_test_signal = "yes"` on the anchor | `descriptive_only` |
> | 7 | `nominal_fundamental_hz` declared, and samples per period and periods in range both at or above the floor record's limits | `descriptive_only` |
> | 8 | both files have `pcm_bit_depth >= min_pcm_bit_depth` | `descriptive_only` |
> | 9 | a floor record matches the measurement identity | `descriptive_only` |
> | 10 | both sides are outside the critical zone | `descriptive_only` |
>
> A side in state `no` with `peak_abs >= full_scale_threshold` or
> `over_threshold_uncounted > 0` is inside the critical zone. When several
> conditions fail, all are listed and `not_comparable` takes precedence over
> `descriptive_only`.
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
> The repeat requirement is a gate on the determinism declaration. It supplies
> no number to the boundary. How observed variation composes with the floor is
> deferred with the `observed_variable` block.
>
> `validate_full_scale_check_record(record)` recomputes facts references,
> counts, eligibility, status and digest at report build and parse boundaries.
> Tampering raises `ValueError`.
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
> - The report states that the fundamental is declared and unchecked, and the
>   number of consistent renders per side the judgment rests on.
>
> The check never enters `StructuredDiagnosis` and never changes the diagnosis
> causal gate.
>
> ### 23.7 Staged authority
>
> 1. Definitions in this section and T-CX349–T-CX364.
> 2. Implementation of facts, declarations, record and gates under an explicit
>    grant. With no floor record, product output stays `descriptive_only`.
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
> T-CX349–T-CX364. Regression comparison judges a comparison-specific
> full-scale sample count and state in a separate immutable record, gated by
> user declarations and a reviewed layer-1 floor record. `clipping_ratio` is
> permanently descriptive in comparison and no product profile may carry a rule
> for it. This amends the reading of §22.2 "only" and of the §22.3 rule shape
> as stated in §23.1; it is an explicit amendment, not a purely additive
> definition.
>
> **Constraints preserved:** frozen V0.2 §§1–64; §22 text, `ComparisonRecord`
> and its validation; product `profile=None`; the single-file clipping
> detector, thresholds, v9.11 prompt and causal policy; D037/D039; the §22
> block on `observed_variable`.
>
> **Not authorized by this decision:** any floor, critical-zone or
> approved-domain value; a characterization run; a judged product status;
> sub-full-scale flat-top judgment; THD judgment; RealLLM; seal; merge.
>
> **Known limits recorded with the decision:** the fact counts samples at the
> threshold and does not tell a flattened waveform from a high unclipped level;
> sub-full-scale clipping is invisible to it; all gating declarations are
> unverifiable; 8-bit files and chains with any render-to-render variation get
> no judgment.

On approval, OQ-020 moves to `approved` with a pointer to D043.

## D. Proposed test IDs

Definitions only; CS numbers refer to the design's tracking list.

| ID | Behavior | Design ref |
| --- | --- | --- |
| T-CX349 | Count equals the existing full-scale mechanism sample for sample; isolated single samples go to `over_threshold_uncounted` | CS02 |
| T-CX350 | Clean-sine cells with non-zero `clipping_ratio` have `counted_samples = 0`; ratio difference never changes the check status | CS01 |
| T-CX351 | `ClippingOutput` fields, existing `ComparisonRecord` content, `required_checks`, overall pass and validation are unchanged | CS03, CS14 |
| T-CX352 | no → yes is `regression_detected` when eligible, and `descriptive_only` when any gate is missing, however large the change | CS04 |
| T-CX353 | yes → yes: above floor is regression; at or below floor and equal are not; boundary inclusion as stated | CS05 |
| T-CX354 | Decrease and disappearance are `no_regression_detected` with the same-screen notice; missing notice fails | CS06 |
| T-CX355 | Fixed templates contain neither "clipping" nor "no clipping"; regression carries the export-settings notice; THD and ratio coverage lines present | CS07 |
| T-CX356 | `periodic_test_signal` omitted, `unknown` or `no` gives `descriptive_only`; omission is never `yes` | CS08 |
| T-CX357 | Critical zone: either side inside gives `descriptive_only` naming the side; a `no` side at or over threshold, or with uncounted samples, is inside | CS09 |
| T-CX358 | Only anchor files and repeats declared independent are counted; others are shown, not counted, and create no contradiction; byte-identical declared-independent repeats count and are marked | CS10 |
| T-CX359 | Fewer than 1 counted repeat on a side gives `descriptive_only`; inconsistent counted renders give `not_comparable` with the contradiction | CS11 |
| T-CX360 | Product builders reject a profile containing a `clipping_ratio` rule; the ratio stays descriptive with its notice | CS12 |
| T-CX361 | Sub-full-scale clipped pair yields no judged status other than by the full-scale state; auxiliary facts remain visible | CS13 |
| T-CX362 | Equal version strings, missing fundamental, out-of-domain samples per period or periods in range, and bit depth below 16 each give `descriptive_only` with the reason | §12.3 |
| T-CX363 | No matching floor record gives `descriptive_only`; clients cannot upload a floor or approval flag; product ships with none | §12.3 |
| T-CX364 | Record lifecycle: one record per accepted anchor or repeat submit, no quota use, immutable, superseding pointer, `not_comparable` precedence, tamper rejected at validation | §12.2 |

## E. Placement decisions (operator, 2026-10-05)

The approved design left these placements open. The operator decided them on
2026-10-05; the text above already follows them.

1. **Declarations.** The three new declarations live in a new
   `FullScaleDeclarations` object carried next to `ComparisonConditions`.
   §22.1 is untouched and existing submit fingerprints do not change. The
   submit surface of §22.4 (`ComparisonUpload`) gains one optional field.
2. **Computation.** The facts are computed by a comparison-side deterministic
   function reading the same samples as the bundle. `MeasurementBundle`, its
   digest and `MEASUREMENT_VERSION` are unchanged.
3. **Bit depth.** Bit depth is a field of `FullScaleFacts`, read from the WAV
   header. `InputIdentity` is unchanged.

Still to check when this is applied: §23, D043 and T-CX349–T-CX364 assume those
numbers are free on the baseline at that time.

Checked while drafting: at `fb38314`, `RetestLink` in `app/regression.py`
carries `kind` and `parent_comparison_id`, and the service rejects a parent
that is not in the same case, so a repeat submit can be tied to its anchor
without changing that model. Not checked: the rest of `app/regression.py`
beyond the link handling; no tests were run.
