from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from builder.config import (
    PAGE_ASSET_ROOT,
    PDFTOPPM,
    QUESTION_PAGE_NUMBERS,
    QUESTION_PDF,
)


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


def render_question_pages(
    source_pdf: Path = QUESTION_PDF,
    output_dir: Path = PAGE_ASSET_ROOT,
    dpi: int = 150,
) -> list[RenderedPage]:
    source_pdf = Path(source_pdf)
    output_dir = Path(output_dir)
    if not source_pdf.is_file():
        raise FileNotFoundError(f"question source PDF does not exist: {source_pdf}")
    if not PDFTOPPM.is_file():
        raise FileNotFoundError(f"pdftoppm does not exist: {PDFTOPPM}")

    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[RenderedPage] = []
    for pdf_page, source_page in enumerate(QUESTION_PAGE_NUMBERS, start=1):
        target = output_dir / f"page-{source_page:03d}.png"
        if not target.exists():
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
                str(target.with_suffix("")),
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
