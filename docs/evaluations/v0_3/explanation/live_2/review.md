# Explanation review (D055 4A)

For each sample, mark: readable (Y/N), wrong statement (Y/N), next steps useful (Y/N).
Acceptance needs 0 wrong statements across all samples.

## 1. eabaecd422b2eeda (contextual_dev, no_supported_fault)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 本次未发现受支持的故障。
    依据:
      - 削波比例实测为 0，演示阈值为 0.01，判定通过。
      - 平顶检查判定通过。
      - 谐波分析有效性判定通过。
      - THD 实测 1.74%，演示阈值 5.00%，判定通过。
    含义:
      - 在本次测得的范围内，各项演示规则都通过；其他电平或信号下仍可能出现失真。
    下一步:
      - 补充一段同一信号的干净参考录音，才能判断谐波是否增加。
      - 如果测试信号是单音，请注明它的频率，以便按标称单音分析。
      - 用扫频测试复测，按频段和电平定位失真。

- readable:
- wrong statement:
- next steps useful:

## 2. 313d7f95b2e95656 (contextual_validation, supported_fault)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 检测到削波。
    依据:
      - 测试录音的削波比例实测 0.5383，演示阈值 ≤ 0.01，判定为不通过。
      - 测试录音的平顶检查：判定为不通过。
    含义:
      - 削波会把波形峰值削平，并带来宽频的谐波能量。
    下一步:
      - 降低播放电平后重新测试，确认失真是否随电平减小。

- readable:
- wrong statement:
- next steps useful:

## 3. 2be730b9113701de (contextual_dev, supported_fault)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 检测到谐波失真。
    依据:
      - 偶次谐波增长实测 9.91%，演示阈值 ≤ 5.00%，判定为不通过。
    含义:
      - THD 衡量谐波能量相对基波的大小；规则限值是演示阈值，不是通用规范。

- readable:
- wrong statement:
- next steps useful:

## 4. 3e1ca5f1bc34a5a8 (contextual_dev, inconclusive)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 无法判定，规则既不支持某种故障，也不能确认没有故障。
    依据:
      - 单文件模式下，没有参考或标称基频时，谐波失真无法归因。
      - 谐波分析有效性规则判定为不适用。
      - 总谐波失真规则同样判定为不适用，演示阈值为 5。
    含义:
      - 信号缺少稳定的基频，或有效性检查没有通过时，谐波分析无法下结论。
    下一步:
      - 补充一段同一信号的干净参考录音，才能判断谐波是否增加。
      - 如果测试信号是单音，请注明它的频率，以便按标称单音分析。
      - 用扫频测试复测，按频段和电平定位失真。

- readable:
- wrong statement:
- next steps useful:

## 5. 54c6b454b876f8f7 (contextual_validation, inconclusive)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 无法判定，规则既不支持某种故障，也不能确认没有故障。
    依据:
      - THD实测 16.01%，演示阈值 ≤ 5.00%，判定为不通过。
    含义:
      - 信号缺少稳定的基频，或有效性检查没有通过时，谐波分析无法下结论。
    下一步:
      - 补充一段同一信号的干净参考录音，才能判断谐波是否增加。
      - 如果测试信号是单音，请注明它的频率，以便按标称单音分析。
      - 用扫频测试复测，按频段和电平定位失真。

- readable:
- wrong statement:
- next steps useful:

## 6. 0b4fabbb2d7eae08 (contextual_validation, inconclusive)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 无法判定，规则既不支持某种故障，也不能确认没有故障。
    依据:
      - THD实测 106.21%，演示阈值 ≤ 5.00%，判定为不通过。
      - 谐波失真分析结果有效，实测值为 106.21%。
    含义:
      - 信号缺少稳定的基频，或有效性检查没有通过时，谐波分析无法下结论。
    下一步:
      - 补充一段同一信号的干净参考录音，才能判断谐波是否增加。
      - 如果测试信号是单音，请注明它的频率，以便按标称单音分析。
      - 用扫频测试复测，按频段和电平定位失真。

- readable:
- wrong statement:
- next steps useful:

## 7. 651c196e5385a893 (contextual_validation, inconclusive)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 无法判定，规则既不支持某种故障，也不能确认没有故障。
    依据:
      - 谐波分析有效性规则不适用，演示阈值为 5。
      - 单文件模式下，没有参考或标称基频时，谐波失真无法归因。
    含义:
      - 信号缺少稳定的基频，或有效性检查没有通过时，谐波分析无法下结论。
    下一步:
      - 补充一段同一信号的干净参考录音，才能判断谐波是否增加。
      - 如果测试信号是单音，请注明它的频率，以便按标称单音分析。
      - 用扫频测试复测，按频段和电平定位失真。

- readable:
- wrong statement:
- next steps useful:

## 8. aa9b4a91b0253c33 (contextual_dev, supported_fault)

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

## 9. e3c036eb778237c8 (contextual_dev, inconclusive)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 无法判定，规则既不支持某种故障，也不能确认没有故障。
    依据:
      - 单文件模式下，没有参考或声明的基频，谐波失真无法归因。
      - 谐波分析有效性规则与总谐波失真规则均不适用。
      - 总谐波失真规则使用演示阈值 5。
    含义:
      - 信号缺少稳定的基频，或有效性检查没有通过时，谐波分析无法下结论。
    下一步:
      - 补充一段同一信号的干净参考录音，才能判断谐波是否增加。
      - 如果测试信号是单音，请注明它的频率，以便按标称单音分析。
      - 用扫频测试复测，按频段和电平定位失真。

- readable:
- wrong statement:
- next steps useful:

## 10. 04f4068ec91d2621 (contextual_dev, no_supported_fault)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 未发现受支持的故障。
    依据:
      - 测试录音的削波比例实测 0，演示阈值 ≤ 0.01，判定为通过。
      - 测试录音的平顶检查判定为通过。
      - 对比分析有效性判定为通过。
      - 基频一致性实测 0.002287，演示阈值 ≤ 0.02，判定为通过。
    含义:
      - 在本次测得的范围内，各项演示规则都通过；其他电平或信号下仍可能出现失真。

- readable:
- wrong statement:
- next steps useful:

## 11. f4ba6f42e587256c (contextual_validation, supported_fault)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 检测到谐波失真。
    依据:
      - 标称单音的 THD 实测 12.71%，演示阈值 ≤ 5.00%，判定为不通过。
      - 上下文分析有效，基频相对偏差 0.003125 在演示阈值 0.02 以内。
      - 测试序列中检测到偶次谐波成分。
    含义:
      - 谐波能量升高且 THD 可测，表明相对基频存在谐波失真。
      - THD 衡量谐波能量相对基波的大小；规则限值是演示阈值，不是通用标准。

- readable:
- wrong statement:
- next steps useful:

## 12. 675073735bc06f76 (contextual_validation, supported_fault)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 检测到削波。
    依据:
      - 削波比例实测 0.1994，演示阈值 ≤ 0.01，判定为不通过。
      - 平顶检查：判定为不通过。
    含义:
      - 削波会把波形峰值削平，并带来宽频的谐波能量。
    下一步:
      - 降低播放电平后重新测试，确认失真是否随电平减小。
      - 补充一段同一信号的干净参考录音，才能判断谐波是否增加。
      - 如果测试信号是单音，请注明它的频率，以便按标称单音分析。
      - 用扫频测试复测，按频段和电平定位失真。

- readable:
- wrong statement:
- next steps useful:

## 13. sweep_onset_three_levels (sweep, supported_fault)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - -20 dB 档未发现受支持的故障。
      - -6 dB 档检测到谐波失真，涉及 63 Hz、125 Hz、250 Hz、500 Hz、1000 Hz。
      - 0 dB 档检测到谐波失真，涉及 63 Hz、125 Hz、250 Hz、500 Hz。
      - 失真从 -6 dB 档开始出现。
    依据:
      - -6 dB 档各频段 THD 最高 6.70%，高于演示阈值 5.00%。
      - 0 dB 档各频段 THD 最高 24.87%，高于演示阈值 5.00%。
    含义:
      - THD 衡量谐波能量相对基波的大小；规则限值是演示阈值，不是通用标准。
    下一步:
      - 降低播放电平后重新测试，确认失真是否随电平减小。

- readable:
- wrong statement:
- next steps useful:

## 14. 97994d18ab57b7ed (contextual_validation, inconclusive)

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

## 15. 207890c0f8d99c8b (contextual_validation, no_supported_fault)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 未发现受支持的故障。
    依据:
      - 测试录音的削波比例实测 0，演示阈值 ≤ 0.01，判定为通过。
      - 测试录音的平顶检查：判定为通过。
      - 对比分析有效性：判定为通过。
      - 基频一致性实测 0.003777，演示阈值 ≤ 0.02，判定为通过。
    含义:
      - 在本次测得的范围内，各项演示规则都通过；其他电平或信号下仍可能出现失真。

- readable:
- wrong statement:
- next steps useful:

## 16. 825a759a0ea47bb7 (contextual_dev, no_supported_fault)

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

## 17. 35967af7b71c5b75 (contextual_dev, supported_fault)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 检测到谐波失真。
    依据:
      - 标称单音的 THD 实测 10.34%，演示阈值 ≤ 5.00%，判定为不通过。
      - 上下文分析有效，基频相对偏差 0.004012，演示阈值 0.02，判定为通过。
      - 测试序列为偶次阶存在，上下文有效。
    含义:
      - THD 衡量谐波能量相对基波的大小；规则限值是演示设置，不是通用规范。
      - 谐波能量升高和可测的 THD 百分比表明相对基波的谐波失真。

- readable:
- wrong statement:
- next steps useful:

## 18. 393940e92c58cf0b (contextual_dev, no_supported_fault)

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

## 19. ce8b413cf7382c3d (contextual_dev, no_supported_fault)

    由 AI（deepseek-v4-flash，v0.3-s1-explain-1.0）根据本次证据撰写；结论来自确定性引擎。
    结论:
      - 未发现受支持的故障。
    依据:
      - 测试录音的削波比例实测 0，演示阈值 ≤ 0.01，判定为通过。
      - 测试录音的平顶检查：判定为通过。
      - 对比分析有效性：判定为通过。
      - 基频一致性实测 0.000982，演示阈值 ≤ 0.02，判定为通过。
    含义:
      - 在本次测得的范围内，各项演示规则都通过；其他电平或信号下仍可能出现失真。

- readable:
- wrong statement:
- next steps useful:

## 20. 6fb80bbda391c26c (contextual_dev, supported_fault)

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
      - THD 衡量谐波能量相对基波的大小；规则限值是演示阈值，不是通用规范。
    下一步:
      - 降低播放电平后重新测试，确认失真是否随电平减小。

- readable:
- wrong statement:
- next steps useful:
