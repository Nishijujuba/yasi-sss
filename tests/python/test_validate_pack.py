from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import pytest

from builder.build_pack import build_pack
from builder.config import PACK_ROOT, REVIEW_ROOT
from builder.models import PendingAnswerCandidate
from builder.validate_pack import (
    ReleaseBlocked,
    covered_numbers,
    export_answers_and_transcript,
    load_source_answers,
    load_source_transcript,
    validate_answer_authority,
    validate_pack,
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


def test_build_pack_writes_released_manifest_and_report():
    report = build_pack()

    manifest = json.loads((PACK_ROOT / "manifest.json").read_text(encoding="utf-8"))
    release_report = json.loads(
        (REVIEW_ROOT / "release-report.json").read_text(encoding="utf-8")
    )

    assert report.status == "released"
    assert manifest["status"] == "released"
    assert release_report["questionCoverage"] == list(range(1, 41))
    assert release_report["overlayCount"] == 53
    assert release_report["answerCount"] == 40


def test_release_requires_all_assets():
    build_pack()
    pack_copy = unique_test_dir("pack-copy") / "listening"
    shutil.copytree(PACK_ROOT, pack_copy)
    manifest_path = pack_copy / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["sections"][3]["audio"] = "assets/audio/missing-section-04.mp3"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ReleaseBlocked, match="missing-section-04.mp3"):
        validate_pack(pack_copy)


def test_release_requires_vision_and_final_confidence_gate():
    build_pack()
    pack_copy = unique_test_dir("pack-low-confidence") / "listening"
    shutil.copytree(PACK_ROOT, pack_copy)
    overlays_path = pack_copy / "overlays.json"
    overlays = json.loads(overlays_path.read_text(encoding="utf-8"))
    overlays[0]["visionConfidence"] = 0.80
    overlays_path.write_text(json.dumps(overlays, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ReleaseBlocked, match="0.85"):
        validate_pack(pack_copy)
