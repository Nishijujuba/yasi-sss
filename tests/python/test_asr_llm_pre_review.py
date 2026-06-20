from __future__ import annotations

import json
import sys
import uuid
from importlib import util as importlib_util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = Path(
    ".agents/skills/yasi-asr-timing-reconciliation/scripts/apply_llm_pre_review.py"
).resolve()


def load_module():
    if str(SCRIPT_PATH.parent) not in sys.path:
        sys.path.insert(0, str(SCRIPT_PATH.parent))
    spec = importlib_util.spec_from_file_location("apply_llm_pre_review_test_module", SCRIPT_PATH)
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


def sample_review() -> dict:
    return {
        "schemaVersion": "yasi.alignment-review.v1",
        "status": "needs-review",
        "sections": [
            {
                "section": 1,
                "status": "pending",
                "autoMapping": {"wordTimings": []},
                "mappingReviews": [
                    {
                        "reviewId": "s01-g0046",
                        "section": 1,
                        "matchType": "exact",
                        "decision": "pending",
                        "officialToken": {
                            "section": 1,
                            "segmentOrder": 6,
                            "tokenIndex": 0,
                            "globalTokenIndex": 46,
                            "text": "24",
                            "normalized": "24",
                            "answerRefs": [1],
                        },
                        "sourceWord": {"word": "24", "normalized": "24", "start": 176.78, "end": 177.38},
                        "timing": {"start": 176.78, "end": 177.38},
                        "riskTypes": ["number", "answer-near"],
                        "reasons": ["risk:number", "risk:answer-near"],
                        "screening": {"tier": "human-required", "rationale": "Numbers stay human-gated."},
                    }
                ],
            }
        ],
    }


def test_attach_llm_pre_review_preserves_decision_and_human_required_tier():
    module = load_module()
    result = module.attach_llm_pre_review(
        sample_review(),
        [
            {
                "reviewId": "s01-g0046",
                "suggestedDecision": "approved",
                "confidence": 0.91,
                "preReviewLabel": "needs-auditory-review",
                "notes": "Text identity matches, but numeric answer-near timing still needs listening.",
                "correction": None,
            }
        ],
        reviewer="test-llm",
        reviewed_at="2026-06-19T00:00:00Z",
    )

    item = result["review"]["sections"][0]["mappingReviews"][0]
    assert item["decision"] == "pending"
    assert item["screening"]["tier"] == "human-required"
    suggestion = item["screening"]["llmSuggestion"]
    assert suggestion["advisory"] is True
    assert suggestion["source"] == "test-llm"
    assert suggestion["suggestedDecision"] == "approved"
    assert suggestion["preReviewLabel"] == "needs-auditory-review"
    assert result["report"]["summary"] == {
        "suggestions": 1,
        "matched": 1,
        "unmatched": 0,
        "decisionsChanged": 0,
    }


def test_apply_llm_pre_review_cli_writes_review_and_report():
    module = load_module()
    root = unique_test_dir("llm-pre-review")
    review_input = root / "alignment-review.code-screened.json"
    llm_output = root / "llm-output.json"
    output = root / "alignment-review.llm-pre-reviewed.json"
    report_output = root / "llm-pre-review-apply-report.json"
    review_input.write_text(json.dumps(sample_review()), encoding="utf-8")
    llm_output.write_text(
        json.dumps(
            [
                {
                    "reviewId": "s01-g0046",
                    "suggestedDecision": "needs-human",
                    "confidence": 0.74,
                    "preReviewLabel": "needs-auditory-review",
                    "notes": "Number near an answer reference.",
                    "correction": None,
                }
            ]
        ),
        encoding="utf-8",
    )

    exit_code = module.main(
        [
            "--review-input",
            str(review_input),
            "--llm-output",
            str(llm_output),
            "--output",
            str(output),
            "--report-output",
            str(report_output),
            "--reviewer",
            "test-llm",
            "--reviewed-at",
            "2026-06-19T00:00:00Z",
        ]
    )

    assert exit_code == 0
    reviewed = json.loads(output.read_text(encoding="utf-8"))
    report = json.loads(report_output.read_text(encoding="utf-8"))
    item = reviewed["sections"][0]["mappingReviews"][0]
    assert item["decision"] == "pending"
    assert item["screening"]["llmSuggestion"]["suggestedDecision"] == "needs-human"
    assert report["summary"]["decisionsChanged"] == 0
