# D060 phase C held-out Q&A questions

Frozen held-out question set for result Q&A acceptance (D060 C).

**File:** `qa_cases_heldout.json`
**SHA-256:** `b819fe7bde45324bb5cc9dd234419a7465db0c88f6780dfc59ffc650894f7edd`

## Independence

Written from the operator brief only. Did **not** read `src/signal_diag/app/result_qa.py`, `src/signal_diag/agent/qa.py`, `src/signal_diag/evaluation/assets/qa_cases.json`, `tests/app/test_result_qa.py`, `tests/app/test_result_qa_surfaces.py`, or `tests/app/test_qa_eval.py`. No model calls.

## Distribution

| | Count |
|---|---:|
| Total | 20 |
| `expect=answer` | 15 |
| `expect=decline` | 5 |
| Chinese (`zh`) | 14 |
| English (`en`) | 6 |
| Distinct `run` ids | 19 |
| Sweep-mode questions | 6 |

### Per case (expect × result × mode × language)

| case_id | expect | result | mode | language | run |
|---------|--------|--------|------|----------|-----|
| hq01 | answer | 有故障 | 参考对比 | zh | `84fd2af41fdc1d54` |
| hq02 | answer | 无故障 | 参考对比 | zh | `f159f483605aed01` |
| hq03 | answer | 无法判定 | 参考对比 | zh | `91280fa05c6dfd2a` |
| hq04 | answer | 有故障 | 参考对比 | en | `313d7f95b2e95656` |
| hq05 | answer | 有故障 | 标称单音 | zh | `7fd4173cde11c0e3` |
| hq06 | answer | 无故障 | 标称单音 | zh | `207890c0f8d99c8b` |
| hq07 | answer | 无法判定 | 标称单音 | zh | `76054f40e6aeec75` |
| hq08 | answer | 有故障 | 参考对比 | en | `6334f80c9b6b30be` |
| hq09 | answer | 无故障 | 单文件 | en | `2a0d47d7d4f05d7f` |
| hq10 | answer | 无法判定 | 单文件 | zh | `651c196e5385a893` |
| hq11 | answer | 有故障 | 扫频 | zh | `sweep_soft_one_level` |
| hq12 | answer | 无故障 | 扫频 | en | `sweep_all_clean_two_levels` |
| hq13 | answer | 无法判定 | 扫频 | zh | `sweep_wrong_stimulus` |
| hq14 | answer | 无故障 | 扫频 | en | `sweep_polynomial_two_levels` |
| hq15 | answer | 有故障 | 参考对比 | zh | `2ca9870c96ed589d` |
| hq16 | decline | 有故障 | 参考对比 | zh | `773852f7513151f1` |
| hq17 | decline | 无法判定 | 扫频 | zh | `sweep_drift` |
| hq18 | decline | 无故障 | 参考对比 | zh | `e333ac4a1bdcbd32` |
| hq19 | decline | 有故障 | 单文件 | en | `675073735bc06f76` |
| hq20 | decline | 有故障 | 扫频 | zh | `sweep_soft_one_level` |

### Answer traps (brief checklist)

| Trap | case_id |
|------|---------|
| Inconclusive as “no problem” | hq03, hq07 |
| Standards / certification | hq08 |
| Numeric conversion (to dB) | hq15 |
| What to do next | hq04, hq10 |

### Decline themes

| Theme | case_id |
|-------|---------|
| Which part failed | hq16, hq17, hq19 |
| Repair cost | hq18 |
| Remaining life | hq20 |
