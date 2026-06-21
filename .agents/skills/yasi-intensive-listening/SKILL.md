---
name: yasi-intensive-listening
description: Use when selecting, reviewing, or drafting section-scoped Yasi Intensive Listening candidate JSON from official IELTS listening transcript/audioscript data, especially builder/source_data/intensive-listening-candidates-section-XX.json source files.
---

# Yasi Intensive Listening

## Overview

Use this skill to produce section-scoped candidate source JSON for one Yasi IELTS Listening Section. The candidates identify official transcript token spans with Intensive Listening value; the builder owns released assets, manifest wiring, and validation.

## Hard Boundaries

- Output only candidate source JSON for `builder/source_data/intensive-listening-candidates-section-XX.json`.
- Never generate `public/packs/.../intensive-listening.json`.
- Never update `manifest.json`.
- Never touch frontend code, builder code, tests, or pack assets.
- Never download models, run ASR, run forced alignment, or run audio alignment.
- Never invent transcript text, segment orders, token indices, reasons, or tags.

## Required Inputs

- Pack or source context, such as `public/packs/<book>/<test>/listening/transcript.json` or `builder/source_data/transcript-section-XX.json`.
- Exactly one Section number, `1` through `4`.
- Official segment text with segment order. `answerRefs` are useful for priority, while the transcript remains the span authority.

Ask for the missing input before producing JSON when any required input is unavailable.

## Workflow

1. Read `references/selection-policy.md` for candidate value rules.
2. Read `references/candidate-schema.md` for the strict source JSON contract.
3. Tokenize each official transcript segment with the same word-token convention expected by the builder. Use zero-based token indices and half-open spans: `[startTokenIndex, endTokenIndex)`.
4. Select high-value IELTS listening spans. Prefer answer-bearing words, spelling-sensitive items, compounds, proper nouns, numbers, weak forms, and phrase boundaries. Avoid padding with low-value function words.
5. Verify every candidate against the official transcript: correct Section, existing segment, ordered indices, exact span text, non-empty reason, unique tags, and no overlap in the same Section.
6. Return strict JSON matching the schema. For model-assisted selection, use `prompts/select-intensive-listening-candidates.md` as the prompt template.

## Resources

- `references/selection-policy.md`: IELTS listening candidate selection rules.
- `references/candidate-schema.md`: strict source JSON schema and field rules.
- `prompts/select-intensive-listening-candidates.md`: reusable prompt template for strict JSON output.
- `fixtures/sample-candidates-section-01.json`: minimal valid candidate source example.
