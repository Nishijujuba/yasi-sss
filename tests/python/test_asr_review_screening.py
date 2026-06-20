from __future__ import annotations

import json
import sys
import uuid
from importlib import util as importlib_util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = Path(
    ".agents/skills/yasi-asr-timing-reconciliation/scripts/screen_alignment_review.py"
).resolve()


def load_module():
    if str(SCRIPT_PATH.parent) not in sys.path:
        sys.path.insert(0, str(SCRIPT_PATH.parent))
    spec = importlib_util.spec_from_file_location("screen_alignment_review_test_module", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib_util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def review_item(
    review_id: str,
    *,
    text: str,
    source_word: str,
    normalized: str | None = None,
    source_normalized: str | None = None,
    start: float | None = 1.0,
    end: float | None = 1.3,
    match_type: str = "exact",
    risk_types: list[str] | None = None,
    reasons: list[str] | None = None,
    answer_refs: list[int] | None = None,
    global_token_index: int = 1,
) -> dict:
    return {
        "reviewId": review_id,
        "section": 1,
        "matchType": match_type,
        "decision": "pending",
        "officialToken": {
            "section": 1,
            "segmentOrder": 2,
            "tokenIndex": global_token_index,
            "globalTokenIndex": global_token_index,
            "text": text,
            "normalized": normalized or text.lower().replace("'", ""),
            "answerRefs": answer_refs or [],
        },
        "sourceWord": {
            "sourceIndex": 10 + global_token_index,
            "word": source_word,
            "normalized": source_normalized or source_word.lower().replace("'", ""),
            "start": start,
            "end": end,
        },
        "timing": {"start": start, "end": end},
        "riskTypes": risk_types or [],
        "reasons": reasons or [],
        "correction": None,
    }


def review_payload(items: list[dict]) -> dict:
    return {
        "schemaVersion": "yasi.alignment-review.v1",
        "reviewArtifact": "build/review/transcript-timing/cambridge-10-test-1-listening/alignment-review.json",
        "status": "needs-review",
        "sections": [
            {
                "section": 1,
                "status": "pending",
                "autoMapping": {
                    "schemaVersion": "yasi.transcript-timings.v1",
                    "status": "draft",
                    "wordTimings": [],
                    "reviewItems": [],
                    "diagnostics": {},
                },
                "mappingReviews": items,
            }
        ],
    }


def unique_test_dir(name: str) -> Path:
    path = REPO_ROOT / "tmp" / "test-runs" / f"{name}-{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    return path


def test_code_screening_approves_exact_safe_answer_near_and_leaves_numeric_pending():
    module = load_module()
    payload = review_payload(
        [
            review_item(
                "safe-answer-near",
                text="Road",
                source_word="Road.",
                normalized="road",
                source_normalized="road",
                risk_types=["answer-near"],
                reasons=["risk:answer-near"],
                answer_refs=[1],
                global_token_index=1,
            ),
            review_item(
                "numeric-answer",
                text="24",
                source_word="24",
                normalized="24",
                source_normalized="24",
                risk_types=["number", "answer-near"],
                reasons=["risk:number", "risk:answer-near"],
                answer_refs=[1],
                global_token_index=2,
            ),
        ]
    )

    result = module.screen_review(payload, reviewer="test-screen", reviewed_at="2026-06-18T00:00:00Z")

    screened = result["screenedReview"]
    items = screened["sections"][0]["mappingReviews"]
    assert items[0]["decision"] == "approved"
    assert items[0]["reviewer"] == "test-screen"
    assert items[0]["reviewedAt"] == "2026-06-18T00:00:00Z"
    assert items[0]["screening"]["tier"] == "code-approved"
    assert items[1]["decision"] == "pending"
    assert items[1]["screening"]["tier"] == "human-required"
    assert result["report"]["summary"] == {
        "total": 2,
        "codeApproved": 1,
        "llmCandidate": 0,
        "humanRequired": 1,
    }


def test_llm_candidates_include_textual_fuzzy_items_and_exclude_missing_timing():
    module = load_module()
    payload = review_payload(
        [
            review_item(
                "fuzzy-name",
                text="Ardleigh",
                source_word="Ardley",
                normalized="ardleigh",
                source_normalized="ardley",
                match_type="fuzzy",
                risk_types=["answer-near"],
                reasons=["match:fuzzy", "risk:answer-near"],
                answer_refs=[1],
                global_token_index=3,
            ),
            review_item(
                "missing-money",
                text="pounds",
                source_word="",
                normalized="pounds",
                source_normalized="",
                start=None,
                end=None,
                match_type="unmatched",
                risk_types=["currency", "answer-near"],
                reasons=["missing-timing", "risk:currency", "risk:answer-near"],
                answer_refs=[9],
                global_token_index=4,
            ),
        ]
    )

    result = module.screen_review(payload, reviewer="test-screen", reviewed_at="2026-06-18T00:00:00Z")

    report = result["report"]
    assert report["llmCandidates"][0]["reviewId"] == "fuzzy-name"
    assert report["humanRequired"][0]["reviewId"] == "missing-money"
    assert "missing-timing" in report["humanRequired"][0]["reasons"]
    batches = module.build_llm_jsonl_records(report, max_items_per_record=10)
    assert len(batches) == 1
    assert batches[0]["task"] == "yasi-alignment-review-suggestion"
    assert batches[0]["items"][0]["reviewId"] == "fuzzy-name"
    assert "Return JSON only" in batches[0]["prompt"]
    pre_review_batches = module.build_llm_pre_review_jsonl_records(report, max_items_per_record=10)
    assert len(pre_review_batches) == 1
    assert pre_review_batches[0]["task"] == "yasi-alignment-blind-pre-review"
    assert [item["reviewId"] for item in pre_review_batches[0]["items"]] == ["fuzzy-name", "missing-money"]


def test_screening_cli_writes_report_screened_review_and_llm_batches():
    module = load_module()
    tmp_path = unique_test_dir("review-screening")
    input_path = tmp_path / "alignment-review.json"
    output_dir = tmp_path / "screened"
    input_path.write_text(
        json.dumps(
            review_payload(
                [
                    review_item(
                        "apostrophe",
                        text="It\u2019s",
                        source_word="It's",
                        normalized="its",
                        source_normalized="its",
                        risk_types=["apostrophe"],
                        reasons=["risk:apostrophe"],
                    )
                ]
            ),
            indent=2,
        ),
        encoding="utf-8",
    )

    exit_code = module.main(
        [
            "--review-input",
            str(input_path),
            "--output-dir",
            str(output_dir),
            "--reviewer",
            "test-screen",
            "--reviewed-at",
            "2026-06-18T00:00:00Z",
        ]
    )

    assert exit_code == 0
    report = json.loads((output_dir / "review-screening-report.json").read_text(encoding="utf-8"))
    screened = json.loads((output_dir / "alignment-review.code-screened.json").read_text(encoding="utf-8"))
    jsonl = (output_dir / "llm-review-candidates.jsonl").read_text(encoding="utf-8")
    pre_review_jsonl = (output_dir / "llm-pre-review-candidates.jsonl").read_text(encoding="utf-8")
    assert report["schemaVersion"] == "yasi.review-screening-report.v1"
    assert screened["sections"][0]["mappingReviews"][0]["decision"] == "approved"
    assert jsonl == ""
    assert pre_review_jsonl == ""
