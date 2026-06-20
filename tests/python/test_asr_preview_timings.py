from __future__ import annotations

import json
import sys
import uuid
from importlib import util as importlib_util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = Path(
    ".agents/skills/yasi-asr-timing-reconciliation/scripts/build_preview_timings.py"
).resolve()


def load_module():
    if str(SCRIPT_PATH.parent) not in sys.path:
        sys.path.insert(0, str(SCRIPT_PATH.parent))
    spec = importlib_util.spec_from_file_location("build_preview_timings_test_module", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib_util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def unique_test_dir(name: str) -> Path:
    path = REPO_ROOT / "tmp" / "test-runs" / f"{name}-{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    return path


def sample_draft() -> dict:
    return {
        "schemaVersion": "yasi.transcript-timings.v1",
        "status": "draft",
        "sections": [
            {
                "section": 1,
                "status": "draft",
                "wordTimings": [
                    {
                        "section": 1,
                        "segmentOrder": 1,
                        "tokenIndex": 0,
                        "globalTokenIndex": 0,
                        "token": "Good",
                        "start": 1.0,
                        "end": 1.2,
                    },
                    {
                        "section": 1,
                        "segmentOrder": 1,
                        "tokenIndex": 1,
                        "globalTokenIndex": 1,
                        "token": "morning",
                        "start": None,
                        "end": None,
                    },
                ],
            }
        ],
    }


def sample_review() -> dict:
    return {
        "schemaVersion": "yasi.alignment-review.v1",
        "status": "needs-review",
        "sections": [
            {
                "section": 1,
                "mappingReviews": [
                    {
                        "reviewId": "s01-g0001",
                        "section": 1,
                        "decision": "pending",
                        "matchType": "unmatched",
                        "officialToken": {
                            "section": 1,
                            "segmentOrder": 1,
                            "tokenIndex": 1,
                            "globalTokenIndex": 1,
                            "text": "morning",
                            "normalized": "morning",
                        },
                        "riskTypes": ["answer-near"],
                        "reasons": ["missing-timing"],
                        "screening": {
                            "tier": "human-required",
                            "llmSuggestion": {
                                "advisory": True,
                                "suggestedDecision": "needs-human",
                                "confidence": 0.6,
                                "preReviewLabel": "needs-auditory-review",
                            },
                        },
                    }
                ],
            }
        ],
    }


def sample_draft_for_section(section: int) -> dict:
    draft = sample_draft()
    draft["sections"][0]["section"] = section
    for entry in draft["sections"][0]["wordTimings"]:
        entry["section"] = section
    return draft


def sample_review_for_section(section: int) -> dict:
    review = sample_review()
    review["sections"][0]["section"] = section
    item = review["sections"][0]["mappingReviews"][0]
    item["section"] = section
    item["reviewId"] = f"s{section:02d}-g0001"
    item["officialToken"]["section"] = section
    return review


def test_build_preview_timings_keeps_pending_review_as_preview_marker():
    module = load_module()
    result = module.build_preview_timings(
        draft_payload=sample_draft(),
        review_payload=sample_review(),
        review_input=Path("alignment-review.llm-pre-reviewed.json"),
        generated_at="2026-06-20T00:00:00Z",
    )

    assert result["status"] == "preview"
    assert result["sections"][0]["status"] == "preview"
    marker_entry = result["sections"][0]["wordTimings"][1]
    assert marker_entry["start"] is None
    assert marker_entry["requiresReview"] is True
    assert marker_entry["review"]["decision"] == "pending"
    assert marker_entry["review"]["llmSuggestion"]["preReviewLabel"] == "needs-auditory-review"
    assert result["preview"]["untimedReviewMarkerCount"] == 1


def test_build_preview_timings_converts_non_positive_preview_intervals_to_untimed_markers():
    module = load_module()
    draft = sample_draft()
    draft["sections"][0]["wordTimings"][0]["end"] = draft["sections"][0]["wordTimings"][0]["start"]
    review = sample_review()
    review["sections"][0]["mappingReviews"].append(
        {
            "reviewId": "s01-g0000",
            "section": 1,
            "decision": "pending",
            "matchType": "exact",
            "officialToken": {
                "section": 1,
                "segmentOrder": 1,
                "tokenIndex": 0,
                "globalTokenIndex": 0,
                "text": "Good",
                "normalized": "good",
            },
            "riskTypes": [],
            "reasons": ["non-positive-interval"],
        }
    )

    result = module.build_preview_timings(
        draft_payload=draft,
        review_payload=review,
        review_input=Path("alignment-review.code-screened.json"),
        generated_at="2026-06-20T00:00:00Z",
    )

    entry = result["sections"][0]["wordTimings"][0]
    assert entry["start"] is None
    assert entry["end"] is None
    assert entry["requiresReview"] is True
    assert "non-positive-interval" in entry["reasons"]
    assert result["preview"]["untimedReviewMarkerCount"] == 2


def test_build_preview_timings_merges_existing_preview_sections():
    module = load_module()
    existing = module.build_preview_timings(
        draft_payload=sample_draft_for_section(1),
        review_payload=sample_review_for_section(1),
        review_input=Path("section-01/alignment-review.code-screened.json"),
        generated_at="2026-06-20T00:00:00Z",
    )

    result = module.build_preview_timings(
        draft_payload=sample_draft_for_section(2),
        review_payload=sample_review_for_section(2),
        review_input=Path("section-02/alignment-review.code-screened.json"),
        existing_payload=existing,
        generated_at="2026-06-20T00:01:00Z",
    )

    assert [section["section"] for section in result["sections"]] == [1, 2]
    assert result["reviewArtifacts"] == {
        "1": "section-01/alignment-review.code-screened.json",
        "2": "section-02/alignment-review.code-screened.json",
    }
    assert result["preview"]["reviewMarkerCount"] == 2
    assert result["preview"]["untimedReviewMarkerCount"] == 2


def test_build_preview_timings_cli_writes_asset():
    module = load_module()
    root = unique_test_dir("preview-timings")
    draft_input = root / "transcript-timings.draft.json"
    review_input = root / "alignment-review.llm-pre-reviewed.json"
    output = root / "transcript-timings.preview.json"
    draft_input.write_text(json.dumps(sample_draft()), encoding="utf-8")
    review_input.write_text(json.dumps(sample_review()), encoding="utf-8")

    exit_code = module.main(
        [
            "--draft-input",
            str(draft_input),
            "--review-input",
            str(review_input),
            "--output",
            str(output),
            "--generated-at",
            "2026-06-20T00:00:00Z",
        ]
    )

    assert exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "preview"
    assert payload["preview"]["reviewMarkerCount"] == 1


def test_public_preview_asset_contains_all_listening_sections():
    manifest = json.loads(
        (REPO_ROOT / "public/packs/cambridge-10/test-1/listening/manifest.json").read_text(
            encoding="utf-8"
        )
    )
    timing_relative = manifest["assets"].get("transcriptTimings")
    assert timing_relative == "transcript-timings.preview.json"

    payload = json.loads(
        (
            REPO_ROOT
            / "public/packs/cambridge-10/test-1/listening"
            / timing_relative
        ).read_text(encoding="utf-8")
    )

    sections = {
        section["section"]: section
        for section in payload.get("sections", [])
        if isinstance(section, dict)
    }
    assert sorted(sections) == [1, 2, 3, 4]
    for section_number, section_payload in sections.items():
        assert section_payload["status"] == "preview"
        assert section_payload["wordTimings"], f"Section {section_number:02d} has no preview word timings"
        for timing in section_payload["wordTimings"]:
            start = timing.get("start")
            end = timing.get("end")
            if start is not None or end is not None:
                assert isinstance(start, (int, float))
                assert isinstance(end, (int, float))
                assert end > start, f"Section {section_number:02d} has invalid interval {start}..{end}"
