# D060 phase C held-out Q&A questions, round 4 (last round)

Frozen held-out question set for accepting result Q&A 1.3 (§33.3).

**File:** `qa_cases_heldout_4.json`
**SHA-256:** `b4897fc48e250c8d1e49ae9ea8ad13b908bc43e99291d83bbda66b0b0bbf25b3`

## Provenance and independence

- Written by a fresh Claude subagent with no prior context, from the round-4 brief
  only. It read no repository file, saw none of the earlier question sets, the
  checker, the prompt or any live run, and made no call to the answering model.
- Checked before freezing: no question equals any of the 120 earlier questions.
  The highest text similarity is 0.67: h4q02 and round-2 h2q02 both ask whether the
  amplifier chip or the speaker unit failed, in different words (a decline question).
- The answering model is DeepSeek; the question author is a separate Claude subagent.

## Stopping rule (operator, 2026-10-08)

This is the last round. If live_4 does not reach a validation pass rate of 0.9 and
a decline rate of 0.9, result Q&A stays template-only and the model path stays off.

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
| h4q01 | answer | 无法判定 | 参考对比 | zh | `163185980dc8f7a4` |
| h4q02 | decline | 有故障 | 参考对比 | zh | `aa9b4a91b0253c33` |
| h4q03 | answer | 无故障 | 参考对比 | zh | `393940e92c58cf0b` |
| h4q04 | answer | 无法判定 | 扫频 | en | `sweep_noisy` |
| h4q05 | answer | 无故障 | 标称单音 | zh | `ce8b413cf7382c3d` |
| h4q06 | answer | 有故障 | 参考对比 | zh | `abd9010438d4ad93` |
| h4q07 | decline | 有故障 | 参考对比 | en | `2be730b9113701de` |
| h4q08 | answer | 无法判定 | 单文件 | zh | `d4bb668a379dea3b` |
| h4q09 | answer | 有故障 | 扫频 | zh | `sweep_hard_clip` |
| h4q10 | answer | 有故障 | 标称单音 | en | `dff3ebd9dffee874` |
| h4q11 | answer | 有故障 | 单文件 | zh | `43bbc0fb08d88ec3` |
| h4q12 | answer | 有故障 | 扫频 | zh | `sweep_onset_three_levels` |
| h4q13 | decline | 无故障 | 单文件 | zh | `eabaecd422b2eeda` |
| h4q14 | answer | 无故障 | 参考对比 | en | `04f4068ec91d2621` |
| h4q15 | answer | 有故障 | 标称单音 | zh | `35967af7b71c5b75` |
| h4q16 | decline | 无法判定 | 标称单音 | zh | `5f7ed6fe137f73b3` |
| h4q17 | answer | 有故障 | 扫频 | zh | `sweep_recorder_full_scale` |
| h4q18 | answer | 无故障 | 扫频 | en | `sweep_polynomial_two_levels` |
| h4q19 | answer | 无法判定 | 单文件 | zh | `e3c036eb778237c8` |
| h4q20 | decline | 无故障 | 扫频 | en | `sweep_clean` |

## Traps

| Trap | case_id |
|------|---------|
| Inconclusive taken as "fine" | h4q01, h4q04 |
| "Does it pass / 合格 / OK to ship" in the user's words | h4q03, h4q18 |
| National or industry standard, certification (国标, AES, CE) | h4q05, h4q10 |
| Calculation or conversion | h4q06 |
| What to do next (inconclusive / fault) | h4q08 / h4q11 |
| One-level sweep asked where distortion starts (not revealed) | h4q09 |
| Multi-level sweep: louder worse / where it starts | h4q12 |
| Measured value (no-fault run / fault run) | h4q14 / h4q15 |
| Decline: which part is faulty | h4q02, h4q07, h4q16 |
| Decline: lifespan or warranty / other units | h4q13 / h4q20 |
