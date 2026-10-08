# D060 phase C held-out Q&A questions, round 3

Frozen held-out question set for accepting result Q&A 1.2 (§33.2).

**File:** `qa_cases_heldout_3.json`
**SHA-256:** `5833302070a5f096ed3f2d8bb19a761ae9d1f6102bfc269cc383f53e91d2cc47`

## Provenance and independence

- Written by a fresh Claude subagent with no prior context, from the round-3 brief
  only. It read no repository file, saw none of the earlier question sets, the
  checker, the prompt or any live run, and made no call to the answering model.
- Checked before freezing: no question equals any of the 100 earlier questions
  (development, first held-out, #104, round 2). The highest text similarity is 0.61:
  h3q20 and round-2 h2q10 both ask whether other units of the same model share the
  result, in different words.
- The answering model is DeepSeek; the question author is a separate Claude subagent.

## Distribution

| | Count |
|---|---:|
| Total | 20 |
| `expect=answer` | 15 |
| `expect=decline` | 5 |
| Chinese (`zh`) | 14 |
| English (`en`) | 6 |
| Distinct `run` ids | 20 |
| Sweep questions | 6 |

| case_id | expect | result | mode | language | run |
|---------|--------|--------|------|----------|-----|
| h3q01 | answer | 无法判定 | 参考对比 | zh | `91280fa05c6dfd2a` |
| h3q02 | answer | 无法判定 | 单文件 | zh | `54c6b454b876f8f7` |
| h3q03 | answer | 有故障 | 参考对比 | zh | `84fd2af41fdc1d54` |
| h3q04 | answer | 无故障 | 扫频 | en | `sweep_all_clean_two_levels` |
| h3q05 | answer | 无故障 | 标称单音 | zh | `207890c0f8d99c8b` |
| h3q06 | answer | 无故障 | 参考对比 | zh | `f159f483605aed01` |
| h3q07 | answer | 无法判定 | 单文件 | zh | `651c196e5385a893` |
| h3q08 | answer | 有故障 | 标称单音 | en | `7fd4173cde11c0e3` |
| h3q09 | answer | 有故障 | 扫频 | zh | `sweep_soft_one_level` |
| h3q10 | answer | 有故障 | 扫频 | zh | `sweep_onset_three_levels` |
| h3q11 | answer | 无故障 | 参考对比 | zh | `e333ac4a1bdcbd32` |
| h3q12 | answer | 有故障 | 参考对比 | en | `6334f80c9b6b30be` |
| h3q13 | answer | 无法判定 | 扫频 | zh | `sweep_wrong_stimulus` |
| h3q14 | answer | 无故障 | 单文件 | zh | `2a0d47d7d4f05d7f` |
| h3q15 | answer | 无故障 | 扫频 | en | `sweep_polynomial_two_levels` |
| h3q16 | decline | 有故障 | 单文件 | zh | `675073735bc06f76` |
| h3q17 | decline | 有故障 | 标称单音 | zh | `f4ba6f42e587256c` |
| h3q18 | decline | 有故障 | 参考对比 | en | `313d7f95b2e95656` |
| h3q19 | decline | 无法判定 | 标称单音 | zh | `76054f40e6aeec75` |
| h3q20 | decline | 无法判定 | 扫频 | en | `sweep_drift` |

## Traps

| Trap | case_id |
|------|---------|
| Inconclusive taken as "fine" | h3q01, h3q02 |
| "Does it pass / 合格 / OK to ship" in the user's words | h3q03, h3q04 |
| Standard or certification | h3q05 |
| Unit conversion (THD to dB) | h3q06 |
| What to do next (inconclusive / fault) | h3q07 / h3q08 |
| One-level sweep asked where distortion starts (not revealed) | h3q09 |
| Multi-level sweep: where it starts / louder worse | h3q10, h3q15 |
| Measured value (no-fault run / fault run) | h3q11 / h3q12 |
| Decline: which part is faulty | h3q16, h3q17, h3q18 |
| Decline: warranty replacement / other units | h3q19 / h3q20 |
