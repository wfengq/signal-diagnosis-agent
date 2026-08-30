# Open Contract and Architecture Questions

**Status:** Active register
**Current open questions:** 0 pending; 10 resolved (OQ-001–OQ-010)

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
Observed problem: Architecture §15 and D012/D016 require WAV, CLI/API/UI, actual Agent trace, reporting, evaluation presentation, and a resume-grade Demo, but CONTRACTS §29 deliberately left every Phase 5 interface unfrozen.
Why the current contract cannot represent a correct implementation: Without exact WAV bounds, application lifecycle, service boundary, trace bridge, report/API/CLI/UI schemas, security semantics, and deterministic/real acceptance states, independent implementations could duplicate diagnosis logic, leak evaluation truth, expose unsafe payloads, or claim completion without a real product path.
Minimal proposed change: Approve the complete Phase 5 written specification, additive §§55–§64, T224–T285, and D026–D030. The selected design uses a shared DiagnosisApplicationService, bounded local polling jobs, strict integer-PCM WAV ingestion, native Web UI, canonical JSON/self-contained HTML reports, a checksum-linked accepted evaluation summary, and separate presentation_harness_accepted / real_demo_completed gates.
Compatibility impact: Additive signal WAV loader, generic evaluation trace helper, app package, optional Web/LLM dependencies, console/API/UI/report surfaces, package assets, and CI only. Frozen Phase 1–4.3.1 numerical, Agent, scoring, target, prompt, dataset, and historical bundle behavior remains unchanged.
Test impact: Adds deterministic T224–T285 and non-CI P5-R001–P5-R003. T001–T223 remain required and unchanged.
User decision: approved OQ-010, the complete Phase 5 written specification, Contracts §§55–§64, Test Plan §28 T224–T285, and D026–D030 on 2026-08-31; authorized Superpowers writing-plans only; source/test implementation, model execution, push, merge, worktree deletion, and build/ cleanup remain unauthorized pending the completed plan and a separate explicit execution choice
```
