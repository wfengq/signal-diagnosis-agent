# S1 HEAD product walkthrough (2026-10-03)

Explanation of what we exercised on the live HEAD product path, which
friction we fixed, and what remains open. This is not a quality certificate
and does not replace the V0.2 **79/80** at `b48790c`.

**Trunk tip at close of this wave:** `dea1c2b` (includes PRs #29–#31).

**Product under test:** `RealLLMPlanner`, prompt `v0.3-s1-planner-9.11`,
default mode `single_signal` (D037). ScriptedPlanner was not used as a product
fallback. OQ-019 / seal / study-campaign work stayed parked (PR #28 left open).

## Why this wave

After D039 landed `observed_facts` on `context_guidance`, the question shifted
from “does the study campaign close?” to “can a person use the single-file
product?” The answer required driving CLI and Web the way a user would, then
fixing only the highest-friction gaps.

## Demo script that worked

Requires a local `DEEPSEEK_API_KEY` and `signal-diag` from a clean sync of
trunk. Do not claim these runs replace sealed evaluation bundles.

1. **Health.** `signal-diag serve --host 127.0.0.1 --port 8765`, then open
   `http://127.0.0.1:8765/`. Lifecycle should show planner ready with
   non-secret identity, or block Run when the key is missing.
2. **Clipping (single file).** Demo preset or WAV for clipping. Expect
   `supported_fault` with a clipping claim; usually no `context_guidance`.
3. **Harmonic (single file).** Demo preset `harmonic_distortion`. Expect
   inconclusive outcome, `context_guidance` that refuses harmonic
   attribution without context, and a same-run `thd_percent` row under
   observed facts (not as a soft diagnosis).
4. **Upgrade (paired).** Same harmonic test WAV plus clean reference
   (`clean_periodic` or another clean WAV). Expect
   `supported_fault` / `harmonic_distortion` when comparison qualifies.
5. **Nominal caution.** Declared fundamental must match the real stimulus.
   The harmonic demo fundamental is about **220 Hz**; declaring **440 Hz**
   stayed inconclusive in this walkthrough.

CLI equivalents used in the wave:

```text
signal-diag diagnose contextual --mode single_signal <wav>
signal-diag diagnose contextual --mode paired_reference <test.wav> --reference <clean.wav>
signal-diag diagnose contextual --mode nominal_single_tone <wav> \
  --nominal-fundamental-hz <hz> --stimulus-kind single_tone
```

Without credentials, product submit must fail closed
(`planner_not_configured`, CLI exit 2 / HTTP 503). That path was checked and
must stay fail-closed.

## Friction fixed in this wave

| Gap | Fix | Landed |
|-----|-----|--------|
| Web UI and CLI text omitted `observed_facts` while HTML listed them | Render facts inside context guidance only (T-CX326) | #29 → `cea3880` |
| UI never read `/api/v1/health`; users discovered missing planner only after submit | Load health on bind; show readiness; disable Run when unconfigured (T-CX327) | #30 → `77f9500` |
| Guidance showed wire enums (`paired_reference`, raw `reason_codes`) | Human labels aligned with the mode selector; drop redundant reason-code line in UI (T-CX328) | #31 → `dea1c2b` |

## Still open (product)

These were seen but not patched in this wave. None of them block the demo
script above.

- **Browser-held upgrade path.** Upgrade controls exist after a Web run that
  holds test bytes; this wave verified the CLI upgrade path end-to-end more
  thoroughly than a full browser click-through of the upgrade buttons.
- **CLI still prints wire field names** (`reason_codes`, `unlockable_modes`).
  Fine for operators; Web was prioritized for human copy.
- **First-run source default** remains WAV upload, not Demo preset. Preset is
  faster for demos; changing the default needs an explicit product call.
- **HEAD reports stay uncertified** by Phase 4.3.1. Do not quote HEAD scores
  as the V0.2 **79/80**.

## Out of scope on purpose

- OQ-019 / D041 residual gates and PR #28 (study proof binding; H=partial).
- Formal seal, token ceilings, or a new RealLLM evaluation campaign.
- Framework or UI-stack replacement. The S1 vertical slice already owns
  DSP → tools → rules → planner → surfaces; this wave polished the default
  user loop.

## Judgment

The technical route for “make S1 usable on HEAD” is sound: keep the narrow
evidence-gated product, default to conservative single-file diagnosis, and
fix presentation gaps that hide already-computed state. Small PRs were the
right grain once D037/D039 behavior existed. Broader competitor or component
surveys are optional later for positioning, not a prerequisite for this
demo loop.

## Related

- [CONTRACTS_V0_3_CONTEXTUAL.md](CONTRACTS_V0_3_CONTEXTUAL.md) §17–§18
- [TEST_PLAN_V0_3_CONTEXTUAL.md](TEST_PLAN_V0_3_CONTEXTUAL.md) T-CX326–T-CX328
- [DECISIONS.md](DECISIONS.md) D037, D039
- V0.2 acceptance anchor remains `b48790c` / prompt `v0.2-s1-planner-8.1`
