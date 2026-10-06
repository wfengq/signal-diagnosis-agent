# S1 agent-increment offline acceptance

Study `study_s1_agent_increment_1`. This record covers the scripted
offline path only. It is not a RealLLM quality result and it does not
switch the product default prompt away from `v0.3-s1-planner-9.11`.

Held-out manifest hash (frozen with seed `20261006` and template id
`heldout-templates-1.0`):

```text
eeccb3d83996955a9d925343acf1fac992820dc589f98db15597736d78aa5f61
```

The 24 held-out T1 lines are distinct. The template grammar includes
paraphrase, colloquial wording, inversion, irrelevant detail, typos, and
full-width characters. Some blunt sentences that favor B1 remain,
including `参考文件是 {ref}，标称 {hz} Hz 正弦。` and the clean
`这段 {hz} Hz 正弦听着干净，没有参考文件。` Seed `20261006` is unchanged.

T1 ground-truth conclusions are the labels already stored on the reused
WAV, not a placeholder. Development rows come from
`docs/evaluations/v0_3/contextual/development/study_v0_3_contextual_dev_1/contextual_manifest.json`.
Held-out rows come from
`docs/evaluations/v0_3/contextual/validation/study_v0_3_contextual_validation_1/contextual_manifest.json`.
The copied fields are `expected_outcome` and `expected_causal_set`.
`inconclusive` appears only when that source row says `inconclusive`.
A reference file is the WAV whose bytes match `reference_wav_sha256`.
The eight held-out no-fault rows cycle two validation recordings,
`extwav_validation_6bc03693bd8f0023_test.wav` and
`extwav_validation_9f719b53a909854f_test.wav`. The validation manifest
has four distinct `no_supported_fault` test hashes; this study uses two
of them.

Dry-run ceilings, agent arm only, 21 calls per case:

| Split | Cases | Stage cap | Max calls |
| --- | ---: | ---: | ---: |
| dev | 24 | 1500 | 504 |
| heldout | 48 | 1008 | 1008 |

T-CX387–T-CX398 are implemented by tests whose names start with
`test_t_cx<id>_`. The offline end-to-end test is
`test_t_cx398_scripted_arms_write_a_complete_report`. It runs all three
arms on the dev and held-out cases with scripted stand-ins, writes a
report whose identity fields are populated, and records zero HTTP calls.

The Web UI adds a draft-only intake box. It posts to `/api/v1/intake/draft`
and does not submit the existing diagnosis form.

## Batch driver (T-CX400–T-CX404)

`python -m signal_diag.evaluation.agent_increment` now has three mutually exclusive actions:

```text
--dry-run --split {dev,heldout} --cases N          # estimate only, no model
--freeze-prompts --approved-by NAME --approved-at DATE   # stage F record, write-once
--run --split {dev,heldout} [--out DIR]            # live stage; needs DEEPSEEK_API_KEY
```

- `--run --split dev` writes to `<study>/runs/dev_<UTC stamp>/` by default: `identity.json`, one `cases/<case_id>.json` per completed case, `ledger.json`, `report.json`, and `stop_record.json` when a stage stops early.
- `--run --split heldout` refuses without a matching `prompt_freeze_record.json`, outside `<study>/runs/heldout_*`, or when a held-out run already exists.
- Output never contains audio, the API key, or raw provider requests or responses.
- Offline verification uses a fake SDK shaped like the real one (`chat.completions.create` only). D1 round 1 has run (`runs/dev_r1`); see D045.
- Every live diagnosis run receives one neutral request (`DIAGNOSIS_REQUEST`) instead of the case text, because case texts correlate with the label; only the T1 intake reads the case text. The request's hash is in the prompt freeze record. The report's `notes` record this, the localization rule, and that T1 downstream fixed rows are scripted stand-ins.
- D1 round 1 fix (T-CX405): the intake request sends the diagnosis planner's settings (reasoning disabled, JSON object, temperature 0), and empty intake content stops the stage. Round 1's T1 numbers measure the missing settings, not the agent.
- Before D1 round 3 (T-CX406, T-CX407): intake prompt `v0.3-s1-intake-1.1` names every allowed value; validation failures record field locations and error types; the study planner is `v0.3-s1-planner-9.13` (channel and window call plan). See D045 for the two case-set limits found in round 2.
- Before D1 round 4 (T-CX408): the study planner is `v0.3-s1-planner-9.14`, whose call plans fit the runtime's four rule evaluations per run.
- Before D1 round 5 (T-CX409, T-CX410): the study planner is `v0.3-s1-planner-9.15` (single-file no-clipping outcome is `inconclusive`); a run without a diagnosis is never scored correct; case files record `run_errors`.
