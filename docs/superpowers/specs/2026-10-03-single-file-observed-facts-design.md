# Single-file observed facts on context guidance (OQ-013 path C)

**Status:** design approved for documentation (operator 2026-10-03).
Implementation, contract mutation, test registration, product code, and merge
of an implementation PR are **not** authorized by this document alone.

**Date:** 2026-10-03

**Product decisions:** D037 (single-file default); this design → **D039**
(OQ-013 product-behavior path C)

**Related:** OQ-013 deferred product-behavior fork; CONTRACTS_V0_3 §17
`context_guidance`; `src/signal_diag/app/context_guidance.py`;
`tools/service.py` (`analyze_harmonic_distortion`);
`evaluation/contextual/calibration.py` (`contextual_product_tree_sha256`)

## 1. Decision summary

Keep HEAD single-file finish gates and planner identity unchanged
(`v0.3-s1-planner-9.11`, `v9_11_mode_aware_no_fault_recovery`). Do **not**
restore v8.1 harmonic `supported_fault` on `single_signal`.

When eligible single-file runs already emit `context_guidance` for missing
attribution context, attach an optional deterministic `observed_facts`
summary of same-run measured Evidence that passed an independent display
whitelist. Facts state what was measured. They never attribute
`harmonic_distortion` as a supported fault and never soften gates.

## 2. Problem

Under D037 / v9.11, harmonic-rich one-file cases correctly end
`inconclusive` with upgrade guidance. Users see “need reference / nominal”
language but may not see a curated, trustworthy summary of what the same
run already measured (for example THD). The full Measured Evidence list in
HTML remains; it is not a controlled product summary with copy and
compatibility rules.

## 3. Goals and non-goals

### Goals

1. On eligible `context_guidance`, attach `observed_facts` built only from
   same-run valid Evidence that pass a display whitelist independent of the
   §17 reason-code metric set.
2. Copy Evidence fields faithfully, including measurement scope
   (`time_range`, `channel`).
3. Allow empty `observed_facts` when no row qualifies. Do not invent,
   zero-fill, or coerce `not_applicable` into display values.
4. Keep frozen V0.2 DTOs, `/api/v1/runs/*`, and `diagnose wav` byte-stable.
5. Require implementation-time code-identity accounting when `app/` changes
   the live product tree digest.

### Non-goals

- Softening single_signal harmonic finish gates or restoring v8.1 semantics.
- Changing prompt, causal policy, DSP, rules, or Tool outputs.
- Expanding the first-phase whitelist to contextual metrics
  (`even_harmonic_growth_percent`, `test_thd_percent`, …).
- Adding measurements or derived judgments to fill the whitelist.
- Rewriting `diagnose wav` onto contextual submit.
- Mode-filtered tool descriptors (former OQ-016 B-class).
- Seal, RealLLM campaign, HEAD quality claims, planner-ablation budgets.

## 4. Approaches considered

| Option | Idea | Verdict |
|--------|------|---------|
| **C1** | Extend `ContextGuidance` with `observed_facts` and a separate display whitelist | **Accepted** |
| C2 | New top-level `unattributed_measurements` on every completed `single_signal` report | Rejected (broader surface; overlaps Measured Evidence) |
| B | Regain v8.1-like harmonic `supported_fault` on one file | Rejected (OQ-013 path B; over-claims without context) |
| Prompt prose | Ask the LLM to list measurements | Rejected (non-deterministic; identity risk) |

## 5. Design

### 5.1 Data shape

```text
ObservedFact =
  evidence_id: str
  source_tool: ToolName
  call_id: str
  metric: str
  value: bool | int | float | str   # identical to source Evidence; float finite
  unit: str | None
  validity: "valid"                 # only valid rows may enter
  time_range: TimeRange | None      # copied
  channel: ChannelMode              # copied

ContextGuidance +=
  observed_facts: tuple[ObservedFact, ...]   # may be ()
```

Each fact must match the cited same-run Evidence on
`metric`, `value`, `unit`, `validity`, `time_range`, `channel`,
`source_tool`, and `call_id`.

### 5.2 First-phase display whitelist

This table is **not** the §17 reason-selection metric set. Reason selection
stays as frozen today. Display filtering is independent.

| metric | source_tool | type | unit | applicability |
|--------|-------------|------|------|---------------|
| `thd_percent` | `analyze_harmonic_distortion` | finite `float` | `%` | Same-run Evidence with `validity=="valid"` and matching `source_tool` / `unit` / type. Produced on the single-file harmonic tool path (`tools/service.py`). |

**Explicitly out of first phase:** names in the reason set that tools do not
emit (`even_harmonic_growth`), and contextual-tool metrics
(`even_harmonic_growth_percent`, `test_thd_percent`, …). Later expansions
require a verified source_tool row and a new design or amendment. Do not add
measurements to pad the list.

### 5.3 Scope and selection

1. Candidates = same-run `AgentRunResult.evidence` rows that satisfy a
   whitelist row.
2. If several rows share `(metric, channel, time_range)`, keep the one with
   the lexicographically smallest `evidence_id`. Do not merge or average.
3. Order: whitelist table order, then `evidence_id` ascending.
4. If none qualify → `observed_facts = ()`.

### 5.4 Emission

On top of existing §17 emission (`single_signal`, `inconclusive`, …):

1. Emit `context_guidance` as today.
2. When reason codes include `harmonic_attribution_requires_context`, select
   facts per §5.2–§5.3. Field-faithful copy with measurement scope. If none
   qualify, return `()`. Summary must not promise displayable facts.
3. When only `insufficient_evidence_for_supported_fault` applies →
   `observed_facts = ()`.
4. Summary stays on fixed templates. An optional fixed clause that facts are
   measured and not fault-attributed may attach only when
   `len(observed_facts) > 0`. Ban soft diagnosis wording
   (“可能是”, “likely”, “harmonic fault” as attribution).

Reason selection does not change when facts are empty.

### 5.5 Compatibility (`extra="forbid"`)

| Direction | Rule |
|-----------|------|
| New model reads old payload (no `observed_facts`) | Default `observed_facts=()` |
| Old consumer reads new payload | Current `ContextGuidance` uses `extra="forbid"`, so old schema/code **rejects** unknown fields. Implementation must update every in-repo parse site and contract tests. Out-of-repo old binaries are not guaranteed. Acceptance needs both “old shape without field still green” and “new shape with field still green” tests. |

### 5.6 Layer boundary

Touch only `app/` builders and contextual report/HTML rendering for guidance.
Do not change `tools/`, `dsp/`, `rules/`, or `agent/` prompt/policy/gates.

### 5.7 Code identity accounting (implementation phase)

`app/` is part of `contextual_product_tree_sha256()` in
`evaluation/contextual/calibration.py`. Adding guidance fields can change the
live product-tree digest even when prompt and finish gates are unchanged.

If implementation changes that digest, add a new append-only code-identity
record and update active-identity verification. Keep prior records (including
PR #21 / D038 telemetry rows) and historical digests. Do not overwrite old
rows or recompute historical campaign artifacts. Do not change
planner-ablation budgets, resource ledgers, or scoring. A digest change is
not a prompt/policy identity change and is not quality certification.

### 5.8 Contracts and tests (implementation phase only)

This design PR does **not** edit these files. A later implementation grant
must:

1. Amend `CONTRACTS_V0_3_CONTEXTUAL.md` §17 with `ObservedFact`, the display
   whitelist, selection rules, empty-tuple allowance, and the compatibility
   table.
2. Register additive test IDs in `TEST_PLAN_V0_3_CONTEXTUAL.md` starting at
   **T-CX319** if still free at implementation tip (free as of design base
   `ecadfef` / check tip `d152489` lineage; re-check before landing).
3. Implement builders, renderers, and tests under those IDs.
4. Perform §5.7 identity accounting when digests move.

Frozen `CONTRACTS_V0_2.md` §§1–64 stay byte-stable.

### 5.9 Proposed identifiers (re-check before land)

| ID | Intent | Status at design writing |
|----|--------|---------------------------|
| D039 | This product-behavior decision | Unused in `DECISIONS.md` on base `ecadfef` |
| T-CX319… | Implementation tests for observed facts | T-CX318 is last registered additive ID on base `ecadfef` |

Re-verify both numbers at the implementation tip before registration.

## 6. Authorization boundary

**Authorized now:** this design document, D039, and OQ-013 disposition
bookkeeping.

**Not authorized by approving this design:**

- implementation code or contract/test-plan edits;
- seal, RealLLM campaign, or HEAD quality claims;
- planner-ablation budget / resource-ledger / scoring changes;
- merge of an implementation PR without a separate grant.

## 7. Success criteria (when later implemented)

Given a single-file inconclusive run with same-run valid `thd_percent`
Evidence from `analyze_harmonic_distortion`, `context_guidance.observed_facts`
contains a field-faithful copy of that Evidence (including scope), outcome
remains `inconclusive`, and no harmonic `supported_fault` appears. If no
whitelist row qualifies, guidance may still emit with `observed_facts=()` and
unchanged reason codes.
