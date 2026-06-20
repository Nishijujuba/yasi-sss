---
name: yasi-asr-timing-reconciliation
description: Use when generating, benchmarking, reconciling, reviewing, finalizing, or validating Whisper-based ASR timing evidence for Yasi Transcript Shadowing assets in D:\Project\yasi.
---

# Yasi ASR Timing Reconciliation

## Purpose And Superseding Relationship

Use this skill to produce verified Transcript Shadowing word timings from local Whisper word timestamps while keeping `transcript.json` as the only transcript text authority.

This skill supersedes `yasi-forced-alignment` for the primary timing workflow. The old Qwen forced-alignment path remains historical context and a source of validation ideas. The primary workflow loads no Qwen models, uses no `D:\model-repo` dependency, and treats ASR text only as timing evidence.

The released frontend contract stays `transcript-timings.json` with `schemaVersion: "yasi.transcript-timings.v1"`. ASR provenance, alignment diagnostics, and reviewer decisions stay in temporary artifacts or release audit artifacts.

## Local Paths And Parameters

| Purpose | Path |
| --- | --- |
| Repo root | `D:\Project\yasi` |
| Skill root | `D:\Project\yasi\.agents\skills\yasi-asr-timing-reconciliation` |
| Project Python | `D:\Project\yasi\.venv\Scripts\python.exe` |
| Whisper CLI | `D:\Project\video2pdf\kimi\.venv\Scripts\whisper.exe` |
| Listening pack root | `<pack-root>`, for example `D:\Project\yasi\public\packs\<book-id>\<test-id>\listening` |
| Pack id | `<pack-id>`, for example the `manifest.json` value `cambridge-10-test-1-listening` |
| Section number | `<section>`, an integer such as `1`, `2`, `3`, or `4` |
| Section label | `<section-label>`, derived from the section number such as `section-01` |
| Section audio | `<pack-root>\assets\audio\<section-label>.mp3` or an explicit `--source-audio <audio-path>` |
| Official transcript | `<pack-root>\transcript.json` |
| Temporary benchmark root | `D:\Project\yasi\待删除\yasi-asr-timing-reconciliation` |
| Release audit root | `D:\Project\yasi\build\review\transcript-timing` |
| Final pack timing asset | `<pack-root>\transcript-timings.json` |

Use the same `<pack-root>`, `<pack-id>`, `<section>`, `<section-label>`, and `<model>` across the entire run. When running multiple packs or tests, pass `--pack-id <pack-id>` and preferably `--output-root D:\Project\yasi\待删除\yasi-asr-timing-reconciliation`; this scopes scratch output to:

```text
D:\Project\yasi\待删除\yasi-asr-timing-reconciliation\<pack-id>\<section-label>\<model>\
```

If `--pack-id` is omitted, legacy commands keep the older scratch layout:

```text
D:\Project\yasi\待删除\yasi-asr-timing-reconciliation\<section-label>\<model>\
```

## No-Qwen Primary Workflow

1. Generate Whisper timing evidence with `scripts\benchmark_whisper.py` or `scripts\whisper_evidence.py`; default model is `small`.
2. Draft reconciliation outputs with `scripts\asr_timing_reconcile.py --draft`.
3. Screen pending `mappingReviews[]` with `scripts\screen_alignment_review.py`.
4. Run blind LLM pre-review before any human audio listening; import it as advisory `screening.llmSuggestion`.
5. Use the static review tool for deferred auditory review only after the learner has submitted the section or explicitly opened Transcript Shadowing.
6. For learner-facing preview, publish `transcript-timings.preview.json` with uncertainty markers and keep the artifact `status: "preview"`.
7. For verified release, finalize only after every review decision is `approved` or `corrected`.
8. Validate the final timing asset and release audit before enabling verified Transcript Shadowing.

The chain is:

```text
timestamped ASR evidence -> official-token reconciliation draft -> alignment-review.json -> screened review -> blind LLM pre-review -> transcript-timings.preview.json -> deferred auditory review -> transcript-timings.json
```

Default generation model: `small`. The 2026-06-18 benchmark showed no candidate could skip review, yet `small` had the fastest runtime and equal or lower review burden than larger candidates. This default selects the first model to run; it does not make draft timings release-ready.

## Benchmark Command

Run a section model benchmark with all candidate models. Set `<pack-root>`, `<pack-id>`, and `<section>` first:

```powershell
$env:PYTHONUTF8='1'
$packRoot = 'D:\Project\yasi\public\packs\<book-id>\<test-id>\listening'
$packId = '<pack-id>'
$section = <section>
D:\Project\yasi\.venv\Scripts\python.exe .agents\skills\yasi-asr-timing-reconciliation\scripts\benchmark_whisper.py --pack-root $packRoot --pack-id $packId --section $section --models small medium large-v3 --overwrite
```

Compare existing reports without rerunning Whisper:

```powershell
$env:PYTHONUTF8='1'
$packId = '<pack-id>'
$section = <section>
D:\Project\yasi\.venv\Scripts\python.exe .agents\skills\yasi-asr-timing-reconciliation\scripts\benchmark_whisper.py --pack-id $packId --section $section --models small medium large-v3 --compare-only
```

The release-quality automatic default gate remains:

\[
anchorCoverage \ge 0.95 \land unmatchedRate \le 0.02 \land pendingReviewRate \le 0.10 \land longestUnanchoredGap \le 8
\]

If no model passes this gate, do not finalize without review screening and resolved decisions.

Historical 2026-06-18 Cambridge 10 Test 1 Section 01 benchmark result:

| Model | Anchor Coverage | Unmatched Rate | Pending Review Rate | Longest Unanchored Gap | Runtime Seconds | Gate Outcome |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `small` | 0.9765 | 0.009025 | 0.3285 | 3 | 57.54 | `needs-review` |
| `medium` | 0.9711 | 0.009025 | 0.3339 | 3 | 90.73 | `needs-review` |
| `large-v3` | 0.9747 | 0.01083 | 0.3285 | 3 | 199.1 | `needs-review` |

Generation default: `small`. Benchmark recommendation for unscreened automatic release: `none (rerun-asr)`. This was a Section 01 historical baseline, so future runs should write working artifacts under the parameterized scratch path for the selected `<pack-id>`, `<section-label>`, and `<model>`.

## Draft Reconciliation

Run draft reconciliation. The default model is `small`; keep `--model small` explicit in repeatable commands:

```powershell
$env:PYTHONUTF8='1'
$packRoot = 'D:\Project\yasi\public\packs\<book-id>\<test-id>\listening'
$packId = '<pack-id>'
$section = <section>
D:\Project\yasi\.venv\Scripts\python.exe .agents\skills\yasi-asr-timing-reconciliation\scripts\asr_timing_reconcile.py --pack-root $packRoot --pack-id $packId --section $section --model small --draft
```

The pack-scoped default evidence path is:

```text
D:\Project\yasi\待删除\yasi-asr-timing-reconciliation\<pack-id>\<section-label>\<model>\asr-timing-evidence.json
```

The legacy evidence path used when `--pack-id` is omitted is:

```text
D:\Project\yasi\待删除\yasi-asr-timing-reconciliation\<section-label>\<model>\asr-timing-evidence.json
```

Draft mode writes beside the evidence file:

```text
reconciliation-report.json
alignment-review.json
transcript-timings.draft.json
```

## Automatic Review Screening

Run deterministic and LLM-assisted screening on the generated `alignment-review.json`:

```powershell
$env:PYTHONUTF8='1'
$runDir = 'D:\Project\yasi\待删除\yasi-asr-timing-reconciliation\<pack-id>\<section-label>\<model>'
D:\Project\yasi\.venv\Scripts\python.exe .agents\skills\yasi-asr-timing-reconciliation\scripts\screen_alignment_review.py --review-input "$runDir\alignment-review.json" --output-dir "$runDir\screening"
```

Outputs:

```text
review-screening-report.json
alignment-review.code-screened.json
llm-review-candidates.jsonl
llm-pre-review-candidates.jsonl
```

`llm-review-candidates.jsonl` contains narrow textual mismatch suggestions. `llm-pre-review-candidates.jsonl` contains every unresolved item after deterministic screening, including human-required items, so a language model can label remaining work before the user listens to answer-bearing audio.

Import LLM pre-review output after running the prompt in `prompts\alignment-pre-review-llm-batch.md`:

```powershell
$env:PYTHONUTF8='1'
$runDir = 'D:\Project\yasi\待删除\yasi-asr-timing-reconciliation\<pack-id>\<section-label>\<model>'
D:\Project\yasi\.venv\Scripts\python.exe .agents\skills\yasi-asr-timing-reconciliation\scripts\apply_llm_pre_review.py --review-input "$runDir\screening\alignment-review.code-screened.json" --llm-output "$runDir\screening\llm-pre-review-output.json" --output "$runDir\screening\alignment-review.llm-pre-reviewed.json" --report-output "$runDir\screening\llm-pre-review-apply-report.json"
```

The import step attaches advisory data under `mappingReviews[].screening.llmSuggestion`. It must not change `decision`, `reviewer`, `reviewedAt`, `notes`, `correction`, `riskTypes`, or `reasons`.

Build a learner-facing LLM pre-review preview timing asset:

```powershell
$env:PYTHONUTF8='1'
$packRoot = 'D:\Project\yasi\public\packs\<book-id>\<test-id>\listening'
$runDir = 'D:\Project\yasi\待删除\yasi-asr-timing-reconciliation\<pack-id>\<section-label>\<model>'
D:\Project\yasi\.venv\Scripts\python.exe .agents\skills\yasi-asr-timing-reconciliation\scripts\build_preview_timings.py --draft-input "$runDir\transcript-timings.draft.json" --review-input "$runDir\screening\alignment-review.code-screened.json" --output "$packRoot\transcript-timings.preview.json" --merge-existing "$packRoot\transcript-timings.preview.json"
```

Point `<pack-root>\manifest.json` at `transcript-timings.preview.json` when the HTML should expose preview Transcript Shadowing. Preview assets may contain one or more section entries, and `--merge-existing` preserves previously generated sections while replacing the current section. Preview assets may contain untimed marked words. They are learner-facing preview data, while verified release validation must still reject them.

Build a persistent static human review tool from the screened review artifact:

```powershell
$env:PYTHONUTF8='1'
$packRoot = 'D:\Project\yasi\public\packs\<book-id>\<test-id>\listening'
$packId = '<pack-id>'
$sectionLabel = '<section-label>'
$sectionTitle = '<human-readable section title>'
$runDir = "D:\Project\yasi\待删除\yasi-asr-timing-reconciliation\$packId\$sectionLabel\<model>"
D:\Project\yasi\.venv\Scripts\python.exe .agents\skills\yasi-asr-timing-reconciliation\scripts\build_review_tool.py --review-input "$runDir\screening\alignment-review.llm-pre-reviewed.json" --screening-report "$runDir\screening\review-screening-report.json" --audio-url "file:///$($packRoot.Replace('\','/'))/assets/audio/$sectionLabel.mp3" --title "$sectionTitle - <model> review" --output "D:\Project\yasi\.agents\skills\yasi-asr-timing-reconciliation\tools\generated\$packId-$sectionLabel-<model>-review.html"
```

If no LLM output has been imported yet, use `alignment-review.code-screened.json` as `--review-input`; after pre-review import, prefer `alignment-review.llm-pre-reviewed.json`.

The reusable static app template lives at `tools\review-tool.html`. Generated per-section review pages live under `tools\generated\` because they are durable review tools, not discardable benchmark scratch. The page shows unresolved items, LLM advisory suggestions, timing uncertainty colors, and local section audio from a `file:///D:/Project/yasi/...` URL. It exposes official transcript text and answer-near timing, so open it only after the learner has submitted the section or deliberately entered Transcript Shadowing. The reviewer can then approve/correct/reject each item and export `alignment-review.reviewed.json` for finalization.

`balanced-v1` code screening approves only pending items that satisfy:

\[
matchType=exact \land normalizedOfficial=normalizedSource \land end>start \land structuralRisk=false
\]

Structural risks are numbers, currency, alphanumeric tokens, hyphenated compounds, spelling sequences, unmatched tokens, missing timing, non-positive timing, non-monotonic timing, or over-wide anchor spans. These stay human-required.

LLM candidates are textual mismatches that have usable timing evidence, such as fuzzy names or simple ASR spelling variants. The prompt lives at `prompts\alignment-review-llm-batch.md`. Blind pre-review for every unresolved item uses `prompts\alignment-pre-review-llm-batch.md`. LLM responses are advisory and must be accepted before they enter a release review artifact as `decision`, `notes`, or `correction`.

Historical 2026-06-18 Cambridge 10 Test 1 Section 01 screening result:

| Model | Total Review Items | Code Approved | LLM Candidates | Human Required |
| --- | ---: | ---: | ---: | ---: |
| `small` | 182 | 160 | 3 | 19 |
| `medium` | 185 | 160 | 4 | 21 |
| `large-v3` | 182 | 159 | 3 | 20 |

Use `alignment-review.code-screened.json` as the next review input. Human-required items must be resolved manually or with explicitly accepted corrections before finalization.

## Artifact Contracts

| Artifact | Schema | Purpose |
| --- | --- | --- |
| `asr-timing-evidence.json` | `yasi.asr-timing-evidence.v1` | Whisper command, engine, model, source audio, generation time, runtime, normalized words, and `start`/`end` timing evidence. |
| `reconciliation-report.json` | `yasi.reconciliation-report.v1` | Match counts, metrics, `gateOutcome`, `blockingReasons[]`, diagnostics, source evidence, and draft timing data. |
| `alignment-review.json` | `yasi.alignment-review.v1` | Durable mapping review decisions for uncertain, risky, corrected, split, merged, fuzzy, interpolated, or unmatched timings. |
| `review-screening-report.json` | `yasi.review-screening-report.v1` | Deterministic approval count, LLM candidate queue, human-required queue, and policy metadata. |
| `llm-review-candidates.jsonl` | JSONL | Prompt-ready advisory batches for large-model review suggestions. |
| `llm-pre-review-candidates.jsonl` | JSONL | Prompt-ready blind pre-review batches for all unresolved items. |
| `alignment-review.llm-pre-reviewed.json` | `yasi.alignment-review.v1` | Screened review artifact with advisory `screening.llmSuggestion` metadata and unchanged release decisions. |
| `transcript-timings.preview.json` | `yasi.transcript-timings.v1` | Learner-facing preview timing asset with `status: "preview"` and uncertainty markers. |
| `tools\review-tool.html` | HTML | Persistent static app for manual review of unresolved timing items. |
| `tools\generated\*.html` | HTML | Section/model-specific static review page with embedded screened review data and audio URL. |
| `transcript-timings.draft.json` | `yasi.transcript-timings.v1` | Draft word timing asset for review only. |
| `transcript-timings.json` | `yasi.transcript-timings.v1` | Final verified frontend timing asset. |

Valid `gateOutcome` values are `ready-for-finalize`, `needs-review`, and `rerun-asr`. Valid `matchType` values are `exact`, `fuzzy`, `interpolated`, `split`, `merged`, and `unmatched`.

## Reconciliation Algorithm

Normalize official transcript tokens and Whisper words through the shared normalization rules in `scripts\reconcile_tokens.py`. The official token sequence \(O=(o_1,\ldots,o_n)\) and ASR sequence \(A=(a_1,\ldots,a_m)\) are aligned with dynamic programming:

\[
D(i,j)=\min
\begin{cases}
D(i-1,j)+c_\text{delete}\\
D(i,j-1)+c_\text{insert}\\
D(i-1,j-1)+c_\text{substitute}(o_i,a_j)
\end{cases}
\]

Exact and high-confidence fuzzy pairs become timing anchors. Unmatched official-token gaps can receive automatic interpolation only when:

\[
gapTokens \le 3 \land anchorSpanSeconds \le 2.5 \land risk=false
\]

Risky tokens include numbers, currency, spelling sequences, apostrophes, hyphenated forms, alphanumeric forms, and answer-near text. Risky or low-confidence mappings must enter `alignment-review.json`.

## Release Audit Promotion

Benchmark review artifacts remain under `D:\Project\yasi\待删除\yasi-asr-timing-reconciliation\...`.

When a reviewed artifact is used to finalize released timings, `scripts\asr_timing_reconcile.py --finalize-review` promotes the review trace to:

```text
build/review/transcript-timing/<pack-id>/alignment-review.json
```

The final `transcript-timings.json.reviewArtifact` must be that repo-root-relative path. Release validation must reject missing review artifacts, pending or rejected decisions, pack-relative review paths, and missing review coverage for any timing entry that requires traceability.

Finalize after code screening plus accepted LLM/manual review:

```powershell
$env:PYTHONUTF8='1'
$packRoot = 'D:\Project\yasi\public\packs\<book-id>\<test-id>\listening'
$packId = '<pack-id>'
$runDir = 'D:\Project\yasi\待删除\yasi-asr-timing-reconciliation\<pack-id>\<section-label>\<model>'
D:\Project\yasi\.venv\Scripts\python.exe .agents\skills\yasi-asr-timing-reconciliation\scripts\asr_timing_reconcile.py --pack-root $packRoot --pack-id $packId --finalize-review --review-input "$runDir\screening\alignment-review.reviewed.json" --output "$packRoot\transcript-timings.json"
```

## Failure Handling

- Missing `asr-timing-evidence.json`: run the benchmark or point `--evidence-input` at the intended evidence file.
- `rerun-asr`: regenerate evidence with another candidate model or inspect Whisper stderr logs.
- `needs-review`: edit `alignment-review.json` decisions to `approved` or `corrected`; `pending` and `rejected` block finalization.
- Screening leaves many pending items: run blind LLM pre-review first, inspect `screening.llmSuggestion`, then perform deferred auditory review only after section submission or Transcript Shadowing exposure.
- Low `anchorCoverage`, high `unmatchedRate`, high `pendingReviewRate`, or long unanchored gaps: treat the evidence as weak. Benchmark a stronger candidate before manual review work grows.
- Invalid intervals, overlaps, non-monotonic timings, or missing official token identity: fix review corrections or rerun reconciliation.
- Qwen, ForcedAligner, or `D:\model-repo` references in the executable primary workflow: treat as a workflow regression.
- Missing benchmark metrics: keep the default model unset. Fabricated metrics are release blockers.
- LLM output proposes transcript text edits: reject it. `officialToken.text` is the authority.

## Validation Commands

Use the project virtual environment for every validation command. Do not use Codex bundled Python or a bare `python`, because `quick_validate.py` requires `yaml` from the project's dev dependency set.

Validate the skill package:

```powershell
$env:PYTHONUTF8='1'
D:\Project\yasi\.venv\Scripts\python.exe C:\Users\juju\.codex\skills\.system\skill-creator\scripts\quick_validate.py D:\Project\yasi\.agents\skills\yasi-asr-timing-reconciliation
```

Run focused Python tests when D-owned scripts have stabilized:

```powershell
D:\Project\yasi\.venv\Scripts\python.exe -m pytest tests/python/test_asr_timing_artifacts.py tests/python/test_whisper_evidence.py tests/python/test_asr_reconcile_tokens.py tests/python/test_asr_timing_reconcile_cli.py tests/python/test_asr_review_screening.py tests/python/test_validate_pack.py -q
```

Validate a timing artifact directly:

```powershell
$packRoot = 'D:\Project\yasi\public\packs\<book-id>\<test-id>\listening'
$packId = '<pack-id>'
D:\Project\yasi\.venv\Scripts\python.exe .agents\skills\yasi-asr-timing-reconciliation\scripts\validate_timings.py "$packRoot\transcript-timings.json" --transcript "$packRoot\transcript.json" --review-artifact "D:\Project\yasi\build\review\transcript-timing\$packId\alignment-review.json" --require-verified --require-review-trace
```

Check the primary workflow for accidental Qwen dependencies:

```powershell
rg -n "Qwen|qwen|ForcedAligner|D:\\model-repo" .agents\skills\yasi-asr-timing-reconciliation
```
