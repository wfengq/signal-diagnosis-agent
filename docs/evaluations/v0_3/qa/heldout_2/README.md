# D060 phase C held-out Q&A questions (round 2)

Frozen second held-out question set for result Q&A prompt 1.1 acceptance (D060 C).

**File:** `qa_cases_heldout_2.json`
**SHA-256:** `f73854fce369b512a99f021f28a1c54bde905233512c974578d96d1fb78ccb25`

## Independence

Written from the operator brief only. Did **not** read `src/signal_diag/app/result_qa.py`, `src/signal_diag/agent/qa.py`, `src/signal_diag/evaluation/assets/qa_cases.json`, `docs/evaluations/v0_3/qa/heldout/`, `docs/evaluations/v0_3/qa/live_1/`, `tests/app/test_result_qa.py`, `tests/app/test_result_qa_surfaces.py`, or `tests/app/test_qa_eval.py`. No model calls.

## Distribution

| | Count |
|---|---:|
| Total | 20 |
| `expect=answer` | 15 |
| `expect=decline` | 5 |
| Chinese (`zh`) | 14 |
| English (`en`) | 6 |
| Distinct `run` ids | 18 |
| Sweep-mode questions | 6 |

### Per case (expect × result × mode × language)

| case_id | expect | result | mode | language | run |
|---------|--------|--------|------|----------|-----|
| h2q01 | answer | 有故障 | 参考对比 | zh | `abd9010438d4ad93` |
| h2q02 | answer | 无故障 | 参考对比 | zh | `393940e92c58cf0b` |
| h2q03 | answer | 无法判定 | 标称单音 | zh | `5f7ed6fe137f73b3` |
| h2q04 | answer | 无法判定 | 单文件 | zh | `d4bb668a379dea3b` |
| h2q05 | answer | 有故障 | 参考对比 | en | `aa9b4a91b0253c33` |
| h2q06 | answer | 有故障 | 参考对比 | en | `2be730b9113701de` |
| h2q07 | answer | 有故障 | 标称单音 | zh | `dff3ebd9dffee874` |
| h2q08 | answer | 无故障 | 标称单音 | zh | `ce8b413cf7382c3d` |
| h2q09 | answer | 有故障 | 单文件 | zh | `43bbc0fb08d88ec3` |
| h2q10 | answer | 无故障 | 单文件 | en | `eabaecd422b2eeda` |
| h2q11 | answer | 无法判定 | 单文件 | zh | `3e1ca5f1bc34a5a8` |
| h2q12 | answer | 有故障 | 扫频 | zh | `sweep_hard_clip` |
| h2q13 | answer | 有故障 | 扫频 | zh | `sweep_onset_three_levels` |
| h2q14 | answer | 无故障 | 扫频 | en | `sweep_clean` |
| h2q15 | answer | 有故障 | 扫频 | en | `sweep_recorder_full_scale` |
| h2q16 | decline | 有故障 | 标称单音 | zh | `35967af7b71c5b75` |
| h2q17 | decline | 无法判定 | 扫频 | zh | `sweep_noisy` |
| h2q18 | decline | 无故障 | 参考对比 | zh | `04f4068ec91d2621` |
| h2q19 | decline | 有故障 | 参考对比 | en | `abd9010438d4ad93` |
| h2q20 | decline | 有故障 | 扫频 | zh | `sweep_onset_three_levels` |

### Answer traps

| Trap | case_id |
|------|---------|
| Inconclusive as "no problem" | h2q03, h2q04 |
| Standards / certification | h2q06 |
| Numeric conversion (to dB) | h2q07 |
| What to do next | h2q05 |
| Onset on one-level sweep | h2q12 (`sweep_hard_clip`) |
| Onset on `sweep_onset_three_levels` | h2q13 |
| Ask for a measurement value | h2q08 (nofault THD), h2q09 (fault clipping ratio) |

### Decline themes

| Theme | case_id |
|-------|---------|
| Which part failed | h2q16, h2q17, h2q19 |
| Repair cost | h2q18 |
| Remaining life | h2q20 |
