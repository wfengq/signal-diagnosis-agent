# Result Q&A review (D060 C)

For each sample, mark: answers the question (Y/N), wrong statement (Y/N),
declined correctly when the evidence cannot answer (Y/N/-).
Acceptance needs 0 wrong statements across all samples.

## 1. h3q10 (sweep_onset_three_levels, supported_fault, expect answer)

    Q: 这几档电平测下来，是不是音量越大失真越严重？大概从哪一档开始不行的？
    本次扫频测了 -20 dB、-6 dB 和 0 dB 三档电平。
    -20 dB 时各频段与满量程检查均通过，未支持失真。
    从 -6 dB 起失真开始被支持，63 Hz 至 1000 Hz 的谐波失真超过演示阈值。
    0 dB 时同样频段失真更高，例如 63 Hz 达 24.87%，高于演示阈值 5.00%。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 2. h3q15 (sweep_polynomial_two_levels, no_supported_fault, expect answer)

    Q: Quick one: between the two levels I tested, did the distortion get noticeably worse at the louder one, or did it stay about the same?
    Two levels were tested: -12 dB and 0 dB.
    At -12 dB every band measured 0.63% distortion, below the 5.00% demo threshold.
    At 0 dB every band measured 2.50%, still below the 5.00% demo threshold.
    So distortion rose from 0.63% to 2.50% at the louder level, but no fault was supported.
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 3. h3q02 (54c6b454b876f8f7, inconclusive, expect answer)

    Q: 我就录了一段音频传上去，结果是不确定。既然没报故障，我理解成这台录音笔基本是好的，对吗？
    不能这样理解：本次运行既没有支持故障，也没有确认无故障。
    单文件模式下，没有参考或声明的基频，谐波失真无法归因。
    测得的总谐波失真为16.01%，高于演示阈值5.00%，该检查判定为未通过。
    建议：补充一段同一信号的干净参考录音，才能判断谐波是否增加。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 4. h3q07 (651c196e5385a893, inconclusive, expect answer)

    Q: 结果是无法判断，我下一步该怎么做才能得到一个明确的结论？
    本次运行未得出支持故障或确认无故障的结论。
    单信号模式下，缺少参考或声明的基频时，谐波失真无法归因。
    谐波分析与总谐波失真两项检查均未适用，只与演示阈值比较。
    要得到明确结论，可补充参考录音或声明基频，或改做扫频测试。
    建议：补充一段同一信号的干净参考录音，才能判断谐波是否增加。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 5. h3q12 (6334f80c9b6b30be, supported_fault, expect answer)

    Q: What was the measured THD on this run, and how far over the threshold was it?
    This run's evidence cannot answer that question.
    This run measured harmonic distortion and compared it with demonstration thresholds, but no THD value is reported in the packet.
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 6. h3q16 (675073735bc06f76, supported_fault, expect decline)

    Q: 检测说有故障，你能看出来是机器里面哪个元件出问题了吗？是电容还是运放？
    本次测试的证据回答不了这个问题。
    本次运行只比较了测量值与演示阈值，无法判断是哪个元件导致失真。
    建议：补充一段同一信号的干净参考录音，才能判断谐波是否增加。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 7. h3q19 (76054f40e6aeec75, inconclusive, expect decline)

    Q: 这台机子还在保修期内，凭这次测试结果厂家会不会给我免费换新？
    本次测试的证据回答不了这个问题。
    本次运行只做了单频测试，结论为不确定，无法判断保修换新。
    建议：用扫频测试复测，按频段和电平定位失真。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 8. h3q18 (313d7f95b2e95656, supported_fault, expect decline)

    Q: Which part is causing this, the speaker cone or the amp module inside? I need to know what to order a replacement for.
    This run's evidence cannot answer that question.
    This run measured clipping evidence in the captured audio, not which physical part produced it.
    Suggested: Lower the playback level and test again to see whether the distortion drops.
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 9. h3q17 (f4ba6f42e587256c, supported_fault, expect decline)

    Q: 我拆开看了下板子，想直接换零件。根据这次结果，应该换的是输出级那颗芯片吧？
    本次测试的证据回答不了这个问题。
    本次运行只测量了单音谐波失真，无法判断是哪个零件造成的。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 10. h3q04 (sweep_all_clean_two_levels, no_supported_fault, expect answer)

    Q: Ran the sweep at two levels on this DAC board. Can I mark it as OK to ship to the customer based on this run?
    This run tested two levels, -20 dB and -6 dB, and found no supported fault at either.
    At -20 dB every measurable band and the full-scale check passed against the demonstration thresholds.
    At -6 dB every measurable band and the full-scale check also passed against the demonstration thresholds.
    This run only compares measurements with demonstration thresholds, so it cannot decide shipping approval.
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 11. h3q11 (e333ac4a1bdcbd32, no_supported_fault, expect answer)

    Q: 虽然判定没故障，但我想看看具体数字：削波比例实际测出来是多少？
    本次运行测得的削波比例为 0，演示阈值为 0.01。
    参考信号的削波比例同样为 0，演示阈值为 0.01。
    偶次谐波增长为 0.00%，演示阈值为 5.00%。
    所有规则均通过，未发现受支持的故障。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 12. h3q09 (sweep_soft_one_level, supported_fault, expect answer)

    Q: 扫频测下来说有失真，想知道音量开到哪一档开始出现失真的？
    本次扫频只在 0 dB 这一档做了测试，没有测其他档位。
    在 0 dB 下，63 Hz、125 Hz、250 Hz、500 Hz、1000 Hz 的八度带 THD 均超过演示阈值。
    例如 63 Hz 处测得 6.70%，高于演示阈值 5.00%，判定为 fail。
    因此无法判断失真从哪一档开始，只能说明该档位已出现失真。
    建议：再录一到两个更低的音量，找出失真从哪一档开始。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 13. h3q01 (91280fa05c6dfd2a, inconclusive, expect answer)

    Q: 结果显示“无法确定”，那是不是说明没查出毛病？我就当它没问题先用着，可以吧？
    不能当作没问题：本次运行既未支持存在故障，也未确认不存在故障。
    上下文分析有效性检查未通过，基频兼容性检查为不适用。
    偶次谐波增长与标称失真检查同样为不适用，因此没有可用的失真数值。
    本次运行只把测量值与演示阈值比较，未给出可用结论。
    建议：确认参考录音与测试录音使用的是同一个测试信号。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 14. h3q08 (7fd4173cde11c0e3, supported_fault, expect answer)

    Q: OK so it says there's a fault. What should I actually try next before I go and re-test?
    This run measured a nominal single tone and found clipping supported by its mechanism evidence and failing clipping rules.
    The clipping ratio measured 0.03112 against a demonstration threshold of 0.01, and the flat-top check also failed.
    Flat tops, clipping events and an elevated clipping ratio all point to clipping in this run.
    Before re-testing, try lowering the playback level as the suggested next step.
    Suggested: Lower the playback level and test again to see whether the distortion drops.
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 15. h3q13 (sweep_wrong_stimulus, inconclusive, expect answer)

    Q: 为什么这次扫频给不出结论？是我录音的时候哪里没弄对吗？
    这次扫频的结论是不确定，因为录音未通过有效性规则。
    对齐相关性实测为 0.006773，低于演示阈值 0.3，该项判定失败。
    漂移实测为 543497.6 ppm，高于演示阈值 200.0 ppm，该项判定失败。
    信噪比实测为 -0.1 dB，低于演示阈值 40.0 dB，该项判定失败。
    建议：确认播放的是本产品下载的扫频文件，并且没有被处理过。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 16. h3q06 (f159f483605aed01, no_supported_fault, expect answer)

    Q: 报告里的THD是百分比，能帮我换算成dB是多少吗？我习惯看dB。
    本次测试的证据回答不了这个问题。
    本次运行只比较了削波比例、平顶缺失与偶次谐波增长等测量值与演示阈值，未测量或报告THD。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 17. h3q20 (sweep_drift, inconclusive, expect decline)

    Q: I have three other units of the same model sitting on the shelf. Does this result mean they'll have the same problem?
    This run's evidence cannot answer that question.
    This run measured a sweep and could not judge at least one level, so it says nothing about other units.
    Suggested: Play and record on the same audio interface or clock where possible.
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:
