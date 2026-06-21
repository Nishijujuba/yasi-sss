# Candidate Schema

Candidate source files are section-scoped JSON documents for the builder. They are inputs, not released pack assets.

## File Location

Use one file per Section:

```text
builder/source_data/intensive-listening-candidates-section-01.json
builder/source_data/intensive-listening-candidates-section-02.json
builder/source_data/intensive-listening-candidates-section-03.json
builder/source_data/intensive-listening-candidates-section-04.json
```

## Top-Level Shape

The JSON document must be an object with exactly these fields:

```json
{
  "schemaVersion": "yasi.intensive-listening-candidates.v1",
  "section": 1,
  "candidates": []
}
```

Field rules:

- `schemaVersion`: exactly `"yasi.intensive-listening-candidates.v1"`.
- `section`: integer `1`, `2`, `3`, or `4`; it must match the filename Section.
- `candidates`: array of candidate objects sorted by `segmentOrder`, then `startTokenIndex`.
- Extra top-level fields are invalid.

## Candidate Shape

Each item in `candidates` must use exactly these fields:

```json
{
  "section": 1,
  "segmentOrder": 12,
  "startTokenIndex": 8,
  "endTokenIndex": 10,
  "text": "photo card",
  "reason": "IELTS form-completion noun phrase with spelling and word-boundary value.",
  "tags": ["form-completion", "noun-phrase", "spelling-risk"]
}
```

Field rules:

- `section`: integer matching the top-level `section`.
- `segmentOrder`: positive integer matching an official transcript segment `order` in that Section.
- `startTokenIndex`: zero-based integer index into the segment's builder word tokens.
- `endTokenIndex`: zero-based exclusive end index; it must satisfy `0 <= startTokenIndex < endTokenIndex`.
- `text`: exact official span text formed from tokens in `[startTokenIndex, endTokenIndex)`, joined with single spaces, preserving official spelling and case.
- `reason`: non-empty sentence explaining IELTS listening value.
- `tags`: non-empty array of unique kebab-case strings.
- Extra candidate fields are invalid. `acceptedVariants`, released blank `id`, `answer`, timings, scores, UI labels, and manifest paths are outside this source schema.

## Span Rules

- Token indices address transcript text only, never speaker names.
- Punctuation-only marks are not blank candidates.
- Avoid candidates whose tokenization is uncertain. Choose a cleaner span or ask for the builder tokenizer output.
- Candidates in the same Section must not overlap. Within one segment, `[s1,e1)` and `[s2,e2)` overlap when `s1 < e2` and `s2 < e1`.
- Duplicate locations are invalid even when `text`, `reason`, or `tags` differ.

## Output Rules

Return strict JSON only when asked for machine-readable output. Markdown fences, comments, trailing commas, and explanatory prose make the output invalid.
