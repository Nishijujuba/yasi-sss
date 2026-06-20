from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECT_PYTHON = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
SCRIPT = (
    REPO_ROOT
    / ".agents"
    / "skills"
    / "yasi-asr-timing-reconciliation"
    / "scripts"
    / "asr_timing_reconcile.py"
)
PACK_ID = "cambridge-10-test-1-listening"
REVIEW_RELATIVE = f"build/review/transcript-timing/{PACK_ID}/alignment-review.json"


def unique_test_dir(name: str) -> Path:
    path = REPO_ROOT / "tmp" / "test-runs" / f"{name}-{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    return path


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def project_python() -> str:
    if PROJECT_PYTHON.exists():
        return str(PROJECT_PYTHON)
    return sys.executable


def sample_evidence() -> dict:
    words = "Good morning World Tours My name is Jamie How can I help you".split()
    return {
        "schemaVersion": "yasi.asr-timing-evidence.v1",
        "engine": "whisper",
        "model": "small",
        "sourceAudio": "public/packs/cambridge-10/test-1/listening/assets/audio/section-01.mp3",
        "generatedAt": "2026-06-18T00:00:00Z",
        "words": [
            {
                "index": index,
                "word": word,
                "start": round(index * 0.32, 3),
                "end": round(index * 0.32 + 0.2, 3),
            }
            for index, word in enumerate(words)
        ],
    }


def auto_entry(
    *,
    token: str,
    token_index: int,
    global_token_index: int,
    start: float,
    end: float,
    match_type: str = "exact",
    requires_review: bool = False,
    risk_types: list[str] | None = None,
) -> dict:
    return {
        "section": 1,
        "segmentOrder": 1,
        "tokenIndex": token_index,
        "globalTokenIndex": global_token_index,
        "token": token,
        "normalized": token.lower(),
        "answerRefs": [],
        "riskTypes": risk_types or [],
        "start": start,
        "end": end,
        "sourceIndex": global_token_index,
        "sourceWord": token,
        "sourceNormalized": token.lower(),
        "matchType": match_type,
        "match": match_type,
        "requiresReview": requires_review,
    }


def review_item_for(entry: dict, *, decision: str, correction: dict | None = None) -> dict:
    return {
        "reviewId": f"s01-g{entry['globalTokenIndex']:04d}",
        "section": entry["section"],
        "matchType": entry["matchType"],
        "decision": decision,
        "officialToken": {
            "section": entry["section"],
            "segmentOrder": entry["segmentOrder"],
            "tokenIndex": entry["tokenIndex"],
            "globalTokenIndex": entry["globalTokenIndex"],
            "text": entry["token"],
            "normalized": entry["normalized"],
            "answerRefs": [],
        },
        "sourceWord": {
            "sourceIndex": entry["sourceIndex"],
            "word": entry["sourceWord"],
            "normalized": entry["sourceNormalized"],
            "start": entry["start"],
            "end": entry["end"],
        },
        "timing": {"start": entry["start"], "end": entry["end"]},
        "riskTypes": entry["riskTypes"],
        "reasons": ["match:fuzzy"] if entry["matchType"] == "fuzzy" else [],
        "correction": correction,
    }


def write_review_artifact(path: Path, *, decision: str = "corrected") -> None:
    good = auto_entry(token="Good", token_index=0, global_token_index=0, start=0.1, end=0.3)
    morning = auto_entry(
        token="morning",
        token_index=1,
        global_token_index=1,
        start=0.31,
        end=0.55,
        match_type="fuzzy",
        requires_review=True,
        risk_types=["answer-near"],
    )
    correction = {"start": 0.32, "end": 0.58, "reviewer": "test"} if decision == "corrected" else None
    write_json(
        path,
        {
            "schemaVersion": "yasi.alignment-review.v1",
            "reviewArtifact": REVIEW_RELATIVE,
            "status": "reviewed",
            "generatedAt": "2026-06-18T00:00:00Z",
            "tool": {"name": "test"},
            "draftTimingArtifact": "transcript-timings.draft.json",
            "finalTimingArtifact": "transcript-timings.json",
            "sections": [
                {
                    "section": 1,
                    "status": "reviewed",
                    "autoMapping": {
                        "schemaVersion": "yasi.transcript-timings.v1",
                        "status": "draft",
                        "wordTimings": [good, morning],
                        "reviewItems": [review_item_for(morning, decision="pending")],
                        "diagnostics": {},
                    },
                    "mappingReviews": [
                        review_item_for(morning, decision=decision, correction=correction)
                    ],
                }
            ],
        },
    )


def write_empty_auto_mapping_review_artifact(path: Path) -> None:
    write_json(
        path,
        {
            "schemaVersion": "yasi.alignment-review.v1",
            "reviewArtifact": REVIEW_RELATIVE,
            "status": "reviewed",
            "generatedAt": "2026-06-18T00:00:00Z",
            "tool": {"name": "test"},
            "draftTimingArtifact": "transcript-timings.draft.json",
            "finalTimingArtifact": "transcript-timings.json",
            "sections": [
                {
                    "section": 1,
                    "status": "reviewed",
                    "autoMapping": {
                        "schemaVersion": "yasi.transcript-timings.v1",
                        "status": "draft",
                        "wordTimings": [],
                        "reviewItems": [],
                        "diagnostics": {},
                    },
                    "mappingReviews": [],
                }
            ],
        },
    )


def write_manifest(path: Path, *, pack_id: str) -> None:
    write_json(
        path,
        {
            "packId": pack_id,
            "schemaVersion": 1,
            "status": "released",
            "title": "Test Pack",
            "sections": [],
            "assets": {"transcript": "transcript.json"},
            "build": {
                "sourceCommit": "test",
                "builtAt": "2026-06-18T00:00:00Z",
            },
        },
    )


def test_draft_cli_writes_reconciliation_review_and_draft_outputs():
    run_dir = unique_test_dir("asr-draft-cli")
    evidence_path = run_dir / "asr-timing-evidence.json"
    write_json(evidence_path, sample_evidence())

    completed = subprocess.run(
        [
            project_python(),
            str(SCRIPT),
            "--section",
            "1",
            "--model",
            "small",
            "--evidence-input",
            str(evidence_path),
            "--draft",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    report = read_json(run_dir / "reconciliation-report.json")
    review = read_json(run_dir / "alignment-review.json")
    draft = read_json(run_dir / "transcript-timings.draft.json")

    assert report["schemaVersion"] == "yasi.reconciliation-report.v1"
    assert report["model"] == "small"
    assert report["reviewArtifact"] == REVIEW_RELATIVE
    assert draft["schemaVersion"] == "yasi.transcript-timings.v1"
    assert draft["status"] == "draft"
    assert draft["reviewArtifact"] == REVIEW_RELATIVE
    assert review["schemaVersion"] == "yasi.alignment-review.v1"
    assert review["reviewArtifact"] == REVIEW_RELATIVE
    assert review["sections"][0].keys() >= {"section", "autoMapping", "mappingReviews"}
    assert review["sections"][0]["mappingReviews"]
    first_review = review["sections"][0]["mappingReviews"][0]
    assert first_review.keys() >= {
        "reviewId",
        "matchType",
        "decision",
        "officialToken",
        "timing",
        "riskTypes",
        "reasons",
        "correction",
    }
    assert first_review["decision"] == "pending"


def test_finalize_review_applies_correction_and_promotes_review_artifacts():
    run_dir = unique_test_dir("asr-finalize-cli")
    repo_root = run_dir / "repo-root"
    review_input = run_dir / "alignment-review.json"
    output = run_dir / "public" / "packs" / "cambridge-10" / "test-1" / "listening" / "transcript-timings.json"
    write_review_artifact(review_input, decision="corrected")
    write_json(run_dir / "reconciliation-report.json", {"schemaVersion": "yasi.reconciliation-report.v1"})

    completed = subprocess.run(
        [
            project_python(),
            str(SCRIPT),
            "--finalize-review",
            "--review-input",
            str(review_input),
            "--output",
            str(output),
            "--repo-root",
            str(repo_root),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    final_payload = read_json(output)
    promoted_review = read_json(repo_root / REVIEW_RELATIVE)
    promoted_report = read_json(
        repo_root
        / "build"
        / "review"
        / "transcript-timing"
        / PACK_ID
        / "reconciliation-report.json"
    )

    assert final_payload["schemaVersion"] == "yasi.transcript-timings.v1"
    assert final_payload["status"] == "verified"
    assert final_payload["reviewArtifact"] == REVIEW_RELATIVE
    corrected = final_payload["sections"][0]["wordTimings"][1]
    assert corrected["start"] == 0.32
    assert corrected["end"] == 0.58
    assert corrected["review"]["decision"] == "corrected"
    assert corrected["review"]["reviewArtifact"] == REVIEW_RELATIVE
    assert promoted_review["reviewArtifact"] == REVIEW_RELATIVE
    assert promoted_report["reviewArtifact"] == REVIEW_RELATIVE


def test_finalize_review_uses_supplied_repo_root_for_default_pack_metadata():
    run_dir = unique_test_dir("asr-finalize-root")
    repo_root = run_dir / "repo-root"
    pack_root = repo_root / "public" / "packs" / "cambridge-10" / "test-1" / "listening"
    custom_pack_id = "custom-pack"
    review_input = run_dir / "alignment-review.json"
    output = run_dir / "transcript-timings.json"
    write_manifest(pack_root / "manifest.json", pack_id=custom_pack_id)
    write_review_artifact(review_input, decision="approved")

    completed = subprocess.run(
        [
            project_python(),
            str(SCRIPT),
            "--finalize-review",
            "--review-input",
            str(review_input),
            "--output",
            str(output),
            "--repo-root",
            str(repo_root),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    final_payload = read_json(output)

    assert final_payload["packRoot"] == "public/packs/cambridge-10/test-1/listening"
    assert final_payload["transcript"] == "public/packs/cambridge-10/test-1/listening/transcript.json"
    assert final_payload["reviewArtifact"] == (
        "build/review/transcript-timing/custom-pack/alignment-review.json"
    )


def test_finalize_review_rejects_empty_auto_mapping_word_timings():
    run_dir = unique_test_dir("asr-finalize-empty-mapping")
    review_input = run_dir / "alignment-review.json"
    output = run_dir / "transcript-timings.json"
    write_empty_auto_mapping_review_artifact(review_input)

    completed = subprocess.run(
        [
            project_python(),
            str(SCRIPT),
            "--finalize-review",
            "--review-input",
            str(review_input),
            "--output",
            str(output),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "wordTimings" in completed.stderr
    assert not output.exists()


def test_finalize_review_blocks_pending_or_rejected_decisions():
    run_dir = unique_test_dir("asr-finalize-blocks")
    review_input = run_dir / "alignment-review.json"
    output = run_dir / "transcript-timings.json"
    write_review_artifact(review_input, decision="pending")

    completed = subprocess.run(
        [
            project_python(),
            str(SCRIPT),
            "--finalize-review",
            "--review-input",
            str(review_input),
            "--output",
            str(output),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "pending" in completed.stderr
    assert not output.exists()
