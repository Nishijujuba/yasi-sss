#!/usr/bin/env python3
"""Validate ASR reconciliation transcript timing artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from reconcile_tokens import TIMING_SCHEMA_VERSION as SCHEMA_VERSION
from reconcile_tokens import flatten_official_transcript


REVIEW_SCHEMA_VERSION = "yasi.alignment-review.v1"
ALLOWED_STATUS = {"draft", "verified", "preview", "failed"}
REVIEWED_DECISIONS = {"approved", "corrected"}
UNRESOLVED_DECISIONS = {"pending", "rejected"}
TRACE_MATCH_TYPES = {"fuzzy", "split", "merged", "unmatched", "review-corrected"}


@dataclass(frozen=True)
class Token:
    section: int
    segment_order: int
    token_index: int
    global_token_index: int
    text: str
    normalized: str
    answer_refs: tuple[int | str, ...]
    risk_types: tuple[str, ...]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a yasi transcript timing JSON artifact.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("timings", help="Timing JSON to validate.")
    parser.add_argument("--transcript", required=True, help="Official transcript.json path.")
    parser.add_argument("--review-artifact", default=None, help="alignment-review.json used for review trace checks.")
    parser.add_argument("--require-all-sections", action="store_true", help="Require sections 1, 2, 3, and 4.")
    parser.add_argument("--require-verified", action="store_true", help="Require artifact and section status verified.")
    parser.add_argument("--require-review-trace", action="store_true", help="Require approved/corrected review trace for risky mappings.")
    return parser


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_official_sections(path: str | Path) -> dict[int, dict[str, Any]]:
    payload = load_json(path)
    if isinstance(payload, dict) and isinstance(payload.get("sections"), list):
        sections = payload["sections"]
    elif isinstance(payload, list):
        sections = payload
    else:
        raise ValueError("Official transcript must be a section list or contain sections[].")
    out: dict[int, dict[str, Any]] = {}
    for section in sections:
        if not isinstance(section, dict):
            continue
        section_number = int(section.get("section"))
        out[section_number] = section
    return out


def official_tokens(section_payload: dict[str, Any]) -> list[Token]:
    section = int(section_payload["section"])
    records = flatten_official_transcript(section_payload, section=section)
    return [
        Token(
            section=int(record["section"]),
            segment_order=int(record["segmentOrder"]),
            token_index=int(record["tokenIndex"]),
            global_token_index=int(record["globalTokenIndex"]),
            text=str(record["text"]),
            normalized=str(record["normalized"]),
            answer_refs=tuple(record.get("answerRefs") or ()),
            risk_types=tuple(record.get("riskTypes") or ()),
        )
        for record in records
    ]


def _risk_types(entry: dict[str, Any]) -> list[str]:
    values = entry.get("riskTypes")
    if values is None:
        values = entry.get("risks")
    return [str(value) for value in values or []]


def _match_type(entry: dict[str, Any]) -> str:
    return str(entry.get("matchType") or entry.get("match") or "")


def timing_requires_trace(entry: dict[str, Any]) -> bool:
    return bool(
        entry.get("requiresReview")
        or _risk_types(entry)
        or _match_type(entry) in TRACE_MATCH_TYPES
        or entry.get("review")
    )


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _review_identity(item: dict[str, Any]) -> tuple[int, int, int] | None:
    official = item.get("officialToken")
    if not isinstance(official, dict):
        official = {}
    section = item.get("section", official.get("section"))
    segment_order = item.get("segmentOrder", official.get("segmentOrder"))
    token_index = item.get("tokenIndex", official.get("tokenIndex"))
    if section is None or segment_order is None or token_index is None:
        return None
    try:
        return int(section), int(segment_order), int(token_index)
    except (TypeError, ValueError):
        return None


def review_lookup(review_payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not review_payload:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for section_payload in review_payload.get("sections") or []:
        if not isinstance(section_payload, dict):
            continue
        for item in section_payload.get("mappingReviews") or []:
            if not isinstance(item, dict):
                continue
            review_id = item.get("reviewId")
            if review_id:
                out[str(review_id)] = item
    return out


def validate_review_artifact(
    review_payload: dict[str, Any] | None,
    errors: list[str],
    *,
    require_resolved: bool,
) -> None:
    if review_payload is None:
        return
    if review_payload.get("schemaVersion") != REVIEW_SCHEMA_VERSION:
        errors.append(f"review artifact schemaVersion must be {REVIEW_SCHEMA_VERSION!r}.")
    seen: set[str] = set()
    for section_payload in review_payload.get("sections") or []:
        if not isinstance(section_payload, dict):
            errors.append("review artifact sections[] entries must be objects.")
            continue
        for item in section_payload.get("mappingReviews") or []:
            if not isinstance(item, dict):
                errors.append("review artifact mappingReviews[] entries must be objects.")
                continue
            review_id = item.get("reviewId")
            if not review_id:
                errors.append("review artifact mappingReviews entry is missing reviewId.")
            elif str(review_id) in seen:
                errors.append(f"review artifact has duplicate reviewId {review_id!r}.")
            else:
                seen.add(str(review_id))
            if _review_identity(item) is None:
                errors.append(f"reviewId {review_id!r} is missing official token identity.")
            decision = item.get("decision")
            if decision not in {"pending", "approved", "corrected", "rejected"}:
                errors.append(f"reviewId {review_id!r} has invalid decision {decision!r}.")
            if require_resolved and decision in UNRESOLVED_DECISIONS:
                errors.append(f"reviewId {review_id!r} has unresolved decision {decision!r}.")
            if decision == "corrected":
                correction = item.get("correction") or {}
                start = _number(correction.get("start"))
                end = _number(correction.get("end"))
                if start is None or end is None or end <= start:
                    errors.append(f"reviewId {review_id!r} has invalid correction timing.")


def _trace_identity_matches(
    *,
    entry: dict[str, Any],
    review_item: dict[str, Any],
    section: int,
) -> bool:
    identity = _review_identity(review_item)
    if identity is None:
        return False
    return identity == (
        section,
        int(entry.get("segmentOrder")),
        int(entry.get("tokenIndex")),
    )


def validate_section(
    section_payload: dict[str, Any],
    transcript_sections: dict[int, dict[str, Any]],
    errors: list[str],
    *,
    require_review_trace: bool,
    review_by_id: dict[str, dict[str, Any]],
    expected_review_artifact: str | None,
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
        errors.append(
            f"Section {section} token coverage mismatch: expected {len(expected_tokens)}, got {len(word_timings)}."
        )

    seen_identities: set[tuple[int, int, int]] = set()
    previous_start: float | None = None
    previous_end: float | None = None
    missing_timing = 0

    for index, entry in enumerate(word_timings):
        if not isinstance(entry, dict):
            errors.append(f"Section {section} entry {index} must be an object.")
            continue
        identity = (
            entry.get("section"),
            entry.get("segmentOrder"),
            entry.get("tokenIndex"),
        )
        if identity in seen_identities:
            errors.append(f"Section {section} duplicate token identity {identity}.")
        seen_identities.add(identity)
        if entry.get("section") != section:
            errors.append(f"Section {section} entry {index} has wrong section {entry.get('section')!r}.")

        if index < len(expected_tokens):
            expected = expected_tokens[index]
            if (
                entry.get("segmentOrder") != expected.segment_order
                or entry.get("tokenIndex") != expected.token_index
            ):
                errors.append(
                    f"Section {section} entry {index} identity mismatch: "
                    f"expected segment {expected.segment_order} token {expected.token_index}, "
                    f"got {entry.get('segmentOrder')} token {entry.get('tokenIndex')}."
                )
            if entry.get("normalized") != expected.normalized:
                errors.append(
                    f"Section {section} entry {index} normalized mismatch: "
                    f"expected {expected.normalized!r}, got {entry.get('normalized')!r}."
                )

        start = _number(entry.get("start"))
        end = _number(entry.get("end"))
        if start is None or end is None:
            missing_timing += 1
            if (entry.get("start") is None) != (entry.get("end") is None):
                errors.append(f"Section {section} entry {index} has only one timing boundary.")
        else:
            if end <= start:
                errors.append(
                    f"Section {section} entry {index} has non-positive interval start={start}, end={end}."
                )
            if status != "preview" and previous_start is not None and start < previous_start - 0.025:
                errors.append(
                    f"Section {section} entry {index} start time moved backward: "
                    f"previous={previous_start}, current={start}."
                )
            if status != "preview" and previous_end is not None and end < previous_end - 0.05:
                errors.append(
                    f"Section {section} entry {index} end time moved backward: "
                    f"previous={previous_end}, current={end}."
                )
            previous_start = start
            previous_end = end

        if require_review_trace and timing_requires_trace(entry):
            trace = entry.get("review")
            if not isinstance(trace, dict):
                errors.append(f"Section {section} entry {index} requires review trace but has none.")
                continue
            decision = trace.get("decision")
            if decision not in REVIEWED_DECISIONS:
                errors.append(f"Section {section} entry {index} has unresolved review decision {decision!r}.")
            if expected_review_artifact and trace.get("reviewArtifact") != expected_review_artifact:
                errors.append(
                    f"Section {section} entry {index} reviewArtifact mismatch: "
                    f"expected {expected_review_artifact!r}, got {trace.get('reviewArtifact')!r}."
                )
            review_id = trace.get("reviewId")
            if not review_id:
                errors.append(f"Section {section} entry {index} review trace is missing reviewId.")
                continue
            review_item = review_by_id.get(str(review_id))
            if not review_item:
                errors.append(f"Section {section} entry {index} reviewId {review_id!r} is absent from review artifact.")
                continue
            review_decision = review_item.get("decision")
            if review_decision not in REVIEWED_DECISIONS:
                errors.append(f"Section {section} entry {index} reviewId {review_id!r} has unresolved review artifact decision {review_decision!r}.")
            if decision != review_decision:
                errors.append(
                    f"Section {section} entry {index} review decision mismatch: "
                    f"trace has {decision!r}, review artifact has {review_decision!r}."
                )
            if not _trace_identity_matches(entry=entry, review_item=review_item, section=int(section)):
                errors.append(f"Section {section} entry {index} reviewId {review_id!r} points to a different token identity.")
            expected_risks = set(_risk_types(entry))
            trace_risks = set(trace.get("riskTypes") or [])
            if expected_risks and not expected_risks.issubset(trace_risks):
                missing = sorted(expected_risks - trace_risks)
                errors.append(f"Section {section} entry {index} review trace misses risk type(s): {missing}.")

    if status == "verified" and missing_timing:
        errors.append(f"Section {section} is verified but has {missing_timing} token(s) without timing.")


def validate(
    payload: dict[str, Any],
    transcript_sections: dict[int, dict[str, Any]],
    require_all_sections: bool,
    require_verified: bool,
    require_review_trace: bool,
    review_payload: dict[str, Any] | None,
) -> list[str]:
    errors: list[str] = []
    validate_review_artifact(
        review_payload,
        errors,
        require_resolved=require_review_trace,
    )
    review_by_id = review_lookup(review_payload)
    expected_review_artifact = payload.get("reviewArtifact")
    if review_payload is not None:
        review_artifact = review_payload.get("reviewArtifact")
        if expected_review_artifact and review_artifact and review_artifact != expected_review_artifact:
            errors.append(
                "review artifact path mismatch: "
                f"timings declare {expected_review_artifact!r}, review declares {review_artifact!r}."
            )
        if not expected_review_artifact and isinstance(review_artifact, str):
            expected_review_artifact = review_artifact
    if require_review_trace and review_payload is None:
        errors.append("--require-review-trace requires --review-artifact.")
    if require_review_trace and not payload.get("reviewArtifact"):
        errors.append("reviewArtifact is required when review trace is required.")
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        errors.append(f"schemaVersion must be {SCHEMA_VERSION!r}.")
    status = payload.get("status")
    if status not in ALLOWED_STATUS:
        errors.append(f"Artifact has invalid status {status!r}.")
    sections = payload.get("sections")
    if not isinstance(sections, list):
        return errors + ["sections must be a list."]

    seen_sections: set[int] = set()
    for section_payload in sections:
        if not isinstance(section_payload, dict):
            errors.append("sections[] entries must be objects.")
            continue
        section = section_payload.get("section")
        if section in seen_sections:
            errors.append(f"Duplicate section {section}.")
        if isinstance(section, int):
            seen_sections.add(section)
        validate_section(
            section_payload,
            transcript_sections,
            errors,
            require_review_trace=require_review_trace,
            review_by_id=review_by_id,
            expected_review_artifact=expected_review_artifact if isinstance(expected_review_artifact, str) else None,
        )

    if require_all_sections and seen_sections != {1, 2, 3, 4}:
        errors.append(f"--require-all-sections expected [1, 2, 3, 4], got {sorted(seen_sections)}.")
    if require_verified and status != "verified":
        errors.append(f"require-verified expected artifact status verified, got {status!r}.")
    if require_verified:
        for section_payload in sections:
            if isinstance(section_payload, dict) and section_payload.get("status") != "verified":
                errors.append(
                    f"require-verified expected section {section_payload.get('section')} status verified, "
                    f"got {section_payload.get('status')!r}."
                )
    return errors


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = load_json(args.timings)
    transcript_sections = load_official_sections(args.transcript)
    review_payload = load_json(args.review_artifact) if args.review_artifact else None
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
