from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from builder.intensive_listening import (
    INTENSIVE_LISTENING_SCHEMA_VERSION,
    IntensiveListeningBuildError,
    build_intensive_listening_asset,
    export_intensive_listening,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _unique_test_dir(name: str) -> Path:
    path = Path("tmp") / "test-runs" / f"{name}-{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    return path


def _transcript_payload() -> list[dict]:
    return [
        {
            "section": 1,
            "source": {"pages": [1]},
            "segments": [
                {
                    "order": 1,
                    "speaker": None,
                    "text": "Remember your photo card.",
                    "answerRefs": [],
                    "startTime": None,
                    "endTime": None,
                }
            ],
            "review": {"status": "reviewed"},
        },
        {
            "section": 2,
            "source": {"pages": [2]},
            "segments": [
                {
                    "order": 1,
                    "speaker": None,
                    "text": "Alpha beta gamma.",
                    "answerRefs": [],
                    "startTime": None,
                    "endTime": None,
                }
            ],
            "review": {"status": "reviewed"},
        },
        {
            "section": 3,
            "source": {"pages": [3]},
            "segments": [
                {
                    "order": 1,
                    "speaker": None,
                    "text": "Carbon dioxide returns.",
                    "answerRefs": [],
                    "startTime": None,
                    "endTime": None,
                }
            ],
            "review": {"status": "reviewed"},
        },
        {
            "section": 4,
            "source": {"pages": [4]},
            "segments": [
                {
                    "order": 1,
                    "speaker": None,
                    "text": "Old-growth rainforest matters.",
                    "answerRefs": [],
                    "startTime": None,
                    "endTime": None,
                }
            ],
            "review": {"status": "reviewed"},
        },
    ]


def _candidate(
    section: int,
    *,
    text: str,
    start: int,
    end: int,
    segment_order: int = 1,
) -> dict:
    return {
        "section": section,
        "segmentOrder": segment_order,
        "startTokenIndex": start,
        "endTokenIndex": end,
        "text": text,
        "reason": "High-value listening and spelling target.",
        "tags": ["spelling-risk"],
    }


def _valid_candidates() -> list[dict]:
    return [
        _candidate(1, text="PHOTO CARD", start=2, end=4),
        _candidate(2, text="Alpha", start=0, end=1),
        _candidate(3, text="carbon dioxide", start=0, end=2),
        _candidate(4, text="Old-growth", start=0, end=1),
    ]


def _candidate_source(section: int, candidates: list[dict]) -> dict:
    return {
        "schemaVersion": "yasi.intensive-listening-candidates.v1",
        "section": section,
        "candidates": candidates,
    }


def test_build_asset_derives_answer_and_stable_id_from_official_span():
    asset = build_intensive_listening_asset(_transcript_payload(), _valid_candidates())

    payload = asset.model_dump(mode="json")
    section_one_blank = payload["sections"][0]["blanks"][0]

    assert payload["schemaVersion"] == INTENSIVE_LISTENING_SCHEMA_VERSION
    assert section_one_blank["id"] == "il-s01-seg001-t002-t004"
    assert section_one_blank["answer"] == "photo card"
    assert section_one_blank["acceptedVariants"] == []
    assert section_one_blank["reason"] == "High-value listening and spelling target."
    assert section_one_blank["tags"] == ["spelling-risk"]


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda item: item.update({"section": 5}), "section"),
        (lambda item: item.update({"segmentOrder": 99}), "segment"),
        (lambda item: item.update({"startTokenIndex": 4, "endTokenIndex": 4}), "token range"),
        (lambda item: item.update({"endTokenIndex": 99}), "token range"),
        (lambda item: item.update({"text": "parking card"}), "candidate text"),
        (lambda item: item.update({"reason": "   "}), "reason"),
        (lambda item: item.update({"tags": []}), "tags"),
        (lambda item: item.update({"tags": ["spelling-risk", "spelling-risk"]}), "tags"),
        (lambda item: item.update({"tags": ["Spelling Risk"]}), "tags"),
    ],
)
def test_build_asset_rejects_invalid_candidates(mutate, message):
    candidates = _valid_candidates()
    mutate(candidates[0])

    with pytest.raises(IntensiveListeningBuildError, match=message):
        build_intensive_listening_asset(_transcript_payload(), candidates)


def test_build_asset_rejects_duplicate_generated_ids():
    candidates = _valid_candidates()
    candidates.append(dict(candidates[0]))

    with pytest.raises(IntensiveListeningBuildError, match="duplicate"):
        build_intensive_listening_asset(_transcript_payload(), candidates)


def test_build_asset_rejects_overlapping_blanks_in_same_section():
    candidates = _valid_candidates()
    candidates.append(_candidate(1, text="your photo", start=1, end=3))

    with pytest.raises(IntensiveListeningBuildError, match="overlap"):
        build_intensive_listening_asset(_transcript_payload(), candidates)


def test_export_intensive_listening_reads_four_candidate_sources_and_writes_asset():
    root = _unique_test_dir("intensive-export")
    source_dir = root / "source"
    pack_root = root / "pack"
    _write_json(pack_root / "transcript.json", _transcript_payload())

    for section, candidate in enumerate(_valid_candidates(), start=1):
        _write_json(
            source_dir / f"intensive-listening-candidates-section-{section:02d}.json",
            _candidate_source(section, [candidate]),
        )

    asset = export_intensive_listening(output_root=pack_root, source_dir=source_dir)

    written = json.loads((pack_root / "intensive-listening.json").read_text(encoding="utf-8"))
    assert asset.schemaVersion == INTENSIVE_LISTENING_SCHEMA_VERSION
    assert written["sections"][0]["blanks"][0]["id"] == "il-s01-seg001-t002-t004"
