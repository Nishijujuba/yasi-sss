# Mistake Vocabulary Review And Archive Design

## Purpose

Extend the Mistake Vocabulary Notebook from a single active-recall drill into a small review system with two explicit training modes and a recoverable archive.

The feature keeps three learner intents separate:

- passive listening review for ear-word-memory alignment;
- high-cadence dictation for IELTS-style pressure training;
- archive management for mastered or low-value cards.

## Decisions

- The existing `错题本` entry remains the center of the experience.
- The notebook page uses a segmented mode control with `听音复习` and `听写模式`.
- Both modes support `全部` and one-time `随机 10` queues.
- Listening Review plays the queue sequentially, highlights the current card, and waits a learner-set number of seconds after each audio asset ends before moving on. The default interval is three seconds.
- Listening Review shows spelling and Simplified Chinese meaning by default.
- Listening Review supports temporary eye toggles for spelling and meaning. Those toggles apply to the whole current run, are UI-only, and are not saved.
- Dictation Run hides spelling and meaning during the run.
- Dictation Run plays each card audio automatically and uses a fixed three-second answer window after that audio ends.
- When the post-audio three-second dictation window ends, the current input is automatically submitted and the run advances to the next card.
- Empty dictation input is incorrect.
- Dictation Run has no per-card manual play, submit, or next-card controls while the run is active.
- Dictation Run shows each queued card's current-round correctness, then shows end-of-run reviewed count, correct count, wrong count, and accuracy.
- Incorrect Dictation Run answers increase the card's visible error count.
- Active notebook ordering uses Mistake Vocabulary Error Priority after dictation statistics change.
- Manual removal remains available for cards the learner does not want to train, such as low-value place names.
- Archive is distinct from removal. Archived cards keep historical statistics and can be restored.
- Archive page is a lightweight review and recovery page, not a separate training surface.

## Current Code Surface

- `src/components/MistakeVocabularyView.tsx` already renders the notebook, card list, per-card audio playback, `全量顺序练习`, `随机 10`, and manual `移除`.
- `src/lib/mistakeVocabulary.ts` already owns notebook persistence, capture, manual removal, practice outcome recording, and full/random queue helpers.
- `src/components/MistakeVocabularyView.test.tsx` already covers empty state, card details, per-card play, ordered practice, variants, and hidden `spokenText`.
- `src/lib/mistakeVocabulary.test.ts` already covers persistence, removal, capture idempotence, practice queues, and random sampling.
- Existing notebook state has `cards` only. It has no archived collection and no dictation-specific statistics.
- Existing practice updates `practiceAttempts`, `practiceCorrect`, `masteryCount`, and `lastPracticeResult`.

## Page Structure

The notebook page keeps one header:

- title: `错题本`;
- secondary command: `返回首页`;
- archive command: `归档`.

Below the header, the page shows a segmented mode control:

- `听音复习`;
- `听写模式`.

The active mode determines the queue controls and the run panel. The card list remains below the run panel. Each active card keeps:

- term;
- accepted variants;
- Simplified Chinese meaning;
- mistake and practice statistics;
- `播放`;
- `归档`;
- `移除`.

The archive page shows archived cards with:

- term;
- accepted variants;
- Simplified Chinese meaning;
- historical statistics;
- `播放`;
- `恢复到错题本`;
- return command.

Archive cards do not appear in active notebook queues until restored.

## Listening Review

Listening Review is passive review. It is closer to a word follow-along list than to a test.

Queue creation:

- `全部` uses the current active notebook order.
- `随机 10` samples up to ten active cards once and freezes the queue for that run.

Run behavior:

1. Start with the first queued card.
2. Play its Mistake Vocabulary Answer Audio.
3. Highlight the matching card in the list.
4. Keep spelling and meaning visible unless the learner hides them with eye toggles.
5. Keep the spelling and meaning visibility state unchanged for every later card in the current run.
6. When audio ends, wait the current interval setting in seconds.
7. Move to the next queued card.
8. Stop after the final card.

Controls:

- interval seconds input;
- pause;
- continue;
- stop.

Pause freezes the current playback/interval state. Stop clears the current Listening Review queue and highlight. Listening Review does not update mastery or dictation statistics.

## Dictation Run

Dictation Run is a scored, fixed-cadence exercise. It imitates high-pressure IELTS listening by making the time window part of the task.

Queue creation:

- `全部` uses the current active notebook order.
- `随机 10` samples up to ten active cards once and freezes the queue for that run.

Run behavior:

1. Start with the first queued card.
2. Play its Mistake Vocabulary Answer Audio automatically.
3. Focus a single answer input.
4. Start a `3000ms` timer when the audio asset ends.
5. When the timer ends, submit the current input automatically.
6. Treat an empty input as incorrect.
7. Clear the input and immediately advance to the next card.
8. Stop after the final card and show the run result.

The learner has no per-card manual play, submit, or next-card command during an active Dictation Run. The fixed cadence is the scoring boundary.

Answer checking uses the same normalization as existing strict marking:

```text
correct = normalize(input) is in normalize([term, ...acceptedVariants])
```

The run result shows:

- reviewed count;
- correct count;
- wrong count;
- accuracy percentage.

Dictation Run updates card history after each submitted answer. An incorrect dictation answer increases the visible error count for that card; a correct dictation answer updates dictation statistics without reducing the error count.

During an active or just-completed Dictation Run, the card list shows each queued card's current-round state:

- `本轮：待听写`;
- `本轮：正确`;
- `本轮：错误`.

## Error Priority

Active notebook ordering follows Mistake Vocabulary Error Priority. The list should put the most urgent cards first:

1. cards with a higher visible error count;
2. among cards with the same visible error count, cards whose latest scored review result is incorrect;
3. among cards still tied, cards with higher scored review wrong counts;
4. among cards with at least one scored review attempt, cards with lower scored review accuracy;
5. more recently failed or captured cards;
6. stable term order as the final tie-breaker.

Accuracy is:

```text
scoredReviewAttempts = practiceAttempts + dictationAttempts
scoredReviewAccuracy = scoredReviewAttempts === 0 ? null : (practiceCorrect + dictationCorrect) / scoredReviewAttempts
```

Cards with zero scored review attempts do not enter the accuracy comparison. Their active priority comes from visible error count, recency, and stable term order.

## State Model

The notebook persistence can keep the existing localStorage key, but the value needs an upgraded internal shape:

```ts
interface MistakeVocabularyNotebookState {
  version: 2;
  packId: "cambridge-10-test-1-listening";
  cards: Record<string, MistakeVocabularyCardState>;
  archivedCards: Record<string, MistakeVocabularyCardState>;
}

interface MistakeVocabularyCardState {
  termId: string;
  createdAt: string;
  mistakeCount: number;
  lastIncorrectResponse: string;
  lastCapturedAt: string;
  practiceAttempts: number;
  practiceCorrect: number;
  masteryCount: number;
  lastPracticeResult: "correct" | "incorrect" | null;
  lastPracticedAt: string | null;
  dictationAttempts: number;
  dictationCorrect: number;
  lastDictationResult: "correct" | "incorrect" | null;
  lastDictationAt: string | null;
  archivedAt?: string | null;
}
```

Dictation wrong count is derived as:

```text
dictationWrong = dictationAttempts - dictationCorrect
```

Migration rules:

- Existing version 1 notebook state remains valid input.
- Missing `archivedCards` becomes `{}`.
- Missing dictation fields become `0` or `null`.
- Existing `cards` stay active.
- Malformed state keeps the existing archive-and-reset behavior.

Archive rules:

- archive moves a card from `cards` to `archivedCards`;
- archive sets `archivedAt`;
- archive preserves all historical statistics;
- restore moves a card from `archivedCards` back to `cards`;
- restore clears `archivedAt` or sets it to `null`;
- remove deletes from active cards only, unless a future design explicitly adds archive removal.

## Error Handling

- Empty active notebook: show the existing empty state and disable both mode queue starts.
- Missing vocabulary item for an active or archived card: keep the card visible, show the missing `termId`, and disable playback/training for that card.
- Missing audio asset: keep the card visible, show a pack diagnostic, and prevent that card from blocking the whole page.
- Playback failure during Listening Review: stop the current run and show which term/audio path failed.
- Playback failure during Dictation Run: mark the current card as unplayable for the run and stop with a diagnostic, because scoring a word the learner could not hear is invalid.
- Timer cleanup must run when switching modes, stopping a run, leaving the page, or unmounting the component.

## Testing

### Unit Tests

- version 1 notebook state migrates to version 2 with `archivedCards` and dictation fields;
- archive moves a card from active cards to archived cards and preserves statistics;
- restore moves a card from archived cards to active cards and preserves statistics;
- manual removal remains available for active cards;
- dictation answer matching uses `term` and `acceptedVariants`, not `spokenText`;
- empty dictation input is incorrect;
- dictation result updates attempts, correct count, visible error count on wrong answers, latest result, and timestamp;
- Error Priority sorts higher visible error counts first, then uses recent wrong review state and review wrong counts as tie-breakers;
- random ten queues remain one-time samples;
- temporary eye-toggle state is not written to localStorage.

### Component Tests

- notebook switches between `听音复习` and `听写模式`;
- Listening Review starts `全部` and `随机 10` queues;
- Listening Review highlights the current card and supports pause, continue, and stop;
- Listening Review interval seconds input controls the post-audio delay;
- Listening Review eye toggles hide and reveal spelling and meaning for the whole current run without persistence;
- Dictation Run auto-plays each card audio and auto-submits `3000ms` after audio end;
- Dictation Run treats blank input as wrong;
- Dictation Run shows each queued card's current-round correctness;
- Dictation Run shows end-of-run accuracy;
- active card list reorders by Error Priority after dictation;
- archive command moves a card out of the active list;
- archive page restores a card to the active list.

### Browser Acceptance

- Open the notebook and run a short Listening Review queue.
- Confirm the current card highlight, visible spelling/meaning, interval seconds input, run-scoped eye toggles, and pause/continue/stop.
- Run a short Dictation queue.
- Confirm automatic audio playback, the three-second post-audio forced cadence, auto-submit, automatic card advance, blank-as-wrong behavior, per-card current-round correctness, visible error-count increments, and final accuracy display.
- Archive one card, confirm it leaves active practice, open archive, then restore it.
- Confirm restored cards rejoin active practice queues with historical statistics intact.

## Non-Goals

- No server-side user account or cross-device sync.
- No generated audio rebuild.
- No official section-audio excerpt playback.
- No spaced-repetition scheduling beyond Error Priority ordering.
- No separate training mode inside the archive page.
