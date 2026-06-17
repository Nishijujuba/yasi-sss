# Transcript Shadowing Design

## Purpose

Add Transcript Shadowing to the Cambridge IELTS listening practice app. The learner can open official English audioscript text beside the original question surface while official section audio plays. The panel highlights the currently spoken word from verified word-level timings and supports click-to-seek for replay.

This feature is for follow-reading and listening review. It excludes recording, microphone access, speaking scores, pronunciation assessment, generated transcript display, and copy-to-clipboard.

## Product Decisions

- The displayed text authority is always `transcript.json`, the reviewed official audioscript asset.
- Qwen alignment output is timing evidence only. It never silently replaces official text.
- The v1 forced-alignment entrypoint is the project skill `yasi-forced-alignment`.
- The public frontend consumes only verified timing assets.
- Complete pack release requires verified Transcript Shadowing coverage for all four Listening Sections.
- Section 01 may be used as a development-only Transcript Alignment Pilot to validate the full workflow before expanding to Sections 02-04.
- The user may open Transcript Shadowing before submission. Once opened, the current practice session is marked as transcript-viewed until reset.

## Alignment Workflow

The build-time chain is:

```text
Qwen raw timings -> auto mapping draft -> alignment-review.json -> transcript-timings.json
```

The `yasi-forced-alignment` skill owns the reusable workflow and scripts:

- `.agents/skills/yasi-forced-alignment/SKILL.md`
- `.agents/skills/yasi-forced-alignment/scripts/align_transcript.py`
- `.agents/skills/yasi-forced-alignment/scripts/validate_timings.py`

The alignment script invokes the local Qwen ASR wrapper and `D:\model-repo\Qwen3-ForcedAligner-0.6B` through the verified local environment. Its dry-run mode checks paths and emits the wrapper command without loading models.

## Timing Artifacts

`transcript-timings.json` is a separate pack asset from `transcript.json`.

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

## Transcript Timing Review

Uncertain official-token-to-timing mappings must enter `alignment-review.json`. Review results must be durable JSON, not chat-only approval.

The following cases always require review:

- one official token maps to multiple timing tokens, or multiple official tokens map to one timing token;
- numbers, currency, spelling sequences, abbreviations, apostrophes, and hyphenated forms;
- invalid or suspicious time intervals, including overlap, large gaps, and unusually short or long durations;
- normalized Qwen text still disagrees with normalized official text;
- low-confidence or special mappings near answer-bearing transcript regions.

The review artifact uses explicit decisions:

- `pending`: mapping still needs review and prevents final verification;
- `approved`: the automatic timing is correct;
- `corrected`: the reviewed correction supplies the final timing interval;
- `rejected`: the mapping is invalid and prevents final verification unless replaced by a correction.

The final timing asset is produced only after approved or corrected review entries are applied.

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
- extend release validation for verified timing status, full-section coverage, monotonic intervals, and review trace.

React components:

- add `TranscriptShadowingPanel`;
- update `ExamWorkspace` for three-column layout, panel toggle, timing lookup, and audio time propagation;
- update `PracticeActions` to enable or disable Transcript Shadowing based on timing availability;
- update Practice Session persistence with `transcriptViewed`;
- update `MarkingFeedback` with Transcript-Viewed Marking Feedback.

## Verification

Python verification:

- `yasi-forced-alignment` dry-run for Section 01;
- fixture validation for timing JSON and `alignment-review.json`;
- release validation fails when verified timings are incomplete, non-monotonic, missing review trace, or missing sections for pack release;
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
