---
name: yasi-pdf-chapter-splitting
description: Use when splitting Yasi IELTS source PDFs, Cambridge IELTS books, answer-key PDFs, audioscript PDFs, or scanned workbook PDFs into chapter or test-section PDF files from a verified page-range manifest, especially when processing multiple books or tests under D:\Project\yasi\resources.
---

# Yasi PDF Chapter Splitting

## Overview

Use this skill to split one source PDF into stable chapter PDFs while preserving every original page. The source of truth is a UTF-8 JSON manifest with physical PDF page ranges; OCR text, bookmarks, and screenshots are evidence only.

The leading word is **ledger**: each page in the source PDF must be accounted for once unless the manifest explicitly allows gaps. For a complete split with \(N\) source pages and chapter intervals \([s_i,e_i]\), the ledger check is:

\[
\bigcup_i [s_i,e_i] = [1,N] \land [s_i,e_i] \cap [s_j,e_j] = \varnothing \quad (i \ne j)
\]

## Workflow

1. Locate the source PDF and requested output directory. Treat the user-provided table of contents, screenshot, or prior split as a draft ledger.
2. Read `references/manifest-schema.md` before writing or editing a manifest.
3. Build a manifest with one-based, inclusive physical PDF pages. Include a front-matter chapter for cover, copyright, or table-of-contents pages outside the printed contents list.
4. Validate page starts against direct evidence before splitting. Prefer PDF page count plus rendered page checks; use `pdfplumber` text extraction only as weak evidence because scanned Cambridge books often extract `(cid:...)` text.
5. Run `scripts/split_pdf_chapters.py --manifest <manifest.json> --dry-run` until the ledger is clean.
6. Run the split command. Existing output files are moved into the repo-root `待删除` folder by the script before replacement.
7. Verify results: every chapter page count matches the manifest, total output pages match the source page count for complete ledgers, and rendered first pages are nonblank and visually aligned with chapter starts.

## Commands

Dry-run validation:

```powershell
$env:PYTHONUTF8='1'
D:\Project\yasi\.venv\Scripts\python.exe .agents\skills\yasi-pdf-chapter-splitting\scripts\split_pdf_chapters.py --manifest <manifest.json> --dry-run
```

Split and render first-page checks:

```powershell
$env:PYTHONUTF8='1'
D:\Project\yasi\.venv\Scripts\python.exe .agents\skills\yasi-pdf-chapter-splitting\scripts\split_pdf_chapters.py --manifest <manifest.json> --render-first-pages
```

Validate the skill package on Windows:

```powershell
D:\Project\yasi\.venv\Scripts\python.exe -X utf8 C:\Users\juju\.codex\skills\.system\skill-creator\scripts\quick_validate.py D:\Project\yasi\.agents\skills\yasi-pdf-chapter-splitting
```

If project Python lacks `pypdf` or `Pillow`, use the Codex bundled workspace Python after loading workspace dependencies. Keep the manifest UTF-8 and prefer forward slashes or escaped Unicode paths for Chinese filenames when embedding paths in shell one-liners.

## Resources

- `scripts/split_pdf_chapters.py`: manifest-driven splitter, page ledger validator, output page-count verifier, optional first-page renderer.
- `references/manifest-schema.md`: manifest contract and multi-book rules.
- `fixtures/cambridge-10-chapter-split.json`: Cambridge IELTS 10 example based on the 2026-06-15 verified split.

## Boundaries

- Never hardcode Cambridge 10 page ranges into the script or this `SKILL.md`.
- Never delete old outputs; move replacements to `待删除`.
- Never trust PDF bookmarks alone. Scanned source PDFs may contain only `Scan0001`-style bookmarks.
- Never release a split from OCR evidence alone. A page ledger plus page-count verification is the minimum gate; rendered first-page inspection is the visual gate.
