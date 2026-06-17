import pytest
from pydantic import ValidationError

import builder.models as model_module
from builder.models import (
    Answer,
    ChoiceOption,
    NormalizedRect,
    Overlay,
    Question,
    Rect,
    ReleasedManifest,
    validate_answer_membership,
    validate_question_coverage,
    validate_questions,
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


def test_vocabulary_item_model_accepts_pack_shape_and_rejects_extra_fields():
    assert hasattr(model_module, "VocabularyItem")
    item = model_module.VocabularyItem.model_validate(
        {
            "id": "photo-card",
            "term": "photo card",
            "normalizedTerm": "photo card",
            "acceptedVariants": ["photo cards"],
            "meaningZh": "照片卡",
            "audio": "assets/audio/vocabulary/photo-card.mp3",
        }
    )

    assert item.term == "photo card"
    assert item.acceptedVariants == ["photo cards"]

    with pytest.raises(ValidationError):
        model_module.VocabularyItem.model_validate(
            {
                "id": "photo-card",
                "term": "photo card",
                "normalizedTerm": "photo card",
                "acceptedVariants": [],
                "meaningZh": "照片卡",
                "audio": "assets/audio/vocabulary/photo-card.mp3",
                "unexpected": True,
            }
        )


def test_answer_audio_window_model_requires_valid_positive_window():
    assert hasattr(model_module, "AnswerAudioWindow")
    window = model_module.AnswerAudioWindow.model_validate(
        {
            "vocabularyId": "photo-card",
            "questionId": "q1",
            "section": 1,
            "startTime": 35.2,
            "endTime": 36.4,
            "paddingBefore": 0.15,
            "paddingAfter": 0.25,
        }
    )

    assert window.vocabularyId == "photo-card"
    assert window.endTime > window.startTime

    with pytest.raises(ValidationError, match="endTime"):
        model_module.AnswerAudioWindow.model_validate(
            {
                "vocabularyId": "photo-card",
                "questionId": "q1",
                "section": 1,
                "startTime": 36.4,
                "endTime": 35.2,
                "paddingBefore": 0.15,
                "paddingAfter": 0.25,
            }
        )


def test_manifest_assets_requires_vocabulary_asset():
    payload = minimal_manifest()
    payload["assets"]["vocabulary"] = "vocabulary.json"

    manifest = ReleasedManifest.model_validate(payload)

    assert manifest.assets.vocabulary == "vocabulary.json"

    del payload["assets"]["vocabulary"]
    with pytest.raises(ValidationError):
        ReleasedManifest.model_validate(payload)


def test_release_report_requires_vocabulary_window_and_clip_counts():
    payload = {
        "status": "released",
        "questionCoverage": list(range(1, 41)),
        "overlayCount": 53,
        "answerCount": 40,
        "transcriptSections": [1, 2, 3, 4],
        "audioSections": [1, 2, 3, 4],
        "pageAssets": ["assets/pages/page-010.png"],
        "pendingAnswerCandidates": 0,
        "vocabularyCount": 33,
        "windowCount": 33,
        "clipCount": 33,
        "errors": [],
    }

    report = model_module.ReleaseReport.model_validate(payload)

    assert report.vocabularyCount == 33
    assert report.windowCount == 33
    assert report.clipCount == 33

    del payload["clipCount"]
    with pytest.raises(ValidationError):
        model_module.ReleaseReport.model_validate(payload)


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


def test_overlay_allows_lower_deterministic_confidence_when_combined_gate_passes():
    overlay = Overlay.model_validate(
        {
            "questionId": "q1",
            "optionId": None,
            "page": "page-010.png",
            "interactionType": "blank",
            "pixel": {"x": 10, "y": 20, "w": 100, "h": 30},
            "normalized": {"x": 0.01, "y": 0.02, "w": 0.1, "h": 0.03},
            "deterministicConfidence": 0.75,
            "visionConfidence": 0.95,
            "confidence": 0.90,
            "validationEvidence": ["synthetic"],
        }
    )

    assert overlay.deterministicConfidence == 0.75


def test_rect_rejects_normalized_coordinate_outside_page():
    with pytest.raises(ValidationError):
        NormalizedRect(x=0.9, y=0.1, w=0.2, h=0.1)


def test_question_coverage_must_be_exactly_one_to_forty():
    with pytest.raises(ValueError, match="1 through 40"):
        validate_question_coverage(list(range(1, 40)))


def make_question(number: int, *, section: int | None = None, focus: int | None = None):
    response_type = "single-choice" if 21 <= number <= 25 else "blank"
    return Question(
        id=f"q{number}",
        number=number,
        section=section or ((number - 1) // 10 + 1),
        responseType=response_type,
        page=f"page-{10 + min((number - 1) // 6, 6):03d}.png",
        focusOrder=focus or number,
        options=(
            [
                ChoiceOption(id="A", label="A"),
                ChoiceOption(id="B", label="B"),
                ChoiceOption(id="C", label="C"),
            ]
            if response_type == "single-choice"
            else []
        ),
    )


def test_question_collection_rejects_duplicate_focus_order():
    questions = [make_question(number) for number in range(1, 41)]
    questions[39] = make_question(40, focus=39)

    with pytest.raises(ValueError, match="focus order"):
        validate_questions(questions)


def test_question_collection_rejects_wrong_section_owner():
    questions = [make_question(number) for number in range(1, 41)]
    questions[20] = make_question(21, section=2)

    with pytest.raises(ValueError, match="section ownership"):
        validate_questions(questions)


def test_answer_membership_rejects_unknown_question_id():
    questions = [make_question(number) for number in range(1, 41)]
    answers = [
        Answer(
            questionIds=[f"q{number}"],
            accepted=[[f"answer-{number}"]],
            provenance=[
                {
                    "kind": "official-answer-key",
                    "source": "answer-key.pdf",
                    "page": 151,
                    "detail": "TEST 1 LISTENING",
                }
            ],
            reviewStatus="official",
        )
        for number in range(1, 41)
    ]
    answers[-1] = answers[-1].model_copy(update={"questionIds": ["q41"]})

    with pytest.raises(ValueError, match="answer membership"):
        validate_answer_membership(answers, questions)
