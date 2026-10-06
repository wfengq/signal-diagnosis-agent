# Results report: `study_s1_agent_increment_1`

| Field | Value |
|---|---|
| Date | 2026-10-06 |
| Status | Complete. One held-out run (H1), under frozen prompts. |
| Question | On two task families that a fixed pipeline handles poorly by construction, how many more cases does the agent get right than the strongest fixed pipeline? |
| Decision record | D045 (definitions, scoring correction, round notes, stage F, safety reading), D046 |
| Design / plan | `docs/superpowers/specs/2026-10-06-s1-agent-increment-design.md`, `docs/superpowers/plans/2026-10-06-s1-agent-increment.md` |
| Contract | `docs/CONTRACTS_V0_3_CONTEXTUAL.md` §24 |

## 1. Verdict

| Family | Primary metric | Agent | Strongest fixed | Increment | Pre-registered label |
|---|---|---|---|---|---|
| T1 free-text intake | first draft, all four context fields correct | **22/24** | 17/24 | **+5** | **measurable increment** (line: ≥ +3) |
| T2 localized faults | correct conclusion | **18/24** | 18/24 | **0** | **no significant increment** |

Agent safety, read per the operator's 2026-10-06 decision (§4): **0 unsupported positive conclusions in 48 cases**, and evidence traceability **1.0**.

In plain terms:

- **T1:** reading a free-text description into structured context is where the agent adds measurable value over a keyword/regex parser.
- **T2:** on localized faults, the agent reaches the same correctness as an exhaustive segment scan with about 8.6 times fewer tool calls. Fewer calls is an efficiency gain, not a correctness gain, so it does not count toward the pre-registered increment.

## 2. Setup

- **Model:** DeepSeek `deepseek-v4-flash`, with reasoning disabled, JSON output and temperature 0.
- **Frozen identity** (`study_s1_agent_increment_1/prompt_freeze_record.json`, equal to `runs/heldout_h1/identity.json`):
  - planner `v0.3-s1-planner-9.15` (sha256 `ad3d27ed…455c`)
  - intake `v0.3-s1-intake-1.1` (sha256 `a41827a6…a3c9`)
  - neutral diagnosis request (sha256 `243fdcb0…b71d`)
  - product tree `99719634…b1e6`
- **Product default is unchanged.** The product still runs `v0.3-s1-planner-9.11`. Nothing in this study switches it.
- **Arms**, each case run once with no retry-and-pick:
  - `agent`: the live agent.
  - `strong_fixed`: B1, a deterministic keyword/regex intake for T1; B2, an exhaustive 0.25 s / 50 %-overlap segment scan on every channel for T2.
  - `weak_fixed`: B0, which ignores the text and analyses the whole file.
- **Cases:** 24 dev and 24 held-out per family. The held-out manifest is frozen (sha256 `eeccb3d8…5f61`, seed 20261006).
- **Call budget:**

  | Stage | HTTP calls | Cap |
  |---|---|---|
  | D1 (dev, 5 rounds) | 480 | 1,500 |
  | H1 (held-out, once) | 217 | 1,008 |
  | **Total** | **697** | |

  No run hit a cap.

## 3. Held-out results by arm

**T1 (24 cases: 8 clean nominal-tone, 4 insufficient-information, 12 paired-reference faults)**

| Arm | First draft all correct | Field accuracy | Downstream conclusion (secondary) | Unsupported positive |
|---|---|---|---|---|
| agent | 22 | 0.98 | 16 | 0 |
| strong_fixed (B1) | 17 | — | 12 | 4 |
| weak_fixed (B0) | 4 | — | 12 | 0 |

**T2 (24 cases: 8 clean, 4 insufficient, 6 segment-harmonic, 6 clipping)**

| Arm | Correct conclusion | Clipping cases localized | Tool calls | Unsupported positive |
|---|---|---|---|---|
| agent | 18 | 6/6 | 96 | 0 |
| strong_fixed (B2) | 18 | 6/6 | 824 | 0 |
| weak_fixed (B0) | 18 | 0/6 | 56 | 0 |

Every agent run finished normally: 48 of 48 ended `planner_finished`, and no run recorded `run_errors`.

## 4. Safety reading (operator decision, 2026-10-06)

`report.json` computes `safety_hard_pass` over all three arms. On T1 it reads **false** with 4 unsupported positives. All four come from the `strong_fixed` arm: its scripted stand-in judge claimed a fault on the clean cases `held-t1-00`, `-02`, `-04` and `-06`.

The design states the hard conditions for the system under evaluation (§4.2: unsupported positive conclusions must be 0, traceability must be 1.0). The operator therefore decided that the safety conditions apply to the agent arm.

Under that reading, T1 records a measurable increment with agent safety passed. The baseline's four false alarms are reported here rather than hidden. `report.json` is unchanged and keeps the all-arm figure.

## 5. What drives each result

**T1 (+5).** The held-out texts are more colloquial than the dev texts. The regex intake missed 7 drafts, the agent 2.

- **Regex misses** (`-05`, `-18` to `-23`), re-derived offline by running B1 on the same texts:
  - **Full-width `Ｈｚ`** hides the frequency (`-05`, `-22`).
  - **Reference cues outside its marker list** ("先前那份叫 …", "同事说先听 …", "你先听 …", the typo "参靠文件") lose the reference file, so the whole paired context collapses to `single_signal` (`-18`, `-19`, `-21`, `-22`).
  - **No sine marker it recognizes**, including the typo "正玄", leaves `stimulus_kind` empty (`-18`, `-20`, `-22`, `-23`).
- **Agent misses** (`-18`, `-20`): `stimulus_kind` was left empty. The text gives a nominal frequency ("标称写的是 440 Hz") but never says "sine" or "single tone".
- **Corrections:** the simulated user corrected nothing in any agent draft (0 corrections).

**T2 (0).** All three arms agree on every case: 18 correct, the same 6 wrong.

- **Clipping:** a short clipped span crosses the 1 % demonstration threshold inside a window. The agent's four-call plan therefore finds and localizes it, just like the 14- to 90-call scan.
- **The 6 errors:** the segment-harmonic cases, which no arm can answer (§6.1).
- **What distinguishes the arms is cost and localization, not correctness.** The agent localizes 6/6 with 96 calls, where B2 needs 824. The whole-file arm B0 reaches the same correctness with 56 calls but localizes nothing.

## 6. Limits that bound these numbers

1. **Six T2 cases are unanswerable by any arm.** At 8 kHz, automatic F0 estimation locks onto a subharmonic (about 87.9 Hz) of the 440 Hz tone, over the whole file and over the 1.0–1.25 s fault window. Harmonic analysis without a stated fundamental is therefore invalid. The same tone at 48 kHz is estimated correctly (D045, round 2 note). These cases cost every arm the same, so the T2 increment is unaffected, but T2 correctness tops out at 18/24.
2. **Held-out T1 clean cases state the wrong frequency.**
   - The eight clean nominal-tone cases reuse two WAVs whose tone is 220 Hz, while their texts state 440 Hz or 1000 Hz, rendered from templates. The labels say `no_supported_fault`.
   - The agent takes the user's stated frequency, which is the T1 task. The diagnosis then correctly finds that the measured fundamental contradicts it and answers `inconclusive`.
   - As a result the agent scores 0/8 downstream on these cases, while the scripted judge scores 4 correct and 4 false alarms.
   - The primary metric is unaffected: the truth's nominal field equals the stated text.
   - This is a case-construction defect. The downstream comparison should be read with it in mind.
3. **T1 downstream is not a paired comparison.** The fixed arms' downstream conclusions come from a scripted stand-in judge, not the live planner. It is reported as secondary only.
4. **The dev clean-control labels conflict with their texts.** `dev-t1-00` to `-03` state a tone frequency but are labelled `single_signal` with no frequency (D045, round 2 note). This affected dev numbers only. No held-out label has this pattern.
5. **Scale and generality.**
   - One run of 24 cases per family, with no confidence interval: a +5 on 24 is a measured difference, not a significance test.
   - One model.
   - Case texts and the harness come from the same project.
   - The audio is synthetic or reused from earlier studies.
6. **Development exposure.**
   - Prompts were iterated over five dev rounds and frozen before H1.
   - The held-out audio was examined once, deterministically and without a model, only to confirm that the v9.14 call plan was feasible (D045, round 3 note). Nothing was tuned on it.
   - The scoring correction (a run without a diagnosis is never correct) was approved before any held-out run.

## 7. What D1 found along the way

Each round's problem was a harness or prompt defect rather than model quality. Each is recorded in D045 with a regression test.

| Round | Calls | Finding | Fix |
|---|---|---|---|
| 1 | 49 | Intake request lacked the planner's settings, so 10/12 intake replies were empty | Request settings; empty reply stops the stage (T-CX405) |
| 2 | 50 | Intake prompt named keys without allowed values, so 12/12 drafts failed validation | Intake 1.1; validation failures recorded (T-CX407) |
| 3 | 130 | Call plan exceeded the 4 rule evaluations a run may spend, so 23/24 runs ended undiagnosed | v9.14 plan sized from `AgentLimits` (T-CX408) |
| 4 | 139 | Single-file "no clipping" finish was impossible under the runtime's claim rules, so no-fault runs were rejected; crashed runs scored as correct | v9.15 names `inconclusive`; scoring correction; `run_errors` (T-CX409, T-CX410) |
| 5 | 112 | All 24 runs finished; D1 closed | Stage F |

Every fix after round 2 came with a test that drives the real runtime through the planned call path offline. That class of test would have caught rounds 3 and 4 before any model call.

## 8. What this does and does not authorize

- **It does not change the product.** The product default stays `v0.3-s1-planner-9.11`. Adopting intake 1.1 or planner v9.15 in the product would need its own decision. Before that, the localization plan should be reconciled with D037's conservative single-file policy and with the product's runtime limits.
- **It does not extend beyond these families.** The result covers T1 and T2 as constructed here, on this model.
- **Worth doing next, each under its own authorization:**
  - fix the T2 harmonic cases (sample rate or F0 handling) and the T1 clean-case frequencies;
  - repeat H1 on a fresh held-out set with a confidence interval.

## 9. Artifacts

| Item | Path |
|---|---|
| Held-out run | `study_s1_agent_increment_1/runs/heldout_h1/` (`report.json`, `identity.json`, `ledger.json`, `cases/`) |
| Dev rounds | `study_s1_agent_increment_1/runs/dev_r1/` … `dev_r5/` |
| Prompt freeze | `study_s1_agent_increment_1/prompt_freeze_record.json` |
| Manifest | `study_s1_agent_increment_1/manifest.json` (+ `manifest.sha256`, `SHA256SUMS`) |
| Code | `src/signal_diag/evaluation/agent_increment/`, `src/signal_diag/agent/intake.py`, `src/signal_diag/agent/prompts_v03.py` |
| Tests | T-CX387–T-CX410 in `docs/TEST_PLAN_V0_3_CONTEXTUAL.md` |
