#!/usr/bin/env python3
"""Generate yasi forced-alignment draft, review, and final timing artifacts."""

from __future__ import annotations

import argparse
import copy
import difflib
import json
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "yasi.transcript-timings.v1"
REVIEW_SCHEMA_VERSION = "yasi.alignment-review.v1"
TOOL_NAME = "yasi-forced-alignment"
TOOL_VERSION = "0.2.0"

DEFAULT_PACK_ROOT = Path(r"D:\Project\yasi\public\packs\cambridge-10\test-1\listening")
DEFAULT_TRANSCRIPT = DEFAULT_PACK_ROOT / "transcript.json"
DEFAULT_OUTPUT = DEFAULT_PACK_ROOT / "transcript-timings.json"
DEFAULT_DRAFT_OUTPUT = DEFAULT_PACK_ROOT / "transcript-timings.draft.json"
DEFAULT_REVIEW_OUTPUT = DEFAULT_PACK_ROOT / "alignment-review.json"
DEFAULT_QWEN_PYTHON = Path(r"D:\Project\video2pdf\newskill-kimi\.venvs\qwen3-asr\Scripts\python.exe")
DEFAULT_QWEN_WRAPPER = Path(
    r"D:\Project\video2pdf\newskill-kimi\.agents\skills\qwen-bilibili-render-pdf\scripts\qwen_asr_transcribe.py"
)
DEFAULT_MODEL_ROOT = Path(r"D:\model-repo")
DEFAULT_ALIGNER = DEFAULT_MODEL_ROOT / "Qwen3-ForcedAligner-0.6B"
DEFAULT_FAST_ASR = DEFAULT_MODEL_ROOT / "Qwen3-ASR-0.6B"
DEFAULT_QUALITY_ASR = DEFAULT_MODEL_ROOT / "Qwen3-ASR-1.7B"
DEFAULT_FFMPEG = Path(r"D:\Project\video2pdf\kimi\tools\ffmpeg\bin\ffmpeg.exe")
DEFAULT_FFPROBE = Path(r"D:\Project\video2pdf\kimi\tools\ffmpeg\bin\ffprobe.exe")

TOKEN_RE = re.compile(
    r"[£$€]?\d+(?:[,.]\d+)*(?:-[A-Za-z0-9]+)?|[A-Za-z0-9]+(?:[’'][A-Za-z0-9]+)?(?:-[A-Za-z0-9]+)*"
)
APOSTROPHES = {"'", "’", "‘", "`"}
CURRENCY = {"£", "$", "€"}
REVIEWED_DECISIONS = {"approved", "corrected"}


@dataclass(frozen=True)
class Token:
    text: str
    normalized: str
    segment_order: int
    token_index: int
    global_index: int
    risks: tuple[str, ...]


@dataclass(frozen=True)
class TimedToken:
    text: str
    normalized: str
    start: float
    end: float
    source_index: int


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create yasi IELTS listening timing artifacts through Qwen raw timings, auto mapping, alignment review, and final frontend timings.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    section_group = parser.add_mutually_exclusive_group()
    section_group.add_argument("--section", type=int, action="append", choices=(1, 2, 3, 4), help="Section to align. Repeat for multiple sections.")
    section_group.add_argument("--all-sections", action="store_true", help="Align sections 1 through 4.")
    parser.add_argument("--finalize-review", action="store_true", help="Read alignment-review.json and write final transcript-timings.json without running Qwen.")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan and wrapper commands without loading models or writing output.")
    parser.add_argument("--pack-root", default=str(DEFAULT_PACK_ROOT), help="Listening pack root.")
    parser.add_argument("--transcript", default=str(DEFAULT_TRANSCRIPT), help="Official transcript.json path.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Final frontend timing JSON output path.")
    parser.add_argument("--draft-output", default=str(DEFAULT_DRAFT_OUTPUT), help="Auto-mapping draft timing JSON output path.")
    parser.add_argument("--review-output", default=str(DEFAULT_REVIEW_OUTPUT), help="Alignment review JSON path generated from uncertain mappings.")
    parser.add_argument("--review-input", default=None, help="Alignment review JSON path to finalize. Defaults to --review-output.")
    parser.add_argument("--qwen-python", default=str(DEFAULT_QWEN_PYTHON), help="Python executable for the Qwen ASR venv.")
    parser.add_argument("--qwen-wrapper", default=str(DEFAULT_QWEN_WRAPPER), help="Reference Qwen ASR wrapper script.")
    parser.add_argument("--profile", choices=("fast", "quality"), default="quality", help="Qwen model profile.")
    parser.add_argument("--language", default="English", help="Language passed to Qwen wrapper, or auto.")
    parser.add_argument("--context", default="Preserve IELTS listening wording, names, numbers, currency, postcodes, and discourse markers.", help="ASR context prompt.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing generated artifacts.")
    parser.add_argument("--model-root", default=str(DEFAULT_MODEL_ROOT), help="Root containing local Qwen model directories.")
    parser.add_argument("--ffmpeg", default=str(DEFAULT_FFMPEG), help="ffmpeg executable passed to the wrapper.")
    parser.add_argument("--ffprobe", default=str(DEFAULT_FFPROBE), help="Documented ffprobe path for environment diagnostics.")
    return parser


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: Any, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def section_audio(pack_root: Path, section: int) -> Path:
    return pack_root / "assets" / "audio" / f"section-{section:02d}.mp3"


def find_project_root(pack_root: Path) -> Path:
    for candidate in (pack_root, *pack_root.parents):
        if (candidate / "package.json").exists():
            return candidate
    return Path.cwd()


def work_dir_for(pack_root: Path) -> Path:
    return find_project_root(pack_root) / "待删除" / "yasi-forced-alignment"


def normalize_token(text: str) -> str:
    value = unicodedata.normalize("NFKC", text).strip().lower()
    for mark in ("’", "‘", "`"):
        value = value.replace(mark, "'")
    value = value.replace(",", "")
    for symbol in CURRENCY:
        value = value.replace(symbol, "")
    value = value.replace("-", "")
    value = value.replace("'", "")
    return re.sub(r"[^a-z0-9]+", "", value)


def token_risks(text: str) -> tuple[str, ...]:
    risks: list[str] = []
    if any(ch in text for ch in APOSTROPHES):
        risks.append("apostrophe")
    if "-" in text:
        if re.fullmatch(r"[A-Za-z](?:-[A-Za-z])+", text):
            risks.append("hyphen-spelling")
        else:
            risks.append("hyphenated")
    if any(ch.isdigit() for ch in text):
        risks.append("number")
    if any(ch in text for ch in CURRENCY):
        risks.append("currency")
    if re.search(r"[A-Za-z]*\d+[A-Za-z]+|[A-Za-z]+\d+[A-Za-z]*", text):
        risks.append("alphanumeric")
    return tuple(risks)


def tokenize_text(text: str) -> list[tuple[str, str, tuple[str, ...]]]:
    tokens = []
    for match in TOKEN_RE.finditer(text):
        raw = match.group(0)
        normalized = normalize_token(raw)
        if normalized:
            tokens.append((raw, normalized, token_risks(raw)))
    return tokens


def load_official_sections(transcript_path: Path) -> dict[int, dict[str, Any]]:
    data = load_json(transcript_path)
    if not isinstance(data, list):
        raise ValueError(f"Expected transcript root list: {transcript_path}")
    sections: dict[int, dict[str, Any]] = {}
    for item in data:
        section = int(item["section"])
        sections[section] = item
    return sections


def official_tokens(section_payload: dict[str, Any]) -> list[Token]:
    out: list[Token] = []
    global_index = 0
    for segment in section_payload.get("segments", []):
        order = int(segment["order"])
        for token_index, (raw, normalized, risks) in enumerate(tokenize_text(str(segment.get("text", "")))):
            out.append(
                Token(
                    text=raw,
                    normalized=normalized,
                    segment_order=order,
                    token_index=token_index,
                    global_index=global_index,
                    risks=risks,
                )
            )
            global_index += 1
    return out


def make_review_item(
    *,
    section: int,
    item_type: str,
    severity: str,
    message: str,
    segment_order: int | None = None,
    token_index: int | None = None,
    token: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "section": section,
        "type": item_type,
        "severity": severity,
        "message": message,
    }
    if segment_order is not None:
        item["segmentOrder"] = segment_order
    if token_index is not None:
        item["tokenIndex"] = token_index
    if token is not None:
        item["token"] = token
    if details:
        item["details"] = details
    return item


def scalar_time(item: dict[str, Any], *names: str) -> float | None:
    for name in names:
        value = item.get(name)
        if value is not None:
            return float(value)
    return None


def split_timed_item(text: str, start: float, end: float, source_index: int) -> list[TimedToken]:
    parts = tokenize_text(text)
    if not parts:
        return []
    duration = max(0.0, end - start)
    step = duration / len(parts) if parts else 0.0
    out = []
    for idx, (raw, normalized, _risks) in enumerate(parts):
        token_start = start + step * idx
        token_end = end if idx == len(parts) - 1 else start + step * (idx + 1)
        out.append(TimedToken(raw, normalized, token_start, token_end, source_index))
    return out


def timed_tokens_from_qwen(payload: dict[str, Any], section: int, review_items: list[dict[str, Any]]) -> list[TimedToken]:
    timed: list[TimedToken] = []
    raw_items = payload.get("timestamps") or payload.get("words") or payload.get("word_timestamps") or []
    for source_index, item in enumerate(raw_items):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or item.get("word") or item.get("token") or "")
        start = scalar_time(item, "start_time", "start", "startTime")
        end = scalar_time(item, "end_time", "end", "endTime")
        if start is None or end is None:
            review_items.append(
                make_review_item(
                    section=section,
                    item_type="qwen-token-missing-time",
                    severity="warning",
                    message="Qwen timestamp item had text without both start and end.",
                    token=text,
                    details={"sourceIndex": source_index},
                )
            )
            continue
        timed.extend(split_timed_item(text, start, end, source_index))

    if timed:
        return timed

    for source_index, segment in enumerate(payload.get("segments") or []):
        if not isinstance(segment, dict):
            continue
        text = str(segment.get("text") or "")
        start = scalar_time(segment, "start", "start_time", "startTime")
        end = scalar_time(segment, "end", "end_time", "endTime")
        if start is None or end is None:
            continue
        timed.extend(split_timed_item(text, start, end, source_index))
    if timed:
        review_items.append(
            make_review_item(
                section=section,
                item_type="segment-interpolated-timing",
                severity="warning",
                message="Wrapper JSON lacked word timestamps, so segment timings were split evenly across tokens.",
            )
        )
    else:
        review_items.append(
            make_review_item(
                section=section,
                item_type="no-word-timings",
                severity="error",
                message="Wrapper JSON contained no usable word or segment timings.",
            )
        )
    return timed


def build_wrapper_command(args: argparse.Namespace, audio: Path, work_dir: Path, section: int) -> tuple[list[str], Path]:
    basename = f"section-{section:02d}"
    qwen_json = work_dir / f"{basename}.qwen.json"
    cmd = [
        str(Path(args.qwen_python)),
        str(Path(args.qwen_wrapper)),
        "--input",
        str(audio),
        "--output-dir",
        str(work_dir),
        "--basename",
        basename,
        "--profile",
        args.profile,
        "--language",
        args.language,
        "--context",
        args.context,
        "--model-root",
        str(Path(args.model_root)),
        "--ffmpeg",
        str(Path(args.ffmpeg)),
    ]
    if args.overwrite:
        cmd.append("--overwrite")
    return cmd, qwen_json


def run_wrapper(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=True, text=True, capture_output=True)


def review_reasons_for(entry: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if entry.get("risks"):
        reasons.extend(f"risk:{risk}" for risk in entry["risks"])
    if entry.get("match") != "exact":
        reasons.append(f"match:{entry.get('match')}")
    if entry.get("start") is None or entry.get("end") is None:
        reasons.append("missing-timing")
    return reasons


def review_id_for(section: int, global_token_index: int) -> str:
    return f"s{section:02d}-g{global_token_index:04d}"


def token_context(word_timings: list[dict[str, Any]], index: int, radius: int = 4) -> list[dict[str, Any]]:
    out = []
    for item in word_timings[max(0, index - radius) : min(len(word_timings), index + radius + 1)]:
        out.append(
            {
                "segmentOrder": item.get("segmentOrder"),
                "tokenIndex": item.get("tokenIndex"),
                "globalTokenIndex": item.get("globalTokenIndex"),
                "token": item.get("token"),
                "start": item.get("start"),
                "end": item.get("end"),
            }
        )
    return out


def map_tokens(section: int, official: list[Token], timed: list[TimedToken]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    review_items: list[dict[str, Any]] = []
    official_norms = [token.normalized for token in official]
    timed_norms = [token.normalized for token in timed]
    matches: dict[int, int] = {}

    matcher = difflib.SequenceMatcher(a=official_norms, b=timed_norms, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                matches[i1 + offset] = j1 + offset
            continue
        details = {
            "officialRange": [i1, i2],
            "qwenRange": [j1, j2],
            "officialSample": [t.text for t in official[i1 : min(i2, i1 + 8)]],
            "qwenSample": [t.text for t in timed[j1 : min(j2, j1 + 8)]],
        }
        review_items.append(
            make_review_item(
                section=section,
                item_type=f"sequence-{tag}",
                severity="warning",
                message="Official transcript tokens and Qwen timed tokens diverged.",
                details=details,
            )
        )

    word_timings: list[dict[str, Any]] = []
    missing = 0
    last_start: float | None = None
    timing_errors = 0
    for token in official:
        source_index = matches.get(token.global_index)
        source_token = timed[source_index] if source_index is not None else None
        start = source_token.start if source_token else None
        end = source_token.end if source_token else None
        match = "exact" if source_token else "unmatched"
        if source_token is None:
            missing += 1
        elif end <= start:
            timing_errors += 1
            review_items.append(
                make_review_item(
                    section=section,
                    item_type="non-positive-interval",
                    severity="error",
                    message="Mapped token timing has a non-positive interval.",
                    segment_order=token.segment_order,
                    token_index=token.token_index,
                    token=token.text,
                    details={"start": start, "end": end},
                )
            )
        elif last_start is not None and start < last_start - 0.025:
            timing_errors += 1
            review_items.append(
                make_review_item(
                    section=section,
                    item_type="non-monotonic-token",
                    severity="error",
                    message="Mapped token start time moved backward.",
                    segment_order=token.segment_order,
                    token_index=token.token_index,
                    token=token.text,
                    details={"previousStart": last_start, "start": start},
                )
            )
        if start is not None:
            last_start = start
        for risk in token.risks:
            review_items.append(
                make_review_item(
                    section=section,
                    item_type="token-review-risk",
                    severity="warning",
                    message=f"Official token needs durable mapping review because it contains {risk}.",
                    segment_order=token.segment_order,
                    token_index=token.token_index,
                    token=token.text,
                    details={"risk": risk},
                )
            )
        entry = {
            "section": section,
            "segmentOrder": token.segment_order,
            "tokenIndex": token.token_index,
            "globalTokenIndex": token.global_index,
            "token": token.text,
            "normalized": token.normalized,
            "start": round(start, 3) if start is not None else None,
            "end": round(end, 3) if end is not None else None,
            "sourceIndex": source_index,
            "sourceToken": source_token.text if source_token else None,
            "match": match,
            "risks": list(token.risks),
        }
        entry["requiresReview"] = bool(review_reasons_for(entry))
        word_timings.append(entry)

    extra_qwen = len(timed) - len(set(matches.values()))
    if missing:
        review_items.append(
            make_review_item(
                section=section,
                item_type="missing-official-token-timing",
                severity="warning",
                message="Some official transcript tokens did not receive exact Qwen timing.",
                details={"missingCount": missing},
            )
        )
    if extra_qwen:
        review_items.append(
            make_review_item(
                section=section,
                item_type="extra-qwen-tokens",
                severity="warning",
                message="Some Qwen timed tokens did not map to official transcript tokens.",
                details={"extraCount": extra_qwen},
            )
        )
    diagnostics = {
        "officialTokenCount": len(official),
        "qwenTokenCount": len(timed),
        "timedOfficialTokenCount": len(official) - missing,
        "missingOfficialTokenCount": missing,
        "extraQwenTokenCount": extra_qwen,
        "coverageRatio": round((len(official) - missing) / len(official), 6) if official else 1.0,
        "timingErrorCount": timing_errors,
    }
    return word_timings, review_items, diagnostics


def status_from(review_items: list[dict[str, Any]], diagnostics: dict[str, Any], pending_reviews: int = 0) -> str:
    if pending_reviews:
        return "draft"
    if diagnostics.get("missingOfficialTokenCount") or diagnostics.get("timingErrorCount"):
        return "draft"
    if any(item.get("severity") in {"warning", "error"} for item in review_items):
        return "draft"
    return "verified"


def align_section(args: argparse.Namespace, section: int, transcript_sections: dict[int, dict[str, Any]], pack_root: Path, work_dir: Path) -> dict[str, Any]:
    official = official_tokens(transcript_sections[section])
    audio = section_audio(pack_root, section)
    section_review: list[dict[str, Any]] = []
    if not audio.exists():
        raise FileNotFoundError(f"Section audio not found: {audio}")

    cmd, qwen_json = build_wrapper_command(args, audio, work_dir, section)
    completed = run_wrapper(cmd)
    if completed.stderr.strip():
        section_review.append(
            make_review_item(
                section=section,
                item_type="qwen-wrapper-stderr",
                severity="info",
                message="Qwen wrapper emitted stderr; inspect if alignment looks suspicious.",
                details={"stderr": completed.stderr.strip()[-4000:]},
            )
        )
    if not qwen_json.exists():
        raise FileNotFoundError(f"Expected Qwen wrapper JSON was absent: {qwen_json}")
    payload = load_json(qwen_json)
    timed = timed_tokens_from_qwen(payload, section, section_review)
    word_timings, mapping_review, diagnostics = map_tokens(section, official, timed)
    section_review.extend(mapping_review)
    pending_reviews = sum(1 for entry in word_timings if entry.get("requiresReview"))
    return {
        "section": section,
        "status": status_from(section_review, diagnostics, pending_reviews),
        "audio": str(audio),
        "qwenJson": str(qwen_json),
        "segmentCount": len(transcript_sections[section].get("segments", [])),
        "wordTimings": word_timings,
        "reviewItems": section_review,
        "diagnostics": {**diagnostics, "pendingReviewCount": pending_reviews},
    }


def selected_sections(args: argparse.Namespace) -> list[int]:
    if args.all_sections:
        return [1, 2, 3, 4]
    if args.section:
        return sorted(set(args.section))
    return []


def tool_metadata(args: argparse.Namespace, work_dir: Path) -> dict[str, Any]:
    return {
        "name": TOOL_NAME,
        "version": TOOL_VERSION,
        "profile": args.profile,
        "language": args.language,
        "context": args.context,
        "qwenPython": str(Path(args.qwen_python)),
        "qwenWrapper": str(Path(args.qwen_wrapper)),
        "modelRoot": str(Path(args.model_root)),
        "forcedAligner": str(DEFAULT_ALIGNER),
        "fastAsrModel": str(DEFAULT_FAST_ASR),
        "qualityAsrModel": str(DEFAULT_QUALITY_ASR),
        "ffmpeg": str(Path(args.ffmpeg)),
        "ffprobe": str(Path(args.ffprobe)),
        "workDir": str(work_dir),
    }


def build_timing_artifact(
    args: argparse.Namespace,
    sections: list[dict[str, Any]],
    pack_root: Path,
    transcript: Path,
    work_dir: Path,
    review_artifact: Path | None,
    generated_from_review: bool,
    review_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    review_items = [item for section in sections for item in section.get("reviewItems", [])]
    status = "verified" if sections and all(section.get("status") == "verified" for section in sections) else "draft"
    payload: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "status": status,
        "generatedAt": utc_now(),
        "tool": tool_metadata(args, work_dir),
        "packRoot": str(pack_root),
        "transcript": str(transcript),
        "reviewArtifact": str(review_artifact) if review_artifact else None,
        "generatedFromReview": generated_from_review,
        "sections": sections,
        "reviewItems": review_items,
    }
    if review_summary:
        payload["reviewSummary"] = review_summary
    return payload


def build_mapping_reviews(section_payload: dict[str, Any]) -> list[dict[str, Any]]:
    section = int(section_payload["section"])
    word_timings = section_payload.get("wordTimings", [])
    reviews = []
    for index, entry in enumerate(word_timings):
        reasons = review_reasons_for(entry)
        if not reasons:
            continue
        reviews.append(
            {
                "reviewId": review_id_for(section, int(entry["globalTokenIndex"])),
                "section": section,
                "segmentOrder": entry.get("segmentOrder"),
                "tokenIndex": entry.get("tokenIndex"),
                "globalTokenIndex": entry.get("globalTokenIndex"),
                "token": entry.get("token"),
                "normalized": entry.get("normalized"),
                "riskTypes": list(entry.get("risks") or []),
                "reasons": reasons,
                "auto": {
                    "start": entry.get("start"),
                    "end": entry.get("end"),
                    "sourceIndex": entry.get("sourceIndex"),
                    "sourceToken": entry.get("sourceToken"),
                    "match": entry.get("match"),
                },
                "context": token_context(word_timings, index),
                "decision": "pending",
                "correction": None,
                "reviewer": None,
                "reviewedAt": None,
                "notes": "",
            }
        )
    return reviews


def build_review_artifact(
    args: argparse.Namespace,
    sections: list[dict[str, Any]],
    pack_root: Path,
    transcript: Path,
    work_dir: Path,
    draft_output: Path,
    final_output: Path,
) -> dict[str, Any]:
    review_sections = []
    pending_count = 0
    for section_payload in sections:
        mapping_reviews = build_mapping_reviews(section_payload)
        pending_count += sum(1 for item in mapping_reviews if item.get("decision") == "pending")
        review_sections.append(
            {
                "section": section_payload["section"],
                "status": "needs-review" if mapping_reviews else "no-review-needed",
                "audio": section_payload.get("audio"),
                "qwenJson": section_payload.get("qwenJson"),
                "autoMapping": {
                    "schemaVersion": SCHEMA_VERSION,
                    "status": section_payload.get("status"),
                    "segmentCount": section_payload.get("segmentCount"),
                    "wordTimings": section_payload.get("wordTimings", []),
                    "reviewItems": section_payload.get("reviewItems", []),
                    "diagnostics": section_payload.get("diagnostics", {}),
                },
                "mappingReviews": mapping_reviews,
            }
        )
    return {
        "schemaVersion": REVIEW_SCHEMA_VERSION,
        "status": "needs-review" if pending_count else "reviewed",
        "generatedAt": utc_now(),
        "tool": tool_metadata(args, work_dir),
        "packRoot": str(pack_root),
        "transcript": str(transcript),
        "draftTimingArtifact": str(draft_output),
        "finalTimingArtifact": str(final_output),
        "instructions": {
            "decision": "Set each mappingReviews[].decision to approved or corrected after review.",
            "approved": "Use approved when the automatic timing is correct.",
            "corrected": "Use corrected with correction.start and correction.end when the automatic timing is wrong.",
            "audit": "Keep reviewer, reviewedAt, notes, and correction fields so special mappings remain traceable.",
        },
        "sections": review_sections,
    }


def review_map_for(review_payload: dict[str, Any]) -> dict[tuple[int, int, int], dict[str, Any]]:
    out: dict[tuple[int, int, int], dict[str, Any]] = {}
    for section_payload in review_payload.get("sections") or []:
        for item in section_payload.get("mappingReviews") or []:
            identity = (int(item["section"]), int(item["segmentOrder"]), int(item["tokenIndex"]))
            out[identity] = item
    return out


def trace_for(review_path: Path, review_item: dict[str, Any], decision: str) -> dict[str, Any]:
    correction = review_item.get("correction") or {}
    return {
        "reviewArtifact": str(review_path),
        "reviewId": review_item.get("reviewId"),
        "decision": decision,
        "riskTypes": list(review_item.get("riskTypes") or []),
        "reasons": list(review_item.get("reasons") or []),
        "reviewer": correction.get("reviewer") or review_item.get("reviewer"),
        "reviewedAt": correction.get("reviewedAt") or review_item.get("reviewedAt"),
        "notes": correction.get("notes") or review_item.get("notes") or "",
    }


def apply_review_to_section(section_payload: dict[str, Any], review_path: Path, review_lookup: dict[tuple[int, int, int], dict[str, Any]]) -> tuple[dict[str, Any], dict[str, int]]:
    section = int(section_payload["section"])
    out = {
        "section": section,
        "status": "verified",
        "audio": section_payload.get("audio"),
        "qwenJson": section_payload.get("qwenJson"),
        "segmentCount": section_payload.get("autoMapping", {}).get("segmentCount"),
        "wordTimings": [],
        "reviewItems": [],
        "diagnostics": dict(section_payload.get("autoMapping", {}).get("diagnostics") or {}),
    }
    counts = {"pending": 0, "approved": 0, "corrected": 0, "rejected": 0, "missingTrace": 0}
    for entry in copy.deepcopy(section_payload.get("autoMapping", {}).get("wordTimings") or []):
        identity = (section, int(entry["segmentOrder"]), int(entry["tokenIndex"]))
        review_item = review_lookup.get(identity)
        reasons = review_reasons_for(entry)
        if review_item:
            decision = str(review_item.get("decision") or "pending")
            if decision == "approved":
                if entry.get("start") is None or entry.get("end") is None:
                    counts["pending"] += 1
                    out["reviewItems"].append(
                        make_review_item(
                            section=section,
                            item_type="approved-mapping-missing-time",
                            severity="error",
                            message="Reviewed mapping was approved while automatic timing was absent.",
                            segment_order=entry.get("segmentOrder"),
                            token_index=entry.get("tokenIndex"),
                            token=entry.get("token"),
                            details={"reviewId": review_item.get("reviewId")},
                        )
                    )
                else:
                    counts["approved"] += 1
                    entry["review"] = trace_for(review_path, review_item, decision)
            elif decision == "corrected":
                correction = review_item.get("correction") or {}
                start = correction.get("start")
                end = correction.get("end")
                if not isinstance(start, (int, float)) or not isinstance(end, (int, float)) or end <= start:
                    counts["pending"] += 1
                    out["reviewItems"].append(
                        make_review_item(
                            section=section,
                            item_type="invalid-review-correction",
                            severity="error",
                            message="Corrected mapping requires numeric correction.start and correction.end with a positive interval.",
                            segment_order=entry.get("segmentOrder"),
                            token_index=entry.get("tokenIndex"),
                            token=entry.get("token"),
                            details={"reviewId": review_item.get("reviewId"), "correction": correction},
                        )
                    )
                else:
                    counts["corrected"] += 1
                    entry["start"] = round(float(start), 3)
                    entry["end"] = round(float(end), 3)
                    entry["sourceIndex"] = correction.get("sourceIndex", entry.get("sourceIndex"))
                    entry["sourceToken"] = correction.get("sourceToken", entry.get("sourceToken"))
                    entry["match"] = "review-corrected"
                    entry["review"] = trace_for(review_path, review_item, decision)
            elif decision == "rejected":
                counts["rejected"] += 1
                out["reviewItems"].append(
                    make_review_item(
                        section=section,
                        item_type="review-rejected-mapping",
                        severity="warning",
                        message="Review rejected this automatic mapping and no corrected timing was supplied.",
                        segment_order=entry.get("segmentOrder"),
                        token_index=entry.get("tokenIndex"),
                        token=entry.get("token"),
                        details={"reviewId": review_item.get("reviewId")},
                    )
                )
            else:
                counts["pending"] += 1
                out["reviewItems"].append(
                    make_review_item(
                        section=section,
                        item_type="pending-review-mapping",
                        severity="warning",
                        message="Mapping still needs an approved or corrected review decision.",
                        segment_order=entry.get("segmentOrder"),
                        token_index=entry.get("tokenIndex"),
                        token=entry.get("token"),
                        details={"reviewId": review_item.get("reviewId"), "decision": decision},
                    )
                )
        elif reasons:
            counts["missingTrace"] += 1
            out["reviewItems"].append(
                make_review_item(
                    section=section,
                    item_type="missing-review-trace",
                    severity="warning",
                    message="A mapping that requires review has no entry in alignment-review.json.",
                    segment_order=entry.get("segmentOrder"),
                    token_index=entry.get("tokenIndex"),
                    token=entry.get("token"),
                    details={"reasons": reasons},
                )
            )
        out["wordTimings"].append(entry)

    unresolved = counts["pending"] + counts["rejected"] + counts["missingTrace"]
    out["diagnostics"]["reviewPendingCount"] = counts["pending"]
    out["diagnostics"]["reviewApprovedCount"] = counts["approved"]
    out["diagnostics"]["reviewCorrectedCount"] = counts["corrected"]
    out["diagnostics"]["reviewRejectedCount"] = counts["rejected"]
    out["diagnostics"]["reviewMissingTraceCount"] = counts["missingTrace"]
    out["status"] = "draft" if unresolved or out["reviewItems"] else "verified"
    return out, counts


def finalize_from_review(
    args: argparse.Namespace,
    review_path: Path,
    transcript_sections: dict[int, dict[str, Any]],
    pack_root: Path,
    transcript: Path,
    work_dir: Path,
) -> dict[str, Any]:
    review_payload = load_json(review_path)
    if review_payload.get("schemaVersion") != REVIEW_SCHEMA_VERSION:
        raise ValueError(f"Expected {REVIEW_SCHEMA_VERSION} in review artifact: {review_path}")
    review_lookup = review_map_for(review_payload)
    sections = []
    totals = {"pending": 0, "approved": 0, "corrected": 0, "rejected": 0, "missingTrace": 0}
    for section_payload in review_payload.get("sections") or []:
        section = int(section_payload["section"])
        if section not in transcript_sections:
            raise ValueError(f"Review artifact references section absent from transcript: {section}")
        final_section, counts = apply_review_to_section(section_payload, review_path, review_lookup)
        sections.append(final_section)
        for key, value in counts.items():
            totals[key] += value
    review_summary = {
        "artifact": str(review_path),
        "pendingCount": totals["pending"],
        "approvedCount": totals["approved"],
        "correctedCount": totals["corrected"],
        "rejectedCount": totals["rejected"],
        "missingTraceCount": totals["missingTrace"],
    }
    return build_timing_artifact(args, sections, pack_root, transcript, work_dir, review_path, True, review_summary)


def dry_run_plan(args: argparse.Namespace, transcript_sections: dict[int, dict[str, Any]], pack_root: Path, transcript: Path, work_dir: Path) -> dict[str, Any]:
    if args.finalize_review:
        review_input = Path(args.review_input or args.review_output)
        return {
            "dryRun": True,
            "mode": "finalize-review",
            "schemaVersion": SCHEMA_VERSION,
            "reviewInput": str(review_input),
            "reviewInputExists": review_input.exists(),
            "output": str(Path(args.output)),
            "transcript": str(transcript),
        }

    planned = []
    for section in selected_sections(args):
        audio = section_audio(pack_root, section)
        cmd, qwen_json = build_wrapper_command(args, audio, work_dir, section)
        planned.append(
            {
                "section": section,
                "audio": str(audio),
                "audioExists": audio.exists(),
                "officialSegmentCount": len(transcript_sections[section].get("segments", [])),
                "officialTokenCount": len(official_tokens(transcript_sections[section])),
                "qwenJson": str(qwen_json),
                "wrapperCommand": cmd,
            }
        )
    return {
        "dryRun": True,
        "mode": "align-and-review",
        "schemaVersion": SCHEMA_VERSION,
        "reviewSchemaVersion": REVIEW_SCHEMA_VERSION,
        "packRoot": str(pack_root),
        "transcript": str(transcript),
        "draftOutput": str(Path(args.draft_output)),
        "reviewOutput": str(Path(args.review_output)),
        "finalOutput": str(Path(args.output)),
        "qwenPythonExists": Path(args.qwen_python).exists(),
        "qwenWrapperExists": Path(args.qwen_wrapper).exists(),
        "modelRootExists": Path(args.model_root).exists(),
        "forcedAlignerExists": DEFAULT_ALIGNER.exists(),
        "fastAsrModelExists": DEFAULT_FAST_ASR.exists(),
        "qualityAsrModelExists": DEFAULT_QUALITY_ASR.exists(),
        "ffmpegExists": Path(args.ffmpeg).exists(),
        "ffprobeExists": Path(args.ffprobe).exists(),
        "workDir": str(work_dir),
        "plannedSections": planned,
    }


def validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace, transcript_sections: dict[int, dict[str, Any]]) -> None:
    sections = selected_sections(args)
    if args.finalize_review and sections:
        parser.error("--finalize-review reads sections from the review artifact; omit --section and --all-sections.")
    if not args.finalize_review and not sections:
        parser.error("alignment mode requires --section or --all-sections.")
    missing_sections = [section for section in sections if section not in transcript_sections]
    if missing_sections:
        parser.error(f"Transcript is missing requested section(s): {missing_sections}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    pack_root = Path(args.pack_root)
    transcript = Path(args.transcript)
    output = Path(args.output)
    draft_output = Path(args.draft_output)
    review_output = Path(args.review_output)
    work_dir = work_dir_for(pack_root)
    transcript_sections = load_official_sections(transcript)
    validate_args(parser, args, transcript_sections)

    if args.dry_run:
        print(json.dumps(dry_run_plan(args, transcript_sections, pack_root, transcript, work_dir), ensure_ascii=False, indent=2))
        return 0

    if args.finalize_review:
        review_input = Path(args.review_input or args.review_output)
        artifact = finalize_from_review(args, review_input, transcript_sections, pack_root, transcript, work_dir)
        write_json(output, artifact, args.overwrite)
        print(json.dumps({"output": str(output), "status": artifact["status"], "reviewInput": str(review_input)}, ensure_ascii=False))
        return 0

    work_dir.mkdir(parents=True, exist_ok=True)
    sections = [align_section(args, section, transcript_sections, pack_root, work_dir) for section in selected_sections(args)]
    draft_artifact = build_timing_artifact(args, sections, pack_root, transcript, work_dir, review_output, False)
    review_artifact = build_review_artifact(args, sections, pack_root, transcript, work_dir, draft_output, output)
    write_json(draft_output, draft_artifact, args.overwrite)
    write_json(review_output, review_artifact, args.overwrite)
    pending = sum(
        1
        for section_payload in review_artifact["sections"]
        for item in section_payload.get("mappingReviews", [])
        if item.get("decision") == "pending"
    )
    print(
        json.dumps(
            {
                "draftOutput": str(draft_output),
                "reviewOutput": str(review_output),
                "pendingReviewCount": pending,
                "finalizeCommand": [
                    str(Path(args.qwen_python)),
                    str(Path(__file__)),
                    "--finalize-review",
                    "--review-input",
                    str(review_output),
                    "--output",
                    str(output),
                    "--overwrite",
                ],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"Qwen wrapper failed with exit code {exc.returncode}", file=sys.stderr)
        print("Command:", " ".join(exc.cmd), file=sys.stderr)
        if exc.stdout:
            print("stdout:", exc.stdout[-4000:], file=sys.stderr)
        if exc.stderr:
            print("stderr:", exc.stderr[-4000:], file=sys.stderr)
        raise SystemExit(exc.returncode)
