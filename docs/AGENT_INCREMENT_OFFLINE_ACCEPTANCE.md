# S1 agent-increment offline acceptance

Study `study_s1_agent_increment_1`. This record covers the scripted
offline path only. It is not a RealLLM quality result and it does not
switch the product default prompt away from `v0.3-s1-planner-9.11`.

Held-out manifest hash (frozen with seed `20261006` and template id
`heldout-templates-1.0`):

```text
2f989e736d2b3d4f28c43cd923eeb89e43dee4d1d2d5dec7e6ac6d489975e95f
```

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
