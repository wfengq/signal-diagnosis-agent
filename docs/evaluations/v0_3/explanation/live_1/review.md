# Explanation review (D055 4A)

For each sample, mark: readable (Y/N), wrong statement (Y/N), next steps useful (Y/N).
Acceptance needs 0 wrong statements across all samples.

## 1. d4bb668a379dea3b (contextual_dev, inconclusive)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 无法判定，规则既不支持某种故障，也不能确认没有故障。
    依据:
      - 单文件模式下，没有参考或标称基频时，谐波失真无法归因。
      - 谐波分析有效性规则判定为不适用。
      - 总谐波失真可接受规则判定为不适用，演示阈值为 5。
    含义:
      - 信号缺少稳定的基频，或有效性检查没有通过时，谐波分析无法下结论。
    下一步:
      - 补充一段同一信号的干净参考录音，才能判断谐波是否增加。
      - 如果测试信号是单音，请注明它的频率，以便按标称单音分析。
      - 用扫频测试复测，按频段和电平定位失真。

- readable:
- wrong statement:
- next steps useful:

## 2. 2ca9870c96ed589d (contextual_validation, supported_fault)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 检测到削波。
      - 检测到谐波失真。
    依据:
      - 测试录音的削波比例实测 0.1564，演示阈值 ≤ 0.01，判定为不通过。
      - 测试录音的平顶检查判定为不通过。
      - 偶次谐波增长实测 9.91%，演示阈值 ≤ 5.00%，判定为不通过。
    含义:
      - 削波会把波形峰值削平，并带来宽频的谐波能量。
      - THD 衡量谐波能量相对基波的大小；规则限值是演示阈值，不是通用规范。
    下一步:
      - 降低播放电平后重新测试，确认失真是否随电平减小。

- readable:
- wrong statement:
- next steps useful:

## 3. 6fb80bbda391c26c (contextual_dev, supported_fault)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 检测到削波。
      - 检测到谐波失真。
    依据:
      - 测试录音的削波比例实测 0.02562，演示阈值 ≤ 0.01，判定为不通过。
      - 测试录音的平顶检查：判定为不通过。
      - 偶次谐波增长实测 8.81%，演示阈值 ≤ 5.00%，判定为不通过。
    含义:
      - 削波会把波形峰值削平，并带来宽频的谐波能量。
      - THD 衡量谐波能量相对基波的大小；规则限值是演示设置，不是通用规范。
    下一步:
      - 降低播放电平后重新测试，确认失真是否随电平减小。

- readable:
- wrong statement:
- next steps useful:

## 4. f159f483605aed01 (contextual_validation, no_supported_fault)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 未发现受支持的故障。
    依据:
      - 测试录音的削波比例实测 0，演示阈值 ≤ 0.01，判定为通过。
      - 测试录音的平顶检查判定为通过。
      - 对比分析有效性判定为通过。
      - 基频一致性实测 0，演示阈值 ≤ 0.02，判定为通过。
    含义:
      - 在本次测得的范围内，各项演示规则都通过；其他电平或信号下仍可能出现失真。

- readable:
- wrong statement:
- next steps useful:

## 5. sweep_all_clean_two_levels (sweep, no_supported_fault)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - -20 dB 下未发现受支持的故障。
      - -6 dB 下同样未发现受支持的故障。
    依据:
      - -20 dB 录音完整性判定为通过。
      - -20 dB 与测试信号的匹配度实测 1，演示阈值 ≥ 0.3，判定为通过。
      - -20 dB 时钟漂移实测 0.0 ppm，演示阈值 ≤ 200.0 ppm，判定为通过。
      - -20 dB 信噪比实测 200.0 dB，演示阈值 ≥ 40.0 dB，判定为通过。
    含义:
      - 在本次测得的范围内，各项演示规则都通过；其他电平或信号下仍可能出现失真。

- readable:
- wrong statement:
- next steps useful:

## 6. 393940e92c58cf0b (contextual_dev, no_supported_fault)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 未发现受支持的故障。
    依据:
      - 测试录音的削波比例实测 0，演示阈值 ≤ 0.01，判定为通过。
      - 测试录音的平顶检查判定为通过。
      - 对比分析有效性判定为通过。
      - 基频一致性实测 0.000010，演示阈值 ≤ 0.02，判定为通过。
    含义:
      - 在本次测得的范围内，各项演示规则都通过；其他电平或信号下仍可能出现失真。

- readable:
- wrong statement:
- next steps useful:

## 7. eb8d416412ce3c22 (contextual_dev, inconclusive)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 无法判定，规则既不支持某种故障，也不能确认没有故障。
    依据:
      - 单文件模式下，没有参考或声明的基频，谐波失真无法归因。
      - 谐波分析有效性规则判定为不适用。
      - 总谐波失真可接受规则判定为不适用，演示阈值为 5。
    含义:
      - 信号缺少稳定的基频，或有效性检查没有通过时，谐波分析无法下结论。
    下一步:
      - 补充一段同一信号的干净参考录音，才能判断谐波是否增加。
      - 如果测试信号是单音，请注明它的频率，以便按标称单音分析。
      - 用扫频测试复测，按频段和电平定位失真。

- readable:
- wrong statement:
- next steps useful:

## 8. 163185980dc8f7a4 (contextual_dev, inconclusive)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 无法判定，规则既不支持某种故障，也不能确认没有故障。
    依据:
      - 原因：参考与测试的基频不一致。
      - 对比分析有效性：判定为不通过。
    含义:
      - 信号缺少稳定的基频，或有效性检查没有通过时，谐波分析无法下结论。
    下一步:
      - 用扫频测试复测，按频段和电平定位失真。
      - 确认参考录音与测试录音使用的是同一个测试信号。

- readable:
- wrong statement:
- next steps useful:

## 9. 97994d18ab57b7ed (contextual_validation, inconclusive)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 无法判定，规则既不支持某种故障，也不能确认没有故障。
    依据:
      - THD实测 13.32%，演示阈值 ≤ 5.00%，判定为不通过。
    含义:
      - 信号缺少稳定的基频，或有效性检查没有通过时，谐波分析无法下结论。
    下一步:
      - 补充一段同一信号的干净参考录音，才能判断谐波是否增加。
      - 如果测试信号是单音，请注明它的频率，以便按标称单音分析。
      - 用扫频测试复测，按频段和电平定位失真。

- readable:
- wrong statement:
- next steps useful:

## 10. sweep_onset_three_levels (sweep, supported_fault)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - -20 dB 档未发现受支持的故障。
      - -6 dB 档检测到谐波失真，涉及 63 Hz、125 Hz、250 Hz、500 Hz、1000 Hz。
      - 0 dB 档检测到谐波失真，涉及 63 Hz、125 Hz、250 Hz、500 Hz。
      - 失真从 -6 dB 档开始出现。
    依据:
      - -6 dB 档：63 Hz 的 THD 为 6.70%，高于 5.00% 的演示阈值。
      - 0 dB 档：63 Hz 的 THD 为 24.87%，高于 5.00% 的演示阈值。
    含义:
      - THD 衡量谐波能量相对基波的大小；规则限值是演示阈值，不是通用规范。
    下一步:
      - 降低播放电平后重新测试，确认失真是否随电平减小。

- readable:
- wrong statement:
- next steps useful:

## 11. 91280fa05c6dfd2a (contextual_validation, inconclusive)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 无法判定，规则既不支持某种故障，也不能确认没有故障。
    依据:
      - 原因：参考与测试的基频不一致。
      - 对比分析有效性：判定为不通过。
    含义:
      - 信号缺少稳定的基频，或有效性检查没有通过时，谐波分析无法下结论。
    下一步:
      - 用扫频测试复测，按频段和电平定位失真。
      - 确认参考录音与测试录音使用的是同一个测试信号。

- readable:
- wrong statement:
- next steps useful:

## 12. 2be730b9113701de (contextual_dev, supported_fault)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 检测到谐波失真。
    依据:
      - 偶次谐波增长实测 9.91%，演示阈值 ≤ 5.00%，判定为不通过。
      - 上下文分析有效，参考削波比率为 0，未检出平顶。
    含义:
      - 谐波能量升高和可测的 THD 百分比表明相对基波的谐波失真。
      - THD 衡量谐波能量相对基波的大小；规则限值是演示阈值，不是通用规范。

- readable:
- wrong statement:
- next steps useful:

## 13. e3c036eb778237c8 (contextual_dev, inconclusive)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 无法判定，规则既不支持某种故障，也不能确认没有故障。
    依据:
      - 单文件模式下，没有参考或标称基频时，谐波失真无法归因。
      - 谐波分析有效性规则判定为不适用。
      - 总谐波失真可接受规则判定为不适用，演示阈值为 5。
    含义:
      - 信号缺少稳定的基频，或有效性检查没有通过时，谐波分析无法下结论。
    下一步:
      - 补充一段同一信号的干净参考录音，才能判断谐波是否增加。
      - 如果测试信号是单音，请注明它的频率，以便按标称单音分析。
      - 用扫频测试复测，按频段和电平定位失真。

- readable:
- wrong statement:
- next steps useful:

## 14. 825a759a0ea47bb7 (contextual_dev, no_supported_fault)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 未发现受支持的故障。
    依据:
      - 测试录音的削波比例实测 0，演示阈值 ≤ 0.01，判定为通过。
      - 测试录音的平顶检查判定为通过。
      - 对比分析有效性判定为通过。
      - 基频一致性实测 0，演示阈值 ≤ 0.02，判定为通过。
    含义:
      - 在本次测得的范围内，各项演示规则都通过；其他电平或信号下仍可能出现失真。

- readable:
- wrong statement:
- next steps useful:

## 15. 6334f80c9b6b30be (contextual_validation, supported_fault)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 检测到谐波失真。
    依据:
      - 偶次谐波增长实测 12.99%，演示阈值 ≤ 5.00%，判定为不通过。
    含义:
      - THD 衡量谐波能量相对基波的大小；规则限值是演示设置，不是通用规范。

- readable:
- wrong statement:
- next steps useful:

## 16. 651c196e5385a893 (contextual_validation, inconclusive)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 无法判定，规则既不支持某种故障，也不能确认没有故障。
    依据:
      - 单文件模式下，没有参考或声明的基频时，谐波失真无法归因。
      - 谐波分析有效性规则判定为不适用。
      - 总谐波失真可接受规则判定为不适用，演示阈值为 5。
    含义:
      - 信号缺少稳定的基频，或有效性检查没有通过时，谐波分析无法下结论。
    下一步:
      - 补充一段同一信号的干净参考录音，才能判断谐波是否增加。
      - 如果测试信号是单音，请注明它的频率，以便按标称单音分析。
      - 用扫频测试复测，按频段和电平定位失真。

- readable:
- wrong statement:
- next steps useful:

## 17. b1584e9fd6bf5c1d (contextual_validation, supported_fault)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 检测到削波。
      - 检测到谐波失真。
    依据:
      - 测试录音的削波比例实测 0.1509，演示阈值 ≤ 0.01，判定为不通过。
      - 测试录音的平顶检查：判定为不通过。
      - 偶次谐波增长实测 8.48%，演示阈值 ≤ 5.00%，判定为不通过。
    含义:
      - 削波会把波形峰值削平，并带来宽频的谐波能量。
      - THD 衡量谐波能量相对基波的大小；规则限值是演示设置，不是通用规范。
    下一步:
      - 降低播放电平后重新测试，确认失真是否随电平减小。

- readable:
- wrong statement:
- next steps useful:

## 18. 76054f40e6aeec75 (contextual_validation, inconclusive)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 无法判定，规则既不支持某种故障，也不能确认没有故障。
    依据:
      - 原因：测得的基频与声明的频率不一致。
      - 对比分析有效性：判定为不通过。
    含义:
      - 信号缺少稳定的基频，或有效性检查没有通过时，谐波分析无法下结论。
    下一步:
      - 用扫频测试复测，按频段和电平定位失真。

- readable:
- wrong statement:
- next steps useful:

## 19. sweep_clean (sweep, no_supported_fault)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - -12 dB 下未发现受支持的故障。
    依据:
      - -12 dB 录音完整性判定为通过。
      - -12 dB 与测试信号的匹配度实测 1，演示阈值 ≥ 0.3，判定为通过。
      - -12 dB 时钟漂移实测 0.0 ppm，演示阈值 ≤ 200.0 ppm，判定为通过。
      - -12 dB 信噪比实测 200.0 dB，演示阈值 ≥ 40.0 dB，判定为通过。
    含义:
      - 在本次测得的范围内，各项演示规则都通过；其他电平或信号下仍可能出现失真。

- readable:
- wrong statement:
- next steps useful:

## 20. aa9b4a91b0253c33 (contextual_dev, supported_fault)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 检测到削波。
      - 检测到谐波失真。
    依据:
      - 测试录音的削波比例实测 0.06525，演示阈值 ≤ 0.01，判定为不通过。
      - 测试录音的平顶检查：判定为不通过。
      - 偶次谐波增长实测 10.42%，演示阈值 ≤ 5.00%，判定为不通过。
    含义:
      - 削波会把波形峰值削平，并带来宽频的谐波能量。
      - THD 衡量谐波能量相对基波的大小；规则限值是演示设置，不是通用规范。
    下一步:
      - 降低播放电平后重新测试，确认失真是否随电平减小。

- readable:
- wrong statement:
- next steps useful:
