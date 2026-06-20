#!/usr/bin/env python3
"""Build a static HTML review tool for unresolved alignment-review items."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = SKILL_ROOT / "tools" / "review-tool.html"
PLACEHOLDER = "window.__YASI_REVIEW_TOOL_DATA__ = null;"


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _review_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for section in payload.get("sections", [])
        if isinstance(section, dict)
        for item in section.get("mappingReviews", [])
        if isinstance(item, dict)
    ]


def _word_timings(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for section in payload.get("sections", [])
        if isinstance(section, dict)
        for item in (section.get("autoMapping") or {}).get("wordTimings", [])
        if isinstance(item, dict)
    ]


def _report_map(report: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for key in ("humanRequired", "llmCandidates", "codeApproved", "preservedReviewed"):
        for item in (report or {}).get(key, []):
            if isinstance(item, dict) and item.get("reviewId"):
                out[str(item["reviewId"])] = item
    return out


def _tier(item: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> str:
    screening = _screening(item, by_id)
    if isinstance(screening, dict) and screening.get("tier"):
        return str(screening["tier"])
    return "unclassified"


def _screening(item: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    report_record = by_id.get(str(item.get("reviewId"))) or {}
    report_screening = report_record.get("screening") if isinstance(report_record.get("screening"), dict) else {}
    item_screening = item.get("screening") if isinstance(item.get("screening"), dict) else {}
    merged: dict[str, Any] = {}
    merged.update(report_record)
    merged.update(report_screening)
    merged.update(item_screening)
    return merged


def _context(item: dict[str, Any], timings: list[dict[str, Any]], radius: int = 4) -> list[dict[str, Any]]:
    official = item.get("officialToken") if isinstance(item.get("officialToken"), dict) else {}
    target = official.get("globalTokenIndex")
    if target is None:
        return []
    target = int(target)
    out: list[dict[str, Any]] = []
    for entry in timings:
        index = entry.get("globalTokenIndex")
        if isinstance(index, int) and abs(index - target) <= radius:
            out.append(
                {
                    "globalTokenIndex": index,
                    "token": entry.get("token"),
                    "start": entry.get("start"),
                    "end": entry.get("end"),
                    "isTarget": index == target,
                }
            )
    return out


def _summary(items: list[dict[str, Any]], queue: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total": len(items),
        "pending": sum(1 for item in items if item.get("decision") == "pending"),
        "approved": sum(1 for item in items if item.get("decision") == "approved"),
        "corrected": sum(1 for item in items if item.get("decision") == "corrected"),
        "rejected": sum(1 for item in items if item.get("decision") == "rejected"),
        "queue": len(queue),
    }


def _marker_for(item: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    official = item.get("officialToken") if isinstance(item.get("officialToken"), dict) else {}
    global_token_index = official.get("globalTokenIndex")
    if not isinstance(global_token_index, int):
        return None
    screening = _screening(item, by_id)
    return {
        "globalTokenIndex": global_token_index,
        "reviewId": item.get("reviewId"),
        "decision": item.get("decision") or "pending",
        "tier": _tier(item, by_id),
        "matchType": item.get("matchType"),
        "riskTypes": list(item.get("riskTypes") or []),
        "reasons": list(item.get("reasons") or []),
        "llmSuggestion": screening.get("llmSuggestion"),
    }


def _transcript_map(
    *,
    review_items: list[dict[str, Any]],
    timings: list[dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    markers = {
        marker["globalTokenIndex"]: marker
        for item in review_items
        if item.get("decision") not in {"approved", "corrected"}
        for marker in [_marker_for(item, by_id)]
        if marker is not None
    }
    out: list[dict[str, Any]] = []
    for entry in timings:
        index = entry.get("globalTokenIndex")
        out.append(
            {
                "globalTokenIndex": index,
                "token": entry.get("token"),
                "start": entry.get("start"),
                "end": entry.get("end"),
                "marker": markers.get(index) if isinstance(index, int) else None,
            }
        )
    return out


def build_tool_data(
    *,
    review_payload: dict[str, Any],
    screening_report: dict[str, Any] | None,
    audio_url: str,
    title: str,
) -> dict[str, Any]:
    items = _review_items(review_payload)
    timings = _word_timings(review_payload)
    by_id = _report_map(screening_report)
    queue: list[dict[str, Any]] = []
    for item in items:
        if item.get("decision") in {"approved", "corrected"}:
            continue
        official = item.get("officialToken") if isinstance(item.get("officialToken"), dict) else {}
        source = item.get("sourceWord") if isinstance(item.get("sourceWord"), dict) else {}
        queue.append(
            {
                "reviewId": item.get("reviewId"),
                "section": item.get("section") or official.get("section"),
                "decision": item.get("decision") or "pending",
                "tier": _tier(item, by_id),
                "matchType": item.get("matchType"),
                "officialToken": official,
                "sourceWord": source,
                "timing": item.get("timing") or {},
                "riskTypes": list(item.get("riskTypes") or []),
                "reasons": list(item.get("reasons") or []),
                "context": _context(item, timings),
                "screening": _screening(item, by_id),
            }
        )
    return {
        "schemaVersion": "yasi.review-tool-data.v1",
        "title": title,
        "audioUrl": audio_url,
        "reviewPayload": review_payload,
        "screeningReport": screening_report or {},
        "queueItems": queue,
        "transcriptMap": _transcript_map(review_items=items, timings=timings, by_id=by_id),
        "summary": _summary(items, queue),
    }


def render_review_tool_html(data: dict[str, Any]) -> str:
    html = TEMPLATE.read_text(encoding="utf-8")
    serialized = json.dumps(data, ensure_ascii=False)
    return html.replace(PLACEHOLDER, f"window.__YASI_REVIEW_TOOL_DATA__ = {serialized};")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a static Yasi timing review HTML file.")
    parser.add_argument("--review-input", type=Path, required=True)
    parser.add_argument("--screening-report", type=Path)
    parser.add_argument("--audio-url", required=True)
    parser.add_argument("--title", default="Yasi Timing Review")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    data = build_tool_data(
        review_payload=load_json(args.review_input),
        screening_report=load_json(args.screening_report) if args.screening_report else None,
        audio_url=args.audio_url,
        title=args.title,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_review_tool_html(data), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
