# D060 phase C held-out Q&A questions, round 2

Frozen held-out question set for accepting result Q&A 1.1 (§33.1).

**File:** `qa_cases_heldout_2.json`
**SHA-256:** `25eb24e0af6f7c94f4624594ecd3d7d078a474931823c6d18aa4f7f58bfe661d`

## Provenance and independence

- Written by a fresh Claude subagent with no prior context, from the round-2 brief only
  (the same brief given to Cursor for #104). It read no repository file and made no
  model call to the answering model.
- Replaces #104: 13 of that set's 20 questions repeated earlier questions word for
  word (12 from the first held-out set, 1 from the development set), most likely
  because the same Cursor session wrote both held-out sets.
- Checked before freezing: no question equals any of the 80 earlier questions
  (development, first held-out, #104), and the highest text similarity to any of
  them is 0.56.
- The answering model is DeepSeek; the question author is a separate Claude
  subagent that never saw the checker, the prompt, live_1 or any earlier questions.

## Distribution

| | Count |
|---|---:|
| Total | 20 |
| `expect=answer` | 15 |
| `expect=decline` | 5 |
| Chinese (`zh`) | 14 |
| English (`en`) | 6 |
| Distinct `run` ids | 18 |
| Sweep questions | 5 |

| case_id | expect | result | mode | language | run |
|---------|--------|--------|------|----------|-----|
| h2q01 | answer | 有故障 | 参考对比 | zh | `abd9010438d4ad93` |
| h2q02 | decline | 有故障 | 参考对比 | zh | `aa9b4a91b0253c33` |
| h2q03 | decline | 有故障 | 参考对比 | zh | `2be730b9113701de` |
| h2q04 | answer | 无故障 | 参考对比 | zh | `393940e92c58cf0b` |
| h2q05 | answer | 无故障 | 参考对比 | zh | `04f4068ec91d2621` |
| h2q06 | answer | 无故障 | 标称单音 | en | `ce8b413cf7382c3d` |
| h2q07 | decline | 有故障 | 标称单音 | en | `dff3ebd9dffee874` |
| h2q08 | decline | 有故障 | 标称单音 | zh | `35967af7b71c5b75` |
| h2q09 | answer | 无法判定 | 标称单音 | zh | `5f7ed6fe137f73b3` |
| h2q10 | decline | 无故障 | 单文件 | en | `eabaecd422b2eeda` |
| h2q11 | answer | 有故障 | 单文件 | zh | `43bbc0fb08d88ec3` |
| h2q12 | answer | 无法判定 | 单文件 | en | `d4bb668a379dea3b` |
| h2q13 | answer | 无法判定 | 单文件 | zh | `3e1ca5f1bc34a5a8` |
| h2q14 | answer | 无故障 | 扫频 | zh | `sweep_clean` |
| h2q15 | answer | 有故障 | 扫频 | zh | `sweep_onset_three_levels` |
| h2q16 | answer | 有故障 | 扫频 | zh | `sweep_hard_clip` |
| h2q17 | answer | 有故障 | 扫频 | en | `sweep_recorder_full_scale` |
| h2q18 | answer | 无法判定 | 扫频 | zh | `sweep_noisy` |
| h2q19 | answer | 有故障 | 标称单音 | zh | `dff3ebd9dffee874` |
| h2q20 | answer | 有故障 | 参考对比 | en | `2be730b9113701de` |

## Traps

| Trap | case_id |
|------|---------|
| Inconclusive taken as "fine" | h2q09, h2q12 |
| Standard or certification | h2q04 |
| Unit conversion (THD to dB) | h2q06 |
| What to do next | h2q11 |
| One-level sweep asked where distortion starts (not revealed) | h2q16 |
| Three-level sweep asked where distortion starts | h2q15 |
| Measured value (fault run / no-fault run) | h2q01 / h2q05 |
| Decline: which part is faulty | h2q02, h2q07, h2q08 |
| Decline: repair cost / other devices | h2q03 / h2q10 |
