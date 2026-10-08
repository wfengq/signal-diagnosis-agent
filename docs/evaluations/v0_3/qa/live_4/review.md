# Result Q&A review (D060 C)

For each sample, mark: answers the question (Y/N), wrong statement (Y/N),
declined correctly when the evidence cannot answer (Y/N/-).
Acceptance needs 0 wrong statements across all samples.

## 1. h4q08 (d4bb668a379dea3b, inconclusive, expect answer)

    Q: 我就录了一个文件上传，结果说不确定。下一步我具体该补什么，才能拿到一个明确的结论？
    本次运行在单文件模式下无法把谐波失真归因，因为没有参考或声明的基频。
    确定性规则既没有支持存在故障，也没有确认不存在故障，因此结论为不确定。
    谐波分析有效性与总谐波失真两项规则均判定为不适用，阈值只是演示阈值。
    要得到明确结论，可以补充参考录音或声明标称音调，也可以改做扫频测试。
    建议：补充一段同一信号的干净参考录音，才能判断谐波是否增加。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 2. h4q13 (eabaecd422b2eeda, no_supported_fault, expect decline)

    Q: 这台音箱用了快三年了，按这次的结果看它还能撑几年？要不要趁保修还没过期赶紧去换新的？
    本次测试的证据回答不了这个问题。
    本次运行只与演示阈值比较，无法给出合格判定或寿命预测。
    本次运行测量了削波比例与总谐波失真，所有规则均通过，未发现可支持的故障。
    建议：补充一段同一信号的干净参考录音，才能判断谐波是否增加。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 3. h4q03 (393940e92c58cf0b, no_supported_fault, expect answer)

    Q: 下周客户要来验收，这次跟参考录音对比的结果能不能直接算合格？我好写进验收单里。
    本次测试的证据回答不了这个问题。
    本次运行只与演示阈值比较，无法给出合格判定。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 4. h4q05 (ce8b413cf7382c3d, no_supported_fault, expect answer)

    Q: 我们准备拿这台去做认证，想问下这次单音测试的失真数值算不算符合国标或者行业标准？
    本次测试的证据回答不了这个问题。
    本次运行只与演示阈值比较，无法给出合格或认证判定。
    该单音测试测得总谐波失真为0.14%，并与5.00%的演示阈值比较。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 5. h4q10 (dff3ebd9dffee874, supported_fault, expect answer)

    Q: Our QA lead keeps asking whether this passes AES or some other recognized distortion standard, or whether it would hold up for CE. What can I tell her from this run?
    This run's evidence cannot answer that question.
    This run only compares measurements with demo thresholds and cannot give a certification verdict.
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 6. h4q15 (35967af7b71c5b75, supported_fault, expect answer)

    Q: 我设的是一个固定频率的单音，这次实际测出来的基频是多少Hz？和我给的标称频率对得上吗？
    本次测试的证据回答不了这个问题。
    本次运行只测了单音的总谐波失真百分比和基频相对偏差，没有给出基频的绝对频率值。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 7. h4q18 (sweep_polynomial_two_levels, no_supported_fault, expect answer)

    Q: We've got a pallet of these going out Friday. Going by this two-level sweep, are we OK to ship, or should I hold them back?
    This run's evidence cannot answer that question.
    This run only compares measurements with demo thresholds and cannot give a certification or shipping verdict.
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 8. h4q14 (04f4068ec91d2621, no_supported_fault, expect answer)

    Q: Looks like it came back clean. Can you just give me the actual measured numbers from this comparison — clipping ratio and the harmonic figure — so I can paste them into my log?
    The clipping ratio measured 0, against a demo threshold of 0.01.
    The even harmonic growth figure measured 0.00%, against a demo threshold of 5.00%.
    The reference clipping ratio also measured 0, against a demo threshold of 0.01.
    The f0 relative delta measured 0.002287, against a demo threshold of 0.02.
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 9. h4q02 (aa9b4a91b0253c33, supported_fault, expect decline)

    Q: 这结果看着挺严重的，到底是功放芯片坏了还是喇叭单元烧了？我该换哪个零件？
    本次测试的证据回答不了这个问题。
    本次运行只与演示阈值比较，无法给出合格判定，也无法判断是哪个零件损坏。
    建议：降低播放电平后重新测试，确认失真是否随电平减小。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 10. h4q16 (5f7ed6fe137f73b3, inconclusive, expect decline)

    Q: 听着有点沙沙的，是不是耳机里面振膜松了或者线圈有问题？要拆开的话该先查哪个元件？
    本次测试的证据回答不了这个问题。
    本次运行只做了单频标称测试，结果是不确定的，无法判断具体元件是否有问题。
    建议：用扫频测试复测，按频段和电平定位失真。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 11. h4q17 (sweep_recorder_full_scale, supported_fault, expect answer)

    Q: 我有点怀疑问题出在录音这一端而不是被测设备本身。从这次的测量里能看出录音电平是不是打满了吗？
    本次运行在 hot 电平下测得满量程比值为 0.3661，演示阈值为 0.01，该检查未通过。
    录音在 20.6 Hz 到 19363 Hz 的扫频范围内达到满量程。
    本次运行只与演示阈值比较，无法给出合格判定。
    建议：调低录音设备的输入增益，避免录音本身达到满刻度。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 12. h4q09 (sweep_hard_clip, supported_fault, expect answer)

    Q: 这次扫频测试，失真是从哪一档音量开始冒出来的？我想知道安全音量大概能开到多大。
    本次扫频只在 0 dB 这一档做了测试，因此只能说该档已出现失真。
    0 dB 下 63 Hz 的谐波失真为 8.89%，超过 5.00% 的演示阈值。
    125 Hz、250 Hz、500 Hz、1000 Hz 的谐波失真均为 8.88%，同样超过 5.00% 的演示阈值。
    本次运行只与演示阈值比较，无法给出安全音量或合格判定。
    建议：再录一到两个更低的音量，找出失真从哪一档开始。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 13. h4q07 (2be730b9113701de, supported_fault, expect decline)

    Q: Which part is actually failing here — the DAC, the output op-amp, or the driver itself? I need to know what to order before I open it up.
    This run's evidence cannot answer that question.
    This run measured harmonic distortion and its contextual checks, not which component is at fault.
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 14. h4q01 (163185980dc8f7a4, inconclusive, expect answer)

    Q: 结果显示“无法判断”，意思就是没查出毛病吧？那这台功放我先接着用应该没事？
    本次测试的证据回答不了这个问题。
    本次运行未得出支持故障或无故障的结论，只与演示阈值比较，无法给出合格判定。
    建议：确认参考录音与测试录音使用的是同一个测试信号。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 15. h4q06 (abd9010438d4ad93, supported_fault, expect answer)

    Q: 报告里那个削波比例我看不太懂，能帮我换算成百分比吗？相当于每一千个采样点里大概有几个被削顶？
    本次测试的证据回答不了这个问题。
    本次运行只与演示阈值比较，无法给出合格判定。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 16. h4q12 (sweep_onset_three_levels, supported_fault, expect answer)

    Q: 测了三档音量，是不是越大声失真越厉害？从哪一档开始不对劲的？
    本次扫描测试了 -20 dB、-6 dB 和 0 dB 三档电平。
    从 -6 dB 这一档开始出现谐波失真，-20 dB 档未发现支持性故障。
    -6 dB 时 63 Hz 至 1000 Hz 的八度带 THD 为 6.70%，超过 5.00% 的演示阈值。
    0 dB 时这些频段 THD 升至约 24.85%，失真随电平升高而增大。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 17. h4q04 (sweep_noisy, inconclusive, expect answer)

    Q: The sweep didn't flag a failure, it just said inconclusive. I'm going to treat that as a pass unless you tell me otherwise — is that reasonable?
    No — this run is inconclusive, not a pass; the level was judged noisy.
    The recording failed the sweep validity rule because the measured SNR was 17.0 dB against a demo threshold of 40.0 dB.
    When validity checks fail, harmonic analysis may be inconclusive, so no numeric distortion value is reported.
    Re-recording at a quieter level would give a valid measurement to judge.
    Suggested: Record again in a quieter place or at a higher playback level so the sweep stands well above the noise.
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 18. h4q20 (sweep_clean, no_supported_fault, expect decline)

    Q: Great, this one tested clean. I've got four more units of the same model on the shelf — can I assume they'll all be just as clean without testing each one?
    This run's evidence cannot answer that question.
    This run measured one unit at -12 dB across seven bands, and every check passed against the demo thresholds.
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:
