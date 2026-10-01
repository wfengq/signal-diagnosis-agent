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
| T-CX197..207 | truth-free deterministic contextual fixed pipeline and reseal |
| T-CX231..240 | v9.10 contextual clipping recovery |
| T-CX276..288 | D038 planner-ablation utility study (definitions; harness gated) |
| T-CX289..302 | D038 protocol revision / study_s1_planner_ablation_dev_2 (definitions; seal/RealLLM gated) |

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

## Registered identities (truth-free fixed pipeline remediation)

| ID | Title |
|----|-------|
| T-CX197 | Fixed-pipeline request schema excludes labels, confidence, role, and transform provenance |
| T-CX198 | Truth-free request and deterministic baseline are public contextual-harness APIs |
| T-CX199 | Fixed-pipeline execution rejects a manifest `ContextualCase` at its boundary |
| T-CX200 | Baseline implementation contains no truth/provenance field access |
| T-CX201 | Clean single-signal result derives from real Tool Evidence and frozen rules |
| T-CX202 | Clipping requires mechanism Evidence plus a substantial clipping-rule failure |
| T-CX203 | Paired harmonic diagnosis requires contextual growth-rule failure |
| T-CX204 | Invalid paired comparison remains grounded and inconclusive |
| T-CX205 | Nominal harmonic diagnosis retains its declared-single-tone limitation |
| T-CX206 | Replacement seal binds the repaired evaluation-harness SHA independently of product identity |
| T-CX207 | Historical and replacement seals verify with identical study inputs and zero executions |

## Registered identities (contextual validation campaign runner)

| ID | Title |
|----|-------|
| T-CX208 | Execution-input schema excludes truth, provenance, waveform, and FFT payload fields |
| T-CX209 | Nominal execution input requires a finite positive declared frequency |
| T-CX210 | Execution plan enforces unique cases and the frozen arm-major order |
| T-CX211 | Seal optionally binds truth-free execution inputs and detects drift |
| T-CX212 | Campaign executes every planned slot exactly once in arm-major order |
| T-CX213 | Behavioral failure continues while infrastructure failure stops immediately |
| T-CX214 | Existing campaign output is append-only and cannot be overwritten |
| T-CX215 | Historical validation seal v2 is refused for execution |
| T-CX216 | Real executor construction selects RealLLMPlanner without a provider call |
| T-CX217 | Product snapshots map to sanitized ArmResult artifacts without truth or WAV bytes |
| T-CX218 | Fixed pipeline uses only local WAV, declared stimulus context, DSP, and frozen rules |
| T-CX219 | Preflight refuses an existing output before any execution |
| T-CX220 | Truth is loaded after complete execution and every metric/role hard gate is applied |
| T-CX221 | CLI requires the exact written real-model authorization token |
| T-CX222 | T-CX208–T-CX230 are registered exactly once |
| T-CX223 | Active v3 preflight resolves case-keyed WAV checksums and yields exactly 20 cases / 60 slots |
| T-CX224 | Unexpected executor exceptions are sanitized, persisted as infrastructure failure, and stop execution |
| T-CX225 | Evaluation-harness identity covers the provider-facing campaign adapter |
| T-CX226 | Real executor refuses provider/model/base URL/planner/prompt/policy drift |
| T-CX227 | Preflight pins the authoritative active-seal path, status, and seal-index SHA |
| T-CX228 | Campaign startup copies the non-secret active seal identity into its append-only output |
| T-CX229 | Live campaign CLI exposes separate preflight-validation and run-validation commands |
| T-CX230 | Complete campaign finalization writes the required run summary |

## Registered identities (v9.10 contextual clipping recovery)

| ID | Title |
|----|-------|
| T-CX231 | Preserve v9.9 identities and recorded evidence; register T-CX231–T-CX240 once |
| T-CX232 | Contextual DSP propagates deterministic test clipping mechanism |
| T-CX233 | Contextual Tool emits one compact test clipping-mechanism Evidence item |
| T-CX234 | Additive v9.10 profile preserves the original profile and threshold semantics |
| T-CX235 | v9.10 automatic closure evaluates test-side clipping rules from one Evidence suffix |
| T-CX236 | v9.10 clipping claims require one coherent evidence family |
| T-CX237 | v9.10 contextual no-fault accepts only a complete contextual clean family |
| T-CX238 | Single-signal unsupported harmonic sibling yields clipping-subset recovery guidance |
| T-CX239 | Product freezes and wires v9.10 prompt, policy, and additive profile identity |
| T-CX240 | Two-failure replay and cumulative offline acceptance gate |
| T-CX241 | v9.10 development freeze resolves only through an append-only behavior-bearing identity amendment with matching deterministic recomputation evidence. |
| T-CX242 | v9.9 validation seal v3 is historical and accurately records 47 original slots plus 13 diagnostic-only continuation slots with no active seal. |
| T-CX243 | Contextual validation preflight rejects historical seal v3 before execution and creates no output. |
| T-CX244 | Lifecycle test IDs T-CX241 through T-CX244 are registered exactly once. |
| T-CX245 | Provider failure fingerprints retain only coarse non-sensitive diagnostics. |
| T-CX246 | Ordinary internal failures are not mislabeled as provider failures. |
| T-CX247 | The real contextual executor persists a safe failure fingerprint without secrets or payloads. |
| T-CX248 | The append-only observability identity amendment matches the current evaluation harness. |
| T-CX249 | A later append-only identity amendment preserves T-CX248 and bridges the post-assemble compatibility fix to the current harness. |
| T-CX250 | Preserve v9.10 prompt, policy, and retained development evidence while registering T-CX250–T-CX255 once. |
| T-CX251 | v9.11 single-signal no-fault accepts only the complete legacy clipping clean family. |
| T-CX252 | v9.11 paired and nominal no-fault retain the complete contextual test clean family and mode gates. |
| T-CX253 | v9.11 no-fault rejection reports every missing requirement with available same-run IDs in one error. |
| T-CX254 | Product freezes and wires v9.11 prompt and policy without changing profiles or thresholds. |
| T-CX255 | Deterministic replay covers the three retained v9.10 no-fault failure shapes without model or WAV access. |
| T-CX256 | Evidence grounding and unsupported positive-claim rate use their preregistered dynamic claim populations. |
| T-CX257 | A behavioral failure without a completed diagnosis contributes no claim to either dynamic population. |
| T-CX258 | Campaign result projection counts claims and resolves their Evidence and rule references within the same run. |
| T-CX259 | A zero predicted-positive denominator is not evaluated and blocks the unsupported-claim gate. |
| T-CX260 | Immutable campaign result payloads deterministically reconstruct claim populations and the corrected verdict. |
| T-CX261 | Arm-result claim population counters reject impossible and failed-result states. |
| T-CX262 | Append-only identity amendment binds the deterministic reconstruction implementation without changing campaign evidence. |
| T-CX263 | OQ-014 Option C: single_signal supported_fault clipping via flat_top_detected plus substantial legacy clipping-rule FAIL without clipping_mechanism=true. |
| T-CX264 | single_signal inconclusive with harmonic Evidence emits harmonic_attribution_requires_context guidance; wording forbids soft diagnosis. |
| T-CX265 | context_guidance is absent for supported_fault, no_supported_fault, and non-single_signal modes. |
| T-CX266 | contextual submit accepts mode=single_signal (test WAV only) and rejects reference/nominal fields. |
| T-CX267 | completed single_signal inconclusive snapshots attach deterministic context_guidance (including harmonic path). |
| T-CX268 | API/CLI/UI wire single_signal contextual submit; UI default unknown one-WAV uses contextual single_signal and renders guidance. |
| T-CX269 | GET /api/v1/presets/{id}/wav returns deterministic mono 48 kHz 32-bit PCM WAV without planner credentials. |
| T-CX270 | Served preset WAV preserves Demo DSP/tool discrete Evidence vs in-memory preset within float tolerance anchors. |
| T-CX271 | Unknown preset WAV route returns unknown_preset. |
| T-CX272 | Preset-derived contextual submit with filename input.wav never places Demo preset IDs in PlannerContext. |
| T-CX273 | Served harmonic_distortion WAV under ScriptedPlanner emits harmonic_attribution_requires_context guidance. |
| T-CX274 | Held-bytes upgrade resubmits the same test bytes as paired_reference / nominal_single_tone (survives parent eviction). |
| T-CX275 | Web UI fetches preset WAV, submits contextual single_signal as input.wav, renders upgrade controls, and does not POST /api/v1/runs/synthetic. |
| T-CX276 | Planner-ablation product slots use complete `submit_contextual_wav` kwargs and `wait_for_contextual_terminal`; legacy `submit_wav` / `wait_for_terminal` fail if called; Scripted integration returns a contextual snapshot. |
| T-CX277 | Study `fixed_pipeline` `single_signal` clipping finish accepts OQ-014 Option C equivalently to product gates. |
| T-CX278 | Study `fixed_pipeline` paired clipping requires contextual test-family evidence; no family mixing. |
| T-CX279 | Deterministic report parity across both arms for guidance emission, omission, reason codes, and required inputs; guidance never scored as planner skill. |
| T-CX280 | Study seal/scorer rejects foreign study identities and wrong denominator derivation; does not forbid coincidental numeric equality with historical rates. |
| T-CX281 | `evaluation/planner_ablation` does not import app composition/service/report modules; product diagnosis unchanged for non-study callers. |
| T-CX282 | Scripted dry-run covers both modes for Scripted executor and fixed baseline (four executor×mode paths), with fail-on-call provider spy proving zero provider calls. |
| T-CX283 | Scorer keeps diagnosis-less terminals in completion/outcome denominators when required; claim-level metrics use claim populations; zero-denominator rules explicit. |
| T-CX284 | Offline labels `context_obtainable`, `context_valid`, `context_sufficient` never appear in execution-arm inputs. |
| T-CX285 | Upgrade success reports both full pre-fixed population and conditional-success denominators. |
| T-CX286 | Parameterized decision function: dominance allowed under equal 100% completion only when all other required conditions hold; negative cases forbid dominance/advantage. |
| T-CX287 | Full matching-matrix tests for both frozen modes (clipping, harmonic, no-fault, valid inconclusive) on study baseline vs product gates. |
| T-CX288 | Scored-input validator rejects Scripted/harness-only artifacts even if arm label is rewritten to `product_agent`. |
| T-CX289 | Request identity from mode/test-byte/reference-byte/nominal/channel-segment/normalized question; equal-input oracle consistency; explicit single-mode aliases without double-counting scored units. |
| T-CX290 | Unique schedule (9 single + 10 paired keys), source/master relations, three rounds, and deterministic paired order with repetition outermost; 114 slots including 57 product slots. |
| T-CX291 | Fixed U/C/G populations and exact upgrade targets registered before execution; truth-free `ByteRequest` boundary excludes oracle/U/C/G/scenario truth from arm inputs. |
| T-CX292 | Shared timer `encoded_bytes_to_terminal_v1` includes decode/execute/guidance on both arms and excludes persistence/serialization after terminal readiness; wrong markers/version fail matching. |
| T-CX293 | Complete D037 service entry (`submit_contextual_wav` / `wait_for_contextual_terminal`) and two-arm report/gate matching including v9.11 and §16 Option C; no legacy submit/wait. |
| T-CX294 | Actual execution provenance from session construction/execution; relabeled Scripted/fake-client/offline artifacts rejected for scored product ingestion. |
| T-CX295 | Scheduled quality (exact outcome-plus-causal-set primary; outcome-only secondary), usefulness, and completion populations over unique requests; failed/no-diagnosis slots remain in required denominators. |
| T-CX296 | Same-run semantic claim/rule support; zero-claim and zero-eligibility states block positive conclusions or return not-evaluable — never fabricated 100% success. |
| T-CX297 | Parameterized zero-loss decision with all mode/round gates; dominance needs exact (0.20, 0.100 s) savings bands and no p95/action regression; planner advantage requires same-mode quality gain in every round; negative cases yield `insufficient_evidence`. |
| T-CX298 | Typed infrastructure stop vs behavioral continuation; outer deadline/teardown accounting; truncated campaign preserves full schedule and blocks accepted conclusion. |
| T-CX299 | Effective limits, bounded worst-case request/token budget, and actual resource telemetry; unknown limits or unavailable retry telemetry block execution. |
| T-CX300 | Full input/code/seal binding; readonly verify; generation refuses existing populated and empty destinations; foreign identity and mutated bindings fail. |
| T-CX301 | Dev_1 reproducer and preserved assets unchanged; `evaluation` must not import app composition; public product builder/default and historical contextual baseline unchanged. |
| T-CX302 | Full offline schedule acceptance with fail-on-call provider spy (zero calls); review_status remains pending; no formal seal or RealLLM during offline acceptance. |

T-CX004–T-CX145 are allocated to later tasks per the implementation plan and must
not collide with V0.2 T001–T285 numbering. T-CX146–T-CX165 are additive for the
v9.6 contextual remediation and must not alter T-CX001–T-CX145 meanings.
T-CX166–T-CX185 are additive for the v9.7 deterministic rule-closure remediation
and must not alter T-CX001–T-CX165 meanings.
T-CX186–T-CX190 are additive for the v9.8 claim-reference recovery remediation
and must not alter T-CX001–T-CX185 meanings.
T-CX191–T-CX196 are additive for the v9.9 paired-reference recovery remediation
and must not alter T-CX001–T-CX190 meanings.
T-CX197–T-CX207 are additive for the truth-free fixed-pipeline remediation and
must not alter T-CX001–T-CX196 meanings.
T-CX208–T-CX230 are additive for the contextual validation campaign runner and
must not alter T-CX001–T-CX207 meanings.
T-CX231–T-CX240 are additive for the v9.10 contextual clipping recovery and
must not alter T-CX001–T-CX230 meanings.
T-CX241–T-CX244 are additive lifecycle gates for the v9.10 development freeze
and historical v9.9 validation seal; they must not alter T-CX001–T-CX240
meanings.
T-CX245–T-CX247 are additive evaluation-observability gates for failed v9.10
real-model slots; they must not alter product error presentation, scoring,
retry behavior, or historical evidence.
T-CX248 is the append-only identity bridge for that evaluation-only change and
must not alter the v9.10 behavior-bearing identity or its qualification data.
T-CX249 preserves that historical bridge and binds the later post-assemble
evaluation-harness compatibility fix without changing product behavior.
T-CX250–T-CX255 are additive for v9.11 mode-aware no-fault recovery and must
not alter v9.10 identities, profiles, thresholds, data, scoring, or evidence.
T-CX256–T-CX259 correct the contextual scorer implementation to the already
preregistered claim populations. They must not alter campaign inputs, product
behavior, prompt, rules, thresholds, labels, or historical run artifacts.
T-CX260–T-CX261 add only deterministic offline reconstruction and boundary
validation for the same scoring correction.
T-CX262 records the follow-up evaluation-harness identity bridge only.
T-CX263 records OQ-014 Option C single_signal flat-top clipping finish behavior
and the append-only behavior identity bridge `oq014_option_c_single_signal_flat_top_clipping`.
T-CX264–T-CX268 are additive for D037 single-file context guidance. They must
not alter DSP, rule thresholds, planner prompts, causal finish gates, or frozen
V0.2 endpoints/DTOs. The append-only code-identity bridge
`d037_single_file_context_guidance` rebinds the live product-tree digest without
rewriting the sealed OQ-014 behavior-identity row.
T-CX269–T-CX275 are additive for the D037 Web UI upgrade loop (preset WAV
materialization and held-bytes upgrade). They supersede UI string assertions in
T277/T-CX268 that required `/api/v1/runs/synthetic` in `app.js`; the server route
remains for V0.2 compatibility. No RealLLM acceptance runs are required.
T-CX276–T-CX288 are additive definitions for the D038 planner-ablation utility
study (`CONTRACTS_V0_3_CONTEXTUAL.md` §19). Registering these IDs does not
implement or pass the behaviors. Harness code, Scripted dry-run execution,
protocol seal, and RealLLM campaign require later explicit grants. They must
not alter frozen V0.2 §§1–64, sealed v9.11 identities, DSP thresholds, or the
product planner default.
T-CX289–T-CX302 are additive definitions for the D038 protocol revision
(`CONTRACTS_V0_3_CONTEXTUAL.md` §20; study `study_s1_planner_ablation_dev_2`).
Registering these IDs does not implement or pass the behaviors and does not
seal approved design values. Study-only offline harness code and temporary
fixtures require an implementation grant already covering Tasks 2–7; formal
protocol seal, RealLLM campaign, product changes, and commit/push/merge remain
separately gated. They must not alter §19 / `dev_1` meanings, frozen V0.2
§§1–64, sealed v9.11 identities, DSP thresholds, or the product planner
default.
