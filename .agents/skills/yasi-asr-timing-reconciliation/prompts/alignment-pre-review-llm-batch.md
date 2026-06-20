# Alignment Blind Pre-Review LLM Batch Prompt

Use this prompt for `llm-pre-review-candidates.jsonl` items produced by `scripts/screen_alignment_review.py`.

```text
You are doing blind pre-review for Yasi Transcript Shadowing alignment-review items.
Return JSON only, as an array with one object per item:
{"reviewId": "...", "suggestedDecision": "approved|corrected|needs-human", "confidence": 0.0-1.0, "notes": "...", "correction": null|{"start": number, "end": number}, "preReviewLabel": "likely-safe|needs-auditory-review|needs-manual-timing|reject-evidence"}

Rules:
- This is advisory pre-review only. Do not claim final release approval.
- Use only the supplied officialToken, sourceWord, timing, context, risks, and reasons. Do not rely on audio listening.
- Keep officialToken text as the transcript authority; sourceWord is ASR timing evidence only.
- Mark numbers, currency, spelling sequences, missing timing, unmatched tokens, and answer-near uncertainty as needs-auditory-review or needs-manual-timing unless the text and interval are unquestionably safe.
- Suggest approved only when token identity and interval evidence are straightforward.
- Suggest corrected only when the item includes enough neighboring timing evidence to propose a concrete interval.
- Never invent transcript text. Never silently rewrite officialToken.text.
```

The output is imported with `scripts/apply_llm_pre_review.py`. The script attaches the result as `screening.llmSuggestion` and leaves `decision` unchanged.
