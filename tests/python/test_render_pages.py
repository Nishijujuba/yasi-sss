import uuid
from pathlib import Path

from PIL import Image

from builder.config import QUESTION_PDF
from builder.render_pages import render_question_pages


def unique_test_dir(name: str) -> Path:
    path = Path("tmp") / "test-runs" / f"{name}-{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    return path


def test_render_question_pages_uses_stable_names_and_dimensions():
    output_dir = unique_test_dir("render-pages")
    results = render_question_pages(
        source_pdf=QUESTION_PDF,
        output_dir=output_dir,
        dpi=150,
    )

    assert [item.output.name for item in results] == [
        "page-010.png",
        "page-011.png",
        "page-012.png",
        "page-013.png",
        "page-014.png",
        "page-015.png",
        "page-016.png",
    ]
    for item in results:
        assert 1000 <= item.width <= 1100
        assert 1400 <= item.height <= 1500
        assert item.sha256
        with Image.open(item.output) as image:
            assert image.mode in {"RGB", "RGBA"}
            assert image.getbbox() is not None


def test_render_question_pages_rejects_missing_source():
    output_dir = unique_test_dir("missing-source")
    missing = output_dir / "missing.pdf"

    try:
        render_question_pages(missing, output_dir / "out")
    except FileNotFoundError as exc:
        assert str(missing) in str(exc)
    else:
        raise AssertionError("missing source PDF must fail")
