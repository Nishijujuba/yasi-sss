# Cambridge IELTS 10 Test 1 Listening Practice Design

## Purpose

Build a desktop listening practice experience for Cambridge IELTS 10 Test 1. The product preserves the original PDF question layout, adds keyboard and mouse answer interactions, plays the four official listening audio sections, marks all 40 questions from pre-extracted answers, and prepares structured official transcripts for later shadowing and intensive listening features.

The first release covers Test 1 Listening only. Mobile layouts, strict one-play exam playback, transcript timestamps, transcript shadowing, and generated intensive listening exercises remain outside this release.

## Product Boundaries

- The delivered product is a versioned Listening Practice Pack consumed by a static React application.
- Original Cambridge source files remain read-only.
- PDF interpretation, answer extraction, coordinate detection, transcript extraction, and audio conversion happen before the application runs.
- The browser performs no PDF recognition, OCR, answer discovery, or coordinate inference.
- The first release targets recent desktop Microsoft Edge and Google Chrome.
- A Python script launches a local HTTP server and opens the static application.

## Architecture

The system has three boundaries:

1. **Source layer**: Cambridge PDFs, WMA audio, official answer keys, and official audioscripts.
2. **Pack Builder layer**: page rendering, coordinate detection, vision validation, answer extraction and review, transcript structuring, audio conversion, and release validation.
3. **Practice App layer**: home page, listening-section navigation, audio playback, answer entry, persistence, strict marking, and result feedback.

```text
Cambridge Sources
       |
       v
Pack Builder ---> Review Artifacts / Answer Review
       |
       v
Released Practice Pack
       |
       v
React Practice App
```

The dependency direction is one way. The Practice App loads only released pack artifacts and does not depend on source-processing tools.

## Technology

- React
- TypeScript
- Vite
- Static production build
- Python local HTTP launcher
- FFmpeg and FFprobe from:
  - `D:\Project\video2pdf\kimi\tools\ffmpeg\bin\ffmpeg.exe`
  - `D:\Project\video2pdf\kimi\tools\ffmpeg\bin\ffprobe.exe`
- Pillow and NumPy for deterministic image analysis
- A separate vision subagent for coordinate validation
- Playwright for browser workflow and screenshot verification

React state and narrowly scoped context providers are sufficient for the first release. An external state-management framework is outside the initial design.

## Practice Pack Layout

```text
packs/cambridge-10/test-1/listening/
|-- manifest.json
|-- questions.json
|-- answers.json
|-- overlays.json
|-- transcript.json
`-- assets/
    |-- pages/
    `-- audio/
```

### `manifest.json`

Contains the pack identifier, schema version, source references, four Listening Sections, asset paths, build metadata, and release status.

### `questions.json`

Contains question number, Listening Section, response type, page reference, focus order, and selection limit where applicable.

### `answers.json`

Contains accepted answer sets, marking behavior, answer provenance, review status, and grouped-answer rules such as `IN EITHER ORDER`.

### `overlays.json`

Contains page references, interaction types, question identifiers, pixel coordinates, normalized coordinates, confidence values, and validation evidence.

For source image dimensions \(W\) and \(H\):

\[
x_n=\frac{x}{W},\qquad y_n=\frac{y}{H},\qquad
w_n=\frac{w}{W},\qquad h_n=\frac{h}{H}
\]

Normalized coordinates remain stable if a page is rendered again at a different DPI.

### `transcript.json`

Contains ordered official Transcript Segments with Listening Section, optional speaker, English text, answer references, and empty `startTime` and `endTime` fields reserved for later audio alignment.

### `assets`

- `pages/`: rendered question-page PNG files.
- `audio/`: four MP3 files generated from the original WMA tracks.

## Pack Builder Flow

1. Select the Test 1 Listening pages from the split test PDF.
2. Render the pages to normalized PNG assets at a stable DPI.
3. Detect blank lines, table answer regions, option rows, and other response geometry with deterministic image analysis.
4. Associate candidates with question numbers and enforce monotonic question order.
5. Send proposed coordinates and page images to a separate vision subagent for semantic validation.
6. Reject any coordinate below `0.85` confidence or any disagreement between deterministic and vision validation.
7. Generate machine-readable overlays and visual review images.
8. Extract all 40 official answers before runtime.
9. Expand official alternatives and grouped-answer rules into explicit accepted answer sets.
10. When the official answer PDF is unreadable, create a Pending Answer Candidate containing the candidate answer, source URL, access date, question crop, answer-key crop, and official transcript evidence.
11. Require explicit user approval before an internet-sourced candidate enters formal marking.
12. Extract and structure the four official audioscript sections.
13. Convert the four WMA tracks to MP3 and compare source and output duration with FFprobe.
14. Validate schemas, question coverage, assets, provenance, overlays, transcript completeness, and browser behavior.
15. Set the pack status to `released` only after every release gate passes.

The builder may fail. A partially verified pack may not run as a formal Exam Simulation.

## Coordinate Detection

Coordinate discovery is fully automated:

- Deterministic image analysis measures horizontal rules, dotted blanks, table cells, option regions, and nearby number anchors.
- The vision subagent checks whether each proposed region represents the intended response area for its question.
- The expected question count and page order act as hard constraints.
- Pixel and normalized coordinates are both retained.
- Review images draw translucent response boxes over the source pages.

The pipeline fails closed when:

- confidence is below `0.85`;
- an expected question has no region;
- two questions map ambiguously to one region;
- regions overlap materially;
- page or question order is inconsistent;
- deterministic and vision results disagree.

Manual coordinate annotation is outside the primary workflow. Repeated failures require correcting the detection logic and rerunning the builder.

## Answer Authority And Review

Answer evidence uses this order:

1. Official Cambridge answer key.
2. Official alternative forms and grouped-answer instructions.
3. Official audioscript evidence when answer-key text is unreadable.
4. Internet material as an explicitly attributed candidate only.

Every accepted answer stores provenance. Internet-sourced candidates require:

- a specific source URL;
- access date;
- consistency with the official audioscript;
- explicit user approval.

The local Answer Review page displays:

- question number;
- cropped question region;
- cropped official answer-key region;
- official transcript evidence;
- candidate answer;
- source link and access date;
- approve and reject commands.

An unapproved internet answer never enters `answers.json` as an accepted answer. Conflicting official evidence blocks release.

## Strict Marking

The marker:

- ignores letter case;
- trims leading and trailing whitespace;
- collapses repeated internal whitespace;
- requires exact spelling;
- requires an accepted singular or plural form;
- requires an accepted tense;
- requires an accepted number form;
- evaluates single-choice questions by option identifier;
- evaluates multi-choice answers as order-independent sets;
- requires grouped answers to satisfy the official combination rule.

For normalization:

\[
N(s)=\operatorname{lowercase}
\left(
\operatorname{collapseSpaces}
\left(
\operatorname{trim}(s)
\right)
\right)
\]

A response receives credit when its normalized value matches a normalized member of the Accepted Answer Set. Normalization does not add semantic or grammatical tolerance.

## Practice App Components

- `PracticePackHome`: shows Cambridge IELTS 10 Test 1 Listening and saved progress.
- `ExamWorkspace`: owns the desktop workspace and active practice session.
- `SectionNavigation`: displays `01`, `02`, `03`, and `04`.
- `AudioPlayer`: controls the active Browser Audio Asset.
- `QuestionScrollArea`: displays all source pages for the active Listening Section.
- `QuestionPage`: renders one Question Facsimile Layer.
- `InteractionOverlay`: positions response controls above a page.
- `BlankResponse`: centered fixed-geometry text entry.
- `ChoiceResponse`: single-choice or limited multi-choice interaction.
- `PracticeActions`: submit, reset, disabled future features, and return home.
- `MarkingFeedback`: score, response state, accepted answers, and next-error navigation.

## Desktop Layout

The accepted layout uses:

- a fixed top bar containing Listening Section navigation, section title, and audio controls;
- a large left Question Scroll Area;
- a fixed-width right action rail;
- independent vertical scrolling for question pages;
- a minimum design target of `1440x900`;
- a wider verification target of `1920x1080`;
- approximately `900px` for the question surface and `300px` for the action rail.

The chosen visual direction follows the supplied reference screenshot:

- pale blue top area;
- pale yellow shortcut panel;
- pale green submission action;
- pale purple navigation and secondary action accents;
- white PDF pages as the dominant visual surface;
- restrained shadows and small corner radii.

The interface uses Simplified Chinese for controls and marking states. Official questions, choices, accepted answers, and transcripts remain in English.

## Runtime Behavior

### Navigation And Persistence

- First entry opens Listening Section `01`.
- Switching sections preserves all answers.
- Answer changes save immediately to `localStorage`.
- Switching sections and returning home force an additional save.
- A brief non-blocking saved indicator may appear.
- Refresh restores answers and the active Listening Section.
- Incompatible stored schema versions are archived before a new Practice Session is created.

### Audio

- Each Listening Section uses its own MP3.
- Playback is unrestricted practice playback.
- Switching sections pauses the current audio.
- Each section retains its in-memory playback position while navigating.
- Refresh resets every audio position to `0:00`.
- Audio never autoplays.

Keyboard commands:

- `Enter`: play or pause.
- `Alt + Left`: seek backward five seconds.
- `Alt + Right`: seek forward five seconds.

### Answer Entry

- `Tab` follows question-number order.
- Blank Responses use the detected original line width and center entered text.
- Input width never changes based on answer length.
- Overflowing text scrolls within the control.
- A single-choice question is one focus stop; arrow keys change its option and Space confirms.
- Multi-choice options are individually focusable and enforce the official maximum selection count.
- Completing questions `10`, `20`, or `30` does not switch sections automatically.

### Submission And Feedback

- Submission marks all 40 questions.
- The result shows a raw score such as `32 / 40`.
- Correct, incorrect, and unanswered states are visually distinct.
- Mistakes show the user's response and accepted official forms.
- A command moves focus to the next incorrect response.
- Answers remain editable after submission.
- Resubmission recalculates the result.
- No IELTS Band estimate appears in the first release.

### Reset

Reset requires confirmation. Approval:

- clears all 40 answers;
- clears marking results;
- removes the stored Practice Session;
- pauses every audio track and resets it to `0:00`;
- retains the currently selected Listening Section.

### Future Feature Placeholders

The intensive listening and transcript shadowing actions remain visible and disabled with a development status. The return-home action is functional.

## Error Handling

### Builder Errors

The builder stops when:

- question coverage is not exactly `1-40`;
- a question number is missing or duplicated;
- overlay confidence is below `0.85`;
- coordinate validators disagree;
- answer evidence conflicts;
- an internet candidate lacks user approval;
- an audio source is missing;
- converted audio duration is outside the allowed tolerance;
- a transcript section is missing or incomplete;
- a referenced asset does not exist.

Every failure identifies the source file, page or section, question number where applicable, and the failed release rule.

### Runtime Errors

- A pack load failure shows a clear diagnostic screen.
- An audio load failure identifies the Listening Section and asset path.
- A malformed question blocks submission and identifies its question number.
- Unsupported or incompatible stored state is archived and replaced.
- The application never shows an empty question workspace as a fallback.

## Verification

### Data Tests

- JSON schema validation.
- Exact question coverage from `1` through `40`.
- Valid section ownership.
- Existing page and audio assets.
- Answer provenance and review status.
- Complete transcript sections.
- Overlay confidence and collision checks.

For overlay rectangles \(A\) and \(B\):

\[
\operatorname{IoU}(A,B)=
\frac{|A\cap B|}{|A\cup B|}
\]

Material overlap is flagged for review.

### Unit Tests

- answer normalization;
- strict spelling and form matching;
- official alternatives;
- multi-choice set comparison;
- grouped-answer rules;
- practice-session persistence;
- schema migration and archival behavior.

### Browser Tests

Playwright covers:

- entering blanks;
- selecting single and multiple choices;
- question-order keyboard navigation;
- audio shortcuts;
- section switching;
- refresh restoration;
- submission and resubmission;
- next-error navigation;
- reset confirmation;
- return-home persistence.

### Visual Tests

Verify screenshots at:

- `1440x900`;
- `1920x1080`.

Checks include:

- no overlapping controls;
- no clipped button text;
- no blank page images;
- overlay boxes aligned to answer lines and option regions;
- fixed top and right controls remaining visible;
- stable page dimensions during focus and marking changes.

## Release Gate

Cambridge IELTS 10 Test 1 Listening is releasable only when:

- all 40 questions are present;
- every question has a verified type, section, answer, and overlay;
- all coordinate confidences are at least `0.85`;
- all official answers are verified or user-confirmed with provenance;
- all four MP3 files play and pass duration checks;
- all four transcript sections are complete;
- unit, data, and Playwright tests pass;
- desktop screenshots pass visual inspection in Edge and Chrome.
