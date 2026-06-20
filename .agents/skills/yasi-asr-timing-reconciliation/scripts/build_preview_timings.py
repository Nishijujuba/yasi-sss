#!/usr/bin/env python3
"""Build an LLM pre-review timing preview asset for Transcript Shadowing."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TIMING_SCHEMA_VERSION = "yasi.transcript-timings.v1"
REVIEW_SCHEMA_VERSION = "yasi.alignment-review.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: Any) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _identity_from_entry(section: int, entry: dict[str, Any]) -> tuple[int, int, int] | None:
    segment_order = entry.get("segmentOrder")
    token_index = entry.get("tokenIndex")
    if isinstance(segment_order, int) and isinstance(token_index, int):
        return section, segment_order, token_index
    return None


def _identity_from_review(item: dict[str, Any]) -> tuple[int, int, int] | None:
    official = item.get("officialToken") if isinstance(item.get("officialToken"), dict) else {}
    section = official.get("section", item.get("section"))
    segment_order = official.get("segmentOrder")
    token_index = official.get("tokenIndex")
    if isinstance(section, int) and isinstance(segment_order, int) and isinstance(token_index, int):
        return section, segment_order, token_index
    return None


def _review_map(review_payload: dict[str, Any]) -> dict[tuple[int, int, int], dict[str, Any]]:
    out: dict[tuple[int, int, int], dict[str, Any]] = {}
    for section_payload in review_payload.get("sections") or []:
        if not isinstance(section_payload, dict):
            continue
        for item in section_payload.get("mappingReviews") or []:
            if not isinstance(item, dict):
                continue
            identity = _identity_from_review(item)
            if identity is not None:
                out[identity] = item
    return out


def _review_marker(review_input: str | Path, item: dict[str, Any]) -> dict[str, Any]:
    screening = item.get("screening") if isinstance(item.get("screening"), dict) else {}
    marker = {
        "reviewArtifact": artifact_path_string(review_input),
        "reviewId": item.get("reviewId"),
        "decision": item.get("decision") or "pending",
        "tier": screening.get("tier"),
        "riskTypes": list(item.get("riskTypes") or []),
        "reasons": list(item.get("reasons") or []),
    }
    llm_suggestion = screening.get("llmSuggestion")
    if isinstance(llm_suggestion, dict):
        marker["llmSuggestion"] = llm_suggestion
    return marker


def _preview_counts(sections: list[dict[str, Any]]) -> tuple[int, int]:
    marker_count = 0
    untimed_marker_count = 0
    for section_payload in sections:
        for entry in section_payload.get("wordTimings") or []:
            if not isinstance(entry, dict) or not entry.get("requiresReview"):
                continue
            marker_count += 1
            if entry.get("start") is None or entry.get("end") is None:
                untimed_marker_count += 1
    return marker_count, untimed_marker_count


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def sanitize_preview_interval(entry: dict[str, Any]) -> None:
    start = _number(entry.get("start"))
    end = _number(entry.get("end"))
    if start is None and end is None:
        return
    reason = None
    if start is None or end is None:
        reason = "missing-timing"
    elif end <= start:
        reason = "non-positive-interval"
    if reason is None:
        return
    entry["start"] = None
    entry["end"] = None
    entry["requiresReview"] = True
    reasons = list(entry.get("reasons") or [])
    if reason not in reasons:
        reasons.append(reason)
    entry["reasons"] = reasons


def _section_sort_key(section_payload: dict[str, Any]) -> int:
    section = section_payload.get("section")
    return int(section) if isinstance(section, int) else 0


def artifact_path_string(path: str | Path) -> str:
    return Path(path).as_posix()


def merge_preview_timings(
    *,
    existing_payload: dict[str, Any],
    next_payload: dict[str, Any],
) -> dict[str, Any]:
    if existing_payload.get("schemaVersion") != TIMING_SCHEMA_VERSION:
        raise ValueError(f"existing timing schemaVersion must be {TIMING_SCHEMA_VERSION!r}")
    if next_payload.get("schemaVersion") != TIMING_SCHEMA_VERSION:
        raise ValueError(f"next timing schemaVersion must be {TIMING_SCHEMA_VERSION!r}")
    if existing_payload.get("status") != "preview" or next_payload.get("status") != "preview":
        raise ValueError("existing and next timing payloads must both have preview status")

    merged = copy.deepcopy(existing_payload)
    sections_by_number: dict[int, dict[str, Any]] = {}
    for section_payload in existing_payload.get("sections") or []:
        if isinstance(section_payload, dict) and isinstance(section_payload.get("section"), int):
            sections_by_number[int(section_payload["section"])] = copy.deepcopy(section_payload)
    for section_payload in next_payload.get("sections") or []:
        if isinstance(section_payload, dict) and isinstance(section_payload.get("section"), int):
            sections_by_number[int(section_payload["section"])] = copy.deepcopy(section_payload)

    merged["generatedAt"] = next_payload.get("generatedAt") or existing_payload.get("generatedAt")
    merged["sections"] = sorted(sections_by_number.values(), key=_section_sort_key)
    merged["reviewItems"] = []

    review_artifacts: dict[str, str] = {}
    existing_artifacts = existing_payload.get("reviewArtifacts")
    if isinstance(existing_artifacts, dict):
        review_artifacts.update({str(key): artifact_path_string(str(value)) for key, value in existing_artifacts.items()})
    elif isinstance(existing_payload.get("reviewArtifact"), str):
        for section_payload in existing_payload.get("sections") or []:
            section = section_payload.get("section") if isinstance(section_payload, dict) else None
            if isinstance(section, int):
                review_artifacts[str(section)] = artifact_path_string(str(existing_payload["reviewArtifact"]))

    next_review_artifact = next_payload.get("reviewArtifact")
    if isinstance(next_review_artifact, str):
        for section_payload in next_payload.get("sections") or []:
            section = section_payload.get("section") if isinstance(section_payload, dict) else None
            if isinstance(section, int):
                review_artifacts[str(section)] = artifact_path_string(next_review_artifact)
    if review_artifacts:
        merged["reviewArtifacts"] = dict(sorted(review_artifacts.items(), key=lambda item: int(item[0])))
    unique_artifacts = set(review_artifacts.values())
    if len(unique_artifacts) == 1:
        merged["reviewArtifact"] = next(iter(unique_artifacts))
    elif "reviewArtifact" in merged:
        del merged["reviewArtifact"]

    marker_count, untimed_marker_count = _preview_counts(merged["sections"])
    merged["preview"] = {
        "mode": "llm-pre-review",
        "warning": "Preview timings are available for Transcript Shadowing with uncertainty markers. They are not verified release timings.",
        "reviewStatus": next_payload.get("preview", {}).get("reviewStatus"),
        "reviewMarkerCount": marker_count,
        "untimedReviewMarkerCount": untimed_marker_count,
    }
    return merged


def build_preview_timings(
    *,
    draft_payload: dict[str, Any],
    review_payload: dict[str, Any],
    review_input: Path,
    existing_payload: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    if draft_payload.get("schemaVersion") != TIMING_SCHEMA_VERSION:
        raise ValueError(f"draft timing schemaVersion must be {TIMING_SCHEMA_VERSION!r}")
    if review_payload.get("schemaVersion") != REVIEW_SCHEMA_VERSION:
        raise ValueError(f"review artifact schemaVersion must be {REVIEW_SCHEMA_VERSION!r}")

    review_by_identity = _review_map(review_payload)
    sections: list[dict[str, Any]] = []
    marker_count = 0
    untimed_marker_count = 0

    for section_payload in draft_payload.get("sections") or []:
        if not isinstance(section_payload, dict):
            continue
        section = int(section_payload["section"])
        word_timings: list[dict[str, Any]] = []
        for raw_entry in section_payload.get("wordTimings") or []:
            if not isinstance(raw_entry, dict):
                continue
            entry = copy.deepcopy(raw_entry)
            review_item = review_by_identity.get(_identity_from_entry(section, entry))
            if review_item is not None:
                decision = review_item.get("decision")
                if decision in {"approved", "corrected"}:
                    entry["requiresReview"] = False
                else:
                    marker_count += 1
                    if entry.get("start") is None or entry.get("end") is None:
                        untimed_marker_count += 1
                    entry["requiresReview"] = True
                    entry["matchType"] = review_item.get("matchType", entry.get("matchType"))
                    entry["riskTypes"] = list(review_item.get("riskTypes") or entry.get("riskTypes") or [])
                    entry["reasons"] = list(review_item.get("reasons") or entry.get("reasons") or [])
                    entry["review"] = _review_marker(review_input, review_item)
            sanitize_preview_interval(entry)
            word_timings.append(entry)
        sections.append(
            {
                "section": section,
                "status": "preview",
                "wordTimings": word_timings,
                "reviewItems": [],
                "diagnostics": {
                    "previewReviewMarkerCount": marker_count,
                    "previewUntimedReviewMarkerCount": untimed_marker_count,
                },
            }
        )

    marker_count, untimed_marker_count = _preview_counts(sections)
    payload = {
        "schemaVersion": TIMING_SCHEMA_VERSION,
        "status": "preview",
        "generatedAt": generated_at or utc_now(),
        "reviewArtifact": artifact_path_string(review_input),
        "preview": {
            "mode": "llm-pre-review",
            "warning": "Preview timings are available for Transcript Shadowing with uncertainty markers. They are not verified release timings.",
            "reviewStatus": review_payload.get("status"),
            "reviewMarkerCount": marker_count,
            "untimedReviewMarkerCount": untimed_marker_count,
        },
        "sections": sections,
        "reviewItems": [],
    }
    if existing_payload is not None:
        return merge_preview_timings(existing_payload=existing_payload, next_payload=payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build transcript-timings.preview.json from draft timings and a screened or LLM-pre-reviewed alignment review.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--draft-input", type=Path, required=True)
    parser.add_argument("--review-input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--merge-existing", type=Path)
    parser.add_argument("--generated-at", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_preview_timings(
        draft_payload=load_json(args.draft_input),
        review_payload=load_json(args.review_input),
        review_input=args.review_input,
        existing_payload=load_json(args.merge_existing) if args.merge_existing else None,
        generated_at=args.generated_at,
    )
    write_json(args.output, payload)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "status": payload["status"],
                "sections": len(payload["sections"]),
                "reviewMarkerCount": payload["preview"]["reviewMarkerCount"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
