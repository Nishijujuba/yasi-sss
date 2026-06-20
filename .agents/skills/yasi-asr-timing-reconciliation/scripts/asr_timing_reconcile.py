#!/usr/bin/env python3
"""Draft and finalize ASR timing reconciliation artifacts."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import reconcile_tokens


REPORT_SCHEMA_VERSION = "yasi.reconciliation-report.v1"
TIMING_SCHEMA_VERSION = "yasi.transcript-timings.v1"
REVIEW_SCHEMA_VERSION = "yasi.alignment-review.v1"
TOOL_NAME = "yasi-asr-timing-reconciliation"
PACK_ID = "cambridge-10-test-1-listening"
TRACE_MATCH_TYPES = {"fuzzy", "split", "merged", "unmatched", "review-corrected"}


class FinalizeBlocked(RuntimeError):
    """Raised when a review artifact still has unresolved timing decisions."""


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[4]


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


def default_pack_root(repo_root: Path) -> Path:
    return repo_root / "public" / "packs" / "cambridge-10" / "test-1" / "listening"


def default_benchmark_root(repo_root: Path) -> Path:
    return repo_root / "待删除" / "yasi-asr-timing-reconciliation"


def section_label(section: int) -> str:
    return f"section-{section:02d}"


def default_evidence_input(repo_root: Path, section: int, model: str, *, pack_id: str | None = None) -> Path:
    root = default_benchmark_root(repo_root)
    if pack_id:
        root = root / pack_id
    return root / section_label(section) / model / "asr-timing-evidence.json"


def pack_id_for(pack_root: Path, explicit: str | None = None) -> str:
    if explicit:
        return explicit
    manifest_path = pack_root / "manifest.json"
    if manifest_path.is_file():
        manifest = load_json(manifest_path)
        pack_id = manifest.get("packId") if isinstance(manifest, dict) else None
        if isinstance(pack_id, str) and pack_id.strip():
            return pack_id
    return PACK_ID


def review_artifact_relative(pack_id: str) -> str:
    return f"build/review/transcript-timing/{pack_id}/alignment-review.json"


def repo_relative(path: str | Path, repo_root: Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(candidate)


def tool_metadata() -> dict[str, Any]:
    return {"name": TOOL_NAME, "version": "0.1.0"}


def _review_id(section: int, entry: dict[str, Any]) -> str:
    return f"s{section:02d}-g{int(entry.get('globalTokenIndex', 0)):04d}"


def _identity_from_entry(section: int, entry: dict[str, Any]) -> tuple[int, int, int]:
    return section, int(entry["segmentOrder"]), int(entry["tokenIndex"])


def _identity_from_review(item: dict[str, Any]) -> tuple[int, int, int] | None:
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


def _risk_types(entry: dict[str, Any]) -> list[str]:
    values = entry.get("riskTypes")
    if values is None:
        values = entry.get("risks")
    return [str(value) for value in values or []]


def _match_type(entry: dict[str, Any]) -> str:
    return str(entry.get("matchType") or entry.get("match") or "")


def timing_requires_review(entry: dict[str, Any]) -> bool:
    return bool(
        entry.get("requiresReview")
        or _risk_types(entry)
        or _match_type(entry) in TRACE_MATCH_TYPES
    )


def _timing_from_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {"start": entry.get("start"), "end": entry.get("end")}


def _valid_timing(start: Any, end: Any) -> bool:
    return (
        isinstance(start, (int, float))
        and not isinstance(start, bool)
        and isinstance(end, (int, float))
        and not isinstance(end, bool)
        and float(end) > float(start)
    )


def _entry_lookup(draft_section: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    section = int(draft_section["section"])
    for entry in draft_section.get("wordTimings") or []:
        if isinstance(entry, dict):
            out[_review_id(section, entry)] = entry
    return out


def build_mapping_review(review_item: dict[str, Any], draft_entry: dict[str, Any]) -> dict[str, Any]:
    mapping = {
        "reviewId": review_item["reviewId"],
        "section": review_item.get("section"),
        "matchType": review_item.get("matchType"),
        "decision": "pending",
        "officialToken": review_item.get("officialToken"),
        "sourceWord": review_item.get("sourceWord"),
        "timing": _timing_from_entry(draft_entry),
        "riskTypes": list(review_item.get("riskTypes") or []),
        "reasons": list(review_item.get("reasons") or []),
        "correction": None,
    }
    if review_item.get("sourceWordTimings"):
        mapping["sourceWords"] = review_item["sourceWordTimings"]
    elif review_item.get("sourceWords"):
        mapping["sourceWords"] = review_item["sourceWords"]
    return mapping


def build_alignment_review(
    *,
    report: dict[str, Any],
    draft: dict[str, Any],
    pack_root: Path,
    transcript: Path,
    evidence_input: Path,
    review_relative: str,
    draft_output: Path,
    final_output: Path,
    generated_at: str,
    repo_root: Path,
) -> dict[str, Any]:
    review_items_by_section: dict[int, list[dict[str, Any]]] = {}
    for item in report.get("reviewItems") or []:
        if isinstance(item, dict):
            review_items_by_section.setdefault(int(item.get("section", report["section"])), []).append(item)

    review_sections = []
    pending_count = 0
    for section_payload in draft.get("sections") or []:
        section = int(section_payload["section"])
        lookup = _entry_lookup(section_payload)
        mapping_reviews = []
        for item in review_items_by_section.get(section, []):
            draft_entry = lookup.get(str(item.get("reviewId")))
            if draft_entry is None:
                continue
            mapping_reviews.append(build_mapping_review(item, draft_entry))
        pending_count += len(mapping_reviews)
        review_sections.append(
            {
                "section": section,
                "status": "pending" if mapping_reviews else "reviewed",
                "autoMapping": {
                    "schemaVersion": TIMING_SCHEMA_VERSION,
                    "status": section_payload.get("status", "draft"),
                    "wordTimings": section_payload.get("wordTimings", []),
                    "reviewItems": review_items_by_section.get(section, []),
                    "diagnostics": section_payload.get("diagnostics", {}),
                },
                "mappingReviews": mapping_reviews,
            }
        )

    return {
        "schemaVersion": REVIEW_SCHEMA_VERSION,
        "reviewArtifact": review_relative,
        "status": "needs-review" if pending_count else "reviewed",
        "generatedAt": generated_at,
        "tool": tool_metadata(),
        "packRoot": repo_relative(pack_root, repo_root),
        "transcript": repo_relative(transcript, repo_root),
        "sourceEvidence": repo_relative(evidence_input, repo_root),
        "draftTimingArtifact": repo_relative(draft_output, repo_root),
        "finalTimingArtifact": repo_relative(final_output, repo_root),
        "instructions": {
            "decision": "Set each mappingReviews[].decision to approved or corrected after review.",
            "approved": "Use approved when the automatic timing is correct.",
            "corrected": "Use corrected with correction.start and correction.end when the automatic timing is wrong.",
            "audit": "Keep reviewer, reviewedAt, notes, and correction fields so special mappings remain traceable.",
        },
        "sections": review_sections,
    }


def build_draft_timings(
    *,
    report: dict[str, Any],
    pack_root: Path,
    transcript: Path,
    review_relative: str,
    generated_at: str,
    repo_root: Path,
) -> dict[str, Any]:
    draft = copy.deepcopy(report["draftTimings"])
    review_items_by_section: dict[int, list[dict[str, Any]]] = {}
    for item in report.get("reviewItems") or []:
        if isinstance(item, dict):
            review_items_by_section.setdefault(int(item.get("section", report["section"])), []).append(item)
    for section_payload in draft.get("sections") or []:
        section = int(section_payload["section"])
        section_payload["status"] = "draft"
        section_payload["reviewItems"] = review_items_by_section.get(section, [])
        section_payload.setdefault("diagnostics", {})
    draft.update(
        {
            "schemaVersion": TIMING_SCHEMA_VERSION,
            "status": "draft",
            "generatedAt": generated_at,
            "tool": tool_metadata(),
            "packRoot": repo_relative(pack_root, repo_root),
            "transcript": repo_relative(transcript, repo_root),
            "reviewArtifact": review_relative,
            "generatedFromReview": False,
            "reviewItems": list(report.get("reviewItems") or []),
        }
    )
    return draft


def run_draft(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    pack_root = Path(args.pack_root) if args.pack_root else default_pack_root(repo_root)
    section = int(args.section)
    model = args.model
    pack_id = pack_id_for(pack_root, args.pack_id)
    evidence_input = (
        Path(args.evidence_input)
        if args.evidence_input
        else default_evidence_input(repo_root, section, model, pack_id=args.pack_id)
    )
    transcript = Path(args.transcript) if args.transcript else pack_root / "transcript.json"
    output_dir = Path(args.output_dir) if args.output_dir else evidence_input.parent
    generated_at = args.generated_at or utc_now()
    review_relative = review_artifact_relative(pack_id)

    evidence_payload = load_json(evidence_input)
    transcript_payload = load_json(transcript)
    report = reconcile_tokens.reconcile_transcript(
        transcript_payload,
        evidence_payload,
        section=section,
        source_evidence=repo_relative(evidence_input, repo_root),
        review_artifact=review_relative,
        model=model,
        source_audio=evidence_payload.get("sourceAudio"),
        generated_at=generated_at,
    )
    report["schemaVersion"] = REPORT_SCHEMA_VERSION
    report["engine"] = evidence_payload.get("engine")
    report["model"] = model
    report["sourceAudio"] = evidence_payload.get("sourceAudio")
    report["officialTranscript"] = repo_relative(transcript, repo_root)

    report_output = output_dir / "reconciliation-report.json"
    draft_output = output_dir / "transcript-timings.draft.json"
    review_output = output_dir / "alignment-review.json"
    final_output = pack_root / "transcript-timings.json"
    draft = build_draft_timings(
        report=report,
        pack_root=pack_root,
        transcript=transcript,
        review_relative=review_relative,
        generated_at=generated_at,
        repo_root=repo_root,
    )
    review = build_alignment_review(
        report=report,
        draft=draft,
        pack_root=pack_root,
        transcript=transcript,
        evidence_input=evidence_input,
        review_relative=review_relative,
        draft_output=draft_output,
        final_output=final_output,
        generated_at=generated_at,
        repo_root=repo_root,
    )

    write_json(report_output, report)
    write_json(draft_output, draft)
    write_json(review_output, review)
    print(
        json.dumps(
            {
                "reconciliationReport": str(report_output),
                "draftTimings": str(draft_output),
                "alignmentReview": str(review_output),
                "gateOutcome": report.get("gateOutcome"),
                "reviewItems": len(report.get("reviewItems") or []),
            },
            ensure_ascii=False,
        )
    )
    return 0


def _review_map_for(section_payload: dict[str, Any]) -> dict[tuple[int, int, int], dict[str, Any]]:
    out: dict[tuple[int, int, int], dict[str, Any]] = {}
    for item in section_payload.get("mappingReviews") or []:
        if not isinstance(item, dict):
            continue
        identity = _identity_from_review(item)
        if identity is not None:
            out[identity] = item
    return out


def _all_mapping_reviews(review_payload: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for section_payload in review_payload.get("sections") or []:
        if isinstance(section_payload, dict):
            out.extend(item for item in section_payload.get("mappingReviews") or [] if isinstance(item, dict))
    return out


def _trace_for(review_relative: str, review_item: dict[str, Any], decision: str) -> dict[str, Any]:
    correction = review_item.get("correction") or {}
    return {
        "reviewArtifact": review_relative,
        "reviewId": review_item.get("reviewId"),
        "decision": decision,
        "riskTypes": list(review_item.get("riskTypes") or []),
        "reasons": list(review_item.get("reasons") or []),
        "reviewer": correction.get("reviewer") or review_item.get("reviewer"),
        "reviewedAt": correction.get("reviewedAt") or review_item.get("reviewedAt"),
        "notes": correction.get("notes") or review_item.get("notes") or "",
    }


def validate_review_ready(review_payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if review_payload.get("schemaVersion") != REVIEW_SCHEMA_VERSION:
        errors.append(f"review artifact schemaVersion must be {REVIEW_SCHEMA_VERSION!r}")
    for item in _all_mapping_reviews(review_payload):
        review_id = item.get("reviewId")
        decision = item.get("decision")
        if decision not in {"approved", "corrected"}:
            errors.append(f"reviewId {review_id!r} has {decision!r} decision")
        if decision == "corrected":
            correction = item.get("correction") or {}
            if not _valid_timing(correction.get("start"), correction.get("end")):
                errors.append(f"reviewId {review_id!r} has invalid correction timing")
    for section_payload in review_payload.get("sections") or []:
        if not isinstance(section_payload, dict):
            continue
        section = int(section_payload.get("section", 0))
        review_by_identity = _review_map_for(section_payload)
        auto_mapping = section_payload.get("autoMapping") or {}
        word_timings = auto_mapping.get("wordTimings")
        if not isinstance(word_timings, list) or not word_timings:
            errors.append(f"section {section} autoMapping.wordTimings must be a non-empty list")
            continue
        for entry in word_timings:
            if not isinstance(entry, dict) or not timing_requires_review(entry):
                continue
            identity = _identity_from_entry(section, entry)
            if identity not in review_by_identity:
                errors.append(
                    "required review timing is missing mappingReviews coverage "
                    f"for section {section} segment {entry.get('segmentOrder')} token {entry.get('tokenIndex')}"
                )
    return errors


def apply_review_to_section(
    section_payload: dict[str, Any],
    *,
    review_relative: str,
) -> tuple[dict[str, Any], dict[str, int]]:
    section = int(section_payload["section"])
    auto_mapping = section_payload.get("autoMapping") or {}
    word_timings = auto_mapping.get("wordTimings")
    if not isinstance(word_timings, list) or not word_timings:
        raise FinalizeBlocked(f"section {section} autoMapping.wordTimings must be a non-empty list")
    review_by_identity = _review_map_for(section_payload)
    counts = {"approved": 0, "corrected": 0}
    final_entries: list[dict[str, Any]] = []

    for original in word_timings:
        entry = copy.deepcopy(original)
        review_item = review_by_identity.get(_identity_from_entry(section, entry))
        if review_item is None:
            final_entries.append(entry)
            continue
        decision = str(review_item.get("decision"))
        if decision == "approved":
            if not _valid_timing(entry.get("start"), entry.get("end")):
                raise FinalizeBlocked(f"reviewId {review_item.get('reviewId')!r} approved an entry without timing")
            counts["approved"] += 1
            entry["review"] = _trace_for(review_relative, review_item, decision)
        elif decision == "corrected":
            correction = review_item.get("correction") or {}
            start = correction.get("start")
            end = correction.get("end")
            if not _valid_timing(start, end):
                raise FinalizeBlocked(f"reviewId {review_item.get('reviewId')!r} has invalid correction timing")
            counts["corrected"] += 1
            entry["start"] = round(float(start), 3)
            entry["end"] = round(float(end), 3)
            entry["sourceIndex"] = correction.get("sourceIndex", entry.get("sourceIndex"))
            entry["sourceWord"] = correction.get("sourceToken", correction.get("sourceWord", entry.get("sourceWord")))
            entry["match"] = "review-corrected"
            entry["review"] = _trace_for(review_relative, review_item, decision)
        final_entries.append(entry)

    return (
        {
            "section": section,
            "status": "verified",
            "wordTimings": final_entries,
            "reviewItems": [],
            "diagnostics": {
                "reviewApprovedCount": counts["approved"],
                "reviewCorrectedCount": counts["corrected"],
            },
        },
        counts,
    )


def promote_review_artifacts(
    *,
    review_payload: dict[str, Any],
    review_input: Path,
    repo_root: Path,
    review_relative: str,
) -> None:
    review_output = repo_root / Path(*review_relative.split("/"))
    promoted_review = copy.deepcopy(review_payload)
    promoted_review["reviewArtifact"] = review_relative
    write_json(review_output, promoted_review)

    report_input = review_input.parent / "reconciliation-report.json"
    if report_input.is_file():
        report_payload = load_json(report_input)
        if isinstance(report_payload, dict):
            report_payload["reviewArtifact"] = review_relative
            write_json(review_output.parent / "reconciliation-report.json", report_payload)


def run_finalize(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    pack_root = Path(args.pack_root) if args.pack_root else default_pack_root(repo_root)
    pack_id = pack_id_for(pack_root, args.pack_id)
    review_relative = review_artifact_relative(pack_id)
    review_input = Path(args.review_input)
    output = Path(args.output)
    generated_at = args.generated_at or utc_now()
    review_payload = load_json(review_input)

    errors = validate_review_ready(review_payload)
    if errors:
        raise FinalizeBlocked("; ".join(errors))

    sections = []
    totals = {"approved": 0, "corrected": 0}
    for section_payload in review_payload.get("sections") or []:
        if not isinstance(section_payload, dict):
            continue
        final_section, counts = apply_review_to_section(
            section_payload,
            review_relative=review_relative,
        )
        sections.append(final_section)
        totals["approved"] += counts["approved"]
        totals["corrected"] += counts["corrected"]
    if not sections:
        raise FinalizeBlocked("review artifact has no sections to finalize")

    final_payload = {
        "schemaVersion": TIMING_SCHEMA_VERSION,
        "status": "verified",
        "generatedAt": generated_at,
        "tool": tool_metadata(),
        "packRoot": repo_relative(pack_root, repo_root),
        "transcript": repo_relative(pack_root / "transcript.json", repo_root),
        "reviewArtifact": review_relative,
        "generatedFromReview": True,
        "sections": sections,
        "reviewItems": [],
        "reviewSummary": {
            "approved": totals["approved"],
            "corrected": totals["corrected"],
            "reviewInput": str(review_input),
        },
    }

    promote_review_artifacts(
        review_payload=review_payload,
        review_input=review_input,
        repo_root=repo_root,
        review_relative=review_relative,
    )
    write_json(output, final_payload)
    print(
        json.dumps(
            {
                "output": str(output),
                "reviewArtifact": review_relative,
                "status": "verified",
                "sections": [section["section"] for section in sections],
            },
            ensure_ascii=False,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Draft or finalize Yasi ASR transcript timing reconciliation artifacts.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--draft", action="store_true", help="Create reconciliation-report, draft timings, and alignment review.")
    mode.add_argument("--finalize-review", action="store_true", help="Finalize transcript timings from a reviewed alignment-review.json.")
    parser.add_argument("--section", type=int, default=1, help="Listening section number for draft mode.")
    parser.add_argument("--model", default="small", help="ASR model label for draft mode.")
    parser.add_argument("--evidence-input", type=Path, help="asr-timing-evidence.json path.")
    parser.add_argument("--review-input", type=Path, help="alignment-review.json path for finalize mode.")
    parser.add_argument("--output", type=Path, help="Final transcript-timings.json path for finalize mode.")
    parser.add_argument("--output-dir", type=Path, help="Draft output directory. Defaults to the evidence parent.")
    parser.add_argument("--transcript", type=Path, help="Official transcript.json path. Defaults to the pack transcript.")
    parser.add_argument("--pack-root", type=Path, help="Listening pack root.")
    parser.add_argument("--pack-id", help="Pack id for release review artifact path.")
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_script(), help="Repository root for promoted review artifacts.")
    parser.add_argument("--generated-at", help="Override generatedAt timestamp.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.draft:
            return run_draft(args)
        if args.review_input is None:
            raise FinalizeBlocked("--finalize-review requires --review-input")
        if args.output is None:
            raise FinalizeBlocked("--finalize-review requires --output")
        return run_finalize(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
