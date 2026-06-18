# Localized Forced Alignment Slicing Plan

> **Status:** Superseded by [ADR 0008](../../adr/0008-use-asr-timing-reconciliation-for-transcript-shadowing.md). Keep this plan as historical context for the abandoned Qwen forced-alignment slicing route.

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` for script behavior changes and `superpowers:verification-before-completion` before claiming completion. This plan uses checkbox syntax for progress tracking.

**Goal:** Update `yasi-forced-alignment` so long Cambridge listening audio is aligned through localized audio/text slices instead of plain audio slices. The workflow must preserve `transcript.json` as the official text authority while using ASR only to find time anchors inside the raw audio.

**Architecture:** `align_transcript.py` will run a localization stage before Qwen3-ForcedAligner when section audio exceeds the slice threshold or when explicit localization is requested. The localization stage produces a timestamped ASR artifact, finds the official content start, builds a coarse official-token-to-time map, creates localized slice plans, materializes slice WAV files and official text files, runs Qwen direct alignment per slice, offsets timings back to the original section timeline, and merges duplicate overlap output.

**Primary Decision Record:** [ADR 0007](../../adr/0007-use-localization-asr-for-forced-alignment-slicing.md).

**Existing Code Surface:**

- `.agents/skills/yasi-forced-alignment/SKILL.md`
- `.agents/skills/yasi-forced-alignment/scripts/align_transcript.py`
- `.agents/skills/yasi-forced-alignment/scripts/qwen_direct_align.py`
- `.agents/skills/yasi-forced-alignment/scripts/launch_alignment_job.py`
- `.agents/skills/yasi-forced-alignment/scripts/monitor_alignment_job.py`
- `.agents/skills/yasi-forced-alignment/scripts/validate_timings.py`
- `tests/python/test_align_transcript_script.py`

**Local Tool Paths:**

- Project Python: `D:\Project\yasi\.venv\Scripts\python.exe`
- Qwen Python: `D:\Project\video2pdf\newskill-kimi\.venvs\qwen3-asr\Scripts\python.exe`
- Whisper CLI: `D:\Project\video2pdf\kimi\.venv\Scripts\whisper.exe`
- ffmpeg: `D:\Project\video2pdf\kimi\tools\ffmpeg\bin\ffmpeg.exe`
- ffprobe: `D:\Project\video2pdf\kimi\tools\ffmpeg\bin\ffprobe.exe`

## Terms

**Localization Transcript:** A timestamped ASR artifact generated from the raw section audio to estimate where official transcript tokens occur in time. It is timing evidence only.

**Content Start:** The section-audio timestamp where the first official transcript token begins after any examples, instructions, pauses, or extra audio.

**Localized Slice:** A planned unit containing one audio time range and the corresponding official transcript token range.

**Transcript Text Authority:** The existing project rule that final displayed text and token identity come from official `transcript.json`.

## Why This Change

Qwen3-ForcedAligner receives both audio and text:

```text
alignment input = audio span + known transcript span
```

For a long audio section with extra instructions, using a short slice audio and full section transcript increases the mismatch:

```text
audio: local 180-second window
text: entire section transcript
```

The intended matching problem is smaller:

```text
audio: local 180-second window
text: official transcript tokens likely spoken inside that window
```

This keeps the approximate search scale closer to:

$$
C_{\text{slice}} \approx A_{\text{slice}} \times T_{\text{slice}}
$$

instead of repeatedly paying:

$$
C_{\text{bad}} \approx A_{\text{slice}} \times T_{\text{section}}
$$

The second form wastes work and can send the aligner into poor paths when the slice lacks most of the supplied text.

## Task 1: Establish Localization CLI Contract

**Files:**

- Modify: `.agents/skills/yasi-forced-alignment/scripts/align_transcript.py`
- Modify: `tests/python/test_align_transcript_script.py`

- [x] **Step 1: Add failing parser tests**

Add tests for these arguments:

```text
--localize-content-start
--localizer whisper|qwen-asr|existing
--content-start-seconds <float>
--localization-input <path>
--localization-output <path>
--min-localization-score 0.82
--slice-overlap-seconds 3
--text-overlap-tokens 20
--whisper <path>
```

Expected behavior:

- `--content-start-seconds` accepts non-negative floats.
- `--min-localization-score` accepts values in `[0, 1]`.
- `--slice-overlap-seconds` accepts non-negative floats.
- `--text-overlap-tokens` accepts non-negative integers.
- invalid values raise parser errors.

- [x] **Step 2: Verify RED**

Run:

```powershell
D:\Project\yasi\.venv\Scripts\python.exe -m pytest tests/python/test_align_transcript_script.py -q
```

Expected: parser tests fail because the new arguments do not exist yet.

- [x] **Step 3: Implement minimal parser support**

Add defaults:

```python
DEFAULT_WHISPER = Path(r"D:\Project\video2pdf\kimi\.venv\Scripts\whisper.exe")
DEFAULT_LOCALIZATION_SCORE = 0.82
DEFAULT_SLICE_OVERLAP_SECONDS = 3.0
DEFAULT_TEXT_OVERLAP_TOKENS = 20
```

Use `localizer="existing"` when `--localization-input` is supplied.

- [x] **Step 4: Verify GREEN**

Run the parser-focused tests and confirm they pass.

## Task 2: Represent Official Tokens And Localization Tokens

**Files:**

- Modify: `.agents/skills/yasi-forced-alignment/scripts/align_transcript.py`
- Modify: `tests/python/test_align_transcript_script.py`

- [x] **Step 1: Add failing token model tests**

Test that official section text can be flattened into stable token records:

```python
[
  {
    "globalTokenIndex": 0,
    "segmentOrder": 1,
    "tokenIndex": 0,
    "text": "Hello",
    "normalized": "hello"
  }
]
```

Test that localization tokens carry:

```python
{
  "text": "hello",
  "normalized": "hello",
  "start": 42.31,
  "end": 42.62,
  "sourceIndex": 86
}
```

- [x] **Step 2: Verify RED**

Expected: tests fail where the localization token loader or serializer is absent.

- [x] **Step 3: Implement token helpers**

Reuse existing token normalization rules used for official tokens. Keep one normalization path for official and localization tokens so numbers, apostrophes, hyphens, and currency symbols compare consistently.

- [x] **Step 4: Verify GREEN**

Run the token tests.

## Task 3: Generate Or Load Localization Transcript

**Files:**

- Modify: `.agents/skills/yasi-forced-alignment/scripts/align_transcript.py`
- Modify: `tests/python/test_align_transcript_script.py`

- [x] **Step 1: Add failing localization transcript tests**

Cover three cases:

1. Existing localization JSON is loaded and normalized.
2. Whisper command shape is generated with local tool paths.
3. Missing localization input and missing localizer executable fail before GPU work starts.

Expected localization JSON shape:

```json
{
  "schemaVersion": "yasi.localization-transcript.v1",
  "sourceAudio": "D:\\Project\\yasi\\public\\packs\\cambridge-10\\test-1\\listening\\assets\\audio\\section-01.mp3",
  "engine": "whisper",
  "generatedAt": "2026-06-18T00:00:00Z",
  "tokens": [
    {"text": "hello", "normalized": "hello", "start": 42.31, "end": 42.62, "sourceIndex": 86}
  ],
  "segments": []
}
```

- [x] **Step 2: Verify RED**

Expected: tests fail because the localization transcript loader/generator is absent.

- [x] **Step 3: Implement loading first**

Implement `load_localization_transcript(path)` and `localization_tokens_from_payload(payload)`.

Handle common timestamped shapes:

- Whisper JSON segments with `words`;
- SRT-like segment records with start/end and text;
- current Qwen-compatible `timestamps` entries.

- [x] **Step 4: Implement Whisper generation wrapper**

Command shape:

```powershell
D:\Project\video2pdf\kimi\.venv\Scripts\whisper.exe "<audio>" --model medium --language en --word_timestamps True --output_format json --output_dir "<localization-dir>"
```

Normalize the result into `section-XX.localization.json`.

Write stdout/stderr logs beside the localization artifact:

```text
待删除\yasi-forced-alignment\localization\section-01.whisper.stdout.log
待删除\yasi-forced-alignment\localization\section-01.whisper.stderr.log
```

- [x] **Step 5: Verify GREEN**

Use tests with monkeypatched subprocess output. Avoid running full Whisper in unit tests.

## Task 4: Locate Official Content Start

**Files:**

- Modify: `.agents/skills/yasi-forced-alignment/scripts/align_transcript.py`
- Modify: `tests/python/test_align_transcript_script.py`

- [x] **Step 1: Add failing content-start tests**

Create synthetic tokens:

```text
ASR: example instructions ... now listen ... hello welcome to the tour
Official: hello welcome to the tour
```

Expected:

```json
{
  "contentStartSeconds": <time of ASR token hello>,
  "score": >= 0.82,
  "matchedOfficialTokenRange": [0, 5],
  "matchedLocalizationTokenRange": [...]
}
```

Also test a low-score input:

```python
with pytest.raises(LocalizationError, match="score"):
    locate_content_start(...)
```

- [x] **Step 2: Verify RED**

Expected: missing `locate_content_start` failure.

- [x] **Step 3: Implement sliding-window fuzzy match**

Algorithm:

1. Take the first `prefix_token_count`, default `40`, official tokens.
2. Slide ASR windows from 20 to 70 tokens.
3. Score with `difflib.SequenceMatcher` on normalized token strings.
4. Choose the best score, then use the first matched ASR token start as `contentStartSeconds`.
5. Subtract a small safety margin, default `0.5` seconds, only when the result stays non-negative.

Record evidence:

```json
{
  "score": 0.91,
  "officialPreview": "...",
  "localizationPreview": "...",
  "safetyMarginSeconds": 0.5
}
```

- [x] **Step 4: Add manual override behavior**

When `--content-start-seconds` is supplied, skip fuzzy content-start detection and record:

```json
{"source": "manual", "contentStartSeconds": 42.3}
```

- [x] **Step 5: Verify GREEN**

Run content-start tests.

## Task 5: Build A Coarse Official Token Time Map

**Files:**

- Modify: `.agents/skills/yasi-forced-alignment/scripts/align_transcript.py`
- Modify: `tests/python/test_align_transcript_script.py`

- [x] **Step 1: Add failing mapping tests**

Given official tokens and localization tokens with extra instruction tokens, the mapper should produce anchors:

```json
[
  {"officialTokenIndex": 0, "time": 42.3, "localizationTokenIndex": 86},
  {"officialTokenIndex": 120, "time": 108.7, "localizationTokenIndex": 215}
]
```

Test that unmatched ASR instruction tokens before `contentStartSeconds` are ignored.

- [x] **Step 2: Verify RED**

Expected: missing map builder failure.

- [x] **Step 3: Implement sequence matching**

Use `SequenceMatcher` over normalized tokens:

- exact equal ranges become anchors;
- replace/delete/insert ranges become diagnostics;
- require enough anchors to cover the section before automatic slicing.

Recommended minimum:

```text
minimumAnchorCount = max(10, officialTokenCount * 0.20)
```

For short sections, require at least 10 matched tokens or accept manual slicing only.

- [x] **Step 4: Verify GREEN**

Run mapping tests.

## Task 6: Generate Localized Slice Plan

**Files:**

- Modify: `.agents/skills/yasi-forced-alignment/scripts/align_transcript.py`
- Modify: `tests/python/test_align_transcript_script.py`

- [x] **Step 1: Add failing localized slice tests**

Expected output:

```json
{
  "index": 1,
  "audioStart": 42.3,
  "audioEnd": 222.3,
  "officialTokenStart": 0,
  "officialTokenEnd": 315,
  "textPreview": "..."
}
```

Test:

- every `audioEnd - audioStart <= sliceSeconds + 2 * sliceOverlapSeconds`;
- every slice has a non-empty official token range;
- adjacent slices overlap by configured audio/text margins;
- final slice stops at source audio duration;
- `--dry-run` shows this plan.

- [x] **Step 2: Verify RED**

Expected: current dry-run only reports audio slices or lacks official token ranges.

- [x] **Step 3: Implement time-to-token lookup**

Create helpers:

```python
official_token_at_or_before(time_seconds, anchors)
official_token_at_or_after(time_seconds, anchors)
```

Use nearest anchors around each slice boundary. Apply text overlap after converting times to token boundaries.

- [x] **Step 4: Materialize plan JSON**

Write:

```text
待删除\yasi-forced-alignment\plans\section-01.localized-slices.json
```

Include:

- source audio;
- official transcript path;
- localization artifact path;
- content-start evidence;
- all localized slices;
- token counts;
- text previews;
- diagnostics.

- [x] **Step 5: Verify GREEN**

Run dry-run and slice-plan tests.

## Task 7: Materialize Slice Audio And Official Slice Text

**Files:**

- Modify: `.agents/skills/yasi-forced-alignment/scripts/align_transcript.py`
- Modify: `tests/python/test_align_transcript_script.py`

- [x] **Step 1: Add failing materialization tests**

Test command shape for `ffmpeg`:

```text
ffmpeg -ss <audioStart> -t <duration> -i <source> -ac 1 -ar 16000 -c:a pcm_s16le <slice.wav>
```

Test official text content:

```text
section-01.slice-001.official.txt
```

must be derived from official tokens `[officialTokenStart:officialTokenEnd]`.

- [x] **Step 2: Verify RED**

Expected: existing code either writes full official section text per slice or lacks text range materialization.

- [x] **Step 3: Implement materialization**

For each localized slice:

```text
待删除\yasi-forced-alignment\slices\section-01.slice-001.wav
待删除\yasi-forced-alignment\slices\section-01.slice-001.official.txt
```

Use `--overwrite` behavior consistently:

- if output exists and `--overwrite` is absent, reuse only when the slice plan hash matches;
- if plan hash mismatches, fail with a clear diagnostic.

- [x] **Step 4: Verify GREEN**

Run materialization tests with subprocess monkeypatching.

## Task 8: Align Localized Slices And Merge Timings

**Files:**

- Modify: `.agents/skills/yasi-forced-alignment/scripts/align_transcript.py`
- Modify: `tests/python/test_align_transcript_script.py`

- [x] **Step 1: Add failing worker loop tests**

Test that each slice command uses its slice audio and slice official text:

```text
--input section-01.slice-001.wav
--text-file section-01.slice-001.official.txt
```

Test merged timings:

```text
global_time = slice_local_time + audioStart
```

- [x] **Step 2: Add failing overlap dedupe tests**

When adjacent slices both produce the same official token in the overlap range, final output should contain one timing for that official token.

Selection rule:

1. prefer mapped official identity;
2. prefer monotonic interval;
3. prefer token whose midpoint is farther from slice boundary;
4. preserve earlier slice only as final tie-break.

- [x] **Step 3: Verify RED**

Expected: existing merge behavior cannot identify duplicate official tokens from localized ranges.

- [x] **Step 4: Implement slice-aware merge**

Carry these fields from slice plan into intermediate records:

```json
{
  "sliceIndex": 1,
  "sliceAudioStart": 42.3,
  "officialTokenStart": 0,
  "officialTokenEnd": 315
}
```

Map Qwen output back to the official token range before final section-level mapping. Keep `sourceIndex`, `sliceIndex`, and `sliceQwenJson` for review diagnostics.

- [x] **Step 5: Verify GREEN**

Run merge and worker-loop tests.

## Task 9: Update Review And Validation Diagnostics

**Files:**

- Modify: `.agents/skills/yasi-forced-alignment/scripts/validate_timings.py`
- Modify: `.agents/skills/yasi-forced-alignment/scripts/monitor_alignment_job.py`
- Modify: `tests/python/test_align_transcript_script.py`

- [x] **Step 1: Add failing diagnostics tests**

Validation should fail when:

- section has localization slices yet final timing lacks slice provenance;
- token times are non-monotonic after merge;
- localization score is below threshold and final artifact claims verified;
- a localized slice has an empty official token range.

Monitor output should include:

```text
section-01.localization.json
section-01.localized-slices.json
section-01.slice-001.qwen.json
section-01.slice-001.direct-align.wrapper.log.json
```

- [x] **Step 2: Verify RED**

Expected: existing validation and monitor outputs lack localization-specific checks.

- [x] **Step 3: Implement diagnostics**

Add `localization` metadata to draft timing artifacts:

```json
{
  "localization": {
    "source": "whisper",
    "contentStartSeconds": 42.3,
    "score": 0.91,
    "artifact": "...section-01.localization.json",
    "slicePlan": "...section-01.localized-slices.json"
  }
}
```

Extend monitor snapshots to report localization and per-slice artifacts.

- [x] **Step 4: Verify GREEN**

Run relevant Python tests.

## Task 10: Update Skill Documentation

**Files:**

- Modify: `.agents/skills/yasi-forced-alignment/SKILL.md`

- [x] **Step 1: Update Local Defaults**

Add:

```markdown
- Whisper CLI: `D:\Project\video2pdf\kimi\.venv\Scripts\whisper.exe`
- Localization output root: `D:\Project\yasi\待删除\yasi-forced-alignment\localization`
- Localized slice plan root: `D:\Project\yasi\待删除\yasi-forced-alignment\plans`
```

- [x] **Step 2: Add workflow section**

Add `Audio/Text Localization Before Slicing`:

```markdown
When section audio exceeds 180 seconds, first localize official transcript content inside the raw audio. Use ASR as timing evidence only. Generate localized slices that pair each audio range with the matching official transcript token range. Each Qwen worker must receive slice audio plus slice official text from `transcript.json`.
```

- [x] **Step 3: Replace ASR wording**

Use:

```markdown
ASR output is a localization aid only. It may estimate content start and slice boundaries. It never replaces official transcript text, answer evidence, review identity, or displayed shadowing text.
```

- [x] **Step 4: Update command example**

Recommended command:

```powershell
D:\Project\yasi\.venv\Scripts\python.exe .agents\skills\yasi-forced-alignment\scripts\launch_alignment_job.py --job-name section-01-localized -- --section 1 --overwrite --localize-content-start --localizer whisper --qwen-device-map cuda:0 --qwen-dtype float16 --qwen-timeout-seconds 900 --slice-threshold-seconds 180 --slice-seconds 180 --slice-overlap-seconds 3 --text-overlap-tokens 20 --min-localization-score 0.82 --min-free-gpu-memory-mib 6000
```

- [x] **Step 5: Update failure handling**

Add:

```markdown
If localization confidence is too low, stop before Qwen model loading. Report the localization artifact, best match previews, score, and suggested manual `--content-start-seconds` override.
```

## Task 11: End-To-End Dry Run And Focused Verification

**Files:**

- Modify only if tests reveal real gaps.

- [x] **Step 1: Run focused unit tests**

```powershell
D:\Project\yasi\.venv\Scripts\python.exe -m pytest tests/python/test_align_transcript_script.py -q
```

- [x] **Step 2: Run skill dry-run**

```powershell
D:\Project\yasi\.venv\Scripts\python.exe .agents\skills\yasi-forced-alignment\scripts\align_transcript.py --dry-run --section 1 --localize-content-start --localizer existing --localization-input <known-good-localization.json> --slice-threshold-seconds 180 --slice-seconds 180 --slice-overlap-seconds 3 --text-overlap-tokens 20
```

Expected dry-run output:

- `contentStartSeconds` present;
- `localizationScore` present;
- `plannedSections[].slicing.required` true for long audio;
- every slice has `audioStart`, `audioEnd`, `officialTokenStart`, `officialTokenEnd`, `textPreview`;
- GPU worker commands use slice audio and slice official text;
- no Qwen model loading occurs.

- [x] **Step 3: Run one short synthetic integration test**

Use tiny generated WAV fixtures and synthetic localization JSON. Verify:

- materialized slice audio command shape;
- materialized official text range;
- merged global timings;
- validation diagnostics.

- [x] **Step 4: Run skill validation**

```powershell
$env:PYTHONUTF8='1'
D:\Project\video2pdf\newskill-kimi\.venvs\qwen3-asr\Scripts\python.exe C:\Users\juju\.codex\skills\.system\skill-creator\scripts\quick_validate.py D:\Project\yasi\.agents\skills\yasi-forced-alignment
```

- [x] **Step 5: Run full Python suite if the implementation touches shared validation**

```powershell
D:\Project\yasi\.venv\Scripts\python.exe -m pytest tests/python -q
```

## Acceptance Criteria

- [x] ASR output is used only for localization metadata and slice boundary estimation.
- [x] Final alignment text for every Qwen worker comes from `transcript.json`.
- [x] Audio over 180 seconds creates localized slices with matching official token ranges.
- [x] Dry-run exposes content start, localization score, audio ranges, token ranges, and text previews.
- [x] Low-confidence localization stops before GPU work starts.
- [x] Manual `--content-start-seconds` override works and is recorded in artifacts.
- [x] Slice-local timings are offset back to the raw section audio timeline.
- [x] Overlap duplicates are removed without losing monotonicity.
- [x] Final `transcript-timings.json` remains validated against official transcript tokens.
- [x] `SKILL.md` describes localization ASR as timing evidence only.
- [x] ADR 0007 records the text-authority and localization trade-off.

## Risks And Mitigations

- **Risk: ASR misses or rewrites answer-bearing words.** Mitigation: ASR never becomes final text authority; it only supplies coarse time anchors.
- **Risk: localization score is high for a repeated phrase.** Mitigation: include official prefix preview, matched ASR preview, and optional manual override; require enough later anchors before accepting automatic slicing.
- **Risk: slice boundaries split a phrase.** Mitigation: use audio overlap and text token overlap, then dedupe.
- **Risk: Qwen worker still stalls on a bad slice.** Mitigation: keep per-slice timeout, per-slice wrapper logs, and monitor artifacts.
- **Risk: stale localization artifacts mislead reruns.** Mitigation: record source audio path, duration, transcript hash, CLI parameters, and plan hash in every localization and slice plan artifact.

