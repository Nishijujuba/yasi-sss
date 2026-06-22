---
status: superseded by ADR-0008
---

# Use Localization ASR For Forced Alignment Slicing

> **2026-06-22 update:** The project skill package `.agents\skills\yasi-forced-alignment\` has been archived under `D:\Project\yasi\待删除\yasi-forced-alignment\archived-skill-2026-06-22\yasi-forced-alignment\`. This ADR remains historical context for the abandoned Qwen forced-alignment route. Active Transcript Shadowing timing work uses ADR-0008 and `.agents\skills\yasi-asr-timing-reconciliation\`.

Transcript Alignment will use a short-lived localization transcript to find where the official audioscript begins inside the raw listening audio and to estimate per-slice official token ranges before running Qwen3-ForcedAligner. The official `transcript.json` remains the Transcript Text Authority for all displayed text, timing identity, review traces, and final pack artifacts.

This records the boundary between timing evidence and text authority. Cambridge listening audio can contain example audio, section instructions, pauses, and other speech that is absent from the official audioscript. Aligning a 180-second audio slice against the full section transcript creates an unstable alignment task because the audio window and text window describe different spans.

## Considered Options

- Align full section audio against the full official transcript: simple command shape, yet long sections with non-transcript audio can stall or produce shifted timings.
- Slice only the audio: reduces audio length, yet each short audio slice still receives unrelated official text unless the text is sliced too.
- Use ASR output as the transcript: provides time anchors, yet it violates Transcript Text Authority and can rewrite spellings, names, numbers, currency, and answer-bearing words.
- Use ASR only for localization: provides coarse time anchors while final alignment text still comes from the official transcript.

## Decision

Use localization ASR as timing evidence only. For any section audio over the configured slice threshold, the alignment workflow must:

- locate `contentStartSeconds`, the point where official audioscript content begins in the raw audio;
- build a coarse map from official transcript tokens to localization transcript times;
- create localized slices that pair each audio window with the matching official transcript token range;
- align each slice using only official transcript text derived from `transcript.json`;
- offset slice-local timings back to the original section timeline;
- merge overlapping slice output into one section-level timing artifact.

If localization confidence is below the configured threshold, the workflow must stop and request either a corrected localizer artifact or a manual `--content-start-seconds` value.

## Consequences

The forced-alignment pipeline gains a preprocessing stage before Qwen model loading. This stage adds deterministic artifacts under `待删除\yasi-forced-alignment`, including a localization transcript, content-start evidence, localized slice plans, slice audio files, and slice official-text files.

`SKILL.md` must describe ASR as a localization aid only. Future agents should avoid treating ASR text as display text, answer evidence, or a replacement for the official transcript. Dry-run output must show the localization decision, confidence score, audio ranges, official token ranges, and text previews before any GPU job starts.
