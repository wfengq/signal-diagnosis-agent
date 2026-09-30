# S1 default-path utility and planner-ablation study

**Status:** design draft (operator authorized design-only 2026-09-30; not an
implementation or RealLLM campaign grant)

**Date:** 2026-09-30

**Product decisions:** D003–D006, D009, D016, D037; AGENTS.md scope gates

**Related evidence:**

- `docs/evaluations/v0_3/contextual/V9_11_CONTEXTUAL_VALIDATION_ACCEPTANCE_REPORT.md`
  (Agent 16/17 vs fixed pipeline 17/17; retained failure `675073735bc06f76`)
- `docs/evaluations/phase4_3_1/official/bench_official_s1_v12_planner8_1_gate5/`
  (V0.2 Agent 79/80 vs baseline 14/16; historical latency)
- `docs/evaluations/v0_2_external_wav/investigation_report_2026-09-02.md`
  (measurement-validity findings)
- Codex critique of Hybrid+S1 direction (operator paste 2026-09-30): LLM
  planning value vs deterministic diagnosis remains open; market fit is not the
  only uncertainty

**Open question:** OQ-019

**Plan:** not written until this design is approved and a separate
implementation authorization is issued

## 1. Decision summary

Authorize a **bounded evaluation design** that asks whether product
`RealLLMPlanner` earns its complexity on the HEAD default path relative to a
truth-free deterministic baseline that shares the same DSP, rule profiles,
stimulus context, and causal claim gates.

This design does **not**:

- replace `RealLLMPlanner` as the product planner;
- soften single_signal harmonic finish gates;
- rewrite sealed V0.2 or V0.3 campaign bytes;
- authorize RealLLM campaign execution (that needs a later explicit grant);
- adopt LangGraph, vector retrieval, or a second diagnosis domain.

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
| **A** | Fresh development study: Agent vs truth-free fixed pipeline under matched DSP/rules/context/gates; freeze success criteria before any run; include single_signal utility and guidance follow-through measures | **Chosen** |
| B | Re-interpret sealed v9.11 / V0.2 official numbers as planner ablation | Rejected: different case sets, different questions, risk of post-hoc story |
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

Arms (exact set):

1. `product_agent`. HEAD product path (`RealLLMPlanner`, current prompt and
   causal policy identity recorded in the freeze record).
2. `fixed_pipeline`. Truth-free deterministic baseline per
   `CONTRACTS_V0_3_CONTEXTUAL.md` §11.1
   (`ContextualFixedPipelineBaseline` in
   `src/signal_diag/evaluation/contextual/baseline.py`). Same Tools, DSP, rule
   profiles, stimulus context, and finish-claim gates as the Agent arm. No LLM
   planning.
3. Optional later arm (not required for first freeze): `scripted_agent` dry-run
   for harness acceptance only. Never substitutes for `product_agent` in the
   scored comparison.

Modes under test (minimum):

- `single_signal` default path (D037);
- at least one contextual upgrade path (`paired_reference`,
   `nominal_single_tone`, or both) so the study can separate context value from
   planner value.

## 5. Preregistration requirements

Before any scored execution:

1. Freeze case list, arm order, scorer populations, and pass/fail bands in a
   preregistration record under `docs/evaluations/v0_3/planner_ablation/`
   (new tree; do not mutate sealed studies such as
   `study_v0_3_contextual_validation_1`).
2. Freeze code identity digests the same way other contextual studies do
   (implementation SHA, product tree, and prompt SHA as applicable).
3. State whether each metric includes failed or diagnosis-less runs in its
   denominator. Explicit populations are mandatory (v9.11 scorer lesson).
4. Prohibit rewriting historical bundles. New results are additive.

## 5.1 Integration sketch (harness PR only)

A later implementation authorization may reuse
`evaluation/contextual/` (`campaign.py`, `runner.py`, `scoring.py`,
`sealing.py`) with a new study id and seal. Product packages under `agent/` and
`app/` stay unchanged for the scored comparison except the existing product path
used by the `product_agent` arm. This design PR does not add harness code.

## 6. Metrics (minimum set)

Correctness and safety:

- outcome accuracy (with explicit population);
- causal exact-set accuracy;
- unsupported positive claim rate;
- evidence grounding;
- diagnosis completion rate (include diagnosis-less terminals as non-completion).

Cost and experience:

- wall-clock latency per case;
- estimated model cost or token count for `product_agent` only;
- tool-action count.

Default-path utility (single_signal focus):

- rate of `inconclusive` with `context_guidance` present when harmonic
  attribution is blocked;
- rate at which guidance names an obtainable next input
  (`reference_wav`, `nominal_fundamental_hz`, or both);
- conditional rate: among cases where upgrade context is supplied in-protocol,
  rate of reaching a useful terminal (`supported_fault` clipping,
  `supported_fault` harmonic under upgraded mode, or justified
  `no_supported_fault`).

"Useful" must be defined in the preregistration with examples. Correct
`inconclusive` without obtainable context remains allowed and is not scored as
a planner defect.

## 7. Falsification criteria

Record these as study conclusions, not automatic product changes:

| Claim under test | Falsified when |
|------------------|----------------|
| LLM planning earns its keep on matched inputs | Fixed pipeline matches diagnosis quality and usefulness while improving completion, latency, and cost across the frozen band |
| S1 remains the right product focus | Intended users rarely have the problem, cannot supply needed context, or cannot act on results (needs separate user evidence; out of band for this engineering study) |
| Current DSP/rules remain adequate | Representative inputs repeatedly defeat measurement validity under frozen association/F0/THD contracts |
| Current orchestration/retrieval remain adequate | Failures specifically require persistence/resumption or semantic retrieval (not hypothesized in this study's first freeze) |

## 8. Authorization layers

| Layer | This design | Needs later grant |
|-------|-------------|-------------------|
| Written design + OQ-019 | Yes (this document) | n/a |
| Additive CONTRACTS / TEST_PLAN IDs for harness | No | Design approval + implementation authorization |
| Harness code + Scripted dry-run tests | No | Implementation authorization |
| RealLLM `product_agent` campaign | No | Explicit RealLLM / campaign authorization |
| Product planner replacement or gate softening | No | New behavior design + contracts + tests + explicit authorization |

## 9. Non-goals

- LangGraph, vector DB, Docker, auth, public deploy.
- Softening D037 single_signal harmonic gates or autofilling nominal Hz from F0.
- Replacing sealed Demo or official **79/80** narrative with HEAD numbers.
- User interviews (may be recommended after engineering results; not in scope).

## 10. Defaults applied under design-only grant

These defaults stand unless the operator reverses them with the named word:

| Default | Reverse word |
|---------|--------------|
| Study stays evaluation-only; product planner unchanged | `替换产品 planner` |
| Fresh development cases; do not re-score sealed v9.11/V0.2 official slots as this study | `复用密封包` |
| RealLLM campaign not started by this PR | `批准 RealLLM 战役` |
| First freeze requires paired context arm plus single_signal utility metrics | `只要 single_signal` |

## 11. Verification of this design package

- Spec self-review: no TBD placeholders for normative names above; scope gates
  mirrored from AGENTS.md.
- No product code or live-model runs in the design PR.
- Operator reviews this file before any writing-plans / harness work.
