# Use Generated Answer Audio For Mistake Vocabulary

Mistake Vocabulary Cards will use pre-generated answer-pronunciation audio derived from the canonical first accepted answer. The builder will send each vocabulary item's `spokenText` to Windows `System.Speech` using `Microsoft Zira Desktop`, convert the generated WAV to MP3 with FFmpeg, and publish the result under `assets/audio/vocabulary/`.

This supersedes ADR 0005 for the primary notebook audio path.

## Considered Options

- Repair official section slices: preserves original IELTS audio context, but still depends on reliable answer-level alignment that the current source data does not provide.
- Keep dual audio tracks: preserves future optionality, but complicates the data model and leaves broken official slices close to the active product path.
- Generate answer-pronunciation audio: uses the answer authority already available at build time, gives deterministic assets, and keeps the static React app simple.

## Consequences

`VocabularyItem` now records `spokenText` separately from the displayed canonical `term`. Numeric answers such as `429` and `2020` can be pronounced as natural values while marking continues to use the answer-key form.

The release gate no longer requires `answer-audio-windows.json`. Official section-context clips require a future forced-alignment workflow before they can become a release-blocking asset again.
