# Selection Policy

Use this policy when choosing Yasi Intensive Listening candidates from an official IELTS Listening Section transcript.

## Goal

Choose spans that train recognition, spelling, and word-boundary control. A useful blank should make the learner listen more precisely than ordinary transcript reading would.

## Strong Candidates

- Answer-bearing spans from segments with `answerRefs`, especially form-completion answers.
- Proper nouns, place names, organization names, road names, and named attractions.
- Numbers, prices, dates, times, measurements, phone numbers, postcodes, and route details.
- Compounds and lexical chunks where the boundary is easy to miss, such as `self-drive tour` or `theme parks`.
- Noun phrases that carry IELTS task information, especially labels, categories, and destinations.
- Spelling-risk words: uncommon spellings, silent letters, doubled letters, hyphenation, and easily confused vowels.
- Weak-form or connected-speech spans where the learner may hear a reduced form.
- Distractor or contrast spans that distinguish the correct detail from a nearby rejected detail.
- Signpost phrases when they carry task structure, sequence, or correction value.

## Weak Candidates

- Single high-frequency function words, such as articles, auxiliaries, and prepositions.
- Long clauses that test memory or reading comprehension more than listening precision.
- Spans whose value depends on background knowledge rather than the official audio.
- Repeated filler, greetings, backchannels, and discourse padding.
- Token spans with ambiguous indexing under the builder tokenizer.
- Overlapping spans. For two spans in the same segment, `[a,b)` and `[c,d)` are compatible only when `b <= c` or `d <= a`.

## Candidate Count

Use no artificial cap. Include every high-value candidate that passes the schema rules, then stop. Quality matters more than a round number.

## Tie Breakers

When two candidates compete for the same words, prefer this order:

1. Official-answer or answer-bearing span.
2. Shorter exact phrase with the same learning value.
3. Higher spelling or word-boundary risk.
4. Earlier span in transcript order.

## Review Standard

Every candidate needs a reason that explains the listening value in one concise sentence. Tags must describe the pedagogical value, such as `answer-bearing`, `form-completion`, `proper-noun`, `spelling-risk`, `number`, `compound`, `weak-form`, or `distractor-contrast`.
