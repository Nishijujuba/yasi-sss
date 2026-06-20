#!/usr/bin/env python3
"""Screen alignment-review.json before manual timing review."""

from __future__ import annotations

import argparse
import copy
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "yasi.review-screening-report.v1"
REVIEW_SCHEMA_VERSION = "yasi.alignment-review.v1"
POLICY_VERSION = "balanced-v1"
DEFAULT_REVIEWER = f"code-screen:{POLICY_VERSION}"

AUTO_APPROVE_MATCH_TYPES = {"exact"}
AUTO_APPROVE_RISKS = {"answer-near", "apostrophe"}
AUTO_APPROVE_REASONS = {"risk:answer-near", "risk:apostrophe"}
STRUCTURAL_RISKS = {
    "number",
    "currency",
    "alphanumeric",
    "hyphenated",
    "hyphen-spelling",
}
HUMAN_REQUIRED_MATCH_TYPES = {"unmatched"}
HUMAN_REQUIRED_REASONS = {
    "missing-timing",
    "non-monotonic-timing",
    "non-positive-interval",
    "anchor-span-too-wide",
}
LLM_REVIEW_MATCH_TYPES = {"fuzzy", "split", "merged", "interpolated"}

LLM_PROMPT = """You are reviewing Yasi Transcript Shadowing alignment-review items.
Return JSON only, as an array with one object per item:
{"reviewId": "...", "suggestedDecision": "approved|corrected|needs-human", "confidence": 0.0-1.0, "notes": "...", "correction": null|{"start": number, "end": number}}

Rules:
- The officialToken text is the transcript authority; sourceWord is ASR timing evidence only.
- Suggest approved only when the official token and source word are clearly the same spoken token after punctuation, casing, apostrophe, or obvious ASR spelling variation.
- Suggest corrected only when the provided timing interval is clearly wrong and the item includes enough neighboring timing evidence to propose a better interval.
- Suggest needs-human for numbers, currency, phone/postcode-like tokens, missing timing, unmatched tokens, non-positive intervals, and any answer-bearing item where timing cannot be inferred from text alone.
- Never invent transcript text. Never silently rewrite officialToken.text.
"""

LLM_PRE_REVIEW_PROMPT = """You are doing blind pre-review for Yasi Transcript Shadowing alignment-review items.
Return JSON only, as an array with one object per item:
{"reviewId": "...", "suggestedDecision": "approved|corrected|needs-human", "confidence": 0.0-1.0, "notes": "...", "correction": null|{"start": number, "end": number}, "preReviewLabel": "likely-safe|needs-auditory-review|needs-manual-timing|reject-evidence"}

Rules:
- This is advisory pre-review only. Do not claim final release approval.
- Use only the supplied officialToken, sourceWord, timing, context, risks, and reasons. Do not rely on audio listening.
- Keep officialToken text as the transcript authority; sourceWord is ASR timing evidence only.
- Mark numbers, currency, spelling sequences, missing timing, unmatched tokens, and answer-near uncertainty as needs-auditory-review or needs-manual-timing unless the text and interval are unquestionably safe.
- Suggest approved only when token identity and interval evidence are straightforward.
- Suggest corrected only when the item includes enough neighboring timing evidence to propose a concrete interval.
- Never invent transcript text. Never silently rewrite officialToken.text.
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: Any) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        candidate = float(value)
        if math.isfinite(candidate):
            return candidate
    return None


def valid_timing(item: dict[str, Any]) -> bool:
    timing = item.get("timing") if isinstance(item.get("timing"), dict) else {}
    start = _number(timing.get("start"))
    end = _number(timing.get("end"))
    return start is not None and end is not None and end > start


def official_token(item: dict[str, Any]) -> dict[str, Any]:
    value = item.get("officialToken")
    return value if isinstance(value, dict) else {}


def source_word(item: dict[str, Any]) -> dict[str, Any]:
    value = item.get("sourceWord")
    return value if isinstance(value, dict) else {}


def risk_types(item: dict[str, Any]) -> set[str]:
    return {str(value) for value in item.get("riskTypes") or []}


def reasons(item: dict[str, Any]) -> set[str]:
    return {str(value) for value in item.get("reasons") or []}


def normalized_equal(item: dict[str, Any]) -> bool:
    official = str(official_token(item).get("normalized") or "")
    source = str(source_word(item).get("normalized") or "")
    return bool(official and source and official == source)


def has_structural_risk(item: dict[str, Any]) -> bool:
    return bool(risk_types(item) & STRUCTURAL_RISKS)


def has_bad_timing_reason(item: dict[str, Any]) -> bool:
    return bool(reasons(item) & HUMAN_REQUIRED_REASONS)


def classify_item(item: dict[str, Any]) -> tuple[str, str]:
    match_type = str(item.get("matchType") or "")
    item_reasons = reasons(item)
    item_risks = risk_types(item)

    if item.get("decision") in {"approved", "corrected"}:
        return "already-reviewed", "Existing reviewed decision is preserved."
    if has_bad_timing_reason(item) or not valid_timing(item):
        return "human-required", "Timing is missing, non-positive, non-monotonic, or too wide."
    if match_type in HUMAN_REQUIRED_MATCH_TYPES:
        return "human-required", "Unmatched tokens need human timing evidence."
    if has_structural_risk(item):
        return "human-required", "Numbers, currency, spelling, hyphenated, and alphanumeric tokens stay human-gated."
    if (
        match_type in AUTO_APPROVE_MATCH_TYPES
        and normalized_equal(item)
        and item_risks <= AUTO_APPROVE_RISKS
        and item_reasons <= AUTO_APPROVE_REASONS
    ):
        return "code-approved", "Exact normalized ASR/official identity with valid timing and no structural risk."
    if match_type in LLM_REVIEW_MATCH_TYPES:
        return "llm-candidate", "Textual mismatch or compound mapping can receive an LLM suggestion."
    return "human-required", "No stable automatic screening rule applies."


def report_item(item: dict[str, Any], *, tier: str, rationale: str) -> dict[str, Any]:
    official = official_token(item)
    source = source_word(item)
    return {
        "reviewId": item.get("reviewId"),
        "tier": tier,
        "rationale": rationale,
        "matchType": item.get("matchType"),
        "officialToken": {
            "text": official.get("text"),
            "normalized": official.get("normalized"),
            "answerRefs": list(official.get("answerRefs") or []),
            "section": official.get("section"),
            "segmentOrder": official.get("segmentOrder"),
            "tokenIndex": official.get("tokenIndex"),
            "globalTokenIndex": official.get("globalTokenIndex"),
        },
        "sourceWord": {
            "word": source.get("word"),
            "normalized": source.get("normalized"),
            "sourceIndex": source.get("sourceIndex"),
            "start": source.get("start"),
            "end": source.get("end"),
        },
        "timing": copy.deepcopy(item.get("timing")),
        "riskTypes": list(item.get("riskTypes") or []),
        "reasons": list(item.get("reasons") or []),
    }


def apply_code_approval(
    item: dict[str, Any],
    *,
    reviewer: str,
    reviewed_at: str,
    rationale: str,
) -> None:
    item["decision"] = "approved"
    item["reviewer"] = reviewer
    item["reviewedAt"] = reviewed_at
    item["notes"] = rationale
    item["correction"] = None


def refresh_statuses(review_payload: dict[str, Any]) -> None:
    unresolved = 0
    for section in review_payload.get("sections") or []:
        if not isinstance(section, dict):
            continue
        pending = [
            item
            for item in section.get("mappingReviews") or []
            if isinstance(item, dict) and item.get("decision") not in {"approved", "corrected"}
        ]
        unresolved += len(pending)
        section["status"] = "pending" if pending else "reviewed"
    review_payload["status"] = "needs-review" if unresolved else "reviewed"


def screen_review(
    review_payload: dict[str, Any],
    *,
    reviewer: str = DEFAULT_REVIEWER,
    reviewed_at: str | None = None,
) -> dict[str, Any]:
    if review_payload.get("schemaVersion") != REVIEW_SCHEMA_VERSION:
        raise ValueError(f"review artifact schemaVersion must be {REVIEW_SCHEMA_VERSION!r}")

    reviewed_at = reviewed_at or utc_now()
    screened = copy.deepcopy(review_payload)
    code_approved: list[dict[str, Any]] = []
    llm_candidates: list[dict[str, Any]] = []
    human_required: list[dict[str, Any]] = []
    preserved: list[dict[str, Any]] = []

    for section in screened.get("sections") or []:
        if not isinstance(section, dict):
            continue
        for item in section.get("mappingReviews") or []:
            if not isinstance(item, dict):
                continue
            tier, rationale = classify_item(item)
            item["screening"] = {
                "policyVersion": POLICY_VERSION,
                "tier": tier,
                "rationale": rationale,
            }
            record = report_item(item, tier=tier, rationale=rationale)
            if tier == "code-approved":
                apply_code_approval(
                    item,
                    reviewer=reviewer,
                    reviewed_at=reviewed_at,
                    rationale=rationale,
                )
                code_approved.append(record)
            elif tier == "llm-candidate":
                llm_candidates.append(record)
            elif tier == "already-reviewed":
                preserved.append(record)
            else:
                human_required.append(record)

    refresh_statuses(screened)
    total = len(code_approved) + len(llm_candidates) + len(human_required) + len(preserved)
    report = {
        "schemaVersion": SCHEMA_VERSION,
        "policyVersion": POLICY_VERSION,
        "reviewArtifact": review_payload.get("reviewArtifact"),
        "generatedAt": reviewed_at,
        "reviewer": reviewer,
        "summary": {
            "total": total,
            "codeApproved": len(code_approved),
            "llmCandidate": len(llm_candidates),
            "humanRequired": len(human_required),
        },
        "preservedReviewed": preserved,
        "codeApproved": code_approved,
        "llmCandidates": llm_candidates,
        "humanRequired": human_required,
    }
    return {"screenedReview": screened, "report": report}


def build_llm_jsonl_records(
    report: dict[str, Any],
    *,
    max_items_per_record: int = 25,
) -> list[dict[str, Any]]:
    items = list(report.get("llmCandidates") or [])
    records: list[dict[str, Any]] = []
    if max_items_per_record < 1:
        raise ValueError("max_items_per_record must be positive")
    for offset in range(0, len(items), max_items_per_record):
        chunk = items[offset : offset + max_items_per_record]
        records.append(
            {
                "task": "yasi-alignment-review-suggestion",
                "policyVersion": POLICY_VERSION,
                "prompt": LLM_PROMPT,
                "items": chunk,
            }
        )
    return records


def build_llm_pre_review_jsonl_records(
    report: dict[str, Any],
    *,
    max_items_per_record: int = 25,
) -> list[dict[str, Any]]:
    items = list(report.get("llmCandidates") or []) + list(report.get("humanRequired") or [])
    records: list[dict[str, Any]] = []
    if max_items_per_record < 1:
        raise ValueError("max_items_per_record must be positive")
    for offset in range(0, len(items), max_items_per_record):
        chunk = items[offset : offset + max_items_per_record]
        records.append(
            {
                "task": "yasi-alignment-blind-pre-review",
                "policyVersion": POLICY_VERSION,
                "prompt": LLM_PRE_REVIEW_PROMPT,
                "items": chunk,
            }
        )
    return records


def write_jsonl(path: str | Path, records: list[dict[str, Any]]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Apply deterministic screening and prepare LLM review batches for alignment-review.json.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--review-input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--reviewer", default=DEFAULT_REVIEWER)
    parser.add_argument("--reviewed-at", default=None)
    parser.add_argument("--max-items-per-llm-record", type=int, default=25)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = args.output_dir or args.review_input.parent
    result = screen_review(
        load_json(args.review_input),
        reviewer=args.reviewer,
        reviewed_at=args.reviewed_at,
    )
    report = result["report"]
    screened = result["screenedReview"]
    llm_records = build_llm_jsonl_records(
        report,
        max_items_per_record=args.max_items_per_llm_record,
    )
    pre_review_records = build_llm_pre_review_jsonl_records(
        report,
        max_items_per_record=args.max_items_per_llm_record,
    )
    write_json(Path(output_dir) / "review-screening-report.json", report)
    write_json(Path(output_dir) / "alignment-review.code-screened.json", screened)
    write_jsonl(Path(output_dir) / "llm-review-candidates.jsonl", llm_records)
    write_jsonl(Path(output_dir) / "llm-pre-review-candidates.jsonl", pre_review_records)
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
