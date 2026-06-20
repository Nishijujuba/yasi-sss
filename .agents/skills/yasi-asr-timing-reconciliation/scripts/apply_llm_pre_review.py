#!/usr/bin/env python3
"""Attach advisory LLM pre-review metadata to alignment-review.json."""

from __future__ import annotations

import argparse
import copy
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REVIEW_SCHEMA_VERSION = "yasi.alignment-review.v1"
DEFAULT_REVIEWER = "llm-pre-review"
VALID_DECISIONS = {"approved", "corrected", "needs-human"}
VALID_LABELS = {"likely-safe", "needs-auditory-review", "needs-manual-timing", "reject-evidence"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: Any) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        candidate = float(value)
        if math.isfinite(candidate):
            return candidate
    return None


def _valid_correction(value: Any) -> dict[str, float] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("correction must be null or an object")
    start = _finite_number(value.get("start"))
    end = _finite_number(value.get("end"))
    if start is None or end is None or end <= start:
        raise ValueError("correction must contain positive numeric start and end")
    return {"start": start, "end": end}


def _looks_like_suggestion(value: dict[str, Any]) -> bool:
    return "reviewId" in value and (
        "suggestedDecision" in value or "preReviewLabel" in value or "confidence" in value
    )


def _flatten_suggestions(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        out: list[dict[str, Any]] = []
        for entry in value:
            out.extend(_flatten_suggestions(entry))
        return out
    if not isinstance(value, dict):
        return []
    if _looks_like_suggestion(value):
        return [value]
    for key in ("suggestions", "items", "results"):
        nested = value.get(key)
        if isinstance(nested, list):
            return _flatten_suggestions(nested)
    return []


def load_suggestions(path: str | Path) -> list[dict[str, Any]]:
    text = Path(path).read_text(encoding="utf-8").strip()
    if not text:
        return []
    try:
        return _flatten_suggestions(json.loads(text))
    except json.JSONDecodeError:
        suggestions: list[dict[str, Any]] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                suggestions.extend(_flatten_suggestions(json.loads(line)))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at line {line_number}: {exc}") from exc
        return suggestions


def normalize_suggestion(raw: dict[str, Any], *, reviewer: str, reviewed_at: str) -> dict[str, Any]:
    review_id = raw.get("reviewId")
    if not isinstance(review_id, str) or not review_id:
        raise ValueError("suggestion.reviewId is required")

    decision = raw.get("suggestedDecision")
    if decision not in VALID_DECISIONS:
        raise ValueError(f"{review_id}: suggestedDecision must be one of {sorted(VALID_DECISIONS)}")

    confidence = _finite_number(raw.get("confidence"))
    if confidence is None or confidence < 0 or confidence > 1:
        raise ValueError(f"{review_id}: confidence must be a number from 0 to 1")

    label = raw.get("preReviewLabel")
    if label is None:
        label = "needs-auditory-review" if decision == "needs-human" else "likely-safe"
    if label not in VALID_LABELS:
        raise ValueError(f"{review_id}: preReviewLabel must be one of {sorted(VALID_LABELS)}")

    notes = raw.get("notes")
    if notes is not None and not isinstance(notes, str):
        raise ValueError(f"{review_id}: notes must be a string")

    return {
        "advisory": True,
        "reviewId": review_id,
        "source": reviewer,
        "reviewedAt": reviewed_at,
        "suggestedDecision": decision,
        "confidence": confidence,
        "preReviewLabel": label,
        "notes": notes or "",
        "correction": _valid_correction(raw.get("correction")),
    }


def iter_mapping_reviews(review_payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for section in review_payload.get("sections") or []
        if isinstance(section, dict)
        for item in section.get("mappingReviews") or []
        if isinstance(item, dict)
    ]


def attach_llm_pre_review(
    review_payload: dict[str, Any],
    suggestions: list[dict[str, Any]],
    *,
    reviewer: str = DEFAULT_REVIEWER,
    reviewed_at: str | None = None,
) -> dict[str, Any]:
    if review_payload.get("schemaVersion") != REVIEW_SCHEMA_VERSION:
        raise ValueError(f"review artifact schemaVersion must be {REVIEW_SCHEMA_VERSION!r}")

    reviewed_at = reviewed_at or utc_now()
    out = copy.deepcopy(review_payload)
    by_id = {str(item.get("reviewId")): item for item in iter_mapping_reviews(out) if item.get("reviewId")}
    normalized = [normalize_suggestion(raw, reviewer=reviewer, reviewed_at=reviewed_at) for raw in suggestions]

    matched = 0
    unmatched: list[str] = []
    seen_ids: set[str] = set()
    for suggestion in normalized:
        review_id = str(suggestion["reviewId"])
        if review_id in seen_ids:
            continue
        seen_ids.add(review_id)
        if review_id not in by_id:
            unmatched.append(review_id)
            continue
        screening = by_id[review_id].setdefault("screening", {})
        if not isinstance(screening, dict):
            screening = {}
            by_id[review_id]["screening"] = screening
        screening["llmSuggestion"] = suggestion
        matched += 1

    return {
        "review": out,
        "report": {
            "schemaVersion": "yasi.llm-pre-review-apply-report.v1",
            "reviewer": reviewer,
            "reviewedAt": reviewed_at,
            "summary": {
                "suggestions": len(normalized),
                "matched": matched,
                "unmatched": len(unmatched),
                "decisionsChanged": 0,
            },
            "unmatchedReviewIds": unmatched,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Attach advisory LLM pre-review results to alignment-review.json without changing decisions.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--review-input", type=Path, required=True)
    parser.add_argument("--llm-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path)
    parser.add_argument("--reviewer", default=DEFAULT_REVIEWER)
    parser.add_argument("--reviewed-at", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = attach_llm_pre_review(
        load_json(args.review_input),
        load_suggestions(args.llm_output),
        reviewer=args.reviewer,
        reviewed_at=args.reviewed_at,
    )
    write_json(args.output, result["review"])
    if args.report_output is not None:
        write_json(args.report_output, result["report"])
    print(json.dumps(result["report"]["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
