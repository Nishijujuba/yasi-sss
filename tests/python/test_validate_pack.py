from __future__ import annotations

import json
import re
import shutil
import sys
import uuid
from importlib import util as importlib_util
from pathlib import Path

import pytest

import builder.build_pack as build_pack_module
import builder.validate_pack as validate_pack_module
from builder.config import PACK_ROOT, SOURCE_DATA_ROOT
from builder.models import PendingAnswerCandidate, ReleaseReport
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
REPO_ROOT = Path(__file__).resolve().parents[2]
PACK_ID = "cambridge-10-test-1-listening"
REVIEW_ARTIFACT_RELATIVE = (
    f"build/review/transcript-timing/{PACK_ID}/alignment-review.json"
)


def unique_test_dir(name: str) -> Path:
    path = Path("tmp") / "test-runs" / f"{name}-{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    return path


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _load_timing_helpers():
    script_path = Path(
        ".agents/skills/yasi-asr-timing-reconciliation/scripts/validate_timings.py"
    ).resolve()
    script_dir = str(script_path.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    spec = importlib_util.spec_from_file_location("test_asr_timing_helpers", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib_util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


def _copy_pack_with_vocabulary(monkeypatch, name: str) -> tuple[Path, list[dict]]:
    pack_copy = unique_test_dir(name) / "listening"
    shutil.copytree(PACK_ROOT, pack_copy)

    manifest_path = pack_copy / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["assets"]["vocabulary"] = "vocabulary.json"
    manifest["assets"].pop("transcriptTimings", None)
    _write_json(manifest_path, manifest)

    records = _canonical_blank_records()
    vocabulary = []
    clip_dir = pack_copy / "assets" / "audio" / "vocabulary"
    clip_dir.mkdir(parents=True, exist_ok=True)

    for record in records:
        clip_path = clip_dir / f"{record['id']}.mp3"
        clip_path.write_bytes(b"mp3")
        vocabulary.append(
            {
                "id": record["id"],
                "term": record["term"],
                "normalizedTerm": record["normalizedTerm"],
                "acceptedVariants": record["acceptedVariants"],
                "meaningZh": "释义",
                "spokenText": record["term"],
                "audio": f"assets/audio/vocabulary/{record['id']}.mp3",
            }
        )

    _write_json(pack_copy / "vocabulary.json", vocabulary)

    def fake_probe_duration(media_path: Path, **kwargs) -> float:
        name = Path(media_path).name
        if name.startswith("section-"):
            return 300.0
        return 1.0

    monkeypatch.setattr(validate_pack_module, "probe_duration_seconds", fake_probe_duration)
    return pack_copy, vocabulary


def _write_transcript_timing_asset(
    pack_root: Path,
    *,
    sections: tuple[int, ...] = (1,),
    status: str = "verified",
    risky_first_token: bool = False,
    review_artifact: str | None = None,
    include_review_trace: bool = False,
    review_decision: str = "approved",
    trace_review_artifact: str | None = None,
    trace_decision: str | None = None,
) -> None:
    helpers = _load_timing_helpers()
    transcript_sections = helpers.load_official_sections(pack_root / "transcript.json")
    timing_sections = []
    review_id = "s01-g0000"

    for section in sections:
        word_timings = []
        for index, token in enumerate(helpers.official_tokens(transcript_sections[section])):
            entry = {
                "section": section,
                "segmentOrder": token.segment_order,
                "tokenIndex": token.token_index,
                "globalTokenIndex": token.global_token_index,
                "token": token.text,
                "text": token.text,
                "normalized": token.normalized,
                "start": round(index * 0.25, 3),
                "end": round(index * 0.25 + 0.18, 3),
                "matchType": "exact",
                "match": "exact",
                "riskTypes": [],
                "requiresReview": False,
            }
            if risky_first_token and section == sections[0] and index == 0:
                entry["riskTypes"] = ["number"]
                entry["requiresReview"] = True
                if include_review_trace:
                    entry["review"] = {
                        "reviewArtifact": trace_review_artifact or review_artifact,
                        "reviewId": review_id,
                        "decision": trace_decision or review_decision,
                        "riskTypes": ["number"],
                        "reasons": ["risk:number"],
                        "reviewer": "test",
                        "reviewedAt": "2026-06-18T00:00:00Z",
                        "notes": "",
                    }
            word_timings.append(entry)
        timing_sections.append(
            {
                "section": section,
                "status": status,
                "segmentCount": len(transcript_sections[section]["segments"]),
                "wordTimings": word_timings,
                "reviewItems": [],
                "diagnostics": {},
            }
        )

    payload = {
        "schemaVersion": helpers.SCHEMA_VERSION,
        "status": status,
        "generatedAt": "2026-06-17T00:00:00Z",
        "tool": {"name": "test"},
        "packRoot": str(pack_root),
        "transcript": "transcript.json",
        "reviewArtifact": review_artifact,
        "generatedFromReview": False,
        "sections": timing_sections,
        "reviewItems": [],
    }
    _write_json(pack_root / "transcript-timings.json", payload)

    manifest_path = pack_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["assets"]["transcriptTimings"] = "transcript-timings.json"
    _write_json(manifest_path, manifest)


def _write_preview_transcript_timing_asset(pack_root: Path, *, sections: tuple[int, ...] = (1,)) -> None:
    helpers = _load_timing_helpers()
    transcript_sections = helpers.load_official_sections(pack_root / "transcript.json")
    timing_sections = []
    for section in sections:
        word_timings = []
        for index, token in enumerate(helpers.official_tokens(transcript_sections[section])):
            word_timings.append(
                {
                    "section": section,
                    "segmentOrder": token.segment_order,
                    "tokenIndex": token.token_index,
                    "globalTokenIndex": token.global_token_index,
                    "token": token.text,
                    "text": token.text,
                    "normalized": token.normalized,
                    "start": round(index * 0.25, 3),
                    "end": round(index * 0.25 + 0.18, 3),
                    "matchType": "exact",
                    "match": "exact",
                    "riskTypes": [],
                    "requiresReview": False,
                }
            )
        timing_sections.append({"section": section, "status": "preview", "wordTimings": word_timings})

    payload = {
        "schemaVersion": helpers.SCHEMA_VERSION,
        "status": "preview",
        "generatedAt": "2026-06-20T00:00:00Z",
        "sections": timing_sections,
        "reviewItems": [],
    }
    _write_json(pack_root / "transcript-timings.preview.json", payload)

    manifest_path = pack_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["assets"]["transcriptTimings"] = "transcript-timings.preview.json"
    _write_json(manifest_path, manifest)


def _write_alignment_review(
    repo_root: Path,
    *,
    decision: str = "approved",
    include_item: bool = True,
) -> Path:
    helpers = _load_timing_helpers()
    transcript_sections = helpers.load_official_sections(PACK_ROOT / "transcript.json")
    token = helpers.official_tokens(transcript_sections[1])[0]
    review_dir = repo_root / "build" / "review" / "transcript-timing" / PACK_ID
    review_path = review_dir / "alignment-review.json"
    mapping_reviews = []
    if include_item:
        mapping_reviews.append(
            {
                "reviewId": "s01-g0000",
                "section": 1,
                "matchType": "exact",
                "decision": decision,
                "officialToken": {
                    "section": 1,
                    "segmentOrder": token.segment_order,
                    "tokenIndex": token.token_index,
                    "globalTokenIndex": token.global_token_index,
                    "text": token.text,
                    "normalized": token.normalized,
                    "answerRefs": list(token.answer_refs),
                },
                "sourceWord": {
                    "sourceIndex": 0,
                    "word": token.text,
                    "normalized": token.normalized,
                    "start": 0.0,
                    "end": 0.18,
                },
                "timing": {"start": 0.0, "end": 0.18},
                "riskTypes": ["number"],
                "reasons": ["risk:number"],
                "correction": None,
                "reviewer": "test",
                "reviewedAt": "2026-06-18T00:00:00Z",
                "notes": "",
            }
        )
    _write_json(
        review_path,
        {
            "schemaVersion": helpers.REVIEW_SCHEMA_VERSION,
            "reviewArtifact": REVIEW_ARTIFACT_RELATIVE,
            "status": "reviewed" if decision in {"approved", "corrected"} else "needs-review",
            "generatedAt": "2026-06-17T00:00:00Z",
            "tool": {"name": "test"},
            "packRoot": "public/packs/cambridge-10/test-1/listening",
            "transcript": "public/packs/cambridge-10/test-1/listening/transcript.json",
            "draftTimingArtifact": "transcript-timings.json",
            "finalTimingArtifact": "transcript-timings.json",
            "sections": [
                {"section": 1, "status": "reviewed", "mappingReviews": mapping_reviews}
            ],
        },
    )
    return review_path


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


def _patch_build_steps_to_noop(monkeypatch) -> None:
    for name in [
        "render_question_pages",
        "write_overlay_proposals",
        "draw_review_images",
        "finalize_overlays",
        "convert_audio_sections",
        "export_answers_and_transcript",
        "export_vocabulary",
        "build_vocabulary_audio_clips",
    ]:
        monkeypatch.setattr(build_pack_module, name, lambda: None)


def test_build_pack_writes_released_manifest_and_report(monkeypatch):
    root = unique_test_dir("build-pack-report")
    pack_root = root / "listening"
    review_root = root / "review"
    expected_report = ReleaseReport(
        status="released",
        questionCoverage=list(range(1, 41)),
        overlayCount=53,
        answerCount=40,
        vocabularyCount=VOCABULARY_COUNT,
        clipCount=VOCABULARY_COUNT,
        transcriptSections=[1, 2, 3, 4],
        audioSections=[1, 2, 3, 4],
        pageAssets=["assets/pages/page-010.png"],
        pendingAnswerCandidates=0,
        errors=[],
    )

    _patch_build_steps_to_noop(monkeypatch)
    monkeypatch.setattr(build_pack_module, "PACK_ROOT", pack_root)
    monkeypatch.setattr(build_pack_module, "REVIEW_ROOT", review_root)

    def fake_validate_pack(path: Path) -> ReleaseReport:
        assert path == pack_root
        return expected_report

    monkeypatch.setattr(build_pack_module, "validate_pack", fake_validate_pack)

    report = build_pack_module.build_pack()

    manifest = json.loads((pack_root / "manifest.json").read_text(encoding="utf-8"))
    release_report = json.loads(
        (review_root / "release-report.json").read_text(encoding="utf-8")
    )

    assert report.status == "released"
    assert report.clipCount == VOCABULARY_COUNT
    assert manifest["status"] == "released"
    assert manifest["assets"]["vocabulary"] == "vocabulary.json"
    assert "transcriptTimings" not in manifest["assets"]
    assert release_report["questionCoverage"] == list(range(1, 41))
    assert release_report["overlayCount"] == 53
    assert release_report["answerCount"] == 40
    assert release_report["vocabularyCount"] == VOCABULARY_COUNT
    assert release_report["clipCount"] == VOCABULARY_COUNT
    assert "windowCount" not in release_report


def test_build_pack_preserves_existing_release_report_when_validation_fails(monkeypatch):
    root = unique_test_dir("build-pack-report-preserve")
    pack_root = root / "listening"
    review_root = root / "review"
    report_path = review_root / "release-report.json"
    old_report = {"status": "released", "clipCount": 33, "sentinel": "keep"}
    _write_json(report_path, old_report)

    _patch_build_steps_to_noop(monkeypatch)
    monkeypatch.setattr(build_pack_module, "PACK_ROOT", pack_root)
    monkeypatch.setattr(build_pack_module, "REVIEW_ROOT", review_root)

    def fake_validate_pack(path: Path) -> ReleaseReport:
        raise ReleaseBlocked("blocked after build outputs")

    monkeypatch.setattr(build_pack_module, "validate_pack", fake_validate_pack)

    with pytest.raises(ReleaseBlocked, match="blocked after build outputs"):
        build_pack_module.build_pack()

    assert json.loads(report_path.read_text(encoding="utf-8")) == old_report


def test_validate_pack_reports_vocabulary_and_clip_counts_without_loading_windows(monkeypatch):
    pack_copy, _ = _copy_pack_with_vocabulary(
        monkeypatch,
        "pack-vocabulary-counts",
    )
    real_read_json = validate_pack_module._read_json
    read_paths = []

    def spy_read_json(path: Path) -> object:
        path = Path(path)
        if path.name == "answer-audio-windows.json":
            raise AssertionError("release validation must not load answer-audio-windows.json")
        read_paths.append(path)
        return real_read_json(path)

    monkeypatch.setattr(validate_pack_module, "_read_json", spy_read_json)

    report = validate_pack(pack_copy)

    assert report.vocabularyCount == VOCABULARY_COUNT
    assert report.clipCount == VOCABULARY_COUNT
    assert not hasattr(report, "windowCount")
    assert "windowCount" not in report.model_dump()
    assert all(path.name != "answer-audio-windows.json" for path in read_paths)


def test_validate_pack_allows_missing_optional_transcript_timings(monkeypatch):
    pack_copy, _ = _copy_pack_with_vocabulary(
        monkeypatch,
        "pack-timings-missing-optional",
    )
    manifest = json.loads((pack_copy / "manifest.json").read_text(encoding="utf-8"))

    report = validate_pack(pack_copy)

    assert "transcriptTimings" not in manifest["assets"]
    assert report.status == "released"


def test_validate_pack_allows_preview_transcript_timings_for_optional_gate(monkeypatch):
    pack_copy, _ = _copy_pack_with_vocabulary(
        monkeypatch,
        "pack-timings-preview-optional",
    )
    _write_preview_transcript_timing_asset(pack_copy, sections=(1, 2, 3, 4))

    report = validate_pack(pack_copy)

    assert report.status == "released"


def test_validate_pack_rejects_declared_draft_transcript_timings(monkeypatch):
    pack_copy, _ = _copy_pack_with_vocabulary(
        monkeypatch,
        "pack-timings-draft",
    )
    _write_transcript_timing_asset(pack_copy, status="draft")

    with pytest.raises(ReleaseBlocked, match="require-verified"):
        validate_pack(pack_copy)


def test_validate_pack_accepts_section_01_transcript_timing_pilot(monkeypatch):
    pack_copy, _ = _copy_pack_with_vocabulary(
        monkeypatch,
        "pack-timings-section-01-pilot",
    )
    _write_transcript_timing_asset(pack_copy, sections=(1,))

    report = validate_pack(pack_copy, transcript_timing_gate="section-01-pilot")

    assert report.status == "released"


def test_validate_pack_release_timing_gate_rejects_missing_sections(monkeypatch):
    pack_copy, _ = _copy_pack_with_vocabulary(
        monkeypatch,
        "pack-timings-release-missing-sections",
    )
    repo_root = unique_test_dir("pack-timings-review-root")
    monkeypatch.setattr(validate_pack_module, "_repo_root", lambda: repo_root)
    _write_alignment_review(repo_root, include_item=False)
    _write_transcript_timing_asset(
        pack_copy,
        sections=(1,),
        review_artifact=REVIEW_ARTIFACT_RELATIVE,
    )

    with pytest.raises(ReleaseBlocked, match="require-all-sections"):
        validate_pack(pack_copy, transcript_timing_gate="release")


def test_validate_pack_release_timing_gate_rejects_missing_review_artifact(monkeypatch):
    pack_copy, _ = _copy_pack_with_vocabulary(
        monkeypatch,
        "pack-timings-release-missing-review-artifact",
    )
    _write_transcript_timing_asset(pack_copy, sections=(1, 2, 3, 4))

    with pytest.raises(ReleaseBlocked, match="reviewArtifact"):
        validate_pack(pack_copy, transcript_timing_gate="release")


def test_validate_pack_release_timing_gate_rejects_pack_relative_review_artifact(monkeypatch):
    pack_copy, _ = _copy_pack_with_vocabulary(
        monkeypatch,
        "pack-timings-release-pack-relative-review",
    )
    _write_transcript_timing_asset(
        pack_copy,
        sections=(1, 2, 3, 4),
        review_artifact="alignment-review.json",
    )

    with pytest.raises(ReleaseBlocked, match="repo-root-relative"):
        validate_pack(pack_copy, transcript_timing_gate="release")


def test_validate_pack_release_timing_gate_rejects_pending_review_artifact(monkeypatch):
    pack_copy, _ = _copy_pack_with_vocabulary(
        monkeypatch,
        "pack-timings-release-pending-review",
    )
    repo_root = unique_test_dir("pack-timings-review-root")
    monkeypatch.setattr(validate_pack_module, "_repo_root", lambda: repo_root)
    _write_alignment_review(repo_root, decision="pending")
    _write_transcript_timing_asset(
        pack_copy,
        sections=(1, 2, 3, 4),
        risky_first_token=True,
        review_artifact=REVIEW_ARTIFACT_RELATIVE,
        include_review_trace=True,
        review_decision="pending",
    )

    with pytest.raises(ReleaseBlocked, match="pending"):
        validate_pack(pack_copy, transcript_timing_gate="release")


def test_validate_pack_release_timing_gate_rejects_missing_review_trace(monkeypatch):
    pack_copy, _ = _copy_pack_with_vocabulary(
        monkeypatch,
        "pack-timings-release-missing-review-trace",
    )
    repo_root = unique_test_dir("pack-timings-review-root")
    monkeypatch.setattr(validate_pack_module, "_repo_root", lambda: repo_root)
    _write_alignment_review(repo_root, include_item=False)
    _write_transcript_timing_asset(
        pack_copy,
        sections=(1, 2, 3, 4),
        risky_first_token=True,
        review_artifact=REVIEW_ARTIFACT_RELATIVE,
    )

    with pytest.raises(ReleaseBlocked, match="requires review trace"):
        validate_pack(pack_copy, transcript_timing_gate="release")


def test_validate_pack_release_timing_gate_accepts_repo_root_relative_review_artifact(monkeypatch):
    validate_pack_module._load_timing_validator.cache_clear()
    pack_copy, _ = _copy_pack_with_vocabulary(
        monkeypatch,
        "pack-timings-release-reviewed",
    )
    repo_root = unique_test_dir("pack-timings-review-root")
    monkeypatch.setattr(validate_pack_module, "_repo_root", lambda: repo_root)
    _write_alignment_review(repo_root, decision="approved")
    _write_transcript_timing_asset(
        pack_copy,
        sections=(1, 2, 3, 4),
        risky_first_token=True,
        review_artifact=REVIEW_ARTIFACT_RELATIVE,
        include_review_trace=True,
        review_decision="approved",
    )

    report = validate_pack(pack_copy, transcript_timing_gate="release")

    assert report.status == "released"


def test_validate_pack_release_timing_gate_rejects_trace_review_artifact_mismatch(monkeypatch):
    pack_copy, _ = _copy_pack_with_vocabulary(
        monkeypatch,
        "pack-timings-release-trace-artifact-mismatch",
    )
    repo_root = unique_test_dir("pack-timings-review-root")
    monkeypatch.setattr(validate_pack_module, "_repo_root", lambda: repo_root)
    _write_alignment_review(repo_root, decision="approved")
    _write_transcript_timing_asset(
        pack_copy,
        sections=(1, 2, 3, 4),
        risky_first_token=True,
        review_artifact=REVIEW_ARTIFACT_RELATIVE,
        include_review_trace=True,
        review_decision="approved",
        trace_review_artifact="alignment-review.json",
    )

    with pytest.raises(ReleaseBlocked, match="reviewArtifact"):
        validate_pack(pack_copy, transcript_timing_gate="release")


def test_validate_pack_release_timing_gate_rejects_trace_decision_mismatch(monkeypatch):
    pack_copy, _ = _copy_pack_with_vocabulary(
        monkeypatch,
        "pack-timings-release-trace-decision-mismatch",
    )
    repo_root = unique_test_dir("pack-timings-review-root")
    monkeypatch.setattr(validate_pack_module, "_repo_root", lambda: repo_root)
    _write_alignment_review(repo_root, decision="approved")
    _write_transcript_timing_asset(
        pack_copy,
        sections=(1, 2, 3, 4),
        risky_first_token=True,
        review_artifact=REVIEW_ARTIFACT_RELATIVE,
        include_review_trace=True,
        review_decision="approved",
        trace_decision="corrected",
    )

    with pytest.raises(ReleaseBlocked, match="decision"):
        validate_pack(pack_copy, transcript_timing_gate="release")


def test_release_requires_vocabulary_full_blank_canonical_coverage(monkeypatch):
    pack_copy, vocabulary = _copy_pack_with_vocabulary(
        monkeypatch,
        "pack-vocabulary-missing",
    )
    vocabulary.pop(0)
    _write_json(pack_copy / "vocabulary.json", vocabulary)

    with pytest.raises(ReleaseBlocked, match="vocabulary coverage"):
        validate_pack(pack_copy)


def test_release_rejects_extra_vocabulary_item(monkeypatch):
    pack_copy, vocabulary = _copy_pack_with_vocabulary(
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
            "spokenText": "extra",
            "audio": "assets/audio/vocabulary/extra.mp3",
        }
    )
    (pack_copy / "assets" / "audio" / "vocabulary" / "extra.mp3").write_bytes(b"mp3")
    _write_json(pack_copy / "vocabulary.json", vocabulary)

    with pytest.raises(ReleaseBlocked, match="extra vocabulary"):
        validate_pack(pack_copy)


def test_release_rejects_duplicate_vocabulary_audio_paths(monkeypatch):
    pack_copy, vocabulary = _copy_pack_with_vocabulary(
        monkeypatch,
        "pack-vocabulary-duplicate-audio",
    )
    vocabulary[1]["audio"] = vocabulary[0]["audio"]
    _write_json(pack_copy / "vocabulary.json", vocabulary)

    with pytest.raises(ReleaseBlocked, match="duplicate vocabulary audio path"):
        validate_pack(pack_copy)


def test_release_rejects_vocabulary_missing_meaning(monkeypatch):
    pack_copy, vocabulary = _copy_pack_with_vocabulary(
        monkeypatch,
        "pack-vocabulary-meaning",
    )
    vocabulary[0]["meaningZh"] = ""
    _write_json(pack_copy / "vocabulary.json", vocabulary)

    with pytest.raises(ReleaseBlocked, match="meaningZh"):
        validate_pack(pack_copy)


@pytest.mark.parametrize("spoken_text", [None, ""])
def test_release_rejects_missing_or_empty_spoken_text(monkeypatch, spoken_text):
    pack_copy, vocabulary = _copy_pack_with_vocabulary(
        monkeypatch,
        "pack-vocabulary-spoken-text",
    )
    if spoken_text is None:
        del vocabulary[0]["spokenText"]
    else:
        vocabulary[0]["spokenText"] = spoken_text
    _write_json(pack_copy / "vocabulary.json", vocabulary)

    with pytest.raises(ReleaseBlocked, match="spokenText"):
        validate_pack(pack_copy)


def test_release_requires_existing_vocabulary_clip(monkeypatch):
    pack_copy, vocabulary = _copy_pack_with_vocabulary(
        monkeypatch,
        "pack-vocabulary-missing-clip",
    )
    vocabulary[0]["audio"] = "assets/audio/vocabulary/missing.mp3"
    _write_json(pack_copy / "vocabulary.json", vocabulary)

    with pytest.raises(ReleaseBlocked, match="missing"):
        validate_pack(pack_copy)


def test_release_rejects_empty_vocabulary_clip(monkeypatch):
    pack_copy, vocabulary = _copy_pack_with_vocabulary(
        monkeypatch,
        "pack-vocabulary-empty-clip",
    )
    clip_path = pack_copy / vocabulary[0]["audio"]
    clip_path.write_bytes(b"")

    with pytest.raises(ReleaseBlocked, match="empty"):
        validate_pack(pack_copy)


@pytest.mark.parametrize("clip_duration", [0.24, 6.01])
def test_release_rejects_vocabulary_clip_duration_outside_gate(monkeypatch, clip_duration):
    pack_copy, _ = _copy_pack_with_vocabulary(
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
        validate_pack(pack_copy)


def test_release_requires_all_assets(monkeypatch):
    pack_copy, _ = _copy_pack_with_vocabulary(monkeypatch, "pack-copy")
    manifest_path = pack_copy / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["sections"][3]["audio"] = "assets/audio/missing-section-04.mp3"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ReleaseBlocked, match="missing-section-04.mp3"):
        validate_pack(pack_copy)


def test_release_requires_vision_and_final_confidence_gate(monkeypatch):
    pack_copy, _ = _copy_pack_with_vocabulary(monkeypatch, "pack-low-confidence")
    overlays_path = pack_copy / "overlays.json"
    overlays = json.loads(overlays_path.read_text(encoding="utf-8"))
    overlays[0]["visionConfidence"] = 0.80
    overlays_path.write_text(json.dumps(overlays, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ReleaseBlocked, match="0.85"):
        validate_pack(pack_copy)
