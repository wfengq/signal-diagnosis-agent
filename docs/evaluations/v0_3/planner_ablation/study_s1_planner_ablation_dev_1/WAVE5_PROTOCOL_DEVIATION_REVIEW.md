# Wave 5 Protocol-Deviation Review

**Study:** `study_s1_planner_ablation_dev_1`

**Campaign evidence:** `agent_realllm_campaign_1/` at commit `1e1ac5e`

**Machine `StudyConclusion` (frozen scorer):** `fixed_pipeline_dominance`

**Formal review verdict:** **not accepted as protocol-conformant dominance.**

This report keeps the machine output and records why the dominance enum must
not be treated as an accepted study conclusion under the sealed protocol.
It does not re-run RealLLM, rebuild `protocol_seal/`, replace campaign
artifacts, soften product gates, or change the product planner.

## Scope and authorization

Codex Wave 4 revise (operator paste under poteto-mode) authorizes only this
protocol-deviation review report.

Out of scope for this grant:

- RealLLM re-run or campaign retry
- seal regeneration or mutation of `agent_realllm_campaign_1/`
- product planner / prompt / gate changes
- post-hoc oracle label edits that would raise the formal score

## Frozen identities (unchanged)

| Item | Value |
|------|-------|
| `study_id` | `study_s1_planner_ablation_dev_1` |
| `scoring_identity` | `signal_diag.planner_ablation_scoring` |
| `population_identity` | `c69db6c69d3dd285c2bd572e6013625f7eb2ae761d736a38a55008fdee13f8b6` |
| Schedule keys | 20 |
| Scorable slots | 40 (20 schedule × 2 arms) |
| Arm order | all `product_agent`, then all `fixed_pipeline` |
| Product provenance | every product slot `RealLLMPlanner` / `product_campaign` |
| Scripted fallback | false |

Seal, WAV digests, population / oracle / input / code hashes were rechecked
against on-disk `protocol_seal/` and campaign inputs. They match.

## Machine aggregates (retained)

Both arms, recomputed from slot artifacts with the sealed scorer rules:

| Metric | `single_signal` | `paired_reference` | Combined |
|--------|----------------:|-------------------:|---------:|
| primary quality | 7/10 | 10/10 | 17/20 (0.85) |
| usefulness | 6/10 | 9/10 | 15/20 (0.75) |
| completion | 10/10 | 10/10 | 20/20 (1.0) |

Safety on this claim population (both arms):

- claim evidence grounding: 22/22
- unsupported positive claims: 0/12
- machine `product_safety_ok` / `fixed_safety_ok`: true

Safety remains limited to this completed-diagnosis claim population. Zero
positive claims on other strata would not prove safety.

Recorded machine latency means (not accepted as shared-boundary evidence):

| Arm | Mean wall clock (s) |
|-----|--------------------:|
| `product_agent` | 4.803966 |
| `fixed_pipeline` | 0.008913 |
| recorded relative fixed improvement | 0.998145 |

Tool-action counts on every slot: **2** for product (`tool_history`) and **2**
distinct `source_tool` values for fixed. Equal tool counts do not repair the
timing-boundary defect below.

## P1. Timing boundary mismatch (blocks formal dominance)

### Protocol requirement

`preregistration.md` §5 requires a shared wall-clock timing boundary per slot
for both arms. Material latency improvement (`material_improvement_ratio =
0.20`) is only meaningful under that shared boundary.

### What the campaign runner measured

**Product arm** (`run_planner_ablation_realllm_campaign.py`): timer starts at
`execute_product_slot`, which includes application submit, WAV ingest inside
the service, planner execution, and wait-for-terminal.

**Fixed arm** (same script): WAV decode, repository put, and baseline
construction run **before** `perf_counter()`. Guidance derivation runs
**after** the timed `baseline.run` returns.

### Consequence

The published ~99.8% latency improvement is not a same-boundary comparison.
The sealed scorer still set `matched_comparison=True` because that flag today
tracks schedule/oracle matching, not timing-boundary integrity.

Therefore:

1. Keep the machine enum `fixed_pipeline_dominance` as a **recomputable
   artifact**.
2. **Do not accept** it as a protocol-conformant dominance conclusion.
3. Quality, usefulness, completion, and safety arithmetic remain usable.
4. Latency must be treated as **protocol-deviant / non-decisive** for this
   run.
5. A future shared-boundary experiment needs a **separate authorization**.
   Existing records cannot reconstruct the missing pre-timer fixed work.

## P1. Single-signal oracle defects (keep formal 17/20)

Mode-stratified misses are **identical** on both arms. They are not
planner-specific failures.

| case_id | role | frozen single oracle | observed (both arms) | Notes |
|---------|------|----------------------|----------------------|-------|
| `393940e92c58cf0b` | natural_even_control | `no_supported_fault` | `inconclusive` | fixed single THD ≈ 12.63% vs demo 5% gate |
| `04f4068ec91d2621` | natural_even_control | `no_supported_fault` | `inconclusive` | fixed single THD ≈ 8.47% vs demo 5% gate |
| `163185980dc8f7a4` | invalid_comparison | `inconclusive` | `no_supported_fault` | test WAV SHA-256 identical to clean case `825a759a0ea47bb7` |

### Clean vs invalid_comparison collision

Sealed `case_sources` show the same test WAV digest for:

- `825a759a0ea47bb7` (clean → single oracle `no_supported_fault`)
- `163185980dc8f7a4` (invalid_comparison → single oracle `inconclusive`)

In `single_signal` mode no reference is supplied. The invalid-reference story
cannot affect the single-mode observation. Expecting opposite single oracles
on identical test bytes is an oracle construction defect.

### Natural-even controls vs single-file gate

Both natural controls exceed the demo single-file THD threshold under
`profile_s1_distortion` 1.0.0-demo. Conservative `inconclusive` without a
reference matches the existing gate. The frozen single labels demand
`no_supported_fault`. That mismatch is label/gate conflict, not evidence that
the planner underperformed the fixed baseline.

### Formal score handling

- Retain formal combined quality **17/20** on both arms.
- Do **not** relabel oracles after seeing results.
- Do **not** inflate the formal score.
- Do **not** soften product gates to chase labels.
- Treat the three single misses as **oracle / population defects** in this
  review annex, not as planner ablation signal.

Paired mode remains 10/10 quality on both arms under the frozen paired
oracles.

## Mode-stratified usefulness and default-path utility

| Arm | Mode | Usefulness |
|-----|------|-----------:|
| product / fixed | `single_signal` | 6/10 (0.60) |
| product / fixed | `paired_reference` | 9/10 (0.90) |
| product / fixed | combined | 15/20 (0.75) |

Product `single_signal` slots with `outcome=inconclusive`: **4/4** emitted
`context_guidance`, all with reason code
`harmonic_attribution_requires_context`. Guidance presence is deterministic
product behavior under D037, not planner skill.

## Upgrade success (T-CX285 style denominators)

Upgrade-relevant cases are those whose frozen single oracle differs from the
paired oracle:

`a4a0853be9983f8c`, `2be730b9113701de`, `6fb80bbda391c26c`, `aa9b4a91b0253c33`
(pre-fixed population **N = 4**).

On this run, no candidate already satisfied the paired oracle on the single
slot, so the conditional population is also **4**.

| Arm | Conditional successes | Full pre-fixed | Conditional |
|-----|----------------------:|---------------:|------------:|
| product | 4 | 4/4 = 1.0 | 4/4 = 1.0 |
| fixed | 4 | 4/4 = 1.0 | 4/4 = 1.0 |

Both arms unlock the paired oracle on every upgrade-relevant case. This is
matching evidence for the upgrade path. It does not repair the timing-boundary
defect that blocks formal dominance.

## P2 notes (non-blocking for this report)

### Seal script verify vs regenerate

`scripts/seal_planner_ablation_protocol.py` deletes and rebuilds
`protocol_seal/` when the destination exists, while `preregistration.md`
lists that command under “Regenerate or verify”. **Current seal left
untouched.** A later hygiene grant should make verify read-only and refuse
overwrite.

### Non-inferiority gap wording

Frozen `non_inferiority_max_gap = 0.025` with `n_unit: scorable_slots` and
per-arm denominator 20 means one-slot degradation is **0.05**, which exceeds
0.025. The gap does **not** tolerate a one-slot regression. This run had equal
quality/usefulness/completion on both arms, so the machine dominance path was
not altered by that wording error. Do not rewrite the frozen number in this
grant.

## Accepted vs not accepted

| Claim | Status |
|-------|--------|
| Slot integrity (40/40), RealLLM provenance, no Scripted fallback | Accepted |
| Seal / WAV / identity digests match | Accepted |
| Formal quality / usefulness / completion / safety arithmetic | Accepted as recomputation |
| Mode-stratified 7/10 + 10/10 quality | Accepted |
| Oracle defect analysis for three single misses | Accepted as review finding |
| Upgrade full and conditional 4/4 both arms | Accepted as descriptive metrics |
| Machine enum `fixed_pipeline_dominance` | Retained as artifact only |
| Protocol-conformant fixed-pipeline **dominance** | **Not accepted** |
| Product planner replacement or gate softening | **Unauthorized** |

## Stop

Wave 5 review report complete under the protocol-deviation grant.

Next work that needs a new explicit phrase:

- shared-boundary latency re-measurement experiment
- oracle / population redesign (new seal)
- read-only seal verify tooling
- any product planner change
