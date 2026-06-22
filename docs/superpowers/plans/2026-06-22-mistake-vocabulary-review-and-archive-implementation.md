# Mistake Vocabulary Review And Archive Implementation Plan

## Summary
Codex will implement the approved错题本扩展：`听音复习`、`听写模式`、错误优先排序、归档/恢复，并保留现有手动移除。执行时采用 subagent 并行：状态层、UI 层、集成测试层分工；最后由独立验收 subagent 使用 `chrome:control-chrome` 做真实 Chrome 验收。

## Key Changes
- `src/lib/mistakeVocabulary.ts`
  - Upgrade notebook state to `version: 2` while keeping the same localStorage key.
  - Add `archivedCards`, dictation stats, v1 migration, `archiveMistakeCard`, `restoreMistakeCard`, `recordMistakeDictation`.
  - Add error-priority active ordering and keyed queue helpers: active entries preserve `{ key, card }`.
- `src/context/PracticeSessionContext.tsx` and `src/App.tsx`
  - Expose archive/restore/dictation callbacks to the notebook UI.
  - Preserve existing `removeMistakeCard` behavior and capture-signature clearing.
- `src/components/MistakeVocabularyView.tsx`
  - Replace the old single practice panel with segmented `听音复习` / `听写模式`.
  - Listening Review: `全部` / `随机 10`, current-card highlight, pause/continue/stop, learner-set post-audio interval in seconds, run-scoped spelling/meaning eye toggles.
  - Dictation Run: hidden answer aids, automatic audio playback, fixed 3000ms post-audio forced window, auto-submit latest input, automatic card advance, blank-as-wrong, per-card current-round correctness, visible error-count increments, final accuracy.
  - Remove per-card manual play, submit, and next-card controls from the active Dictation Run panel.
  - Add internal archive page with playback and `恢复到错题本`; archive page has no training queue.
- `src/styles.css`
  - Add restrained controls for mode tabs, active-card highlight, run status, archive view, and compact eye toggles.
  - Reuse existing visual language; avoid new dependencies.

## Parallel Subagent Execution
- Coordinator preflight:
  - Inspect `git status --short`; protect existing unrelated dirty files.
  - Assign strict file ownership before dispatch.
  - Use TDD for each task and run local targeted tests before integration.
- Parallel Wave 1:
  - Subagent A owns state layer: `src/lib/mistakeVocabulary.ts` and `src/lib/mistakeVocabulary.test.ts`.
  - Subagent B owns component behavior: `src/components/MistakeVocabularyView.tsx`, its test file, and CSS classes used only by that component.
  - Both work against fixed interfaces named above; coordinator resolves integration conflicts.
- Wave 2:
  - Subagent C wires context/App props and updates component tests if integration changes prop signatures.
  - Subagent D updates Playwright coverage in `tests/e2e/practice.spec.ts` after UI is integrated.
- Review gates:
  - After each implementation subagent: spec-compliance review subagent, then code-quality review subagent.
  - Final code-review subagent reviews the complete diff before acceptance.
- Independent acceptance:
  - Acceptance subagent is read-only and separate from implementers.
  - It must use `chrome:control-chrome`, connect to user Chrome, navigate to `http://127.0.0.1:4173/`, and verify the workflows through visible UI.
  - It should reuse an existing healthy server. If no server is healthy, use the repo's detached-server policy or ask the user to run `npm run serve` in a user-owned terminal; no foreground long-running server command from Codex.

## Test Plan
- Unit tests:
  - v1 notebook migrates to v2 with `archivedCards` and dictation fields.
  - Archive/restore preserve all historical stats.
  - Removal still deletes active cards and keeps capture re-entry behavior.
  - Dictation matching uses `term` and `acceptedVariants`; `spokenText` remains hidden and invalid for numeric matching.
  - Blank dictation input records wrong and increases the visible error count.
  - Error-priority ordering: visible error count first, then latest wrong, higher review wrong count, lower accuracy, recency, term tie-break.
- Component tests:
  - Mode switch renders `听音复习` and `听写模式`.
  - Listening Review starts all/random queues, highlights current card, pauses/continues/stops, interval seconds input controls delayed advance, and eye toggles apply to the whole current run without persistence.
  - Dictation Run auto-plays each card audio, starts the `3000ms` submit window after audio end, auto-submits, advances without manual per-card controls, displays per-card current-round correctness, and displays final accuracy.
  - Archive command removes card from active list; archive page restores it.
- Commands:
  - `npm test -- src/lib/mistakeVocabulary.test.ts src/components/MistakeVocabularyView.test.tsx`
  - `npm run build`
  - `npx playwright test tests/e2e/practice.spec.ts --project=chrome`
- Chrome acceptance scenarios:
  - Create an Ardleigh mistake through the normal practice UI.
  - Run short Listening Review and verify highlight, visible aids, interval seconds input, run-scoped eye toggles, pause/continue/stop.
  - Run Dictation and verify automatic audio playback, post-audio 3-second cadence, auto-submit, automatic card advance, blank-as-wrong, per-card current-round correctness, visible error-count increments, final accuracy.
  - Archive Ardleigh, verify it leaves active practice, restore from archive, verify historical stats remain.

## Assumptions
- Listening Review defaults to 3 seconds after audio ended and can be changed in the frontend; Dictation keeps an exact fixed `3000ms` window that starts when the current card audio ends.
- Random 10 is sampled once per run and never reshuffled mid-run.
- Archive has no delete command in this iteration; manual removal remains active-list only.
- The plan should be saved during execution as `docs/superpowers/plans/2026-06-22-mistake-vocabulary-review-and-archive-implementation.md`.
