import uuid
from pathlib import Path

from PIL import Image

from builder.config import QUESTION_PDF, TEST2_PDF
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
    heights = {item.output.name: item.height for item in results}
    assert heights["page-011.png"] <= 820
    assert heights["page-012.png"] <= 620
    assert heights["page-013.png"] <= 900
    assert heights["page-014.png"] <= 1120
    assert heights["page-015.png"] <= 720
    assert heights["page-010.png"] >= 1350
    assert heights["page-016.png"] >= 1200

    for item in results:
        assert 1000 <= item.width <= 1100
        assert 550 <= item.height <= 1500
        assert item.sha256
        with Image.open(item.output) as image:
            assert image.mode in {"RGB", "RGBA"}
            assert image.getbbox() is not None
            watermark_area = image.crop((680, 0, image.width, min(120, image.height))).convert("L")
            dark_pixels = sum(1 for pixel in watermark_area.getdata() if pixel < 180)
            assert dark_pixels < 150


def test_render_question_pages_rejects_missing_source():
    output_dir = unique_test_dir("missing-source")
    missing = output_dir / "missing.pdf"

    try:
        render_question_pages(missing, output_dir / "out")
    except FileNotFoundError as exc:
        assert str(missing) in str(exc)
    else:
        raise AssertionError("missing source PDF must fail")


def test_render_question_pages_accepts_custom_source_page_numbers():
    output_dir = unique_test_dir("render-test2-page")

    results = render_question_pages(
        source_pdf=TEST2_PDF,
        output_dir=output_dir,
        dpi=150,
        source_page_numbers=(33,),
    )

    assert [item.output.name for item in results] == ["page-033.png"]
    assert results[0].width >= 1000
    assert results[0].height >= 1000


def test_render_question_pages_crops_test2_half_pages_without_cutting_questions():
    output_dir = unique_test_dir("render-test2-cropped-pages")

    results = render_question_pages(
        source_pdf=TEST2_PDF,
        output_dir=output_dir,
        dpi=150,
        source_page_numbers=(34, 35, 36, 37, 38, 40),
    )

    heights = {item.output.name: item.height for item in results}
    assert heights == {
        "page-034.png": 430,
        "page-035.png": 940,
        "page-036.png": 1180,
        "page-037.png": 870,
        "page-038.png": 1200,
        "page-040.png": 430,
    }

    for item in results:
        with Image.open(item.output) as image:
            watermark_area = image.crop((680, 0, image.width, min(120, image.height))).convert("L")
            dark_pixels = sum(1 for pixel in watermark_area.getdata() if pixel < 180)
            assert dark_pixels < 150
