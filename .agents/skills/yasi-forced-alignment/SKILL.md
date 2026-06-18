---
name: yasi-forced-alignment
description: Superseded historical workflow for Qwen3-ForcedAligner and direct transcript forced alignment in D:\Project\yasi. Use only when inspecting old forced-alignment artifacts, scripts, transcript-timings.json validation conventions, alignment-review.json conventions, or Cambridge listening pack word-level timing history; new Transcript Shadowing timing work should use ASR Timing Reconciliation.
---

# Yasi Forced Alignment

> **Status:** Superseded for new Transcript Shadowing timing work by ASR Timing Reconciliation and ADR-0008. Use this skill only for historical Qwen forced-alignment context or for reusable validation/artifact conventions while the replacement skill is being created.

Use this skill to produce and validate `transcript-timings.json` style assets for IELTS listening shadowing in `D:\Project\yasi`.

## Python Environments

Use two Python environments deliberately:

- Project Python: `D:\Project\yasi\.venv\Scripts\python.exe`
  - Use for `.agents\skills\yasi-forced-alignment\scripts\align_transcript.py --help`, `--dry-run`, review finalization, and `.agents\skills\yasi-forced-alignment\scripts\validate_timings.py`.
  - This environment runs the yasi orchestration and validation scripts. It does not need to import Qwen model packages.
- Qwen Python: `D:\Project\video2pdf\newskill-kimi\.venvs\qwen3-asr\Scripts\python.exe`
  - Use for `scripts\qwen_direct_align.py` and any command that loads `Qwen3-ForcedAligner-0.6B`.
  - Use this environment for skill validation with `quick_validate.py`; on Windows set `PYTHONUTF8=1` first so UTF-8 skill files are read correctly.

Do not run Qwen model loading through the project Python. Keep the heavyweight model runtime isolated in the Qwen venv.

## Local Defaults

- Pack root: `D:\Project\yasi\public\packs\cambridge-10\test-1\listening`
- Official transcript: `public\packs\cambridge-10\test-1\listening\transcript.json`
- Section audio: `assets\audio\section-01.mp3` through `section-04.mp3`
- Qwen Python: `D:\Project\video2pdf\newskill-kimi\.venvs\qwen3-asr\Scripts\python.exe`
- Direct transcript align worker: `.agents\skills\yasi-forced-alignment\scripts\qwen_direct_align.py`
- Model root: `D:\model-repo`
- Forced aligner: `D:\model-repo\Qwen3-ForcedAligner-0.6B`
- ffmpeg: `D:\Project\video2pdf\kimi\tools\ffmpeg\bin\ffmpeg.exe`
- ffprobe: `D:\Project\video2pdf\kimi\tools\ffmpeg\bin\ffprobe.exe`
- Whisper CLI: `D:\Project\video2pdf\kimi\.venv\Scripts\whisper.exe`
- Localization output root: `D:\Project\yasi\待删除\yasi-forced-alignment\localization`
- Localized slice plan root: `D:\Project\yasi\待删除\yasi-forced-alignment\plans`
- Audio slicing default: if a section audio file is longer than 180 seconds, first localize official transcript content inside the raw audio, then create localized audio/text slices before direct alignment.

## Workflow

1. Run `D:\Project\yasi\.venv\Scripts\python.exe .agents\skills\yasi-forced-alignment\scripts\align_transcript.py --dry-run --section 1` first to confirm paths, audio duration, slice plan, and worker commands without loading models.
2. For Codex-safe execution, launch heavy GPU work as a background job. Do not run model-loading commands in a foreground Codex shell.

   ```powershell
   D:\Project\yasi\.venv\Scripts\python.exe .agents\skills\yasi-forced-alignment\scripts\launch_alignment_job.py --job-name section-01-localized -- --section 1 --overwrite --localize-content-start --localizer whisper --qwen-device-map cuda:0 --qwen-dtype float16 --qwen-timeout-seconds 900 --slice-threshold-seconds 180 --slice-seconds 180 --slice-overlap-seconds 3 --text-overlap-tokens 20 --min-localization-score 0.82 --min-free-gpu-memory-mib 6000
   ```

   This returns immediately with a job JSON path and PID. Monitor with short one-shot calls:

   ```powershell
   D:\Project\yasi\.venv\Scripts\python.exe .agents\skills\yasi-forced-alignment\scripts\monitor_alignment_job.py --latest
   ```

   Use repeated one-shot monitor calls from Codex. Use `--watch --max-seconds 120` only from an external terminal where temporary blocking is acceptable.
3. Use the official transcript direct alignment path only. The script writes the official section text to `section-XX.official.txt` and calls `Qwen3ForcedAligner.align(audio, official_text, English)`.
4. For any section audio over 180 seconds, rely on `align_transcript.py` to probe duration with ffprobe, create a localization transcript under `D:\Project\yasi\待删除\yasi-forced-alignment\localization`, create localized slice plans under `D:\Project\yasi\待删除\yasi-forced-alignment\plans`, create PCM WAV slices and slice official text under `D:\Project\yasi\待删除\yasi-forced-alignment\slices`, run direct alignment per slice, offset slice-local timings back to the section timeline, and merge the slice outputs into `section-XX.qwen.json`.
5. ASR output is a localization aid only. It may estimate content start and slice boundaries. It never replaces official transcript text, answer evidence, review identity, or displayed shadowing text.
6. Complete Transcript Timing Review in `alignment-review.json`. A subagent may review uncertain mappings, currency, numbers, spelling sequences, apostrophes, punctuation, and hyphenations, then set each `mappingReviews[].decision` to `approved` or `corrected`. The durable output is the JSON file, never chat-only approval.
7. Run `D:\Project\yasi\.venv\Scripts\python.exe .agents\skills\yasi-forced-alignment\scripts\align_transcript.py --finalize-review --review-input <alignment-review.json> --output <transcript-timings.json> --overwrite` to create the final frontend timing asset.
8. Run `D:\Project\yasi\.venv\Scripts\python.exe .agents\skills\yasi-forced-alignment\scripts\validate_timings.py <timing-json> --review-artifact <alignment-review.json> --require-review-trace --require-all-sections` before app consumption.

The chain is:

```text
Localization transcript -> localized audio/text slices -> Qwen direct raw timings -> auto mapping draft -> alignment-review.json -> final transcript-timings.json
```

The official `transcript.json` remains the text authority. `alignment-review.json` is the audit trail; `transcript-timings.json` is the frontend asset. App design docs may refer to this skill by the name `yasi-forced-alignment`.

## Audio/Text Localization Before Slicing

When section audio exceeds 180 seconds, first localize official transcript content inside the raw audio. Use ASR as timing evidence only. Generate localized slices that pair each audio range with the matching official transcript token range. Each Qwen worker must receive slice audio plus slice official text from `transcript.json`.

The useful mental model is a smaller matching box:

```text
audio: local 180-second window
text: official transcript tokens likely spoken inside that window
```

The old plain-audio slicing shape was a larger matching box:

```text
audio: local 180-second window
text: entire section transcript
```

That larger box wastes work because the aligner repeatedly searches across text that is absent from the slice audio.

## Quality Gates

- On RTX 3080 Laptop, prefer `--qwen-dtype float16`; `bfloat16` is a risky default for this GPU class.
- Keep `--qwen-device-map cuda:0` explicit unless intentionally testing CPU or another GPU. Use `--min-free-gpu-memory-mib 6000` so stale CUDA processes fail preflight before model loading.
- Keep the 180-second slicing rule visible in dry-run output. If `audioDurationSeconds` is greater than `sliceThresholdSeconds`, `plannedSections[].slicing.required` must be `true`; localized slices may include configured audio overlap, and every slice must include `audioStart`, `audioEnd`, `officialTokenStart`, `officialTokenEnd`, and `textPreview`.
- Use direct transcript alignment when `transcript.json` is authoritative. It avoids generating a competing transcript and maps results back to official tokens.
- If localization confidence is below `--min-localization-score`, stop before Qwen model loading and report the localization artifact, previews, score, and a suggested manual `--content-start-seconds` override.
- Inspect job JSON and logs under `待删除\yasi-forced-alignment\jobs\` when a Codex thread is interrupted. Use `monitor_alignment_job.py --latest` before starting another GPU task.
- Review punctuation-sensitive tokens: apostrophes, hyphenated spelling, numbers, postcode-like strings, currency, and IELTS answer-bearing terms.
- Require positive intervals and monotonic section timelines.
- Require review trace for every special mapping before release: final timing entries should point back to `alignment-review.json` with `review.reviewId`, `decision`, `riskTypes`, and notes where useful.
- Keep Qwen wrapper outputs under `D:\Project\yasi\待删除\yasi-forced-alignment`; never remove them automatically.

## Failure Handling

- If CUDA, model loading, local Qwen paths, GPU preflight, or worker timeout fail, stop and report the job JSON, exact worker command, `*.wrapper.log.json`, stderr, `nvidia-smi`, and whether `section-XX.qwen.json` exists.
- If localization confidence is too low, stop before Qwen model loading. Report the localization artifact, best match previews, score, and suggested manual `--content-start-seconds` override.
- If a long section appears stuck, treat a no-output CUDA process as a hang until proven otherwise. The useful signal is: GPU process active, CPU time increasing, no `section-XX.qwen.json`, and no draft/review artifact.
- If Codex UI appears stuck, check `monitor_alignment_job.py --latest` from a separate short command or external terminal before interrupting. If interruption already happened, inspect GPU processes before launching another job.
- If token mapping is uncertain, keep the timing artifact `draft`, write the uncertainty to `alignment-review.json`, and ask a reviewer or subagent to correct that file.
- If validation fails, fix the timing artifact or rerun alignment; do not edit `transcript.json` to fit model output.
