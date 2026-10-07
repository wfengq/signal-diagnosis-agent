# Result Q&A review (D060 C)

For each sample, mark: answers the question (Y/N), wrong statement (Y/N),
declined correctly when the evidence cannot answer (Y/N/-).
Acceptance needs 0 wrong statements across all samples.

## 1. hq08 (6334f80c9b6b30be, supported_fault, expect answer)

    Q: Does this meet AES17 or a THD certification limit?
    This run's evidence cannot answer that question.
    This run measured harmonic distortion against configured demonstration thresholds, not any certification limit.
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 2. hq12 (sweep_all_clean_two_levels, no_supported_fault, expect answer)

    Q: Did the sweep find any distortion at either level?
    The sweep found no supported fault at either level tested.
    At -20 dB, every measurable band and the full-scale check pass.
    At -6 dB, every measurable band and the full-scale check pass.
    Band distortion stayed at 0.00% against a 5.00% demonstration threshold.
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 3. hq04 (313d7f95b2e95656, supported_fault, expect answer)

    Q: What should I do next with this result?
    This run supports a clipping finding, backed by its mechanism evidence and a failing clipping rule.
    The measured clipping ratio was 0.5383 against a demo threshold of 0.01.
    Flat tops and clipping events were also detected in the waveform.
    The suggested next step is to lower the playback level and re-run the test.
    Suggested: Lower the playback level and test again to see whether the distortion drops.
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 4. hq11 (sweep_soft_one_level, supported_fault, expect answer)

    Q: 扫频里大概从哪个电平开始有问题？
    本次扫频从 0 dB 电平起就支持失真判定。
    在 0 dB 下，63 Hz、125 Hz、250 Hz、500 Hz、1000 Hz 的八度带 THD 均超出演示阈值。
    这些频段的实测 THD 为 6.70%，演示阈值为 5.00%。
    建议：再录一到两个更低的音量，找出失真从哪一档开始。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 5. hq18 (e333ac4a1bdcbd32, no_supported_fault, expect decline)

    Q: 如果要修，大概要花多少钱？
    本次测试的证据回答不了这个问题。
    本次运行只做了成对参考的失真对比，未发现可支持的故障。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 6. hq17 (sweep_drift, inconclusive, expect decline)

    Q: 是不是某个电容坏了？
    本次测试的证据回答不了这个问题。
    本次运行只做了扫频漂移检查，结果无法判定。
    建议：尽量让播放和录音使用同一个声卡或同一个时钟。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 7. hq13 (sweep_wrong_stimulus, inconclusive, expect answer)

    Q: 这次扫频为什么没法下结论？
    本次扫频的结论为无法判定，因为录音未满足该测试的有效性规则。
    对齐相关性实测为0.006773，低于演示阈值0.3，因此对齐检查未通过。
    漂移实测为543497.6 ppm，高于演示阈值200.0 ppm，漂移检查未通过。
    信噪比实测为-0.1 dB，低于演示阈值40.0 dB，信噪比检查未通过。
    建议：确认播放的是本产品下载的扫频文件，并且没有被处理过。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 8. hq16 (773852f7513151f1, supported_fault, expect decline)

    Q: 到底是喇叭坏了还是功放坏了？
    本次测试的证据回答不了这个问题。
    本次运行只评估了谐波失真，无法判断是哪个部件损坏。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 9. hq15 (2ca9870c96ed589d, supported_fault, expect answer)

    Q: 报告里的削波比例换算成 dB 是多少？
    本次测试的证据回答不了这个问题。
    本次运行测量了削波比例与偶次谐波增长等指标，未提供以 dB 表示的削波比例。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 10. hq01 (84fd2af41fdc1d54, supported_fault, expect answer)

    Q: 这次参考对比测出来有问题吗？具体是什么？
    本次参考对比测出削波问题，结论为已支持的故障。
    削波比观测值为 0.1643，高于演示阈值 0.01，该规则判定不通过。
    平顶检测规则同样判定不通过，机制证据有效。
    平顶、削波事件与偏高的削波比共同支持削波结论。
    建议：降低播放电平后重新测试，确认失真是否随电平减小。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 11. hq20 (sweep_soft_one_level, supported_fault, expect decline)

    Q: 这台设备还能正常用几年？
    本次测试的证据回答不了这个问题。
    本次运行只测量了 0 dB 下的扫频谐波失真，无法预测设备还能使用多少年。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 12. hq19 (675073735bc06f76, supported_fault, expect decline)

    Q: Which cable or power-supply part failed?
    This run's evidence cannot answer that question.
    This run measured clipping in a single-signal recording, not which part failed.
    Suggested: Lower the playback level and test again to see whether the distortion drops.
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:

## 13. hq05 (7fd4173cde11c0e3, supported_fault, expect answer)

    Q: 标称单音这次有没有测出失真？
    本次标称单音运行判定为支持故障，结论是削波。
    削波比观测值为 0.03112，高于演示阈值 0.01，该规则判定为不通过。
    平顶检测规则同样判定为不通过，并检测到平顶。
    平顶、削波事件与升高的削波比共同支持削波这一结论。
    [source: model]

- answers the question:
- wrong statement:
- declined correctly:
