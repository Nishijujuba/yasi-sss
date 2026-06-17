# Build Official Mistake Vocabulary Audio Clips

Status: Superseded by ADR 0006 for the primary Mistake Vocabulary Notebook audio path.

Mistake Vocabulary Cards will play official audio excerpts generated during the practice-pack build. The builder will align each blank-answer canonical term to a time window in the section MP3, cut a standalone clip with FFmpeg, validate the clip, and publish it with `vocabulary.json` so the static React app only plays ready-made assets.

## Considered Options

- Browser text-to-speech: easy to ship, weak for IELTS listening because pronunciation, accent, and phrase rhythm depend on the user's browser voice.
- Runtime section-range playback: avoids extra files, fragile for repeated card practice because browser timing and pause boundaries can drift.
- Build-time clip generation: adds alignment and validation work, gives stable assets for ordered and random notebook practice.

## Consequences

The practice-pack pipeline now owns answer-level audio alignment and clip validation. A pack with missing or invalid Mistake Vocabulary Audio Clips should fail release validation instead of degrading to full-section replay or generated pronunciation.
