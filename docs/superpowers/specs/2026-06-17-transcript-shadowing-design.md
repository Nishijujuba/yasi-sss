# Transcript Shadowing Design

## Purpose

Add Transcript Shadowing to the Cambridge IELTS listening practice app. The learner can open official English audioscript text beside the original question surface while official section audio plays. The panel highlights the currently spoken word from verified word-level timings and supports click-to-seek for replay.

This feature is for follow-reading and listening review. It excludes recording, microphone access, speaking scores, pronunciation assessment, generated transcript display, and copy-to-clipboard.

## Product Decisions

- The displayed text authority is always `transcript.json`, the reviewed official audioscript asset.
- ASR Timing Reconciliation is the primary build-time strategy for generating Transcript Word Timings.
- Local Whisper word timestamps are the default ASR timing source.
- ASR output is timing evidence only. It must be reconciled against official transcript token identities before it can enter a verified timing asset.
- The primary ASR Timing Reconciliation workflow must not load Qwen models.
- The former `yasi-forced-alignment` route is superseded by ADR-0008 and remains historical implementation context.
- The public frontend consumes only verified timing assets.
- Complete pack release requires verified Transcript Shadowing coverage for all four Listening Sections.
- Section 01 may be used as a development-only Transcript Alignment Pilot to validate the full workflow before expanding to Sections 02-04.
- The user may open Transcript Shadowing before submission. Once opened, the current practice session is marked as transcript-viewed until reset.

## Alignment Workflow

The build-time chain is:

```text
timestamped ASR evidence -> official-token reconciliation draft -> alignment-review.json -> transcript-timings.json
```

The new ASR Timing Reconciliation skill should live at `.agents/skills/yasi-asr-timing-reconciliation/` and own the reusable workflow and scripts. Its temporary working root is `D:\Project\yasi\待删除\yasi-asr-timing-reconciliation\`, with benchmark runs grouped by section and model. It must generate or load timestamped Whisper evidence, align ASR tokens to official transcript tokens, record uncertain mappings in `alignment-review.json`, and emit only validated `transcript-timings.json` assets for frontend consumption.

Suggested benchmark layout:

```text
待删除\yasi-asr-timing-reconciliation\
  section-01\
    small\
    medium\
    large-v3\
```

The stable evidence artifact is `asr-timing-evidence.json`. It should record the ASR engine, model, command, source audio path or hash, generation time, normalized word list, and each word's `start` and `end` time. Its text is timing evidence for reconciliation, while `transcript.json` remains the only displayed transcript source.

The stable run report is `reconciliation-report.json`. It should record:

- official token count and ASR word count;
- `matchType` counts for `exact`, `fuzzy`, `interpolated`, `split`, `merged`, and `unmatched`;
- automatic pass ratio and pending review count;
- highest-risk transcript regions and representative diagnostics;
- Whisper command, model, audio identity or hash, and generation time;
- gate outcome, such as `ready-for-finalize`, `needs-review`, or `rerun-asr`.

Gate outcomes mean:

- `ready-for-finalize`: all required timings are valid, no blocking review item remains, and `transcript-timings.json` can be finalized.
- `needs-review`: ASR evidence is usable, while one or more mappings require durable approval or correction in `alignment-review.json`.
- `rerun-asr`: ASR evidence is too weak or malformed for productive review, such as low anchor coverage, excessive unmatched tokens, long unbounded gaps, or audio/provenance mismatch.

Detailed failure causes belong in `blockingReasons[]` and diagnostics instead of expanding the outcome enum.

This report is for build tooling and operator triage. These working artifacts are temporary evaluation and review evidence, not pack source data. The frontend continues to consume only verified `transcript-timings.json`.

The verified local Whisper entrypoint is:

```powershell
$env:PYTHONUTF8='1'
D:\Project\video2pdf\kimi\.venv\Scripts\whisper.exe <audio> --model <cached-model> --model_dir "$env:USERPROFILE\.cache\whisper" --language en --word_timestamps True --output_format json --output_dir <work-dir>
```

The local CLI was smoke-tested with `tiny` on a short Section 01 clip and produced JSON segment words with `word`, `start`, and `end` fields. Larger production runs may choose a larger cached Whisper model, but the text authority and review gates do not change.

The default Whisper model must be selected by a Section 01 benchmark first, starting with cached `small`, `medium`, and `large-v3`. A model is eligible for the first skill default only when:

```text
ready-for-default =
  run completes
  anchorCoverage >= 0.95
  unmatchedRate <= 0.02
  pendingReviewRate <= 0.10
  longestUnanchoredGap <= 8 official tokens
```

When multiple models pass, choose the smallest passing model.

All four Listening Sections must still pass the same reconciliation and timing validation gates before Transcript Shadowing can be released for the pack.

## Timing Artifacts

`transcript-timings.json` is a separate pack asset from `transcript.json`.

ASR Timing Reconciliation does not change the frontend timing contract. The released pack continues to expose `schemaVersion: "yasi.transcript-timings.v1"`; ASR provenance, reconciliation diagnostics, confidence, interpolation notes, and reviewer decisions stay in `build/review/transcript-timing/` release audit artifacts.

The final frontend asset must include:

- schema version;
- overall status, which must be `verified` for frontend consumption;
- section entries;
- word timing entries keyed by section, transcript segment order, and token index;
- positive `[startTime, endTime]` intervals;
- monotonic timing order within each section;
- trace information for reviewed special mappings.

For the active word at playback position \(t\), the frontend uses:

\[
activeWord(t)=i \quad \text{where} \quad start_i \le t < end_i
\]

If a released pack enables Transcript Shadowing, then:

\[
pack.status = released \land shadowingEnabled = true \Rightarrow timings.status = verified
\]

Draft timing artifacts may exist during development, but the static app may not read them as a degraded fallback.

## Reconciliation Algorithm

ASR Timing Reconciliation uses sequence alignment plus anchor interpolation:

```text
Whisper words -> normalize -> align to official tokens -> exact anchors -> interpolate gaps -> review risky mappings
```

The official token sequence \(O=(o_1,\ldots,o_n)\) and ASR token sequence \(A=(a_1,\ldots,a_m)\) should be aligned with dynamic programming. The substitution cost should reward exact normalized matches, allow close normalized matches with a higher cost, and penalize insertions or deletions from either sequence:

\[
D(i,j)=\min
\begin{cases}
D(i-1,j)+c_\text{delete}\\
D(i,j-1)+c_\text{insert}\\
D(i-1,j-1)+c_\text{substitute}(o_i,a_j)
\end{cases}
\]

Exact or high-confidence matches become timing anchors. Official tokens inside a gap receive interpolated intervals only when the surrounding anchors are close enough and monotonic. The interpolation method, gap width, source anchors, and confidence diagnostics must be recorded in review artifacts.

Automatic interpolation is allowed only when all of these are true:

- the gap contains at most 3 official tokens;
- the left and right timing anchors are at most 2.5 seconds apart;
- the gap contains no high-risk token;
- the gap is not near an answer-bearing transcript region.

In compact form:

\[
gapTokens \le 3 \land anchorSpanSeconds \le 2.5 \land risk=false
\]

Any interpolation outside that boundary must enter `alignment-review.json` and cannot produce verified Transcript Word Timings until approved or corrected.

## Transcript Timing Review

Uncertain official-token-to-timing mappings must enter `alignment-review.json`. Review results must be durable JSON, not chat-only approval.

The following cases always require review:

- one official token maps to multiple timing tokens, or multiple official tokens map to one timing token;
- any official token receives an interpolated interval across a wide or low-confidence gap;
- numbers, currency, spelling sequences, abbreviations, apostrophes, and hyphenated forms;
- invalid or suspicious time intervals, including overlap, large gaps, and unusually short or long durations;
- normalized ASR text still disagrees with normalized official text;
- low-confidence or special mappings near answer-bearing transcript regions.

The review artifact uses explicit decisions:

- `pending`: mapping still needs review and prevents final verification;
- `approved`: the automatic timing is correct;
- `corrected`: the reviewed correction supplies the final timing interval;
- `rejected`: the mapping is invalid and prevents final verification unless replaced by a correction.

Each review item must include `matchType` so reviewers can tell how the timing was derived:

- `exact`: one official token directly matches one ASR word after normalization;
- `fuzzy`: one official token is close to one ASR word after normalization or similarity scoring;
- `interpolated`: timing was estimated from surrounding anchors;
- `split`: one official token maps across multiple ASR words;
- `merged`: multiple official tokens map to one ASR word or one shared ASR span;
- `unmatched`: no reliable ASR timing evidence exists for the official token.

Default trust levels:

- `exact` may auto-pass only when the interval is valid and no risk rule applies;
- `fuzzy`, `interpolated`, `split`, and `merged` need diagnostics and may require review depending on risk rules;
- `unmatched` blocks final verification until corrected.

The final timing asset is produced only after approved or corrected review entries are applied.

Benchmark `alignment-review.json` files stay under the temporary ASR Timing Reconciliation working root. When a review artifact is used to produce a released verified `transcript-timings.json`, that exact review trace becomes a Transcript Timing Release Audit and must be promoted under `build/review/transcript-timing/`. The release audit must preserve reviewer decisions, corrections, `matchType`, risk types, and source timing evidence references needed to explain every non-trivial verified timing.

Recommended release audit layout:

```text
build/review/transcript-timing/
  cambridge-10-test-1-listening/
    alignment-review.json
    reconciliation-report.json
```

## Frontend Layout

Transcript Shadowing uses a three-column workspace when open:

1. left: existing Question Scroll Area;
2. middle: Transcript Shadowing Panel;
3. right: existing action rail.

The Transcript Shadowing action remains visible when the pack lacks verified timings, but it is disabled with a short hint such as `等待逐词时间轴`.

Opening the panel does not autoplay, pause, seek, or reset audio. It preserves the current section playback state and current time.

## Transcript Panel Behavior

The panel displays the entire current Listening Section transcript.

It does not display:

- speaker labels;
- `Q1`, `Q2`, or other answer reference markers;
- copy controls.

The current word uses a pale yellow background and stronger text weight. The current segment receives only a subtle background so it remains context rather than the main focus.

Default behavior is automatic follow:

- playback keeps the active word near the vertical middle of the panel;
- manual transcript scrolling temporarily disables follow;
- a `跟随当前词` control restores automatic follow;
- clicking any word seeks the section audio to that word's `startTime`;
- click-to-seek does not fill answers and does not scroll the question surface.

## Session And Marking

Opening Transcript Shadowing sets `transcriptViewed: true` in the current Practice Session.

This flag is persisted to `localStorage`. It survives:

- panel close;
- section navigation;
- return home and resume;
- page refresh.

It is cleared only by reset.

Submission remains allowed after transcript viewing. Marking still shows the score, but the feedback enters Transcript-Viewed Marking Feedback and must label the result as practice reference, for example: `已查看原文，本次分数仅作练习参考`.

The score remains useful for review, but it is no longer exam-equivalent because official transcript exposure can reveal answers.

## Implementation Surface

Builder and pack loading:

- add an optional manifest asset for `transcriptTimings`;
- load timings only when present and verified;
- keep `transcript.json` schema as official text authority;
- extend release validation for verified timing status, full-section coverage, monotonic intervals, and durable review trace.
- require `transcript-timings.json.reviewArtifact` to be a repo-root-relative path that resolves to `build/review/transcript-timing/<pack-id>/alignment-review.json` for released packs;
- reject release when the review artifact is missing, has pending decisions, or fails to cover every timing entry that requires review.

Example:

```json
{
  "reviewArtifact": "build/review/transcript-timing/cambridge-10-test-1-listening/alignment-review.json"
}
```

React components:

- add `TranscriptShadowingPanel`;
- update `ExamWorkspace` for three-column layout, panel toggle, timing lookup, and audio time propagation;
- update `PracticeActions` to enable or disable Transcript Shadowing based on timing availability;
- update Practice Session persistence with `transcriptViewed`;
- update `MarkingFeedback` with Transcript-Viewed Marking Feedback.

## Verification

Python verification:

- ASR Timing Reconciliation dry-run for Section 01;
- local Whisper CLI smoke test with `PYTHONUTF8=1` and `--word_timestamps True`;
- fixture validation for timing JSON and `alignment-review.json`;
- release validation fails when verified timings are incomplete, non-monotonic, missing durable review trace, missing required review coverage, or missing sections for pack release;
- Section 01 pilot artifacts may validate without weakening the full-pack release gate.

Vitest verification:

- timing lookup chooses the correct active word for a given `currentTime`;
- Transcript Shadowing button availability follows verified timing state;
- opening the panel preserves audio position and playback state;
- clicking a word seeks to `startTime`;
- manual scroll disables auto-follow and the follow control restores it;
- `transcriptViewed` persists and clears only on reset;
- feedback label appears after transcript viewing.

Playwright verification:

- three-column desktop layout does not overlap at `1440x900` and `1920x1080`;
- disabled button hint appears without verified timings;
- Section 01 pilot can show the panel in development validation;
- opening and closing the panel does not reset audio;
- submitting after transcript viewing shows practice-reference feedback.

## Explicit Non-Goals

- No microphone recording.
- No pronunciation scoring.
- No generated transcript display.
- No runtime browser alignment.
- No approximate equal-duration word pacing.
- No copy transcript action.
- No user-visible Section-only production release inside a mixed-coverage pack.
