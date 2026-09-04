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

T-CX004–T-CX145 are allocated to later tasks per the implementation plan and must
not collide with V0.2 T001–T285 numbering. T-CX146–T-CX165 are additive for the
v9.6 contextual remediation and must not alter T-CX001–T-CX145 meanings.
