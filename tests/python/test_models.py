import pytest
from pydantic import ValidationError

from builder.models import (
    Overlay,
    Rect,
    ReleasedManifest,
    validate_question_coverage,
)


def minimal_manifest(status: str = "released") -> dict:
    return {
        "packId": "cambridge-10-test-1-listening",
        "schemaVersion": 1,
        "status": status,
        "title": "Cambridge IELTS 10 Test 1 Listening",
        "sections": [
            {
                "number": section,
                "title": f"Listening Section {section:02d}",
                "questionNumbers": list(range((section - 1) * 10 + 1, section * 10 + 1)),
                "audio": f"assets/audio/section-{section:02d}.mp3",
                "pages": [f"assets/pages/page-0{9 + section}.png"],
            }
            for section in range(1, 5)
        ],
        "assets": {
            "questions": "questions.json",
            "answers": "answers.json",
            "overlays": "overlays.json",
            "transcript": "transcript.json",
        },
        "build": {"sourceCommit": "test", "builtAt": "2026-06-15T00:00:00Z"},
    }


def test_manifest_rejects_non_released_status_for_runtime():
    with pytest.raises(ValidationError):
        ReleasedManifest.model_validate(minimal_manifest(status="building"))


def test_overlay_rejects_confidence_below_gate():
    payload = {
        "questionId": "q1",
        "optionId": None,
        "page": "page-010.png",
        "interactionType": "blank",
        "pixel": {"x": 10, "y": 20, "w": 100, "h": 30},
        "normalized": {"x": 0.01, "y": 0.02, "w": 0.1, "h": 0.03},
        "deterministicConfidence": 0.95,
        "visionConfidence": 0.849,
        "confidence": 0.849,
        "validationEvidence": ["synthetic"],
    }
    with pytest.raises(ValidationError):
        Overlay.model_validate(payload)


def test_rect_rejects_normalized_coordinate_outside_page():
    with pytest.raises(ValidationError):
        Rect(x=0.9, y=0.1, w=0.2, h=0.1, normalized=True)


def test_question_coverage_must_be_exactly_one_to_forty():
    with pytest.raises(ValueError, match="1 through 40"):
        validate_question_coverage(list(range(1, 40)))
