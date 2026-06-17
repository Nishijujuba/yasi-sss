from __future__ import annotations

import json
import re
import shutil
import uuid
from pathlib import Path

import pytest

import builder.validate_pack as validate_pack_module
from builder.build_pack import build_pack
from builder.config import PACK_ROOT, REVIEW_ROOT, SOURCE_DATA_ROOT
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


VOCABULARY_COUNT = 33


def unique_test_dir(name: str) -> Path:
    path = Path("tmp") / "test-runs" / f"{name}-{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    return path


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _slug(term: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-")
    return slug or "term"


def _canonical_blank_records() -> list[dict]:
    questions_payload = json.loads(
        (SOURCE_DATA_ROOT / "questions.json").read_text(encoding="utf-8")
    )
    answers_payload = json.loads(
        (SOURCE_DATA_ROOT / "answers.json").read_text(encoding="utf-8")
    )
    questions_by_id = {question["id"]: question for question in questions_payload}
    records = []

    for answer in answers_payload:
        if len(answer["questionIds"]) != 1:
            continue
        question_id = answer["questionIds"][0]
        question = questions_by_id[question_id]
        if question["responseType"] != "blank":
            continue

        term = answer["accepted"][0][0]
        records.append(
            {
                "id": _slug(term),
                "term": term,
                "normalizedTerm": term.lower(),
                "acceptedVariants": [
                    accepted_group[0]
                    for accepted_group in answer["accepted"][1:]
                    if accepted_group
                ],
                "questionId": question_id,
                "section": question["section"],
            }
        )

    assert len(records) == VOCABULARY_COUNT
    return records


def _copy_pack_with_vocabulary(monkeypatch, name: str) -> tuple[Path, Path, list[dict], list[dict]]:
    pack_copy = unique_test_dir(name) / "listening"
    shutil.copytree(PACK_ROOT, pack_copy)

    manifest_path = pack_copy / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["assets"]["vocabulary"] = "vocabulary.json"
    _write_json(manifest_path, manifest)

    records = _canonical_blank_records()
    vocabulary = []
    windows = []
    clip_dir = pack_copy / "assets" / "audio" / "vocabulary"
    clip_dir.mkdir(parents=True, exist_ok=True)

    for index, record in enumerate(records, start=1):
        clip_path = clip_dir / f"{record['id']}.mp3"
        clip_path.write_bytes(b"mp3")
        vocabulary.append(
            {
                "id": record["id"],
                "term": record["term"],
                "normalizedTerm": record["normalizedTerm"],
                "acceptedVariants": record["acceptedVariants"],
                "meaningZh": "释义",
                "audio": f"assets/audio/vocabulary/{record['id']}.mp3",
            }
        )
        windows.append(
            {
                "vocabularyId": record["id"],
                "questionId": record["questionId"],
                "section": record["section"],
                "startTime": float(index),
                "endTime": float(index) + 1.0,
                "paddingBefore": 0.05,
                "paddingAfter": 0.05,
            }
        )

    _write_json(pack_copy / "vocabulary.json", vocabulary)
    windows_path = pack_copy.parent / "answer-audio-windows.json"
    _write_json(windows_path, windows)

    def fake_probe_duration(media_path: Path, **kwargs) -> float:
        name = Path(media_path).name
        if name.startswith("section-"):
            return 300.0
        return 1.0

    monkeypatch.setattr(validate_pack_module, "probe_duration_seconds", fake_probe_duration)
    return pack_copy, windows_path, vocabulary, windows


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
    assert manifest["assets"]["vocabulary"] == "vocabulary.json"
    assert release_report["questionCoverage"] == list(range(1, 41))
    assert release_report["overlayCount"] == 53
    assert release_report["answerCount"] == 40
    assert release_report["vocabularyCount"] == VOCABULARY_COUNT
    assert release_report["windowCount"] == VOCABULARY_COUNT
    assert release_report["clipCount"] == VOCABULARY_COUNT


def test_validate_pack_reports_vocabulary_window_and_clip_counts(monkeypatch):
    pack_copy, windows_path, _, _ = _copy_pack_with_vocabulary(
        monkeypatch,
        "pack-vocabulary-counts",
    )

    report = validate_pack(pack_copy, answer_audio_windows_path=windows_path)

    assert report.vocabularyCount == VOCABULARY_COUNT
    assert report.windowCount == VOCABULARY_COUNT
    assert report.clipCount == VOCABULARY_COUNT


def test_release_requires_vocabulary_full_blank_canonical_coverage(monkeypatch):
    pack_copy, windows_path, vocabulary, _ = _copy_pack_with_vocabulary(
        monkeypatch,
        "pack-vocabulary-missing",
    )
    vocabulary.pop(0)
    _write_json(pack_copy / "vocabulary.json", vocabulary)

    with pytest.raises(ReleaseBlocked, match="vocabulary coverage"):
        validate_pack(pack_copy, answer_audio_windows_path=windows_path)


def test_release_rejects_extra_vocabulary_item(monkeypatch):
    pack_copy, windows_path, vocabulary, windows = _copy_pack_with_vocabulary(
        monkeypatch,
        "pack-vocabulary-extra",
    )
    vocabulary.append(
        {
            "id": "extra",
            "term": "extra",
            "normalizedTerm": "extra",
            "acceptedVariants": [],
            "meaningZh": "额外项",
            "audio": "assets/audio/vocabulary/extra.mp3",
        }
    )
    windows.append(
        {
            "vocabularyId": "extra",
            "questionId": "q1",
            "section": 1,
            "startTime": 1.0,
            "endTime": 2.0,
            "paddingBefore": 0.05,
            "paddingAfter": 0.05,
        }
    )
    (pack_copy / "assets" / "audio" / "vocabulary" / "extra.mp3").write_bytes(b"mp3")
    _write_json(pack_copy / "vocabulary.json", vocabulary)
    _write_json(windows_path, windows)

    with pytest.raises(ReleaseBlocked, match="extra vocabulary"):
        validate_pack(pack_copy, answer_audio_windows_path=windows_path)


def test_release_rejects_vocabulary_missing_meaning(monkeypatch):
    pack_copy, windows_path, vocabulary, _ = _copy_pack_with_vocabulary(
        monkeypatch,
        "pack-vocabulary-meaning",
    )
    vocabulary[0]["meaningZh"] = ""
    _write_json(pack_copy / "vocabulary.json", vocabulary)

    with pytest.raises(ReleaseBlocked, match="meaningZh"):
        validate_pack(pack_copy, answer_audio_windows_path=windows_path)


def test_release_requires_existing_non_empty_vocabulary_clip(monkeypatch):
    pack_copy, windows_path, vocabulary, _ = _copy_pack_with_vocabulary(
        monkeypatch,
        "pack-vocabulary-empty-clip",
    )
    clip_path = pack_copy / vocabulary[0]["audio"]
    clip_path.write_bytes(b"")

    with pytest.raises(ReleaseBlocked, match="empty"):
        validate_pack(pack_copy, answer_audio_windows_path=windows_path)


def test_release_rejects_window_section_mismatch(monkeypatch):
    pack_copy, windows_path, _, windows = _copy_pack_with_vocabulary(
        monkeypatch,
        "pack-window-section",
    )
    windows[0]["section"] = 2
    _write_json(windows_path, windows)

    with pytest.raises(ReleaseBlocked, match="section"):
        validate_pack(pack_copy, answer_audio_windows_path=windows_path)


def test_release_rejects_window_outside_section_duration(monkeypatch):
    pack_copy, windows_path, _, windows = _copy_pack_with_vocabulary(
        monkeypatch,
        "pack-window-duration",
    )
    windows[0]["endTime"] = 301.0
    _write_json(windows_path, windows)

    with pytest.raises(ReleaseBlocked, match="section duration"):
        validate_pack(pack_copy, answer_audio_windows_path=windows_path)


def test_release_rejects_non_positive_window(monkeypatch):
    pack_copy, windows_path, _, windows = _copy_pack_with_vocabulary(
        monkeypatch,
        "pack-window-positive",
    )
    windows[0]["endTime"] = windows[0]["startTime"]
    _write_json(windows_path, windows)

    with pytest.raises(ReleaseBlocked, match="endTime"):
        validate_pack(pack_copy, answer_audio_windows_path=windows_path)


@pytest.mark.parametrize("clip_duration", [0.24, 6.01])
def test_release_rejects_vocabulary_clip_duration_outside_gate(monkeypatch, clip_duration):
    pack_copy, windows_path, _, _ = _copy_pack_with_vocabulary(
        monkeypatch,
        f"pack-clip-duration-{clip_duration}",
    )

    def fake_probe_duration(media_path: Path, **kwargs) -> float:
        name = Path(media_path).name
        if name.startswith("section-"):
            return 300.0
        return clip_duration

    monkeypatch.setattr(validate_pack_module, "probe_duration_seconds", fake_probe_duration)

    with pytest.raises(ReleaseBlocked, match="clip duration"):
        validate_pack(pack_copy, answer_audio_windows_path=windows_path)


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
