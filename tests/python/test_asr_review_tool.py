from __future__ import annotations

import json
import sys
import uuid
from importlib import util as importlib_util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = Path(
    ".agents/skills/yasi-asr-timing-reconciliation/scripts/build_review_tool.py"
).resolve()


def load_module():
    if str(SCRIPT_PATH.parent) not in sys.path:
        sys.path.insert(0, str(SCRIPT_PATH.parent))
    spec = importlib_util.spec_from_file_location("build_review_tool_test_module", SCRIPT_PATH)
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


def sample_review_payload() -> dict:
    pending = {
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
        "sourceWord": {
            "sourceIndex": 290,
            "word": "24",
            "normalized": "24",
            "start": 176.78,
            "end": 177.38,
        },
        "timing": {"start": 176.78, "end": 177.38},
        "riskTypes": ["number", "answer-near"],
        "reasons": ["risk:number", "risk:answer-near"],
        "correction": None,
        "screening": {
            "tier": "human-required",
            "rationale": "Numbers stay human-gated.",
            "llmSuggestion": {
                "advisory": True,
                "source": "test-llm",
                "reviewedAt": "2026-06-19T00:00:00Z",
                "suggestedDecision": "needs-human",
                "confidence": 0.7,
                "preReviewLabel": "needs-auditory-review",
                "notes": "Numeric answer-near item needs listening after practice.",
                "correction": None,
            },
        },
    }
    approved = {
        "reviewId": "s01-g0048",
        "section": 1,
        "matchType": "exact",
        "decision": "approved",
        "officialToken": {
            "section": 1,
            "segmentOrder": 6,
            "tokenIndex": 2,
            "globalTokenIndex": 48,
            "text": "Road",
            "normalized": "road",
            "answerRefs": [1],
        },
        "sourceWord": {
            "sourceIndex": 292,
            "word": "Road.",
            "normalized": "road",
            "start": 177.98,
            "end": 178.42,
        },
        "timing": {"start": 177.98, "end": 178.42},
        "riskTypes": ["answer-near"],
        "reasons": ["risk:answer-near"],
        "correction": None,
        "screening": {"tier": "code-approved", "rationale": "Exact safe match."},
    }
    word_timings = []
    for index, token in enumerate(["please", "confirm", "24", "Ardleigh", "Road"]):
        word_timings.append(
            {
                "section": 1,
                "segmentOrder": 6,
                "tokenIndex": index,
                "globalTokenIndex": 44 + index,
                "token": token,
                "start": 175.0 + index,
                "end": 175.4 + index,
            }
        )
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
                    "wordTimings": word_timings,
                    "reviewItems": [],
                    "diagnostics": {},
                },
                "mappingReviews": [pending, approved],
            }
        ],
    }


def sample_screening_report() -> dict:
    return {
        "schemaVersion": "yasi.review-screening-report.v1",
        "summary": {"total": 2, "codeApproved": 1, "llmCandidate": 0, "humanRequired": 1},
        "humanRequired": [{"reviewId": "s01-g0046", "tier": "human-required"}],
        "llmCandidates": [],
    }


def test_tool_data_contains_only_unresolved_queue_with_context_and_audio_url():
    module = load_module()

    data = module.build_tool_data(
        review_payload=sample_review_payload(),
        screening_report=sample_screening_report(),
        audio_url="file:///D:/Project/yasi/public/packs/cambridge-10/test-1/listening/assets/audio/section-01.mp3",
        title="Section 01 small",
    )

    assert data["title"] == "Section 01 small"
    assert data["audioUrl"].startswith("file:///D:/Project/yasi/")
    assert [item["reviewId"] for item in data["queueItems"]] == ["s01-g0046"]
    assert data["queueItems"][0]["context"][2]["token"] == "24"
    assert data["queueItems"][0]["context"][2]["isTarget"] is True
    assert data["queueItems"][0]["screening"]["llmSuggestion"]["suggestedDecision"] == "needs-human"
    marked = [entry for entry in data["transcriptMap"] if entry["marker"] is not None]
    assert marked[0]["marker"]["reviewId"] == "s01-g0046"
    assert marked[0]["marker"]["llmSuggestion"]["preReviewLabel"] == "needs-auditory-review"
    assert data["summary"]["pending"] == 1
    assert data["summary"]["approved"] == 1


def test_rendered_html_embeds_data_and_export_function():
    module = load_module()
    data = module.build_tool_data(
        review_payload=sample_review_payload(),
        screening_report=sample_screening_report(),
        audio_url="file:///D:/Project/yasi/audio.mp3",
        title="Section 01 small",
    )

    html = module.render_review_tool_html(data)

    assert "window.__YASI_REVIEW_TOOL_DATA__" in html
    assert "s01-g0046" in html
    assert "file:///D:/Project/yasi/audio.mp3" in html
    assert "Advisory LLM suggestion" in html
    assert "Timing Map" in html
    assert "function exportReviewedJson" in html
    assert "alignment-review.reviewed.json" in html


def test_review_tool_cli_writes_static_html(tmp_path: Path | None = None):
    module = load_module()
    root = unique_test_dir("review-tool")
    review_input = root / "alignment-review.code-screened.json"
    report_input = root / "review-screening-report.json"
    output = root / "review-tool.html"
    review_input.write_text(json.dumps(sample_review_payload()), encoding="utf-8")
    report_input.write_text(json.dumps(sample_screening_report()), encoding="utf-8")

    exit_code = module.main(
        [
            "--review-input",
            str(review_input),
            "--screening-report",
            str(report_input),
            "--audio-url",
            "file:///D:/Project/yasi/section-01.mp3",
            "--title",
            "Section 01 small",
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    html = output.read_text(encoding="utf-8")
    assert "<audio" in html
    assert "Section 01 small" in html
    assert "s01-g0046" in html
