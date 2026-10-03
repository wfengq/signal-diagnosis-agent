# Single-file observed facts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** plan revised after Codex/operator revise on tip `a680e2d`
(2026-10-03). Spec still approved. Execution requires a separate operator
grant (`授权实现`). Design-only PR #22 must not be treated as implementation
authorization.

**Authorship of commits under `授权实现`:** Implementation authorization covers
Tasks 1–5 file edits and offline verification only. It does **not**
automatically include `git commit`, `git push`, opening an implementation PR,
or merge. Without a separate commit/push/PR grant, leave an uncommitted diff
for independent recheck.

**Goal:** On eligible single-file `context_guidance`, attach deterministic
`observed_facts` copied from same-run valid Evidence that pass an independent
display whitelist (first phase: `thd_percent` from
`analyze_harmonic_distortion`), without restoring v8.1 harmonic
`supported_fault` (D039 / approved design).

**Architecture:** Keep reason selection in `build_context_guidance` unchanged.
Add `ObservedFact` + selection helpers in `app/context_guidance.py`. Default
`observed_facts=()` for old payloads. Render facts in contextual HTML only.
Append a new code-identity row when the live product-tree digest moves.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, existing contextual app
reporting.

**Spec:** `docs/superpowers/specs/2026-10-03-single-file-observed-facts-design.md`

## Global Constraints

- Frozen `CONTRACTS_V0_2.md` §§1–64 and V0.2 `AppRunSnapshot` /
  `DiagnosisReport` / `/api/v1/runs/*` / `diagnose wav` remain byte-stable.
- No DSP, rule-threshold, planner-prompt, or causal-gate changes.
- Prompt stays `v0.3-s1-planner-9.11`; policy stays
  `v9_11_mode_aware_no_fault_recovery`.
- Display whitelist is independent of the §17 reason-selection metric set.
- First phase whitelist is only `thd_percent` /
  `analyze_harmonic_distortion` / **strict finite `float`** (not `int`, not
  `bool`, not `str`) / unit `%`. Do not coerce other types via `float(...)`.
- Empty `observed_facts` is valid. No zero-fill. No derived metrics.
- Summary must not soft-diagnose (`可能是`, `likely`, harmonic fault as
  attribution).
- No RealLLM campaign, seal, HEAD quality claims, or planner-ablation
  budget/ledger/scoring edits.
- Re-check that D039 / T-CX319… are still free at the implementation tip
  before registering them.
- Every task’s requirements include this section.

## File map

| File | Responsibility |
|------|----------------|
| `docs/CONTRACTS_V0_3_CONTEXTUAL.md` | Additive §17: `ObservedFact`, whitelist, selection, compatibility |
| `docs/TEST_PLAN_V0_3_CONTEXTUAL.md` | Register T-CX319–T-CX323 (adjust if tip collision) |
| `src/signal_diag/app/context_guidance.py` | `ObservedFact`, selection, `observed_facts` on model |
| `src/signal_diag/app/contextual_reporting.py` | HTML render of `observed_facts` |
| `tests/app/test_context_guidance.py` | Builder / selection / compatibility tests |
| `tests/app/test_contextual_reporting.py` or extend existing HTML tests | Render coverage |
| `docs/evaluations/v0_3/contextual/development/study_v0_3_contextual_dev_1/code_identity_amendment.json` | Append-only D039 identity row |
| `tests/agent/test_v03_prompt_v9_11.py` | Freeze prior tip digest; assert new tip == live tree |
| design/plan status lines | Mark plan linked; no product merge claim |

---

### Task 1: Register contracts and test IDs

**Files:**
- Modify: `docs/CONTRACTS_V0_3_CONTEXTUAL.md` (§17 and header Test IDs range)
- Modify: `docs/TEST_PLAN_V0_3_CONTEXTUAL.md` (table rows T-CX319–T-CX323)
- Modify: `docs/superpowers/specs/2026-10-03-single-file-observed-facts-design.md`
  (add Plan link; keep implementation-not-authorized until code lands)

**Interfaces:**
- Produces: normative names frozen for implementers in later tasks

- [ ] **Step 1: Re-check free IDs**

```bash
rg -n 'D039|T-CX319|T-CX320|T-CX321|T-CX322|T-CX323' docs/
```

Expected: only design/decision mentions of D039; no prior T-CX319+. If
collisions exist, pick the next free T-CX* block and use that block in every
later task.

- [ ] **Step 2: Amend CONTRACTS §17**

Append under §17 (keep existing reason emission text):

```text
ObservedFact =
  evidence_id, source_tool, call_id, metric, value, unit, validity,
  time_range, channel
  # validity must be "valid"; value/unit/metric/scope match same-run Evidence

ContextGuidance.observed_facts: tuple[ObservedFact, ...]  # may be ()

Display whitelist (first phase; independent of reason metric set):
  metric=thd_percent
  source_tool=analyze_harmonic_distortion
  type=strict finite float  # reject int/bool/str; no float() coercion
  unit=%

Selection: filter whitelist; dedupe by (metric, channel, time_range) keeping
lexicographically smallest evidence_id; order whitelist then evidence_id.
Empty tuple allowed. Reason selection unchanged when facts empty.

Compatibility:
  missing observed_facts on decode → ()
  extra="forbid" consumers must be updated in-repo; out-of-repo old binaries
  not guaranteed
```

Update the document header Test IDs line to include the new T-CX range.

- [ ] **Step 3: Register TEST_PLAN rows**

| ID | Obligation |
|----|------------|
| T-CX319 | harmonic_attribution guidance with qualifying finite-float `thd_percent` Evidence yields non-empty field-faithful `observed_facts` |
| T-CX320 | harmonic reason with no qualifying display Evidence yields `observed_facts=()` with reason codes exactly unchanged |
| T-CX321 | insufficient_evidence path yields `observed_facts=()`; int/bool/str/NaN/Inf/wrong-tool/N/A excluded from display without coercion |
| T-CX322 | old payload without `observed_facts` → `()`; new guidance round-trips through snapshot/report JSON with scope fields intact; soft-diagnosis banned |
| T-CX323 | HTML lists facts only inside the context-guidance section (not Measured Evidence); product_tree identity append-only row binds digest change |

- [ ] **Step 4: Stop for recheck** — leave the contract/test-plan edits in the
  working tree. Do not commit unless a separate commit grant exists.

---

### Task 2: ObservedFact model + selection (T-CX319–T-CX322)

**Files:**
- Modify: `src/signal_diag/app/context_guidance.py`
- Modify: `tests/app/test_context_guidance.py`

**Interfaces:**
- Consumes: `Evidence` from `signal_diag.tools.evidence`
- Produces:
  - `class ObservedFact(BaseModel)` frozen, `extra="forbid"`
  - `ContextGuidance.observed_facts: tuple[ObservedFact, ...] = ()`
  - `build_context_guidance(...)` fills facts per spec §5.4
  - helpers `_select_observed_facts(result, reason_codes) -> tuple[ObservedFact, ...]`

- [ ] **Step 1: Write failing tests**

Extend `tests/app/test_context_guidance.py` (adjust helper to set
`unit="%"` and `source_tool` explicitly):

```python
import math
from signal_diag.app.context_guidance import ContextGuidance, build_context_guidance
from signal_diag.signal.models import TimeRange
from signal_diag.tools.evidence import Evidence


def _evidence(
    *,
    metric: str,
    value: object,
    evidence_id: str = "ev_guide_001",
    tool: str = "analyze_harmonic_distortion",
    unit: str | None = "%",
    validity: str = "valid",
    channel: str = "mixdown",
    time_range: TimeRange | None = None,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source_tool=tool,  # type: ignore[arg-type]
        call_id="call_analyze_harmonic_distortion_000000",
        metric=metric,
        value=value,  # type: ignore[arg-type]
        unit=unit,
        channel=channel,  # type: ignore[arg-type]
        validity=validity,  # type: ignore[arg-type]
        time_range=time_range,
    )


def test_t_cx319_qualifying_thd_emits_field_faithful_facts() -> None:
    tr = TimeRange(start_s=0.0, end_s=1.0)
    ev = _evidence(
        metric="thd_percent",
        value=12.65,  # must be float, not int 12
        evidence_id="ev_analyze_harmonic_distortion_x_002",
        unit="%",
        time_range=tr,
        channel="mixdown",
    )
    result = _result(outcome="inconclusive", evidence=(ev,))
    guidance = build_context_guidance(mode="single_signal", result=result)
    assert guidance is not None
    assert guidance.reason_codes == ("harmonic_attribution_requires_context",)
    assert len(guidance.observed_facts) == 1
    fact = guidance.observed_facts[0]
    assert fact.evidence_id == ev.evidence_id
    assert fact.source_tool == ev.source_tool
    assert fact.call_id == ev.call_id
    assert fact.metric == ev.metric
    assert fact.value == ev.value
    assert fact.unit == ev.unit
    assert fact.validity == "valid"
    assert fact.channel == ev.channel
    assert fact.time_range == ev.time_range
    assert "可能是" not in guidance.summary
    assert "likely" not in guidance.summary.lower()


def test_t_cx320_harmonic_reason_with_empty_display_facts() -> None:
    # Reason set still sees even_order_present; display whitelist does not.
    ev = _evidence(
        metric="even_order_present",
        value=True,
        unit=None,
        evidence_id="ev_guide_eop",
    )
    result = _result(outcome="inconclusive", evidence=(ev,))
    guidance = build_context_guidance(mode="single_signal", result=result)
    assert guidance is not None
    assert guidance.reason_codes == ("harmonic_attribution_requires_context",)
    assert guidance.observed_facts == ()


def test_t_cx321_display_exclusions_keep_harmonic_reason() -> None:
    # Valid thd_percent name keeps reason harmonic; none qualify for display.
    nan_ev = _evidence(
        metric="thd_percent", value=float("nan"), evidence_id="ev_nan"
    )
    inf_ev = _evidence(
        metric="thd_percent", value=float("inf"), evidence_id="ev_inf"
    )
    int_ev = _evidence(metric="thd_percent", value=12, evidence_id="ev_int")
    bool_ev = _evidence(
        metric="thd_percent", value=True, unit="%", evidence_id="ev_bool"
    )
    str_ev = _evidence(
        metric="thd_percent", value="12.65", unit="%", evidence_id="ev_str"
    )
    wrong_tool = _evidence(
        metric="thd_percent",
        value=9.0,
        tool="detect_clipping",
        evidence_id="ev_wrong_tool",
    )
    na = _evidence(
        metric="thd_percent",
        value="not_applicable",
        validity="not_applicable",
        evidence_id="ev_na",
    )
    result = _result(
        outcome="inconclusive",
        evidence=(nan_ev, inf_ev, int_ev, bool_ev, str_ev, wrong_tool, na),
    )
    guidance = build_context_guidance(mode="single_signal", result=result)
    assert guidance is not None
    assert guidance.reason_codes == ("harmonic_attribution_requires_context",)
    assert guidance.observed_facts == ()

    clean = _result(outcome="inconclusive", evidence=())
    g_insufficient = build_context_guidance(mode="single_signal", result=clean)
    assert g_insufficient is not None
    assert g_insufficient.reason_codes == (
        "insufficient_evidence_for_supported_fault",
    )
    assert g_insufficient.observed_facts == ()


def test_t_cx322_compat_old_payload_and_report_round_trip() -> None:
    old = ContextGuidance.model_validate(
        {
            "reason_codes": ("insufficient_evidence_for_supported_fault",),
            "unlockable_modes": ("paired_reference", "nominal_single_tone"),
            "required_inputs": {
                "paired_reference": ("reference_wav",),
                "nominal_single_tone": (
                    "nominal_fundamental_hz",
                    "stimulus_kind=single_tone",
                ),
            },
            "summary": "fixture summary without observed_facts key",
        }
    )
    assert old.observed_facts == ()

    tr = TimeRange(start_s=0.0, end_s=1.0)
    ev = _evidence(
        metric="thd_percent",
        value=12.65,
        evidence_id="ev_rt_001",
        time_range=tr,
    )
    guidance = build_context_guidance(
        mode="single_signal",
        result=_result(outcome="inconclusive", evidence=(ev,)),
    )
    assert guidance is not None
    # Round-trip through real snapshot/report models (not bare ContextGuidance).
    # Reuse completed-snapshot builders from tests/app/test_contextual_models.py
    # (StimulusContext mode=single_signal, attach context_guidance=guidance),
    # then:
    #   payload = snapshot.model_dump(mode="json")
    #   restored = ContextualAppRunSnapshot.model_validate(payload)
    #   fact = restored.context_guidance.observed_facts[0]
    #   assert fact.metric == "thd_percent"
    #   assert isinstance(fact.value, float) and fact.value == 12.65
    #   assert fact.unit == "%"
    #   assert fact.time_range == tr
    #   assert fact.channel == "mixdown"
    #   report = build_contextual_diagnosis_report(restored, generated_at=...)
    #   report2 = ContextualDiagnosisReport.model_validate(
    #       report.model_dump(mode="json")
    #   )
    #   assert report2.context_guidance.observed_facts[0].evidence_id == "ev_rt_001"
```

Also add a dedupe test: two valid finite-float `thd_percent` rows with the
same channel/time_range keep the smaller `evidence_id`.

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/app/test_context_guidance.py -q
```

Expected: FAIL on missing `observed_facts` / `ObservedFact`.

- [ ] **Step 3: Implement minimal builder changes**

In `context_guidance.py`:

```python
import math
from signal_diag.signal.models import ChannelMode, TimeRange
from signal_diag.tools.contracts import ToolName
from signal_diag.tools.evidence import Evidence

class ObservedFact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    evidence_id: str
    source_tool: ToolName
    call_id: str
    metric: str = Field(min_length=1)
    value: bool | int | float | str
    unit: str | None = None
    validity: Literal["valid"] = "valid"
    time_range: TimeRange | None = None
    channel: ChannelMode

# ContextGuidance: add
observed_facts: tuple[ObservedFact, ...] = ()

_DISPLAY_WHITELIST: tuple[tuple[str, ToolName, str | None], ...] = (
    ("thd_percent", "analyze_harmonic_distortion", "%"),
)

_FACTS_SUMMARY_SUFFIX = (
    " Listed observed_facts are same-run measurements and are not a "
    "fault attribution."
)

def _is_finite_float(value: object) -> bool:
    # Strict: reject bool/int/str; do not coerce via float(value).
    return isinstance(value, float) and math.isfinite(value)

def _row_matches_whitelist(item: Evidence) -> bool:
    for metric, tool, unit in _DISPLAY_WHITELIST:
        if item.metric != metric or item.source_tool != tool:
            continue
        if item.validity != "valid" or item.unit != unit:
            continue
        if not _is_finite_float(item.value):
            continue
        return True
    return False

def _select_observed_facts(
    result: AgentRunResult,
    reason_codes: tuple[ContextGuidanceReasonCode, ...],
) -> tuple[ObservedFact, ...]:
    if "harmonic_attribution_requires_context" not in reason_codes:
        return ()
    candidates = [item for item in result.evidence if _row_matches_whitelist(item)]
    best: dict[tuple[str, str, str | None], Evidence] = {}
    for item in candidates:
        key = (
            item.metric,
            item.channel,
            None if item.time_range is None else item.time_range.model_dump_json(),
        )
        prev = best.get(key)
        if prev is None or item.evidence_id < prev.evidence_id:
            best[key] = item
    ordered_metrics = [m for m, _, _ in _DISPLAY_WHITELIST]
    selected = sorted(
        best.values(),
        key=lambda e: (ordered_metrics.index(e.metric), e.evidence_id),
    )
    return tuple(
        ObservedFact(
            evidence_id=e.evidence_id,
            source_tool=e.source_tool,
            call_id=e.call_id,
            metric=e.metric,
            value=e.value,
            unit=e.unit,
            validity="valid",
            time_range=e.time_range,
            channel=e.channel,
        )
        for e in selected
    )
```

Wire into `build_context_guidance` after computing `reasons` / `summary`:

```python
facts = _select_observed_facts(result, tuple(reasons))
if facts:
    summary = summary + _FACTS_SUMMARY_SUFFIX
return ContextGuidance(..., summary=summary, observed_facts=facts)
```

Keep `_HARMONIC_METRICS` reason detection unchanged. Display filtering must
not call `float(value)` on non-floats.

- [ ] **Step 4: pytest green**

```bash
pytest tests/app/test_context_guidance.py -q
```

Expected: PASS

- [ ] **Step 5: Stop for recheck** — leave builder/test edits uncommitted unless
  a separate commit grant exists.

---

### Task 3: HTML render (part of T-CX323)

**Files:**
- Modify: `src/signal_diag/app/contextual_reporting.py` (guidance section)
- Modify or create: `tests/app/test_contextual_reporting.py`

**Interfaces:**
- Consumes: `context_guidance.observed_facts` on report JSON dict
- Produces: HTML subsection listing metric/value/unit/evidence_id

- [ ] **Step 1: Failing render test**

Scope assertions to the guidance section so Measured Evidence cannot
false-green the check. Use a marker id on the facts list.

```python
def test_t_cx323_html_lists_observed_facts_inside_guidance() -> None:
    # Build ContextualDiagnosisReport with:
    # - context_guidance.observed_facts = one thd_percent=12.65 row
    # - result.evidence also containing thd_percent=99.0 (Measured Evidence)
    #   so a naive "12.65"/"thd_percent" search is not enough if facts missing.
    html = render_contextual_report_html(report)
    start = html.index('id="context-guidance"')
    end = html.index('id="measured-evidence"')
    guidance_html = html[start:end]
    measured_html = html[end:]
    assert 'id="observed-facts"' in guidance_html
    assert "thd_percent" in guidance_html
    assert "12.65" in guidance_html
    assert "12.65" not in measured_html  # decoy value only in guidance facts
    assert "99.0" in measured_html
```

Construct the report via helpers in `tests/app/test_contextual_models.py`
/ reporting tests; keep decoy Evidence value distinct from the fact value.

- [ ] **Step 2: pytest fail**

- [ ] **Step 3: Implement** inside the existing `context-guidance` HTML block,
  **before** that section closes and before `measured-evidence`:

```python
facts = guidance.get("observed_facts") or ()
if facts:
    parts.append('<ul id="observed-facts">')
    for fact in facts:
        parts.append(
            "<li>"
            f"{_esc(fact.get('evidence_id'))} "
            f"{_esc(fact.get('metric'))}="
            f"{_esc(fact.get('value'))}"
            f"{'' if fact.get('unit') is None else ' ' + _esc(fact.get('unit'))}"
            "</li>"
        )
    parts.append("</ul>")
```

- [ ] **Step 4: green; stop for recheck** — leave HTML/test edits uncommitted
  unless a separate commit grant exists.

---

### Task 4: Code identity append-only row (rest of T-CX323)

**Files:**
- Modify: `docs/evaluations/v0_3/contextual/development/study_v0_3_contextual_dev_1/code_identity_amendment.json`
- Modify: `tests/agent/test_v03_prompt_v9_11.py`

**Interfaces:**
- Consumes: `contextual_product_tree_sha256()`,
  `contextual_implementation_sha256()`
- Produces: new tip row `d039_single_file_observed_facts`

- [ ] **Step 1: Capture digests after Task 2–3 code exists**

```bash
python - <<'PY'
from signal_diag.evaluation.contextual.calibration import (
    contextual_implementation_sha256,
    contextual_product_tree_sha256,
)
print("implementation", contextual_implementation_sha256())
print("product_tree", contextual_product_tree_sha256())
PY
```

Record the **pre-change** tip digest currently stored on
`d038_planner_ablation_dev_2_token_transport_telemetry` by reading the live
tree hash **before** app edits if still matching; after app edits, freeze that
historical telemetry row to the digest it had at PR #21 merge tip (do not
overwrite other fields except switching the v9_11 test from live equality on
that row to a pinned digest). Append the new D039 row with the new live
`product_tree_sha256`.

- [ ] **Step 2: Failing identity assertion**

Update `tests/agent/test_v03_prompt_v9_11.py`:

- Keep `d038_telemetry["product_tree_sha256"]` as a **pinned** historical
  digest (the value true at the telemetry tip before observed_facts).
- Add `d039` row lookup; assert
  `d039["product_tree_sha256"] == contextual_product_tree_sha256()`.
- Assert `d039["prior_bridge_current_implementation_sha256"]` chains from the
  previous tip’s `current_implementation_sha256`.
- Assert prompt/policy fields unchanged; `model_calls == 0`.
- Assert historical rows (including all D038 rows) remain byte-stable in their
  pinned digests.

Run: `pytest tests/agent/test_v03_prompt_v9_11.py -q` → expect FAIL until JSON
row exists.

- [ ] **Step 3: Append JSON row**

```json
{
  "amendment_id": "d039_single_file_observed_facts",
  "amendment_kind": "append_only_code_identity",
  "created_at_utc": "use datetime.now(UTC).isoformat()",
  "original_calibration_code_sha256": "da72a8e856712af019a4bdd8fbdf7c3c20be59d6593793fb3e91f0f49b2a5ea9",
  "current_implementation_sha256": "call contextual_implementation_sha256()",
  "prior_bridge_current_implementation_sha256": "prior tip row current_implementation_sha256",
  "product_tree_sha256": "call contextual_product_tree_sha256() after app changes",
  "prompt_version": "v0.3-s1-planner-9.11",
  "prompt_sha256": "b4c279dfcbee2d5c22f7eb6d5b4f211555da95bbeb2e2867b68a3f1d11681ca0",
  "causal_policy_version": "v9_11_mode_aware_no_fault_recovery",
  "scope": "D039 single-file observed_facts on context_guidance: additive ObservedFact fields and HTML render; no prompt, causal finish gate, DSP, rule threshold, seal, RealLLM, or planner-ablation budget mutation",
  "qualification_recompute_unchanged": true,
  "calibration_recompute_unchanged": true,
  "selected_threshold_percent_unchanged": 5.0,
  "model_calls": 0
}
```

Do not rewrite prior rows’ digests except the test’s expectation that the
telemetry tip is no longer the live equality anchor.

- [ ] **Step 4: focused green; stop for recheck**

```bash
pytest tests/agent/test_v03_prompt_v9_11.py tests/app/test_context_guidance.py -q
```

Expected: PASS. Leave identity JSON/test edits uncommitted unless a separate
commit grant exists.

---

### Task 5: Closeout verification

**Files:** none required beyond fixes from failures

Do not mark this plan complete until every Step below is green. Focused
suites alone are insufficient.

- [ ] **Step 1: Focused suite (smoke)**

```bash
pytest tests/app/test_context_guidance.py tests/app/test_contextual_reporting.py \
  tests/app/test_contextual_service.py tests/agent/test_v03_prompt_v9_11.py -q
```

Expected: PASS (omit reporting path if that file was not created and the
HTML test lives elsewhere; still run whatever file owns T-CX323 HTML).

- [ ] **Step 2: Full pytest**

```bash
pytest -q
```

Expected: all required tests PASS; zero required skip/xfail.

- [ ] **Step 3: Full-repo Ruff and mypy**

```bash
ruff check .
mypy src
```

Expected: clean.

- [ ] **Step 4: Architecture and whitespace against the implementation baseline**

```bash
pytest tests/test_architecture_boundaries.py -q
git diff --check
```

`git diff --check` is against the uncommitted implementation working tree
(or the authorized commit range if a commit grant was given). Expected:
architecture PASS; no whitespace errors.

- [ ] **Step 5: Stop** — do not seal, do not RealLLM, do not cite HEAD quality
  numbers. Do not `git commit`, `git push`, open an implementation PR, or
  merge unless a separate grant names those actions. Prefer leaving the
  verified uncommitted diff for independent recheck. Optionally update this
  plan header Status to note verification results without claiming merge.

---

## Spec coverage check

| Spec § | Task |
|--------|------|
| 5.1 Data shape | Task 2 |
| 5.2 Display whitelist | Task 1–2 |
| 5.3 Selection / dedupe | Task 2 |
| 5.4 Emission / empty facts | Task 2 |
| 5.5 Compatibility | Task 2 (T-CX322) |
| 5.6 Layer boundary | Global + Tasks 2–3 |
| 5.7 Code identity | Task 4 |
| 5.8 Contracts / tests | Task 1 |
| 5.9 ID re-check | Task 1 Step 1 |
| §6 Authorization | Plan status + Task 5 Step 5 |
| §7 Success criteria | Tasks 2–3 |

## Handoff

After this revise lands on PR #22 and the operator replies `plan ok`,
execution of Tasks 1–5 still requires a separate grant. Suggested text:

```text
授权实现：按 docs/superpowers/plans/2026-10-03-single-file-observed-facts.md
执行 D039 observed_facts Tasks 1–5 文件修改与离线验证；additive V0.3 only；
不 seal；不 RealLLM campaign；不碰 planner-ablation 预算；
不自动 commit/push/开实施 PR/merge（另授）。
```

Commit/push/implementation-PR/merge each need their own named authorization
beyond `授权实现` as written above.
