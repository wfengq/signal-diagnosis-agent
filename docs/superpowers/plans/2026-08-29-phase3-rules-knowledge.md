# Phase 3 Rules and Knowledge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不改变 Phase 1–2 冻结接口语义的前提下，为 Scenario S1 增加确定性规则判断、小型本地知识检索、Agent 运行时动作与完整 T093–T124 验收路径。

**Architecture:** 保持 `signal → dsp → tools → rules/knowledge → agent` 单向依赖。DSP Tool 只生成 Evidence；RuleEngine 只把 Evidence 与版本化阈值比较；KnowledgeIndex 只返回可追溯解释片段；Agent runtime 负责动作路由、预算、状态传播和最终引用校验。`RealLLMPlanner` 仍是产品路径，`ScriptedPlanner`/确定性测试 planner 仅用于可重复验收。

**Tech Stack:** Python 3.11+、Pydantic V2、PyYAML `safe_load`、pytest/pytest-asyncio、Ruff、mypy、现有 NumPy DSP/Tool 层。

**Spec:** `AGENTS.md`；`docs/ARCHITECTURE_V0_2.md` §13；`docs/CONTRACTS_V0_2.md` §32–§40；`docs/TEST_PLAN_V0_2.md` §21；D014。

## Global Constraints

- OQ-001 已批准；§32–§40 和 T093–T124 已冻结。
- OQ-003 已于 2026-08-29 批准；`1.0.0-demo` 精确阈值由 D015 冻结。
- Cursor 负责全部实现代码；Codex 负责设计、契约和只读验收审查，除非用户另行授权。
- 不实现 Phase 4 数据集、固定流水线对照或评估 schema；不实现 Phase 5 WAV/API/UI/报告适配器。
- 不引入 LangGraph、向量数据库、embedding、网络知识检索或 LLM 生成阈值。
- required pytest 不访问网络，不调用真实 LLM，不 mock DSP 数值结果。
- Phase 2-only 的 `DistortionDiagnosisRuntime(...)` 构造方式必须继续工作。
- 每个任务遵循 RED → GREEN → 累积回归 → 本地提交；实现者完成后由独立 reviewer 检查契约与测试覆盖。
- 不提交 `real_model_eval_output/`；真实模型检查始终是非 CI 行为评估。

---

## Task 0: Resolve OQ-003 with the exact demo profile — completed

**Status:** Completed by design approval on 2026-08-29. Cursor starts at Task 1.

**Files:**

- Modify: `docs/OPEN_QUESTIONS.md`
- Modify: `docs/DECISIONS.md`
- Modify: `docs/CONTRACTS_V0_2.md` §40.2 only to remove OQ-003 from remaining items after approval

**Approved decision:**

Freeze `profile_s1_distortion`, version `1.0.0-demo`, with comparators interpreted as PASS conditions:

```yaml
profile_id: profile_s1_distortion
version: 1.0.0-demo
description: Demonstration-only S1 clipping and harmonic-distortion limits; not an industry standard.
rules:
  - rule_id: rule_clipping_detected_absent
    metric: clipping_detected
    source_tool: detect_clipping
    comparator: eq
    threshold: false
    unit: null
    description: No clipping detection is acceptable.
  - rule_id: rule_clipping_ratio_acceptable
    metric: clipping_ratio
    source_tool: detect_clipping
    comparator: lte
    threshold: 0.01
    unit: null
    description: A clipping ratio at or below one percent passes the demo rule.
  - rule_id: rule_flat_top_absent
    metric: flat_top_detected
    source_tool: detect_clipping
    comparator: eq
    threshold: false
    unit: null
    description: No flat-top event is acceptable.
  - rule_id: rule_harmonic_analysis_valid
    metric: valid
    source_tool: analyze_harmonic_distortion
    comparator: eq
    threshold: true
    unit: null
    description: Harmonic analysis must be applicable before THD is judged.
  - rule_id: rule_thd_acceptable
    metric: thd_percent
    source_tool: analyze_harmonic_distortion
    comparator: lte
    threshold: 5.0
    unit: "%"
    description: THD at or below five percent passes the demo rule.
```

These values separate the accepted synthetic fixtures: clean THD is near zero,
S1-HARM THD is approximately 11.18%, S1-CLIP-SUBFS has a 0.625 clipping ratio
and flat top, and S1-NOISE produces not-applicable harmonic Evidence. They are
explicitly demo thresholds, not standards or product limits.

The approval is recorded in OQ-003 and D015 before implementation. The contract
model/engine interfaces are unchanged. Cursor must not repeat Task 0 or revise
these values silently.

---

## Task 1: Add rule models, explicit YAML loader, and package gate

**Test IDs:** T093–T095, T097

**Files:**

- Modify: `pyproject.toml`
- Create: `src/signal_diag/rules/__init__.py`
- Create: `src/signal_diag/rules/models.py`
- Create: `src/signal_diag/rules/loader.py`
- Create: `src/signal_diag/rules/profiles/s1_distortion_v1.yaml`
- Create: `tests/rules/__init__.py`
- Create: `tests/rules/test_models.py`
- Verify: `tests/test_architecture_boundaries.py`

**Step 1 — write RED tests:**

Create tests that instantiate the frozen Pydantic models, reject empty/duplicate
rules, preserve threshold scalar categories, and load only an explicitly mapped
profile path. The core cases must include:

```python
def test_t094_duplicate_rule_ids_are_rejected() -> None:
    rule = RuleDefinition(
        rule_id="rule_ratio",
        metric="clipping_ratio",
        source_tool="detect_clipping",
        comparator="lte",
        threshold=0.01,
        description="demo ratio",
    )
    with pytest.raises(ValidationError, match="duplicate rule_id"):
        RuleProfile(
            profile_id="profile_test",
            version="1",
            description="test",
            rules=(rule, rule),
        )


def test_t095_empty_profile_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RuleProfile(
            profile_id="profile_test",
            version="1",
            description="test",
            rules=(),
        )


def test_t097_loader_uses_explicit_mapping(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(VALID_PROFILE_YAML, encoding="utf-8")
    loader = YamlRuleProfileLoader({"profile_test": profile_path})
    assert loader.load("profile_test").profile_id == "profile_test"
    with pytest.raises(KeyError):
        loader.load("profile_missing")
```

Run:

```powershell
python -m pytest tests/rules/test_models.py tests/test_architecture_boundaries.py -q -p no:cacheprovider
```

Expected RED: import failure for `signal_diag.rules`.

**Step 2 — implement the frozen models:**

Use the exact fields from §33–§34. `RuleProfile` uses a post-model validator for
duplicate IDs. Preserve YAML-native `bool`, `int`, `float`, and `str` values;
never compare with `isinstance(value, int)` when distinguishing bool from int.

```python
@runtime_checkable
class RuleProfileLoader(Protocol):
    def load(self, profile_id: str) -> RuleProfile: ...


class YamlRuleProfileLoader:
    def __init__(self, profile_paths: Mapping[str, Path]) -> None:
        self._profile_paths = dict(profile_paths)

    def load(self, profile_id: str) -> RuleProfile:
        try:
            path = self._profile_paths[profile_id]
        except KeyError as error:
            raise KeyError(f"unknown rule profile: {profile_id}") from error
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        profile = RuleProfile.model_validate(payload)
        if profile.profile_id != profile_id:
            raise ValueError("loaded profile_id does not match requested profile_id")
        return profile
```

Add `PyYAML>=6.0` to runtime dependencies because the frozen package layout uses
a YAML profile, and add `types-PyYAML>=6.0.12` to development dependencies for
mypy. Install the revised project environment before GREEN:

```powershell
python -m pip install -e ".[dev,llm]"
```

This is the only new Phase 3 runtime dependency. Add package data so installed
distributions retain the profile:

```toml
[tool.setuptools.package-data]
"signal_diag.rules" = ["profiles/*.yaml"]
```

Do not add directory scanning or a module-level default loader.

**Step 3 — add the approved profile and exports:**

Write the exact Task 0 YAML to
`src/signal_diag/rules/profiles/s1_distortion_v1.yaml`. Export only the frozen
models, `RuleEngine` later, and the explicit loader implementation required for
composition.

**Step 4 — GREEN and regression:**

```powershell
python -m pytest tests/rules/test_models.py tests/test_architecture_boundaries.py -q -p no:cacheprovider
python -m pytest -q -p no:cacheprovider
python -m ruff check --no-cache src tests
python -m mypy --no-incremental src
```

Expected: T093–T095 and T097 pass; the former `rules/` package skips disappear;
Phase 1–2 remain green. T096 waits for RuleEngine in Task 2. Knowledge skips
remain until Task 3.

**Step 5 — commit:**

```powershell
git add pyproject.toml src/signal_diag/rules tests/rules tests/test_architecture_boundaries.py
git commit -m "feat: add versioned Phase 3 rule profiles"
```

---

## Task 2: Implement deterministic RuleEngine

**Test IDs:** T096, T098, T099, T100, T101, T102, T103, T104, T105

**Files:**

- Modify: `src/signal_diag/rules/__init__.py`
- Create: `src/signal_diag/rules/engine.py`
- Create: `tests/rules/test_engine.py`
- Modify if needed for scanner coverage only: `tests/test_architecture_boundaries.py`

**Step 1 — write RED tests:**

Use real `Evidence` objects. Cover all six comparators, with explicit assertions
for the frozen PASS interpretation. Include exact strictness cases:

```python
@pytest.mark.parametrize(
    ("observed", "threshold", "unit"),
    [(1, 1.0, None), (True, 1, None), (5.0, 5.0, "Hz")],
)
def test_t101_incompatible_evidence_is_not_applicable(
    observed: EvidenceValue,
    threshold: EvidenceValue,
    unit: str | None,
) -> None:
    evidence = make_evidence(value=observed, unit="%" if unit else None)
    evaluation = evaluate_one(threshold=threshold, rule_unit=unit, evidence=evidence)
    assert evaluation.judgment == "not_applicable"
    assert evaluation.evidence_refs == (evidence.evidence_id,)
    assert evaluation.reason
```

Also assert:

- the approved profile passes at clipping ratio `0.01` and THD `5.0`, fails at
  `0.0101` and `5.01`, and passes at `0.0099` and `4.99`;
- no match → one NOT_APPLICABLE result with empty refs;
- invalid Evidence → NOT_APPLICABLE citing its ID;
- two matching Evidence records → two evaluations in input order;
- `evidence_filter` excludes all other IDs;
- normalized outputs from repeated calls are identical;
- architecture scanner finds no forbidden imports.

Run and expect missing `RuleEngine`:

```powershell
python -m pytest tests/rules/test_engine.py -q -p no:cacheprovider
```

**Step 2 — implement comparison and compatibility:**

Use exact scalar categories and unit rules before invoking a comparator:

```python
def _same_scalar_category(left: EvidenceValue, right: EvidenceValue) -> bool:
    return type(left) is type(right) and type(left) in {bool, int, float, str}


_COMPARATORS: dict[RuleComparator, Callable[[EvidenceValue, EvidenceValue], bool]] = {
    "lt": operator.lt,
    "lte": operator.le,
    "gt": operator.gt,
    "gte": operator.ge,
    "eq": operator.eq,
    "neq": operator.ne,
}
```

The evaluation loop order is profile rule order, then matching Evidence input
order. Generate `ruleval_` and `rulebatch_` IDs from a canonical SHA-256 payload
containing profile ID/version, rule data, Evidence ID/value/validity/unit, and
match ordinal. This makes complete results deterministic while remaining within
§32.1.

**Step 3 — implement result semantics:**

- no match: `observed_value=None`, empty refs, non-empty reason;
- invalid/type mismatch/unit mismatch: cite that Evidence and set reason;
- valid compatible Evidence: apply comparator as PASS condition;
- `reason=None` for PASS/FAIL;
- engine never imports DSP, agent, service, registry runtime callables, LLM,
  evaluation, or app modules.

**Step 4 — GREEN and regression:**

```powershell
python -m pytest tests/rules/test_engine.py tests/test_architecture_boundaries.py -q -p no:cacheprovider
python -m pytest -q -p no:cacheprovider
python -m ruff check --no-cache src tests
python -m mypy --no-incremental src
```

**Step 5 — commit:**

```powershell
git add src/signal_diag/rules tests/rules tests/test_architecture_boundaries.py
git commit -m "feat: evaluate deterministic evidence rules"
```

---

## Task 3: Add knowledge models and curated deterministic corpus

**Test IDs:** T093 package-boundary portion; knowledge model prerequisites for T106

**Files:**

- Modify: `pyproject.toml`
- Create: `src/signal_diag/knowledge/__init__.py`
- Create: `src/signal_diag/knowledge/models.py`
- Create: `src/signal_diag/knowledge/corpus/clipping.md`
- Create: `src/signal_diag/knowledge/corpus/harmonic_distortion.md`
- Create: `src/signal_diag/knowledge/corpus/inconclusive.md`
- Create: `tests/knowledge/__init__.py`
- Create: `tests/knowledge/test_models.py`
- Verify: `tests/test_architecture_boundaries.py`

**Step 1 — write RED tests:**

Test frozen ID patterns, non-empty title/excerpt/version fields, tuple defaults,
and immutability. The generated fixed-corpus chunk identity is tested as T106
after `KnowledgeIndex` implements real chunking in Task 4:

```python
def test_knowledge_chunk_contract_is_frozen() -> None:
    chunk = KnowledgeChunk(
        chunk_id="chunk_clipping_001",
        document_id="doc_clipping",
        title="Clipping / Observable evidence",
        excerpt="Flat tops and a non-zero clipping ratio support clipping.",
        tags=("clipping", "flat-top"),
        heading_path=("Clipping", "Observable evidence"),
    )
    assert chunk.model_dump()["chunk_id"] == "chunk_clipping_001"
    with pytest.raises(ValidationError):
        KnowledgeChunk(
            chunk_id="bad",
            document_id="doc_clipping",
            title="x",
            excerpt="x",
        )
```

Run and expect import failure:

```powershell
python -m pytest tests/knowledge/test_models.py tests/test_architecture_boundaries.py -q -p no:cacheprovider
```

**Step 2 — implement exact models:**

Implement `KnowledgeDocument`, `KnowledgeChunk`, `KnowledgeMatch`, and
`KnowledgeRetrievalResult` exactly as §35–§36. Do not import signal, tools,
rules, agent, DSP, or any LLM/vector package.

**Step 3 — write the three corpus documents:**

Use this deterministic Markdown convention:

```markdown
# Clipping
Tags: clipping, flat-top, distortion

## Observable evidence
Flat tops, clipping events, and an elevated clipping ratio support clipping.

## Interpretation
Clipping limits waveform peaks and introduces broadband harmonic energy. Rule
thresholds are configured demonstration limits, not universal standards.
```

Create equivalent concise documents for harmonic distortion/THD and for
invalid-or-inconclusive periodic analysis. Include no numerical threshold values
in knowledge text; thresholds live only in the rule profile.

Extend package data without removing the rule entry:

```toml
[tool.setuptools.package-data]
"signal_diag.rules" = ["profiles/*.yaml"]
"signal_diag.knowledge" = ["corpus/*.md"]
```

**Step 4 — GREEN and regression:**

```powershell
python -m pytest tests/knowledge/test_models.py tests/test_architecture_boundaries.py -q -p no:cacheprovider
python -m pytest -q -p no:cacheprovider
```

Expected: all four former Phase 3 package-absence skips are gone.

**Step 5 — commit:**

```powershell
git add pyproject.toml src/signal_diag/knowledge tests/knowledge tests/test_architecture_boundaries.py
git commit -m "feat: add curated S1 knowledge corpus"
```

---

## Task 4: Implement deterministic keyword/tag retrieval

**Test IDs:** T106, T107, T108, T109, T110, T111, T112

**Files:**

- Modify: `src/signal_diag/knowledge/__init__.py`
- Create: `src/signal_diag/knowledge/index.py`
- Create: `tests/knowledge/test_index.py`
- Verify: `tests/test_architecture_boundaries.py`

**Step 1 — write RED tests:**

Create a `tmp_path` corpus so ranking tests are independent of prose changes.
Cover:

```python
def test_t106_fixed_corpus_produces_stable_chunks(corpus_root: Path) -> None:
    first = KnowledgeIndex(corpus_root).retrieve(query_text="clipping")
    second = KnowledgeIndex(corpus_root).retrieve(query_text="clipping")
    assert first.chunks == second.chunks
    assert first.chunks[0].chunk_id == "chunk_clipping_000"


def test_t107_empty_query_and_invalid_limit(index: KnowledgeIndex) -> None:
    result = index.retrieve(query_text="")
    assert result.query_text == ""
    assert result.matches == ()
    assert result.chunks == ()
    with pytest.raises(ValueError, match="max_results"):
        index.retrieve(query_text="clipping", max_results=0)


def test_t108_unicode_casefold_punctuation_and_dedup(index: KnowledgeIndex) -> None:
    result = index.retrieve(query_text="THD, thd; CLIPPING!")
    assert result.matches
    assert result.matches[0].matched_terms == ("thd", "clipping")


def test_t110_matches_and_chunks_are_one_to_one(index: KnowledgeIndex) -> None:
    result = index.retrieve(query_text="distortion")
    assert len(result.matches) == len(result.chunks)
    assert [m.chunk_id for m in result.matches] == [c.chunk_id for c in result.chunks]
```

Also prove tag matching is strip-only and case-sensitive, ranking is score
descending then document/chunk ID, and imports remain stdlib-only plus local
knowledge models.

Run and expect missing `KnowledgeIndex`:

```powershell
python -m pytest tests/knowledge/test_index.py -q -p no:cacheprovider
```

**Step 2 — implement deterministic corpus loading:**

- read sorted `*.md` paths only in `KnowledgeIndex.__init__`;
- derive `document_id` as `doc_` plus underscore-normalized file stem;
- read H1 as document title and comma-separated `Tags:` as document tags;
- create one chunk per H2 section in file order;
- derive IDs as `chunk_<stem>_<zero-based ordinal:03d>`;
- set document version to the first 12 hex characters of SHA-256 content;
- keep `source_path` relative to `corpus_root`;
- reject malformed documents with clear `ValueError`.

**Step 3 — implement normalization/ranking:**

```python
def _tokens(text: str) -> tuple[str, ...]:
    seen: set[str] = set()
    output: list[str] = []
    for token in re.split(r"[\W_]+", text.casefold()):
        if token and token not in seen:
            seen.add(token)
            output.append(token)
    return tuple(output)
```

Match query terms against tokens from title, heading path, excerpt, and tags.
Strip query/chunk tags and compare exact strings without casefold. Rank by
`-(len(matched_terms) + len(matched_tags))`, then `document_id`, then
`chunk_id`. Return the first `max_results`. Generate a deterministic `know_` ID
from canonical query, tags, and ordered match IDs.

**Step 4 — GREEN and regression:**

```powershell
python -m pytest tests/knowledge/test_index.py tests/test_architecture_boundaries.py -q -p no:cacheprovider
python -m pytest -q -p no:cacheprovider
python -m ruff check --no-cache src tests
python -m mypy --no-incremental src
```

**Step 5 — commit:**

```powershell
git add src/signal_diag/knowledge tests/knowledge tests/test_architecture_boundaries.py
git commit -m "feat: add deterministic S1 knowledge retrieval"
```

---

## Task 5: Extend Agent contracts, ScriptedPlanner, and real-model prompt

**Test IDs:** T113–T116

**Files:**

- Modify: `src/signal_diag/agent/models.py`
- Modify: `src/signal_diag/agent/state.py`
- Modify: `src/signal_diag/agent/policies.py`
- Modify: `src/signal_diag/agent/planner.py`
- Modify: `src/signal_diag/agent/__init__.py`
- Create: `tests/agent/test_phase3_models.py`
- Modify: `tests/agent/test_scripted_planner.py`
- Modify: `tests/agent/test_real_llm_planner.py`

**Step 1 — write RED model tests:**

```python
def test_t113_evaluate_rules_decision_validation() -> None:
    decision = EvaluateRulesDecision(
        profile_id="profile_s1_distortion",
        evidence_refs=("ev_clip_001",),
        purpose="apply configured limits",
    )
    assert decision.decision_type == "evaluate_rules"
    with pytest.raises(ValidationError):
        EvaluateRulesDecision(profile_id="bad", purpose="x")


def test_t114_retrieve_knowledge_requires_query() -> None:
    with pytest.raises(ValidationError):
        RetrieveKnowledgeDecision(query_text="", purpose="explain")


def test_t115_context_uses_immutable_snapshots() -> None:
    context = planner_context(
        rule_evaluation_batches=(batch,),
        knowledge_retrievals=(retrieval,),
    )
    assert isinstance(context.rule_evaluation_batches, tuple)
    assert isinstance(context.knowledge_retrievals, tuple)
```

Test T116 by constructing `DiagnosisState` and appending to its four new fields.
Add parser/fake-client tests for both new discriminator values, and a
`ScriptedPlanner` test whose consecutive steps return `EvaluateRulesDecision`
and `RetrieveKnowledgeDecision`.

Run:

```powershell
python -m pytest tests/agent/test_phase3_models.py tests/agent/test_scripted_planner.py tests/agent/test_real_llm_planner.py -q -p no:cacheprovider
```

Expected RED: missing decision models/fields.

**Step 2 — implement additive models and state:**

- add the two frozen decision models and extend the discriminated union;
- add `rule_refs` and `knowledge_refs` to `DiagnosisClaim`;
- add batch/retrieval tuples to `PlannerContext`, `StructuredDiagnosis`, and
  `AgentRunResult` with empty defaults;
- add two lists and two integer counters to `DiagnosisState`;
- extend `TerminationReason` with both exact budget reasons;
- extend `AgentLimits` with defaults 4 and `ge=0`;
- preserve every Phase 2 field/default.

**Step 3 — update planner behavior:**

Bump `PROMPT_VERSION` to `v0.2-s1-planner-4`. Add exact JSON examples for
`evaluate_rules` and `retrieve_knowledge`, instruct the product planner to use
`profile_s1_distortion`, cite only IDs present in context, and treat knowledge
as explanation rather than numerical Evidence. Extend normalization only for
the two new top-level branch wrappers; do not infer missing profile IDs or
queries.

```python
elif "evaluate_rules" in normalized and isinstance(normalized["evaluate_rules"], dict):
    branch = normalized.pop("evaluate_rules")
    normalized = {**normalized, **branch, "decision_type": "evaluate_rules"}
elif "retrieve_knowledge" in normalized and isinstance(normalized["retrieve_knowledge"], dict):
    branch = normalized.pop("retrieve_knowledge")
    normalized = {**normalized, **branch, "decision_type": "retrieve_knowledge"}
```

**Step 4 — GREEN and regression:**

```powershell
python -m pytest tests/agent/test_phase3_models.py tests/agent/test_scripted_planner.py tests/agent/test_real_llm_planner.py -q -p no:cacheprovider
python -m pytest -q -p no:cacheprovider
python -m ruff check --no-cache src tests
python -m mypy --no-incremental src
```

**Step 5 — commit:**

```powershell
git add src/signal_diag/agent tests/agent
git commit -m "feat: extend planner contracts for rules and knowledge"
```

---

## Task 6: Integrate rule actions and rule budget into runtime

**Test IDs:** T117, rule portion of T120

**Files:**

- Modify: `src/signal_diag/agent/runtime.py`
- Create: `tests/agent/test_phase3_runtime.py`

**Step 1 — write RED runtime tests:**

Use counting injected fakes that implement only the frozen protocols. Prove:

- limit 0 rejects before loader/engine execution and returns
  `max_rule_evaluations`;
- counter increments before a dependency exception and the run ends
  `runtime_error`;
- one successful action appends a batch to the next `PlannerContext` and final
  `AgentRunResult`;
- an equivalent profile/filter request increments no-progress, does not call the
  engine again, and does not consume the rule budget;
- missing loader or engine returns `runtime_error` without implicit loading;
- the original Phase 2 constructor and path still pass unchanged.

```python
@pytest.mark.asyncio
async def test_t117_zero_rule_budget_terminates_before_execution(runtime_parts) -> None:
    engine = CountingRuleEngine()
    result = await build_runtime(
        planner=rule_first_planner(),
        rule_engine=engine,
        limits=AgentLimits(max_rule_evaluations=0),
    ).run(signal_id=runtime_parts.signal_id, user_request="Why distorted?")
    assert result.termination_reason == "max_rule_evaluations"
    assert engine.calls == 0
```

Run and expect constructor/dispatch failures:

```powershell
python -m pytest tests/agent/test_phase3_runtime.py -k "rule or phase2" -q -p no:cacheprovider
```

**Step 2 — add optional dependency injection:**

Add the exact optional constructor arguments from §38.1. Store them without
creating defaults or reading paths. Initialize state counters/lists in
`_initial_state` and expose immutable batch/retrieval snapshots in
`_build_context` and final results.

**Step 3 — dispatch rule decisions:**

For `EvaluateRulesDecision`:

1. apply the same initial `task_assessment` and unsupported-task checks as Tool
   decisions;
2. check budget before execution;
3. reject canonical `(profile_id, evidence_refs)` duplicates through existing
   no-progress semantics without incrementing the counter;
4. validate every non-empty `evidence_ref` belongs to current run Evidence;
5. fail `runtime_error` if loader/engine is absent;
6. increment `rule_evaluation_count` immediately before loader/engine execution;
7. pass `frozenset(evidence_refs)` or `None` to RuleEngine;
8. append the returned batch and reset no-progress;
9. convert dependency exceptions to an explicit error result.

Keep per-run equivalence-key sets local to `run()` so one runtime instance does
not leak state between runs.

**Step 4 — GREEN and regression:**

```powershell
python -m pytest tests/agent/test_phase3_runtime.py -k "rule or phase2" -q -p no:cacheprovider
python -m pytest tests/agent -q -p no:cacheprovider
python -m pytest -q -p no:cacheprovider
```

**Step 5 — commit:**

```powershell
git add src/signal_diag/agent/runtime.py tests/agent/test_phase3_runtime.py
git commit -m "feat: route deterministic rule actions"
```

---

## Task 7: Integrate knowledge actions and extended diagnosis validation

**Test IDs:** T118–T120

**Files:**

- Modify: `src/signal_diag/agent/runtime.py`
- Modify: `src/signal_diag/agent/diagnosis.py`
- Modify: `tests/agent/test_phase3_runtime.py`
- Create: `tests/agent/test_phase3_diagnosis.py`

**Step 1 — write RED tests:**

Mirror the exact T117 checks for knowledge: zero budget, pre-execution counter,
exception, propagation, duplicate `(query_text, stripped tags)` no-progress,
and missing index. Add diagnosis tests that reject unknown rule/knowledge IDs
while preserving the Phase 2 Evidence requirements.

```python
def test_t119_unknown_rule_reference_is_rejected() -> None:
    decision = FinishDecision(
        outcome="supported_fault",
        claims=(DiagnosisClaim(
            claim_id="claim_clip",
            fault_type="clipping",
            statement="Configured clipping rule failed.",
            evidence_refs=("ev_clip_001",),
            rule_refs=("ruleval_missing",),
        ),),
        confidence_label="high",
    )
    with pytest.raises(DiagnosisValidationError, match="unknown rule reference"):
        validate_finish_decision(
            decision,
            known_evidence_ids=frozenset({"ev_clip_001"}),
            known_rule_evaluation_ids=frozenset({"ruleval_real"}),
            known_knowledge_retrieval_ids=frozenset(),
            task_assessment=assessment(),
        )
```

Run:

```powershell
python -m pytest tests/agent/test_phase3_runtime.py tests/agent/test_phase3_diagnosis.py -q -p no:cacheprovider
```

Expected RED: knowledge dispatch and extended validator are absent.

**Step 2 — dispatch knowledge decisions:**

Apply the same assessment and budget order as rule actions. Canonicalize the
duplicate key from exact `query_text` plus whitespace-stripped tags. Invoke
`knowledge_index.retrieve(query_text=..., tags=...)` with the contract default
`max_results=5`, append the result, increment immediately before execution, and
map exceptions/missing dependency to `runtime_error`.

**Step 3 — extend finish validation:**

Change `validate_finish_decision` additively to accept empty-default known rule
and knowledge ID sets so Phase 2 callers remain source-compatible. Validate all
non-empty refs and retain the existing Evidence requirements. Do not infer
threshold semantics from free-text claim wording; T121–T124 explicitly assert
that configured-threshold claims contain supporting rule refs. Knowledge refs
never replace Evidence refs. Copy batches/retrievals into `StructuredDiagnosis`
on accepted finish.

**Step 4 — GREEN and regression:**

```powershell
python -m pytest tests/agent/test_phase3_runtime.py tests/agent/test_phase3_diagnosis.py -q -p no:cacheprovider
python -m pytest tests/agent -q -p no:cacheprovider
python -m pytest -q -p no:cacheprovider
python -m ruff check --no-cache src tests
python -m mypy --no-incremental src
```

**Step 5 — commit:**

```powershell
git add src/signal_diag/agent tests/agent
git commit -m "feat: route knowledge actions and validate trace refs"
```

---

## Task 8: Complete scripted S1 rules/knowledge acceptance

**Test IDs:** T121–T124

**Files:**

- Create: `tests/agent/test_phase3_s1_acceptance.py`
- Modify if shared fixture extraction is justified: `tests/conftest.py`
- Verify: `src/signal_diag/rules/profiles/s1_distortion_v1.yaml`
- Verify: `src/signal_diag/knowledge/corpus/*.md`

**Step 1 — build one deterministic test harness:**

Use real `InMemorySignalRepository`, `SignalToolService`, DSP-backed synthetic
fixtures, `RuleEngine`, `YamlRuleProfileLoader`, and `KnowledgeIndex`. A small
test-only context-aware planner may select deterministic actions and build the
final decision from IDs present in `PlannerContext`; it must never fabricate an
Evidence, rule, or retrieval ID.

Add shared assertions:

```python
def assert_phase3_trace_is_grounded(result: AgentRunResult) -> None:
    evidence_ids = {item.evidence_id for item in result.evidence}
    rule_ids = {
        evaluation.evaluation_id
        for batch in result.rule_evaluation_batches
        for evaluation in batch.evaluations
    }
    knowledge_ids = {item.retrieval_id for item in result.knowledge_retrievals}
    assert result.diagnosis is not None
    for claim in result.diagnosis.claims:
        assert set(claim.evidence_refs) <= evidence_ids
        assert set(claim.rule_refs) <= rule_ids
        assert set(claim.knowledge_refs) <= knowledge_ids
```

**Step 2 — T121 CLEAN:**

Route clipping → harmonic → evaluate rules → finish. Assert all available
clipping and THD limit rules PASS, outcome is `no_supported_fault`, claim cites
negative Evidence and PASS rule IDs, and no knowledge call is forced.

**Step 3 — T122 CLIP:**

Route clipping → evaluate rules → finish. Assert the clipping detected, ratio,
and flat-top rules FAIL for S1-CLIP-SUBFS; harmonic rules are NOT_APPLICABLE due
to no matching Evidence; claim cites clipping Evidence and at least one FAIL
evaluation.

**Step 4 — T123 HARM:**

Route clipping → harmonic → evaluate rules → finish. Assert clipping rules PASS,
the harmonic validity rule PASS, THD rule FAIL at approximately 11.18%, and the
harmonic claim cites THD Evidence plus the THD FAIL evaluation.

**Step 5 — T124 combined and invalid branches:**

Create two test functions under T124:

- combined signal: clipping → harmonic → rules → knowledge query with tags
  `("clipping", "harmonic-distortion")` → finish with two claims; both cite
  Evidence and rule refs, and explanatory claims cite the returned `know_` ID;
- noise: clipping → harmonic invalid → rules → knowledge query tagged
  `inconclusive` → finish inconclusive; the `valid` rule and missing THD rule are
  NOT_APPLICABLE, and no numeric THD/F0 claim is created.

Run RED before adding/finalizing the planner harness:

```powershell
python -m pytest tests/agent/test_phase3_s1_acceptance.py -q -p no:cacheprovider
```

Expected RED: missing complete runtime routes or final trace refs.

**Step 6 — GREEN and full gate:**

```powershell
python -m pytest tests/agent/test_phase3_s1_acceptance.py -q -p no:cacheprovider
python -m pytest -q -p no:cacheprovider
python -m ruff check --no-cache src tests scripts
python -m mypy --no-incremental src
git diff --check
```

Expected: T001–T124 all pass, zero required skip/xfail, no architecture skips.

**Step 7 — commit:**

```powershell
git add tests/agent/test_phase3_s1_acceptance.py tests/conftest.py
git commit -m "test: accept Phase 3 S1 rules and knowledge paths"
```

---

## Task 9: Verify the product planner path and close Phase 3

**Validation layer:** non-CI real-model behavior plus deterministic completion

**Files:**

- Create: `scripts/run_phase3_real_model_eval.py`
- Create after an actual run: `docs/reports/PHASE3_REAL_MODEL_BEHAVIOR_REPORT.md`
- Modify: `docs/README.md`
- Modify: `AGENTS.md` only after every required gate passes

**Step 1 — add a non-CI manual runner:**

Compose `RealLLMPlanner`, real repository/Tools, `RuleEngine`, the explicitly
mapped YAML loader, and `KnowledgeIndex`. Reuse the four Phase 2 S1 signal
definitions but write traces below `real_model_eval_output/phase3/`. Enforce the
same raw-waveform/full-FFT safety check. Never fall back to `ScriptedPlanner`.

The runner records action sequence, rule/knowledge counts, latency, model ID,
prompt version, diagnosis refs, and provider usage when returned. Missing
credentials produce a clear non-zero exit and do not affect pytest.

**Step 2 — unit-check the runner without network:**

Add a `--help` smoke test only if script coverage is already part of project
practice; otherwise rely on Ruff/import verification. Do not add a fake model
result and label it real-model evaluation.

**Step 3 — execute the complete deterministic gate:**

```powershell
python -m pytest -q -p no:cacheprovider
python -m ruff check --no-cache src tests scripts
python -m mypy --no-incremental src
git diff --check
```

Required result: T001–T124 pass, zero skip/xfail, Ruff and mypy pass.

**Step 4 — execute the real path when credentials are configured:**

```powershell
python scripts/run_phase3_real_model_eval.py --output-dir real_model_eval_output/phase3
```

Score selection, observation-driven rule/retrieval decisions, unnecessary
actions, stopping, grounding, and limitations without rerunning until favorable.
If credentials are absent, record “not run — credentials unavailable”; this does
not block deterministic acceptance but must remain visible in the completion
report.

**Step 5 — request independent review:**

Use `superpowers:requesting-code-review` against:

- §32–§40 contract conformance;
- T093–T124 coverage and zero skips;
- Phase 1–2 backward compatibility;
- architecture imports;
- raw waveform/FFT safety;
- claims that cite valid Evidence/rule/knowledge IDs.

Fix findings with `superpowers:receiving-code-review` and rerun the complete
gate. Then use `superpowers:verification-before-completion` before any completion
claim.

**Step 6 — update status and commit:**

Only after all deterministic gates pass, update `AGENTS.md` to mark Phase 3
accepted and Phase 4 gated. Link the actual real-model report from
`docs/README.md`; do not create a passing report if the run did not occur.

```powershell
git add scripts/run_phase3_real_model_eval.py docs/reports docs/README.md AGENTS.md
git commit -m "chore: verify and close Phase 3"
```

---

## Test-ID Coverage Map

| Work item | Required test IDs |
|---|---|
| Task 1 — rule package/models/loader | T093, T094, T095, T097 |
| Task 2 — RuleEngine | T096, T098, T099, T100, T101, T102, T103, T104, T105 |
| Task 3 — knowledge models/corpus | T093 package-boundary portion; T106 prerequisites |
| Task 4 — KnowledgeIndex | T106, T107, T108, T109, T110, T111, T112 |
| Task 5 — Agent contracts/planners/state | T113, T114, T115, T116 |
| Task 6 — rule runtime action | T117, T120 |
| Task 7 — knowledge runtime and diagnosis validation | T118, T119, T120 |
| Task 8 — complete S1 acceptance | T121, T122, T123, T124 |
| Task 9 — accumulated gate and product-path observation | T001 through T124 plus non-CI real-model review |

No Phase 3 ID is left unmapped. T093 and T120 intentionally span more than one
task because their acceptance statements cover both sides of a package/runtime
boundary.

## Definition of Done

Phase 3 is complete only when:

- OQ-003 and profile `1.0.0-demo` are explicitly approved and committed;
- T001–T124 pass with zero required skip/xfail;
- all four former architecture package-absence skips have become passing checks;
- Ruff, mypy, and `git diff --check` pass;
- Phase 2-only runtime construction remains green;
- scripted S1 traces use real DSP, Tools, RuleEngine, and KnowledgeIndex;
- every final reference resolves within the same run;
- no raw waveform/full FFT array enters planner or report context;
- an independent review has no unresolved blocking findings;
- real-model Phase 3 behavior is reported honestly as run/not-run and is not a
  CI requirement.
