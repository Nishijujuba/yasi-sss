import json
from pathlib import Path, PurePosixPath


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = (
    REPO_ROOT
    / ".agents"
    / "skills"
    / "yasi-asr-timing-reconciliation"
    / "fixtures"
)
GATE_OUTCOMES = {"ready-for-finalize", "needs-review", "rerun-asr"}
MATCH_TYPES = {"exact", "fuzzy", "interpolated", "split", "merged", "unmatched"}
REVIEW_DECISIONS = {"pending", "approved", "corrected", "rejected"}


def load_fixture(name):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def assert_repo_root_relative_review_artifact(path_text):
    path = PurePosixPath(path_text)
    assert not path.is_absolute()
    assert path.parts[:3] == ("build", "review", "transcript-timing")
    assert path.name == "alignment-review.json"


def test_asr_timing_evidence_contract():
    payload = load_fixture("sample-asr-timing-evidence.json")

    assert payload["schemaVersion"] == "yasi.asr-timing-evidence.v1"
    assert payload["engine"] == "whisper"
    assert payload["model"] in {"small", "medium", "large-v3"}
    assert payload["sourceAudio"].endswith("section-01.mp3")
    assert payload["words"]
    assert payload["words"][0].keys() >= {"index", "word", "normalized", "start", "end"}


def test_reconciliation_report_contract():
    payload = load_fixture("sample-reconciliation-report.json")

    assert payload["schemaVersion"] == "yasi.reconciliation-report.v1"
    assert payload["gateOutcome"] in GATE_OUTCOMES
    assert payload["matchTypeCounts"].keys() >= MATCH_TYPES
    assert payload["metrics"]["anchorCoverage"] >= 0
    assert_repo_root_relative_review_artifact(payload["reviewArtifact"])


def test_alignment_review_contract():
    payload = load_fixture("sample-alignment-review.json")

    assert payload["schemaVersion"] == "yasi.alignment-review.v1"
    assert_repo_root_relative_review_artifact(payload["reviewArtifact"])
    assert "mappingReviews" not in payload
    if "summary" in payload:
        assert isinstance(payload["summary"], dict)
    assert payload["sections"]
    review_ids = set()
    for section in payload["sections"]:
        assert section["section"] in {1, 2, 3, 4}
        assert section["status"] in {"pending", "reviewed"}
        assert section["mappingReviews"]
        for item in section["mappingReviews"]:
            assert item.keys() >= {
                "reviewId",
                "matchType",
                "decision",
                "officialToken",
                "riskTypes",
                "sourceWord",
                "timing",
                "correction",
            }
            assert item["reviewId"]
            assert item["reviewId"] not in review_ids
            review_ids.add(item["reviewId"])
            assert item["matchType"] in MATCH_TYPES
            assert item["decision"] in REVIEW_DECISIONS
            assert isinstance(item["riskTypes"], list)
            assert item["officialToken"].keys() >= {
                "section",
                "segmentOrder",
                "tokenIndex",
                "globalTokenIndex",
                "text",
            }
            assert item["sourceWord"].keys() >= {"sourceIndex", "word", "start", "end"}
            assert item["timing"].keys() >= {"start", "end"}
            correction = item["correction"]
            if correction is not None:
                assert correction.keys() >= {"start", "end"}
                assert correction["end"] > correction["start"]
