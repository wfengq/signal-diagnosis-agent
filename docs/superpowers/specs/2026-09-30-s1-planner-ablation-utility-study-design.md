# S1 default-path utility and planner-ablation study

**Status:** study-shape approved (OQ-019 / D038, operator 2026-09-30).
Implementation plan revised after Codex Wave 0 review the same day; awaiting
accept before Wave 1 definitions. This is not an executable experiment
protocol, harness grant, or RealLLM campaign grant.

**Date:** 2026-09-30

**Product decisions:** D003–D006, D009, D016, D037, D038; AGENTS.md scope gates

**Related evidence:**

- `docs/evaluations/v0_3/contextual/V9_11_CONTEXTUAL_VALIDATION_ACCEPTANCE_REPORT.md`
  (Agent 16/17 vs fixed pipeline 17/17; retained failure `675073735bc06f76`)
- `docs/evaluations/phase4_3_1/official/bench_official_s1_v12_planner8_1_gate5/`
  (V0.2 Agent 79/80 vs baseline 14/16; historical latency)
- `docs/evaluations/v0_2_external_wav/investigation_report_2026-09-02.md`
  (measurement-validity findings)
- Codex critique of Hybrid+S1 direction (operator paste 2026-09-30)
- Codex revise of this design package (operator paste 2026-09-30): baseline and
  HEAD finish gates are not yet matched; D037 entry must be measured; equal
  completion must not block a fixed-pipeline dominance conclusion

**Open question:** OQ-019 (resolved — study shape approved; see D038)

**Plan:** `docs/superpowers/plans/2026-09-30-s1-planner-ablation-utility-study.md`
(Wave 0 draft; Wave 1+ gated)

## 1. Decision summary

Authorize a **study-shape freeze** for a bounded evaluation question: whether
product `RealLLMPlanner` earns its complexity on the HEAD default path relative
to a truth-free deterministic baseline under matched DSP, rule profiles,
stimulus context, claim gates, application entry, and deterministic report
processing.

This freeze does **not**:

- freeze an executable experiment protocol (case list, numeric bands, seals);
- assert that `ContextualFixedPipelineBaseline` already matches HEAD gates;
- replace `RealLLMPlanner` as the product planner;
- soften single_signal harmonic finish gates;
- rewrite sealed V0.2 or V0.3 campaign bytes;
- authorize writing-plans, harness, or RealLLM campaign execution;
- adopt LangGraph, vector retrieval, or a second diagnosis domain.

Staging (Option D, refinement of Option A): freeze matching conditions and a
decidable protocol in the later plan, complete model-free design review, then
decide whether to buy RealLLM data. Do not pay for a difference that cannot be
attributed.

## 2. Problem

v9.11 contextual validation showed that declared reference/stimulus context
improves harmonic attribution versus no-context ablation. The same report shows
the truth-free fixed pipeline matching or beating the contextual Agent on
outcome and causal exact-set accuracy (17/17 vs 16/17). The Agent's retained
failure attached an unsupported harmonic claim to supported clipping, exhausted
retries, and produced no diagnosis. The runtime protected claim validity. The
user lost a useful clipping result.

That pattern makes "the Agent must justify its complexity" an open engineering
question. It is separate from "is LangGraph missing?" and separate from market
fit. D037 guidance reduces the cost of supplying context. It does not prove that
LLM planning is the best way to deliver S1 once context exists.

## 3. Approaches considered

| Option | Idea | Verdict |
|--------|------|---------|
| **A + D** | Fresh development study: Agent vs truth-free fixed pipeline under matched conditions; freeze study shape now; freeze executable protocol and matching proofs in a later plan before any scored run; include single_signal utility measures | **Chosen** |
| B | Re-interpret sealed v9.11 / V0.2 official numbers as planner ablation | Rejected as the scored experiment. Read-only reuse of sealed reports remains valid preparation |
| C | Replace product planner with fixed pipeline now | Rejected: no fresh matched study; violates AGENTS authorization gate |

## 4. Study identity (normative names)

Proposed study id (implementation may refine spelling once contracted):

```text
study_s1_planner_ablation_dev_1
```

Proposed evidence root (additive; do not mutate sealed trees):

```text
docs/evaluations/v0_3/planner_ablation/
```

Scored arms (exact set):

1. `product_agent`. HEAD product path (`RealLLMPlanner`, current prompt and
   causal policy identity recorded in the freeze record).
2. `fixed_pipeline`. Truth-free deterministic baseline. Historical
   `ContextualFixedPipelineBaseline`
   (`src/signal_diag/evaluation/contextual/baseline.py`) and the contextual
   harness are **reuse candidates**, not proof that the arms already share HEAD
   mode-specific claim gates, the D037 application boundary, or equivalent
   deterministic report processing.

Harness-only arm (optional later; never scored against `product_agent`):

3. `scripted_agent` dry-run for harness acceptance only.

Modes under test (first freeze default):

- `single_signal` on the D037 default contextual entry path;
- `paired_reference` as the required contextual upgrade arm.

`nominal_single_tone` may be added later by a revised study-shape decision. It
is not a silent substitute for the paired arm under the defaults in §10.

## 4.1 Matching prerequisites (before attributable planner conclusions)

A later plan must establish, mode by mode:

1. Claim-gate equivalence for clipping and harmonic finishes between
   `product_agent` and `fixed_pipeline`, including OQ-014 Option C
   (`flat_top_detected` branch on `single_signal`) and contextual test-family
   clipping on paired/nominal modes
   (`CONTRACTS_V0_3_CONTEXTUAL.md` §16).
2. Measurement of `single_signal` through the D037 contextual submission path
   that can emit `context_guidance`, not legacy `submit_wav` /
   `POST /api/v1/runs/wav` alone
   (`CONTRACTS_V0_3_CONTEXTUAL.md` §17;
   current campaign adapter still uses legacy `submit_wav` for
   `single_signal` in `app/contextual_campaign.py`).
3. Equivalent deterministic report processing across arms. Existing
   `context_guidance` is template-generated in `app/context_guidance.py` and is
   not an LLM contribution. Guidance presence must not be scored as planner
   skill.
4. Independent study protocol and scoring identity. Do not reuse sealed v9.11
   seal, 20/60 slot plan, or fixed 17/6 denominators as this study's identity.
5. Dependency direction preserved: evaluation must not import app composition
   as a product dependency inversion. A study adapter is allowed only if it
   keeps product diagnosis behavior unchanged.

If matching fails and the plan still compares unmatched systems, report the
result as a system-effect comparison. Do not attribute the full delta to LLM
planning.

Any required baseline or harness behavior change needs its own additive design
and authorization. Preserve historical baseline and campaign identities.

## 5. Preregistration requirements

Before any scored execution, approve and seal under
`docs/evaluations/v0_3/planner_ablation/` (new tree; do not mutate
`study_v0_3_contextual_validation_1` or other sealed studies):

1. Paired case and mode populations (same test WAV across both planner arms and
   across `single_signal` and the selected upgrade mode). Treat related samples
   from one source as dependent evidence.
2. Arm order, repetition count for the LLM arm, stop/retry rules, and a ban on
   post-hoc extra runs after seeing results.
3. Primary metrics, non-inferiority bounds, material-improvement thresholds,
   sample-size rationale, and uncertainty handling.
4. Explicit populations and zero-denominator rules for every metric, including
   claim-level metrics. Diagnosis-less terminals remain in completion, outcome,
   and recall-style denominators when the preregistration says so (v9.11
   lesson).
5. Code identity digests (implementation SHA, product tree, prompt SHA, harness
   SHA as applicable).
6. Resource limits and identical timing boundaries for both arms. Token or model
   bill metrics must not be labeled as total ownership cost unless the protocol
   measures that cost.

New results are additive. Historical bundles stay immutable.

## 5.1 Integration sketch (later grants only)

A later bounded grant may define additive CONTRACTS / TEST_PLAN IDs and then
implement harness plus Scripted dry-run against those definitions. Definitions
precede implementation inside that grant. Reuse of
`evaluation/contextual/` modules is allowed only under §4.1 matching rules and
a new study id / seal.

This design PR adds no harness code and no contract IDs.

## 6. Metrics (minimum set)

Correctness and safety:

- outcome accuracy (with explicit population);
- causal exact-set accuracy;
- unsupported positive claim rate;
- evidence grounding;
- diagnosis completion rate over all scheduled slots (include diagnosis-less
  terminals as non-completion when applicable);
- mode-stratified miss analysis, including "supported clipping Evidence present
  but no delivered clipping diagnosis".

Cost and experience:

- wall-clock latency per case under a shared timing boundary;
- estimated model cost or token count for `product_agent` only;
- tool-action count;
- failure-path time and retry cost.

Default-path utility (`single_signal` focus):

- rate of `inconclusive` with `context_guidance` present when the emission
  rules in §17 apply (report presence as deterministic product behavior, not
  planner skill);
- rate at which guidance names protocol-required next inputs
  (`reference_wav`, `nominal_fundamental_hz`, or both);
- upgrade success on a **pre-fixed** upgrade sample population, not only on the
  subset that happened to emit guidance;
- conditional upgrade success among cases that receive valid, sufficient
  in-protocol upgrade context, reported with the full-population denominator
  alongside the conditional one.

Offline score labels must separate, without leaking to execution arms:

| Label | Meaning |
|-------|---------|
| context obtainable in protocol | study can supply the next input |
| context valid | supplied input is usable for the mode |
| context sufficient to decide | supplied input is enough for a supported conclusion under the oracle |

Scoring treatment for utility versus correctness:

| Situation | Correctness | Utility |
|-----------|-------------|---------|
| No sufficient evidence; correct `inconclusive` | correct completed diagnosis | problem unresolved |
| Context supplied but invalid or still insufficient; correct `inconclusive` | not a planner correctness defect | unresolved, tracked separately |
| Sufficient supported clipping Evidence, yet no diagnosis | failure | useful result lost |
| Valid sufficient upgrade context present, still no supported conclusion | wrong per preregistered oracle | upgrade failure |

Naming an input field in guidance proves only that the template lists a
requirement. It does not prove a real user can obtain that input. Protocol
obtainability is an engineering label. Real-world obtainability needs separate
user evidence.

"Useful" terminals must be defined in the preregistration with examples.

## 7. Falsification and decision language

Record these as study conclusions, not automatic product changes.

For "LLM planning earns its keep on matched inputs", prefer one of three
recorded conclusions after the frozen band:

1. **Planner advantage.** `product_agent` is better on the primary quality or
   utility metric beyond the preregistered margin, with safety constraints held.
2. **Fixed-pipeline dominance within bounds.** On the preregistered band,
   `fixed_pipeline` is non-inferior on quality, safety, usefulness, and
   completion, and shows a material improvement on at least one preregistered
   cost or experience metric, with no unacceptable regression on the other
   constrained metrics. Equal 100% completion does not block this conclusion.
3. **Insufficient evidence.** Failure to demonstrate a difference is not
   evidence of equivalence. Failure to falsify planning value is not a reason
   to keep the planner.

Other claims under test:

| Claim under test | How the study may speak |
|------------------|-------------------------|
| S1 remains the right product focus | Out of band here; needs separate user evidence |
| Current DSP/rules remain adequate | Representative inputs repeatedly defeat measurement validity under frozen association/F0/THD contracts |
| Current orchestration/retrieval remain adequate | Failures specifically require persistence/resumption or semantic retrieval (not hypothesized in this study's first freeze) |

## 8. Authorization layers

| Layer | This design package | Needs later grant |
|-------|---------------------|-------------------|
| Study-shape design + OQ-019 / D038 | Approved 2026-09-30 | Shape frozen; later grants still required |
| writing-plans (docs only) | Plan revised after Codex Wave 0 review 2026-09-30 | Operator accept before Wave 1 definitions |
| Additive CONTRACTS / TEST_PLAN definitions | No | Bounded grant; definitions before code |
| Harness + Scripted dry-run | No | Same bounded grant after definitions, or a follow-on grant |
| Execution-protocol seal and identity check | No | Before any scored run |
| RealLLM `product_agent` campaign | No | Explicit RealLLM / campaign authorization |
| Result review | No | After campaign artifacts exist |
| Product planner replacement or gate softening | No | New behavior design + contracts + tests + explicit authorization |

Recommended next grant after shape approval: **writing-plans only**.

Reversal words in §10 request a scope-change review. They do not bypass
contracts, tests, or execution authorization. Changing frozen modes or the
research question requires a revised design review.

## 9. Non-goals

- LangGraph, vector DB, Docker, auth, public deploy.
- Softening D037 single_signal harmonic gates or autofilling nominal Hz from F0.
- Replacing sealed Demo or official **79/80** narrative with HEAD numbers.
- Treating sealed v9.11 / V0.2 official slots as this study's scored population.
- User interviews as a substitute for the engineering matching question (may
  run in parallel; not in this study's critical path).

## 10. Defaults applied under design-only grant

These defaults stand unless the operator requests a scope change with the named
word and a revised design review accepts that change:

| Default | Reverse word |
|---------|--------------|
| Study stays evaluation-only; product planner unchanged | `替换产品 planner` |
| Fresh development cases; do not re-score sealed v9.11/V0.2 official slots as this study | `复用密封包` |
| RealLLM campaign not started by this PR | `批准 RealLLM 战役` |
| First freeze requires `paired_reference` plus `single_signal` utility metrics | `只要 single_signal` |

## 11. Verification of this design package

- Codex revise findings on gate mismatch, D037 entry, falsification logic,
  inconclusive treatment, and authorization staging were checked against
  `baseline.py`, `CONTRACTS_V0_3_CONTEXTUAL.md` §16–§17, and
  `app/contextual_campaign.py`, then folded into §§1, 4–8.
- No product code or live-model runs in the design PR.
- Operator approved revised OQ-019 / D038 on 2026-09-30 (study shape only).
  Executable protocol freeze waits for a writing-plans grant, the plan, and a
  later seal.
