#!/usr/bin/env python3
"""Validate yasi forced-alignment timing artifacts and review traces."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from align_transcript import DEFAULT_TRANSCRIPT, REVIEW_SCHEMA_VERSION, SCHEMA_VERSION, load_official_sections, official_tokens

ALLOWED_STATUS = {"draft", "verified", "failed"}
ALLOWED_SEVERITY = {"info", "warning", "error"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a yasi transcript timing JSON artifact against the official transcript.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("timings", help="Timing JSON to validate.")
    parser.add_argument("--transcript", default=str(DEFAULT_TRANSCRIPT), help="Official transcript.json path.")
    parser.add_argument("--review-artifact", default=None, help="alignment-review.json used to finalize this timing artifact.")
    parser.add_argument("--require-all-sections", action="store_true", help="Require sections 1, 2, 3, and 4.")
    parser.add_argument("--require-verified", action="store_true", help="Fail if the artifact or any section is draft.")
    parser.add_argument("--require-review-trace", action="store_true", help="Require traceable approved/corrected review entries for all special mappings.")
    return parser


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def review_items_for(payload: dict[str, Any], section: int | None = None) -> list[dict[str, Any]]:
    items = list(payload.get("reviewItems") or [])
    if section is None:
        return items
    out = [item for item in items if item.get("section") == section]
    for section_payload in payload.get("sections") or []:
        if section_payload.get("section") == section:
            out.extend(section_payload.get("reviewItems") or [])
    return out


def has_warning_or_error(items: list[dict[str, Any]]) -> bool:
    return any(item.get("severity") in {"warning", "error"} for item in items)


def timing_requires_trace(entry: dict[str, Any]) -> bool:
    return bool(entry.get("risks") or entry.get("requiresReview") or entry.get("match") in {"unmatched", "review-corrected"})


def review_lookup(review_payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not review_payload:
        return {}
    out = {}
    for section_payload in review_payload.get("sections") or []:
        for item in section_payload.get("mappingReviews") or []:
            review_id = item.get("reviewId")
            if review_id:
                out[str(review_id)] = item
    return out


def validate_review_artifact(review_payload: dict[str, Any] | None, errors: list[str]) -> None:
    if review_payload is None:
        return
    if review_payload.get("schemaVersion") != REVIEW_SCHEMA_VERSION:
        errors.append(f"review artifact schemaVersion must be {REVIEW_SCHEMA_VERSION!r}.")
    seen: set[str] = set()
    for section_payload in review_payload.get("sections") or []:
        for item in section_payload.get("mappingReviews") or []:
            review_id = item.get("reviewId")
            if not review_id:
                errors.append("review artifact mappingReviews entry is missing reviewId.")
            elif review_id in seen:
                errors.append(f"review artifact has duplicate reviewId {review_id!r}.")
            else:
                seen.add(str(review_id))
            decision = item.get("decision")
            if decision not in {"pending", "approved", "corrected", "rejected"}:
                errors.append(f"reviewId {review_id!r} has invalid decision {decision!r}.")
            if decision == "corrected":
                correction = item.get("correction") or {}
                start = correction.get("start")
                end = correction.get("end")
                if not isinstance(start, (int, float)) or not isinstance(end, (int, float)) or end <= start:
                    errors.append(f"reviewId {review_id!r} has invalid correction timing.")


def validate_review_items(items: list[dict[str, Any]], errors: list[str]) -> None:
    for idx, item in enumerate(items):
        severity = item.get("severity")
        if severity not in ALLOWED_SEVERITY:
            errors.append(f"reviewItems[{idx}] has invalid severity {severity!r}.")
        if not item.get("type"):
            errors.append(f"reviewItems[{idx}] is missing type.")
        if not item.get("message"):
            errors.append(f"reviewItems[{idx}] is missing message.")


def validate_section(
    section_payload: dict[str, Any],
    transcript_sections: dict[int, dict[str, Any]],
    artifact: dict[str, Any],
    errors: list[str],
    *,
    require_review_trace: bool,
    review_by_id: dict[str, dict[str, Any]],
) -> None:
    section = section_payload.get("section")
    if section not in transcript_sections:
        errors.append(f"Section {section!r} does not exist in transcript.")
        return
    status = section_payload.get("status")
    if status not in ALLOWED_STATUS:
        errors.append(f"Section {section} has invalid status {status!r}.")
    expected_tokens = official_tokens(transcript_sections[int(section)])
    word_timings = section_payload.get("wordTimings")
    if not isinstance(word_timings, list):
        errors.append(f"Section {section} wordTimings must be a list.")
        return
    if len(word_timings) != len(expected_tokens):
        errors.append(f"Section {section} token coverage mismatch: expected {len(expected_tokens)}, got {len(word_timings)}.")

    seen_identities: set[tuple[int, int, int]] = set()
    previous_start: float | None = None
    previous_end: float | None = None
    missing_timing = 0

    for idx, entry in enumerate(word_timings):
        identity = (entry.get("section"), entry.get("segmentOrder"), entry.get("tokenIndex"))
        if identity in seen_identities:
            errors.append(f"Section {section} duplicate token identity {identity}.")
        seen_identities.add(identity)
        if entry.get("section") != section:
            errors.append(f"Section {section} entry {idx} has wrong section {entry.get('section')!r}.")

        if idx < len(expected_tokens):
            expected = expected_tokens[idx]
            if entry.get("segmentOrder") != expected.segment_order or entry.get("tokenIndex") != expected.token_index:
                errors.append(
                    f"Section {section} entry {idx} identity mismatch: expected segment {expected.segment_order} token {expected.token_index}, got {entry.get('segmentOrder')} token {entry.get('tokenIndex')}."
                )
            if entry.get("normalized") != expected.normalized:
                errors.append(
                    f"Section {section} entry {idx} normalized mismatch: expected {expected.normalized!r}, got {entry.get('normalized')!r}."
                )

        start = entry.get("start")
        end = entry.get("end")
        if start is None or end is None:
            missing_timing += 1
            if (start is None) != (end is None):
                errors.append(f"Section {section} entry {idx} has only one timing boundary.")
            continue
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            errors.append(f"Section {section} entry {idx} timing values must be numeric.")
            continue
        if end <= start:
            errors.append(f"Section {section} entry {idx} has non-positive interval start={start}, end={end}.")
        if previous_start is not None and start < previous_start - 0.025:
            errors.append(f"Section {section} entry {idx} start time moved backward: previous={previous_start}, current={start}.")
        if previous_end is not None and end < previous_end - 0.05:
            errors.append(f"Section {section} entry {idx} end time moved backward: previous={previous_end}, current={end}.")
        previous_start = float(start)
        previous_end = float(end)

        if require_review_trace and timing_requires_trace(entry):
            trace = entry.get("review")
            if not isinstance(trace, dict):
                errors.append(f"Section {section} entry {idx} requires review trace but has none.")
                continue
            review_id = trace.get("reviewId")
            decision = trace.get("decision")
            if decision not in {"approved", "corrected"}:
                errors.append(f"Section {section} entry {idx} has unresolved review decision {decision!r}.")
            if not review_id:
                errors.append(f"Section {section} entry {idx} review trace is missing reviewId.")
                continue
            review_item = review_by_id.get(str(review_id))
            if not review_item:
                errors.append(f"Section {section} entry {idx} reviewId {review_id!r} is absent from review artifact.")
                continue
            if review_item.get("section") != section or review_item.get("segmentOrder") != entry.get("segmentOrder") or review_item.get("tokenIndex") != entry.get("tokenIndex"):
                errors.append(f"Section {section} entry {idx} reviewId {review_id!r} points to a different token identity.")
            risk_types = set(trace.get("riskTypes") or [])
            expected_risks = set(entry.get("risks") or [])
            if expected_risks and not expected_risks.issubset(risk_types):
                errors.append(f"Section {section} entry {idx} review trace misses risk type(s): {sorted(expected_risks - risk_types)}.")

    section_review = review_items_for(artifact, int(section))
    if status == "verified":
        if missing_timing:
            errors.append(f"Section {section} is verified but has {missing_timing} token(s) without timing.")
        if has_warning_or_error(section_review):
            errors.append(f"Section {section} is verified but has warning/error review items.")
    if status == "draft" and missing_timing and not section_review:
        errors.append(f"Section {section} is draft with missing timings but no review items.")


def validate(
    payload: dict[str, Any],
    transcript_sections: dict[int, dict[str, Any]],
    require_all_sections: bool,
    require_verified: bool,
    require_review_trace: bool,
    review_payload: dict[str, Any] | None,
) -> list[str]:
    errors: list[str] = []
    validate_review_artifact(review_payload, errors)
    review_by_id = review_lookup(review_payload)
    if require_review_trace and review_payload is None:
        errors.append("--require-review-trace requires --review-artifact.")
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        errors.append(f"schemaVersion must be {SCHEMA_VERSION!r}.")
    status = payload.get("status")
    if status not in ALLOWED_STATUS:
        errors.append(f"Artifact has invalid status {status!r}.")
    sections = payload.get("sections")
    if not isinstance(sections, list):
        return errors + ["sections must be a list."]

    review_items = review_items_for(payload)
    validate_review_items(review_items, errors)

    seen_sections: set[int] = set()
    for section_payload in sections:
        section = section_payload.get("section")
        if section in seen_sections:
            errors.append(f"Duplicate section {section}.")
        if isinstance(section, int):
            seen_sections.add(section)
        validate_section(
            section_payload,
            transcript_sections,
            payload,
            errors,
            require_review_trace=require_review_trace,
            review_by_id=review_by_id,
        )

    if require_all_sections and seen_sections != {1, 2, 3, 4}:
        errors.append(f"--require-all-sections expected [1, 2, 3, 4], got {sorted(seen_sections)}.")
    if require_verified and status != "verified":
        errors.append(f"--require-verified expected artifact status verified, got {status!r}.")
    if status == "verified" and has_warning_or_error(review_items):
        errors.append("Artifact is verified but has warning/error review items.")
    if status == "draft" and require_verified:
        errors.append("Artifact is draft and --require-verified was set.")
    if status == "draft" and not review_items:
        errors.append("Artifact is draft but has no reviewItems explaining why.")
    if status == "verified":
        for section_payload in sections:
            if section_payload.get("status") != "verified":
                errors.append(f"Artifact is verified but section {section_payload.get('section')} is {section_payload.get('status')!r}.")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = load_json(Path(args.timings))
    transcript_sections = load_official_sections(Path(args.transcript))
    review_payload = load_json(Path(args.review_artifact)) if args.review_artifact else None
    errors = validate(
        payload,
        transcript_sections,
        args.require_all_sections,
        args.require_verified,
        args.require_review_trace,
        review_payload,
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    sections = sorted(section.get("section") for section in payload.get("sections", []))
    print(json.dumps({"valid": True, "status": payload.get("status"), "sections": sections}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
