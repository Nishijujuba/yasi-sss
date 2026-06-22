# ASR Timing Reconciliation Skill Plan

> **Status:** Draft plan for the replacement Transcript Shadowing timing skill. Primary decision record: [ADR 0008](../../adr/0008-use-asr-timing-reconciliation-for-transcript-shadowing.md).
>
> **2026-06-22 update:** The superseded `yasi-forced-alignment` package has been archived under `D:\Project\yasi\待删除\yasi-forced-alignment\archived-skill-2026-06-22\yasi-forced-alignment\`. References to that package in this plan are historical; active implementation should use `.agents\skills\yasi-asr-timing-reconciliation\`.

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

Only models that pass this Section 01 gate can become an automatic release-ready default. If no candidate passes, keep the release gate unresolved and report `rerun-asr` or a benchmark failure instead of pretending one model is production-ready. Full-pack release still requires all four sections to pass reconciliation and timing validation.

**2026-06-18 benchmark result:**

| Model | Anchor Coverage | Unmatched Rate | Pending Review Rate | Longest Unanchored Gap | Runtime Seconds | Gate Outcome | Review Items |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| `small` | 0.9765 | 0.009025 | 0.3285 | 3 | 57.54 | `needs-review` | 182 |
| `medium` | 0.9711 | 0.009025 | 0.3339 | 3 | 90.73 | `needs-review` | 185 |
| `large-v3` | 0.9747 | 0.01083 | 0.3285 | 3 | 199.1 | `needs-review` | 182 |

Result: no model qualifies as an unscreened automatic release default. The skill generation default is now `small` because it is fastest and has equal or lower review burden than the larger candidates. This does not weaken the release gate; it only selects the first model to run. Temporary artifacts were generated under `D:\Project\yasi\待删除\yasi-asr-timing-reconciliation\section-01\<model>\`.

**2026-06-18 review screening result:**

| Model | Total Review Items | Code Approved | LLM Candidates | Human Required |
| --- | ---: | ---: | ---: | ---: |
| `small` | 182 | 160 | 3 | 19 |
| `medium` | 185 | 160 | 4 | 21 |
| `large-v3` | 182 | 159 | 3 | 20 |

The code-screening layer can approve exact normalized mappings with valid timing and no structural risk. The LLM layer receives textual fuzzy or variant candidates as advisory suggestions. Human review remains mandatory for numbers, currency, phone/postcode-like tokens, spelling sequences, unmatched tokens, missing timing, and invalid timing intervals.

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
- Run deterministic and LLM-assisted review screening before manual review to reduce the unresolved queue.
- Emit `transcript-timings.json` with schema `yasi.transcript-timings.v1`.
- Promote the final review trace to `build/review/transcript-timing/<pack-id>/alignment-review.json` before release validation passes.
- Set `transcript-timings.json.reviewArtifact` to the promoted release audit artifact as a repo-root-relative path, such as `build/review/transcript-timing/cambridge-10-test-1-listening/alignment-review.json`.
- Extend release validation so released packs fail when the declared review artifact is missing, contains pending decisions, or does not cover every timing entry that requires review.
- Use the timing validation rules now present in `.agents\skills\yasi-asr-timing-reconciliation\scripts\validate_timings.py`; consult the archived `yasi-forced-alignment` copy only for historical comparison.
- Block finalization when any required timing is missing, non-monotonic, non-positive, pending review, or detached from official transcript token identity.
