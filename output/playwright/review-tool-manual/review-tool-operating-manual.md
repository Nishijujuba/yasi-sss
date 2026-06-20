# Yasi ASR Timing Review HTML 操作说明书

适用页面：

`D:/Project/yasi/.agents/skills/yasi-asr-timing-reconciliation/tools/generated/cambridge-10-test-1-listening-section-01-small-review.html`

页面读取的是 Section 01 的 `small` 模型筛选结果。当前队列有 22 个未解决项：19 个 `human-required`，3 个 `llm-candidate`。已经由代码筛掉并自动批准的项有 160 个。

## 人工核对的点

复核人核对的是“官方 transcript token 是否在给定音频区间里被准确说出”。区间记为：

\[
[start, end], \quad 0 \le start < end
\]

一个合格 timing 需要同时满足三件事：

1. `Official token` 和音频里听到的词一致。
2. `Start` 接近该词发音开始，`End` 接近该词发音结束。
3. 与前后上下文顺序一致，尤其不能出现明显倒序：

\[
end_i \le start_{i+1}
\]

需要人工重点看的类别：

| 类别 | 含义 | 核对方式 |
| --- | --- | --- |
| `number` | 数字、电话、里程、门牌号 | 逐位听，确认数字完整，首尾时间覆盖完整读法。 |
| `currency` | 金额，如 `£525`、`£429` | 听金额数字和单位语义，避免只截到部分数字。 |
| `alphanumeric` | 字母数字混合，如 postcode `BH5 2OP` | 字母和数字逐个核对，分段边界要跟读音一致。 |
| `hyphen-spelling` | 拼写串，如 `A-R-D-L-E-I-G-H` | 按字母顺序逐个听，确认 ASR 拆分没有漏字母。 |
| `hyphenated` | 连字符词，如 `self-drive` | 听完整词组，检查是否被错误贴到前后句。 |
| `missing-timing` | 没有 start/end | 需要人工用音频和上下文补区间，无法确认则保留 pending。 |
| `non-monotonic-timing` | 时间顺序异常 | 重点看它是否被对到另一处重复文本。 |
| `match:fuzzy` | ASR 文本和官方文本近似 | 大模型或 ASR 只提供线索，最终以听音频为准。 |

## 当前 22 个待复核项

| Review ID | Tier | Official token | Whisper source | Timing | 主要原因 |
| --- | --- | --- | --- | --- | --- |
| `s01-g0020` | human-required | `self-drive` | `self -drive` | `121.68-122.42` | split, hyphenated, non-monotonic |
| `s01-g0046` | human-required | `24` | `24` | `176.78-177.38` | number, answer-near |
| `s01-g0047` | llm-candidate | `Ardleigh` | `Ardley` | `177.38-177.98` | fuzzy, answer-near |
| `s01-g0053` | human-required | `A-R-D-L-E-I-G-H` | `Ard -L -E -I -G -H` | `181.00-184.28` | spelling sequence |
| `s01-g0056` | human-required | `BH5` | `B -H -5` | `187.00-188.24` | alphanumeric, number |
| `s01-g0057` | human-required | `2` | `-2` | `188.24-189.18` | number |
| `s01-g0058` | llm-candidate | `OP` | `-P.` | `189.56-189.94` | fuzzy |
| `s01-g0073` | human-required | `07786643091` | `077 -86 -643 -091.` | `195.88-200.59` | phone number split |
| `s01-g0163` | human-required | `self-drive` | `self -drive` | `165.78-166.50` | split, hyphenated, non-monotonic |
| `s01-g0298` | llm-candidate | `Hearst` | `Hurst` | `275.60-276.04` | fuzzy |
| `s01-g0421` | human-required | `self-drive` | `self -drive` | `352.76-353.34` | split, hyphenated, answer-near |
| `s01-g0427` | human-required | `twelve` | missing | empty | missing timing |
| `s01-g0431` | human-required | `2,020` | `,020` | `357.80-358.94` | fuzzy number |
| `s01-g0437` | human-required | `206` | `206` | `361.66-362.62` | number, answer-near |
| `s01-g0438` | human-required | `km` | missing | empty | missing timing |
| `s01-g0443` | human-required | `632` | `632` | `364.66-365.60` | number, answer-near |
| `s01-g0448` | human-required | `£525` | `£525` | `368.02-369.06` | number, currency |
| `s01-g0483` | human-required | `980` | `980` | `382.72-383.64` | number |
| `s01-g0494` | human-required | `a` | missing | empty | missing timing |
| `s01-g0495` | human-required | `hundred` | missing | empty | missing timing |
| `s01-g0496` | human-required | `pounds` | missing | empty | missing timing |
| `s01-g0499` | human-required | `£429` | `£429` | `389.62-390.56` | number, currency |

## 打开 HTML

在浏览器里打开这个本地文件：

`D:/Project/yasi/.agents/skills/yasi-asr-timing-reconciliation/tools/generated/cambridge-10-test-1-listening-section-01-small-review.html`

页面顶部的 Audio URL 应该已经是：

`file:///D:/Project/yasi/public/packs/cambridge-10/test-1/listening/assets/audio/section-01.mp3`

如果音频栏能显示 `0:00 / 7:36`，说明本地音频加载正常。

![界面总览](D:/Project/yasi/output/playwright/review-tool-manual/images/01-overview.png)

## 单项复核流程

1. 在左侧队列选择一个 `reviewId`。
2. 看右侧 `Official token`、`Whisper source`、`Match type`、`Risks`、`Reasons`。
3. 看 `Transcript context`，确认目标词在句子里的位置。
4. 点击 `Play window`，页面会播放当前 timing 前后约 1.2 秒的音频。
5. 如果 timing 准确，点击 `Approve timing`。
6. 如果 timing 不准，修改 `Start` 和 `End`，点击 `Save correction`。
7. 如果无法判断，点击 `Keep pending`。
8. 如果映射本身错误，点击 `Reject`，并在 Notes 写明原因。

缺失 timing 的项需要复核人补出区间。例如 `s01-g0427` 的 `twelve` 没有 `Start` 和 `End`，复核人要听 `lasts twelve days` 附近，把 `twelve` 的开始和结束秒数填进去。

![缺失 timing 示例](D:/Project/yasi/output/playwright/review-tool-manual/images/02-missing-timing-item.png)

## 筛选 LLM 候选

左侧第二个下拉框选择 `LLM candidate` 可以只看大模型候选项。这里的大模型输出只能当作建议，因为它没有替复核人听音频做最终确认。

![LLM 候选筛选](D:/Project/yasi/output/playwright/review-tool-manual/images/03-llm-candidates.png)

这类项的判断方式：

| 示例 | 判断重点 |
| --- | --- |
| `Ardleigh -> Ardley` | 听地址名发音，官方文本仍以 `Ardleigh` 为准，只判断 timing 是否覆盖这段发音。 |
| `OP -> -P.` | 听 postcode 末尾是否包含 `O P`，检查是否漏掉 `O` 的时间。 |
| `Hearst -> Hurst` | 听地名发音，确认时间是否落在 `Hearst Castle` 的前一个词。 |

## 按风险筛选

右侧风险下拉框可以筛 `number`、`currency`、`hyphenated` 等类别。数字类建议集中处理，因为这类错误最容易影响听力题答案。

![数字风险筛选](D:/Project/yasi/output/playwright/review-tool-manual/images/04-number-risk-filter.png)

## 按钮含义

| 按钮 | 结果 | 何时使用 |
| --- | --- | --- |
| `Approve timing` | `decision=approved` | 当前 start/end 已准确。 |
| `Save correction` | `decision=corrected`，写入 `correction.start/end` | 需要调整时间。 |
| `Keep pending` | `decision=pending` | 仍然不确定，需要之后再看。 |
| `Reject` | `decision=rejected` | 映射错误或音频证据无法支持。 |
| `Export reviewed JSON` | 下载 `alignment-review.reviewed.json` | 全部处理完或阶段性保存时使用。 |

最终发布前，所有进入发布审计链的 review 项都需要变成 `approved` 或 `corrected`。`pending` 和 `rejected` 会阻塞生成最终 `transcript-timings.json`。

## 导出与交接

点击 `Export reviewed JSON` 后，浏览器会下载：

`alignment-review.reviewed.json`

复核完成后，后续 finalize 应使用这个 reviewed JSON 作为输入。复核人需要确保每个修改过的项都保留 `reviewer`、`reviewedAt`、`notes` 和 `correction` 信息，因为这些字段是 release audit 的证据链。

## 容易漏掉的风险

1. 反复出现的词容易对到错误位置。`self-drive` 在 Section 01 中出现多次，复核时要看上下文。
2. 数字 timing 往往覆盖整段读法，不能只看 ASR token 是否相同。
3. 缺失 timing 可以通过前后词定位，边界要留在目标词发音内外合理位置。
4. LLM 候选只降低查找成本，最终结论仍然来自音频、官方 token 和上下文。
5. 浏览器下载的 JSON 是本地文件，页面本身不会自动覆盖 repo 里的 review artifact。
