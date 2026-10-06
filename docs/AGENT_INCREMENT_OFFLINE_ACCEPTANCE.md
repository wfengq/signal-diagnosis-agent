# S1 agent-increment offline acceptance

Study `study_s1_agent_increment_1`. This record covers the scripted
offline path only. It is not a RealLLM quality result and it does not
switch the product default prompt away from `v0.3-s1-planner-9.11`.

Held-out manifest hash (frozen with seed `20261006` and template id
`heldout-templates-1.0`):

```text
02590e499a14af67850cb244365042fad1d5b730c03f06901a7a5d44716ff11f
```

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
