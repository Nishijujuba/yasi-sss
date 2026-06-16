from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from builder.models import PendingAnswerCandidate
from builder.validate_pack import (
    ReleaseBlocked,
    covered_numbers,
    export_answers_and_transcript,
    load_source_answers,
    load_source_transcript,
    validate_answer_authority,
    validate_transcript_sections,
)


def unique_test_dir(name: str) -> Path:
    path = Path("tmp") / "test-runs" / f"{name}-{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    return path


def test_all_answers_have_official_provenance():
    answers = load_source_answers()

    assert covered_numbers(answers) == set(range(1, 41))
    assert all(answer.reviewStatus in {"official", "user-confirmed"} for answer in answers)
    assert all(answer.provenance for answer in answers)


def test_unapproved_answer_candidate_blocks_release():
    candidate = PendingAnswerCandidate(
        questionNumber=1,
        status="pending",
        candidate="Ardleigh",
        sourceUrl="https://example.invalid",
        accessedAt="2026-06-15T00:00:00Z",
        questionCrop="q1.png",
        answerKeyCrop="answer-key.png",
        transcriptEvidence="",
    )

    with pytest.raises(ReleaseBlocked, match="user approval"):
        validate_answer_authority([candidate])


def test_transcript_has_all_four_sections_and_reserved_timing_fields():
    transcript = load_source_transcript()

    assert {section.section for section in transcript} == {1, 2, 3, 4}
    for section in transcript:
        for segment in section.segments:
            assert segment.startTime is None
            assert segment.endTime is None


def test_transcript_answer_refs_cover_official_answers():
    answers = load_source_answers()
    transcript = load_source_transcript()

    validate_transcript_sections(transcript, answers)


def test_export_answers_and_transcript_writes_public_pack():
    output_root = unique_test_dir("answers-transcript-pack")
    export_answers_and_transcript(output_root=output_root)

    answers = json.loads((output_root / "answers.json").read_text(encoding="utf-8"))
    transcript = json.loads((output_root / "transcript.json").read_text(encoding="utf-8"))

    assert len(answers) == 39
    assert {section["section"] for section in transcript} == {1, 2, 3, 4}
