# S1 planner-ablation protocol revision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline-verified dev_2 study path with common request timing, consistent mode-specific oracles and fixed populations, ready for a separately authorized protocol seal.

**Architecture:** Add a separate `evaluation/planner_ablation/v2/` protocol and scorer; preserve dev_1 entry points and reproducer. App-owned study adapters accept encoded bytes and return one common terminal view. Evaluation owns population, timing validation, scoring and immutable identity, and never imports app composition.

**Tech Stack:** Existing Python >=3.11, Pydantic 2, NumPy, pytest/pytest-asyncio, Ruff and mypy; no new dependency.

**Spec:** `docs/superpowers/specs/2026-10-01-s1-planner-ablation-protocol-revision-design.md`, approved 2026-10-01.

**Status:** implementation plan for review; only this plan and the design approval metadata are changed by the current task.

## Global Constraints

- Study `study_s1_planner_ablation_dev_2`; scorer `signal_diag.planner_ablation_scoring` version `2.0.0-dev.1`; additive root `docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_2/`.
- Known development calibration inputs, seven source masters; no held-out, population-equivalence or model-stability claim.
- Two scored arms, `product_agent` and `fixed_pipeline`; modes `single_signal` and `paired_reference`. Real product requires `RealLLMPlanner`; all offline execution is harness-only, including RealLLMPlanner with an injected fake client.
- Nine unique single requests plus ten paired requests, three rounds, 114 slots including 57 product slots. Aliases never add scored units. Fixed populations U=7, C=6, G=4 remain subject to the design's independent offline label review before seal.
- Request interval is encoded bytes to complete terminal result with guidance; 120-second outer deadline. Fresh empty container per slot, sequential execution, no warm-up provider calls.
- Zero quality/usefulness/completion/upgrade/guidance loss; fixed dominance additionally needs >=20% and >=100 ms mean latency savings in every mode/round, no p95 or mean tool-action regression. Planner superiority uses quality only.
- Preserve frozen V0.2 §§1–64, dev_1 evidence, identities and seal, and historical contextual baseline. Keep D037 and HEAD v9.11 gates unchanged. Demonstration thresholds are not industry standards.
- No current authorization for CONTRACTS/TEST_PLAN edits, code/tests, fixtures, seal, RealLLM, product changes, commit or push. Tasks below are future work after their specified grant.
- Commit/push and real protocol seal each require separate authorization. Temporary test seals become allowed only under the later offline implementation grant.

## Review Focus

1. An invalid reference withheld in single mode must not change that request's oracle or create a second scored unit (Task 2).
2. Fixed decoding or guidance outside the timer can recreate apparent dominance while both arms produce correct answers (Task 3).
3. A real planner object using fake transport is still offline evidence; changing its arm label cannot make it scored product evidence (Tasks 3 and 7).
4. Globally equal rates can hide one mode/round regression; zero positive claims cannot make an arm appear safe (Task 4).
5. A valid manifest index can hide changed runner bytes, labels or WAV files; cancellation can leave background work affecting the next slot (Tasks 5 and 6).

## Baseline and file map

Source inspected: PR #17 merge `8962747ade7052584f3ddcd25e50ad42992273cc`. The local checkout used to write this plan is older (`9931875`); never execute this plan on that old checkout without first obtaining a clean checkout containing the merge and these two documents. Preserve unrelated user work.

At the inspected merge, the contextual contract ends at §19 and test definitions at T-CX288. §20 and T-CX289–302 below are **proposed allocations**, not registrations. Recheck the execution baseline for collisions and update this plan's mapping before editing definitions.

| Files to create/modify later | Responsibility |
|---|---|
| `docs/CONTRACTS_V0_3_CONTEXTUAL.md` §20; `docs/TEST_PLAN_V0_3_CONTEXTUAL.md` T-CX289–302 | Additive dev_2 definitions; preserve §19/dev_1 meaning |
| `src/signal_diag/evaluation/planner_ablation/v2/__init__.py`, `models.py` | Explicit v2 types and entry points; no retagging v1 objects |
| `.../v2/population.py`, `labels.py` | Canonical requests, aliases, slots, oracle review and U/C/G |
| `.../v2/timing.py`, `campaign.py` | Arm-neutral timing, deadline/failure accounting, schedule execution |
| `src/signal_diag/app/planner_ablation_v2_adapter.py` | Byte-to-terminal product and fixed study adapters, lifecycle/provenance |
| `.../v2/scoring.py`, `decision.py` | Counts, semantic support, mode/round comparison and prerequisites |
| `.../v2/sealing.py` | Full referenced-file verification and new-directory-only seal writes |
| `scripts/run_planner_ablation_v2.py`, `scripts/seal_planner_ablation_v2.py` | Explicit v2 entry points; no changes to dev_1 scripts |
| `tests/evaluation/planner_ablation/v2/test_{population,timing,scoring,decision,campaign,sealing,offline_acceptance}.py` | New behavioral coverage, with explicit test-ID mapping |
| `tests/app/test_planner_ablation_v2_adapter.py` | Real service integration and two-arm boundary/parity proof |
| `tests/test_architecture_boundaries.py` | Extend boundary checks to v2 and preserve non-study wiring |
| `docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_2/design_inputs.md`, `OFFLINE_ACCEPTANCE.md` | Unsealed proposal/rationales, test and readiness evidence |

All `.../v2/` entries expand to `src/signal_diag/evaluation/planner_ablation/v2/`. Test filenames listed in braces are separate files. Existing `planner_ablation/baseline.py` and `report_fields.py` are read-only reuse candidates; product composition, service, runtime, diagnosis, rule profiles and prompts are read-only dependencies.

## Stages and dependencies

| Stage | Tasks | Required authorization / stop |
|---|---|---|
| Plan | This document | Already authorized by design approval; stop for plan review |
| Definitions | 1 | Explicit definitions-only grant, or explicit offline implementation grant covering definitions; stop here if definitions-only |
| Offline implementation | 2–7 | Explicit grant for study-only code/tests and temporary fixtures; Task 1 must be complete |
| Seal preparation/review | Concrete labels, limits, implementation identity, manifest | Offline acceptance does not itself authorize creation of the real seal |
| Protocol seal | Outside these executable tasks | Separate grant against reviewed concrete inputs; commit identity must already exist under separate commit authorization |
| RealLLM campaign | Outside these executable tasks | Separate grant with exact seal digest and numerical request/token budget |

Dependency order: 1 → 2 → 3 → 4 → 5 → 6 → 7. Task 2 owns all shared model declarations; later tasks extend them with the fields named in their Interfaces blocks. Task 4 tests pure scoring/decision logic using explicitly synthetic fixtures until Task 6 supplies production verification; no fixture helper is exported as a production verified-input constructor. Task 6 verifies the final runner written in Task 5. Rerun its hash validation after any subsequent implementation edit. At each task boundary, leave a reviewable diff; do not commit automatically.

### Task 1: Register additive definitions without implementation

**Files:** modify only the two contextual definition documents above. Read design §§4–9, existing §19, service contextual submit/wait and `agent/diagnosis.py` v9.11 finish validation.

**Interfaces:** produces the following new definitions. They specify observable behavior, not a claim that a test already exists or passes.

| Proposed ID | Contract behavior | Owning task |
|---|---|---|
| T-CX289 | Request identity, equal-input oracle consistency and explicit aliases | 2 |
| T-CX290 | Unique schedule, source relations, rounds and deterministic paired order | 2 |
| T-CX291 | Fixed U/C/G, exact upgrade targets and truth-free request boundary | 2, 4 |
| T-CX292 | Shared timer includes decode/execute/guidance and excludes persistence | 3 |
| T-CX293 | Complete D037 service entry and two-arm report/gate matching | 3 |
| T-CX294 | Actual execution provenance; relabeled offline artifacts rejected | 3, 7 |
| T-CX295 | Scheduled quality/usefulness/completion and claim-level populations | 4 |
| T-CX296 | Same-run semantic support, zero-claim and zero-eligibility states | 4 |
| T-CX297 | Parameterized zero-loss decision, all mode/round gates and negative cases | 4 |
| T-CX298 | Typed infrastructure stop vs behavioral continuation, timeout/teardown | 5 |
| T-CX299 | Effective limits, bounded budget and actual resource telemetry | 5 |
| T-CX300 | Full input/code/seal binding, readonly verify, existing-target refusal | 6 |
| T-CX301 | Dev_1 reproducer and preserved assets; evaluation ↛ app | 6, 7 |
| T-CX302 | Full offline schedule acceptance, fail-on-call provider and review status | 7 |

- [ ] Recheck ID/section availability at the actual implementation base; record its commit and preserve existing definitions.
- [ ] Add §20 definitions for identity, request timing, populations, decision bands, provenance, failure accounting and staged authority. State that values are approved design choices awaiting a concrete seal, not already sealed values.
- [ ] Add T-CX289–302 descriptions with the exact ownership above. Define primary quality as exact outcome-plus-causal-set accuracy; outcome-only accuracy is secondary. Usefulness requires that exact oracle-compatible result and semantic support.
- [ ] Verify by reading the diff against each design requirement and run `git diff --check`. Expected: only additive definition changes, no executable files and no rewritten §19 or frozen V0.2 text. This is a documentation gate, not a pytest pass.

### Task 2: Define v2 population, oracle and execution boundary

**Files:** create v2 `__init__.py`, `models.py`, `population.py`, `labels.py`; `test_population.py`; unsealed `design_inputs.md`.

**Interfaces (frozen typed models; serialized fields reject unknown keys):**

- `ByteRequest`: mode, test bytes, optional paired reference bytes, channel=`mixdown`, segment policy=`full_signal`, normalized question. No scenario truth, oracle, U/C/G, filenames or predecoded signal ID. Adapters use constant filenames. Dev_2 rejects nominal mode and a supplied reference in single mode.
- `ScenarioDefinition`: logical/source/master IDs, input paths and hashes, per-mode `OracleLabel(outcome, exact_causal_faults)`, rationale and review record, upgrade target and U/C/G labels. Offline only.
- `RequestKey`: lowercase SHA-256 of canonical public request metadata; `SlotKey`: `(request_key, arm, round_index)`; `Schedule`: canonical requests, scenario aliases, expanded ordered slots and their digest.
- `StudyProtocolV2`: exact v2 identities, 3 rounds, 120-second deadline, timing version `encoded_bytes_to_terminal_v1`, zero-loss/20%/0.100-second bands, sole primary endpoint `quality`, runtime limits and binding references. Keep dev_1's model unchanged.
- `build_schedule(scenarios: Sequence[ScenarioDefinition], protocol: StudyProtocolV2) -> Schedule`; `validate_labels(scenarios: Sequence[ScenarioDefinition], schedule: Schedule) -> LabelReviewResult` in population/labels respectively. Review result carries errors and review provenance; no fabricated approval.

- [ ] Write `test_alias_collision_and_schedule`, `test_conflicting_equal_input_oracle_rejected`, `test_fixed_eligibility_and_truth_free_request` with assertions: `(single, paired, slots, product_slots) == (9, 10, 114, 57)`; single alias `163185980dc8f7a4` points to `825a759a0ea47bb7`; their paired keys differ; U/C/G counts `(7,6,4)`; changing a withheld reference cannot change a single key; injecting labels in `ByteRequest` fails.
- [ ] Run `pytest tests/evaluation/planner_ablation/v2/test_population.py -q`. Expected red before implementation: missing v2 population/types or failed invariants, never a network or credential failure.
- [ ] Implement canonical metadata as UTF-8 JSON, sorted keys, compact separators, no NaN; hash exact WAV bytes. Normalize question using Unicode NFC plus CRLF/CR to LF, without dropping whitespace or changing case. Execute this same normalized text on both arms. Sort request keys lexicographically, index keys and rounds from zero; product first iff `(i+r)%2 == 0`, round outermost. No arm-major reorder.
- [ ] Copy all ten oracle rows and source/master relationships from the approved design/source metadata into the unsealed proposal, disclosing prior-output exposure. Derive unique keys from actual bytes, not from expected counts. Define each upgrade target: harmonic attribution, added harmonic coverage for combined cases, or supported no-fault for natural controls; invalid reference has no resolution target and stays outside C.
- [ ] Reject unexpected key collisions, unequal labels on equal keys, empty/foreign populations, missing aliases or inconsistent source mappings. U/C/G use reviewed construction labels; no output-dependent membership. Label review disagreement stays a seal blocker, not an invitation to change gates.
- [ ] Rerun the focused command. Expected all pass, with no generated protocol seal or new WAV in the evidence root. Review the diff and leave it uncommitted absent a separate grant.

### Task 3: Implement matched byte adapters and common timing

**Files:** create v2 `timing.py`; app `planner_ablation_v2_adapter.py`; `test_timing.py`; `test_planner_ablation_v2_adapter.py`; extend v2 models.

**Interfaces:** `StudyTerminal` contains run/slot identity, status, typed failure cause, diagnosis, evidence/rule batches, task assessment and actual stimulus context needed for validation, guidance, action events, execution provenance and timing. `ArmSession` protocol has `async execute(request: ByteRequest) -> StudyTerminal` and `async aclose() -> None`. App provides product/fixed session builders; neither builder receives labels. `measure_request(session: ArmSession, request: ByteRequest, *, clock: Callable[[], float], deadline_s: float) -> StudyTerminal` owns outer events. Default clock is `time.perf_counter`; session creation and teardown are outside it.

- [ ] Add controlled-clock tests that independently advance decode, execution and guidance by 1, 2 and 3 units: outer elapsed must be 6 for both arms; a later serialization delay must leave it at 6. Test success, valid inconclusive and diagnosis-less failure. Missing/reversed markers, nonpositive/NaN/infinite durations and wrong timing versions must fail comparison validation.
- [ ] Add real `DiagnosisApplicationService` integration using ScriptedPlanner with a fail-on-call provider spy attached at the planner/client boundary. Make legacy submit/wait fail if called. Assert full contextual kwargs, `channel='mixdown'`, correct mode/reference/nominal fields and contextual waiter, plus a fresh empty repository for every slot.
- [ ] Run `pytest tests/evaluation/planner_ablation/v2/test_timing.py tests/app/test_planner_ablation_v2_adapter.py -q`; expect red for absent adapters or boundary violations.
- [ ] Implement the product session through the existing contextual service submit/wait. Do not override planner gates or product defaults. Fixed session decodes both byte inputs inside `execute`, applies the identical channel/full-segment/record/context construction, then invokes the unchanged study baseline and derives guidance before returning. Reject non-byte/predecoded request input. Reuse lower-level pure helpers; no service/runtime refactor.
- [ ] Record actual concrete planner/provider mode from session construction and execution, never from an input arm label. Scripted, fake-client RealLLMPlanner, synthetic fixtures and any offline session have immutable `harness_only` provenance. Require exact approved product type/prompt and verified online execution context for future scored ingestion; a class name string alone is insufficient. No offline test creates a scored campaign artifact.
- [ ] Add matching tests against actual `validate_finish_decision` with explicit `v9_11_mode_aware_no_fault_recovery`: both clipping Option C branches, natural-single inconclusive, paired harmonic/no-fault five-rule families, invalid reference, and no legacy-family substitution. Reconstruct finish inputs without altering refs or adding ground-truth claims. Confirm paired harmonic needs no extra `even_order` gate.
- [ ] Assert full guidance equality (summary, reason codes, unlockable modes, required inputs), plus diagnosis/failure and reference-field parity for equivalent deterministic terminals. For real runs, parity means schema/semantics parity, not demanding identical arm diagnoses. Emit observable phase markers only; disclose product preview/event overhead instead of subtracting it.
- [ ] Rerun the focused command, existing `test_matched_gates.py` and existing app adapter tests. Expected all pass. Keep dev_1 adapter and public product composition unchanged; review diff without an automatic commit.

### Task 4: Derive metrics and decisions from verified records

**Files:** create v2 `scoring.py`, `decision.py`, `test_scoring.py`, `test_decision.py`; extend models.

**Interfaces:** `VerifiedStudyV2` binds protocol/schedule/reviewed labels to verified identity (constructed only by Task 6). `calculate_metrics(study: VerifiedStudyV2, records: Sequence[StudyTerminal]) -> MetricTables` and `evaluate_prerequisites(study: VerifiedStudyV2, records: Sequence[StudyTerminal]) -> PrerequisiteReport`; `decide(protocol: StudyProtocolV2, metrics: MetricTables, prerequisites: PrerequisiteReport) -> DecisionResult`. Result carries machine candidate, eligible conclusion, reason codes and `review_status='pending'`. No caller-supplied safety/matching booleans or latency improvement ratio.

- [ ] Add tests for failure denominator `1/2`, correct inconclusive (quality/completion yes, usefulness no), incorrect no-fault (usefulness zero), exact combined causal sets, duplicate/missing/cross-round records, and zero claim populations. Assert per-arm/round denominators 9/10 and totals 27/30, never 114. A partial campaign may report descriptive counts but never enter the complete comparison path.
- [ ] Add tests where a claim cites existing but semantically wrong evidence/rules, references another run, or uses hidden source truth for a single harmonic attribution; safety must fail. Revalidate finish semantics with the unchanged v9.11 validator and independently validate reference run ownership; do not call a reference-existence check a semantic proof.
- [ ] Add fixed U/C/G tests: no guidance, failed execution and a lucky single answer leave denominators unchanged. Fully correct eligible paired results yield `S/7=6/7` and `S/6=1`; invalid-reference abstention is separate. G emission/correctness uses all 4 scheduled members. Zero C and zero emitted-guidance conditional populations return explicit not-evaluable, never 1. An already-met target cannot be reported as incremental gain.
- [ ] Add parameterized decision tests: all prerequisites + equal quality/completion + savings exactly `(0.20, 0.100)` in every mode/round permit dominance; either savings just below its boundary prevents it. One mode/round regression, worse p95, worse mean actions, zero positive claims, bad timing or incomplete campaign yields insufficient evidence. Planner quality gains must include >=1 extra correct key in the **same** mode in all 3 rounds; gains switching modes or utility-only gains do not qualify. Test the three exact conclusions independently.
- [ ] Run `pytest tests/evaluation/planner_ablation/v2/test_scoring.py tests/evaluation/planner_ablation/v2/test_decision.py -q`; expect red on missing code/failed invariants.
- [ ] Implement counts before rates; compute latency mean/median/nearest-rank p95/max including behavioral failures. Count actual tool events including repeats/failures, not unique tool names. Require evaluable positive claims and complete claim data in every arm/mode/round. Compute constrained regressions from metric tables and verify matching from schema, timing, pinned gate identity and matching-test evidence. Invalid prerequisites fail closed with reason codes.
- [ ] Implement exactly zero loss without epsilon; compare count/rational rates without rounding before thresholds. Across-round summary uses equal mode weighting and is descriptive only. Upgrade/guidance are round-level cross-mode endpoints and must not regress in any round. Keep machine decision distinct from later human review and product authority.
- [ ] Rerun both files and dev_1 `test_study_score.py`/`test_decision_language.py`. Expected all pass, with no dev_1 behavior change. Offline synthetic metric fixtures test decision logic without labeling a dry-run as a scored product campaign.

### Task 5: Execute the schedule offline, classify failures and expose limits

**Files:** create v2 `campaign.py`, `test_campaign.py`, `scripts/run_planner_ablation_v2.py`; extend models and app study adapter for study-only observers.

**Interfaces:** `run_schedule(schedule: Schedule, protocol: StudyProtocolV2, session_factory: Callable[[SlotKey], Awaitable[ArmSession]], *, execution_mode: Literal['offline','online']) -> CampaignRecord`; `inspect_limits(config: EffectiveConfiguration) -> BudgetAssessment`. Factory performs no slot analysis. Campaign owns preparation, measured dispatch, persistence and teardown; analysis is Task 3's responsibility. Record attempted/completed/failed/unstarted slot states against the unchanged full schedule.

- [ ] Add `test_behavior_failure_continues_without_retry`, `test_infrastructure_failure_stops_and_preserves_schedule`, `test_timeout_cancels_before_teardown`, `test_unknown_failure_blocks_campaign`, and `test_limits_and_telemetry_block_unknowns`. Assert one attempt per slot, no dynamic retry/reorder, behavioral failures retained in denominator, no request overlaps after timeout, and no positive conclusion after infrastructure stop. Include a synchronous fixed-path overrun: an async timeout alone must not allow a late result to be accepted as within deadline.
- [ ] Run `pytest tests/evaluation/planner_ablation/v2/test_campaign.py -q`; expect red before implementation.
- [ ] Implement sequential pair order from Task 2. Apply the outer deadline to all request work and independently check elapsed time at terminal readiness, so synchronous work cannot bypass it. Cancel and await cleanup before any later slot; record teardown duration/error separately. A timed-out worker that cannot be drained stops the campaign, never overlaps a replacement. Unknown causes are infrastructure failures. A known runtime diagnosis/repair-budget terminal is behavioral; auth/transport exhaustion, persistence failure and unresolved timeout stop. If product terminal data loses the underlying cause and observation cannot recover it without a product edit, fail closed and report a blocker.
- [ ] Capture actual planner/tool/rule/repair/transport attempts and available token usage through study-owned observation without changing return data, retries, payloads or defaults. Redact credentials and do not persist raw waveforms/FFT into provider traces. Effective configuration must match the pinned product path.
- [ ] Audit `AgentLimits` and planner transport configuration. At merge, defaults are tool=8, planner_retries=2, no_progress=2, rule_evaluations=4, knowledge_retrievals=4; planner calls use temperature 0, thinking disabled, and no explicit `max_tokens`, timeout or retry override. These source facts do **not** prove an effective request/token bound. Inspect the pinned installed SDK and verified provider specification later, without a connectivity test. Record a reasoned finite planner-call bound from runtime control flow, transport attempts per call, and input/output token bounds; never equate tool count with planner calls.
- [ ] Compute worst-case requests as `57 * planner_calls_per_slot_bound * transport_attempts_per_call_bound`, and token bounds including retry attempts and maximal prompts. If any limit or actual retry telemetry is unknown, output explicit blockers. Do not add provider limits or patch planner/composition within this plan. A need for such product changes must go back to separate design/authorization.
- [ ] Make the script require an explicit mode and output directory. Offline mode attaches fail-on-call provider instrumentation and writes only harness artifacts to a fresh temporary/test directory. Online mode is not executed by this plan and must reject missing verified seal, matching authorization reference or complete budget preflight before constructing a network client. An authorization-reference field is an audit link, not self-issued permission.
- [ ] Rerun campaign tests; expected pass with zero provider calls and no actual study seal. Missing production limits may remain a documented seal/execution blocker even though the rejection tests pass; never report this as full seal readiness.

### Task 6: Bind the complete protocol and preserve old evidence

**Files:** create v2 `sealing.py`, `test_sealing.py`, `scripts/seal_planner_ablation_v2.py`; extend models. All fixtures remain temporary.

**Interfaces:** `verify_manifest(path: Path, *, repository_root: Path, input_root: Path) -> VerifiedStudyV2`; `generate_seal(candidate: CandidateManifestV2, destination: Path) -> Path`. Candidate includes reviewed labels/rationales/U/C/G, source relations, exact schedule/aliases, limits/bands, environment, operator references and immutable code identity. `verify_manifest` is the production constructor for Task 4's verified input.

- [ ] Add tests mutating WAV bytes, question/channel policy, alias/oracle/U/C/G, prompt/profile/corpus, adapter/scorer, campaign/sealing script and dependency identity. Each must fail verification. Verify both the canonical manifest digest and actual referenced bytes; reject foreign v1/v2 identity and malformed/full-schema fields.
- [ ] Add tests that generation rejects existing populated **and empty** directories, verification cannot create files, success/failure verify preserves the entire input tree hashes, and candidate path traversal or a symlink escape cannot access outside the declared roots. A race creating the destination must not overwrite existing data.
- [ ] Run `pytest tests/evaluation/planner_ablation/v2/test_sealing.py -q`; expect red for missing verification/refusal behavior.
- [ ] Implement canonical serialization and explicit coverage of all runtime-loaded product/study code, both actual scripts, profiles/corpus and relevant dependencies; do not hash only an informal file shortlist. Bind the implementation commit independently of the later seal artifact commit. Recompute hashes against both the declared code commit and working bytes; reject dirty relevant code or a changed entry script. Unrelated documentation must not create a self-referential seal hash.
- [ ] Derive request hashes from verified inputs and reconstruct the frozen schedule; check labels/alias consistency, review records and full protocol. Require complete effective limits before a real candidate can become seal-ready. Preserve all 114 slot identities and execution order for later campaign verification.
- [ ] Provide separate `verify-only` and `generate` commands. Generation uses exclusive directory creation, no delete/replace path; it requires the later seal grant for the real evidence root. Verification recomputes referenced bindings, not just index checksums. Do not call generate against dev_1 under any mode.
- [ ] Rerun new sealing tests and existing `test_seal.py`, `test_seal_script_safety.py`, `test_protocol_seal_bundle.py`; expected all pass. Verify the dev_1 machine result using its own oracle/scorer and compare preserved source-tree hashes to the starting merged baseline; never feed its RealLLM outputs through dev_2 scoring.

### Task 7: Whole offline acceptance and handoff

**Files:** create `test_offline_acceptance.py`, extend architecture tests, write unsealed `OFFLINE_ACCEPTANCE.md` and finish `design_inputs.md` review records.

**Interfaces:** consume Tasks 2–6. Produce a requirements-to-tests report, concrete unresolved blockers and a candidate manifest description; no sealed bundle or accepted scientific conclusion.

- [ ] Add `test_complete_harness_schedule_has_no_provider_calls`: execute the entire 114-slot schedule through actual Scripted service and fixed adapters in temporary output, verify all four arm/mode paths, timing and population accounting. Spy must attach to the actual provider boundary and assert zero calls. Synthetic clocks are harness metadata, never RealLLM latency evidence.
- [ ] Add `test_relabelled_harness_bundle_is_not_scored_product`: take that real dry-run bundle, rewrite only arm/class labels, and assert provenance/verified-context rejection. Add a fake-client RealLLMPlanner variant. Altered stored provenance invalidates the bundle binding; do not claim hashes authenticate arbitrary maliciously fabricated artifacts.
- [ ] Add architecture/preservation assertions for evaluation ↛ app, unchanged public product builder/default, unchanged historical contextual baseline and dev_1 files. Run the new acceptance/architecture tests red before adding their final integration wiring; then rerun expecting pass.
- [ ] Have an independent offline reviewer check all ten proposed oracle rows, source/master mapping, U/C/G and targets against construction and gates, without treating either arm's answer as truth. Record reviewer/date/rationale/disagreements. Unresolved disagreement blocks seal; do not manufacture signoff or expand into a new campaign.
- [ ] Run `pytest tests/evaluation/planner_ablation tests/app/test_planner_ablation_adapter.py tests/app/test_planner_ablation_v2_adapter.py -q`, full `pytest`, `ruff check .`, `mypy src`, `pytest tests/test_architecture_boundaries.py -q`, and `git diff --check`. Require no required skip/xfail. Run wheel smoke if packaging changes; a release gate additionally requires clean CPython 3.11/3.12 checks. No live-model gate is invoked.
- [ ] Write `OFFLINE_ACCEPTANCE.md`: actual commands/results, every T-CX mapping, baseline and preservation hashes, offline execution identity, label review state, configuration/budget blockers, and exact future grant boundaries. Report unknown production constraints honestly; green tests proving refusal are not proof that a live run is ready.
- [ ] Stop. Present the reviewable offline diff and concrete seal prerequisites. Commit/push, creation of the real seal, RealLLM and any product changes still require their separate grants.

## Plan self-review and completion boundary

| Approved design | Coverage |
|---|---|
| §§1–3 scope and old evidence | Global constraints, Tasks 1/6/7 |
| §4 timing/lifecycle and attribution | Tasks 3/5; no post-hoc subtraction |
| §5 oracle, aliases and fixed U/C/G | Tasks 2/4/7; independent label review |
| §6 rounds/order/limits/failures | Tasks 2/5; unknown bounds block progression |
| §7 populations, safety and decisions | Task 4; mode/round negative tests |
| §8 versioning, architecture and binding | File map, Tasks 3/6/7 |
| §§9–10 offline acceptance and grants | Tasks 1–7 and stage table |

All five Review Focus items have owning tests. Interfaces distinguish truth-free execution from offline labels and verified scoring; the chosen v2 package avoids modifying the old validator or scorer. This plan does not certify that the current provider configuration can satisfy all approved prerequisites. That is an explicit offline discovery result with a fail-closed boundary, not permission to alter the product.

Current deliverable: this plan for review. Recommended execution method after a separate grant is native task-by-task implementation, with independent review before seal readiness is accepted; the shared types and provenance/timing flow benefit from one implementation owner. No implementation follows automatically from approval of this document.
