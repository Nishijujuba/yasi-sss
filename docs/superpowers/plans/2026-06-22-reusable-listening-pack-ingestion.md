# Reusable Listening Pack Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Cambridge IELTS 10 Test 1 Listening 的完整接入经验抽象成一条可复用的 `Listening Practice Pack` 接入流水线，用于后续 Cambridge IELTS 书籍和测试题包。

**Architecture:** 先把 Test 1 中的硬编码路径、状态键、source data 和发布逻辑改成 `PackConfig` 驱动，再用同一套 builder 生成每个测试的 `manifest.json`、题目、答案、叠层、原文、音频、词汇、精听和可选跟读计时资产。前端从可选 pack 列表加载指定 `baseUrl`，本地状态按 `packId` 隔离。

**Tech Stack:** Python 3.11, Pydantic, Pillow, NumPy, FFmpeg/FFprobe, pdftoppm, React, TypeScript, Vite, Vitest, Playwright, project interpreter `.venv\Scripts\python.exe`.

---

## Terms And Boundaries

`Listening Practice Pack` 是一个完整 IELTS 听力测试的发布单位。它至少包含 40 道题、四个 `Listening Section`、官方答案、官方 audioscript、页面截图、交互叠层、四段 MP3 音频和发布 manifest。

`Core Exam Pack` 是可练、可提交、可严格判分的最小发布层，包含 `questions.json`、`answers.json`、`overlays.json`、`transcript.json`、section MP3、question page PNG 和 `manifest.json`。

`Derived Learning Assets` 是从 `Core Exam Pack` 派生出的学习层，包含 `vocabulary.json`、vocabulary audio clips、`intensive-listening.json`、`transcript-timings.preview.json` 或验证后的 `transcript-timings.json`。

`Source Data` 是人工或模型辅助整理后进入 builder 的权威输入。它和 public pack 输出要分开保存。public pack 是可发布产物，source data 是可审查的构建证据。

`PackConfig` 是每套题的构建参数集合。它回答“这套题来自哪个 PDF、哪些页、哪些音频、输出到哪个 pack root、source data 在哪里、review artifact 写哪里”。

`Source Book PDF` 是完整官方 Cambridge IELTS 书籍 PDF。它像原始账本，后续题目、原文、答案和切分证据都要能追溯回它。

`Chapter-Split Source PDF` 是从 `Source Book PDF` 按章节或测试范围切出的稳定 PDF，例如 Test 1、Audioscripts、Answer Keys。builder 应优先使用这类分 P 文件作为直接输入。

## Why This Shape

Flat `builder/source_data/*.json` 只支持一个活跃测试，继续沿用会让新题包覆盖旧题包的 source data。每包独立目录能保留所有测试的答案、原文、候选精听和人工 review 证据。

Copy-paste builder modules 会让 detector、validator、音频转换、manifest 生成的修复扩散成四份。共享 builder 加 `PackConfig` 让所有 pack 走同一条门禁。

Core pack 先行能先锁住题目、答案、页面、叠层、原文和音频这些权威输入。词汇、精听、跟读计时依赖这些输入，放在第二层能减少返工。

每次执行这份计划时，目标书籍和测试编号必须由提示词传入。计划中的尖括号占位符是执行参数，例如 `<book-id>`、`<test-id>`、`<pack-id>`、`<pack-config-path>`，执行 agent 必须先用提示词里的具体值替换，再运行命令。

## Existing Test 1 Surface To Abstract

Current hardcoded areas:

- `builder/config.py`: `QUESTION_PDF`, `AUDIO_SOURCE_ROOT`, `PACK_ROOT`, `PAGE_ASSET_ROOT`, `AUDIO_ASSET_ROOT`, `SOURCE_DATA_ROOT`, `QUESTION_PAGE_NUMBERS`.
- `builder/build_pack.py`: `packId`, title, section page mapping, assets list.
- `builder/render_pages.py`: default PDF, output dir, page numbers.
- `builder/convert_audio.py`: Test 1 WMA sources and output audio directory.
- `builder/detect_overlays.py`: flat `questions.json`, flat `overlay-proposals.json`, Test 1 refined rectangles.
- `builder/overlay_review.py`: flat `vision-validation.json`, flat public overlays path.
- `builder/validate_pack.py`: default `PACK_ROOT`, flat source answers/transcript/vocabulary.
- `builder/intensive_listening.py`: flat candidate filenames under `builder/source_data`.
- `src/lib/loadPack.ts`: default base URL `/packs/cambridge-10/test-1/listening`.
- `src/lib/session.ts`: Test 1 session key and `SESSION_PACK_ID`.
- `src/lib/mistakeVocabulary.ts`: Test 1 notebook key and typed `PACK_ID`.
- `src/context/PracticeSessionContext.tsx`: boot path assumes a single default pack.

Current repo examples for Cambridge 10 orientation:

These examples help an agent understand the current checkout. They are examples only; the prompted input contract supplies the execution target.

- Test 1 source PDF: `resources/剑桥/剑桥雅思10/剑桥雅思真题10分P/02_Test_1_p010-p032.pdf`.
- Test 2 source PDF: `resources/剑桥/剑桥雅思10/剑桥雅思真题10分P/03_Test_2_p033-p056.pdf`.
- Test 3 source PDF: `resources/剑桥/剑桥雅思10/剑桥雅思真题10分P/04_Test_3_p057-p079.pdf`.
- Test 4 source PDF: `resources/剑桥/剑桥雅思10/剑桥雅思真题10分P/05_Test_4_p080-p103.pdf`.
- Shared audioscript PDF: `resources/剑桥/剑桥雅思10/剑桥雅思真题10分P/08_Audioscripts_p130-p150.pdf`.
- Shared answer key PDF: `resources/剑桥/剑桥雅思10/剑桥雅思真题10分P/09_Listening_and_Reading_Answer_Keys_p151-p160.pdf`.
- Audio directories: `resources/剑桥/剑桥雅思10/剑桥雅思10音频/test1` through `test4`.
- For Cambridge 11, Cambridge 12, or later books, the prompt must provide the equivalent source root, split PDF names, answer-key PDF, audioscript PDF, and audio directory.

## Prompt Input Contract

Before executing the reusable ingestion flow, the prompt must provide:

- `<book-id>`: stable URL/path identifier, such as `cambridge-10`, `cambridge-11`, or `cambridge-12`.
- `<book-title>`: display title prefix, such as `Cambridge IELTS 11`.
- `<book-resource-root>`: source root under `resources/`, such as `resources/剑桥/剑桥雅思11`.
- `<source-book-pdf>`: full-book `Source Book PDF` under `<book-resource-root>`, such as `resources/剑桥/剑桥雅思11/剑桥雅思真题11A.pdf`.
- `<split-output-dir>`: directory for `Chapter-Split Source PDF` outputs, such as `resources/剑桥/剑桥雅思11/剑桥雅思真题11A分P`.
- `<split-manifest-path>`: UTF-8 page-ledger manifest path for `yasi-pdf-chapter-splitting`, such as `.agents/skills/yasi-pdf-chapter-splitting/fixtures/cambridge-11a-chapter-split.json`.
- `<test-id>`: stable test identifier, such as `test-2`.
- `<test-number>`: display number, such as `2`.
- `<pack-id>`: stable manifest id, such as `<book-id>-<test-id>-listening`.
- `<pack-config-path>`: config file path, usually `builder/pack_configs/<pack-id>.json`.
- `<question-pdf>`: `Chapter-Split Source PDF` containing the question pages for this test; this is produced by Task 0 when absent.
- `<question-page-numbers>`: source book page numbers used for listening question pages.
- `<audioscript-pdf>`: official audioscript `Chapter-Split Source PDF` for the book; this is produced by Task 0 when absent.
- `<answer-key-pdf>`: official answer-key `Chapter-Split Source PDF` for the book; this is produced by Task 0 when absent.
- `<audio-source-01>` through `<audio-source-04>`: four source WMA or audio files for Listening Sections 01-04.
- `<source-data-root>`: `builder/source_data/<book-id>/<test-id>/listening`.
- `<pack-root>`: `public/packs/<book-id>/<test-id>/listening`.
- `<review-root>`: `build/review/<book-id>/<test-id>/listening`.
- `<timing-review-artifact>`: `build/review/transcript-timing/<pack-id>/alignment-review.json`.

If `<question-pdf>`, `<audioscript-pdf>`, or `<answer-key-pdf>` are missing from the prompt, Task 0 must derive them from existing files under `<split-output-dir>` or create them with `yasi-pdf-chapter-splitting`. If `<book-resource-root>`, `<source-book-pdf>`, or `<split-manifest-path>` are missing and no split PDFs exist, the agent should stop at preflight and ask for that exact missing value.

## PackConfig Contract

Create one config per pack:

```jsonc
{
  "bookId": "<book-id>",
  "testId": "<test-id>",
  "packId": "<pack-id>",
  "title": "<book-title> Test <test-number> Listening",
  "questionPdf": "<question-pdf>",
  "questionPageNumbers": ["<source-page-001>", "<source-page-002>"],
  "audioscriptPdf": "<audioscript-pdf>",
  "answerKeyPdf": "<answer-key-pdf>",
  "audioSources": [
    "<audio-source-01>",
    "<audio-source-02>",
    "<audio-source-03>",
    "<audio-source-04>"
  ],
  "sourceDataRoot": "<source-data-root>",
  "packRoot": "<pack-root>",
  "reviewRoot": "<review-root>",
  "sections": [
    {"number": 1, "questionNumbers": [1,2,3,4,5,6,7,8,9,10], "audio": "assets/audio/section-01.mp3", "pages": ["assets/pages/page-<section-01-page-a>.png"]},
    {"number": 2, "questionNumbers": [11,12,13,14,15,16,17,18,19,20], "audio": "assets/audio/section-02.mp3", "pages": ["assets/pages/page-<section-02-page-a>.png"]},
    {"number": 3, "questionNumbers": [21,22,23,24,25,26,27,28,29,30], "audio": "assets/audio/section-03.mp3", "pages": ["assets/pages/page-<section-03-page-a>.png"]},
    {"number": 4, "questionNumbers": [31,32,33,34,35,36,37,38,39,40], "audio": "assets/audio/section-04.mp3", "pages": ["assets/pages/page-<section-04-page-a>.png"]}
  ]
}
```

The exact page-to-section mapping must be visually checked per test. The gate accepts a mapping only after every question number appears on the declared section pages.

Normalized overlay coordinates remain the invariant:

\[
x_n=\frac{x}{W},\quad y_n=\frac{y}{H},\quad w_n=\frac{w}{W},\quad h_n=\frac{h}{H}
\]

Strict marking keeps the Test 1 rule:

\[
N(s)=\operatorname{lowercase}(\operatorname{collapseSpaces}(\operatorname{trim}(s)))
\]

A learner response receives credit only when \(N(response)\) matches an accepted answer form after the same normalization.

## File And Ownership Map

- Create: `builder/pack_config.py` for loading and validating `PackConfig`.
- Create: `builder/pack_configs/cambridge-10-test-1-listening.json`.
- Create per-pack configs at `builder/pack_configs/<pack-id>.json` as each target pack is supplied by prompt.
- Move source-data ownership into: `builder/source_data/cambridge-10/test-1/listening/`.
- Create per-pack source-data folders at `builder/source_data/<book-id>/<test-id>/listening/` as each pack is prepared.
- Modify: `builder/render_pages.py` to accept config paths.
- Modify: `builder/convert_audio.py` to accept config audio sources and output dir.
- Modify: `builder/detect_overlays.py` to accept config source data, page dir, review dir, and pack root.
- Modify: `builder/overlay_review.py` to accept config review dir and vision-validation path.
- Modify: `builder/validate_pack.py` to accept config source data and pack root.
- Modify: `builder/intensive_listening.py` to accept per-pack candidate source directory.
- Modify: `builder/build_pack.py` to accept `--pack-config`.
- Create: `src/lib/packCatalog.ts` for available packs.
- Modify: `src/lib/loadPack.ts` so the default remains Test 1 while callers can pass any pack base URL.
- Modify: `src/lib/session.ts` so keys derive from `packId`.
- Modify: `src/lib/mistakeVocabulary.ts` so notebook keys derive from `packId`.
- Modify: `src/context/PracticeSessionContext.tsx` so selected pack controls load and state.
- Modify: `src/components/PracticePackHome.tsx` to show available packs and current selected pack.
- Add tests under `tests/python/` and `src/**.test.ts(x)` for pack config, parameterized build, and state-key isolation.

## Task 0: Resolve Chapter-Split Source PDFs

**Files:**
- Read: `<book-resource-root>`
- Read or create: `<split-manifest-path>`
- Generate if absent: `<split-output-dir>/*.pdf`
- Use skill: `.agents/skills/yasi-pdf-chapter-splitting/SKILL.md`
- Use reference: `.agents/skills/yasi-pdf-chapter-splitting/references/manifest-schema.md`
- Use script: `.agents/skills/yasi-pdf-chapter-splitting/scripts/split_pdf_chapters.py`

- [ ] **Step 1: Inspect the book resource root**

Run:

```powershell
Get-ChildItem -File -LiteralPath '<book-resource-root>' | Select-Object Name,Length
Get-ChildItem -Directory -LiteralPath '<book-resource-root>' | Select-Object Name
```

Expected: the full-book `Source Book PDF` is visible under `<book-resource-root>`, and an existing split directory such as `<split-output-dir>` may already exist.

- [ ] **Step 2: Check whether usable split PDFs already exist**

Run:

```powershell
Get-ChildItem -File -LiteralPath '<split-output-dir>' -Filter '*.pdf' | Select-Object Name,Length
```

Expected when split PDFs already exist: files include a test PDF for `<test-id>`, an Audioscripts PDF, and a Listening and Reading Answer Keys PDF. In that case, set `<question-pdf>`, `<audioscript-pdf>`, and `<answer-key-pdf>` from those files and skip to Step 7.

Expected when split PDFs are absent: the command reports no files or the directory does not exist. In that case, continue to Step 3.

- [ ] **Step 3: Prepare the split manifest**

Use `.agents/skills/yasi-pdf-chapter-splitting/references/manifest-schema.md` as the contract. The manifest must use:

```json
{
  "schemaVersion": "yasi.pdf-chapter-split.v1",
  "sourcePdf": "<source-book-pdf>",
  "outputDir": "<split-output-dir>",
  "expectedTotalPages": 0,
  "coverage": "complete",
  "pageNumberBasis": "pdf-physical-1-based",
  "chapters": []
}
```

Replace `expectedTotalPages` and `chapters` with the verified physical PDF page ledger for the prompted book. Cambridge examples are available at `.agents/skills/yasi-pdf-chapter-splitting/fixtures/cambridge-10-chapter-split.json` and `.agents/skills/yasi-pdf-chapter-splitting/fixtures/cambridge-11a-chapter-split.json`.

- [ ] **Step 4: Validate the split ledger in dry-run mode**

Run:

```powershell
$env:PYTHONUTF8='1'
.venv\Scripts\python.exe .agents\skills\yasi-pdf-chapter-splitting\scripts\split_pdf_chapters.py --manifest <split-manifest-path> --dry-run
```

Expected: dry-run succeeds, every physical source page is accounted for once, and no split output is written.

If this command fails because the project Python is missing `pypdf` or `Pillow`, install or enable a Python environment that satisfies the skill dependency before continuing. Do not bypass the ledger validation.

- [ ] **Step 5: Split and render first-page checks**

Run:

```powershell
$env:PYTHONUTF8='1'
.venv\Scripts\python.exe .agents\skills\yasi-pdf-chapter-splitting\scripts\split_pdf_chapters.py --manifest <split-manifest-path> --render-first-pages
```

Expected: chapter PDFs are written under `<split-output-dir>`, existing outputs are moved by the script into repo-root `待删除`, every output page count matches the manifest, and first-page renders are created for visual inspection.

- [ ] **Step 6: Visually verify split starts**

Inspect the rendered first pages created by the split script. Confirm that the prompted test chapter, Audioscripts chapter, and Listening and Reading Answer Keys chapter start on the intended pages.

- [ ] **Step 7: Bind split PDFs to pack inputs**

Set these Prompt Input Contract values from the split directory:

```text
<question-pdf> = the Chapter-Split Source PDF for the prompted test
<audioscript-pdf> = the Chapter-Split Source PDF for Audioscripts
<answer-key-pdf> = the Chapter-Split Source PDF for Listening and Reading Answer Keys
```

Expected: all three paths exist, are non-empty PDFs, and sit under `<split-output-dir>`.

## Task 1: Introduce PackConfig

**Files:**
- Create: `builder/pack_config.py`
- Create: `builder/pack_configs/cambridge-10-test-1-listening.json`
- Create: `tests/python/test_pack_config.py`

- [ ] **Step 1: Write failing tests for config validation**

```python
from pathlib import Path

import pytest

from builder.pack_config import PackConfig, load_pack_config


def test_loads_test1_pack_config():
    config = load_pack_config(Path("builder/pack_configs/cambridge-10-test-1-listening.json"))

    assert config.pack_id == "cambridge-10-test-1-listening"
    assert config.pack_root.as_posix().endswith("public/packs/cambridge-10/test-1/listening")
    assert [section.number for section in config.sections] == [1, 2, 3, 4]
    assert [len(section.question_numbers) for section in config.sections] == [10, 10, 10, 10]


def test_rejects_missing_question_coverage(tmp_path):
    config_path = tmp_path / "bad-pack.json"
    config_path.write_text(
        '''
        {
          "bookId": "cambridge-10",
          "testId": "test-x",
          "packId": "bad",
          "title": "Bad Pack",
          "questionPdf": "resources/剑桥/剑桥雅思10/剑桥雅思真题10分P/02_Test_1_p010-p032.pdf",
          "questionPageNumbers": [10],
          "audioscriptPdf": "resources/剑桥/剑桥雅思10/剑桥雅思真题10分P/08_Audioscripts_p130-p150.pdf",
          "answerKeyPdf": "resources/剑桥/剑桥雅思10/剑桥雅思真题10分P/09_Listening_and_Reading_Answer_Keys_p151-p160.pdf",
          "audioSources": [],
          "sourceDataRoot": "builder/source_data/bad",
          "packRoot": "public/packs/bad",
          "reviewRoot": "build/review/bad",
          "sections": [
            {"number": 1, "questionNumbers": [1], "audio": "assets/audio/section-01.mp3", "pages": ["assets/pages/page-010.png"]}
          ]
        }
        ''',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="1 through 40"):
        load_pack_config(config_path)
```

- [ ] **Step 2: Run the failing config tests**

```powershell
.venv\Scripts\python.exe -m pytest tests\python\test_pack_config.py -q
```

Expected: import fails because `builder.pack_config` does not exist.

- [ ] **Step 3: Implement the config model**

Implement `PackConfig` and `SectionConfig` with Pydantic or dataclasses. Validate:

- `packId` is a non-empty string.
- `audioSources` contains exactly four existing files.
- `questionPageNumbers` is non-empty.
- `sections` contains exactly sections `1..4`.
- section question coverage is exactly `1..40`.
- paths resolve inside the repo for source data, pack output, and review output.

- [ ] **Step 4: Save the Test 1 config**

Use the existing Test 1 values from `builder/config.py`, preserving the current released pack layout.

- [ ] **Step 5: Verify**

```powershell
.venv\Scripts\python.exe -m pytest tests\python\test_pack_config.py -q
```

Expected: tests pass.

## Task 2: Move Test 1 Source Data Into A Per-Pack Folder

**Files:**
- Move by Git-aware rename: `builder/source_data/*.json` into `builder/source_data/cambridge-10/test-1/listening/`
- Modify: `builder/pack_configs/cambridge-10-test-1-listening.json`
- Modify: tests that read flat source data

- [ ] **Step 1: Create the target folder**

```powershell
New-Item -ItemType Directory -Force -Path builder\source_data\cambridge-10\test-1\listening
```

- [ ] **Step 2: Move source files with `Move-Item`**

Use `Move-Item`, preserving the files as Git renames. The source data files include:

- `answers.json`
- `questions.json`
- `vision-validation.json`
- `vocabulary.json`
- `transcript-section-01.json`
- `transcript-section-02.json`
- `transcript-section-03.json`
- `transcript-section-04.json`
- `intensive-listening-candidates-section-01.json`
- `intensive-listening-candidates-section-02.json`
- `intensive-listening-candidates-section-03.json`
- `intensive-listening-candidates-section-04.json`

- [ ] **Step 3: Update tests and builder defaults to read from `PackConfig.sourceDataRoot`**

Every source-data read should receive an explicit directory from config or from a test fixture.

- [ ] **Step 4: Verify Test 1 still builds**

```powershell
.venv\Scripts\python.exe -m pytest tests\python -q
.venv\Scripts\python.exe -m builder.build_pack --pack-config builder\pack_configs\cambridge-10-test-1-listening.json
```

Expected: Python tests pass and Test 1 `release-report.json` still reports released status.

## Task 3: Parameterize The Builder

**Files:**
- Modify: `builder/build_pack.py`
- Modify: `builder/render_pages.py`
- Modify: `builder/convert_audio.py`
- Modify: `builder/detect_overlays.py`
- Modify: `builder/overlay_review.py`
- Modify: `builder/validate_pack.py`
- Modify: `builder/intensive_listening.py`
- Modify: `tests/python/test_validate_pack.py`
- Modify: `tests/python/test_render_pages.py`
- Modify: `tests/python/test_convert_audio.py`
- Modify: `tests/python/test_detect_overlays.py`

- [ ] **Step 1: Add a failing CLI test**

```python
import json
import subprocess


def test_build_pack_accepts_pack_config():
    completed = subprocess.run(
        [
            ".venv/Scripts/python.exe",
            "-m",
            "builder.build_pack",
            "--pack-config",
            "builder/pack_configs/cambridge-10-test-1-listening.json",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["packId"] == "cambridge-10-test-1-listening"
```

- [ ] **Step 2: Implement `--pack-config` and `--dry-run`**

`--dry-run` should load the config, prove paths and source files exist, then print JSON containing `packId`, `packRoot`, `sourceDataRoot`, and section page/audio mapping.

- [ ] **Step 3: Thread config through every builder stage**

Each stage receives config-derived paths:

- render pages: `questionPdf`, `questionPageNumbers`, `packRoot/assets/pages`.
- overlays: `sourceDataRoot/questions.json`, `reviewRoot/overlay-proposals.json`, `sourceDataRoot/vision-validation.json`, `packRoot/overlays.json`.
- audio: `audioSources`, `packRoot/assets/audio`.
- source export: `sourceDataRoot/answers.json`, transcript sections, vocabulary.
- intensive listening: `sourceDataRoot/intensive-listening-candidates-section-*.json`.
- manifest: `packId`, title, sections, assets.
- report: `reviewRoot/release-report.json`.

- [ ] **Step 4: Keep Test 1 as the default CLI behavior**

Running the old command should still target Test 1:

```powershell
.venv\Scripts\python.exe -m builder.build_pack
```

Expected: same effective config as `cambridge-10-test-1-listening.json`.

- [ ] **Step 5: Verify**

```powershell
.venv\Scripts\python.exe -m pytest tests\python -q
.venv\Scripts\python.exe -m builder.build_pack --pack-config builder\pack_configs\cambridge-10-test-1-listening.json
```

Expected: Test 1 releases with the parameterized code path.

## Task 4: Generalize Frontend Pack Loading And Local State

**Files:**
- Create: `src/lib/packCatalog.ts`
- Modify: `src/lib/loadPack.ts`
- Modify: `src/lib/session.ts`
- Modify: `src/lib/mistakeVocabulary.ts`
- Modify: `src/context/PracticeSessionContext.tsx`
- Modify: `src/components/PracticePackHome.tsx`
- Modify: related tests under `src/`

- [ ] **Step 1: Add failing state-key tests**

```typescript
import { sessionKeyForPack } from "./session";
import { mistakeVocabularyKeyForPack } from "./mistakeVocabulary";

it("derives practice session keys from packId", () => {
  expect(sessionKeyForPack("<pack-id>")).toBe(
    "yasi:<pack-id>:session:v3",
  );
});

it("derives mistake notebook keys from packId", () => {
  expect(mistakeVocabularyKeyForPack("<pack-id>")).toBe(
    "yasi:<pack-id>:mistake-vocabulary:v2",
  );
});
```

- [ ] **Step 2: Implement key helpers**

Keep legacy Test 1 key migration for existing localStorage users. New packs should use `packId` directly in the key.

- [ ] **Step 3: Add a pack catalog**

```typescript
export const PACK_CATALOG = [
  {
    packId: "cambridge-10-test-1-listening",
    title: "Cambridge IELTS 10 Test 1 Listening",
    baseUrl: "/packs/cambridge-10/test-1/listening",
  },
  {
    packId: "<pack-id>",
    title: "<book-title> Test <test-number> Listening",
    baseUrl: "/packs/<book-id>/<test-id>/listening",
  },
];
```

Only add the prompted pack to the catalog after its `manifest.json` reaches released status.

- [ ] **Step 4: Load selected pack by base URL**

The provider should accept or store selected pack identity, call `loadPack(selected.baseUrl)`, then load session, mistake notebook, and intensive-listening state using `loaded.manifest.packId`.

- [ ] **Step 5: Verify**

```powershell
npm test -- src/lib/session.test.ts src/lib/mistakeVocabulary.test.ts src/lib/loadPack.test.ts src/components/PracticePackHome.test.tsx
npm test
npm run build
```

Expected: state isolation works for multiple pack IDs, legacy Test 1 storage still migrates, build passes.

## Task 5: Ingest One New Core Exam Pack

**Files For The Prompted Pack:**
- Create: `builder/pack_configs/<pack-id>.json`
- Create: `builder/source_data/<book-id>/<test-id>/listening/questions.json`
- Create: `builder/source_data/<book-id>/<test-id>/listening/answers.json`
- Create: `builder/source_data/<book-id>/<test-id>/listening/transcript-section-01.json`
- Create: `builder/source_data/<book-id>/<test-id>/listening/transcript-section-02.json`
- Create: `builder/source_data/<book-id>/<test-id>/listening/transcript-section-03.json`
- Create: `builder/source_data/<book-id>/<test-id>/listening/transcript-section-04.json`
- Create: `builder/source_data/<book-id>/<test-id>/listening/vision-validation.json`
- Generate: `public/packs/<book-id>/<test-id>/listening/manifest.json`
- Generate: `public/packs/<book-id>/<test-id>/listening/questions.json`
- Generate: `public/packs/<book-id>/<test-id>/listening/answers.json`
- Generate: `public/packs/<book-id>/<test-id>/listening/overlays.json`
- Generate: `public/packs/<book-id>/<test-id>/listening/transcript.json`
- Generate: `public/packs/<book-id>/<test-id>/listening/assets/pages/*.png`
- Generate: `public/packs/<book-id>/<test-id>/listening/assets/audio/section-*.mp3`
- Generate: `build/review/<book-id>/<test-id>/listening/release-report.json`
- Generate: `build/review/<book-id>/<test-id>/listening/overlays/*.png`

- [ ] **Step 1: Create pack config**

For the prompted pack:

```powershell
Copy-Item builder\pack_configs\cambridge-10-test-1-listening.json <pack-config-path>
```

Then edit values from the prompt input contract. Keep source PDFs read-only.

- [ ] **Step 2: Render and visually inspect pages**

```powershell
.venv\Scripts\python.exe -m builder.render_pages --pack-config <pack-config-path>
```

Expected: non-empty `page-*.png` files under `<pack-root>\assets\pages`. Inspect each page image and record which pages contain questions `1..40`.

- [ ] **Step 3: Write `questions.json`**

Encode question type, section, page ownership, focus order, choice options, and selection limits. Do this before overlay detection, because detector semantics depend on the expected question list.

- [ ] **Step 4: Detect overlay proposals**

```powershell
.venv\Scripts\python.exe -m builder.detect_overlays --pack-config <pack-config-path>
.venv\Scripts\python.exe -m builder.overlay_review --pack-config <pack-config-path>
```

Expected: review PNGs under `<review-root>\overlays`.

- [ ] **Step 5: Perform independent visual validation**

A reviewer checks original page PNGs and overlay review PNGs. The output is `vision-validation.json`, one entry per blank or choice option. Every approved region must have confidence \(\ge 0.85\).

- [ ] **Step 6: Finalize overlays**

```powershell
.venv\Scripts\python.exe -m builder.overlay_review --pack-config <pack-config-path> --finalize
```

Expected: `<pack-root>\overlays.json`.

- [ ] **Step 7: Extract official answers**

Use the official answer-key PDF. Each answer entry records provenance and review status. Internet candidates require explicit user approval before they enter `answers.json`.

- [ ] **Step 8: Extract official audioscript**

Use the shared audioscript PDF. Write four transcript section files with ordered segments, source pages, answer references, and `startTime` / `endTime` as `null`.

- [ ] **Step 9: Convert audio**

```powershell
.venv\Scripts\python.exe -m builder.convert_audio --pack-config <pack-config-path>
```

Expected: `section-01.mp3` through `section-04.mp3` exist and each output duration differs from source WMA by at most `0.10` seconds.

- [ ] **Step 10: Build core pack**

```powershell
.venv\Scripts\python.exe -m builder.build_pack --pack-config <pack-config-path> --core-only
```

Expected: core files exist and release report identifies exact missing derived assets if Stage B has not run.

## Task 6: Add Derived Learning Assets

**Files For The Prompted Pack:**
- Create: `builder/source_data/<book-id>/<test-id>/listening/vocabulary.json`
- Create: `builder/source_data/<book-id>/<test-id>/listening/intensive-listening-candidates-section-01.json`
- Create: `builder/source_data/<book-id>/<test-id>/listening/intensive-listening-candidates-section-02.json`
- Create: `builder/source_data/<book-id>/<test-id>/listening/intensive-listening-candidates-section-03.json`
- Create: `builder/source_data/<book-id>/<test-id>/listening/intensive-listening-candidates-section-04.json`
- Generate: `public/packs/<book-id>/<test-id>/listening/vocabulary.json`
- Generate: `public/packs/<book-id>/<test-id>/listening/assets/audio/vocabulary/*.mp3`
- Generate: `public/packs/<book-id>/<test-id>/listening/intensive-listening.json`

- [ ] **Step 1: Build vocabulary source from accepted blank answers**

Every single blank answer becomes one vocabulary item. Preserve numeric answers such as `2020` and `429` when they appear in a pack.

- [ ] **Step 2: Generate vocabulary audio clips**

```powershell
.venv\Scripts\python.exe -m builder.vocabulary_audio --pack-config <pack-config-path>
```

Expected: every vocabulary item references an existing MP3 clip between `0.25s` and `6.0s`.

- [ ] **Step 3: Produce section-scoped intensive-listening candidates**

Use `.agents/skills/yasi-intensive-listening/` only for candidate-source JSON. The builder remains the authority for released `intensive-listening.json`.

- [ ] **Step 4: Export intensive-listening asset**

```powershell
.venv\Scripts\python.exe -m builder.intensive_listening --pack-config <pack-config-path>
```

Expected: `intensive-listening.json` has schema version `yasi.intensive-listening.v1`, covers sections `1..4`, and all blank answers match official transcript token spans.

## Task 7: Add Transcript Timing Preview Or Verified Shadowing

**Files For The Prompted Pack:**
- Generate preview: `public/packs/<book-id>/<test-id>/listening/transcript-timings.preview.json`
- Generate verified release: `public/packs/<book-id>/<test-id>/listening/transcript-timings.json`
- Generate review audit: `build/review/transcript-timing/<pack-id>/alignment-review.json`

- [ ] **Step 1: Build preview timings when verified timings are unavailable**

Use the ASR timing reconciliation workflow with pack-scoped parameters. Preview timing may contain untimed review markers.

- [ ] **Step 2: Validate preview timing**

```powershell
.venv\Scripts\python.exe .agents\skills\yasi-asr-timing-reconciliation\scripts\validate_timings.py `
  --pack-root <pack-root> `
  --status preview
```

Expected: preview status validates for learner-facing preview paths.

- [ ] **Step 3: Promote only after release audit**

Verified `transcript-timings.json` requires complete, monotonic word timings and an existing review artifact:

```text
build/review/transcript-timing/<pack-id>/alignment-review.json
```

## Task 8: Final Release Verification

**Files:**
- Modify as needed: `tests/e2e/practice.spec.ts`
- Add per-pack browser coverage when new packs become visible in catalog

- [ ] **Step 1: Run Python gates**

```powershell
.venv\Scripts\python.exe -m pytest tests\python -q
.venv\Scripts\python.exe -m builder.build_pack --pack-config <pack-config-path>
```

Expected: all Python tests pass and the new pack release report is `released`.

- [ ] **Step 2: Run frontend gates**

```powershell
npm test
npm run build
```

Expected: all Vitest tests pass and production build completes.

- [ ] **Step 3: Run browser acceptance**

```powershell
npx playwright test tests\e2e\practice.spec.ts --project=chrome
```

Expected: pack selection, answer entry, section switching, submission, mistake notebook, intensive listening unlock, and return-home flows work for the selected pack.

- [ ] **Step 4: Inspect in a real browser**

Reuse an existing healthy preview server on `http://127.0.0.1:4173/` when available. If Codex must launch a server, use the detached ProcessStartInfo pattern from `AGENT.md` and verify readiness with a short `Invoke-WebRequest` command.

- [ ] **Step 5: Check status**

```powershell
git diff --check
git status --short
```

Expected: whitespace is clean and changed files match the intended pack ingestion scope.

## Reusable Per-Pack Checklist

- [ ] Pack config exists and points to the correct Cambridge source PDFs and WMA files.
- [ ] Source files remain under `resources/` and are read-only inputs.
- [ ] Source data lives under `builder/source_data/<book-id>/<test-id>/listening/`.
- [ ] Public output lives under `public/packs/<book-id>/<test-id>/listening/`.
- [ ] Review output lives under `build/review/<book-id>/<test-id>/listening/`.
- [ ] Questions cover exactly `1..40`.
- [ ] Section ownership covers exactly four groups of ten questions.
- [ ] Page images are non-empty and visually correspond to the declared pages.
- [ ] Overlays have deterministic and visual confidence \(\ge 0.85\).
- [ ] Answers come from the official answer key or user-confirmed review entries.
- [ ] Transcript sections cover all four sections and reference answer-bearing segments.
- [ ] Four MP3 section files exist and pass duration checks.
- [ ] Vocabulary covers all single blank canonical answer terms.
- [ ] Vocabulary audio clips exist and pass duration checks.
- [ ] Intensive listening candidates are section-scoped and builder-validated.
- [ ] Transcript timing asset is either preview-valid or verified with release audit.
- [ ] Manifest status is `released`.
- [ ] Frontend state keys are isolated by `packId`.
- [ ] Browser acceptance proves the chosen pack and records which `packId` was exercised.

## Rollout Order

1. Resolve `Chapter-Split Source PDF` inputs for the prompted book with Task 0.
2. Parameterize Test 1 while preserving its released behavior.
3. Move Test 1 source data into the per-pack directory.
4. For the prompted target pack, create `<pack-config-path>` from the prompt input contract.
5. Build the prompted target pack through Python, builder, frontend, and browser gates.
6. Add the prompted target pack to the frontend catalog after its manifest is released.
7. Repeat the same prompt-driven flow for the next supplied book/test pair.
8. Run one final multi-pack browser pass that starts from the home screen, opens each released pack, enters at least one answer, switches sections, submits, and returns home.

## Self-Review

- Spec coverage: this plan covers split-PDF preflight, Test 1 abstraction, builder parameterization, per-pack source data, public output, review artifacts, frontend pack loading, local state isolation, derived learning assets, timing preview, and final verification.
- Placeholder scan: the remaining placeholders are intentional execution parameters defined in the Prompt Input Contract.
- Type consistency: `packId`, `packRoot`, `sourceDataRoot`, `reviewRoot`, `Listening Practice Pack`, `Listening Section`, and `Core Exam Pack` match the existing project language in `CONTEXT.md`.
