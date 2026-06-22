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
- Listening Review plays the queue sequentially, highlights the current card, and waits three seconds after each audio asset ends before moving on.
- Listening Review shows spelling and Simplified Chinese meaning by default.
- Listening Review supports temporary eye toggles for spelling and meaning. Those toggles are UI-only and are not saved.
- Dictation Run hides spelling and meaning during the run.
- Dictation Run uses a fixed three-second answer window per card.
- When the three-second dictation window ends, the current input is automatically submitted.
- Empty dictation input is incorrect.
- The learner may submit early and move to the next card; otherwise the timer submits automatically.
- Dictation Run shows end-of-run reviewed count, correct count, wrong count, and accuracy.
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
5. When audio ends, wait `3000ms`.
6. Move to the next queued card.
7. Stop after the final card.

Controls:

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
2. Play its Mistake Vocabulary Answer Audio.
3. Focus a single answer input.
4. Start a `3000ms` timer from the card window start.
5. When the timer ends, submit the current input automatically.
6. Treat an empty input as incorrect.
7. Clear the input and immediately advance to the next card.
8. Stop after the final card and show the run result.

The learner may submit early. Early submit freezes the current answer immediately and advances to the next card. If the learner does nothing, auto-submit does the same at the deadline.

Answer checking uses the same normalization as existing strict marking:

```text
correct = normalize(input) is in normalize([term, ...acceptedVariants])
```

The run result shows:

- reviewed count;
- correct count;
- wrong count;
- accuracy percentage.

Dictation Run updates card history after each submitted answer.

## Error Priority

Active notebook ordering follows Mistake Vocabulary Error Priority. The list should put the most urgent cards first:

1. cards whose latest dictation result is incorrect;
2. cards with higher `dictationWrong`;
3. cards with higher original `mistakeCount`;
4. among cards with at least one dictation attempt, cards with lower dictation accuracy;
5. more recently failed or captured cards;
6. stable term order as the final tie-breaker.

Accuracy is:

```text
dictationAccuracy = dictationAttempts === 0 ? null : dictationCorrect / dictationAttempts
```

Cards with zero dictation attempts do not enter the accuracy comparison. Their active priority comes from original `mistakeCount`, recency, and stable term order.

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
  dictationWrong: number;
  lastDictationResult: "correct" | "incorrect" | null;
  lastDictatedAt: string | null;
  archivedAt?: string | null;
}
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
- dictation result updates attempts, correct, wrong, latest result, and timestamp;
- Error Priority sorts recent wrong cards and higher wrong counts first;
- random ten queues remain one-time samples;
- temporary eye-toggle state is not written to localStorage.

### Component Tests

- notebook switches between `听音复习` and `听写模式`;
- Listening Review starts `全部` and `随机 10` queues;
- Listening Review highlights the current card and supports pause, continue, and stop;
- Listening Review eye toggles hide and reveal spelling and meaning without persistence;
- Dictation Run auto-submits after `3000ms`;
- Dictation Run treats blank input as wrong;
- Dictation Run shows end-of-run accuracy;
- active card list reorders by Error Priority after dictation;
- archive command moves a card out of the active list;
- archive page restores a card to the active list.

### Browser Acceptance

- Open the notebook and run a short Listening Review queue.
- Confirm the current card highlight, visible spelling/meaning, eye toggles, pause/continue/stop, and three-second post-audio interval.
- Run a short Dictation queue.
- Confirm the three-second forced cadence, auto-submit, blank-as-wrong behavior, and final accuracy display.
- Archive one card, confirm it leaves active practice, open archive, then restore it.
- Confirm restored cards rejoin active practice queues with historical statistics intact.

## Non-Goals

- No server-side user account or cross-device sync.
- No generated audio rebuild.
- No official section-audio excerpt playback.
- No spaced-repetition scheduling beyond Error Priority ordering.
- No separate training mode inside the archive page.
