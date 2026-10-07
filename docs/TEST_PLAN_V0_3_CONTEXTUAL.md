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
| T-CX303..318 | D038 token/transport telemetry / study_s1_planner_ablation_dev_2 (definitions; seal/RealLLM gated) |
| T-CX324..325 | OQ-019/dev_2 preseal evidence separation + PRESEAL status board (definitions; seal/RealLLM gated) |
| T-CX319..323 | D039 single-file observed facts on context_guidance (definitions; implementation gated) |
| T-CX329..348 | D042 regression troubleshooting workbench (definitions; Phase A–C implementation gated) |
| T-CX349..370 | D043 regression full-scale check (implemented, PR #41 `0770514`; characterization and floor approval gated) |
| T-CX371..380 | D043 layer-1 characterization tool (definitions; characterization runs and floor approval gated) |
| T-CX381..386 | D044 round_1 full-scale method floor registration (OQ-021 A, OQ-022 B) |
| T-CX387..410 | D045 S1 agent-increment slice: offline implementation, live runner, batch driver and the D1 round 1–4 fixes (live stages D1/F/H1 gated) |

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
| T-CX303 | Honest origins/default flags; unknown and legacy gates remain blocked. |
| T-CX304 | Actual SDK/native transport/source identity; dependency drift rejected. |
| T-CX305 | Requested/declared/returned model policy and acceptance binding. |
| T-CX306 | Observation on/off preserves payload, planner type, diagnosis and exception behavior. |
| T-CX307 | Actual turns/calls, no factory/wrapper double counts; conditional control-flow ceiling. |
| T-CX308 | All parse/reject budget-consumption events; SDK retries are separate. |
| T-CX309 | 500/500/200 attempt trace and usage before planner parsing. |
| T-CX310 | Redirect/send/authentication/lower-transport units and bounds. |
| T-CX311 | Failure/cancellation/lost-response observations and unknown tokens. |
| T-CX312 | Strict usage validation, subdivisions and missing data. |
| T-CX313 | Incomplete/invalid ledger, partial totals and bound violations. |
| T-CX314 | Slot isolation, late callbacks and real worker drain. |
| T-CX315 | Fixture/Scripted/fake/native-mock/forged-context ingestion rejection. |
| T-CX316 | Derived SDK/HTTP/token budgets and fail-closed unknown factors. |
| T-CX317 | Full candidate/review/proof/code/dependency binding; no synthetic shortcuts. |
| T-CX318 | Offline schedule, zero live calls, historical/package preservation. |
| T-CX319 | harmonic_attribution guidance with qualifying finite-float `thd_percent` Evidence yields non-empty field-faithful `observed_facts`. |
| T-CX320 | harmonic reason with no qualifying display Evidence yields `observed_facts=()` with reason codes exactly unchanged. |
| T-CX321 | insufficient_evidence path yields `observed_facts=()`; int/bool/str/NaN/Inf/wrong-tool/N/A excluded from display without coercion. |
| T-CX322 | old payload without `observed_facts` → `()`; new guidance round-trips through snapshot/report JSON with scope fields intact; soft-diagnosis banned. |
| T-CX323 | HTML lists facts only inside the context-guidance section (not Measured Evidence); product_tree identity append-only row binds digest change. |
| T-CX326 | Web UI guidance panel and CLI text list `observed_facts` inside context-guidance only (parity with T-CX323 HTML); empty tuple omits the list; no metric whitelist literals in static JS. |
| T-CX327 | Web UI loads `/api/v1/health` on bind; surfaces `planner_configured` readiness in the lifecycle panel; disables `submit-run` when unconfigured or health fetch fails; shows non-secret `planner_identity` when ready; no API keys, base URLs, or metric whitelist literals in static JS. |
| T-CX328 | Web UI `renderGuidance` humanizes `unlockable_modes` and `required_inputs` with mode-selector labels and readable input names; omits raw `reason_codes` line; `observed_facts` list unchanged; no metric whitelist literals in static JS. |
| T-CX329 | Regression request models are strict-typed with `extra="forbid"`; resolved analysis ranges are recorded; user declarations and observed byte/decode facts remain separated (definition; Tasks 2/5). |
| T-CX330 | Real-tool measurement produces independent bilateral identities for identical WAV bytes; no preprocessing; full tool status retained (definition; Task 2). |
| T-CX331 | Per-metric admission rejects incompatible units, tools, configs, ranges, or validity (definition; Task 3). |
| T-CX332 | Comparison rules honor difference direction, inclusive boundaries, and relative-difference denominator floors (definition; Task 3). |
| T-CX333 | Product path with `profile=None` is descriptive-only; fixture profiles must not publicly enable pass/fail (definition; Tasks 3/5). |
| T-CX334 | Cross-run SourceRef binding requires content/type consistency; rebuild validation rejects tampering (definition; Tasks 3/6). |
| T-CX335 | Partial coverage, pre-existing fault facts, and tool execution errors remain distinguishable; no overall pass when required checks are blocked (definition; Tasks 3/4). |
| T-CX336 | Same-session append, explicit parent links, and idempotent `request_id` submit semantics (definition; Task 5). |
| T-CX337 | File/session caps, busy concurrency, and cleanup release real workers (definition; Tasks 5/6). |
| T-CX338 | Case JSON/HTML preserve sources, escape untrusted text, and distinguish raw Evidence from derived differences (definition; Task 6). |
| T-CX339 | Web dual-file path supports manual retest; late responses and missing keys do not forge success (definition; Task 6). |
| T-CX340 | Retest catalog eligibility, no-eligible abstain, and forbidden overreach parameters (definition; Task 7). |
| T-CX341 | Independent retest planner identity, compact inputs, strict outputs (definition; Task 7). |
| T-CX342 | Retest budget/cancel/failure with no silent Scripted fallback (definition; Task 7). |
| T-CX343 | Fixed-strategy vs model-adapter offline contrast isolates truth labels and failure denominators (definition; Task 8). |
| T-CX344 | Real adapter + fake transport offline wiring with zero network calls (definition; Task 8). |
| T-CX345 | Legacy diagnosis entry points, D037/D039, and sealed assets remain preserved (definition; Tasks 4/9). |
| T-CX346 | Layering, frozen allowlists, and append-only identity bridges for new modules (definition; Tasks 4/9). |
| T-CX347 | Repair retest outcomes distinguish disappeared, persistent, not-applicable, and failed runs (definition; Tasks 5/6). |
| T-CX348 | Without approved rules/benefit evidence, do not claim product or planner acceptance complete (definition; Tasks 8/9). |
| T-CX349 | Count equals the existing full-scale mechanism sample for sample; isolated single samples go to `over_threshold_uncounted`; facts use the bundle's range and channel (definition; §23). |
| T-CX350 | Clean-sine cells with non-zero `clipping_ratio` have `counted_samples = 0`; a ratio difference never changes the check status (definition; §23). |
| T-CX351 | `ClippingOutput`, `MeasurementBundle` digest, `ComparisonRecord` content, `required_checks`, overall pass and validation are unchanged (definition; §23). |
| T-CX352 | no → yes is `regression_detected` when eligible, and has no judged status when any gate is missing, however large the change (definition; §23). |
| T-CX353 | yes → yes: above floor is regression; at or below floor and equal are not (definition; §23). |
| T-CX354 | Decrease and disappearance are `no_regression_detected` with the same-screen notice; missing notice fails (definition; §23). |
| T-CX355 | Templates contain neither "clipping" nor "no clipping"; regression carries the export-settings notice; THD and ratio coverage lines present; "declared, not verified", unchecked-fundamental and render-count lines present; required values shown (definition; §23). |
| T-CX356 | `periodic_test_signal` omitted, `unknown` or `no` gives `descriptive_only`; read from the anchor only (definition; §23). |
| T-CX357 | Critical zone: either side inside gives `descriptive_only` naming the side; fixed minimum for a `no` side within one coarser-depth step below threshold; a one-step difference on such a baseline does not yield `regression_detected` (definition; §23). |
| T-CX358 | Counted-repeat rules: declared independent, same selection/range/rate/channel/versions, own declarations not blocking; others listed with reason and create no contradiction; byte-identical counted repeats are marked; independence declarations ignored on the anchor (definition; §23). |
| T-CX359 | No counted repeat on a side gives `descriptive_only`; inconsistent counted renders give `not_comparable` with the contradiction (definition; §23). |
| T-CX360 | Service construction rejects a profile with a `clipping_ratio` rule; test fixtures exempt; ratio stays descriptive with its notice; overall pass not presented as pending (definition; §23). |
| T-CX361 | Sub-full-scale clipped pair gets no judgment beyond the full-scale state; auxiliary facts visible (definition; §23). |
| T-CX362 | Equal versions, missing fundamental, out-of-domain samples per period or periods in range, and bit depth below 16 each give `descriptive_only` with the reason (definition; §23). |
| T-CX363 | No floor record, or one whose identity fields mismatch, gives no judged status; unevaluable conditions are listed as unevaluated; clients cannot upload a floor or approval flag (definition; §23). |
| T-CX364 | Record lifecycle: one per completed comparison, none for failed submits or idempotent replays, no quota use, immutable, superseding pointer (definition; §23). |
| T-CX365 | Anchor resolution: repeat of repeat reaches the root; `repair` and `recommendation` comparisons are their own anchors (definition; §23). |
| T-CX366 | Blocking anchor declarations and missing facts (tool error) give `not_comparable`; `not_comparable` precedes `descriptive_only`; all unmet conditions listed (definition; §23). |
| T-CX367 | Validation recomputes selection, eligibility, status and digests; cross-checks state, peak, length and threshold against the bundle; tampering raises (definition; §23). |
| T-CX368 | The check never enters `StructuredDiagnosis` or the causal gate; legacy diagnosis paths unchanged (definition; §23). |
| T-CX369 | Layering: counting in `dsp/`, adapter in `tools/`, judgment in `rules/`; allowlist appended; `rules/` imports no `app/` (definition; §23). |
| T-CX370 | Submit fingerprint covers `FullScaleDeclarations`; strict models reject unknown fields; omission equals `unknown` (definition; §23). |
| T-CX324 | Offline observation capability/event-graph tests and per-run ledgers do not admit production worst-case planner/SDK/HTTP/token ceilings; each ceiling needs an independent applicable authenticated proof; preseal must not require a formal RealLLM campaign ledger before seal. |
| T-CX325 | `PRESEAL_BUDGET_STATUS.md` is a permitted unsealed status board under `study_s1_planner_ablation_dev_2`; it is not a numeric bound-fact citation; formal candidate readiness follows source-aware validation, not legacy `inspect_limits`. |

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
T-CX303–T-CX318 are additive definitions for D038 token/transport telemetry
(`CONTRACTS_V0_3_CONTEXTUAL.md` §21; study `study_s1_planner_ablation_dev_2`).
Registering these IDs does not implement or pass the behaviors. They preserve
T-CX299's requirement for actual resource telemetry; ceiling-only estimates
are not a substitute. Later T285 additive paths for this feature are exactly
`src/signal_diag/agent/telemetry.py`,
`src/signal_diag/agent/provider_telemetry.py`, and
`src/signal_diag/evaluation/recording.py`. Unsealed evidence may add
`RESOURCE_BOUNDS.md` under the `dev_2` study root; `protocol_seal/` remains
forbidden. Offline observation, source-aware admission, architecture allowlist
edits, formal seal, RealLLM, concrete numeric budget acceptance,
provider-model mapping acceptance, product request caps, and commit/push/merge
remain separately gated. They must not alter §19 / §20 / `dev_1` meanings,
T-CX001–T-CX302 definitions, frozen V0.2 §§1–64, sealed v9.11 identities, DSP
thresholds, or the product planner default.
T-CX319–T-CX323 and T-CX326 are additive definitions for D039 single-file observed facts
(`CONTRACTS_V0_3_CONTEXTUAL.md` §17; design
`docs/superpowers/specs/2026-10-03-single-file-observed-facts-design.md`).
Registering these IDs does not implement or pass the behaviors. Product code,
HTML render, tests, and the append-only code-identity row require a separate
implementation grant. They must not alter reason-code selection, DSP, rule
thresholds, planner prompt, causal finish gates, frozen V0.2 §§1–64, sealed
v9.11 identities, planner-ablation budgets, or T-CX001–T-CX318 meanings.
T-CX324–T-CX325 are additive definitions for OQ-019/dev_2 preseal evidence
separation (`CONTRACTS_V0_3_CONTEXTUAL.md` §21.9). They clarify that offline
observation/ledgers do not admit worst-case ceilings, that preseal does not
require a RealLLM campaign ledger before seal, and that
`PRESEAL_BUDGET_STATUS.md` is a permitted status board (not a numeric
bound-fact citation) while formal readiness stays on source-aware validation.
Registering these IDs does not clear residual blockers, authorize seal or
RealLLM, retarget legacy `inspect_limits`, or change product diagnosis gates.
They must not alter §19 / §20 / §21.1–21.8 / `dev_1` meanings,
T-CX001–T-CX323 definitions, frozen V0.2 §§1–64, sealed v9.11 identities, DSP
thresholds, or the product planner default.
T-CX329–T-CX348 are additive definitions for D042 regression troubleshooting
workbench (`CONTRACTS_V0_3_CONTEXTUAL.md` §22; design
`docs/superpowers/specs/2026-10-04-s1-regression-troubleshooting-workbench-design.md`).
Registering these IDs does not implement or pass the behaviors. Phase A
measurement/compare code, Phase B case/Web surfaces, Phase C retest planner,
product tolerances, RealLLM, commit/push/merge, and seal remain separately
gated. They must not alter frozen V0.2 §§1–64, D037/D039 diagnosis semantics,
v9.11 planner identity, sealed evaluation/Demo assets, planner-ablation study
authority, or T-CX001–T-CX328 meanings.
T-CX349–T-CX370 are definitions for D043 regression full-scale check
(`CONTRACTS_V0_3_CONTEXTUAL.md` §23). Registering these IDs does not implement
or pass the behaviors and authorizes no floor, critical-zone or
approved-domain value. Implementation, the layer-1 characterization run, floor
approval, RealLLM, merge, and seal remain separately gated. They must not
alter frozen V0.2 §§1–64, D037/D039 diagnosis semantics, v9.11 planner
identity, sealed evaluation/Demo assets, or T-CX001–T-CX348 definitions;
D043 changes the reading of §22 only as stated in §23.1 and D043.
Implementation status: T-CX349–T-CX370 are implemented by PR #41 (`0770514`); the
test function for each ID is listed in
`docs/REGRESSION_FULL_SCALE_CHECK_OFFLINE_ACCEPTANCE.md`. The tests use
fixture floors only; their values are not tolerances.
T-CX371–T-CX380 are definitions for the D043 layer-1 characterization tool
(plan `docs/superpowers/plans/2026-10-05-s1-regression-layer1-characterization.md`;
`CONTRACTS_V0_3_CONTEXTUAL.md` §23.7 step 3 tool portion). Registering these
IDs does not authorize any formal characterization run (R0–R4), floor value,
critical-zone value, or approved-domain value. Implementation of the tool,
characterization runs, floor approval, RealLLM, merge, and seal remain
separately gated.

| ID | Definition |
|----|------------|
| T-CX371 | Characterization package imports only lower layers; product code does not import the package; product floor registry stays empty (empty-registry clause superseded by D044 / T-CX386) |
| T-CX372 | Integer PCM codes match the loader (32-bit vs float32 decode); one-step perturbations stay within one step and keep direction; seed fixes bytes |
| T-CX373 | Manifest is deterministic and hashable; sensitivity pairs carry one perturbation; tolerance codes are only those listed; seed sets do not overlap |
| T-CX374 | Split by source group; no leakage by effective params/codes per channel; near-duplicate sensitivity pairs are excluded and listed; validation subgrid is complete and scale-bounded |
| T-CX375 | Executor uses the full tool path; identity and digests are deterministic; terminal states stay in the denominator; channels are isolated |
| T-CX376 | P0, sandwich, one-sided worst-case equality, single-step flip, or facts verify failure aborts; P9 out-of-zone flips are counted only |
| T-CX377 | Zone checks match product case-by-case; two-step fitting uses the fixed candidate tables only; no margin; no validation-side reads; reports do not rank |
| T-CX378 | Two-step freeze is select-only; artifacts are write-once; incomplete freeze blocks validation side; identity compare set covers measurement path and scoring code |
| T-CX379 | Validation counts only; both hard conditions and all mandatory disclosures are present; abort has a record; no product-judgment wording |
| T-CX380 | End-to-end six steps on a mini manifest are reproducible byte-for-byte |

T-CX381–T-CX386 are definitions for D044 round_1 full-scale method floor
registration (`docs/DECISIONS.md` D044; closes OQ-021 Option A and OQ-022
Option B). They authorize the reviewed freeze values as the product floor
record. They must not alter frozen V0.2 §§1–64, `FullScaleMethodFloor` model
fields, critical-zone or judgment logic (except OQ-021 identity applicability),
sealed evaluation/Demo digests, or T285 allowlists. If product-tree hash
changes from adding a versioned floor YAML under `rules/profiles/` cause V0.2
protection, T285, or sealed-identity failures, stop and report without
updating sealed hashes or allowlists.

**D044 T285 allowlist (operator-authorized 2026-10-06):** append-only addition
to `_V03_ADDITIVE_EXACT_PATHS` of
`src/signal_diag/rules/profiles/s1_full_scale_floor_round_1.yaml` (one line;
no other allowlist or hash rewrites in that authorization).

| ID | Definition |
|----|------------|
| T-CX381 | OQ-021 Option A: when either anchor side has no facts, `_floor_identity_ok` is false; check lists `floor_missing` and does not carry the floor |
| T-CX382 | OQ-022 Option B: §23.4 requires any approved floor `zone_above` ≥ one 16-bit step; registered floor satisfies it; `_in_critical_zone` unchanged |
| T-CX383 | Versioned floor YAML under `rules/profiles/` loads; digest self-check rejects tampering |
| T-CX384 | YAML numeric fields equal freeze_record.json at full precision (no rounding) |
| T-CX385 | `build_regression_service` wires the approved floor (no longer `full_scale_floor=None`); eligible submissions judged with `PRODUCT_APPROVED_FULL_SCALE_FLOORS[0]` follow the product count floor (1280 samples) and transition table (regression / no regression / critical-zone descriptive_only) |
| T-CX386 | `PRODUCT_APPROVED_FULL_SCALE_FLOORS` equals the loaded YAML floor; supersedes empty-registry assertions where they conflict |

T-CX387–T-CX410 are additive definitions for D045
(`CONTRACTS_V0_3_CONTEXTUAL.md` §24; plan
`docs/superpowers/plans/2026-10-06-s1-agent-increment.md`). Registering these
IDs does not authorize a real-model run, a product prompt switch, seal, or
merge. They must not alter frozen V0.2 §§1–64, the v9.11 prompt text, sealed
evaluation or Demo assets, or T-CX001–T-CX386 meanings.

| ID | Definition |
|----|------------|
| T-CX387 | Intake draft validation: nominal Hz must come from a number written in the text, including kHz conversion; the reference file must be an upload and not the test file; mode must match the file count; extra fields are rejected |
| T-CX388 | The intake planner sends only text and file metadata; missing credentials fail and do not fall back to a scripted stand-in |
| T-CX389 | Intake entry: unconfirmed fields do not enter diagnosis; after confirmation the existing contextual endpoint submits and validates as usual |
| T-CX390 | B1 regex baseline is deterministic, its rule table is frozen, and it shares the simulated user and the validator with the agent |
| T-CX391 | v9.12 starts with the current v9.11 text and registers its hash; the product default remains v9.11 |
| T-CX392 | Segment evidence rules: a segment FAIL can support a conclusion; thresholds come from the existing profile; location comes from the cited Evidence |
| T-CX393 | B2 segment scan is deterministic, its parameters are frozen, and it records call counts |
| T-CX394 | The simulated user only confirms or corrects fields already proposed, and does not fill the rest |
| T-CX395 | Scoring matches design §4.2 for increment, safety hard conditions, and T1/T2 metrics |
| T-CX396 | Call caps are 21 per case and the stage total; crossing a cap stops the run and writes a stop record; output is write-once |
| T-CX397 | Case sets meet design §4.1 proportions; the held-out set is generated from the frozen template and seed; SHA256SUMS and the manifest hash stay fixed |
| T-CX398 | Offline end to end: scripted stand-ins run all three arms, the report is complete, and identity fields are present |
| T-CX399 | Live runner: T1 intake then study-planner contextual diagnosis, T2 study-planner runtime (v9.12 until D1 round 2, v9.13 in round 3, v9.14 in round 4, v9.15 from round 5); every HTTP send reserves a call first; caps stop before the next send; missing credentials do not fall back; dry-run does not call a model |
| T-CX400 | Live outcome: the agent row is scored by the same rules as the offline rows of its family; T1 draft accuracy uses the first draft; T2 location comes from the Evidence the claims cite, and whole-file analysis never localizes for any arm; a failed intake scores as wrong without an unsupported claim; a T1 reference and nominal Hz come only from confirmed fields; the call guard reaches the SDK at `chat.completions.create` |
| T-CX401 | Batch driver: cases run in manifest order under one stage ledger; a cap stop (including one raised inside intake) ends the stage with completed cases kept and the report marked incomplete; a transport failure, a malformed intake response or a harness-side intake error stops the stage instead of being scored; an invalid draft is scored as wrong, while empty intake content stops the stage; an abort still writes the ledger, an incomplete report and a stop record; every live diagnosis run gets one neutral request while the T1 intake reads the case text; a cap stop wrapped in another exception type is still a cap stop; output is write-once |
| T-CX402 | Held-out guard: a held-out run needs a matching `prompt_freeze_record.json` (planner and intake prompt hashes), writes only to `<study>/runs/heldout_*`, and runs once; a setup failure before the output directory exists (including an unreadable case WAV) does not use up the run; the freeze record also pins the diagnosis request; a dev run cannot take a `heldout_` name; the freeze record is write-once |
| T-CX403 | Command line: `--run` needs DEEPSEEK_API_KEY and does not fall back; `--dry-run` is unchanged; `--dry-run`, `--run` and `--freeze-prompts` are mutually exclusive |
| T-CX404 | Mini dev stage end to end with a fake SDK: all three arms per case, ledger equals sends, identity complete, no credentials, audio or provider payloads in the output |
| T-CX406 | Study planner v9.13: starts with the v9.11 text, replaces the v9.12 paragraph (whose hash stays pinned) with a channel and window call plan sized from `signal_meta.duration_s`, `signal_meta.channels` and `remaining_tool_calls`, says an invalid harmonic result is not Evidence, and forbids inventing thresholds or a fundamental frequency; the product default remains v9.11; the study harness (offline, live runner, batch driver) uses v9.13 |
| T-CX407 | Intake prompt `v0.3-s1-intake-1.1`: names every allowed `mode` and `stimulus_kind` value and every draft key, and its JSON example validates as a draft; a draft that fails validation records each failing field location, error type and message in the case file, never the model's values |
| T-CX408 | Study planner v9.14: starts with the v9.11 text; v9.12 and v9.13 hashes stay pinned; every call plan it describes fits `AgentLimits` (rule evaluations and tool calls), and its budget figures are derived from `AgentLimits`; executed deterministically without a model, its single-file plan localizes every dev clipping case and flags no dev clean case; the product default remains v9.11; the study harness uses v9.14 |
| T-CX409 | Study planner v9.15: starts with the v9.11 text; the v9.14 hash stays pinned; names `inconclusive` with no claims as the single-file outcome when no window shows clipping; driven through the real runtime by a fake SDK that follows the plan, every prescribed finish (mono clean, mono clipping, stereo clipping) is accepted with no rejection and within the rule-evaluation budget; the study harness uses v9.15 |
| T-CX410 | Scoring correction: an agent run that ends without a diagnosis is never a correct conclusion, including on clean T2 cases; an `inconclusive` finish with no claims on a clean T2 case is correct; each case file records the runtime's rejection messages (`run_errors`) |
| T-CX405 | Intake request settings: the request body sent on the wire disables reasoning (`thinking: disabled`), asks for a JSON object and uses temperature 0, the same settings as the diagnosis planner |

T-CX411–T-CX419 are additive definitions for D047
(`CONTRACTS_V0_3_CONTEXTUAL.md` §25). They do not authorize a real-model run
or a product prompt switch, and must not alter T-CX001–T-CX410 meanings.

| ID | Definition |
|----|------------|
| T-CX411 | Assembly table: every row of `tests/app/fixtures/intake_assembly_cases.json` (each mode, each downgrade, each rejection) gives the expected submission or `invalid_request` |
| T-CX412 | Unconfirmed draft fields never reach the submission: `--yes` drops fields in `missing_fields` or `asked_fields`, and a mode missing a required field is submitted as `single_signal` with the reason |
| T-CX413 | Nominal Hz is never backfilled from audio: with no confirmed number the submission carries none whatever the WAV holds; the WAV header reader returns only the sample rate |
| T-CX414 | API end to end with a scripted intake: draft, confirm, submit with `context_origin=intake_confirmed`; snapshot and reports carry the origin, `assertion_source` is `user_supplied`, the question is the neutral default; form runs omit `context_origin`; any other origin value is rejected |
| T-CX415 | CLI `intake diagnose`: `--yes`, explicit flags overriding the draft, the downgrade note, and the non-terminal refusal without confirmation; invalid flags exit 2 without opening a run |
| T-CX416 | CLI interactive confirmation: keep, edit and skip answers through scripted stdin; a skipped required field downgrades |
| T-CX417 | Missing credentials: `intake diagnose` exits 2 with `planner_not_configured`, prints no report, and no fallback runs |
| T-CX418 | Browser helpers under Node: the draft request body holds text and file metadata only; the diagnose form carries the confirmed fields, the context origin, the neutral question and the audio; the WAV header reader matches Python; the page loads `intake_flow.js` before `app.js` and the draft request sends no audio |
| T-CX419 | The browser assembly and downgrade message match the Python implementation on the shared table |

T-CX420–T-CX424 are additive definitions for the Web UI layout design
(`docs/superpowers/specs/2026-10-06-web-ui-layout-design.md`). They change no
API, report, prompt or frozen test, and must not alter T-CX001–T-CX419 meanings.

| ID | Definition |
|----|------------|
| T-CX420 | The intake panel comes before the manual form; the manual form sits in a collapsed `<details id="manual-panel">` and keeps every original element id |
| T-CX421 | The summary card reads only existing snapshot fields (outcome, confidence, mode, context origin, claims) and holds the report links; technical panels are collapsed `<details class="tech-panel">` with unchanged ids, shown only after a run and hidden when empty; the V0.2 evaluation summary sits collapsed after the results |
| T-CX422 | The two-column layout is a CSS grid above 1100 px with a sticky results column, single column below; no framework or CDN |
| T-CX423 | `lang="zh-CN"`; every English string pinned by frozen tests stays on the page or in the script; the default diagnosis question is not translated |
| T-CX424 | Browser proof (manual, not in CI): with a scripted intake and stub planner, the intake → confirm → diagnose flow completes at 1440 px and 390 px widths with no page errors and no horizontal scroll |

T-CX425–T-CX427 are additive definitions for D048
(`CONTRACTS_V0_3_CONTEXTUAL.md` §21.10). They make no model call and must not
alter T-CX001–T-CX424 meanings.

| ID | Definition |
|----|------------|
| T-CX425 | The audited SDK observation profile names the HTTP client the SDK dispatches through (`httpx2` for `openai==3.6.0`): family, version from that module, and `httpx2.AsyncClient.send`; the reviewed identity matches and the installed profile is supported |
| T-CX426 | An `httpx2` version that differs from the reviewed one makes the profile unsupported with `httpx2_version_drift:…`; a profile naming a different dispatch family is rejected at attach with `native_http_family_mismatch` |
| T-CX427 | Against a closed local port, an attached observation records paired SDK-attempt and HTTP-send start/end events for one SDK call |

T-CX428–T-CX433 are additive definitions for D049
(`CONTRACTS_V0_3_CONTEXTUAL.md` §26). They make no model call and must not
alter T-CX001–T-CX427 meanings or the Workstream A/B tests.

| ID | Definition |
|----|------------|
| T-CX428 | With the guard on, pure tones at 8/16/44.1/48 kHz and 110–997 Hz estimate within 0.1 % and never at a subharmonic; `method` stays `autocorrelation` |
| T-CX429 | With the guard on, the repository's 700 Hz subharmonic-lock probe and the 440 Hz T2 harmonic WAVs estimate within 0.5 % |
| T-CX430 | With the guard on, every V0.2 synthetic case keeps voicing, harmonic validity, series kind and THD judgment against the recorded pre-D049 baseline, with F0 within 0.2 %, and auto-F0 THD equals THD at the true fundamental; with the guard off, F0 and THD equal the baseline exactly |
| T-CX431 | The independent external reference analyzer still reproduces its sealed F0 and does not import `dsp.pitch` |
| T-CX432 | With the guard on, noise stays unvoiced and an aperiodic recording stays unreliable with invalid harmonic analysis |
| T-CX433 | `GuardedSignalToolService` estimates with the guard and the base `SignalToolService` without it; only `app/service.py` (both run paths) and the planner-ablation adapter's fixed arm use the guarded service; evaluation runners, the agent-increment harness, the regression workbench and `tools/service.py` do not |

T-CX434–T-CX440 are additive definitions for D050
(`CONTRACTS_V0_3_CONTEXTUAL.md` §27). They make no model call and must not
alter T-CX001–T-CX433 meanings.

| ID | Definition |
|----|------------|
| T-CX434 | Windows are 0.25 s with 50 % overlap and cover the file; overlapping FAIL windows merge into one interval per fault and channel, and every interval's Evidence and evaluation IDs are present in the same localization |
| T-CX435 | Every H1 held-out T2 case with fault spans is localized: clipping in `single_signal`, harmonic distortion in `nominal_single_tone` with the declared 440 Hz |
| T-CX436 | Clean H1 held-out T2 cases and V0.2 clean synthetic cases produce no interval |
| T-CX437 | `single_signal` never scans harmonics: no harmonic interval or harmonic Evidence |
| T-CX438 | A contextual run calls the scan once after the diagnosis; the diagnosis and the agent's Evidence are the same with the scan on and off, and the scan's Evidence is separate |
| T-CX439 | With localization set, the snapshot, report JSON, HTML report, CLI text and Web UI show it; unset, the snapshot and report JSON omit `fault_localization` and the HTML has no section |
| T-CX440 | Browser proof with a stub planner (manual, not in CI): the 故障位置 panel shows the intervals with the right scope note, with no page error and no horizontal overflow at 1440 px and 390 px |

T-CX441–T-CX447 are additive definitions for D051
(`CONTRACTS_V0_3_CONTEXTUAL.md` §27.1). They make no model call and must not
alter T-CX001–T-CX440 meanings; T-CX434 and T-CX439 now expect scan version
`product-segment-scan-1.1`.

| ID | Definition |
|----|------------|
| T-CX441 | With a diagnosis that supports harmonic distortion, a synthetic harmonic burst at 1.0–1.5 s against a clean reference (steady and decaying, offsets 0, 30 and 200 ms) yields harmonic intervals that overlap the burst on the test timeline and stay within one window of it, each citing the four PASS gate evaluations and the growth FAIL; identical files yield none; with a stereo test and a mono reference only the distorted channel is localized |
| T-CX442 | Windows with a clipped reference span, past the reference end, or with an incompatible fundamental count as not comparable and yield no harmonic interval; `paired_reference` without a reference record is rejected |
| T-CX443 | Every paired case of the contextual development and validation studies, with a diagnosis that supports harmonic distortion: cases whose causal set contains harmonic distortion yield a harmonic interval, all others yield none, and inconclusive cases have every comparison window not comparable |
| T-CX444 | For every H1 held-out T2 case, `single_signal` and `nominal_single_tone` results equal the recorded 1.0 baseline except `scan_version`, with `harmonic_basis` set only for the declared tone and no paired fields |
| T-CX445 | A paired run's snapshot, report JSON, HTML report, CLI text and Web UI show `harmonic_basis`, the comparison windows, the not-comparable count and, when the diagnosis does not support harmonic distortion, the withheld count with no harmonic interval; single-file output omits the paired fields |
| T-CX446 | Browser proof with a stub planner (manual, not in CI): a paired manual run shows the reference-comparison note and the withheld count, with no page error and no horizontal overflow at 1440 px and 390 px |
| T-CX447 | Without a harmonic diagnosis (none, or clipping only), paired harmonic windows yield no interval, no contextual Evidence and no growth evaluation, and `harmonic_windows_withheld` counts them; with one, it is 0; other modes omit it |

T-CX448–T-CX456 are additive definitions for D053
(`CONTRACTS_V0_3_CONTEXTUAL.md` §28). They make no model call and must not
alter T-CX001–T-CX447 meanings.

| ID | Definition |
|----|------------|
| T-CX448 | The engine is a `PlannerModel` that imports no model client; single-file runs call whole-file clipping and harmonic tools and, only without whole-file clipping, every clipping window; contextual runs make one comparison call; supported faults cite knowledge; short files finish |
| T-CX449 | Regenerating `phase1_comparison/report.json` reproduces the committed file byte for byte, with no errors and every run finished by `planner_finished` |
| T-CX450 | Repeated engine runs on the same input give the same outcome and claims |
| T-CX451 | Single-file runs never attribute harmonic distortion, on a synthetic harmonic tone and on every single-file row of the report |
| T-CX452 | Every set with recorded planner results has engine correctness not below the planner's, apart from the cases listed as accepted limitations, which are exactly the cases where only the engine is wrong |
| T-CX453 | `build_engine_service` diagnoses without credentials, rejects `diagnosis_path=planner` without credentials and builds `RealLLMPlanner` with them; `build_product_service` keeps the planner default and has no engine |
| T-CX454 | Engine runs carry `diagnosis_identity` and omit `planner_identity` in the snapshot and report JSON; the HTML has the engine section and no planner section; the CLI defaults to the engine; the health response keeps the T264 fields and adds `diagnosis_engine` |
| T-CX455 | The Web UI enables diagnosis from `diagnosis_engine` without credentials, disables free-text drafting without credentials and shows who decided the verdict |
| T-CX456 | Browser proof with the engine service and no credentials (manual, not in CI): a diagnosis completes, the summary shows the engine, drafting is disabled, with no page error and no horizontal overflow at 1440 px and 390 px |

T-CX457–T-CX465 are additive definitions for D054
(`CONTRACTS_V0_3_CONTEXTUAL.md` §29). They make no model call and must not
alter T-CX001–T-CX456 meanings.

| ID | Definition |
|----|------------|
| T-CX457 | The stimulus is versioned and byte-identical across calls at 44.1 and 48 kHz, starts at 20 Hz after silent padding, peaks at 0.5, and rejects other rates; the downloadable WAV is 24-bit, round-trips through `load_wav_bytes`, carries the version and parameter digest, and a loopback diagnoses as no fault |
| T-CX458 | A polynomial device's band THD matches the analytic value within 0.05 percentage points; identity, chorus and high-pass devices stay below 0.1 % in bands from 125 Hz up; with a low-pass after the polynomial, band THD follows the steady-tone THD within 15 % (harmonics read at n·f) |
| T-CX459 | Low-band clipping exceeds 5 % only in the low bands; hard and soft clipping exceed 5 % with odd dominant orders; recorder full scale yields a clipped ratio and a frequency span |
| T-CX460 | Delay and sample rate do not change results; a wrong stimulus has low alignment, noise lowers SNR and makes bands unmeasurable, 500 ppm drift is measured as above 200 ppm, truncated and non-finite recordings are invalid, and bands respect Nyquist |
| T-CX461 | The profile is `profile_s1_sweep` 1.0.0-demo; clean, harmonic, full-scale, noisy, drifted, wrong-stimulus and truncated recordings give the defined verdicts with same-run citations; device clipping below full scale is harmonic distortion; three levels report the onset; bad inputs map to app error codes; IDs are deterministic |
| T-CX462 | Repeated analysis of the same recording is identical |
| T-CX463 | JSON and HTML reports carry the threshold notice, escape labels, list cited evaluations and refuse claims citing another level; the chart follows the mark specs (2 px lines, validated series colours, dashed demo limit, 24 px hover targets) with no inline style or script |
| T-CX464 | The CLI writes the stimulus, diagnoses 1–3 recordings with labels in text and JSON, writes the HTML report and exits 2 on usage and WAV errors |
| T-CX465 | The API serves the stimulus, runs and reports with the CSP header, returns 404 for unknown runs and report kinds, rejects malformed uploads with 422, and serves `/sweep` and `sweep.js`; the page links from `/` and sets dynamic text without `innerHTML`; browser proof (manual, not in CI): three levels give the onset summary, chart, table and claims with no page error and no horizontal overflow at 1100 px and 390 px |

T-CX466–T-CX476 are additive definitions for D055
(`CONTRACTS_V0_3_CONTEXTUAL.md` §30). They make no model call and must not
alter T-CX001–T-CX465 meanings.

| ID | Definition |
|----|------------|
| T-CX466 | Display values follow the per-unit forms; contextual and sweep packets are deterministic (equal packets and digests), cite exactly the claims' rule evaluations, carry levels, bands and knowledge, and contain no raw arrays |
| T-CX467 | The next-step menu follows the verdict and failing rules for contextual (clipping, single-file, inconclusive paired, no fault) and sweep (full scale, onset, noise, wrong stimulus, clean) runs, and every trigger ref is a packet item |
| T-CX468 | The validator rejects each violation with its check name (structure, citation, conclusion coverage, number, wording, ids in text, length, next step off menu or untriggered, fault mismatch including inconclusive phrased as fine) and accepts rounding, kHz conversion and negated fault mentions |
| T-CX469 | The template passes validation on all 152 recorded engine cases and on synthetic sweep cases, in Chinese and English |
| T-CX470 | The template is deterministic, its meaning sentences cite knowledge, and its steps follow the menu |
| T-CX471 | The model adapter sends the fixed system prompt and only the packet and template baseline, wraps transport failures as `ExplainerError`, and rejects an empty model name |
| T-CX472 | The service returns the template by default with no model call; asking for the model when unavailable is `planner_not_configured`; a valid model draft is returned as `model`; illegal JSON, validation failures and provider errors fall back to the template with the reason; the builder needs both credentials and the enable flag |
| T-CX473 | The API explains completed contextual and sweep runs in both languages, rejects extra body keys and unknown runs, returns 503 for an unavailable model, reports `explanation` in health, and adds the latest explanation to JSON and HTML reports only after one exists |
| T-CX474 | CLI `--explain template` prints and embeds the explanation for contextual and sweep runs, `--explain model` without enablement exits 2, and runs without `--explain` are unchanged |
| T-CX475 | Both pages load `explanation.js`, keep the AI button hidden until health allows it, and set text without `innerHTML`; browser proof (manual, not in CI) with a scripted explainer: template on both pages, the fallback note after the AI button, no page error and no horizontal overflow at 1440 px and 390 px |
| T-CX476 | The acceptance harness writes `results.jsonl`, `summary.json` and a 20-sample `review.md` for 50 cases offline with no model call and no credential text, and in live mode counts model calls, pass rate and fallback reasons |

T-CX477–T-CX482 are additive definitions for D056
(`CONTRACTS_V0_3_CONTEXTUAL.md` §29.1). They download nothing, make no model
call and must not alter T-CX001–T-CX476 meanings.

| ID | Definition |
|----|------------|
| T-CX477 | `estimate_sweep_rate` recovers L within 0.5 % for a pOD-set-like sweep (5 Hz–24 kHz, 4 s, no silence) and for the product sweep, and rejects a non-sweep |
| T-CX478 | On a pOD-set-like sweep, the identity reads ≤ 0.05 % in every band, an alias-free polynomial is within 0.1 pp of theory from 125 Hz to 4 kHz, and a filtered device follows the steady-tone THD within 15 % |
| T-CX479 | A 40-sample lag and level normalization leave band THD unchanged; the analysis is deterministic and rejects a recording shorter than the stimulus |
| T-CX480 | The range reader extracts only the named zip members, and the manifest records their sizes and SHA-256; 18 sweep files per pedal |
| T-CX481 | The synthetic check passes on the dataset-format dry sweep; the short-time-spectrum cross-check agrees at 1, 2 and 4 kHz; the criteria count level and gain monotonicity and cross-check agreement, including the tolerance |
| T-CX482 | An end-to-end run on a simulated cache verifies hashes, writes only `manifest.json`, `results.json` and `summary.json` (no audio), reports the design pedal separately and the onset at the demo limit, and refuses a tampered file |

T-CX483–T-CX493 are additive definitions for D057
(`CONTRACTS_V0_3_CONTEXTUAL.md` §31). They make no model call and must not
alter T-CX001–T-CX482 meanings.

| ID | Definition |
|----|------------|
| T-CX483 | The catalog has four plans and three connections; sweep steps for every connection and language name the confirmed rate and promise only the first level above the demo threshold (no monotonic claim); a nominal plan names its frequency |
| T-CX484 | Valid drafts pass: stated and default rates, default labels, a nominal frequency written as kHz, paired files, and an asked missing frequency |
| T-CX485 | The validator rejects each violation with its check name: unknown plan, connection or field, too many questions, an unsupported rate, an unstated rate, invented label numbers, duplicate labels, quotes not in the text or missing, a sweep when the text rules out a re-test, banned question wording, an unwritten frequency, a missing frequency, one uploaded file for a paired plan, foreign or identical files, and sweep parameters on another plan |
| T-CX486 | The questionnaire reaches every plan and connection with marked defaults, localizes default labels, and rejects missing or unknown answers |
| T-CX487 | Confirmation accepts only complete user-sent values; plan keys are deterministic; the plan store links runs and forgets them with their plan |
| T-CX488 | The guide adapter sends the fixed prompt and only text, file names and sample rates, wraps transport failures, and rejects an empty model name |
| T-CX489 | The service returns the questionnaire by default; asking for an unavailable model is `planner_not_configured`; a valid draft is returned as `model`; illegal JSON, validation failures and provider errors fall back to the questionnaire with the reason; the builder needs credentials and the enable flag |
| T-CX490 | The API serves health `guide`, drafts, questionnaire drafts, confirmation, plan lookup and run linking with the defined errors, and reports carry `test_plan` only for linked sweep and contextual runs |
| T-CX491 | CLI `guide draft`, `questionnaire` and `confirm` print the questionnaire, drafts and steps, and exit 2 for an unavailable model or incomplete confirmation |
| T-CX492 | The home page has the guide panel with the AI button hidden until health allows it; sweep and diagnosis pages load `guide.js`, show the plan banner and link runs; text is set without `innerHTML`; browser proof (manual, not in CI) with a scripted guide: AI draft and questionnaire paths, a prefilled sweep page, a linked report, no page error and no overflow at 390 px |
| T-CX493 | The 40 authored scenarios cover every plan, connection and the tagged edge cases, and each expected plan passes the validator; the harness scores offline with no model call and, in live mode, counts plan and parameter accuracy, number rejections and fallbacks |

T-CX494–T-CX497 are additive definitions for D058
(`CONTRACTS_V0_3_CONTEXTUAL.md` §30.1). They make no model call and must not
alter T-CX001–T-CX493 meanings.

| ID | Definition |
|----|------------|
| T-CX494 | Wording check 1.1 is `explain-validator-1.1`; ordinary English words (slightly, pieces, limitation, limited) pass, while whole banned and threshold words, plurals, and words next to Chinese characters or digits are rejected |
| T-CX495 | A negated "standard/标准" disclaimer passes only with 演示/demo in the sentence; "meets the standard", "not meeting the standard", 符合标准, 不符合标准, 未达标, a leading 行业标准, a disclaimer without demo, other banned words beside a disclaimer, and a second unnegated 标准 are rejected |
| T-CX496 | The rejection sink receives the check, detail and model text for validation failures and illegal output, nothing for a template request or an accepted draft; the result carries `validator_version` and no rejection data |
| T-CX497 | The acceptance harness writes `validator_version`, `rejection_detail` and `rejected_draft` per row and `rejection_details` in the summary; offline rows have none; no credential text is written; `review.md` has no trailing whitespace |

T-CX498–T-CX501 are additive definitions for D059
(`CONTRACTS_V0_3_CONTEXTUAL.md` §31.1). They make no model call and must not
alter T-CX001–T-CX497 meanings; T-CX488 and T-CX490 now expect prompt
`v0.3-s1-guide-1.1`.

| ID | Definition |
|----|------------|
| T-CX498 | The guide prompt is `v0.3-s1-guide-1.1` and states each D059 rule: the sweep generates its own signal and never asks for a test file, the sample rate is only for the sweep, the three connections and no default connection, the paired reference definition, the fields each plan uses, exact keys and no other text; the adapter still sends only text, file names and sample rates |
| T-CX499 | The rejection sink receives the check, detail and model text for invalid JSON, an extra parameter key (with its location) and a validation failure; nothing for an accepted draft or a questionnaire request; the result carries no rejection data |
| T-CX500 | The held-out scenarios match the frozen SHA-256 in both copies, number 20 with the D059 distribution, repeat no development text, quote their own text, and each expected plan passes the validator |
| T-CX501 | `guide_eval` runs the held-out set offline with no model call and full accuracy; rows and summary carry the case set, prompt version and rejection fields; a scripted live run records every rejection; no credential text or trailing whitespace is written |

T-CX503–T-CX512 are additive definitions for D060 phase A
(`CONTRACTS_V0_3_CONTEXTUAL.md` §32). They make no model call and must not
alter T-CX001–T-CX501 meanings. T-CX502 (a conditional D059 slot) is unused.

| ID | Definition |
|----|------------|
| T-CX503 | Level labels round-trip; sessions start with checked answers and parameters and deterministic ids; invalid answers, rates and round limits are rejected |
| T-CX504 | The validator rejects off-grid, unordered, too many, above-maximum and out-of-reach levels, uncited reasons, uncalled-for fixes, repeated tests, a second ask, actions while a test or question is open, actions after finishing, proposals with no rounds left or when the user cannot re-test, and each finish status whose condition does not hold |
| T-CX505 | Resolution needs a clean level within 3 dB below the onset (or the −36 dB floor), clean levels up to the stated maximum, a settled recorder for full-scale results, valid judged levels, or a verdict from a starting contextual run |
| T-CX506 | The rule policy starts with the default levels (capped), asks to re-test after an inconclusive start, tries fixes in order, asks about the recorder and then checks it, brackets onsets between, below and above tested levels, asks the maximum when all is clean, finishes on budget, and every step it takes passes the validator |
| T-CX507 | The sandbox's oracle onset matches the engine, and whole sessions with bracketing, noise, recorder gain and a blocked user end correctly with a summary |
| T-CX508 | The 30 development scenarios cover every tag and expected status; the harness runs selected scenarios offline with no model call and writes results and a summary without trailing whitespace |
| T-CX509 | The API starts sessions, returns the next step, accepts matching sweep runs and answers, rejects mismatched runs, bad answers, bad parameters and non-sweep plans, and returns 404 for unknown sessions |
| T-CX510 | CLI `session simulate` prints the steps, summary and correctness, emits JSON on request, and exits 2 for an unknown scenario |
| T-CX511 | The sweep page has the session panel and loads `session.js`, which sets text without `innerHTML` and links analysed runs; the script is served as JavaScript |
| T-CX512 | The 20 held-out session scenarios match the frozen SHA-256 in both copies and share no id with the development set; the recorded rule-policy acceptance (`rule_heldout/summary.json`) names the current policy and meets the 0.9 bar with no model call; sample held-out sessions still end correctly |

T-CX513–T-CX518 are additive definitions for D060 phase C
(`CONTRACTS_V0_3_CONTEXTUAL.md` §33). They make no network call.

| ID | Requirement |
| --- | --- |
| T-CX513 | The answer validator accepts grounded and declined answers and rejects each violation: sentence count, off-menu step, missing or unknown citation, identifiers in text, uncited numbers, standards wording, unsupported faults and hardware speculation |
| T-CX514 | The deterministic answer passes validation on every recorded case in both languages, declines hardware questions with a menu step, and is deterministic |
| T-CX515 | The adapter sends only language, question and packet; the template is the default; the model path needs credentials and `SIGNAL_DIAG_QA_MODEL`; illegal, rejected and failed model answers fall back with the reason recorded |
| T-CX516 | The question endpoints answer finished contextual and sweep runs, reject bad bodies (422), unknown runs (404) and an unavailable model (503); health reports `qa`; the Web UI loads `qa.js` after `explanation.js`, uses `textContent` and shows the box only when the model is available |
| T-CX517 | The 40 development questions are well formed (10 to decline); the offline harness writes results, summary and a 20-sample review without model calls or trailing whitespace; live mode counts fallbacks |
| T-CX518 | The 20 held-out questions match the frozen SHA-256 in both copies, share no id with the development set, and run through the offline harness with no model call |

T-CX519–T-CX521 are additive definitions for result-qa 1.1 (§33.1).

| ID | Requirement |
| --- | --- |
| T-CX519 | Q&A sentences that name a metric or rule, negate a fault, or cite the run for its verdict pass; sentences that assert a fault the cited items do not support are still rejected |
| T-CX520 | The offline review ends with a single newline; `heldout_2` is a registered case set; the check and prompt report versions 1.1 and the prompt carries the two new rules |
| T-CX521 | The 20 round-2 held-out questions match the frozen SHA-256 in both copies, share no id or question text with the development and first held-out sets, and run through the offline harness with no model call |

T-CX522–T-CX524 are additive definitions for result-qa 1.2 (§33.2).

| ID | Requirement |
| --- | --- |
| T-CX522 | Analysis and detection names after a fault word pass the Q&A fault check; an asserted unsupported fault and a step id used as a citation are still rejected |
| T-CX523 | The check and prompt report versions 1.2; the prompt forbids step ids in refs and banned wording even when denied; `heldout_3` is a registered case set |
| T-CX524 | The 20 round-3 held-out questions match the frozen SHA-256 in both copies, share no id or question text with earlier sets, and run through the offline harness with no model call |
