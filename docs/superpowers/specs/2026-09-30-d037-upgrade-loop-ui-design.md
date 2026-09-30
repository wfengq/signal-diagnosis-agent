# D037 single-file upgrade loop (Web UI)

**Status:** implemented and merged (PR #12 on
`codex/v0.2-real-world-validation`; operator Feature grant 2026-09-30)

**Date:** 2026-09-30

**Product decisions:** D037; prior guidance design
`docs/superpowers/specs/2026-09-29-single-file-context-guidance-design.md`
(§17 already frozen)

**Plan:** `docs/superpowers/plans/2026-09-30-d037-upgrade-loop-ui.md`

**Related:** CONTRACTS_V0_3_CONTEXTUAL.md §17–§18; T-CX269–T-CX275

## 1. Decision summary

Finish the D037 visitor loop in the Web UI:

1. Demo presets materialize as integer PCM WAV bytes and submit through the
   existing contextual `single_signal` path so inconclusive presets emit
   `context_guidance`.
2. The guidance panel can re-submit the **same held test bytes** as
   `paired_reference` (user-uploaded reference WAV) or `nominal_single_tone`
   (user-typed `nominal_fundamental_hz`).
3. Frozen V0.2 `/api/v1/runs/*` DTOs and routes stay unchanged and do not gain
   `context_guidance`. DSP, rule thresholds, planner prompts, and causal gates
   stay unchanged. No RealLLM runs for acceptance.

## 2. Approaches considered

| Option | Idea | Verdict |
|--------|------|---------|
| **A** | `GET /api/v1/presets/{id}/wav` → UI holds Blob → all diagnose via existing contextual WAV submit; upgrade resubmits held Blob | **Chosen** |
| B | Contextual synthetic submit + upgrade-by-run-id | Rejected: in-memory store eviction/restart breaks upgrades; still needs held bytes for uploads |

## 3. Normative behavior

### 3.1 Preset WAV route

```text
GET /api/v1/presets/{preset_id}/wav
→ 200 audio/wav
```

- Body is mono 48 kHz 32-bit integer PCM WAV for the Demo catalog ID.
- Byte-identical across calls for a given ID.
- Unknown ID → existing `unknown_preset` (422).
- No planner credentials required.
- Response must not put a preset ID into `Content-Disposition` filename.

Encoder lives under `src/signal_diag/app/` (not `signal/` or `evaluation/`).

### 3.2 Held test signal (UI)

After a first contextual submit (upload or preset), the UI keeps:

- `blob`: exact test WAV bytes used for that submit
- `filename`: upload name, or fixed `input.wav` for every preset
- `channel`, `userRequest` from the first submit
- last `context_guidance` for upgrade affordances

Reload clears held state. Measured F0 never writes into the Hz field.

### 3.3 Upgrade CTA

When `context_guidance` is present:

- **paired_reference:** user picks a reference file; UI posts held test blob +
  reference to contextual WAV with `mode=paired_reference`.
- **nominal_single_tone:** user types Hz (empty by default); UI posts held test
  blob with `mode=nominal_single_tone`, `stimulus_kind=single_tone`, and the
  typed Hz.

No UI control may auto-select `clean_periodic` as a reference (that would inject
generator-known stimulus). Users may still upload any WAV they choose.

### 3.4 Preset submit path

Web UI preset branch:

1. `GET /api/v1/presets/{id}/wav`
2. submit bytes as `test_file` named `input.wav` via
   `POST /api/v1/contextual-runs/wav` with `mode=single_signal`

Legacy `POST /api/v1/runs/synthetic` remains on the server for frozen V0.2
compatibility and CLI/API clients; the Web UI stops calling it.

### 3.5 Prompt leak rule

When the UI submits a preset-derived WAV, the multipart filename must be
`input.wav` so no Demo preset ID enters `PlannerContext.signal_meta.filename`
(CONTRACTS_V0_2 §57 / planner prompt packing).

## 4. Non-goals

- Softening single_signal harmonic gates
- Prefilling nominal Hz from Evidence F0
- Adding `context_guidance` to V0.2 snapshots/reports
- RealLLM acceptance runs
- Second diagnosis domain (D016 backlog)

## 5. Contracts and tests

- Freeze §18 in `docs/CONTRACTS_V0_3_CONTEXTUAL.md`.
- Register T-CX269–T-CX275 in `docs/TEST_PLAN_V0_3_CONTEXTUAL.md`.
- Update T277 / T-CX268 UI string assertions to the contextual preset path
  (authorized UI evolution; V0.2 server routes remain).

## 6. Verification

- ScriptedPlanner pytest for route fidelity, leak check, guided preset run,
  upgrade resubmit, UI static checks.
- Labeled browser walkthrough with ScriptedPlanner-injected test app (product
  serve without credentials still fail-closes submissions).
- No RealLLM.

## 7. Authorization

Operator Feature grant 2026-09-30 (quoted):

> 授权 Feature：D037 单文件升级闭环 Web UI。…preset 走 contextual
> single_signal…guidance 面板可用上传参考或用户手输频率重提
> paired/nominal。…不要 RealLLM。
