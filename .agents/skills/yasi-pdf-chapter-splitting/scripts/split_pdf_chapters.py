#!/usr/bin/env python3
"""Split a source PDF into chapter PDFs from a validated manifest."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter


SCHEMA_VERSION = "yasi.pdf-chapter-split.v1"


@dataclass(frozen=True)
class Chapter:
    order: int
    title: str
    file_stem: str
    start_page: int
    end_page: int

    @property
    def page_count(self) -> int:
        return self.end_page - self.start_page + 1

    @property
    def filename(self) -> str:
        return f"{self.file_stem}_p{self.start_page:03d}-p{self.end_page:03d}.pdf"


def configure_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Manifest root must be a JSON object.")
    return data


def resolve_path(raw: str, manifest_path: Path) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return (manifest_path.parent / path).resolve()


def require_int(value: Any, field: str) -> int:
    if not isinstance(value, int):
        raise ValueError(f"{field} must be an integer.")
    return value


def parse_chapters(data: dict[str, Any]) -> list[Chapter]:
    raw_chapters = data.get("chapters")
    if not isinstance(raw_chapters, list) or not raw_chapters:
        raise ValueError("chapters must be a non-empty array.")

    chapters: list[Chapter] = []
    for index, item in enumerate(raw_chapters):
        if not isinstance(item, dict):
            raise ValueError(f"chapters[{index}] must be an object.")
        order = require_int(item.get("order"), f"chapters[{index}].order")
        title = item.get("title")
        file_stem = item.get("fileStem")
        start_page = require_int(item.get("startPage"), f"chapters[{index}].startPage")
        end_page = require_int(item.get("endPage"), f"chapters[{index}].endPage")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"chapters[{index}].title must be a non-empty string.")
        if not isinstance(file_stem, str) or not file_stem.strip():
            raise ValueError(f"chapters[{index}].fileStem must be a non-empty string.")
        if any(sep in file_stem for sep in ("/", "\\")):
            raise ValueError(f"chapters[{index}].fileStem must be a filename stem, not a path.")
        if start_page < 1 or end_page < start_page:
            raise ValueError(f"chapters[{index}] has an invalid page interval.")
        chapters.append(Chapter(order, title.strip(), file_stem.strip(), start_page, end_page))

    expected_orders = list(range(len(chapters)))
    actual_orders = [chapter.order for chapter in chapters]
    if actual_orders != expected_orders:
        raise ValueError(f"chapter order must be contiguous from 0: got {actual_orders}.")
    return chapters


def validate_manifest(data: dict[str, Any], manifest_path: Path) -> tuple[Path, Path, int, str, list[Chapter]]:
    if data.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError(f"schemaVersion must be {SCHEMA_VERSION}.")
    if data.get("pageNumberBasis") != "pdf-physical-1-based":
        raise ValueError("pageNumberBasis must be pdf-physical-1-based.")
    coverage = data.get("coverage", "complete")
    if coverage not in {"complete", "listed-only"}:
        raise ValueError("coverage must be complete or listed-only.")
    source_pdf = data.get("sourcePdf")
    output_dir = data.get("outputDir")
    if not isinstance(source_pdf, str) or not source_pdf.strip():
        raise ValueError("sourcePdf must be a non-empty string.")
    if not isinstance(output_dir, str) or not output_dir.strip():
        raise ValueError("outputDir must be a non-empty string.")
    expected_total_pages = require_int(data.get("expectedTotalPages"), "expectedTotalPages")
    if expected_total_pages < 1:
        raise ValueError("expectedTotalPages must be positive.")
    chapters = parse_chapters(data)
    return (
        resolve_path(source_pdf, manifest_path),
        resolve_path(output_dir, manifest_path),
        expected_total_pages,
        coverage,
        chapters,
    )


def validate_ledger(chapters: list[Chapter], total_pages: int, coverage: str) -> None:
    used: dict[int, str] = {}
    for chapter in chapters:
        if chapter.end_page > total_pages:
            raise ValueError(f"{chapter.filename} ends after source page count {total_pages}.")
        for page in range(chapter.start_page, chapter.end_page + 1):
            prior = used.get(page)
            if prior is not None:
                raise ValueError(f"page {page} appears in both {prior} and {chapter.filename}.")
            used[page] = chapter.filename

    if coverage == "complete":
        missing = [page for page in range(1, total_pages + 1) if page not in used]
        if missing:
            preview = ", ".join(str(page) for page in missing[:20])
            raise ValueError(f"complete coverage requires every page; missing: {preview}")


def move_existing_to_trash(path: Path, trash_dir: Path) -> None:
    if not path.exists():
        return
    trash_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    target = trash_dir / f"{stamp}_{path.name}"
    counter = 1
    while target.exists():
        target = trash_dir / f"{stamp}_{counter}_{path.name}"
        counter += 1
    shutil.move(str(path), str(target))


def split_pdf(reader: PdfReader, chapters: list[Chapter], output_dir: Path, trash_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    for chapter in chapters:
        writer = PdfWriter()
        for page_index in range(chapter.start_page - 1, chapter.end_page):
            writer.add_page(reader.pages[page_index])
        target = output_dir / chapter.filename
        move_existing_to_trash(target, trash_dir)
        with target.open("wb") as handle:
            writer.write(handle)
        created.append(target)
    return created


def verify_outputs(created: list[Path], chapters: list[Chapter]) -> int:
    total = 0
    for path, chapter in zip(created, chapters):
        actual_pages = len(PdfReader(str(path)).pages)
        total += actual_pages
        status = "OK" if actual_pages == chapter.page_count else "BAD"
        print(f"{status}\t{path.name}\texpected={chapter.page_count}\tactual={actual_pages}")
        if actual_pages != chapter.page_count:
            raise RuntimeError(f"{path.name} has {actual_pages} pages, expected {chapter.page_count}.")
    print(f"TOTAL_OUTPUT_PAGES\t{total}")
    return total


def render_first_pages(created: list[Path], render_dir: Path, pdftoppm: str | None) -> None:
    exe = pdftoppm or shutil.which("pdftoppm")
    if not exe:
        print("RENDER_SKIPPED\tpdftoppm not found")
        return
    render_dir.mkdir(parents=True, exist_ok=True)
    pngs: list[Path] = []
    for index, pdf_path in enumerate(created):
        prefix = render_dir / f"part{index:02d}_first"
        subprocess.run(
            [exe, "-png", "-f", "1", "-l", "1", "-singlefile", str(pdf_path), str(prefix)],
            check=True,
        )
        png = prefix.with_suffix(".png")
        pngs.append(png)
        print(f"RENDERED\t{png}")
    write_contact_sheet(pngs, render_dir / "contact_sheet.png")


def write_contact_sheet(pngs: list[Path], output: Path) -> None:
    try:
        from PIL import Image, ImageDraw, ImageStat
    except Exception as exc:
        print(f"CONTACT_SHEET_SKIPPED\t{exc}")
        return
    thumbs = []
    for png in pngs:
        image = Image.open(png).convert("RGB")
        stat = ImageStat.Stat(image)
        extrema = image.getextrema()[0]
        mean = round(sum(stat.mean) / 3, 2)
        if extrema[0] == extrema[1]:
            raise RuntimeError(f"{png} appears blank.")
        image.thumbnail((220, 300))
        thumbs.append((png.name, image.copy(), mean, extrema))

    width = 4 * 260
    height = ((len(thumbs) + 3) // 4) * 350
    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (name, image, mean, extrema) in enumerate(thumbs):
        x = (index % 4) * 260 + 20
        y = (index // 4) * 350 + 20
        draw.text((x, y), f"{name} mean={mean} range={extrema}", fill=(0, 0, 0))
        sheet.paste(image, (x, y + 25))
    sheet.save(output)
    print(f"CONTACT_SHEET\t{output}")


def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--render-first-pages", action="store_true")
    parser.add_argument("--pdftoppm")
    parser.add_argument("--trash-dir", type=Path, default=Path.cwd() / "\u5f85\u5220\u9664")
    parser.add_argument("--render-dir", type=Path)
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    data = load_manifest(manifest_path)
    source_pdf, output_dir, expected_total_pages, coverage, chapters = validate_manifest(data, manifest_path)

    if not source_pdf.exists():
        raise FileNotFoundError(source_pdf)
    reader = PdfReader(str(source_pdf))
    total_pages = len(reader.pages)
    print(f"SOURCE_PDF\t{source_pdf}")
    print(f"OUTPUT_DIR\t{output_dir}")
    print(f"SOURCE_PAGES\t{total_pages}")
    if total_pages != expected_total_pages:
        raise RuntimeError(f"source has {total_pages} pages; manifest expected {expected_total_pages}.")
    validate_ledger(chapters, total_pages, coverage)
    for chapter in chapters:
        print(f"LEDGER\t{chapter.order}\t{chapter.filename}\t{chapter.start_page}-{chapter.end_page}\t{chapter.page_count}")
    print("LEDGER_OK\ttrue")

    if args.dry_run:
        print("DRY_RUN\ttrue")
        return 0

    created = split_pdf(reader, chapters, output_dir, args.trash_dir)
    total_output = verify_outputs(created, chapters)
    if coverage == "complete" and total_output != total_pages:
        raise RuntimeError(f"output total {total_output} does not match source total {total_pages}.")

    if args.render_first_pages:
        render_dir = args.render_dir or (
            Path.cwd() / "tmp" / "pdf_chapter_split_checks" / dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        render_first_pages(created, render_dir, args.pdftoppm)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
