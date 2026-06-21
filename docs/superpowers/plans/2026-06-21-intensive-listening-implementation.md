# Intensive Listening Implementation Plan

## Summary

**Goal:** Build the pre-generated, Section-scoped 精听 feature from `docs/superpowers/specs/2026-06-21-intensive-listening-design.md`.

**Execution model:** Use `superpowers:subagent-driven-development` in the new session. Start with a coordinator preflight, then run disjoint implementation subagents in parallel, then run an independent audit subagent, then run final real-browser acceptance through `chrome:control-chrome`.

**Current repo caution:** The worktree already has unrelated dirty files. Every worker must inspect current file contents before editing and must avoid reverting user changes.

## Key Changes

- Add `.agents/skills/yasi-intensive-listening/` with `SKILL.md`, references, prompt template, fixture, and `agents/openai.yaml`; validate with `quick_validate.py`.
- Add Python builder support for `intensive-listening-candidates-section-XX.json`, generated `intensive-listening.json`, manifest `assets.intensiveListening`, and release validation.
- Add TypeScript pack types/loading, strict marking/session helpers, `IntensiveListeningView`, navigation from home/workspace, Section-scoped unlock, answer reveal, transcript reveal, and reset.
- Generate real candidate source files for Sections 01-04 from the current Cambridge 10 Test 1 `transcript.json`; no fixed candidate count, only value-based selection.
- Keep `CONTEXT.md` intensive-listening glossary hunks if present, while avoiding unrelated playback-rate glossary changes in the same commit.

## Parallel Subagents

**Coordinator Preflight**
- Read `AGENT.md`, the spec, current `git status --short`, and `git diff -- CONTEXT.md`.
- Expose multi-agent tools with `tool_search` if needed.
- Save this plan as `docs/superpowers/plans/2026-06-21-intensive-listening-implementation.md` in the execution session.
- Run baseline targeted checks:
  - `.venv\Scripts\python.exe -m pytest tests\python\test_validate_pack.py -q`
  - `npm test -- src/lib/loadPack.test.ts src/components/PracticePackHome.test.tsx src/components/ExamWorkspace.test.tsx`

**Wave 1: Parallel Implementation**
- **Worker A: Skill Package**
  - Owns only `.agents/skills/yasi-intensive-listening/**`.
  - Create the project skill with selection policy, candidate schema, prompt template, fixture, and UI metadata.
  - Run: `$env:PYTHONUTF8='1'; .venv\Scripts\python.exe C:\Users\juju\.codex\skills\.system\skill-creator\scripts\quick_validate.py .agents\skills\yasi-intensive-listening`.

- **Worker B: Builder, Models, Release Gate**
  - Owns `builder/models.py`, new `builder/intensive_listening.py`, `builder/build_pack.py`, `builder/validate_pack.py`, related schemas, and Python tests.
  - Use TDD first in `tests/python/test_intensive_listening.py` and focused additions to `tests/python/test_validate_pack.py`.
  - Implement candidate validation, official-token answer derivation, stable ID generation, overlap rejection, manifest update, and release validation.

- **Worker C: Frontend Data And State**
  - Owns `src/types/pack.ts`, `src/lib/loadPack.ts`, `src/lib/intensiveListening.ts`, `src/lib/intensiveListeningSession.ts`, and tests.
  - Add `IntensiveListeningArtifact`, `LoadedPack.intensiveListening`, optional manifest asset loading with `cache: "no-store"`, strict marking, independent localStorage state, and Section unlock helpers.

- **Worker D: Frontend UI**
  - Owns `src/components/IntensiveListeningView.tsx`, `src/App.tsx`, `src/context/PracticeSessionContext.tsx`, `src/components/PracticePackHome.tsx`, `src/components/PracticeActions.tsx`, `src/components/ExamWorkspace.tsx`, `src/styles.css`, and component tests.
  - Wire home/workspace 精听 entry, Section-locked drill access, full transcript with blank inputs, shared audio/playback-rate controls, submit, answer reveal, transcript reveal, reset, and return navigation.

**Wave 2: Candidate Generation**
- Spawn four short workers in parallel after Worker A/B contracts stabilize.
- Each owns exactly one file:
  - `builder/source_data/intensive-listening-candidates-section-01.json`
  - `builder/source_data/intensive-listening-candidates-section-02.json`
  - `builder/source_data/intensive-listening-candidates-section-03.json`
  - `builder/source_data/intensive-listening-candidates-section-04.json`
- Each worker reads the skill and its assigned transcript section, then emits strict JSON candidates with token spans, text, reason, and tags.
- Coordinator runs the builder to generate `public/packs/cambridge-10/test-1/listening/intensive-listening.json` and update manifest.

**Integration**
- Resolve overlaps or text mismatches by editing candidate source files, then rerun builder.
- Run:
  - `.venv\Scripts\python.exe -m pytest tests\python\test_intensive_listening.py tests\python\test_validate_pack.py -q`
  - `npm test -- src/lib/loadPack.test.ts src/lib/intensiveListening.test.ts src/lib/intensiveListeningSession.test.ts src/components/IntensiveListeningView.test.tsx src/components/PracticePackHome.test.tsx src/components/PracticeActions.test.tsx src/components/ExamWorkspace.test.tsx`
  - `npm run build`
  - `npx playwright test tests/e2e/practice.spec.ts`

## Independent Review And Chrome Acceptance

**Independent Audit Subagent**
- Spawn after integration, read-only unless the coordinator explicitly requests fixes.
- Prompt: audit the final diff against the spec; check answer leakage, Section unlock, candidate-span validation, generated asset authority, independent state, and test coverage.
- Required output: findings with file references, residual risk, and pass/fail recommendation.

**Final Chrome Acceptance Subagent**
- Use `chrome:control-chrome` exactly as requested.
- If no existing preview server is healthy at `http://127.0.0.1:4173/`, launch a detached server using the `AGENT.md` `ProcessStartInfo` pattern, write `tmp\intensive-listening-preview.pid`, then verify readiness with `Invoke-WebRequest`.
- Bootstrap Chrome through the Chrome skill and read the browser documentation as required by that skill.
- Real-browser scenarios:
  - Before original Section submission, 精听 is locked for that Section.
  - Submit Section 01, then Section 01 精听 opens while Section 02 stays locked.
  - Drill shows full Section transcript with generated blanks.
  - Playback and `1.25x` rate work in the drill.
  - `提交精听`, `查看答案`, `查看原文`, and `重置精听` behave independently.
  - Resetting 精听 does not clear original Exam Simulation answers or mistake vocabulary.
- Final Chrome subagent returns DOM/screenshot evidence summary and closes browser tabs via `browser.tabs.finalize({ keep: [] })`.

## Assumptions

- The implementation targets the current Cambridge 10 Test 1 Listening pack first.
- Candidate count has no artificial cap; low-value function words are excluded by selection policy.
- Accepted variants default to `[]`; variants are added only when explicitly generated and validated.
- The app may use preview transcript timings for seek-to-blank when available, while 精听 remains usable without timing data.
- No foreground long-running server commands are allowed from Codex.
