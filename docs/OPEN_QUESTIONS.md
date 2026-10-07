# Open Contract and Architecture Questions

**Status:** Active register
**Current open questions:** 0 open; 22 resolved (OQ-001–OQ-022)

Use this file only for concrete issues that may require changing an approved
contract or architectural boundary.

Each new entry must contain:

```text
ID:
Date:
Status: open / approved / rejected / superseded / blocked
Affected document and section:
Observed problem:
Why the current contract cannot represent a correct implementation:
Minimal proposed change:
Compatibility impact:
Test impact:
User decision:
```

An open entry does not authorize changing a frozen interface. After an explicit
decision, record the lasting outcome in `docs/DECISIONS.md` and update the
affected versioned contract through an approved revision.

---

## OQ-001 — Approve Phase 3 contract draft (§32–§40)

```text
ID: OQ-001
Date: 2026-08-28
Status: approved — revised §32–§40 frozen on 2026-08-28
Affected document and section: docs/CONTRACTS_V0_2.md §32–§40; AGENTS.md Phase 3 gate
Observed problem: Phase 3 public interfaces were drafted with contradictions involving evidence_refs, empty queries, batch/state representation, runtime DI, comparator semantics, multi-evidence mapping, architecture gates, Phase 2 constructor compatibility, and Phase 3 termination reasons/counters.
Why the current contract cannot represent a correct implementation: Before revision, implementation of rules/ and knowledge/ could not begin until contradictions were resolved and the Phase 3 freeze was explicitly accepted.
Minimal proposed change: The user reviewed and approved revised §32–§40 after the initial and follow-up blocking findings were addressed.
Compatibility impact: Additive Phase 3 packages and Agent extensions only; Phase 1–2 frozen surface unchanged except documented AgentLimits extension.
Test impact: Enables Phase 3 implementation once approved; T093+ defined in TEST_PLAN §21.
User decision: approved 2026-08-28 — §32–§40 are frozen and Phase 3 planning and implementation are authorized
```

---

## OQ-002 — Phase 3 required test IDs and completion gate

```text
ID: OQ-002
Date: 2026-08-28
Status: approved
Affected document and section: docs/TEST_PLAN_V0_2.md §21; tests/test_architecture_boundaries.py; AGENTS.md verification
Observed problem: TEST_PLAN_V0_2.md ended at T092 with no Phase 3 test IDs, completion gate, or architecture boundary migration plan.
Why the current contract cannot represent a correct implementation: Phase 3 completion cannot be declared against an undefined acceptance set; architecture tests still enforced Phase 1–2 "packages must not exist" gate.
Minimal proposed change: Added TEST_PLAN §21 (T093–T124) with Phase 3 completion gate; updated architecture boundary tests to Phase 3 expectations (rules/knowledge allowed after doc gate; dependency direction verified when packages exist; evaluation/app remain deferred).
Compatibility impact: Documentation and test gate migration only until T093+ are implemented.
Test impact: T093 architecture boundary migration; T094–T124 cover rules, knowledge, runtime, and S1 acceptance; Phase 1–2 tests remain required.
User decision: approved — architecture boundary migration tests included; OQ-001 approval authorizes implementation
```

---

## OQ-003 — S1 distortion rule profile thresholds

```text
ID: OQ-003
Date: 2026-08-28
Status: approved — exact demonstration profile approved on 2026-08-29
Affected document and section: docs/CONTRACTS_V0_2.md §33–§34; rules/profiles/
Observed problem: Contract names supported metric families and comparator PASS semantics but does not freeze demonstration threshold values for clipping_ratio, thd_percent, flat_top_detected, or related rules.
Why the current contract cannot represent a correct implementation: RuleEngine PASS/FAIL behavior for scripted S1 acceptance requires concrete profile values aligned with synthetic ground truth.
Minimal proposed change: Freeze profile_s1_distortion version 1.0.0-demo with clipping_detected eq false, clipping_ratio lte 0.01, flat_top_detected eq false, harmonic valid eq true, and thd_percent lte 5.0%; document all values as demonstration-only rather than industry standards.
Compatibility impact: Profile file content only; public RuleProfile and RuleEvaluation models unchanged.
Test impact: T098–T120 may use test-local profiles during TDD; T121–T124 and the Phase 3 completion gate require the approved production demonstration profile.
User decision: approved 2026-08-29 — use the exact 1.0.0-demo profile above; changing a comparator or threshold requires a new profile version
```

---

## OQ-004 — Rule and knowledge action limits

```text
ID: OQ-004
Date: 2026-08-28
Status: approved
Affected document and section: docs/CONTRACTS_V0_2.md §38.2; agent/policies.py AgentLimits
Observed problem: Phase 3 adds evaluate_rules and retrieve_knowledge runtime actions but did not freeze whether they share the Tool-call budget or have separate caps.
Why the current contract cannot represent a correct implementation: Termination and no-progress policy need finite limits before runtime integration is implemented.
Minimal proposed change: Extend AgentLimits additively with max_rule_evaluations=4 and max_knowledge_retrievals=4, separate from max_tool_calls. Frozen in §38.2.
Compatibility impact: Additive AgentLimits fields; Phase 2 defaults preserved for Tool-call limits.
Test impact: T117–T118 termination tests for rule/knowledge action exhaustion.
User decision: approved — independent budgets max_rule_evaluations=4, max_knowledge_retrievals=4
```

---

## OQ-005 — Untracked real_model_eval_output/ artifacts

```text
ID: OQ-005
Date: 2026-08-28
Status: approved
Affected document and section: repository hygiene; .gitignore; Phase 4 evaluation output layout
Observed problem: real_model_eval_output/ contains untracked JSON from Phase 2 real-model runs (index.json, s1-*.json).
Why the current contract cannot represent a correct implementation: Not a contract defect; affects whether evaluation artifacts are committed, gitignored, or relocated under a Phase 4 evaluation output path.
Minimal proposed change: Add real_model_eval_output/ to .gitignore and treat as local developer artifacts until Phase 4 defines versioned evaluation reports.
Compatibility impact: None on frozen contracts.
Test impact: None.
User decision: approved — gitignore local eval output
```

---

## OQ-006 — Preserve frozen v5 evidence while authorizing prompt v6 remediation

```text
ID: OQ-006
Date: 2026-08-30
Status: approved/resolved — additive v6 contract and Task 2–8 implementation approved on 2026-08-30
Affected document and section: docs/CONTRACTS_V0_2.md §50; docs/TEST_PLAN_V0_2.md §23 T184/T194; docs/DECISIONS.md D021; Phase 4.1 operational campaign identities
Observed problem: The immutable v5 development campaign at f9392c2 is completed/below_target. Its traces show that v5 appends policy to contradictory v4 examples, causing repeatable failures in D019 dual truth, combined-hypothesis coverage, inconclusive knowledge citation, and no-fault claim semantics. Frozen §50 and T184/T194 name and hash v5, so replacing v5 bytes or silently redirecting its campaign would invalidate recorded provenance.
Why the current contract cannot represent a correct implementation: §50 correctly represents the completed v5 attempt but provides no separate prompt/campaign identity for a second prompt-only development candidate. Correct remediation must preserve v5 and gate1 byte-for-byte while binding a new prompt version, hash, development benchmark ID, and conditional official benchmark ID.
Minimal proposed change: Keep §50 and T184–T195 unchanged; add §51 for v0.2-s1-planner-6, TEST_PLAN §24 T196–T200, and D022. Preserve existing phase4.1-development/official routes as v5 and add phase4.1-v6-development/official routes. Reuse only the v1.1.0 development split until v6 gate2 meets target; held-out remains unexecuted.
Compatibility impact: Additive prompt specification, private planner/config builders, and CLI campaign choices only. No public PlannerModel, AgentDecision, PlannerContext, Runtime, DSP, rule, knowledge, evaluation model, scorer, target, or report schema change. v4/v5 reproducibility and all committed bundles remain intact.
Test impact: Add T196–T200 for v4/v5 immutability, v6 identity and semantic coherence, no leakage and traceability, additive campaign scheduling, and the cumulative gate. T001–T195 remain required and unchanged.
User decision: approved OQ-006, CONTRACTS §51, TEST_PLAN §24/T196–T200, and D022 on 2026-08-30; Task 2–8 implementation is authorized, while real-model held-out execution remains gated by a v6 development completed/meets_target result
```

---

## OQ-007 — Correct evaluation integrity before authorizing planner v7

```text
ID: OQ-007
Date: 2026-08-30
Status: resolved — revised integrity design approved; Task 1 documentation freeze authorized, Tasks 2–10 not authorized
Affected document and section: docs/CONTRACTS_V0_2.md §§42, 50–51; docs/TEST_PLAN_V0_2.md §§22–24 T125–T200; docs/DECISIONS.md D019, D021–D022; Phase 4.2 dataset/prompt/campaign identities
Observed problem: The immutable v6 development campaign at aefccba/808f653 is completed/below_target. Its remaining claim-purity and clipping/harmonic errors are real, but the first v7 draft incorrectly classified them as prompt-only. Initial PlannerContext values expose semantic case labels through signal IDs such as sig_eval_v11_dev_invalid_noise_01. Some v1.1.0 cases have identical visible request/metadata but disjoint acceptable first Tools. Combined-case fairness is established by a matched clipping-only control that is correctly hidden from the Agent, so the current third-harmonic fixture does not give the planner the counterfactual needed to distinguish clipping-induced harmonics from an independently injected cause. Separately, official preflight returns when benchmark_manifest.json is missing, skipping identity comparison.
Why the current contract cannot represent a correct implementation: A prompt-only v7 on v1.1.0 could learn semantic signal IDs or hidden development labels and still satisfy deterministic prompt tests, while a non-leaking planner cannot meet all case-specific first-Tool and latent-cause expectations from the information it receives. Section 51 also has no identity for an integrity-corrected dataset/campaign and does not require a complete development provenance bundle.
Minimal proposed change: Keep §§41–§51, T125–T200, v4/v5/v6 prompts/routes, and every committed bundle unchanged. Add §52 for dataset s1-distortion-synthetic 1.2.0, deterministic opaque v1.2 Agent signal IDs, Planner-visible first-Tool fairness, single-signal combined identifiability via reportable even-order harmonic Evidence under symmetric synthetic clipping, coherent prompt v0.2-s1-planner-7, and strict official provenance. Add TEST_PLAN §25 T201–T208 and D023. Add canonical phase4.2-v7-development/official routes and benchmark IDs bench_phase4_2_dev_v7_v12_gate3 / bench_official_s1_v12_planner7_gate3. Keep v1.1.0 held-out unexecuted and do not use it for Phase 4.2 acceptance. Targets, public Agent/Runtime/DSP/Tool/rule/knowledge/scoring/report contracts, provider, and model remain unchanged.
Compatibility impact: Additive v1.2 manifest, private optional signal-ID materialization, private v7 planner/config/campaign builders, stricter shared official-bundle validation, and deterministic tests. Historical default materialization and all v4/v5/v6 identities remain reproducible. RealLLMPlanner becomes v7 only after the deterministic gate; a private v6 planner preserves historical campaigns.
Test impact: Add T201–T208 for legacy identity, outbound value-level leakage, v1.2 freshness/request fairness, real-DSP combined identifiability, coherent v7 semantics, product-boundary traces, canonical campaign/provenance validation, and the cumulative gate. T001–T200 remain required and unchanged.
User decision: approved revised OQ-007, CONTRACTS §52, TEST_PLAN §25/T201–T208, and D023 on 2026-08-30; authorized Task 1 documentation freeze and local commit only; Tasks 2–10, code implementation, real-model development execution, and every held-out run remain unauthorized
```

---

## OQ-008 — Authorize one final prompt-only planner calibration

```text
ID: OQ-008
Date: 2026-08-30
Status: approved/resolved — written Phase 4.3 design approved; design/test contract frozen; implementation not authorized
Affected document and section: docs/CONTRACTS_V0_2.md §53; docs/TEST_PLAN_V0_2.md §26 T209–T215; docs/DECISIONS.md D024; Phase 4.3 prompt and campaign identities
Observed problem: The integrity-corrected v7 development campaign is completed/below_target. Failures are stable: clean and harmonic cases overuse spectrum/F0, harmonic cases choose spectrum first, the combined case stops after clipping, the noise case omits required knowledge in four of five runs, and all initial hypothesis lists are empty.
Why the current contract cannot represent a correct implementation: §52 freezes v7 and its one-shot development identity. It provides no new identity or semantic contract for another candidate, and silently replacing or rerunning v7 would invalidate provenance. Further prompt-only attempts also need an explicit terminal condition to prevent endless benchmark-driven prompt iteration.
Minimal proposed change: Preserve §§41–§52, T001–T208, dataset 1.2.0, Runtime, PlannerContext, DSP/Tools/rules/knowledge, scoring, targets, provider/model, and every historical asset. Add §53, T209–T215, and D024 for one complete v0.2-s1-planner-8 prompt, explicit viable hypotheses, minimal dynamic Tool use, combined continuation, invalid-result knowledge handling, canonical phase4.3-v8-development/official identities, and strict one-shot gates. A v8 development miss closes the prompt-only route and requires a new model-vs-PlannerContext decision.
Compatibility impact: Additive prompt, private planner/config/campaign bindings, tests, and optional evaluation bundles only. No public interface or deterministic numerical behavior changes.
Test impact: Add deterministic T209–T215. Existing T001–T208 and all historical assets remain required and unchanged. Real-model development/official gates remain outside CI.
User decision: approved the complete written Phase 4.3 design on 2026-08-30; §53, §26/T209–T215, D024, and this OQ resolution are frozen as design authority only; implementation, model execution, held-out access, Phase 5, push, and merge remain unauthorized pending a detailed plan and separate instruction
```

---

## OQ-009 — Correct Phase 4.3 request scope and invalid-Evidence scoring

```text
ID: OQ-009
Date: 2026-08-30
Status: approved/resolved — written Phase 4.3.1 design and additive contract/test correction approved; implementation not authorized
Affected document and section: docs/CONTRACTS_V0_2.md §54; docs/TEST_PLAN_V0_2.md §27 T216–T223; docs/DECISIONS.md D025; Phase 4.3.1 prompt, scoring-policy, and campaign identities
Observed problem: The immutable v8 development campaign is completed/below_target. Its remaining misses are confounded by two deterministic conformance defects. T210 globally prohibited clipping-only finish even though §53 permits symptom-specific request scope, causing all ten clipping runs to continue into unnecessary harmonic analysis. Separately, the legacy scoring proxy excludes structured Evidence from invalid Tool observations and therefore can score the contract-required invalid Evidence -> NOT_APPLICABLE rule transition as premature or inappropriate. V8 also allowed negative prose to carry a positive causal fault_type and over-attributed clipping-generated odd harmonics as an independent harmonic cause.
Why the current contract cannot represent a correct implementation: §53 and D024 close the prompt-only route after v8 and freeze legacy scoring, so silently modifying v8, reusing gate4, or changing scorer behavior globally would violate provenance. At the same time, moving directly to a new model or PlannerContext would treat a known test/scoring non-conformance as product-model evidence. A correct, reproducible correction needs independent prompt, scoring-policy, configuration, and campaign identities while preserving all historical behavior.
Minimal proposed change: Preserve v4–v8 and every committed bundle. Add §54, T216–T223, and D025 for one coherent v0.2-s1-planner-8.1 compliance prompt; request-scoped hypotheses; affirmative-only causal claims; clipping attribution that requires reportable order-2 Evidence for an independent harmonic cause; internal scoring policy signal_diag.scoring 2.0.0 selected through existing BenchmarkConfig.sdk_versions; canonical phase4.3.1-v8.1 development/official campaigns; and strict one-shot gates. The scoring-policy correction recognizes invalid/not-applicable structured Evidence as valid input for a NOT_APPLICABLE rule without changing public models or other scoring formulas.
Compatibility impact: Additive private prompt/planner/config/campaign bindings and internal versioned scorer dispatch only. Public Planner, Runtime, DiagnosisClaim, evaluation, score, report, DSP, Tool, RuleEngine, knowledge, dataset, target, provider, and model contracts remain unchanged. Legacy configurations dispatch to legacy scoring and historical fingerprints, traces, and bundles remain reproducible.
Test impact: Add deterministic T216–T223. T001–T215 and all historical assets remain required. Real-model development and official campaigns remain outside CI and separately gated.
User decision: approved the complete written Phase 4.3.1 design on 2026-08-30; §54, §27/T216–T223, D025, and this OQ resolution are frozen as design/test authority only; implementation, model execution, held-out access, Phase 5, push, and merge remain unauthorized pending a detailed plan and separate instruction
```

---

## OQ-010 — Freeze the written Phase 5 presentation contract

```text
ID: OQ-010
Date: 2026-08-31
Status: resolved — approved and frozen
Affected document and section: docs/superpowers/specs/2026-08-31-phase5-presentation-engineering-design.md; docs/CONTRACTS_V0_2.md §§55–§64; docs/TEST_PLAN_V0_2.md §28 T224–T285; docs/DECISIONS.md D026–D030
Observed problem: Architecture §15 and D012/D016 require WAV, CLI/API/UI, actual Agent trace, reporting, evaluation presentation, and a demonstrable Demo, but CONTRACTS §29 deliberately left every Phase 5 interface unfrozen.
Why the current contract cannot represent a correct implementation: Without exact WAV bounds, application lifecycle, service boundary, trace bridge, report/API/CLI/UI schemas, security semantics, and deterministic/real acceptance states, independent implementations could duplicate diagnosis logic, leak evaluation truth, expose unsafe payloads, or claim completion without a real product path.
Minimal proposed change: Approve the complete Phase 5 written specification, additive §§55–§64, T224–T285, and D026–D030. The selected design uses a shared DiagnosisApplicationService, bounded local polling jobs, strict integer-PCM WAV ingestion, native Web UI, canonical JSON/self-contained HTML reports, a checksum-linked accepted evaluation summary, and separate presentation_harness_accepted / real_demo_completed gates.
Compatibility impact: Additive signal WAV loader, generic evaluation trace helper, app package, optional Web/LLM dependencies, console/API/UI/report surfaces, package assets, and CI only. Frozen Phase 1–4.3.1 numerical, Agent, scoring, target, prompt, dataset, and historical bundle behavior remains unchanged.
Test impact: Adds deterministic T224–T285 and non-CI P5-R001–P5-R003. T001–T223 remain required and unchanged.
User decision: approved OQ-010, the complete Phase 5 written specification, Contracts §§55–§64, Test Plan §28 T224–T285, and D026–D030 on 2026-08-31; authorized Superpowers writing-plans only; source/test implementation, model execution, push, merge, worktree deletion, and build/ cleanup remain unauthorized pending the completed plan and a separate explicit execution choice
```

---

## OQ-011 — Replace hosted CI with local dual-version clean-environment verification

```text
ID: OQ-011
Date: 2026-08-31
Status: resolved — approved and frozen
Affected document and section: docs/CONTRACTS_V0_2.md §64; docs/TEST_PLAN_V0_2.md §28 T284–T285 and acceptance states; docs/DECISIONS.md D030/D031; docs/superpowers/specs/2026-08-31-phase5-presentation-engineering-design.md §§15–16
Observed problem: presentation_harness_accepted currently requires hosted GitHub Actions Python 3.11/3.12 jobs. Push and hosted CI remain unauthorized, so an otherwise complete local deterministic harness cannot close the dual-interpreter gate.
Why the current contract cannot represent a correct implementation: Treating an unauthorized remote workflow as a mandatory acceptance input blocks the frozen dual-version requirement without reducing any other T001–T285, Ruff, mypy, architecture, wheel, clean-install, or diff-check duty. Silent omission of 3.11 would lower the gate; waiting on push would couple acceptance to an unauthorized integration action.
Minimal proposed change: Keep every other Phase 5 gate. Redefine the dual-interpreter input as a committed, secret-free local verifier that creates a fresh venv for CPython 3.11 and for CPython 3.12, installs .[app,llm,dev], and runs the same full pytest / Ruff / mypy / wheel-smoke commands in each environment, plus one repository git diff --check 36ae7c9..HEAD. Hosted GitHub Actions may remain as optional automation and is not required for presentation_harness_accepted.
Compatibility impact: Additive process/test amendment only. No product API, DSP, Runtime, prompt, dataset, scoring, target, or historical bundle change.
Test impact: Retarget T284/T285 from hosted-job success to the local dual-version verifier. T001–T283 and P5-R001–P5-R003 semantics are unchanged. Zero skip/xfail remains required.
User decision: approved the Phase 5 local dual-version acceptance revision on 2026-08-31; freeze written contracts and the test plan first; then implement and run the local 3.11/3.12 clean-environment verifier; do not push, merge, or run a real model
```

---

## OQ-012 — External WAV pilot blocked on harmonic alpha and SMARD host policy

```text
ID: OQ-012
Date: 2026-09-01
Status: resolved — pilot v4 alpha selection passed (alpha=0.50, transform 1.1.0); Task 11 materialization and validation gate complete (commit 7993f0c; gate report docs/evaluations/v0_2_external_wav/validation/validation_gate_report.md)
Affected document and section: docs/superpowers/specs/2026-09-01-v0-2-real-world-validation-design.md §§5.1, 9.1, 9.4; docs/superpowers/specs/2026-09-01-v0-2-external-harmonic-transform-amendment.md; docs/EXTERNAL_VALIDATION_CONTRACTS_V0_2.md EV-C010–EV-C010B; docs/evaluations/v0_2_external_wav/protocol/source_catalog.json 1.0.2; src/signal_diag/evaluation/external/source.py approved-host policy; Task 11 pilot artifacts (source_decision_record.md, validation/pilot_failure_report.json, validation/pilot_failure_report_v2.json, validation/pilot_failure_report_v3.json, validation/pilot_success_report_v4.json)
Observed problem: Task 11 Phase B/C pilot v1 acquired 12 approved dev/validation sources (~728.5 MiB) but stopped at the validation gate with alpha_selection=failed on stepped-sinus SMARD masters. User approved OQ-012 options 1+2 (not option 3) on 2026-09-01. Pilot v2 formalized shares01.portal.aau.dk as the SMARD production download host, re-scanned SMARD cfg 0010 for harmonic-signal and other periodic material classes (harm_sinus_48kHz, sinus_tones_48kHz, exp_swept_sinus_10Hz_24kHz), and applied the frozen clean-master gate independently to each candidate window. Result: harm_sinus captures fail the clean gate (natural THD 141–356%, reportable order-2 present); 42 eligible periodic windows remain across sinus_tones and exp_swept_sinus (clean THD 0.004–0.28%, valid F0, no flat-top/clipping), but no alpha in {0.10, 0.15, 0.20} produces THD > 5% without flat-top/clipping while keeping F0 valid and a reportable order-2 component under signal_diag.external_reference 1.0.0 and transform identity signal_diag.external_transform 1.0.0. Global clipping q=0.03 would still select successfully on validation masters. Cases materialized: 0/14 development + 0/10 validation; final_external_test not accessed; no real model calls. Pilot v3 (OQ-012 option 3, commit 52fc82a): transform 1.1.0 implemented per amendment; synthetic sine fixtures pass alpha selection at alpha=0.10; real SMARD low-amplitude sinus_tones validation master (master_val_01 ch5, clean THD 0.022%, valid F0) fails all frozen alphas — alpha 0.10 triggers flat-top (THD 0.30%); alpha 0.15–0.20 avoid flat-top/clipping but THD remains 0.44–0.59% (< 5% demo threshold) with reportable order-2 present; extrapolation indicates alpha ~0.9 would be needed to exceed 5% THD, outside frozen candidate set {0.10, 0.15, 0.20}. Cases materialized: still 0/14 + 0/10; final_external_test not accessed; no real model calls.
Why the current contract cannot represent a correct implementation: EV-C010 and design §9.4 freeze alpha candidates and the validation rule (smallest global alpha exceeding 5% demo THD on every eligible validation master without clipping). Pilot v2 evidence shows no SMARD cfg 0010 periodic material class in the approved scan set can satisfy that rule under the frozen even-order nonlinearity 1.0.0. Pilot v3 evidence shows transform 1.1.0 (amplitude-normalized even-order injection) also cannot satisfy that rule on real SMARD low-amplitude masters despite passing on synthetic fixtures. Proceeding would require fabricating harmonic/combined strong_ground_truth cases, expanding frozen alpha candidates, adjusting post_gain, or adopting a non-SMARD B-master source.
Minimal proposed change: Preserve transform 1.0.0/1.1.0 and v1/v2/v3 failure reports. Pilot v4 under EV-C010B expanded alpha set selected alpha=0.50 on eligible SMARD validation master `master_val_01` (sinus_tones ch10, frames 320000–336000). Proceed toward 14+10 materialization only after all remaining Task 11 gates pass; do not access final_external_test or run real models without separate authorization.
Compatibility impact: Host-only approval (option 1) remains sealed in catalog 1.0.2. EV-C010B alpha expansion applies only to transform 1.1.0; transform 1.0.0 alpha set and v1/v2/v3 failure reports remain frozen. external_reference 1.0.0 and profile_s1_distortion thresholds unchanged.
Test impact: EV-T027A–EV-T027G cover transform 1.1.0 and expanded alpha selection. Task 11 alpha stop gate cleared by pilot v4; case materialization and Step 5+ remain gated on remaining Task 11 checks.
User decision history:
- 2026-09-01: OQ-012 approved with options 1+2. `shares01.portal.aau.dk` approved as SMARD production download host. Pilot v2 executed; alpha gate failed under transform 1.0.0; OQ-012 reopened.
- 2026-09-01: OQ-012 option 3 approved — authorize additive amplitude-normalized harmonic transform identity 1.1.0, design amendment, TDD implementation, and development-pilot re-run. Do not overwrite v1/v2 failure evidence; do not access final_external_test or run real models.
- 2026-09-01: Pilot v3 executed under transform 1.1.0; alpha gate failed on real SMARD low-amplitude validation master (THD max ~0.59% at alpha=0.20); OQ-012 reopened. Failure report: docs/evaluations/v0_2_external_wav/validation/pilot_failure_report_v3.json.
- 2026-09-01: OQ-012 option 1 approved — bounded alpha-candidate amendment under external transform 1.1.0 only. Candidate set exactly {0.10, 0.15, 0.20, 0.25, 0.50, 0.75, 1.00}. All other transform, post-gain, attenuation, reference-analysis, clean-master, THD, F0, order-2, clipping and flat-top rules remain frozen. Select the smallest alpha passing every eligible validation master. Run development/validation pilot v4 only. If no candidate through 1.00 passes, preserve a v4 failure report and stop. No final-test access, case materialization before the gate, or real-model calls are authorized.
- 2026-09-01: Pilot v4 executed under transform 1.1.0 with EV-C010B expanded alpha set on 42 eligible SMARD periodic windows; validation master `master_val_01` (sinus_tones_48kHz_ch10_ULA_2B, clean THD 0.0037%). Alpha selection passed at alpha=0.50 (candidates 0.10–0.25 failed THD > 5% gate). Success report: docs/evaluations/v0_2_external_wav/validation/pilot_success_report_v4.json. Cases materialized: 0/14 + 0/10 pending Task 11 Step 5 execution; final_external_test not accessed; no real model calls.
- 2026-09-01: Task 11 Step 5 complete — materialized 14 development + 10 validation cases under frozen transform 1.1.0, alpha=0.50, q=0.03, post_gain=0.8. Manifests: development/study_v0_2_external_wav_dev_1/, validation/study_v0_2_external_wav_validation_1/. Deterministic gates passed; no final_external_test access; no real model calls.
- 2026-09-01: Task 11 Step 8 validation gate stop — OQ-012 resolved. Pilot v4 alpha gate (EV-C010B, transform 1.1.0, alpha=0.50) and SMARD host policy (shares01.portal.aau.dk) satisfied the original blockers. Materialization commit 7993f0c; gate report validation/validation_gate_report.md. External pytest 128/128 passed; final_external_test not accessed; no real model calls. Task 12 requires separate final-data authorization.
```

---

## OQ-013 — Live product planner identity vs frozen V0.2 §§55/59

```text
ID: OQ-013
Date: 2026-09-29
Status: resolved — hygiene (2026-09-29)
Disposition: D032, D034, D035; AGENTS.md HEAD vs anchor; CONTRACTS_V0_3 §10 / §15
Observed problem: Frozen Phase 5 text pins the public product planner at DeepSeek / deepseek-v4-flash / v0.2-s1-planner-8.1. HEAD build_product_service and public RealLLMPlanner use v0.3-s1-planner-9.11 with causal policy v9_11_mode_aware_no_fault_recovery; phase4_certified_default is false.
Why the current contract cannot represent a correct implementation: Reading only CONTRACTS_V0_2.md, a reviewer expects the accepted v8.1 product path. HEAD intentionally runs the V0.3 contextual product identity on the same entrypoints (submit_wav / submit_synthetic), so the frozen sections no longer describe the live default.
Minimal proposed change: Keep frozen §§1–64 byte-stable. Document in AGENTS.md and docs/README.md that V0.2 acceptance is anchored at b48790c / ff16e2a (v8.1), while HEAD live product is v9.11 under CONTRACTS_V0_3_CONTEXTUAL.md §15. Amend CONTRACTS_V0_3 §10 header text to name v9.11 as current product identity (historical 9.9 remains immutable). Do not rewrite sealed bundles or restore ScriptedPlanner fallback.
Compatibility impact: Documentation and additive V0.3 contract header hygiene only until a separate design decides whether single_signal must regain v8.1 semantics.
Test impact: None for sealed T001–T285 identities. Focused tests already lock PROMPT_VERSION == v0.3-s1-planner-9.11 and phase4_certified_default is False.
User decision: hygiene path approved 2026-09-29; product-behavior resolution remains deferred pending a separate design
Follow-up (2026-10-03): product-behavior path C approved as D039 —
keep v9.11 gates; add deterministic single-file `observed_facts` on
`context_guidance` per
docs/superpowers/specs/2026-10-03-single-file-observed-facts-design.md.
Does not restore v8.1 harmonic supported_fault. Implementation requires a
separate grant (contracts §17, T-CX319+, app code, code-identity row).
Hygiene disposition (D032/D034/D035) unchanged.
```

---

## OQ-014 — Shared clipping_mechanism vs ARCH §17 S1-CLIP-SUBFS

```text
ID: OQ-014
Date: 2026-09-29
Status: resolved — Option C (2026-09-29)
Disposition: D036; CONTRACTS_V0_3_CONTEXTUAL.md §16; T-CX263; tests/agent/test_oq014_single_signal_flat_top_clipping.py
Design: docs/superpowers/specs/2026-09-29-oq014-clipping-mechanism-semantics-design.md
Plan: docs/superpowers/plans/2026-09-29-oq014-option-c-single-signal-clipping.md
Resolution: Keep strict DSP clipping_mechanism. On single_signal only, supported_fault clipping accepts clipping_mechanism=true or flat_top_detected=true (valid Evidence) plus substantial legacy clipping-rule FAIL. Contextual modes unchanged.
User decision: OQ-014: Option C
```

---

## OQ-015 — Automatic rule closure vs §38.3 / D021

```text
ID: OQ-015
Date: 2026-09-29
Status: resolved — hygiene (2026-09-29)
Disposition: D033; CONTRACTS_V0_3_CONTEXTUAL.md §10.1–§10.2
Observed problem: Phase 3 freeze and D021 require planner-owned EvaluateRulesDecision; runtime must not force rules before finish. Product policies v9.7+ create rule batches automatically from tool observations and reject planner evaluate_rules.
Why the current contract cannot represent a correct implementation: Frozen V0.2 text and live V0.3 product policy disagree on who owns rule evaluation.
Minimal proposed change: Record the V0.3 design authorization (v9.7 deterministic rule closure) as D033. Keep CONTRACTS_V0_2 §38.3 frozen; state in CONTRACTS_V0_3 that automatic closure supersedes planner-owned evaluate_rules for product policies >= v9.7.
Compatibility impact: Documentation / decision register only for this hygiene pass.
Test impact: Existing T-CX coverage for automatic closure remains authoritative for V0.3.
User decision: acknowledged 2026-09-29 — V0.3 automatic closure supersedes §38.3 for live product policies ≥ v9.7; frozen V0.2 text unchanged
```

---

## OQ-016 — Fifth tool always advertised on PlannerContext

```text
ID: OQ-016
Date: 2026-09-29
Status: resolved — hygiene (2026-09-29)
Disposition: CONTRACTS_V0_3_CONTEXTUAL.md §6
Observed problem: Frozen V0.2 lists exactly four S1 tools. get_tool_descriptors() always includes analyze_contextual_distortion, so every planner context (including single_signal) sees five tools.
Why the current contract cannot represent a correct implementation: Frozen tool inventory no longer matches the live descriptor list.
Minimal proposed change: Keep §§16/23 frozen. Document the fifth tool under CONTRACTS_V0_3. Optionally (separate design) filter descriptors by mode so single_signal sees four tools.
Compatibility impact: Hygiene disclosure now; mode-filtered descriptors would be B-class.
Test impact: None for hygiene-only.
User decision: hygiene disclosure approved 2026-09-29; mode-filtered descriptors not authorized
```

---

## OQ-017 — T285 allowlist exempts mutated V0.2 cores

```text
ID: OQ-017
Date: 2026-09-29
Status: resolved — hygiene (2026-09-29)
Disposition: AGENTS.md T285 note; TEST_PLAN_V0_2.md Checkpoint AC note
Observed problem: T285 was the Phase 5 freeze detector against baseline 36ae7c9. It now allowlists agent/planner.py, agent/runtime.py, agent/diagnosis.py, dsp/clipping.py, dsp/harmonics.py, tools/*, app/composition.py, and related paths. Green T285 no longer proves those files match Phase 4.3.1.
Why the current contract cannot represent a correct implementation: Reviewers may treat a green T285 as V0.2 behavioral preservation. The allowlist only records authorized V0.3 edits.
Minimal proposed change: Document in AGENTS.md / TEST_PLAN notes that T285 allowlist means “V0.3 authorized mutation,” not “byte-identical to 36ae7c9.” A future design may split a V0.2-preservation suite from a V0.3 suite.
Compatibility impact: Documentation only.
Test impact: None in this pass.
User decision: documentation clarification approved 2026-09-29
```

---

## OQ-018 — Undocumented EV-C026+ IDs and package version label

```text
ID: OQ-018
Date: 2026-09-29
Status: resolved — hygiene (2026-09-29)
Disposition: EXTERNAL_VALIDATION_CONTRACTS_V0_2.md §11 historical EV-C026+; README package-label note
Observed problem: Reports and code comments cite EV-C026–EV-C029 (and draft EV-C036, superseded/never executed) without normative contract entries. Package metadata remains 0.2.0 while live HEAD behavior is V0.3-identity; bumping the package version would collide with external preservation expectations around tag v0.2.0 / wheel identity history.
Why the current contract cannot represent a correct implementation: Contract ID space and distribution version no longer match the story told by V0.3 reports.
Minimal proposed change: Either append EV-C026+ as historical/superseded entries in EXTERNAL_VALIDATION_CONTRACTS_V0_2.md, or explicitly mark them report-only. Keep pyproject 0.2.0 until a release design chooses 0.3.0 without breaking tag/object preservation checks; disclose the version/label split in README.
Compatibility impact: Docs only for this pass.
Test impact: Do not change v0.2.0 tag preservation tests.
User decision: append historical EV-C026+ entries + keep pyproject 0.2.0 with README disclosure (2026-09-29)
```

---

## OQ-019 — S1 planner-ablation utility study (study-shape freeze)

```text
ID: OQ-019
Date: 2026-09-30
Status: resolved — study shape approved (2026-09-30); `dev_2` stopped before sealing (2026-10-06, D046)
Disposition: D038; docs/superpowers/specs/2026-09-30-s1-planner-ablation-utility-study-design.md (revised)
Affected document and section: AGENTS.md scope gates; CONTRACTS_V0_3_CONTEXTUAL.md §11 / §16 / §17; evaluation/contextual/; app/contextual_campaign.py; docs/evaluations/v0_3/contextual/V9_11_CONTEXTUAL_VALIDATION_ACCEPTANCE_REPORT.md
Observed problem: v9.11 showed truth-free fixed_pipeline at 17/17 outcome and causal exact-set accuracy while the contextual Agent was 16/17, with retained diagnosis-less failure 675073735bc06f76. Sealed studies do not answer whether RealLLMPlanner earns its complexity on a fresh matched set that includes the D037 single_signal default path and upgrade utility metrics.
Why a new authorization boundary is required: Existing contracts preserve historical V0.2 / v9.11 identities and do not authorize this new study. The study requires its own additive protocol, execution identity, evidence tree, and staged authorization. No defect in frozen V0.2 §§1–64 is asserted.
Minimal proposed change: Accept the revised docs/superpowers/specs/2026-09-30-s1-planner-ablation-utility-study-design.md as a study-shape freeze only for study_s1_planner_ablation_dev_1. Scored arms are product_agent and truth-free fixed_pipeline on fresh development cases, with single_signal and at least one contextual upgrade mode (default paired_reference). scripted_agent is harness-only and excluded from scored comparisons. Evidence is additive under docs/evaluations/v0_3/planner_ablation/.
Matching prerequisite: The historical baseline and contextual harness are reuse candidates, not proof that the arms already share HEAD mode-specific claim gates, the D037 application boundary, or equivalent deterministic report processing. The later plan must establish these conditions; any required behavior change needs an explicit additive design and authorization.
Protocol prerequisite: Before scored execution, approve and seal paired case/mode populations, valid-inconclusive treatment, primary metrics, non-inferiority and material-improvement criteria, uncertainty handling, repetition/retry/stop rules, resource limits, and execution identities. Equal completion must not prevent a fixed-pipeline dominance conclusion. Failure to demonstrate a difference is not evidence of equivalence. Study results do not authorize product changes.
Compatibility impact: Documentation and decision register only for this approval. Additive docs/evaluations/v0_3/planner_ablation/ tree when harness work begins under later grants.
Test impact: None for study-shape approval. Future harness work needs new T-CX (or equivalent) IDs under an approved TEST_PLAN revision after a writing-plans grant and definition-before-implementation sequencing.
User decision: approved 2026-09-30 — OQ-019 study-shape freeze accepted. Approval freezes study shape only. Writing-plans requires a separate documentation-only grant. Additive contracts/test definitions and harness/Scripted implementation may share a later bounded grant, with definitions preceding implementation. RealLLM execution and product changes require subsequent explicit grants. Reversal words request scope changes and do not bypass these gates.
```

---

## OQ-020 — Regression comparison: `clipping_ratio` is not unconditionally a clipping-severity measure

```text
ID: OQ-020
Date: 2026-10-05
Status: approved — definitions registered as V0.3 §23, D043, T-CX349–T-CX370 on 2026-10-05; implementation merged 2026-10-05 (PR #41, `0770514`); characterization run, floor values and a judged product status not authorized
Affected document and section: CONTRACTS_V0_3_CONTEXTUAL.md §22.2 (first-phase compare metric `detect_clipping / clipping_ratio`) and §22.3 (comparison rules); src/signal_diag/dsp/clipping.py (`analyze_clipping`); any future method-floor or comparison-tolerance design built on `clipping_ratio`.
Observed problem: A read-only probe at fb38314 called `analyze_clipping` with default parameters on clean, unclipped sines from `generate_sine` (sample rates 44100/48000 Hz; 50/100/220/440/880/997 Hz; amplitudes 0.01/0.05/0.2/0.5/0.9; four start phases each, 0/0.1/1.0/2.0 rad; 2.0 s). 29 of 60 frequency/amplitude/rate cells returned non-zero `clipping_ratio` with `flat_top_detected=true` and `clipping_mechanism=false`. Examples: 100 Hz, amplitude 0.01, 48 kHz ≈ 0.55; 50 Hz, amplitude 0.9, 48 kHz ≈ 0.0125–0.0146; 100 Hz, amplitude 0.9, 48 kHz = 0.0125 at phase 0 and 0.0 at the other three phases. Values change with start phase and sample rate. Cells at ≥ 440 Hz with amplitude ≥ 0.2 were all zero. Cause by code reading: the flat-top mask uses an absolute adjacent-sample tolerance (default 1e-4, minimum 3 samples); near the peak of a low-frequency or low-amplitude sine, adjacent differences fall below that tolerance. Separately, white noise (rms 0.5, limited to full scale, one seed) returned a valid `clipping_ratio` ≈ 0.004; the clipping measurement has no non-applicable outcome for non-periodic input.
Evidence classification: (measured) the clean-sine and white-noise results above; the probe script was not committed, and this was a probe, not a frozen characterization — a reproducible in-repo rerun is recommended before these numbers are cited as formal evidence. (code reading, not measured) `clipping_mechanism` is `full_scale_detected or (flat_top_detected and peak >= full_scale_threshold)`, so genuine sub-full-scale flat-top clipping and clean-sine false plateaus both present as `flat_top_detected=true, clipping_mechanism=false` and are not separable by that flag. (not verified) any effect on the single-file diagnosis path. The §8 causal gate requires `clipping_mechanism=true`, and all 29 cells had it false, so by that rule no clipping claim should form; no end-to-end diagnosis run was made to confirm.
Why the current contract cannot represent a correct implementation: §22.2 registers `clipping_ratio` as a first-phase numeric compare metric and §22.3 lets a future approved profile judge its difference. The value is the fraction of samples satisfying the full-scale or absolute flat-top criteria, which is not equivalent to clipping severity on low-frequency or low-level periodic input. A tolerance or method floor on this value would treat sampling-phase artefacts as clipping change. Filtering on `clipping_mechanism` alone would exclude onset regressions (baseline false, candidate true) and cannot distinguish sub-full-scale clipping from false plateaus. No defect in frozen V0.2 §§1–64 is asserted.
Minimal proposed change: Recording this entry changes no code or contract, but the approved design below does require an explicit contract amendment before implementation; it is not a purely additive clause. Design (operator-approved 2026-10-05, design content only): docs/superpowers/specs/2026-10-05-s1-regression-clipping-comparison-semantics-design.md §12, with the layer-1 characterization design in docs/superpowers/specs/2026-10-05-s1-regression-layer1-characterization-materials-scoring-design.md §10. Summary: (1) the comparison judges a new comparison-specific full-scale sample count (samples with |x| >= full-scale threshold in runs of at least 2, same criterion as the existing full-scale mechanism) and its yes/no state, held in a separate, immutable check record; the existing comparison record, its required checks and its overall-pass logic are untouched; (2) state transitions are judged directionally (onset = regression by state; increase beyond the layer-1 floor = regression; decrease or disappearance = no regression with a fixed same-screen notice), only when every eligibility gate holds, and wording states "samples reaching the full-scale threshold", never "clipping"; (3) no observable fact today separates genuine sub-full-scale flat-top clipping from false plateaus, so that case is out of scope and stays descriptive; (4) `clipping_ratio` stays displayed, is permanently descriptive, and no product profile may carry a rule for it. Required amendment path: a new contract section clarifying that the "only" in §22.2 constrains metrics inside the existing comparison record and that the integer sample-count fact is a different object not governed by the §22.3 float rule shape; a new decision record; new T-CX IDs. The amendment text was approved and registered on 2026-10-05 (§23, D043, T-CX349–T-CX370); implementation is not authorized. The single-file diagnosis detector, thresholds, v9.11 prompt and causal policy stay unchanged.
Review status: an independent read-only subagent review reproduced the probe (29 of 60 cells non-zero, same values) and measured that genuine sub-full-scale clipping (clip levels 0.5/0.9/0.98) gives mechanism flag false and full-scale count 0. Its findings were resolved by the operator in §12 and re-reviewed; six fixes written after the re-review were not reviewed a third time. Measurements were direct DSP calls, not the full tool path with WAV quantization; tests were not run.
Compatibility impact: None from recording this entry. The product already ships descriptive-only comparison (approved profiles: 0), so no judgment is affected today; descriptive `clipping_ratio` values and differences shown in the workbench may be non-zero on unclipped low-frequency or low-level input.
Test impact: None for this entry. Implementation needs new T-CX IDs; design-tracking requirements are CS01–CS14 in the design, plus the clean-sine cells above and a sub-full-scale clipped sine as regression cases.
User decision: approved 2026-10-05 — design (spec §12–§13, characterization §10–§11) and amendment draft revision 2; recorded as D043. Not authorized: implementation plan, implementation, characterization run, any floor value, a judged product status. Revision 2 of the amendment and the last correction sections were not independently re-reviewed before approval.
Implementation (2026-10-05): the implementation plan (revision 4) and its implementation were later authorized separately and merged as PR #41 (`0770514`) after independent review. The product ships no floor record and has no judged status. The layer-1 characterization run, any floor value and floor approval remain unauthorized. Follow-up: OQ-021. Floor registration and OQ-021/OQ-022 closure are recorded as D044.
```

## OQ-021 — Full-scale check: floor applicability when one side has no facts

```text
ID: OQ-021
Date: 2026-10-05
Status: approved — Option A; recorded as D044; T-CX381
Affected document and section: CONTRACTS_V0_3_CONTEXTUAL.md §23.4 (floor applicability) and §23.5 (eligibility condition 8, validation); src/signal_diag/rules/full_scale_check.py (`_floor_identity_ok`, `_applicable_approved_floors`, `validate_full_scale_check_record`).
Observed problem: §23.4 says a floor record applies only when `facts_version`, `full_scale_threshold` and `min_consecutive_samples` equal those of both sides' facts. The merged implementation (`0770514`) skips a side whose facts are missing, so a floor counts as applicable when one or both anchor sides have no facts. Such a record then carries the floor, and plan Task 9B-7 validation requires an applicable approved floor to be present on it. Found in the independent review of PR #41 (finding F4, Info).
Why the current contract cannot represent a correct implementation: The contract can represent it; the question is which reading is intended. Today there is no product impact: the registry is empty, and a missing side already yields `facts_missing:<side>` and `not_comparable`, so no judged status is reachable either way. It matters once a floor record is approved, because the two readings produce different `floor`, `unmet_conditions` and `unevaluated_conditions` contents for the same input.
Minimal proposed change: Decide before any floor record is approved. Option A: follow §23.4 literally; a floor applies only when both anchor sides have facts and all three identity fields match, otherwise `floor_missing` is listed and condition 9 and the reviewed part of condition 10 go to `unevaluated_conditions`. Option B: keep the current behavior and amend §23.4 to say that sides without facts are not compared. Option A is recommended because it matches the frozen wording and needs no contract change.
Compatibility impact: None today (no product floor). Option A changes check-record contents only for inputs with missing facts.
Test impact: Option A needs a rules test (one side without facts plus a matching fixture floor: no floor on the record, `floor_missing` listed) and an adjusted 9B-7 test. Option B needs a contract revision and a test pinning the current behavior.
Related cleanup (no contract impact): in `src/signal_diag/app/regression_reporting.py` `_validate_full_scale_checks`, a record whose anchor is a repeat is rejected with "anchor_comparison_id is missing from comparisons", and the in-loop "not an anchor" check is unreachable. Fix the message or remove the dead check in the same change.
User decision: approved 2026-10-06 — Option A (both sides must have facts for a floor to apply). Recorded as D044. Implementation changes only `_floor_identity_ok` (T-CX381). The reporting-layer cleanup named above remains unauthorized by this decision.
```

## OQ-022 — Full-scale check: fixed-minimum critical zone under the cumulative tolerance reading

```text
ID: OQ-022
Date: 2026-10-05
Status: approved — Option B; recorded as D044; T-CX382
Affected document and section: CONTRACTS_V0_3_CONTEXTUAL.md §23.4 (tolerance decision; fixed minimum of the critical zone); src/signal_diag/rules/full_scale_check.py (`_in_critical_zone`, `_quantization_step`).
Observed problem: The operator decided on 2026-10-05 that §23.4 "at most one quantization step of the coarser of the two bit depths … plus bit-depth conversion" means both can occur together (layer-1 characterization plan, decision A.10). Under that reading the fixed minimum ("a `no` side with `peak_abs >= full_scale_threshold - step` is inside the critical zone") does not contain every tolerated difference. Full tool path, measured in the independent review of the characterization plan and reproduced: 100 Hz, 48 kHz, amplitude 0.989993, phase π/480. The 16-bit rounded file has peak 0.98995972 and counts 0, below 0.99 − 2^-15 = 0.98996948, so it is outside the fixed minimum. The same waveform as 32-bit, rounded and then moved one 16-bit step away from zero, counts 800. With the fixed minimum alone this pair would be judged `regression_detected`.
Why the current contract cannot represent a correct implementation: It can, as long as a floor record exists. The product uses `max(zone_below_threshold, step)` for a `no` side, and the layer-1 characterization now includes this composite in its tolerated null pairs, so under full coverage the fitted `zone_below_threshold` covers it. Without a floor record no judged status is reachable. What is lost is the property that the fixed minimum alone, independent of sampling, contains every tolerated difference.
Minimal proposed change: Decide before any floor record is approved, together with OQ-021. Option A: widen the fixed minimum to `full_scale_threshold - 2 * step` (one step plus a bit-depth conversion error of up to one step when conversion truncates), as a contract revision to §23.4 and a one-line change to `_in_critical_zone`. Option B: keep one step and state in §23.4 that the fixed minimum covers single-depth differences only and that the reviewed floor record must cover the composite. The characterization report gives flip counts outside the one-step and the two-step bounds as evidence. Option A is recommended because it restores a guarantee that does not depend on the characterization grid.
Compatibility impact: None today (no product floor; no judged status). Option A moves some `no` sides into the critical zone once a floor exists, reducing coverage slightly.
Test impact: Option A needs an update to the T-CX357 fixed-minimum tests and a regression case built from the pair above. Option B needs a contract revision and a test that pins the one-step bound.
User decision: approved 2026-10-06 — Option B (no code change to `_in_critical_zone`; append a §23.4 requirement that any approved floor record has `zone_above` of at least one 16-bit step). Recorded as D044. Contract append is T-CX382; critical-zone and judgment logic stay unchanged.
```

## OQ-023 — Provider telemetry: SDK profile names `httpx`, but openai 3.6.0 sends through `httpx2`

```text
ID: OQ-023
Date: 2026-10-06
Status: approved — Option A; recorded as D048; T-CX425–T-CX427
Affected document and section: src/signal_diag/agent/provider_telemetry.py (`_NATIVE_HOOK`, `_AUDITED_HTTPX_VERSION`, `build_audited_sdk_observation_profile`, `reviewed_openai_capability_identity`); CONTRACTS_V0_3_CONTEXTUAL.md §21 (planner-ablation token and transport telemetry).
Observed problem: The locked `openai==3.6.0` dispatches through its vendored `httpx2` (2.12.0): `AsyncOpenAI(...)._client` is an `httpx2.AsyncClient`. The audited SDK observation profile still records `native_http_family="httpx"`, `native_http_version` from `httpx.__version__` (0.28.1), and `native_dispatch_hook="httpx.AsyncClient.send"`, and its version audit pins `httpx`, not `httpx2`. Found while diagnosing why the D047 acceptance script counted zero sends (its class-level `httpx.AsyncClient.send` patch never fired; see `evaluations/v0_3/intake_product/acceptance_1/ACCEPTANCE_NOTE.md`).
Why the current contract cannot represent a correct implementation: It can for counting. Probed on 2026-10-06 against a closed local port with no model call: `attach_sdk_observation` wraps the client instance's own transport and emitted SdkAttemptEvent start/end and HttpSendEvent start/end for the single send, so send telemetry is not blind. What is wrong is the identity metadata, and an `httpx2` upgrade would pass the audit unnoticed.
Minimal proposed change: Option A: add an `httpx2` version pin to the audit and record `native_http_family="httpx2"` with its version and a corrected hook label in new profiles, leaving every recorded artifact unchanged. Option B: document the label as historical and add only the `httpx2` pin as an extra blocker. No change is proposed to the stopped `dev_2` records (D046).
Compatibility impact: Option A changes the identity fields of profiles built after the change; recorded planner-ablation artifacts keep their old values. Option B changes nothing recorded.
Test impact: A test that builds the audited profile and asserts the dispatch family matches `type(AsyncOpenAI(...)._client)`'s module, plus an `httpx2` version-drift blocker test.
User decision: approved 2026-10-06 — Option A. Recorded as D048; design `docs/superpowers/specs/2026-10-06-oq023-sdk-dispatch-identity-design.md`. Implementation confirmed that no existing test fixture needed changing.
```

## OQ-024 — F0: octave-ambiguity detection does not flag subharmonic lock

```text
ID: OQ-024
Date: 2026-10-06
Status: open (deferred by the operator 2026-10-06; not part of the F0 fix)
Affected document and section: src/signal_diag/dsp/spectral_reliability.py (`detect_octave_ambiguity`); src/signal_diag/dsp/pitch.py and src/signal_diag/dsp/harmonics.py (callers); the `octave_ambiguity_detected` field of F0 and harmonic Evidence.
Observed problem: For pure tones whose period is not a whole number of samples, `estimate_f0_autocorrelation` locks onto a subharmonic (8 kHz/440 Hz → 87.91 Hz; 16 kHz/440 Hz → 146.79 Hz; 8 kHz/220 Hz → 73.39 Hz), and `detect_octave_ambiguity` returns False in every case measured on 2026-10-06. The flag therefore gives no warning in exactly the situation it exists for.
Why the current contract cannot represent a correct implementation: It can; the detector's checks simply do not cover a primary lag that is a multiple of the true period. The F0 fix (design `docs/superpowers/specs/2026-10-06-f0-subharmonic-fix-design.md`) removes the measured lock, which reduces but does not remove the need for a working flag.
Minimal proposed change: After the F0 fix lands, measure the flag on the same corpus and decide whether to (A) also test the shorter-lag peaks that are integer divisors of the chosen lag, or (B) document the flag as covering only the octave-up case.
Compatibility impact: Option A changes `octave_ambiguity_detected` in Evidence for affected signals; recorded runs are not rewritten.
Test impact: A table of tones at 8/16/44.1/48 kHz asserting the flag for any deliberately forced subharmonic lag.
User decision: pending; deferred 2026-10-06.
```

## OQ-025 — Clipping: peak-normalized recordings trip the full-scale check

```text
ID: OQ-025
Date: 2026-10-07
Status: open (recorded from the D051 EGFxSet check; no change made)
Affected document and section: src/signal_diag/dsp/clipping.py (full-scale threshold 0.99); rules profile_s1_segment_evidence and profile_s1_contextual_comparison_v9_10 clipping rules; CONTRACTS_V0_3_CONTEXTUAL.md §27.
Observed problem: EGFxSet recordings are normalized so that the peak is 0.88–1.00 of full scale. Single-file clipping intervals appear on all 11 clean notes in the sample, and a clean reference judged as clipping makes the whole-file paired gate fail (7 of 11 clean-versus-clean pairs not comparable). See docs/evaluations/v0_3/fault_localization/egfxset_check_1/README.md.
Why the current contract cannot represent a correct implementation: It can; a sample at or near full scale is treated as clipping evidence by design. The detector cannot tell a normalized peak from a clipped one using level alone.
Minimal proposed change: Measure whether the existing flat-top and ratio evidence separate normalized peaks from true clipping on this sample before proposing any change; any threshold or rule change needs its own design and versioned profile.
Compatibility impact: None until a design is approved; recorded runs are not rewritten.
Test impact: A fixed set of normalized clean recordings and clipped counterparts.
User decision: pending.
```

## OQ-026 — WAV decoding: a trailing partial frame rejects the whole file

```text
ID: OQ-026
Date: 2026-10-07
Status: open (recorded from the D051 EGFxSet check; no change made)
Affected document and section: src/signal_diag/signal/wav.py (`load_wav_bytes`, "data size is not a multiple of block_align").
Observed problem: EGFxSet `Clean/Neck/1-0.wav` (24-bit mono) has a `data` chunk of 709,396 bytes, one byte more than a whole number of 3-byte frames. The decoder rejects the file, so 1 of 72 files in the sample cannot be analyzed.
Why the current contract cannot represent a correct implementation: It can; rejecting a malformed chunk is the current bounded-decoding behavior. Tolerating it would be a behavior change.
Minimal proposed change: Either (A) keep rejecting and show the user a clearer message, or (B) drop the trailing partial frame and record a warning in the source summary.
Compatibility impact: Option B lets files that are rejected today decode; accepted files decode byte-identically.
Test impact: A WAV with a one- and two-byte trailing partial frame for each supported sample width.
User decision: pending.
```
