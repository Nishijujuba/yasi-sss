from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

from builder.config import (
    PAGE_ASSET_ROOT,
    PDFTOPPM,
    QUESTION_PAGE_NUMBERS,
    QUESTION_PDF,
)


PAGE_CROP_HEIGHTS = {
    11: 800,
    12: 560,
    13: 880,
    14: 1120,
    15: 690,
    34: 430,
    35: 940,
    36: 1180,
    37: 870,
    38: 1200,
    40: 430,
}

WATERMARK_RECT = (680, 0, 1100, 130)


@dataclass(frozen=True)
class RenderedPage:
    source_page: int
    output: Path
    width: int
    height: int
    sha256: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _render_raw_page(
    *,
    source_pdf: Path,
    output_dir: Path,
    pdf_page: int,
    source_page: int,
    dpi: int,
    source_digest: str,
) -> Path:
    raw_target = output_dir / f".render-{source_digest[:32]}-{source_page:03d}.png"
    if raw_target.exists():
        return raw_target

    command = [
        str(PDFTOPPM),
        "-f",
        str(pdf_page),
        "-l",
        str(pdf_page),
        "-singlefile",
        "-png",
        "-r",
        str(dpi),
        str(source_pdf),
        str(raw_target.with_suffix("")),
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"question page {source_page} rendering failed: "
            f"{completed.stderr.strip() or completed.stdout.strip()}"
        )
    if not raw_target.is_file():
        raise RuntimeError(f"question page raw render is missing: {raw_target}")
    return raw_target


def _clean_question_page(image: Image.Image, *, source_page: int) -> Image.Image:
    cleaned = image.convert("RGB")
    draw = ImageDraw.Draw(cleaned)
    left, top, right, bottom = WATERMARK_RECT
    draw.rectangle(
        (
            max(0, left),
            max(0, top),
            min(cleaned.width, right),
            min(cleaned.height, bottom),
        ),
        fill=(255, 255, 255),
    )

    crop_height = PAGE_CROP_HEIGHTS.get(source_page)
    if crop_height is not None:
        cleaned = cleaned.crop((0, 0, cleaned.width, min(cleaned.height, crop_height)))
    return cleaned


def render_question_pages(
    source_pdf: Path = QUESTION_PDF,
    output_dir: Path = PAGE_ASSET_ROOT,
    dpi: int = 150,
    source_page_numbers: tuple[int, ...] = QUESTION_PAGE_NUMBERS,
) -> list[RenderedPage]:
    source_pdf = Path(source_pdf)
    output_dir = Path(output_dir)
    if not source_pdf.is_file():
        raise FileNotFoundError(f"question source PDF does not exist: {source_pdf}")
    if not PDFTOPPM.is_file():
        raise FileNotFoundError(f"pdftoppm does not exist: {PDFTOPPM}")

    output_dir.mkdir(parents=True, exist_ok=True)
    source_digest = _sha256(source_pdf)
    results: list[RenderedPage] = []
    for pdf_page, source_page in enumerate(source_page_numbers, start=1):
        target = output_dir / f"page-{source_page:03d}.png"
        raw_target = _render_raw_page(
            source_pdf=source_pdf,
            output_dir=output_dir,
            pdf_page=pdf_page,
            source_page=source_page,
            dpi=dpi,
            source_digest=source_digest,
        )
        with Image.open(raw_target) as raw_image:
            cleaned = _clean_question_page(raw_image, source_page=source_page)
            cleaned.save(target)
        if not target.is_file():
            raise RuntimeError(f"question page render is missing: {target}")
        with Image.open(target) as image:
            width, height = image.size
        results.append(
            RenderedPage(
                source_page=source_page,
                output=target,
                width=width,
                height=height,
                sha256=_sha256(target),
            )
        )
    return results


def main() -> None:
    for page in render_question_pages():
        print(
            f"{page.output.name}: {page.width}x{page.height} "
            f"sha256={page.sha256}"
        )


if __name__ == "__main__":
    main()
