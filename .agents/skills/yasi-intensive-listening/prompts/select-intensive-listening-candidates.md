# Select Intensive Listening Candidates

Use this prompt template to ask a model for section-scoped Yasi Intensive Listening candidate source JSON.

```text
You are selecting Yasi Intensive Listening candidate blanks for exactly one IELTS Listening Section.

Inputs:
- pack_id: {{pack_id}}
- section: {{section_number}}
- source_file: {{source_file}}
- official_transcript_section_json:
{{official_transcript_section_json}}

Task:
Choose high-value IELTS intensive-listening candidates from the official transcript Section. Use answer-bearing spans, spelling-risk words, proper nouns, numbers, compounds, weak forms, connected-speech phrases, distractor contrasts, and phrase boundaries when they create real listening value.

Hard boundaries:
- Output only the candidate source JSON object.
- Never generate public/packs/.../intensive-listening.json.
- Never update manifest JSON.
- Never create frontend, builder, timing, score, or audio-alignment data.
- Use only official transcript text and verified token locations.

Token rules:
- Token indices are zero-based within each official transcript segment.
- startTokenIndex is inclusive.
- endTokenIndex is exclusive.
- Candidate text must equal the official token span joined with single spaces.
- Skip any span whose token indices are uncertain.

Required JSON shape:
{
  "schemaVersion": "yasi.intensive-listening-candidates.v1",
  "section": {{section_number}},
  "candidates": [
    {
      "section": {{section_number}},
      "segmentOrder": 1,
      "startTokenIndex": 0,
      "endTokenIndex": 1,
      "text": "example",
      "reason": "One concise sentence explaining IELTS listening value.",
      "tags": ["answer-bearing"]
    }
  ]
}

Validation before output:
- The top-level section and every candidate section match {{section_number}}.
- Every segmentOrder exists in the official transcript Section.
- Every token span is ordered and in range.
- Candidate text matches the official transcript span exactly.
- Tags are non-empty, unique, and kebab-case.
- Candidates are sorted by segmentOrder and startTokenIndex.
- No two candidates overlap in the same Section.

Return strict JSON only. Do not use Markdown fences. Do not add comments or prose.
```
