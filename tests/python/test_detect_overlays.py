from pathlib import Path

import pytest
from PIL import Image

from builder.detect_overlays import (
    DetectionError,
    build_overlay_proposals,
    detect_blank_regions,
    detect_choice_regions,
    load_source_questions,
    material_overlap,
)
from builder.models import validate_questions
from builder.models import Rect
from builder.overlay_review import merge_vision_evidence


PAGE_ROOT = Path(
    "public/packs/cambridge-10/test-1/listening/assets/pages"
)


@pytest.mark.parametrize(
    ("page_name", "expected_count", "skip_leading"),
    [
        ("page-010.png", 6, 1),
        ("page-011.png", 4, 0),
        ("page-013.png", 8, 0),
        ("page-015.png", 5, 0),
        ("page-016.png", 10, 0),
    ],
)
def test_detects_all_official_blank_regions(
    page_name: str,
    expected_count: int,
    skip_leading: int,
):
    with Image.open(PAGE_ROOT / page_name) as image:
        regions = detect_blank_regions(
            image,
            expected_count=expected_count,
            skip_leading=skip_leading,
        )

    assert len(regions) == expected_count
    assert [region.pixel.y for region in regions] == sorted(
        region.pixel.y for region in regions
    )
    assert all(region.deterministic_confidence >= 0.85 for region in regions)


def test_page_011_q8_region_tracks_answer_line_below_one():
    with Image.open(PAGE_ROOT / "page-011.png") as image:
        regions = detect_blank_regions(image, expected_count=4)

    q8 = regions[1]
    assert q8.pixel.y <= 510
    assert q8.pixel.y + q8.pixel.h >= 525


def test_page_013_q18_region_tracks_answer_line_before_hours():
    with Image.open(PAGE_ROOT / "page-013.png") as image:
        regions = detect_blank_regions(image, expected_count=8)

    q18 = regions[5]
    assert q18.pixel.x >= 520
    assert q18.pixel.y <= 682
    assert q18.pixel.y + q18.pixel.h >= 698


def test_detects_five_multi_choice_rows():
    with Image.open(PAGE_ROOT / "page-012.png") as image:
        regions = detect_choice_regions(
            image,
            crop=(140, 330, 700, 500),
            group_count=1,
            options_per_group=5,
        )

    assert len(regions) == 5


def test_detects_five_single_choice_groups():
    with Image.open(PAGE_ROOT / "page-014.png") as image:
        regions = detect_choice_regions(
            image,
            crop=(150, 340, 950, 1050),
            group_count=5,
            options_per_group=3,
        )

    assert len(regions) == 15


def test_rejects_missing_expected_blank_region():
    image = Image.new("RGB", (300, 200), "white")

    with pytest.raises(DetectionError, match="expected 1.*found 0"):
        detect_blank_regions(image, expected_count=1)


def test_flags_material_overlap():
    first = Rect(x=10, y=10, w=100, h=20)
    second = Rect(x=50, y=10, w=100, h=20)

    assert material_overlap(first, second, threshold=0.15)


def test_source_questions_cover_all_official_questions():
    questions = load_source_questions()

    validate_questions(questions)
    assert [question.focusOrder for question in questions] == list(range(1, 41))
    assert questions[10].id == "q11"
    assert questions[10].responseType == "multi-choice"
    assert questions[10].selectionLimit == 2
    assert [option.id for option in questions[10].options] == ["A", "B", "C", "D", "E"]
    assert questions[11].id == "q12"
    assert questions[11].responseType == "multi-choice"


def test_build_overlay_proposals_for_all_interactive_regions():
    proposals = build_overlay_proposals()

    assert len(proposals) == 53
    assert {proposal["questionId"] for proposal in proposals} >= {
        "q1",
        "q11",
        "q21",
        "q40",
    }
    assert "q12" not in {proposal["questionId"] for proposal in proposals}
    assert all(proposal["deterministicConfidence"] >= 0.85 for proposal in proposals)
    for proposal in proposals:
        normalized = proposal["normalized"]
        assert 0 <= normalized["x"] <= 1
        assert 0 <= normalized["y"] <= 1
        assert normalized["x"] + normalized["w"] <= 1
        assert normalized["y"] + normalized["h"] <= 1


def test_merge_vision_evidence_requires_approved_confidence():
    proposal = {
        "questionId": "q1",
        "optionId": None,
        "page": "page-010.png",
        "interactionType": "blank",
        "pixel": {"x": 10, "y": 20, "w": 100, "h": 30},
        "normalized": {"x": 0.01, "y": 0.02, "w": 0.1, "h": 0.03},
        "deterministicConfidence": 0.92,
        "validationEvidence": ["detected dotted line"],
    }

    overlays = merge_vision_evidence(
        [proposal],
        [
            {
                "questionId": "q1",
                "optionId": None,
                "status": "approved",
                "confidence": 0.96,
                "evidence": "review box is aligned",
            }
        ],
    )

    assert overlays[0].confidence == 0.92

    with pytest.raises(DetectionError, match="vision"):
        merge_vision_evidence(
            [proposal],
            [
                {
                    "questionId": "q1",
                    "optionId": None,
                    "status": "approved",
                    "confidence": 0.80,
                    "evidence": "too uncertain",
                }
            ],
        )

    with pytest.raises(DetectionError, match="missing vision evidence"):
        merge_vision_evidence([proposal], [])

    with pytest.raises(DetectionError, match="vision evidence rejected"):
        merge_vision_evidence(
            [proposal],
            [
                {
                    "questionId": "q1",
                    "optionId": None,
                    "status": "rejected",
                    "confidence": 0.99,
                    "evidence": "box is wrong",
                }
            ],
        )
