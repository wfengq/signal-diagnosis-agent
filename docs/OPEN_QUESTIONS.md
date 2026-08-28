# Open Contract and Architecture Questions

**Status:** Active register
**Current open questions:** 1 pending (OQ-003 deferred); 4 resolved (OQ-001, OQ-002, OQ-004, OQ-005)

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
Status: open — deferred until before Phase 3 completion; comparator-as-PASS-condition frozen first
Affected document and section: docs/CONTRACTS_V0_2.md §33–§34; rules/profiles/
Observed problem: Contract names supported metric families and comparator PASS semantics but does not freeze demonstration threshold values for clipping_ratio, thd_percent, flat_top_detected, or related rules.
Why the current contract cannot represent a correct implementation: RuleEngine PASS/FAIL behavior for scripted S1 acceptance requires concrete profile values aligned with synthetic ground truth.
Minimal proposed change: Approve an initial profile_s1_distortion v1 YAML with explicit comparators and thresholds documented as demonstration-only, not industry standards. Threshold approval is not required for OQ-001 contract freeze.
Compatibility impact: Profile file content only; public RuleProfile and RuleEvaluation models unchanged.
Test impact: T098–T120 may use test-local profiles during TDD; T121–T124 and the Phase 3 completion gate require the approved production demonstration profile.
User decision: deferred — approve demo-only profile thresholds before T121–T124 are finalized and before Phase 3 completion
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
