# V0.3 Validation Construction & Gate Checklist

> Historical only. This checklist was never executed and is superseded by the
> distinct contextual validation protocol under `docs/evaluations/v0_3/contextual/validation/`.

Use with protocol `1.2.0-prereg`, `ev_c036_acceptance_targets.json`, and `val_slot_plan.json`.

## A. Protocol freeze re-review (this phase)

- [x] Accept n=20 / scoreable=17 / unscored=3
- [x] Accept role counts (clean 3 / clip 3 / harm 3 / comb 2 / inconclusive-family 9)
- [x] Accept fixed confidence mix (strong 8 / reference 9 / weak 2 / unknown 1)
- [x] Accept fixed scoreable inconclusive denominator = 6; both natural_even = reference_supported
- [x] Accept no silent confidence downgrade (amendment required)
- [x] Accept role hard gates (clean ≥2/3; clip/harm ≥2/3 exact; combined 2/2; natural_even 2/2 + 0 harmonic; inconclusive ≥5/6)
- [x] Accept strengthened isolation (parent_master / recording_key / session; crops same group; transform ≠ independence)
- [x] Accept source composition (≥10/20 public real; ≥4 real masters for 8 strong; ≤2 positives/master; ≥3 families in reference∪unscored)
- [x] Accept scoring boundaries (fixed dens; infra fail = incorrect; unsupported den=0 → not_evaluated blocks; empty required refs fail grounding; no edits between baseline and Agent)
- [x] Confirm `even_order_present` operational-only language
- [x] Confirm v9.9 frozen identity: code `15c047c…`, evidence `a451775…`, prompt SHA `27a9315a…`, manifest `cca0ee24…`
- [x] Confirm forbid-lists: 14 legacy V0.3 dev + 20 contextual V0.3 dev + V0.2 sealed final

**Stop here until re-review sign-off.** Do not download, open val/test WAV, run models, commit, or push.

## B. Later: catalog construction (requires separate authorization)

- [ ] Create `v03_val_*` catalog with license-clear sources
- [ ] Bind ≥10 public real recording cases
- [ ] Bind 8 strong positives to ≥4 independent real `parent_master_id` with ≤2 scoreable positives each
- [ ] Prove reference∪unscored covers ≥3 independent source/recording families
- [ ] Prove isolation: no shared parent_master_id, source_recording_key, or capture/session lineage with dev or V0.2 sealed final
- [ ] Reject same-recording crops as “new” masters
- [ ] Apply transforms only to new independent val masters
- [ ] Keep both natural_even as `reference_supported`; keep exactly 6 scoreable inconclusive
- [ ] If confidence adjudication fails: stop + amendment (no silent downgrade)
- [ ] Offline DSP spot-checks without planner; seal manifest + SHA

## C. Later: campaigns (requires separate authorization)

- [ ] Fixed-pipeline one-shot archived
- [ ] No product/data/label/identity changes before Agent
- [ ] Agent one-shot RealLLMPlanner v9.9 only (no ScriptedPlanner)
- [ ] Record code / prompt / manifest / model / timestamps
- [ ] Score with fixed denominators; infra failures count as incorrect on scoreable metrics
- [ ] If unsupported positive-claim denominator = 0 → `not_evaluated` (blocks meets_target)
- [ ] Evaluate all role hard gates
- [ ] If `meets_target`: stop and request final-test authorization
- [ ] If `below_target` / blocked: stop; no val-driven edits; no final test

## D. Final test gate (requires separate authorization)

- [ ] Validation `meets_target` including all role hard gates
- [ ] Explicit user authorization for final-test scope
