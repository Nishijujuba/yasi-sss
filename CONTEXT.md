# Cambridge IELTS Listening Practice

This context describes the local IELTS listening practice product built around Cambridge IELTS source books, audio, answer keys, and audioscripts.

## Language

**Listening Practice Pack**:
A self-contained learning set for one Cambridge IELTS listening test or book, containing the questions, audio, answer keys, audioscripts, and scoring rules needed for interactive practice.
_Avoid_: Single HTML file, PDF clone, screenshot page

**Question Facsimile Layer**:
A visual reproduction of the original PDF question pages used to preserve layout fidelity, including tables, spacing, and line lengths.
_Avoid_: Full HTML conversion, retyped page

**Interaction Overlay**:
The structured clickable and typable layer placed over the question facsimile layer for answers, choices, focus order, and feedback.
_Avoid_: Image-only page, manual annotation

**Exam Simulation**:
A practice mode that follows the original listening test order, audio sections, answer entry, and final marking behavior for one complete 40-question listening test.
_Avoid_: Intensive listening, shadowing, generated drill

**Listening Section**:
One of the four ordered audio-and-question units in a complete listening test, shown as `01`, `02`, `03`, or `04` while retaining answers across navigation.
_Avoid_: Page, test, track tab

**Attempted Listening Section**:
A Listening Section that contains at least one non-empty learner response in the current Practice Session, making that whole section eligible for section-scoped submission, feedback, and mistake-review capture.
_Avoid_: Visited section, played audio section, current section

**Practice Playback**:
The unrestricted audio behavior used by the first exam simulation, allowing pause, seeking, replay, and keyboard controls without limiting attempts.
_Avoid_: Strict exam playback, one-time playback

**Marking Feedback**:
The post-submission result view showing the raw score, correct, incorrect, and unanswered states, accepted answers for mistakes, and navigation to the next incorrect response.
_Avoid_: Band estimate, semantic explanation

**Section-Scoped Marking Feedback**:
Marking Feedback for all submitted Attempted Listening Sections, grouped by Listening Section and limited to those sections when displaying accepted answers.
_Avoid_: Current-section-only feedback, all-40 feedback, unattempted-section answer reveal

**Transcript-Viewed Marking Feedback**:
Marking Feedback shown after a learner has opened Transcript Shadowing during the current Practice Session, where the score remains visible but is labeled as practice reference because official transcript exposure can reveal answers.
_Avoid_: Exam-equivalent score, hidden transcript exposure, disabled marking after transcript view

**Submission Readiness**:
The state where at least one answer in the current Practice Session is non-empty, enabling submission and preventing empty `0 / 0` marking.
_Avoid_: Empty submission, current-section assumption, answer reveal without response

**Mistake Vocabulary Notebook**:
A locally persisted review collection made from incorrect Blank Responses in submitted Attempted Listening Sections, where each card represents the accepted answer word or phrase that the learner missed.
_Avoid_: Choice question review, full question history, general vocabulary list

**Mistake Vocabulary Card**:
One review item in the Mistake Vocabulary Notebook, centered on a missed accepted answer word or phrase from a Blank Response and the learning aids needed to practise it again.
_Avoid_: Question card, answer-key row, transcript segment

**Mistake Vocabulary Canonical Term**:
The first accepted answer form for an incorrect Blank Response, used as the Mistake Vocabulary Card's primary word or phrase while other accepted forms remain visible as accepted variants.
_Avoid_: One card per variant, learner-error-derived term, hidden accepted variant

**Mistake Vocabulary Deduplication**:
The rule that the Mistake Vocabulary Notebook keeps one card per normalized accepted answer word or phrase and updates only its mistake count when the learner misses it again.
_Avoid_: Per-attempt card, per-question card, question-number history

**Mistake Vocabulary Capture**:
The section-scoped submission rule that adds only non-empty, incorrect Blank Responses from submitted Attempted Listening Sections to the Mistake Vocabulary Notebook.
_Avoid_: Unanswered blank capture, choice mistake capture, full answer-key import

**Mistake Vocabulary Capture Idempotence**:
The rule that repeated submission of the same incorrect learner response does not increase a Mistake Vocabulary Card's mistake count, while a changed response that is still incorrect creates a new capture event.
_Avoid_: Click-count mistakes, duplicate-submit inflation, daily cap

**Mistake Vocabulary Answer Audio**:
A pre-generated pronunciation audio asset for a Mistake Vocabulary Card's canonical first accepted answer, derived from the known accepted answer text and used for targeted spelling recall.
_Avoid_: Official-audio excerpt, full section replay, runtime browser text-to-speech

**Mistake Vocabulary Spoken Text**:
The explicit English text sent to the pronunciation generator for a Mistake Vocabulary Answer Audio asset, kept separate from the displayed and marked canonical answer so numeric answers can use natural value reading such as `four hundred twenty-nine` for `429`.
_Avoid_: Accepted answer variant, marking value, browser text-to-speech input

**Mistake Vocabulary Definition**:
A short, common Simplified Chinese meaning for a missed accepted answer word or phrase, maintained in the practice pack vocabulary data.
_Avoid_: Long dictionary entry, generated explanation, semantic marking hint

**Mistake Vocabulary Practice**:
An active recall exercise where the learner hears the Mistake Vocabulary Answer Audio, types the English word or phrase, then sees the correct spelling and short Simplified Chinese meaning.
_Avoid_: Passive word list, multiple-choice drill, Chinese-to-English flashcard

**Mistake Vocabulary Practice Queue**:
A fixed sequence of Mistake Vocabulary Cards created when a review run starts, either from the full notebook order or from a one-time random sample of ten cards, and completed with an end-of-run result summary.
_Avoid_: Infinite loop, reshuffled after every card, dynamically expanding queue

**Mistake Vocabulary Mastery Tracking**:
The local review state that keeps a Mistake Vocabulary Card after correct practice, records recent practice outcomes and mastery count, and allows the learner to remove the card manually.
_Avoid_: Automatic removal, permanent pack data deletion, hidden archival

**Desktop Practice Workspace**:
The first-version display environment for the exam simulation, designed for desktop browsers with enough space for the original question layout and supporting controls.
_Avoid_: Mobile layout, responsive reflow

**Question Scroll Area**:
The independently scrolling area that displays all original question pages for the active listening section while navigation, audio, and practice actions remain visible.
_Avoid_: Whole-page scroll, paginated question viewer

**Choice Response**:
A question-ordered keyboard interaction over original PDF option regions: single-choice groups use arrow keys and Space, while multi-choice options remain individually focusable with order-independent limits.
_Avoid_: Free-text letter entry, click-order answer

**Blank Response**:
A question-ordered centered text interaction whose geometry follows the original PDF answer line and remains unchanged by the expected answer length or entered content.
_Avoid_: Auto-sized answer field, answer-length hint

**Practice Session**:
The locally persisted answer and marking state for one exam simulation attempt, saved immediately after answer changes and cleared explicitly by resetting the practice.
_Avoid_: User account, server session

**Practice Pack Home**:
The minimal entry view for opening Cambridge IELTS 10 Test 1 Listening and resuming its locally stored practice session.
_Avoid_: Marketing landing page, content portal

**Mistake Vocabulary Notebook Entry**:
The independent Practice Pack Home command that opens the Mistake Vocabulary Notebook outside the Exam Simulation workspace.
_Avoid_: Side-panel shortcut, disabled future feature, transcript action

**Transcript Segment**:
An ordered portion of the official listening audioscript associated with a listening section, optional speaker identity, currently empty timing fields, and relevant answer references.
_Avoid_: Raw PDF text, generated transcript

**Transcript Shadowing**:
A practice surface where official listening audio plays while the official English audioscript is shown beside the question surface, with playback-synchronized highlighting to guide reading along.
_Avoid_: Recording, microphone capture, speaking score, pronunciation assessment

**Transcript Word Timing**:
A verified time interval for one displayed word in an official audioscript, used to determine which word is currently being spoken during Transcript Shadowing.
_Avoid_: Equal-duration text approximation, decorative highlighting, browser-generated transcript

**Transcript Timing Review**:
An explicit review step for uncertain official-token-to-timing mappings, producing approved corrections or blocking diagnostics before Transcript Word Timings can be treated as verified.
_Avoid_: Silent auto-correction, unreviewed token merges, hidden timing gaps

**Transcript Timing Release Audit**:
The durable review trace retained when verified Transcript Word Timings are released, preserving the approved or corrected evidence behind non-trivial timing mappings.
_Avoid_: Benchmark scratch review, chat approval, temporary ASR evidence

**Reconciliation Report**:
A run-level summary of ASR Timing Reconciliation quality, provenance, match statistics, review burden, and gate outcome for one generated timing attempt.
_Avoid_: Token review list, frontend timing asset, chat summary

**Reconciliation Gate Outcome**:
The run-level decision that says whether a reconciliation attempt can be finalized, needs human timing review, or should rerun ASR before review.
_Avoid_: Review decision, frontend status, score label

**Transcript Timing Match Type**:
A classification of how an official audioscript token received timing evidence during Transcript Alignment, such as direct ASR agreement, fuzzy agreement, interpolation, token split, token merge, or no reliable match.
_Avoid_: Confidence score, review decision, frontend timing status

**Transcript Alignment**:
The build-time process that maps the official listening audio and official audioscript onto verified Transcript Word Timings before a practice pack is released.
_Avoid_: Browser runtime alignment, generated transcript, learner-device audio analysis

**ASR Timing Reconciliation**:
A build-time Transcript Alignment strategy that treats ASR word times as timing evidence and maps them onto official audioscript token identities before Transcript Word Timings can be verified.
_Avoid_: ASR transcript display, Qwen forced alignment, model-authored audioscript

**ASR Timing Evidence**:
Timestamped ASR word output used as evidence for when speech occurred in the official listening audio, without becoming the displayed transcript text or answer evidence.
_Avoid_: Display transcript, answer source, official audioscript

**Transcript Alignment Pilot**:
A development-only validation run that proves Transcript Alignment, Transcript Timing Review, and Transcript Shadowing behavior on one Listening Section before expanding the same release-gated workflow to all four sections.
_Avoid_: Section-only public release, mixed production availability, weakened full-pack coverage

**Transcript Text Authority**:
The rule that the displayed Transcript Shadowing text comes from the official audioscript transcript, while alignment tools provide timing evidence only.
_Avoid_: Model-rewritten transcript display, ASR text substitution, silent official-text edits

**Complete Transcript Shadowing Coverage**:
The release expectation that Transcript Shadowing is available for all four Listening Sections in a practice pack once the feature is enabled for that pack.
_Avoid_: Section-only feature preview, mixed shadowing availability inside one listening test

**Transcript Shadowing Release Gate**:
The acceptance boundary requiring complete, monotonic, verified Transcript Word Timings for every displayed word in all four Listening Sections before Transcript Shadowing can be enabled for a practice pack.
_Avoid_: Partial timing import, low-confidence silent fallback, approximate word pacing

**Transcript Shadowing Availability**:
The pack-level state where Transcript Shadowing is visible as a practice action but becomes interactive only when verified Transcript Word Timings are present for the whole practice pack.
_Avoid_: Hidden future feature, draft timing playback, per-section shadowing toggle

**Bilingual Practice Surface**:
The language boundary where practice controls and marking states use Simplified Chinese while official questions, choices, answers, and transcripts remain in English.
_Avoid_: Translated question paper, language switcher

**Practice Pack Release Gate**:
The acceptance boundary requiring complete questions `1-40`, verified official answers and transcripts, four playable audio assets, coordinate confidence of at least `0.85`, passing browser workflows, and overlap-free desktop screenshots.
_Avoid_: Best-effort release, partial test

**Local Practice Server**:
The Python-launched local HTTP server used to open and serve the static practice pack in a desktop browser without providing application logic.
_Avoid_: Backend service, direct file opening

**Supported Practice Browser**:
The current desktop release target consisting of recent Microsoft Edge and Google Chrome versions.
_Avoid_: Mobile browser, Firefox compatibility target, Safari compatibility target

**Answer Authority**:
The evidence order that treats the official Cambridge answer key as decisive, uses official audioscripts to resolve unreadable spelling, and requires user approval before an internet-sourced candidate enters formal marking.
_Avoid_: Unattributed internet answer, inferred accepted answer

**Answer Provenance**:
The recorded origin of an accepted answer, such as the official answer key, official audioscript, or an explicitly identified internet cross-check.
_Avoid_: Unmarked answer source, silent substitution

**Pending Answer Candidate**:
An internet-sourced answer proposed when the official PDF answer cannot be read, with its source link, access date, and supporting official audioscript evidence, awaiting user approval.
_Avoid_: Accepted answer, automatic fallback

**User-Confirmed Answer**:
A pending answer candidate explicitly approved by the user and therefore allowed to enter the accepted answer set and strict marking flow.
_Avoid_: Unreviewed internet answer, inferred answer

**Answer Review**:
The local approval workflow showing a question crop, official answer-key crop, official transcript evidence, candidate answer, source link, and access date before recording approval or rejection.
_Avoid_: Automatic answer import, hidden moderation

**Section Playback Position**:
The in-memory audio position retained while navigating between listening sections and reset to `0:00` when the browser page is refreshed.
_Avoid_: Persistent audio resume, automatic playback

**Accepted Answer Set**:
The pre-extracted list of answer forms that receive credit for a question, including expanded alternatives from the official answer key.
_Avoid_: Runtime recognition, fuzzy answer

**Strict Marking**:
The listening marking rule that ignores case and extra spacing, while requiring spelling, singular or plural form, tense, number form, and required multi-answer combinations to match the accepted answer set exactly.
_Avoid_: Semantic marking, lenient correction

**Browser Audio Asset**:
An MP3 audio file generated from the original Cambridge listening audio for reliable playback in the exam simulation.
_Avoid_: Original WMA, uploaded audio

**Vision Coordinate Detection**:
The automated process that locates answer blanks and choice regions from rendered PDF page images and emits coordinates for the interaction overlay.
_Avoid_: Manual coordinate annotation, runtime coordinate guessing

**Coordinate Confidence Gate**:
The rule that only vision-detected overlay coordinates with sufficient confidence may enter the exam simulation, with low-confidence detections listed for repair before release.
_Avoid_: Best-effort placement, silent fallback
