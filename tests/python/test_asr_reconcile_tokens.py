from __future__ import annotations

import sys
from importlib import util as importlib_util
from pathlib import Path

import pytest


def _load_reconcile_module():
    script_path = Path(".agents/skills/yasi-asr-timing-reconciliation/scripts/reconcile_tokens.py").resolve()
    if str(script_path.parent) not in sys.path:
        sys.path.insert(0, str(script_path.parent))
    spec = importlib_util.spec_from_file_location("test_asr_reconcile_tokens_module", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib_util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _official(text: str, *, answer_refs: list[int] | None = None) -> list[dict]:
    return [
        {
            "section": 1,
            "segments": [
                {
                    "order": 1,
                    "speaker": "TEST",
                    "text": text,
                    "answerRefs": answer_refs or [],
                    "startTime": None,
                    "endTime": None,
                }
            ],
        }
    ]


def _asr_words(words: list[str], *, start: float = 0.0, step: float = 0.5) -> dict:
    return {
        "schemaVersion": "yasi.asr-timing-evidence.v1",
        "engine": "whisper",
        "model": "small",
        "sourceAudio": "section-01.mp3",
        "words": [
            {
                "index": index,
                "word": word,
                "start": round(start + index * step, 3),
                "end": round(start + index * step + 0.25, 3),
            }
            for index, word in enumerate(words)
        ],
    }


def _asr_timed(items: list[tuple[str, float, float]]) -> dict:
    return {
        "schemaVersion": "yasi.asr-timing-evidence.v1",
        "engine": "whisper",
        "model": "small",
        "sourceAudio": "section-01.mp3",
        "words": [
            {"index": index, "word": word, "start": start, "end": end}
            for index, (word, start, end) in enumerate(items)
        ],
    }


def _entries(report: dict) -> list[dict]:
    return report["draftTimings"]["sections"][0]["wordTimings"]


def test_normalize_token_returns_identity_and_risk_flags():
    module = _load_reconcile_module()

    cases = [
        ("DON'T", "dont", {"apostrophe"}),
        ("don\u2019t", "dont", {"apostrophe"}),
        ("co-op", "coop", {"hyphenated"}),
        ("A-R-D", "ard", {"hyphen-spelling"}),
        ("Hello,", "hello", set()),
        ("$4.50", "450", {"currency", "number"}),
        ("2,000", "2000", {"number"}),
    ]

    for raw, normalized, risks in cases:
        identity = module.normalize_token(raw)
        assert identity["text"] == raw
        assert identity["normalized"] == normalized
        assert set(identity["riskTypes"]) >= risks
        assert identity["isHighRisk"] is bool(risks)

    answer_near = module.normalize_token("Road", answer_refs=[1], answer_near=True)
    assert answer_near["normalized"] == "road"
    assert answer_near["answerRefs"] == [1]
    assert "answer-near" in answer_near["riskTypes"]
    assert answer_near["isHighRisk"] is True


def test_flatten_official_transcript_preserves_token_identity_and_answer_near_risk():
    module = _load_reconcile_module()

    tokens = module.flatten_official_transcript(_official("24, Ardleigh Road.", answer_refs=[1]), section=1)

    assert [token["text"] for token in tokens] == ["24", "Ardleigh", "Road"]
    assert tokens[0]["section"] == 1
    assert tokens[0]["segmentOrder"] == 1
    assert tokens[0]["tokenIndex"] == 0
    assert tokens[0]["globalTokenIndex"] == 0
    assert tokens[0]["answerRefs"] == [1]
    assert "answer-near" in tokens[0]["riskTypes"]
    assert "number" in tokens[0]["riskTypes"]
    assert tokens[1]["normalized"] == "ardleigh"


def test_sequence_alignment_exact_synthetic_transcript_has_full_anchor_coverage():
    module = _load_reconcile_module()
    text = "good morning world tours my name is jamie."
    words = "good morning world tours my name is jamie".split()

    report = module.reconcile_transcript(_official(text), _asr_words(words), section=1)
    entries = _entries(report)

    assert [entry["normalized"] for entry in entries] == words
    assert [entry["matchType"] for entry in entries] == ["exact"] * len(words)
    assert [entry["sourceWord"] for entry in entries] == words
    assert report["metrics"]["anchorCoverage"] == 1.0
    assert report["metrics"]["unmatchedRate"] == 0.0
    assert report["metrics"]["pendingReviewRate"] == 0.0
    assert report["metrics"]["longestUnanchoredGap"] == 0
    assert report["reviewItems"] == []
    assert report["blockingReasons"] == []
    assert report["diagnostics"] == []


def test_sequence_alignment_near_miss_marks_final_token_fuzzy_and_pending_review():
    module = _load_reconcile_module()
    official = "good morning world tours my name is jamie."
    asr = "good morning world tours my name is jammy".split()

    report = module.reconcile_transcript(_official(official), _asr_words(asr), section=1)
    final = _entries(report)[-1]

    assert final["token"] == "jamie"
    assert final["sourceWord"] == "jammy"
    assert final["matchType"] == "fuzzy"
    assert final["requiresReview"] is True
    assert report["metrics"]["pendingReviewRate"] == pytest.approx(1 / 8)
    assert any(
        item["decision"] == "pending"
        and item["matchType"] == "fuzzy"
        and item["officialToken"]["text"] == "jamie"
        for item in report["reviewItems"]
    )
    assert "pending-review" in report["blockingReasons"]
    assert report["diagnostics"]
    assert all(isinstance(item, dict) for item in report["diagnostics"])
    assert any(
        item.get("section") == 1
        and item.get("severity") == "blocking"
        and item.get("code") == "pending-review"
        for item in report["diagnostics"]
    )


def test_rerun_report_populates_top_level_blocking_reasons_and_diagnostics():
    module = _load_reconcile_module()

    report = module.reconcile_transcript(
        _official("alpha bravo charlie delta echo foxtrot golf hotel india"),
        _asr_timed([]),
        section=1,
    )

    assert report["gateOutcome"] == "rerun-asr"
    assert "anchor-coverage-too-low" in report["blockingReasons"]
    assert "unanchored-gap-too-wide" in report["blockingReasons"]
    assert report["diagnostics"]
    assert {
        item["code"]
        for item in report["diagnostics"]
        if item.get("severity") == "blocking"
    } >= {"anchor-coverage-too-low", "unanchored-gap-too-wide"}


def test_fuzzy_threshold_override_changes_near_miss_to_unmatched_review():
    module = _load_reconcile_module()
    official = "good morning jamie."
    asr = "good morning jammy".split()

    default_report = module.reconcile_transcript(_official(official), _asr_words(asr), section=1)
    strict_report = module.reconcile_transcript(
        _official(official),
        _asr_words(asr),
        section=1,
        fuzzy_threshold=0.95,
    )

    assert _entries(default_report)[-1]["matchType"] == "fuzzy"
    assert _entries(strict_report)[-1]["matchType"] == "unmatched"
    assert _entries(strict_report)[-1]["requiresReview"] is True
    assert strict_report["gateOutcome"] == "needs-review"


def test_missing_timing_on_exact_match_requires_pending_review():
    module = _load_reconcile_module()
    asr_payload = {
        "schemaVersion": "yasi.asr-timing-evidence.v1",
        "engine": "whisper",
        "model": "small",
        "sourceAudio": "section-01.mp3",
        "words": [
            {"index": 0, "word": "good", "start": 0.0, "end": 0.25},
            {"index": 1, "word": "morning"},
        ],
    }

    report = module.reconcile_transcript(_official("good morning"), asr_payload, section=1)
    missing = _entries(report)[1]

    assert missing["matchType"] == "exact"
    assert missing["sourceWord"] == "morning"
    assert missing["start"] is None
    assert missing["end"] is None
    assert missing["requiresReview"] is True
    assert report["gateOutcome"] == "needs-review"
    assert any(
        item["decision"] == "pending"
        and item["matchType"] == "exact"
        and "missing-timing" in item["reasons"]
        for item in report["reviewItems"]
    )


def test_merged_mapping_records_multiple_official_tokens_sharing_one_asr_span():
    module = _load_reconcile_module()

    report = module.reconcile_transcript(
        _official("self drive tours"),
        _asr_timed([("self-drive", 0.0, 0.4), ("tours", 0.5, 0.75)]),
        section=1,
    )
    entries = _entries(report)

    assert [entry["matchType"] for entry in entries] == ["merged", "merged", "exact"]
    assert entries[0]["sourceIndex"] == entries[1]["sourceIndex"] == 0
    assert entries[0]["sourceWord"] == entries[1]["sourceWord"] == "self-drive"
    assert entries[0]["start"] == entries[1]["start"] == 0.0
    assert entries[0]["end"] == entries[1]["end"] == 0.4
    assert entries[0]["requiresReview"] is True
    assert entries[1]["requiresReview"] is True
    assert report["matchTypeCounts"]["merged"] == 2
    assert report["gateOutcome"] == "needs-review"
    assert [
        item["officialToken"]["text"]
        for item in report["reviewItems"]
        if item["matchType"] == "merged"
    ] == ["self", "drive"]


def test_split_mapping_records_one_official_token_spanning_multiple_asr_words():
    module = _load_reconcile_module()

    report = module.reconcile_transcript(
        _official("ardleigh road"),
        _asr_timed([("ard", 0.0, 0.2), ("leigh", 0.25, 0.5), ("road", 0.6, 0.85)]),
        section=1,
    )
    entries = _entries(report)

    assert entries[0]["matchType"] == "split"
    assert entries[0]["token"] == "ardleigh"
    assert entries[0]["sourceIndexes"] == [0, 1]
    assert entries[0]["sourceWords"] == ["ard", "leigh"]
    assert entries[0]["start"] == 0.0
    assert entries[0]["end"] == 0.5
    assert entries[0]["requiresReview"] is True
    assert entries[1]["matchType"] == "exact"
    assert report["matchTypeCounts"]["split"] == 1
    assert report["gateOutcome"] == "needs-review"
    assert any(
        item["matchType"] == "split"
        and item["sourceWords"] == ["ard", "leigh"]
        and item["decision"] == "pending"
        for item in report["reviewItems"]
    )


def test_duplicate_split_asr_does_not_rewrite_existing_exact_anchor():
    module = _load_reconcile_module()

    report = module.reconcile_transcript(
        _official("cannot wait"),
        _asr_timed([("cannot", 0.0, 0.25), ("wait", 0.4, 0.65), ("can", 0.8, 1.0), ("not", 1.05, 1.25)]),
        section=1,
    )
    entries = _entries(report)

    assert [entry["token"] for entry in entries] == ["cannot", "wait"]
    assert [entry["matchType"] for entry in entries] == ["exact", "exact"]
    assert entries[0]["sourceIndex"] == 0
    assert entries[0]["sourceWord"] == "cannot"
    assert entries[0]["start"] == 0.0
    assert entries[0]["end"] == 0.25
    assert "sourceIndexes" not in entries[0]
    assert report["matchTypeCounts"]["split"] == 0
    assert report["reviewItems"] == []


def test_duplicate_merged_asr_does_not_rewrite_existing_exact_anchors():
    module = _load_reconcile_module()

    report = module.reconcile_transcript(
        _official("self drive tours"),
        _asr_timed([("self", 0.0, 0.2), ("drive", 0.25, 0.45), ("tours", 0.5, 0.75), ("self-drive", 0.9, 1.2)]),
        section=1,
    )
    entries = _entries(report)

    assert [entry["token"] for entry in entries] == ["self", "drive", "tours"]
    assert [entry["matchType"] for entry in entries] == ["exact", "exact", "exact"]
    assert [entry["sourceWord"] for entry in entries] == ["self", "drive", "tours"]
    assert [entry["sourceIndex"] for entry in entries] == [0, 1, 2]
    assert "mergedOfficialTokens" not in entries[0]
    assert "mergedOfficialTokens" not in entries[1]
    assert report["matchTypeCounts"]["merged"] == 0
    assert report["reviewItems"] == []


def test_optional_report_metadata_is_included_when_provided():
    module = _load_reconcile_module()

    report = module.reconcile_transcript(
        _official("good morning"),
        _asr_words(["good", "morning"]),
        section=1,
        source_evidence="section-01/small/asr-timing-evidence.json",
        review_artifact="section-01/small/alignment-review.json",
        model="small",
        source_audio="assets/audio/section-01.mp3",
        generated_at="2026-06-18T08:00:00Z",
    )

    assert report["sourceEvidence"] == "section-01/small/asr-timing-evidence.json"
    assert report["reviewArtifact"] == "section-01/small/alignment-review.json"
    assert report["model"] == "small"
    assert report["sourceAudio"] == "assets/audio/section-01.mp3"
    assert report["generatedAt"] == "2026-06-18T08:00:00Z"


def test_reconcile_transcript_carries_asr_runtime_seconds_into_report_metrics():
    module = _load_reconcile_module()
    asr_payload = _asr_words(["good", "morning"])
    asr_payload["metrics"] = {"runtimeSeconds": 12.345}

    report = module.reconcile_transcript(_official("good morning"), asr_payload, section=1)

    assert report["metrics"]["runtimeSeconds"] == 12.345


def test_interpolation_auto_fills_small_low_risk_gap_between_close_anchors():
    module = _load_reconcile_module()

    report = module.reconcile_transcript(
        _official("alpha bravo charlie delta echo"),
        _asr_timed([("alpha", 0.0, 0.2), ("echo", 2.2, 2.4)]),
        section=1,
    )
    entries = _entries(report)
    gap = entries[1:4]

    assert [entry["token"] for entry in gap] == ["bravo", "charlie", "delta"]
    assert [entry["matchType"] for entry in gap] == ["interpolated", "interpolated", "interpolated"]
    assert all(entry["requiresReview"] is False for entry in gap)
    assert entries[0]["matchType"] == "exact"
    assert entries[-1]["matchType"] == "exact"
    assert gap[0]["start"] >= entries[0]["end"]
    assert gap[-1]["end"] <= entries[-1]["start"]
    assert report["metrics"]["longestUnanchoredGap"] == 3
    assert not any(item["decision"] == "pending" for item in report["reviewItems"])


def test_interpolation_with_overlapping_anchors_requires_pending_review():
    module = _load_reconcile_module()

    report = module.reconcile_transcript(
        _official("alpha bravo echo"),
        _asr_timed([("alpha", 1.0, 1.3), ("echo", 1.2, 1.5)]),
        section=1,
    )
    gap = _entries(report)[1]

    assert gap["token"] == "bravo"
    assert gap["matchType"] == "unmatched"
    assert gap["start"] is None
    assert gap["end"] is None
    assert gap["requiresReview"] is True
    assert report["gateOutcome"] == "needs-review"
    assert any(
        item["decision"] == "pending"
        and item["officialToken"]["text"] == "bravo"
        and "overlapping-anchors" in item["reasons"]
        for item in report["reviewItems"]
    )
    assert "pending-review" in report["blockingReasons"]


@pytest.mark.parametrize(
    ("official", "asr", "expected_reason"),
    [
        (
            "alpha bravo charlie delta echo foxtrot",
            [("alpha", 0.0, 0.2), ("foxtrot", 2.2, 2.4)],
            "gap-too-wide",
        ),
        (
            "alpha bravo echo",
            [("alpha", 0.0, 0.2), ("echo", 3.1, 3.3)],
            "anchor-span-too-wide",
        ),
        (
            "alpha co-op echo",
            [("alpha", 0.0, 0.2), ("echo", 2.2, 2.4)],
            "risk:hyphenated",
        ),
    ],
)
def test_interpolation_failed_conditions_create_pending_review(official, asr, expected_reason):
    module = _load_reconcile_module()

    report = module.reconcile_transcript(_official(official), _asr_timed(asr), section=1)
    gap_entries = [entry for entry in _entries(report) if entry["matchType"] != "exact"]
    pending = [item for item in report["reviewItems"] if item["decision"] == "pending"]

    assert gap_entries
    assert all(entry["requiresReview"] is True for entry in gap_entries)
    assert pending
    assert any(expected_reason in item["reasons"] for item in pending)
    assert report["metrics"]["pendingReviewRate"] > 0
