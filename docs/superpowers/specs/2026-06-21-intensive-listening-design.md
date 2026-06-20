# Intensive Listening Design

## Purpose

Add section-scoped Intensive Listening practice to the Cambridge IELTS listening app. Each Listening Section gets one pre-generated fill-in-the-blank drill set derived from the official audioscript. The learner enters the drill only after submitting the corresponding original Listening Section.

The feature trains IELTS listening recognition and spelling. It focuses on words and phrases that are frequent, answer-bearing, spelling-sensitive, or easy to miss in connected speech. It is separate from Exam Simulation, Transcript Shadowing, and the Mistake Vocabulary Notebook.

## Decisions

- Each Listening Section has its own Intensive Listening Drill Set.
- Drill sets are generated before release and stored in the practice pack.
- The learner can open a Section drill only after submitting that original Section.
- Original answer-bearing transcript regions may become Intensive Listening blanks.
- The LLM skill outputs only candidate blanks: word or phrase text plus official transcript location.
- Candidate location uses a Transcript Token Span: `section`, `segmentOrder`, `startTokenIndex`, and `endTokenIndex`.
- Candidate sources are section-scoped JSON files under `builder/source_data/`.
- The builder generates the pack-level `intensive-listening.json` asset.
- `manifest.assets.intensiveListening` points the frontend to the generated asset.
- Blank IDs are stable and derived from section, segment order, and token span.
- Final blanks in the same Section cannot overlap.
- Candidate `reason` and `tags` are retained for review metadata, while the learner-facing drill hides them by default.
- Intensive Listening uses independent local session state.
- `提交精听`, `查看答案`, and `查看原文` are separate actions.
- Marking is strict: trim, collapse whitespace, lowercase, then compare with the official span text or explicit accepted variants.

## Architecture

The implementation has three layers.

The `yasi-intensive-listening` skill reads official transcript data and selects candidate words or phrases for one Section. It uses IELTS listening value as the selection rule and emits reviewable candidate source JSON. It does not generate frontend assets, update manifests, or change app code.

The builder reads the candidate sources, validates them against `transcript.json`, resolves official answer text from token spans, checks non-overlap, derives stable IDs, and writes `intensive-listening.json`.

The frontend loads `intensive-listening.json` through the manifest. It uses original Practice Session state only to decide which Section drills are unlocked, then stores Intensive Listening answers and reveal state in a separate localStorage record.

## Candidate Source Contract

The skill writes one source file per Section:

```text
builder/source_data/intensive-listening-candidates-section-01.json
builder/source_data/intensive-listening-candidates-section-02.json
builder/source_data/intensive-listening-candidates-section-03.json
builder/source_data/intensive-listening-candidates-section-04.json
```

Each candidate uses this shape:

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

The `text` field is a self-check and review aid. The builder must derive the released `answer` from official transcript tokens instead of trusting candidate text.

## Released Asset Contract

The builder emits:

```text
public/packs/<book-id>/<test-id>/listening/intensive-listening.json
```

The asset shape is:

```json
{
  "schemaVersion": "yasi.intensive-listening.v1",
  "sections": [
    {
      "section": 1,
      "blanks": [
        {
          "id": "il-s01-seg012-t008-t010",
          "segmentOrder": 12,
          "startTokenIndex": 8,
          "endTokenIndex": 10,
          "answer": "photo card",
          "acceptedVariants": [],
          "reason": "IELTS form-completion noun phrase with spelling and word-boundary value.",
          "tags": ["form-completion", "noun-phrase", "spelling-risk"]
        }
      ]
    }
  ]
}
```

`manifest.json` gains:

```json
{
  "assets": {
    "intensiveListening": "intensive-listening.json"
  }
}
```

## Builder And Validation

The builder must:

- load `transcript.json` plus the four candidate source files;
- tokenize official transcript text with the same word-token rules used by Transcript Shadowing;
- verify every candidate section and segment exists;
- verify token indices are in range and ordered;
- verify normalized candidate `text` matches the official token span;
- reject overlapping blanks in the same Section;
- require non-empty `reason` and at least one tag;
- derive `answer` from official transcript tokens;
- derive stable blank IDs from location;
- write `intensive-listening.json`;
- update `manifest.assets.intensiveListening`.

`validate_pack.py` must fail release when the manifest points to a missing or malformed Intensive Listening asset, when a blank span does not map back to the official transcript, when IDs collide, when answers disagree with official text, or when Section blanks overlap.

Overlapping candidates should fail validation with a clear conflict report. Silent dropping would make drill quality depend on hidden program behavior.

## Frontend Behavior

The app gains an Intensive Listening view. The home screen and workspace action rail can expose a `精听` entry.

Availability is Section-scoped:

- Section 01 submission unlocks Section 01 Intensive Listening.
- Section 02 stays locked until Section 02 has been submitted.
- Whole-test completion is not required for a Section drill that is already unlocked.

The drill surface displays the complete official audioscript for the current Section. Selected token spans render as answer inputs, while other transcript text remains visible. Section MP3 playback and playback-rate controls are reused. If transcript timing data is available, the drill may support seek-to-blank behavior; the drill remains usable with ordinary audio controls if timing data is unavailable.

The session state uses a separate localStorage key such as:

```text
yasi:<pack-id>:intensive-listening:v1
```

The state stores per-Section answers, marking result, `answerRevealed`, and `transcriptRevealed`. It does not modify original Exam Simulation answers, original scores, or Mistake Vocabulary Notebook state.

Actions:

- `提交精听`: marks current inputs with strict Intensive Listening Marking.
- `查看答案`: reveals correct blank spellings and marking results.
- `查看原文`: reveals the full unblanked official audioscript and marks the current drill as reference-only.
- `重置精听`: clears only Intensive Listening state.

## Skill Package

Create `.agents/skills/yasi-intensive-listening/`.

Recommended contents:

- `SKILL.md`: trigger, inputs, output boundary, workflow, and hard rule that the skill outputs candidate sources only.
- `references/selection-policy.md`: IELTS listening selection criteria such as form-completion terms, proper nouns, numbers, compounds, spelling risk, weak forms, and phrase boundaries.
- `references/candidate-schema.md`: candidate source schema and field rules.
- `prompts/select-intensive-listening-candidates.md`: reusable prompt template for strict JSON output.
- `fixtures/sample-candidates-section-01.json`: minimal candidate example.
- `agents/openai.yaml`: UI-facing metadata for the Yasi Intensive Listening skill.

The skill should not download models, run audio alignment, generate `intensive-listening.json`, or touch frontend code.

## Testing

Python tests:

- candidate schema validation accepts valid Section sources;
- validation rejects missing section, missing segment, invalid token span, text mismatch, empty rationale, empty tags, duplicate IDs, and overlapping blanks;
- builder derives `answer` from official transcript tokens;
- builder writes `intensive-listening.json` and updates manifest;
- release validation rejects missing or malformed `manifest.assets.intensiveListening`.

TypeScript tests:

- pack loading accepts and validates `intensiveListening`;
- strict Intensive Listening Marking handles case and whitespace normalization;
- Section unlock follows original Section submission state;
- Intensive Listening state is independent from Practice Session state;
- answer reveal and transcript reveal produce distinct state transitions.

Browser tests:

- locked Section drill cannot be opened before Section submission;
- submitting Section 01 unlocks Section 01 drill only;
- a drill displays full Section transcript with blanks in selected spans;
- `提交精听`, `查看答案`, `查看原文`, and `重置精听` work independently;
- playback rate controls remain usable inside the drill.

## Risks

The biggest product risk is answer leakage. The mitigation is Section-scoped runtime availability: answer-bearing candidates can exist in pre-generated assets, while the learner cannot open a Section drill until after submitting that Section.

The biggest data-quality risk is LLM location drift. The mitigation is builder validation against official transcript token spans, with official span text as the answer authority.

The biggest maintainability risk is schema drift between skill output and builder expectations. The mitigation is a dedicated candidate schema reference, fixtures, and release validation.

## Explicit Non-Goals

- Runtime generation of drill questions.
- Whole-test unlock for every Section after one Section submission.
- Fuzzy semantic marking.
- Mixing Intensive Listening answers into the original Practice Session.
- Replacing Transcript Shadowing.
- Using candidate `text` as released answer authority.
