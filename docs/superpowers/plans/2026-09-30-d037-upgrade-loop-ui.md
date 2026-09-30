# D037 upgrade-loop UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> or poteto Feature playbook. Checkbox steps for tracking.

**Goal:** Presets and uploads share one contextual submit path with held-bytes
upgrade CTAs after `context_guidance`.

**Architecture:** Additive read-only preset WAV route + app-layer PCM encoder;
Web UI holds Blob and posts only to contextual WAV; V0.2 synthetic route remains
server-side unused by UI.

**Tech Stack:** Python 3.11+, FastAPI, existing multipart contextual submit,
vanilla JS UI, pytest ScriptedPlanner doubles.

## Global constraints

- Frozen V0.2 `/api/v1/runs/*` DTOs unchanged.
- No DSP / thresholds / prompts / causal-gate edits.
- No RealLLM for acceptance.
- Nominal Hz never auto-filled from F0.
- Preset multipart filename always `input.wav`.

## File map

| File | Responsibility |
|------|----------------|
| `src/signal_diag/app/pcm_wav.py` | 32-bit integer PCM WAV encoder |
| `src/signal_diag/app/presets.py` | `render_demo_preset_wav(preset_id) -> bytes` |
| `src/signal_diag/app/service.py` | expose preset WAV helper if needed |
| `src/signal_diag/app/api.py` | `GET /api/v1/presets/{preset_id}/wav` |
| `src/signal_diag/app/static/app.js` | held blob; preset fetch; upgrade CTA |
| `src/signal_diag/app/static/index.html` | upgrade form controls |
| `docs/CONTRACTS_V0_3_CONTEXTUAL.md` | §18 |
| `docs/TEST_PLAN_V0_3_CONTEXTUAL.md` | T-CX269–275 |
| `tests/app/test_preset_wav.py` | T-CX269–272 |
| `tests/app/test_contextual_service.py` / `test_api.py` / `test_ui.py` | T-CX273–275 |

---

### Task 1: Docs freeze (§18 + T-CX)

- [x] Commit design + §18 + T-CX269–275

### Task 2: Encoder + GET route (T-CX269–272)

- [x] Failing tests for WAV shape, fidelity anchors, unknown ID, filename leak
- [x] Implement `pcm_wav.py` + preset render + API route
- [x] Green; identity bridge if product tree drifts
- [ ] Commit

### Task 3: Guided preset + upgrade service/API tests (T-CX273–274)

- [x] Harmonic preset bytes → guidance
- [x] Upgrade paired/nominal with same test bytes (including after eviction)
- [ ] Commit

### Task 4: UI wiring (T-CX275) + T277/T-CX268 supersession

- [x] Held blob; preset GET; upgrade forms; remove UI synthetic POST
- [x] Update static UI tests
- [ ] Commit

### Task 5: Verify + PR

- [ ] Focused + full pytest; ruff; mypy; architecture; git diff --check
- [ ] Browser walkthrough with ScriptedPlanner test app (labeled)
- [ ] Open PR
