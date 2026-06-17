---
name: yasi-forced-alignment
description: Use when working in the D:\Project\yasi project on Qwen3-ForcedAligner, transcript timings, forced alignment, transcript-timings.json, alignment-review.json, Transcript Timing Review, IELTS listening shadowing, or Cambridge listening pack word-level timing artifacts. Generates draft, review, and final timing JSON from local Qwen ASR plus forced alignment while keeping transcript.json as the official text authority.
---

# Yasi Forced Alignment

Use this skill to produce and validate `transcript-timings.json` style assets for IELTS listening shadowing in `D:\Project\yasi`.

## Python Environments

Use two Python environments deliberately:

- Project Python: `D:\Project\yasi\.venv\Scripts\python.exe`
  - Use for `scripts\align_transcript.py --help`, `--dry-run`, review finalization, and `scripts\validate_timings.py`.
  - This environment runs the yasi orchestration and validation scripts. It does not need to import Qwen model packages.
- Qwen Python: `D:\Project\video2pdf\newskill-kimi\.venvs\qwen3-asr\Scripts\python.exe`
  - Use for the referenced Qwen ASR wrapper and any command that loads `Qwen3-ASR-*` or `Qwen3-ForcedAligner-0.6B`.
  - Use this environment for skill validation with `quick_validate.py`; on Windows set `PYTHONUTF8=1` first so UTF-8 skill files are read correctly.

Do not run Qwen model loading through the project Python. Keep the heavyweight model runtime isolated in the Qwen venv.

## Local Defaults

- Pack root: `D:\Project\yasi\public\packs\cambridge-10\test-1\listening`
- Official transcript: `public\packs\cambridge-10\test-1\listening\transcript.json`
- Section audio: `assets\audio\section-01.mp3` through `section-04.mp3`
- Qwen Python: `D:\Project\video2pdf\newskill-kimi\.venvs\qwen3-asr\Scripts\python.exe`
- Qwen ASR wrapper: `D:\Project\video2pdf\newskill-kimi\.agents\skills\qwen-bilibili-render-pdf\scripts\qwen_asr_transcribe.py`
- Model root: `D:\model-repo`
- Forced aligner: `D:\model-repo\Qwen3-ForcedAligner-0.6B`
- Fast ASR model: `D:\model-repo\Qwen3-ASR-0.6B`
- Quality ASR model: `D:\model-repo\Qwen3-ASR-1.7B`
- ffmpeg: `D:\Project\video2pdf\kimi\tools\ffmpeg\bin\ffmpeg.exe`
- ffprobe: `D:\Project\video2pdf\kimi\tools\ffmpeg\bin\ffprobe.exe`

## Workflow

1. Run `D:\Project\yasi\.venv\Scripts\python.exe scripts\align_transcript.py --dry-run --section 1` first to confirm paths and wrapper commands without loading models.
2. Run `D:\Project\yasi\.venv\Scripts\python.exe scripts\align_transcript.py --section N --profile quality --overwrite` for one section, or `--all-sections` when the environment is already proven. This writes an auto-mapping draft and `alignment-review.json`; the script invokes the Qwen wrapper with the Qwen Python path.
3. Complete Transcript Timing Review in `alignment-review.json`. A subagent may review uncertain mappings, currency, numbers, spelling sequences, apostrophes, punctuation, and hyphenations, then set each `mappingReviews[].decision` to `approved` or `corrected`. The durable output is the JSON file, never chat-only approval.
4. Run `D:\Project\yasi\.venv\Scripts\python.exe scripts\align_transcript.py --finalize-review --review-input <alignment-review.json> --output <transcript-timings.json> --overwrite` to create the final frontend timing asset.
5. Run `D:\Project\yasi\.venv\Scripts\python.exe scripts\validate_timings.py <timing-json> --review-artifact <alignment-review.json> --require-review-trace --require-all-sections` before app consumption.

The chain is:

```text
Qwen raw timings -> auto mapping draft -> alignment-review.json -> final transcript-timings.json
```

The official `transcript.json` remains the text authority. `alignment-review.json` is the audit trail; `transcript-timings.json` is the frontend asset. App design docs may refer to this skill by the name `yasi-forced-alignment`.

## Quality Gates

- Prefer `--profile quality` for final timing work; use `fast` only for cheap probes or first-pass diagnostics.
- Review punctuation-sensitive tokens: apostrophes, hyphenated spelling, numbers, postcode-like strings, currency, and IELTS answer-bearing terms.
- Require positive intervals and monotonic section timelines.
- Require review trace for every special mapping before release: final timing entries should point back to `alignment-review.json` with `review.reviewId`, `decision`, `riskTypes`, and notes where useful.
- Keep Qwen wrapper outputs under `D:\Project\yasi\待删除\yasi-forced-alignment`; never remove them automatically.

## Failure Handling

- If CUDA, model loading, or local Qwen paths fail, stop and report the exact wrapper command and stderr.
- If token mapping is uncertain, keep the timing artifact `draft`, write the uncertainty to `alignment-review.json`, and ask a reviewer or subagent to correct that file.
- If validation fails, fix the timing artifact or rerun alignment; do not edit `transcript.json` to fit model output.
