# Generated Answer Audio For Mistake Vocabulary Design

## Purpose

Replace the current official-audio slice approach for Mistake Vocabulary Notebook audio with deterministic pre-generated answer-pronunciation audio.

The current slice-based clips are structurally fragile because they depend on manually supplied answer time windows. The project already has all accepted answers before release, so the notebook should use that answer authority directly for its audio assets.

## Decisions

- Mistake Vocabulary Cards play generated answer-pronunciation audio, not official section excerpts.
- Each card generates audio only for the canonical first accepted answer.
- Accepted variants remain visible as text and remain valid for practice answer matching.
- `VocabularyItem` gains `spokenText`, the exact text sent to the pronunciation generator.
- `term` remains the displayed canonical answer and the card identity input.
- `spokenText` is not used for Strict Marking.
- Normal word and phrase terms default to `spokenText = term`.
- Numeric canonical answers use explicit value reading in `spokenText`.
- `429` uses `four hundred twenty-nine`.
- `2020` uses `two thousand twenty`.
- The build uses Windows `System.Speech` with `Microsoft Zira Desktop` to generate WAV files, then FFmpeg converts them to MP3.
- `answer-audio-windows.json` leaves the formal release gate and build path.
- The static React app keeps playing `vocabulary.json` audio paths and does not know about TTS or audio windows.

## Current Problem

The existing `answer-audio-windows.json` gives one start/end window per vocabulary item. Those windows can satisfy file and duration checks while still pointing at the wrong moment in the official section audio. That makes the release gate green while the learner hears unrelated audio.

The core mismatch is:

```text
clip = sectionAudio[startTime - paddingBefore, endTime + paddingAfter]
```

Known answers provide `term`, but they do not provide reliable `startTime` and `endTime`. Without forced alignment or manual listening review, the current model cannot guarantee semantic correctness.

## Data Model

`vocabulary.json` keeps one item per single blank-answer canonical term:

```json
{
  "id": "429",
  "term": "429",
  "normalizedTerm": "429",
  "spokenText": "four hundred twenty-nine",
  "acceptedVariants": [],
  "meaningZh": "四二九，号码",
  "audio": "assets/audio/vocabulary/429.mp3"
}
```

For ordinary terms:

```json
{
  "id": "photo-card",
  "term": "photo card",
  "normalizedTerm": "photo card",
  "spokenText": "photo card",
  "acceptedVariants": ["photo cards"],
  "meaningZh": "照片卡",
  "audio": "assets/audio/vocabulary/photo-card.mp3"
}
```

`spokenText` is a pronunciation input. It is deliberately separate from `term` so generated audio can say natural English while the displayed answer and marking value stay faithful to the answer key.

## Build Flow

1. Load `answers.json`, `questions.json`, and `vocabulary.json`.
2. Derive the canonical single blank-answer terms from answer rules.
3. Validate that every vocabulary item matches its canonical answer.
4. Validate `spokenText` is non-empty.
5. Generate a temporary WAV for each item by passing `spokenText` to Windows `System.Speech`.
6. Convert the WAV to MP3 with FFmpeg.
7. Publish the MP3 to `assets/audio/vocabulary/<id>.mp3`.
8. Archive failed temporary artifacts under `待删除` when they need inspection.

The builder should continue to use existing safe publish behavior: generate to a temporary path, compare or replace, and leave cleanup to the user when a file must be moved aside.

## Release Gate

Validation blocks release when:

- a blank canonical term lacks a vocabulary item;
- a vocabulary item has an empty `meaningZh`;
- a vocabulary item has an empty `spokenText`;
- two vocabulary IDs collide;
- two normalized terms collide;
- a generated MP3 is missing or empty;
- a generated MP3 has invalid duration;
- the Windows voice required by the build is unavailable;
- FFmpeg or FFprobe is unavailable.

The release gate no longer requires answer audio windows because windows are unrelated to generated answer pronunciation.

## Frontend Behavior

No user-facing control changes are required. The notebook continues to:

- play `VocabularyItem.audio`;
- show `VocabularyItem.term`;
- show accepted variants;
- compare practice input against `term` and accepted variants;
- ignore `spokenText` during answer checking.

## Error Handling

The build fails closed. Missing speech voices, TTS failures, conversion failures, empty audio, or invalid durations must not silently degrade to browser text-to-speech or full section replay.

For the app runtime, a missing audio file remains a pack diagnostic: the card can stay visible, but play should fail visibly rather than pretending the notebook is healthy.

## Testing

### Python Builder Tests

- `VocabularyItem` accepts and requires `spokenText`.
- vocabulary release validation rejects empty `spokenText`.
- generated audio uses `spokenText`, not `term`.
- numeric items include explicit `spokenText` values for `429` and `2020`.
- build no longer requires `answer-audio-windows.json`.
- MP3 existence and duration validation still runs.
- missing Windows voice produces a clear build error.

### TypeScript Tests

- pack loading requires `spokenText`.
- `MistakeVocabularyView` still checks practice answers against `term` and `acceptedVariants`.
- `spokenText` does not become visible answer text unless a future diagnostic view intentionally exposes it.

## Risks

Windows desktop TTS is less natural than modern cloud neural voices. The trade-off is acceptable because the notebook needs stable pronunciation assets for spelling recall and local repeatable builds.

Numeric readings need explicit review. `spokenText` keeps this reviewable in source data rather than hiding pronunciation behavior in generator code.

Official section-context listening remains valuable, but it needs a separate forced-alignment workflow. Mixing that unfinished alignment problem into the notebook audio path makes the current product worse.
