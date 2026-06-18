# ASR Timing Reconciliation Skill Plan

> **Status:** Draft plan for the replacement Transcript Shadowing timing skill. Primary decision record: [ADR 0008](../../adr/0008-use-asr-timing-reconciliation-for-transcript-shadowing.md).

**Goal:** Create a new ASR Timing Reconciliation skill that uses local Whisper word timestamps as timing evidence, reconciles them against official `transcript.json`, produces reviewable artifacts, and emits the existing `yasi.transcript-timings.v1` frontend asset only after validation.

**Skill directory:** `.agents/skills/yasi-asr-timing-reconciliation/`

**Working artifact root:** `D:\Project\yasi\待删除\yasi-asr-timing-reconciliation\`

**Release audit root:** `D:\Project\yasi\build\review\transcript-timing\`

**Non-negotiables:**

- Do not load Qwen models in the primary workflow.
- Set `PYTHONUTF8=1` before invoking Whisper on Windows.
- Keep ASR text as timing evidence only; official transcript text remains the display and token identity authority.
- Preserve the final frontend contract: `transcript-timings.json` with schema `yasi.transcript-timings.v1`.
- Write `asr-timing-evidence.json`, `reconciliation-report.json`, and `alignment-review.json` before finalization.
- Treat working artifacts as temporary evaluation and review evidence. The durable pack-facing output is the verified `transcript-timings.json`; model benchmark conclusions belong in ADR/spec/plan updates.

## Task 1: Benchmark The Default Whisper Model

**Question:** Which cached Whisper model should the new skill use by default for the Section 01 pilot: `small`, `medium`, or `large-v3`?

**Why this comes first:** The default model controls runtime and review burden. The earlier `tiny` smoke test only proved the local CLI can produce word timestamps; it did not prove which model produces reliable anchors for IELTS transcript highlighting.

**Candidates:**

- `small`
- `medium`
- `large-v3`

`large-v3` represents the large model tier because it is present in the local Whisper cache and is the newer large checkpoint available on this machine.

**Scope:** Run the default-selection benchmark on Section 01 first. Use all four Listening Sections later as the release gate before enabling Transcript Shadowing for the full pack.

**Benchmark output layout:**

```text
D:\Project\yasi\待删除\yasi-asr-timing-reconciliation\
  section-01\
    small\
    medium\
    large-v3\
```

**Protocol:**

- Use the Section 01 Cambridge IELTS Listening source audio and official `transcript.json` for every candidate.
- Invoke the same local Whisper CLI path: `D:\Project\video2pdf\kimi\.venv\Scripts\whisper.exe`.
- Use `--model_dir "$env:USERPROFILE\.cache\whisper"`, `--language en`, `--word_timestamps True`, `--output_format json`, and `PYTHONUTF8=1`.
- Generate `asr-timing-evidence.json` for each model.
- Run the same reconciliation algorithm for each model.
- Generate `reconciliation-report.json`, draft timing output, and `alignment-review.json` for each model.

**Metrics to compare:**

- Whisper runtime and whether the run completes without error.
- Official token count and ASR word count.
- Anchor coverage and longest unanchored official-token gap.
- `matchType` counts: `exact`, `fuzzy`, `interpolated`, `split`, `merged`, `unmatched`.
- Automatic pass ratio.
- Pending review count.
- Count of high-risk or answer-near mappings.
- Count of interpolation gaps exceeding the automatic boundary.
- Representative risky regions for manual inspection.

**Default-selection rule:**

Choose the smallest model that produces acceptable reconciliation quality. If `small` and `medium` are close, prefer `small` for speed. If `medium` materially reduces unmatched tokens, long gaps, or pending review burden, prefer `medium`. Use `large-v3` only when `medium` fails the quality gate or when `large-v3` sharply reduces manual review enough to justify its runtime.

**Quality gate for default eligibility:**

```text
ready-for-default =
  run completes
  anchorCoverage >= 0.95
  unmatchedRate <= 0.02
  pendingReviewRate <= 0.10
  longestUnanchoredGap <= 8 official tokens
```

Only models that pass this Section 01 gate can become the first skill default. If no candidate passes, keep the skill default unset and report `rerun-asr` or a benchmark failure instead of pretending one model is production-ready. Full-pack release still requires all four sections to pass reconciliation and timing validation.

## Task 2: Define The Artifact Contracts

- Define `asr-timing-evidence.json` fields for engine, model, command, audio identity, generation time, source segments, normalized words, and word `start`/`end`.
- Define `reconciliation-report.json` fields for metrics, `matchType` counts, gate outcome, `blockingReasons[]`, and diagnostics.
- Define required `alignment-review.json` fields for `matchType`, official token identity, ASR evidence reference, timing interval, risk types, review decision, and correction.
- Define release audit promotion: benchmark review artifacts stay temporary, while the final `alignment-review.json` used for released verified timings is copied under `build/review/transcript-timing/`.

## Task 3: Implement Reconciliation

- Normalize official transcript tokens and Whisper words through one shared normalization path.
- Align official and ASR token sequences with dynamic programming.
- Extract exact anchors.
- Apply bounded interpolation only when `gapTokens <= 3`, `anchorSpanSeconds <= 2.5`, and no risk rule applies.
- Mark fuzzy, split, merged, unmatched, high-risk, answer-near, and wide-gap cases for review.

## Task 4: Finalize And Validate

- Apply approved and corrected review entries.
- Emit `transcript-timings.json` with schema `yasi.transcript-timings.v1`.
- Promote the final review trace to `build/review/transcript-timing/<pack-id>/alignment-review.json` before release validation passes.
- Set `transcript-timings.json.reviewArtifact` to the promoted release audit artifact as a repo-root-relative path, such as `build/review/transcript-timing/cambridge-10-test-1-listening/alignment-review.json`.
- Extend release validation so released packs fail when the declared review artifact is missing, contains pending decisions, or does not cover every timing entry that requires review.
- Reuse or port existing timing validation rules from the superseded `yasi-forced-alignment` skill.
- Block finalization when any required timing is missing, non-monotonic, non-positive, pending review, or detached from official transcript token identity.
