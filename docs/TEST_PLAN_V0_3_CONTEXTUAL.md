# TEST_PLAN_V0_3_CONTEXTUAL.md

**Status:** additive V0.3 contextual test registry

**Does not replace:** `docs/TEST_PLAN_V0_2.md` (T001–T285)

**Contracts:** `docs/CONTRACTS_V0_3_CONTEXTUAL.md`

## ID allocation

| Range | Focus |
|-------|-------|
| T-CX001..010 | preservation and context contracts |
| T-CX011..030 | deterministic contextual DSP |
| T-CX031..045 | Tool outputs and Evidence |
| T-CX046..055 | contextual rules |
| T-CX056..075 | runtime causal policy |
| T-CX076..085 | v9.5 prompt and composition |
| T-CX086..105 | application service/store/report |
| T-CX106..120 | API/CLI/Web UI |
| T-CX121..140 | evaluation, scoring, calibration, sealing |
| T-CX141..145 | cumulative, packaging, and preservation gates |
| T-CX146..148 | v9.6 preservation and version compatibility |
| T-CX149..154 | v9.6 mode-aware Tool routing |
| T-CX155..162 | v9.6 prompt and composition |
| T-CX163..165 | v9.6 recorded-failure regressions |
| T-CX166..185 | v9.7 deterministic rule closure |
| T-CX186..190 | v9.8 claim-reference recovery |
| T-CX191..196 | v9.9 paired-reference recovery |

## Registered identities (Task 1)

| ID | Title |
|----|-------|
| T-CX001 | Frozen v8.1/v9.4 prompt bytes, S1 profile, Demo README, official manifest SHA-256 |
| T-CX002 | Protected preservation fixture paths exist |
| T-CX003 | Git tag `v0.2.0` object ID unchanged |

## Registered identities (v9.6 remediation)

| ID | Title |
|----|-------|
| T-CX146 | Frozen v9.5 prompt SHA-256 remains unchanged |
| T-CX147 | Task 13 control artifacts SHA-256 remain unchanged |
| T-CX148 | T-CX146–T-CX165 are registered in this plan |
| T-CX149 | v9.6 rejects plain harmonic Tool in paired mode |
| T-CX150 | v9.6 rejects plain harmonic Tool in nominal mode |
| T-CX151 | v9.6 allows contextual Tool in paired mode |
| T-CX152 | v9.6 allows plain harmonic Tool in single_signal |
| T-CX153 | Rejected route consumes planner retry, not Tool budget |
| T-CX154 | v9.5 routing behavior unchanged under v9_5_contextual |
| T-CX155 | Product prompt version is `v0.3-s1-planner-9.6` |
| T-CX156 | v9.5 prompt SHA remains frozen after v9.6 addition |
| T-CX157 | Contextual modes require contextual Tool wording |
| T-CX158 | no_supported_fault names exact clipping_mechanism=false Evidence |
| T-CX159 | Natural-even no-growth closes as no_supported_fault |
| T-CX160 | Nominal mismatch requires inconclusive |
| T-CX161 | Combined requires two independent gates |
| T-CX162 | Composition wires v9.6 without ScriptedPlanner fallback or thresholds |
| T-CX163 | no-fault citation replay rejects clipping_detected substitute |
| T-CX164 | Combined routing and causal closure replay |
| T-CX165 | Natural-even and clipping preservation replay |

## Registered identities (v9.7 deterministic rule closure)

| ID | Title |
|----|-------|
| T-CX166 | v9.6 prompt SHA and preserved v9.6 run artifacts remain unchanged; T-CX166–T-CX185 registered once |
| T-CX167 | Causal-policy literal compatibility and v9.7 inheritance are exact |
| T-CX168 | Clipping maps to the distortion profile in every mode |
| T-CX169 | Paired contextual analysis maps to the contextual profile |
| T-CX170 | Nominal contextual analysis maps to the contextual profile |
| T-CX171 | Single-signal harmonic analysis maps to the distortion profile |
| T-CX172 | Spectrum, fundamental, and errored Tools create no closure |
| T-CX173 | Invalid relevant Tool Evidence creates `not_applicable` rules |
| T-CX174 | Closure uses the exact complete same-observation Evidence suffix |
| T-CX175 | Automatic closure increments and respects the existing rule bound |
| T-CX176 | Empty Evidence and dependency failures terminate fail-closed |
| T-CX177 | v9.7 rejects manual rule decisions without consuming rule budget |
| T-CX178 | v9.4, v9.5, and v9.6 manual-rule behavior remains unchanged |
| T-CX179 | Tool trace emits Observation then RuleEvaluation with one cause |
| T-CX180 | Historical and v9.7 traces both round-trip and preserve deltas |
| T-CX181 | v9.7 prompt removes positive manual-rule instructions and examples |
| T-CX182 | v9.7 prompt retains mode, finish, and no-fallback semantics |
| T-CX183 | Composition selects v9.7 prompt and policy without thresholds |
| T-CX184 | Deterministic replay covers clean, natural-even, harmonic, combined, and clipping fixtures |
| T-CX185 | Cumulative architecture, preservation, packaging, and registry gate |

## Registered identities (v9.8 claim-reference recovery)

| ID | Title |
|----|-------|
| T-CX186 | v9.7 prompt SHA remains frozen; T-CX186–T-CX190 registered once |
| T-CX187 | Nominal harmonic finish requires all five citations together under v9.8 |
| T-CX188 | Finish rejection lists all deficits with same-run evidence_id/ruleval IDs |
| T-CX189 | v9.8 prompt freezes recovery wording; v9.7 bytes unchanged |
| T-CX190 | Composition wires v9.8 and inherits v9.7 routing/closure/manual-rule rejection |

## Registered identities (v9.9 paired-reference recovery)

| ID | Title |
|----|-------|
| T-CX191 | v9.8 prompt SHA and recorded campaign artifacts remain unchanged; T-CX191–T-CX196 registered once |
| T-CX192 | Paired harmonic finish retains all five existing causal rule requirements |
| T-CX193 | Paired finish rejection lists every deficit with accurate same-run evaluation IDs |
| T-CX194 | Combined finish keeps clipping and paired harmonic requirements independent |
| T-CX195 | v9.9 prompt separates paired recovery from nominal recovery and freezes v9.8 bytes |
| T-CX196 | Composition wires v9.9 while inheriting v9.8 routing, closure, and manual-rule rejection |

T-CX004–T-CX145 are allocated to later tasks per the implementation plan and must
not collide with V0.2 T001–T285 numbering. T-CX146–T-CX165 are additive for the
v9.6 contextual remediation and must not alter T-CX001–T-CX145 meanings.
T-CX166–T-CX185 are additive for the v9.7 deterministic rule-closure remediation
and must not alter T-CX001–T-CX165 meanings.
T-CX186–T-CX190 are additive for the v9.8 claim-reference recovery remediation
and must not alter T-CX001–T-CX185 meanings.
T-CX191–T-CX196 are additive for the v9.9 paired-reference recovery remediation
and must not alter T-CX001–T-CX190 meanings.
