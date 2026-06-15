# Cambridge IELTS 10 Test 1 Listening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and release a complete 40-question Cambridge IELTS 10 Test 1 Listening desktop practice application backed by a validated build-time Practice Pack.

**Architecture:** A Python pack builder reads the immutable Cambridge source PDFs and WMA files, renders seven question pages, detects interaction geometry, validates authoritative answers/transcripts/audio, and emits a versioned static pack. A React + Vite + TypeScript application consumes only a `released` pack and implements section navigation, practice playback, persistence, strict marking, feedback, reset, and disabled future-feature placeholders. Deterministic overlay proposals are accepted only after an independent vision review records per-question confidence of at least `0.85`.

**Tech Stack:** Python 3.11+, Pillow, NumPy, Pydantic, pytest, FFmpeg/FFprobe, React, TypeScript, Vite, Vitest, Testing Library, Playwright, Python `http.server`.

---

## Why These Choices

- The builder uses Python because PDF/image/audio orchestration and deterministic array processing are simpler to test with Pillow, NumPy, and subprocess boundaries than inside the browser.
- The app uses plain React state plus focused context because one local practice session has a small state graph; an external state library would add persistence and migration indirection without reducing current complexity.
- Pack JSON is validated at build time and again at app load time because checked-in assets may drift independently of TypeScript compilation.
- Overlay detection uses page-specific structural expectations such as question ranges and option counts, while coordinates still come from image analysis. This preserves automated discovery and avoids manual rectangle annotation.
- Official transcript transcription is stored as reviewed source data with page provenance. OCR is not a release authority because the PDF text encoding is corrupted and no reliable local OCR engine is installed.

## File And Ownership Map

### Root Tooling

- Create `package.json`: JavaScript commands and dependency declarations.
- Create `tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json`: TypeScript boundaries.
- Create `vite.config.ts`: Vite and Vitest configuration.
- Create `playwright.config.ts`: desktop Chrome/Edge browser projects and screenshot output.
- Create `index.html`: Vite entry document.
- Modify `.gitignore`: ignore generated caches, builds, browser artifacts, and local pack work directories while retaining released pack assets.

### Pack Builder

- Create `pyproject.toml`: Python dependencies and pytest configuration.
- Create `builder/__init__.py`: package marker.
- Create `builder/config.py`: immutable source paths, page ranges, section metadata, and tool locations.
- Create `builder/models.py`: Pydantic models for manifest, questions, answers, overlays, transcript, review, and release reports.
- Create `builder/render_pages.py`: render PDF pages 1-7 at 150 DPI into stable PNG names.
- Create `builder/detect_overlays.py`: deterministic blank-line and choice-row detection.
- Create `builder/overlay_review.py`: draw review rectangles and combine deterministic/vision evidence.
- Create `builder/convert_audio.py`: WMA-to-MP3 conversion and duration checks.
- Create `builder/build_pack.py`: dependency-ordered build orchestration.
- Create `builder/validate_pack.py`: fail-closed release validation.
- Create `builder/source_data/questions.json`: explicit question types, sections, page ownership, expected option counts, and limits.
- Create `builder/source_data/answers.json`: all 40 official answers and provenance from answer-key page 151.
- Create `builder/source_data/transcript-section-01.json` through `transcript-section-04.json`: reviewed official transcript segments with source pages and answer references.
- Create `builder/source_data/vision-validation.json`: independent visual review evidence keyed by question/option region.
- Create `builder/schemas/*.json`: exported JSON Schemas used by tests and release validation.

### Released Practice Pack

- Create `public/packs/cambridge-10/test-1/listening/manifest.json`.
- Create `public/packs/cambridge-10/test-1/listening/questions.json`.
- Create `public/packs/cambridge-10/test-1/listening/answers.json`.
- Create `public/packs/cambridge-10/test-1/listening/overlays.json`.
- Create `public/packs/cambridge-10/test-1/listening/transcript.json`.
- Create `public/packs/cambridge-10/test-1/listening/assets/pages/page-010.png` through `page-016.png`.
- Create `public/packs/cambridge-10/test-1/listening/assets/audio/section-01.mp3` through `section-04.mp3`.
- Create `build/review/overlays/page-010-review.png` through `page-016-review.png`.
- Create `build/review/release-report.json`.
- Create `build/review/answer-review.json` only when an official answer is unreadable; the present visual inspection indicates all 40 official answers are legible, so the expected released report contains zero pending candidates.

### Practice App

- Create `src/main.tsx`: application bootstrap.
- Create `src/App.tsx`: home/workspace routing.
- Create `src/styles.css`: desktop visual system and responsive minimum-width handling.
- Create `src/types/pack.ts`: runtime pack types.
- Create `src/lib/loadPack.ts`: fetch and validate a released pack.
- Create `src/lib/marker.ts`: strict marking.
- Create `src/lib/session.ts`: localStorage save, restore, archive, and reset.
- Create `src/lib/keyboard.ts`: shortcut matching that ignores answer-entry keystrokes correctly.
- Create `src/context/PracticeSessionContext.tsx`: session state and save lifecycle.
- Create `src/components/PracticePackHome.tsx`.
- Create `src/components/ExamWorkspace.tsx`.
- Create `src/components/SectionNavigation.tsx`.
- Create `src/components/AudioPlayer.tsx`.
- Create `src/components/QuestionScrollArea.tsx`.
- Create `src/components/QuestionPage.tsx`.
- Create `src/components/InteractionOverlay.tsx`.
- Create `src/components/BlankResponse.tsx`.
- Create `src/components/ChoiceResponse.tsx`.
- Create `src/components/PracticeActions.tsx`.
- Create `src/components/MarkingFeedback.tsx`.
- Create `src/components/PackErrorScreen.tsx`.
- Create `scripts/serve.py`: build if requested, serve `dist`, and open the local URL.

### Tests

- Create `tests/python/test_models.py`.
- Create `tests/python/test_render_pages.py`.
- Create `tests/python/test_detect_overlays.py`.
- Create `tests/python/test_convert_audio.py`.
- Create `tests/python/test_validate_pack.py`.
- Create `src/lib/marker.test.ts`.
- Create `src/lib/session.test.ts`.
- Create `src/lib/loadPack.test.ts`.
- Create `src/components/ChoiceResponse.test.tsx`.
- Create `src/components/ExamWorkspace.test.tsx`.
- Create `tests/e2e/practice.spec.ts`.
- Create `tests/e2e/visual.spec.ts`.

## Dependency Order

1. Tooling and data contracts.
2. PDF rendering and source-data extraction can proceed in parallel after contracts exist.
3. Overlay detection depends on rendered pages and question metadata.
4. Vision validation depends on overlay review images.
5. Audio conversion depends only on source/tool configuration.
6. Release validation depends on all pack artifacts and vision evidence.
7. App domain logic depends on the JSON contracts.
8. UI depends on domain logic and a released pack.
9. Browser/visual verification depends on the production build and local server.

## Task 1: Establish Tooling And Practice Pack Contracts

**Files:**
- Create: `package.json`
- Create: `tsconfig.json`
- Create: `tsconfig.app.json`
- Create: `tsconfig.node.json`
- Create: `vite.config.ts`
- Create: `playwright.config.ts`
- Create: `index.html`
- Create: `pyproject.toml`
- Create: `builder/__init__.py`
- Create: `builder/config.py`
- Create: `builder/models.py`
- Create: `builder/schemas/*.json`
- Create: `tests/python/test_models.py`
- Modify: `.gitignore`

- [ ] **Step 1: Add failing model tests**

```python
def test_manifest_rejects_non_released_status_for_runtime():
    payload = minimal_manifest(status="building")
    with pytest.raises(ValidationError):
        ReleasedManifest.model_validate(payload)


def test_overlay_rejects_confidence_below_gate():
    payload = minimal_overlay(question_id="q1", confidence=0.849)
    with pytest.raises(ValidationError):
        Overlay.model_validate(payload)


def test_question_coverage_must_be_exactly_one_to_forty():
    questions = [minimal_question(number=n) for n in range(1, 40)]
    with pytest.raises(ValueError, match="1 through 40"):
        validate_question_coverage(questions)
```

- [ ] **Step 2: Run the model tests and verify RED**

Run:

```powershell
uv run --project . pytest tests/python/test_models.py -q
```

Expected: collection fails because `builder.models` does not exist.

- [ ] **Step 3: Implement exact contracts**

Define:

```python
SCHEMA_VERSION = 1
OVERLAY_CONFIDENCE_GATE = 0.85

class Question(BaseModel):
    id: str
    number: int = Field(ge=1, le=40)
    section: int = Field(ge=1, le=4)
    responseType: Literal["blank", "single-choice", "multi-choice"]
    page: str
    focusOrder: int
    selectionLimit: int | None = None
    options: list[ChoiceOption] = []

class Answer(BaseModel):
    questionIds: list[str]
    accepted: list[list[str]]
    orderIndependent: bool = False
    provenance: list[AnswerEvidence]
    reviewStatus: Literal["official", "user-confirmed"]

class Overlay(BaseModel):
    questionId: str
    optionId: str | None = None
    page: str
    interactionType: Literal["blank", "choice-option"]
    pixel: Rect
    normalized: Rect
    deterministicConfidence: float = Field(ge=0, le=1)
    visionConfidence: float = Field(ge=OVERLAY_CONFIDENCE_GATE, le=1)
    confidence: float = Field(ge=OVERLAY_CONFIDENCE_GATE, le=1)
    validationEvidence: list[str]
```

Export JSON schemas from these models and validate exact `1..40` coverage, unique focus order, section ownership, and grouped answer membership.

- [ ] **Step 4: Run model tests and verify GREEN**

Run:

```powershell
uv run --project . pytest tests/python/test_models.py -q
npm install
```

Expected: model tests pass and JavaScript/Python lock metadata is created.

- [ ] **Step 5: Commit checkpoint**

```powershell
git add .gitignore package.json package-lock.json tsconfig*.json vite.config.ts playwright.config.ts index.html pyproject.toml builder tests/python/test_models.py
git commit -m "build: establish listening pack contracts"
```

## Task 2: Render The Seven Official Question Pages

**Files:**
- Create: `builder/render_pages.py`
- Create: `tests/python/test_render_pages.py`
- Generate: `public/packs/cambridge-10/test-1/listening/assets/pages/page-010.png` through `page-016.png`

- [ ] **Step 1: Add a failing render test**

```python
def test_render_question_pages_uses_stable_names_and_dimensions(tmp_path):
    results = render_question_pages(source_pdf=FIXTURE_PDF, output_dir=tmp_path, dpi=150)
    assert [item.output.name for item in results] == [
        "page-010.png", "page-011.png", "page-012.png",
        "page-013.png", "page-014.png", "page-015.png", "page-016.png",
    ]
    assert all(item.width == 1067 for item in results)
    assert all(item.height in {1461, 1462} for item in results)
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
uv run --project . pytest tests/python/test_render_pages.py -q
```

Expected: failure because `render_question_pages` is absent.

- [ ] **Step 3: Implement rendering**

Use `pdftoppm -f 1 -l 7 -png -r 150` against:

```text
resources/剑桥/剑桥雅思10/剑桥雅思真题10分P/02_Test_1_p010-p032.pdf
```

Record SHA-256, source page, output dimensions, and command in the build report. Refuse to overwrite source resources.

- [ ] **Step 4: Verify GREEN and inspect all page images**

Run:

```powershell
uv run --project . pytest tests/python/test_render_pages.py -q
uv run --project . python -m builder.render_pages
```

Expected: seven non-empty 150-DPI PNGs matching book pages 10-16.

Visual acceptance:

- page 10 contains questions 1-6;
- page 11 contains questions 7-10;
- page 12 contains questions 11-12;
- page 13 contains questions 13-20;
- page 14 contains questions 21-25;
- page 15 contains questions 26-30;
- page 16 contains questions 31-40;
- no clipped edges, black pages, or missing text.

- [ ] **Step 5: Commit checkpoint**

```powershell
git add builder/render_pages.py tests/python/test_render_pages.py public/packs/cambridge-10/test-1/listening/assets/pages
git commit -m "feat: render official listening question pages"
```

## Task 3: Detect And Review Interaction Overlays

**Files:**
- Create: `builder/source_data/questions.json`
- Create: `builder/detect_overlays.py`
- Create: `builder/overlay_review.py`
- Create: `tests/python/test_detect_overlays.py`
- Generate: `build/review/overlays/*.png`
- Generate after vision review: `builder/source_data/vision-validation.json`
- Generate: `public/packs/cambridge-10/test-1/listening/questions.json`
- Generate: `public/packs/cambridge-10/test-1/listening/overlays.json`

- [ ] **Step 1: Add failing synthetic detector tests**

```python
def test_detects_dotted_answer_line_as_one_blank_region():
    image = synthetic_page_with_dotted_line(x=220, y=310, width=180)
    regions = detect_blank_regions(image, expected_count=1)
    assert regions[0].pixel.x == pytest.approx(220, abs=6)
    assert regions[0].pixel.w == pytest.approx(180, abs=12)


def test_rejects_missing_expected_region():
    with pytest.raises(DetectionError, match="expected 3.*found 2"):
        detect_blank_regions(synthetic_page_with_two_lines(), expected_count=3)


def test_rejects_material_overlap():
    assert material_overlap(Rect(10, 10, 100, 20), Rect(50, 10, 100, 20), threshold=0.15)
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
uv run --project . pytest tests/python/test_detect_overlays.py -q
```

Expected: failure because detector functions are absent.

- [ ] **Step 3: Implement deterministic detection**

Algorithm:

1. Convert to grayscale and threshold dark pixels.
2. Use horizontal rolling sums and a small vertical merge window to connect dotted/ruled answer lines.
3. Reject page/table borders by span, thickness, and edge proximity.
4. Cluster candidate rows within 5 pixels.
5. Use per-page expected blank counts and top-to-bottom question ordering.
6. Detect choice text bands in the known question block, derive option row rectangles from connected text bounds, and require exactly 5 rows for questions 11-12 plus 15 rows for questions 21-25.
7. Expand input rectangles by fixed padding, normalize by source width/height, calculate deterministic confidence from line continuity, geometry, count agreement, and order agreement.
8. Fail when expected counts differ, regions overlap materially, order is non-monotonic, or deterministic confidence is below `0.85`.

Question metadata must encode response semantics without coordinates:

```json
{
  "id": "q11-12",
  "numbers": [11, 12],
  "section": 2,
  "responseType": "multi-choice",
  "page": "page-012.png",
  "selectionLimit": 2,
  "options": ["A", "B", "C", "D", "E"]
}
```

- [ ] **Step 4: Generate review images**

Run:

```powershell
uv run --project . python -m builder.detect_overlays
uv run --project . python -m builder.overlay_review
```

Expected: seven review PNGs with translucent boxes, question labels, deterministic confidence, and no accepted `overlays.json` yet.

- [ ] **Step 5: Independent vision validation**

Dispatch a separate vision subagent with only:

- the seven original page images;
- the seven review images;
- the expected question/option list;
- ownership of `builder/source_data/vision-validation.json`.

The reviewer records for every blank or option region:

```json
{
  "questionId": "q1",
  "optionId": null,
  "status": "approved",
  "confidence": 0.97,
  "evidence": "Box is centered on the answer line after '241' and before 'Road'."
}
```

Any rejected or `<0.85` result blocks generation; detector logic is corrected and rerun.

- [ ] **Step 6: Merge evidence and verify GREEN**

Run:

```powershell
uv run --project . pytest tests/python/test_detect_overlays.py -q
uv run --project . python -m builder.overlay_review --finalize
```

Expected: 40 question IDs covered, all interaction regions have both deterministic and vision confidence at least `0.85`, normalized rectangles stay within `[0,1]`, and collision checks pass.

- [ ] **Step 7: Commit checkpoint**

```powershell
git add builder/source_data/questions.json builder/source_data/vision-validation.json builder/detect_overlays.py builder/overlay_review.py tests/python/test_detect_overlays.py public/packs/cambridge-10/test-1/listening/questions.json public/packs/cambridge-10/test-1/listening/overlays.json build/review/overlays
git commit -m "feat: detect and validate listening overlays"
```

## Task 4: Extract Official Answers And Structured Transcripts

**Files:**
- Create: `builder/source_data/answers.json`
- Create: `builder/source_data/transcript-section-01.json`
- Create: `builder/source_data/transcript-section-02.json`
- Create: `builder/source_data/transcript-section-03.json`
- Create: `builder/source_data/transcript-section-04.json`
- Create: `tests/python/test_validate_pack.py`
- Generate: `public/packs/cambridge-10/test-1/listening/answers.json`
- Generate: `public/packs/cambridge-10/test-1/listening/transcript.json`
- Generate conditionally: `build/review/answer-review.json`

- [ ] **Step 1: Add failing authority and transcript tests**

```python
def test_all_answers_have_official_provenance():
    answers = load_source_answers()
    assert covered_numbers(answers) == set(range(1, 41))
    assert all(a.reviewStatus in {"official", "user-confirmed"} for a in answers)
    assert all(a.provenance for a in answers)


def test_unapproved_internet_candidate_blocks_release():
    candidate = pending_candidate(approved=False)
    with pytest.raises(ReleaseBlocked, match="user approval"):
        validate_answer_authority([candidate])


def test_transcript_has_all_four_sections_and_reserved_timing_fields():
    transcript = load_source_transcript()
    assert {segment.section for segment in transcript} == {1, 2, 3, 4}
    assert all(segment.startTime is None and segment.endTime is None for segment in transcript)
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
uv run --project . pytest tests/python/test_validate_pack.py -q
```

Expected: failure because source answer/transcript data is absent.

- [ ] **Step 3: Enter the legible official answer key**

Use answer-key page 151 as authority:

```text
1 Ardleigh
2 newspaper
3 theme
4 tent
5 castle
6 beach / beaches
7 2020
8 flight
9 429
10 dinner
11-12 A and C, in either order
13 health problems
14 safety rules
15 plan
16 joining
17 free entry
18 peak
19 guests
20 photo card / photo cards
21 C
22 A
23 B
24 A
25 C
26 presentation
27 model
28 material / materials
29 grant
30 technical
31 gene
32 power / powers
33 strangers
34 erosion
35 islands
36 roads
37 fishing
38 reproduction
39 method / methods
40 expansion
```

Each entry records source PDF, source page `151`, crop path, evidence type `official-answer-key`, and accepted alternatives. Questions 11-12 use one order-independent group accepting exactly `{"A","C"}`.

- [ ] **Step 4: Transcribe the four official audioscript sections**

Assign one independent agent per section with disjoint ownership of its transcript file. Each agent visually reads the rendered official audioscript pages, emits ordered speaker/text segments, preserves English wording, adds answer references, and leaves `startTime`/`endTime` as `null`.

Required source coverage:

- Section 1: book pages 130-131.
- Section 2: book pages 131-132.
- Section 3: book pages 132-133.
- Section 4: book pages 134-135 as needed to include the complete section.

Each transcript file includes a reviewer note and source-page list. The main agent compares answer-bearing phrases against all 40 accepted answers.

- [ ] **Step 5: Implement Answer Review fallback**

When official key text cannot be resolved, emit:

```json
{
  "questionNumber": 0,
  "status": "pending",
  "candidate": "",
  "sourceUrl": "",
  "accessedAt": "",
  "questionCrop": "",
  "answerKeyCrop": "",
  "transcriptEvidence": "",
  "decision": null
}
```

Release validation rejects `pending` and `rejected` candidates. For the current source, expected pending count is zero.

- [ ] **Step 6: Verify GREEN**

Run:

```powershell
uv run --project . pytest tests/python/test_validate_pack.py -q
```

Expected: 40 answers covered with provenance, no pending candidates, four transcript sections present, and every answer-bearing transcript phrase reviewed.

- [ ] **Step 7: Commit checkpoint**

```powershell
git add builder/source_data/answers.json builder/source_data/transcript-section-*.json tests/python/test_validate_pack.py public/packs/cambridge-10/test-1/listening/answers.json public/packs/cambridge-10/test-1/listening/transcript.json
git commit -m "feat: add official answers and transcripts"
```

## Task 5: Convert And Validate Four Audio Sections

**Files:**
- Create: `builder/convert_audio.py`
- Create: `tests/python/test_convert_audio.py`
- Generate: `public/packs/cambridge-10/test-1/listening/assets/audio/section-01.mp3` through `section-04.mp3`

- [ ] **Step 1: Add failing duration tests**

```python
def test_duration_difference_within_tolerance():
    assert_duration_match(source_seconds=456.829, output_seconds=456.801, tolerance=0.10)


def test_duration_difference_blocks_release():
    with pytest.raises(AudioValidationError, match="duration"):
        assert_duration_match(source_seconds=456.829, output_seconds=455.0, tolerance=0.10)
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
uv run --project . pytest tests/python/test_convert_audio.py -q
```

Expected: failure because audio validation functions are absent.

- [ ] **Step 3: Implement conversion**

Use:

```text
D:\Project\video2pdf\kimi\tools\ffmpeg\bin\ffmpeg.exe
D:\Project\video2pdf\kimi\tools\ffmpeg\bin\ffprobe.exe
```

Command shape:

```powershell
ffmpeg -y -i "<source.wma>" -vn -codec:a libmp3lame -q:a 2 "<section.mp3>"
```

Expected source durations:

```text
section-01: 456.829 seconds
section-02: 380.202 seconds
section-03: 390.048 seconds
section-04: 399.707 seconds
```

Require absolute source/output duration difference `<= 0.10` seconds and a non-zero audio stream.

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
uv run --project . pytest tests/python/test_convert_audio.py -q
uv run --project . python -m builder.convert_audio
```

Expected: four playable MP3s, each with an ffprobe report and duration difference at most `0.10` seconds.

- [ ] **Step 5: Commit checkpoint**

```powershell
git add builder/convert_audio.py tests/python/test_convert_audio.py public/packs/cambridge-10/test-1/listening/assets/audio
git commit -m "feat: convert listening audio for browser playback"
```

## Task 6: Build, Validate, And Release The Practice Pack

**Files:**
- Create: `builder/build_pack.py`
- Create: `builder/validate_pack.py`
- Create: `public/packs/cambridge-10/test-1/listening/manifest.json`
- Generate: `build/review/release-report.json`
- Modify: `tests/python/test_validate_pack.py`

- [ ] **Step 1: Add failing release-gate tests**

```python
def test_release_requires_all_assets(tmp_path):
    pack = valid_pack(tmp_path)
    pack.audio_path(4).unlink()
    with pytest.raises(ReleaseBlocked, match="section-04.mp3"):
        validate_pack(pack.root)


def test_release_requires_vision_and_deterministic_agreement(tmp_path):
    pack = valid_pack(tmp_path)
    pack.overlays[0].visionConfidence = 0.80
    with pytest.raises(ReleaseBlocked, match="0.85"):
        validate_pack(pack.root)


def test_valid_pack_is_marked_released(tmp_path):
    report = validate_pack(valid_pack(tmp_path).root)
    assert report.status == "released"
    assert report.questionCoverage == list(range(1, 41))
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
uv run --project . pytest tests/python/test_validate_pack.py -q
```

Expected: release tests fail because orchestration and manifest generation are absent.

- [ ] **Step 3: Implement build orchestration and release report**

The command:

```powershell
uv run --project . python -m builder.build_pack
```

runs render, detect, vision evidence merge, answer/transcript export, audio conversion, JSON-schema validation, asset existence checks, overlay collision checks, provenance checks, and release manifest generation. It writes `status: "released"` only after all gates pass; otherwise it exits non-zero and writes `status: "blocked"` plus exact file/page/question diagnostics.

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
uv run --project . pytest tests/python -q
uv run --project . python -m builder.build_pack
```

Expected: all Python tests pass and `build/review/release-report.json` reports 40 questions, 40 authoritative answers, four transcript sections, four valid audio assets, seven page assets, no pending answer review, and no overlay below `0.85`.

- [ ] **Step 5: Commit checkpoint**

```powershell
git add builder/build_pack.py builder/validate_pack.py tests/python/test_validate_pack.py public/packs/cambridge-10/test-1/listening/manifest.json build/review/release-report.json
git commit -m "feat: enforce listening pack release gate"
```

## Task 7: Implement Strict Marking, Pack Loading, And Session Persistence

**Files:**
- Create: `src/types/pack.ts`
- Create: `src/lib/loadPack.ts`
- Create: `src/lib/loadPack.test.ts`
- Create: `src/lib/marker.ts`
- Create: `src/lib/marker.test.ts`
- Create: `src/lib/session.ts`
- Create: `src/lib/session.test.ts`
- Create: `src/lib/keyboard.ts`
- Create: `src/context/PracticeSessionContext.tsx`

- [ ] **Step 1: Add failing marker tests**

```typescript
it('normalizes case and repeated whitespace only', () => {
  expect(normalizeAnswer('  PHOTO   CARD ')).toBe('photo card')
})

it('requires an explicitly accepted spelling and form', () => {
  expect(markBlank('beaches', ['beach', 'beaches'])).toBe(true)
  expect(markBlank('beachs', ['beach', 'beaches'])).toBe(false)
})

it('marks grouped choices in either order', () => {
  expect(markChoiceSet(['C', 'A'], ['A', 'C'], 2)).toBe(true)
  expect(markChoiceSet(['A'], ['A', 'C'], 2)).toBe(false)
})
```

- [ ] **Step 2: Verify marker RED**

Run:

```powershell
npm test -- src/lib/marker.test.ts
```

Expected: failure because marker functions are absent.

- [ ] **Step 3: Implement minimal strict marker**

Implement:

```typescript
export const normalizeAnswer = (value: string) =>
  value.trim().replace(/\s+/g, ' ').toLocaleLowerCase('en')
```

No punctuation, spelling, tense, number, singular/plural, or semantic tolerance is added unless the exact form appears in `accepted`.

- [ ] **Step 4: Add failing session tests**

```typescript
it('restores answers and active section', () => {
  const restored = restoreSession(storageWith(validSession))
  expect(restored.activeSection).toBe(3)
  expect(restored.answers.q28).toBe('materials')
})

it('archives incompatible schema state before creating a fresh session', () => {
  const storage = storageWith(oldSession)
  restoreSession(storage)
  expect(storage.keys()).toContainEqual(expect.stringMatching(/archive/))
})

it('reset retains active section and clears answers and marking', () => {
  expect(resetSession(submittedSession).activeSection).toBe(4)
  expect(resetSession(submittedSession).answers).toEqual({})
})
```

- [ ] **Step 5: Implement session lifecycle and pack loading**

Use key:

```text
yasi:cambridge-10:test-1:listening:session:v1
```

Save immediately after answer changes, force-save on section switch and home navigation, archive incompatible JSON under a timestamped key, and reject any pack whose manifest status is not `released`.

- [ ] **Step 6: Verify GREEN**

Run:

```powershell
npm test -- src/lib/marker.test.ts src/lib/session.test.ts src/lib/loadPack.test.ts
```

Expected: all domain tests pass.

- [ ] **Step 7: Commit checkpoint**

```powershell
git add src/types src/lib src/context
git commit -m "feat: add strict marking and session persistence"
```

## Task 8: Build The Desktop Practice Interface

**Files:**
- Create: `src/main.tsx`
- Create: `src/App.tsx`
- Create: `src/styles.css`
- Create: `src/components/*.tsx`
- Create: `src/components/ChoiceResponse.test.tsx`
- Create: `src/components/ExamWorkspace.test.tsx`

- [ ] **Step 1: Add failing component interaction tests**

```tsx
it('enforces the two-option limit for questions 11 and 12', async () => {
  render(<ChoiceResponse question={multiChoiceQuestion} value={[]} onChange={onChange} />)
  await user.click(screen.getByRole('checkbox', { name: /A/ }))
  await user.click(screen.getByRole('checkbox', { name: /C/ }))
  await user.click(screen.getByRole('checkbox', { name: /E/ }))
  expect(onChange).toHaveBeenLastCalledWith(['A', 'C'])
})

it('pauses current audio when switching section', async () => {
  const audio = fakeAudioController({ section: 1, playing: true, position: 48 })
  render(<ExamWorkspace audioController={audio} />)
  await user.click(screen.getByRole('button', { name: '02' }))
  expect(audio.pause).toHaveBeenCalledWith(1)
})
```

- [ ] **Step 2: Verify component RED**

Run:

```powershell
npm test -- src/components/ChoiceResponse.test.tsx src/components/ExamWorkspace.test.tsx
```

Expected: failure because components are absent.

- [ ] **Step 3: Implement home and workspace shells**

Home shows one pack card with saved progress. Workspace uses:

- fixed pale-blue top bar;
- `01/02/03/04` navigation;
- active section title and audio controls;
- independently scrolling question area;
- fixed-width right action rail;
- white PDF pages;
- pale-yellow shortcut panel;
- pale-green submit action;
- pale-purple navigation/secondary actions;
- Simplified Chinese controls and states.

- [ ] **Step 4: Implement facsimile and overlays**

`QuestionPage` keeps the image aspect ratio and provides a positioned overlay layer. Rectangles use:

```css
left: calc(var(--x) * 100%);
top: calc(var(--y) * 100%);
width: calc(var(--w) * 100%);
height: calc(var(--h) * 100%);
```

Blank inputs remain fixed-width, centered, horizontally scrollable, and unchanged by answer length. Single-choice groups are one Tab stop with arrow-key movement and Space confirmation. Multi-choice options remain individually focusable and enforce their selection limit.

- [ ] **Step 5: Implement audio, shortcuts, feedback, reset, and placeholders**

Behavior:

- `Enter`: play/pause unless an answer control is consuming Enter.
- `Alt+Left` / `Alt+Right`: seek by five seconds.
- section switch pauses current audio and retains in-memory position;
- refresh starts audio at `0:00`;
- submit marks all 40 and shows raw score;
- correct, incorrect, unanswered states differ visually;
- next-error focuses and scrolls to the next incorrect control;
- reset confirmation clears answers/results/storage/audio positions and retains section;
- “精听” and “原文跟读” remain visible disabled controls;
- return home persists state.

- [ ] **Step 6: Verify GREEN and accessibility**

Run:

```powershell
npm test -- src/components/ChoiceResponse.test.tsx src/components/ExamWorkspace.test.tsx
npm test
```

Expected: all component and domain tests pass, focus order follows question order, and controls have accessible labels.

- [ ] **Step 7: Commit checkpoint**

```powershell
git add src
git commit -m "feat: build desktop listening practice workspace"
```

## Task 9: Add Local Serving, Browser Workflows, And Final Visual Verification

**Files:**
- Create: `scripts/serve.py`
- Create: `tests/e2e/practice.spec.ts`
- Create: `tests/e2e/visual.spec.ts`
- Generate: `output/playwright/1440x900/*.png`
- Generate: `output/playwright/1920x1080/*.png`
- Modify as needed: `package.json`

- [ ] **Step 1: Add failing Playwright workflows**

Cover:

```typescript
test('complete practice lifecycle', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: /开始练习|继续练习/ }).click()
  await page.getByLabel('第 1 题').fill('Ardleigh')
  await page.getByRole('button', { name: '02' }).click()
  await page.reload()
  await expect(page.getByLabel('第 1 题')).toHaveValue('Ardleigh')
  await page.getByRole('button', { name: /提交答案/ }).click()
  await expect(page.getByText(/\/ 40/)).toBeVisible()
})
```

Additional tests cover single/multiple choice, Tab order, audio shortcuts, section position retention, resubmission, next-error, reset, and return-home persistence.

- [ ] **Step 2: Verify browser RED**

Run:

```powershell
npm run build
npm run serve
npx playwright test tests/e2e/practice.spec.ts
```

Expected: workflow failures until the local serving and any integration gaps are complete.

- [ ] **Step 3: Implement the local server**

`scripts/serve.py`:

- optionally runs `npm run build`;
- serves `dist` on `127.0.0.1`;
- chooses port `4173` unless occupied;
- opens `http://127.0.0.1:<port>`;
- provides a clear missing-build diagnostic;
- contains no application logic.

- [ ] **Step 4: Run browser workflows**

Run:

```powershell
npm run build
npx playwright test tests/e2e/practice.spec.ts --project=chrome
npx playwright test tests/e2e/practice.spec.ts --project=edge
```

Expected: all workflows pass in Chrome and Edge projects.

- [ ] **Step 5: Capture and inspect desktop screenshots**

Run:

```powershell
npx playwright test tests/e2e/visual.spec.ts --project=chrome
npx playwright test tests/e2e/visual.spec.ts --project=edge
```

Capture `1440x900` and `1920x1080` for home, each section, and submitted feedback. Inspect every screenshot with an image viewer for:

- overlay alignment with original answer lines/option rows;
- no blank page images;
- no clipped labels or button text;
- no overlapping controls;
- fixed top bar and action rail;
- stable page dimensions on focus and marking;
- correct pale blue/yellow/green/purple visual direction.

- [ ] **Step 6: Run the complete release verification**

Run:

```powershell
uv run --project . pytest tests/python -q
uv run --project . python -m builder.build_pack
npm test
npm run build
npx playwright test --project=chrome
npx playwright test --project=edge
git diff --check
git status --short
```

Expected: zero failures, a released pack report, successful production build, passing Chrome/Edge workflows, clean whitespace check, and only intentional tracked changes.

- [ ] **Step 7: Commit checkpoint**

```powershell
git add scripts tests/e2e output/playwright package.json package-lock.json
git commit -m "test: verify listening practice release"
```

## Final Acceptance Checklist

- [ ] Pack contains exactly questions `1..40` with correct sections and response types.
- [ ] Every question has authoritative accepted answers and provenance.
- [ ] Questions 11-12 accept `A` and `C` in either order.
- [ ] All seven official question pages render clearly.
- [ ] Every overlay has deterministic and vision confidence `>=0.85`.
- [ ] Overlay rectangles remain within page bounds and avoid material collisions.
- [ ] Four MP3 files exist, play, and differ from source durations by at most `0.10` seconds.
- [ ] Four official transcript sections are complete with null timing fields.
- [ ] No unapproved internet answer participates in marking.
- [ ] Home, navigation, audio, shortcuts, persistence, marking, next-error, reset, and return-home work.
- [ ] Intensive listening and transcript shadowing remain disabled placeholders.
- [ ] Python local server opens the static production build.
- [ ] Python, Vitest, build, Chrome, Edge, and visual checks pass.

## Self-Review

- Spec coverage: every design requirement maps to Tasks 1-9 and the final checklist.
- Placeholder scan: no unresolved marker, deferred implementation, unspecified test, or unnamed error-handling step remains.
- Type consistency: `Question`, `Answer`, `Overlay`, `TranscriptSegment`, manifest status, section numbering, confidence gate, and session schema version use the same names across builder and app tasks.
- Known source status: all 40 answer-key entries are visually legible, the seven question pages are available, all four WMA files exist, and source durations are recorded.
