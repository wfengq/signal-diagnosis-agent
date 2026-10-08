# Result Q&A review (D060 C)

For each sample, mark: answers the question (Y/N), wrong statement (Y/N),
declined correctly when the evidence cannot answer (Y/N/-).
Acceptance needs 0 wrong statements across all samples.

## 1. h2q08 (35967af7b71c5b75, supported_fault, expect decline)

    Q: 这台老收音机用了十几年了，是不是里面电容老化了？能看出是哪个元件出的毛病吗？
    本次测试的证据回答不了这个问题。
    本次运行测量的是单音谐波失真，无法判断是哪个元件老化。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 2. h2q14 (sweep_clean, no_supported_fault, expect answer)

    Q: 扫频这一轮看下来，各频段的谐波失真水平大概怎样？有没有哪个频段偏高？
    本轮扫频在 -12 dB 一个电平下测试，各频段总谐波失真均为 0.00%。
    63 Hz、125 Hz、250 Hz、500 Hz、1000 Hz、2000 Hz、4000 Hz 各频段判定均通过，演示阈值为 5.00%。
    没有哪个频段偏高，本轮未发现受支持的失真问题。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 3. h2q02 (aa9b4a91b0253c33, supported_fault, expect decline)

    Q: 到底是功放芯片烧了还是喇叭单元本身坏了？我想知道该换哪个件。
    本次测试的证据回答不了这个问题。
    本次运行测量的是削波与谐波失真，无法判断是哪个硬件部件损坏。
    建议：降低播放电平后重新测试，确认失真是否随电平减小。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 4. h2q05 (04f4068ec91d2621, no_supported_fault, expect answer)

    Q: 没检出问题挺好，不过削波比例具体测出来是多少？离判定阈值还差多远？
    本次运行测得的削波比例为 0。
    该值低于演示阈值 0.01，判定为通过。
    参考信号的削波比例同样为 0，也低于演示阈值 0.01。
    所有必需规则均通过，未发现可支持的故障。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 5. h2q11 (43bbc0fb08d88ec3, supported_fault, expect answer)

    Q: 好吧，查出问题了。接下来我该怎么做？先干啥后干啥？
    本次运行判定为削波，由机制证据和未通过的削波规则支持。
    削波比例观测值为 0.07625，高于演示阈值 0.01。
    平顶检测规则也未通过，说明波形峰值被限制。
    建议先降低播放电平，再补充参考录音或标称音调，之后可运行扫频测试。
    建议：降低播放电平后重新测试，确认失真是否随电平减小。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 6. h2q15 (sweep_onset_three_levels, supported_fault, expect answer)

    Q: 我一共扫了几档音量，失真是从哪一档开始出现的？
    本次扫频共测试了三档音量：-20 dB、-6 dB 和 0 dB。
    在 -20 dB 档，各频段与满量程检查均通过，未支持失真。
    从 -6 dB 档开始出现失真，63 Hz 至 1000 Hz 的八度带 THD 超过 5.00% 的演示阈值。
    0 dB 档同样支持失真，63 Hz 至 500 Hz 的 THD 明显高于演示阈值。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 7. h2q19 (dff3ebd9dffee874, supported_fault, expect answer)

    Q: 我播放的是1kHz正弦，测出来的基频和我设定的对得上吗？
    对得上：基频相对偏差为0.005582，低于演示阈值0.02，该项检查通过。
    本次运行在标称单音下测得总谐波失真6.95%，高于演示阈值5.00%，该项检查未通过。
    同时削波比0.137高于演示阈值0.01，且检出平顶，削波相关检查未通过。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 8. h2q17 (sweep_recorder_full_scale, supported_fault, expect answer)

    Q: Is it possible the problem is on my recording side and not the amp? I had the interface gain cranked pretty high.
    This run cannot tell which part causes the distortion, so it cannot confirm or rule out your recording side.
    At the hot level the recording reached full scale between 20.6 Hz and 19363 Hz, and the full-scale ratio was 0.3661 against a demo threshold of 0.01.
    Octave-band THD failed the demo threshold at 63 Hz, 125 Hz, 250 Hz, 500 Hz and 1000 Hz, with 8.89% at 63 Hz and 8.88% at the others against 5.00%.
    Checking the recorder gain is a listed next step that could address your question.
    Suggested: Lower the recorder's input gain so the recording itself stays below full scale.
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 9. h2q16 (sweep_hard_clip, supported_fault, expect answer)

    Q: 音量开到多大的时候开始失真？想找到一个安全的上限。
    本次扫频只在 0 dB 这一个电平上做了测试。
    在该电平下，63 Hz 到 1000 Hz 各频段的谐波失真都超过了 5.00% 的演示阈值。
    例如 63 Hz 处观测值为 8.89%，125 Hz 到 1000 Hz 处均为 8.88%。
    由于只测了一个电平，无法给出失真开始出现的音量上限。
    建议：再录一到两个更低的音量，找出失真从哪一档开始。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 10. h2q03 (2be730b9113701de, supported_fault, expect decline)

    Q: 拿去售后修大概要花多少钱？值不值得修？
    本次测试的证据回答不了这个问题。
    本次运行只测量了谐波失真相关的检查，无法回答维修费用或是否值得维修的问题。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 11. h2q10 (eabaecd422b2eeda, no_supported_fault, expect decline)

    Q: I have three more speakers of the same model in the storeroom. Since this one came out clean, can I assume they're all fine too?
    This run's evidence cannot answer that question.
    This run measured one signal and found no supported fault, so it cannot tell you about other units.
    Suggested: Retest with the sweep test to locate distortion by band and level.
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 12. h2q07 (dff3ebd9dffee874, supported_fault, expect decline)

    Q: Which component on the board is causing this — the output transistor, a coupling cap, or the DAC?
    This run's evidence cannot answer that question.
    This run measured clipping and harmonic distortion in a single-tone test, not which part is at fault.
    Suggested: Lower the playback level and test again to see whether the distortion drops.
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 13. h2q01 (abd9010438d4ad93, supported_fault, expect answer)

    Q: 这次测出来的削波比例和THD具体是多少？我想记到测试表里。
    本次测得的削波比例为 0.1339。
    该值高于演示阈值 0.01，因此削波比例检查判定为失败。
    本次运行未给出 THD 数值，只报告了削波比例与平顶检测结果。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 14. h2q06 (ce8b413cf7382c3d, no_supported_fault, expect answer)

    Q: The THD is shown as a percentage. Can you convert that to dB for me? Our spec sheet lists everything in dB.
    This run's evidence cannot answer that question.
    This run measured a nominal single-tone distortion check and found no supported fault.
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 15. h2q12 (d4bb668a379dea3b, inconclusive, expect answer)

    Q: ok so it's inconclusive, not a fail. honestly that basically means my mic preamp is fine, right?
    This run's evidence cannot answer that question.
    This run measured a single signal and reached an inconclusive result, so it cannot confirm that any part is fine.
    Suggested: Add a clean reference recording of the same signal so harmonic growth can be judged.
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 16. h2q04 (393940e92c58cf0b, no_supported_fault, expect answer)

    Q: 这个结果算是符合行业标准了吗？我能直接拿它去当产品认证的依据吗？
    本次测试的证据回答不了这个问题。
    本次运行测量了削波比例、平顶缺失、基频一致性与偶次谐波增长等检查，均未发现可支持的故障。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 17. h2q20 (2be730b9113701de, supported_fault, expect answer)

    Q: Did my reference file and the device recording line up properly? I'm worried clock drift between the two messed up the comparison.
    The contextual analysis validity check passed, so the comparison was accepted as valid.
    The fundamental frequency relative delta was 0.000007, within the demo threshold of 0.02.
    That small relative delta indicates the reference and recording were well aligned.
    The failing check was even harmonic growth at 9.91% against a 5.00% demo threshold.
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:
