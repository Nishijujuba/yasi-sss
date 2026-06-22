# PDF Chapter Split Manifest

Use one UTF-8 JSON manifest per source PDF. The manifest is the page ledger for a split run.

## Schema

```json
{
  "schemaVersion": "yasi.pdf-chapter-split.v1",
  "sourcePdf": "resources/剑桥/剑桥雅思10/剑桥雅思真题10.pdf",
  "outputDir": "resources/剑桥/剑桥雅思10/剑桥雅思真题10分P",
  "expectedTotalPages": 180,
  "coverage": "complete",
  "pageNumberBasis": "pdf-physical-1-based",
  "chapters": [
    {
      "order": 0,
      "title": "封面版权目录",
      "fileStem": "00_封面版权目录",
      "startPage": 1,
      "endPage": 3
    }
  ]
}
```

## Fields

- `schemaVersion`: must be `yasi.pdf-chapter-split.v1`.
- `sourcePdf`: absolute path, or a path relative to the manifest file. Use UTF-8 JSON for Chinese names.
- `outputDir`: absolute path, or a path relative to the manifest file.
- `expectedTotalPages`: required source page count. The script rejects mismatches.
- `coverage`: `complete` or `listed-only`. Use `complete` for Cambridge books unless the user explicitly requests a partial extract.
- `pageNumberBasis`: must be `pdf-physical-1-based`; printed book page numbers are evidence, while physical PDF page numbers drive splitting.
- `chapters[]`: ordered page intervals, one-based and inclusive.
- `chapters[].fileStem`: filename stem only. It must contain no path separators; the script appends `_pXXX-pYYY.pdf`.

## Multi-Book Rules

Create a new manifest for each source PDF. Keep book-specific data in the manifest and keep reusable behavior in the script:

- Cambridge 10: one manifest for `剑桥雅思真题10.pdf`.
- Cambridge 11 A: a separate manifest for `剑桥雅思真题11A.pdf`.
- Answer-key-only or audioscript-only PDFs: separate manifests if they are independent source PDFs.

For a complete ledger, every physical source page must appear exactly once. Front matter and trailing acknowledgements count as chapters even when the printed table of contents omits them. The check is like reconciling bank transactions: an omitted page is an unexplained transaction, and an overlapping page is double-counting.

## Evidence Rules

Use these evidence levels in order:

1. PDF total page count from `pypdf`.
2. Rendered first pages for each chapter start.
3. Table-of-contents screenshot or printed page list.
4. `pdfplumber` extracted text as weak evidence.

OCR or extracted text may be garbled on scanned IELTS PDFs. Treat it as a clue, then verify by rendering.
