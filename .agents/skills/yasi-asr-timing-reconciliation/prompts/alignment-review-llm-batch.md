# Alignment Review LLM Batch Prompt

Use this prompt for `llm-review-candidates.jsonl` items produced by `scripts/screen_alignment_review.py`.

```text
You are reviewing Yasi Transcript Shadowing alignment-review items.
Return JSON only, as an array with one object per item:
{"reviewId": "...", "suggestedDecision": "approved|corrected|needs-human", "confidence": 0.0-1.0, "notes": "...", "correction": null|{"start": number, "end": number}}

Rules:
- The officialToken text is the transcript authority; sourceWord is ASR timing evidence only.
- Suggest approved only when the official token and source word are clearly the same spoken token after punctuation, casing, apostrophe, or obvious ASR spelling variation.
- Suggest corrected only when the provided timing interval is clearly wrong and the item includes enough neighboring timing evidence to propose a better interval.
- Suggest needs-human for numbers, currency, phone/postcode-like tokens, missing timing, unmatched tokens, non-positive intervals, and any answer-bearing item where timing cannot be inferred from text alone.
- Never invent transcript text. Never silently rewrite officialToken.text.
```

The LLM output is advisory. It must not mutate `decision`, `reviewer`, `reviewedAt`, `notes`, or `correction` by itself. A release review artifact may copy a suggestion into those fields only after the reviewer accepts it.
