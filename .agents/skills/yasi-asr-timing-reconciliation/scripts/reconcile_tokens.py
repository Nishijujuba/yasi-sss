#!/usr/bin/env python3
"""Reconcile timestamped ASR words against official transcript tokens."""

from __future__ import annotations

import argparse
import difflib
import json
import math
import re
import unicodedata
from pathlib import Path
from typing import Any

REPORT_SCHEMA_VERSION = "yasi.reconciliation-report.v1"
TIMING_SCHEMA_VERSION = "yasi.transcript-timings.v1"
FUZZY_THRESHOLD = 0.6
INSERT_COST = 1.0
DELETE_COST = 1.0
FUZZY_COST = 0.35
MISMATCH_COST = 2.1
MAX_AUTO_GAP_TOKENS = 3
MAX_AUTO_ANCHOR_SPAN_SECONDS = 2.5

TOKEN_RE = re.compile(
    "[\u00a3$\u20ac]?\\d+(?:[,.]\\d+)*(?:-[A-Za-z0-9]+)?|"
    "[A-Za-z0-9]+(?:[\u2019\u2018'`][A-Za-z0-9]+)?(?:-[A-Za-z0-9]+)*"
)
APOSTROPHES = {"'", "\u2019", "\u2018", "`"}
CURRENCY = {"$", "\u00a3", "\u20ac"}
MATCH_TYPES = ("exact", "fuzzy", "interpolated", "split", "merged", "unmatched")
ANCHOR_MATCH_TYPES = {"exact", "fuzzy"}


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: Any) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _ordered_unique(values: list[Any]) -> list[Any]:
    out: list[Any] = []
    for value in values:
        if value not in out:
            out.append(value)
    return out


def _round_time(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 3)


def _scalar_time(item: dict[str, Any], *names: str) -> float | None:
    for name in names:
        if item.get(name) is not None:
            return float(item[name])
    return None


def _token_risks(text: str) -> list[str]:
    risks: list[str] = []
    if any(mark in text for mark in APOSTROPHES):
        risks.append("apostrophe")
    if "-" in text:
        if re.fullmatch(r"[A-Za-z](?:-[A-Za-z])+", text):
            risks.append("hyphen-spelling")
        else:
            risks.append("hyphenated")
    if any(ch.isdigit() for ch in text):
        risks.append("number")
    if any(ch in CURRENCY for ch in text):
        risks.append("currency")
    if re.search(r"[A-Za-z]*\d+[A-Za-z]+|[A-Za-z]+\d+[A-Za-z]*", text):
        risks.append("alphanumeric")
    return risks


def normalize_token(
    text: str,
    *,
    answer_refs: list[int | str] | None = None,
    answer_near: bool = False,
) -> dict[str, Any]:
    """Return normalized token identity plus review-risk metadata."""
    raw = str(text).strip()
    value = unicodedata.normalize("NFKC", raw).strip().lower()
    for mark in ("\u2019", "\u2018", "`"):
        value = value.replace(mark, "'")
    value = value.replace(",", "")
    for symbol in CURRENCY:
        value = value.replace(symbol, "")
    value = value.replace("-", "")
    value = value.replace("'", "")
    normalized = re.sub(r"[^a-z0-9]+", "", value)
    risks = _token_risks(raw)
    refs = list(answer_refs or [])
    if answer_near or refs:
        risks.append("answer-near")
    risks = _ordered_unique(risks)
    return {
        "text": raw,
        "normalized": normalized,
        "riskTypes": risks,
        "isHighRisk": bool(risks),
        "answerRefs": refs,
    }


def tokenize_text(text: str, *, answer_refs: list[int | str] | None = None) -> list[dict[str, Any]]:
    tokens: list[dict[str, Any]] = []
    for match in TOKEN_RE.finditer(str(text)):
        identity = normalize_token(match.group(0), answer_refs=answer_refs, answer_near=bool(answer_refs))
        if identity["normalized"]:
            tokens.append(identity)
    return tokens


def _section_payloads(transcript_payload: Any, section: int | None) -> list[dict[str, Any]]:
    if isinstance(transcript_payload, list):
        payloads = transcript_payload
    elif isinstance(transcript_payload, dict) and isinstance(transcript_payload.get("sections"), list):
        payloads = transcript_payload["sections"]
    elif isinstance(transcript_payload, dict) and "segments" in transcript_payload:
        payloads = [transcript_payload]
    else:
        raise ValueError("Expected transcript payload with section segments.")
    if section is None:
        return [dict(item) for item in payloads]
    selected = [dict(item) for item in payloads if int(item.get("section", section)) == int(section)]
    if not selected:
        raise ValueError(f"Section {section} was not found in official transcript.")
    return selected


def flatten_official_transcript(transcript_payload: Any, *, section: int | None = None) -> list[dict[str, Any]]:
    """Flatten official transcript text into stable token identities."""
    out: list[dict[str, Any]] = []
    for section_payload in _section_payloads(transcript_payload, section):
        section_number = int(section_payload.get("section", section or 0))
        global_index = 0
        for segment in section_payload.get("segments", []):
            segment_order = int(segment.get("order", len(out) + 1))
            answer_refs = list(segment.get("answerRefs") or [])
            for token_index, identity in enumerate(tokenize_text(segment.get("text", ""), answer_refs=answer_refs)):
                out.append(
                    {
                        "section": section_number,
                        "segmentOrder": segment_order,
                        "tokenIndex": token_index,
                        "globalTokenIndex": global_index,
                        "text": identity["text"],
                        "normalized": identity["normalized"],
                        "riskTypes": list(identity["riskTypes"]),
                        "isHighRisk": bool(identity["isHighRisk"]),
                        "answerRefs": list(identity["answerRefs"]),
                    }
                )
                global_index += 1
    return out


def _iter_asr_items(asr_payload: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(asr_payload.get("words"), list):
        return list(asr_payload["words"])
    words: list[dict[str, Any]] = []
    for segment in asr_payload.get("segments") or []:
        if isinstance(segment.get("words"), list):
            words.extend(segment["words"])
        elif segment.get("text"):
            words.append(segment)
    return words


def flatten_asr_words(asr_payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten ASR word timestamp shapes into normalized timed tokens."""
    out: list[dict[str, Any]] = []
    for fallback_index, item in enumerate(_iter_asr_items(asr_payload)):
        word = str(item.get("word") or item.get("text") or item.get("token") or "").strip()
        identity = normalize_token(word)
        if not identity["normalized"]:
            continue
        start = _scalar_time(item, "start", "startTime", "start_time")
        end = _scalar_time(item, "end", "endTime", "end_time")
        out.append(
            {
                "sourceIndex": int(item.get("index", item.get("sourceIndex", fallback_index))),
                "word": identity["text"],
                "normalized": identity["normalized"],
                "start": _round_time(start),
                "end": _round_time(end),
                "riskTypes": list(identity["riskTypes"]),
            }
        )
    return out


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return difflib.SequenceMatcher(a=left, b=right, autojunk=False).ratio()


def _looks_like_compound_fragment(left: str, right: str) -> bool:
    if left == right:
        return False
    if abs(len(left) - len(right)) < 3:
        return False
    return (
        left.startswith(right)
        or left.endswith(right)
        or right.startswith(left)
        or right.endswith(left)
    )


def _substitution(official: dict[str, Any], asr: dict[str, Any], *, fuzzy_threshold: float) -> tuple[float, str, float]:
    left = str(official["normalized"])
    right = str(asr["normalized"])
    if left == right:
        return 0.0, "exact", 1.0
    score = _similarity(left, right)
    if _looks_like_compound_fragment(left, right):
        return MISMATCH_COST, "unmatched", score
    if score >= fuzzy_threshold:
        return FUZZY_COST, "fuzzy", score
    return MISMATCH_COST, "unmatched", score


def align_sequences(
    official_tokens: list[dict[str, Any]],
    asr_words: list[dict[str, Any]],
    *,
    fuzzy_threshold: float = FUZZY_THRESHOLD,
) -> list[dict[str, Any]]:
    """Align official tokens to ASR words with dynamic programming."""
    n = len(official_tokens)
    m = len(asr_words)
    dp = [[math.inf for _ in range(m + 1)] for _ in range(n + 1)]
    back: list[list[dict[str, Any] | None]] = [[None for _ in range(m + 1)] for _ in range(n + 1)]
    dp[0][0] = 0.0

    for i in range(1, n + 1):
        dp[i][0] = dp[i - 1][0] + DELETE_COST
        back[i][0] = {"op": "delete", "officialIndex": i - 1}
    for j in range(1, m + 1):
        dp[0][j] = dp[0][j - 1] + INSERT_COST
        back[0][j] = {"op": "insert", "asrIndex": j - 1}

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            sub_cost, match_type, score = _substitution(
                official_tokens[i - 1],
                asr_words[j - 1],
                fuzzy_threshold=fuzzy_threshold,
            )
            candidates = [
                (
                    dp[i - 1][j - 1] + sub_cost,
                    0,
                    {
                        "op": "pair",
                        "officialIndex": i - 1,
                        "asrIndex": j - 1,
                        "matchType": match_type,
                        "similarity": round(score, 6),
                    },
                ),
                (dp[i - 1][j] + DELETE_COST, 1, {"op": "delete", "officialIndex": i - 1}),
                (dp[i][j - 1] + INSERT_COST, 2, {"op": "insert", "asrIndex": j - 1}),
            ]
            cost, _priority, op = min(candidates, key=lambda item: (item[0], item[1]))
            dp[i][j] = cost
            back[i][j] = op

    operations: list[dict[str, Any]] = []
    i = n
    j = m
    while i > 0 or j > 0:
        op = back[i][j]
        if op is None:
            raise RuntimeError("Alignment backtrace reached an empty operation.")
        operations.append(op)
        if op["op"] == "pair":
            i -= 1
            j -= 1
        elif op["op"] == "delete":
            i -= 1
        elif op["op"] == "insert":
            j -= 1
        else:
            raise RuntimeError(f"Unknown alignment operation: {op['op']}")
    operations.reverse()
    return operations


def _review_id(section: int, global_token_index: int) -> str:
    return f"s{section:02d}-g{global_token_index:04d}"


def _official_token_ref(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "section": entry["section"],
        "segmentOrder": entry["segmentOrder"],
        "tokenIndex": entry["tokenIndex"],
        "globalTokenIndex": entry["globalTokenIndex"],
        "text": entry["token"],
        "normalized": entry["normalized"],
        "answerRefs": list(entry.get("answerRefs") or []),
    }


def _source_word_ref(entry: dict[str, Any]) -> dict[str, Any] | None:
    if entry.get("sourceIndex") is None:
        return None
    return {
        "sourceIndex": entry.get("sourceIndex"),
        "word": entry.get("sourceWord"),
        "normalized": entry.get("sourceNormalized"),
        "start": entry.get("start"),
        "end": entry.get("end"),
    }


def _source_words_ref(entry: dict[str, Any]) -> list[dict[str, Any]]:
    source_indexes = list(entry.get("sourceIndexes") or [])
    source_words = list(entry.get("sourceWords") or [])
    source_starts = list(entry.get("sourceStarts") or [])
    source_ends = list(entry.get("sourceEnds") or [])
    out: list[dict[str, Any]] = []
    for index, word in zip(source_indexes, source_words):
        item: dict[str, Any] = {"sourceIndex": index, "word": word}
        position = len(out)
        if position < len(source_starts):
            item["start"] = source_starts[position]
        if position < len(source_ends):
            item["end"] = source_ends[position]
        out.append(item)
    return out


def _new_entry(token: dict[str, Any]) -> dict[str, Any]:
    return {
        "section": token["section"],
        "segmentOrder": token["segmentOrder"],
        "tokenIndex": token["tokenIndex"],
        "globalTokenIndex": token["globalTokenIndex"],
        "token": token["text"],
        "normalized": token["normalized"],
        "answerRefs": list(token.get("answerRefs") or []),
        "riskTypes": list(token.get("riskTypes") or []),
        "start": None,
        "end": None,
        "sourceIndex": None,
        "sourceWord": None,
        "sourceNormalized": None,
        "matchType": "unmatched",
        "match": "unmatched",
        "requiresReview": False,
        "_reviewReasons": [],
    }


def _mark_for_review(entry: dict[str, Any], reasons: list[str]) -> None:
    combined = list(entry.get("_reviewReasons") or [])
    combined.extend(reasons)
    entry["_reviewReasons"] = _ordered_unique(combined)
    entry["requiresReview"] = True


def _reset_mapping(entry: dict[str, Any]) -> None:
    preserved = {
        "section",
        "segmentOrder",
        "tokenIndex",
        "globalTokenIndex",
        "token",
        "normalized",
        "answerRefs",
        "riskTypes",
    }
    for key in list(entry):
        if key not in preserved and not key.startswith("_"):
            entry.pop(key, None)
    entry.update(
        {
            "start": None,
            "end": None,
            "sourceIndex": None,
            "sourceWord": None,
            "sourceNormalized": None,
            "matchType": "unmatched",
            "match": "unmatched",
            "requiresReview": False,
        }
    )


def _find_asr_index(
    asr_words: list[dict[str, Any]],
    start: int,
    combined: str,
    unavailable_indexes: set[int],
) -> int | None:
    for asr_index in range(start, len(asr_words)):
        if asr_index in unavailable_indexes:
            continue
        if str(asr_words[asr_index]["normalized"]) == combined:
            return asr_index
    return None


def _find_asr_span(
    asr_words: list[dict[str, Any]],
    start: int,
    combined: str,
    unavailable_indexes: set[int],
) -> tuple[int, int] | None:
    for span_start in range(start, len(asr_words)):
        if span_start in unavailable_indexes:
            continue
        value = ""
        for span_end in range(span_start, len(asr_words)):
            if span_end in unavailable_indexes:
                break
            value += str(asr_words[span_end]["normalized"])
            if value == combined and span_end > span_start:
                return span_start, span_end + 1
            if len(value) >= len(combined):
                break
    return None


def _time_bounds(words: list[dict[str, Any]]) -> tuple[float | None, float | None]:
    starts = [word.get("start") for word in words if word.get("start") is not None]
    ends = [word.get("end") for word in words if word.get("end") is not None]
    if not starts or not ends:
        return None, None
    return _round_time(min(float(value) for value in starts)), _round_time(max(float(value) for value in ends))


def _apply_merged_mapping(entries: list[dict[str, Any]], group: list[dict[str, Any]], asr: dict[str, Any]) -> None:
    group_tokens = [entry["token"] for entry in group]
    for entry in group:
        _reset_mapping(entry)
        entry["start"] = _round_time(asr.get("start"))
        entry["end"] = _round_time(asr.get("end"))
        entry["sourceIndex"] = asr.get("sourceIndex")
        entry["sourceWord"] = asr.get("word")
        entry["sourceNormalized"] = asr.get("normalized")
        entry["matchType"] = "merged"
        entry["match"] = "merged"
        entry["mergedOfficialTokens"] = group_tokens
        _mark_for_review(entry, ["match:merged"])


def _apply_split_mapping(entry: dict[str, Any], words: list[dict[str, Any]]) -> None:
    start, end = _time_bounds(words)
    _reset_mapping(entry)
    entry["start"] = start
    entry["end"] = end
    entry["sourceIndex"] = words[0].get("sourceIndex") if words else None
    entry["sourceWord"] = " ".join(str(word.get("word") or "") for word in words).strip()
    entry["sourceNormalized"] = "".join(str(word.get("normalized") or "") for word in words)
    entry["sourceIndexes"] = [word.get("sourceIndex") for word in words]
    entry["sourceWords"] = [word.get("word") for word in words]
    entry["sourceStarts"] = [_round_time(word.get("start")) for word in words]
    entry["sourceEnds"] = [_round_time(word.get("end")) for word in words]
    entry["matchType"] = "split"
    entry["match"] = "split"
    _mark_for_review(entry, ["match:split"])


def _apply_compound_mappings(
    entries: list[dict[str, Any]],
    asr_words: list[dict[str, Any]],
    *,
    paired_asr_indexes: set[int],
) -> None:
    used_official: set[int] = set()
    used_asr: set[int] = set(paired_asr_indexes)

    for start in range(len(entries)):
        if start in used_official or entries[start]["matchType"] != "unmatched":
            continue
        combined = ""
        for end in range(start, min(len(entries), start + 4)):
            if entries[end]["matchType"] != "unmatched":
                break
            combined += str(entries[end]["normalized"])
            if end == start:
                continue
            asr_index = _find_asr_index(asr_words, max(0, start - 1), combined, used_asr)
            if asr_index is None:
                continue
            group = entries[start : end + 1]
            _apply_merged_mapping(entries, group, asr_words[asr_index])
            used_official.update(range(start, end + 1))
            used_asr.add(asr_index)
            break

    for official_index, entry in enumerate(entries):
        if official_index in used_official or entry["matchType"] != "unmatched":
            continue
        span = _find_asr_span(asr_words, max(0, official_index - 1), str(entry["normalized"]), used_asr)
        if span is None:
            continue
        span_start, span_end = span
        _apply_split_mapping(entry, asr_words[span_start:span_end])
        used_official.add(official_index)
        used_asr.update(range(span_start, span_end))


def _has_valid_timing(entry: dict[str, Any]) -> bool:
    start = entry.get("start")
    end = entry.get("end")
    return start is not None and end is not None and float(end) > float(start)


def _is_anchor(entry: dict[str, Any]) -> bool:
    return entry.get("matchType") in ANCHOR_MATCH_TYPES and _has_valid_timing(entry)


def _anchor_span_seconds(left: dict[str, Any], right: dict[str, Any]) -> float:
    return round(float(right["start"]) - float(left["start"]), 6)


def _gap_failure_reasons(gap: list[dict[str, Any]], left: dict[str, Any] | None, right: dict[str, Any] | None) -> list[str]:
    reasons: list[str] = []
    if left is None:
        reasons.append("no-left-anchor")
    if right is None:
        reasons.append("no-right-anchor")
    if len(gap) > MAX_AUTO_GAP_TOKENS:
        reasons.append("gap-too-wide")
    if left is not None and right is not None:
        if float(left["end"]) >= float(right["start"]):
            reasons.append("overlapping-anchors")
        elif _anchor_span_seconds(left, right) > MAX_AUTO_ANCHOR_SPAN_SECONDS:
            reasons.append("anchor-span-too-wide")
    for entry in gap:
        for risk in entry.get("riskTypes") or []:
            reasons.append(f"risk:{risk}")
    return _ordered_unique(reasons)


def _interpolate_gap(gap: list[dict[str, Any]], left: dict[str, Any], right: dict[str, Any]) -> None:
    gap_start = float(left["end"])
    gap_end = float(right["start"])
    step = (gap_end - gap_start) / len(gap)
    for offset, entry in enumerate(gap):
        start = gap_start + offset * step
        end = gap_start + (offset + 1) * step
        entry["start"] = _round_time(start)
        entry["end"] = _round_time(end)
        entry["matchType"] = "interpolated"
        entry["match"] = "interpolated"
        entry["requiresReview"] = False
        entry["interpolation"] = {
            "method": "bounded-linear",
            "gapTokens": len(gap),
            "anchorSpanSeconds": _anchor_span_seconds(left, right),
            "leftAnchor": _official_token_ref(left),
            "rightAnchor": _official_token_ref(right),
        }


def _apply_interpolation(entries: list[dict[str, Any]]) -> None:
    index = 0
    while index < len(entries):
        if entries[index]["matchType"] != "unmatched":
            index += 1
            continue
        gap_start = index
        while index < len(entries) and entries[index]["matchType"] == "unmatched":
            index += 1
        gap = entries[gap_start:index]
        left = entries[gap_start - 1] if gap_start > 0 and _is_anchor(entries[gap_start - 1]) else None
        right = entries[index] if index < len(entries) and _is_anchor(entries[index]) else None
        reasons = _gap_failure_reasons(gap, left, right)
        if not reasons and left is not None and right is not None:
            _interpolate_gap(gap, left, right)
            continue
        for entry in gap:
            _mark_for_review(entry, [*reasons, "missing-timing"])


def _entry_review_reasons(entry: dict[str, Any]) -> list[str]:
    reasons = list(entry.get("_reviewReasons") or [])
    if entry["matchType"] == "fuzzy":
        reasons.append("match:fuzzy")
    if entry["matchType"] in {"split", "merged"}:
        reasons.append(f"match:{entry['matchType']}")
    if entry["matchType"] == "unmatched" and not _has_valid_timing(entry):
        reasons.append("missing-timing")
    if entry["matchType"] != "unmatched" and not _has_valid_timing(entry):
        reasons.append("missing-timing")
    for risk in entry.get("riskTypes") or []:
        reasons.append(f"risk:{risk}")
    if entry.get("start") is not None and entry.get("end") is not None and float(entry["end"]) <= float(entry["start"]):
        reasons.append("non-positive-interval")
    return _ordered_unique(reasons)


def _finalize_review_flags(entries: list[dict[str, Any]]) -> None:
    previous_start: float | None = None
    for entry in entries:
        reasons = _entry_review_reasons(entry)
        if entry.get("start") is not None:
            start = float(entry["start"])
            if previous_start is not None and start < previous_start - 0.025:
                reasons.append("non-monotonic-timing")
            previous_start = start
        reasons = _ordered_unique(reasons)
        entry["requiresReview"] = bool(reasons)
        entry["_reviewReasons"] = reasons


def _build_review_items(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for entry in entries:
        reasons = list(entry.get("_reviewReasons") or [])
        if not reasons:
            continue
        item: dict[str, Any] = {
            "reviewId": _review_id(int(entry["section"]), int(entry["globalTokenIndex"])),
            "section": entry["section"],
            "matchType": entry["matchType"],
            "decision": "pending",
            "officialToken": _official_token_ref(entry),
            "riskTypes": list(entry.get("riskTypes") or []),
            "reasons": reasons,
            "diagnostics": {},
        }
        source_word = _source_word_ref(entry)
        if source_word is not None:
            item["sourceWord"] = source_word
        source_words = _source_words_ref(entry)
        if source_words:
            item["sourceWords"] = list(entry.get("sourceWords") or [])
            item["sourceWordTimings"] = source_words
        if entry.get("interpolation"):
            item["diagnostics"]["interpolation"] = entry["interpolation"]
        items.append(item)
    return items


def _strip_internal_fields(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clean: list[dict[str, Any]] = []
    for entry in entries:
        item = {key: value for key, value in entry.items() if not key.startswith("_")}
        clean.append(item)
    return clean


def _match_type_counts(entries: list[dict[str, Any]]) -> dict[str, int]:
    counts = {match_type: 0 for match_type in MATCH_TYPES}
    for entry in entries:
        counts[str(entry["matchType"])] = counts.get(str(entry["matchType"]), 0) + 1
    return counts


def _longest_unanchored_gap(entries: list[dict[str, Any]]) -> int:
    longest = 0
    current = 0
    for entry in entries:
        if entry["matchType"] in ANCHOR_MATCH_TYPES:
            longest = max(longest, current)
            current = 0
        else:
            current += 1
    return max(longest, current)


def _rate(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(count / total, 6)


def _metrics(entries: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(entries)
    anchors = sum(1 for entry in entries if entry["matchType"] in ANCHOR_MATCH_TYPES and _has_valid_timing(entry))
    unmatched = sum(1 for entry in entries if entry["matchType"] == "unmatched")
    pending = sum(1 for entry in entries if entry.get("requiresReview"))
    return {
        "anchorCoverage": _rate(anchors, total),
        "unmatchedRate": _rate(unmatched, total),
        "pendingReviewRate": _rate(pending, total),
        "longestUnanchoredGap": _longest_unanchored_gap(entries),
    }


def _gate_outcome(metrics: dict[str, Any], review_items: list[dict[str, Any]]) -> str:
    if review_items and metrics["unmatchedRate"] == 0:
        return "needs-review"
    if metrics["anchorCoverage"] < 0.5 or metrics["longestUnanchoredGap"] > 8:
        return "rerun-asr"
    if review_items:
        return "needs-review"
    return "ready-for-finalize"


DIAGNOSTIC_MESSAGES = {
    "pending-review": "One or more timing mappings require review before finalization.",
    "anchor-coverage-too-low": "Anchor coverage is below the minimum useful reconciliation threshold.",
    "unanchored-gap-too-wide": "The longest unanchored token gap is too wide for reliable review.",
}


def _blocking_reasons(gate_outcome: str, metrics: dict[str, Any], review_items: list[dict[str, Any]]) -> list[str]:
    reasons: list[str] = []
    if gate_outcome == "needs-review" and review_items:
        reasons.append("pending-review")
    if gate_outcome == "rerun-asr":
        if metrics["anchorCoverage"] < 0.5:
            reasons.append("anchor-coverage-too-low")
        if metrics["longestUnanchoredGap"] > 8:
            reasons.append("unanchored-gap-too-wide")
    return _ordered_unique(reasons)


def _report_diagnostics(
    *,
    section: int,
    blocking_reasons: list[str],
    metrics: dict[str, Any],
    review_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for reason in blocking_reasons:
        item: dict[str, Any] = {
            "section": section,
            "severity": "blocking",
            "code": reason,
            "message": DIAGNOSTIC_MESSAGES.get(reason, reason),
        }
        if reason == "pending-review":
            item["reviewItemCount"] = len(review_items)
        elif reason == "anchor-coverage-too-low":
            item["anchorCoverage"] = metrics["anchorCoverage"]
        elif reason == "unanchored-gap-too-wide":
            item["longestUnanchoredGap"] = metrics["longestUnanchoredGap"]
        diagnostics.append(item)
    return diagnostics


def reconcile_tokens(
    official_tokens: list[dict[str, Any]],
    asr_words: list[dict[str, Any]],
    *,
    section: int,
    fuzzy_threshold: float = FUZZY_THRESHOLD,
    source_evidence: Any | None = None,
    review_artifact: Any | None = None,
    model: str | None = None,
    source_audio: str | None = None,
    generated_at: str | None = None,
    runtime_seconds: Any | None = None,
) -> dict[str, Any]:
    entries = [_new_entry(token) for token in official_tokens]
    operations = align_sequences(official_tokens, asr_words, fuzzy_threshold=fuzzy_threshold)
    paired_asr_indexes = {int(operation["asrIndex"]) for operation in operations if operation["op"] == "pair"}

    for operation in operations:
        if operation["op"] != "pair" or operation.get("matchType") not in ANCHOR_MATCH_TYPES:
            continue
        official_index = int(operation["officialIndex"])
        asr_index = int(operation["asrIndex"])
        asr = asr_words[asr_index]
        entry = entries[official_index]
        entry["start"] = _round_time(asr.get("start"))
        entry["end"] = _round_time(asr.get("end"))
        entry["sourceIndex"] = asr.get("sourceIndex")
        entry["sourceWord"] = asr.get("word")
        entry["sourceNormalized"] = asr.get("normalized")
        entry["matchType"] = operation["matchType"]
        entry["match"] = operation["matchType"]
        entry["similarity"] = operation.get("similarity")

    _apply_compound_mappings(entries, asr_words, paired_asr_indexes=paired_asr_indexes)
    _apply_interpolation(entries)
    _finalize_review_flags(entries)
    review_items = _build_review_items(entries)
    clean_entries = _strip_internal_fields(entries)
    counts = _match_type_counts(clean_entries)
    metrics = _metrics(clean_entries)
    if runtime_seconds is not None:
        metrics["runtimeSeconds"] = runtime_seconds
    gate_outcome = _gate_outcome(metrics, review_items)
    blocking_reasons = _blocking_reasons(gate_outcome, metrics, review_items)

    draft = {
        "schemaVersion": TIMING_SCHEMA_VERSION,
        "status": "draft",
        "sections": [
            {
                "section": section,
                "status": "draft",
                "wordTimings": clean_entries,
            }
        ],
    }
    report = {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "section": section,
        "gateOutcome": gate_outcome,
        "officialTokenCount": len(official_tokens),
        "asrWordCount": len(asr_words),
        "matchTypeCounts": counts,
        "metrics": metrics,
        "blockingReasons": blocking_reasons,
        "diagnostics": _report_diagnostics(
            section=section,
            blocking_reasons=blocking_reasons,
            metrics=metrics,
            review_items=review_items,
        ),
        "draftTimings": draft,
        "reviewItems": review_items,
        "alignment": operations,
    }
    optional_metadata = {
        "sourceEvidence": source_evidence,
        "reviewArtifact": review_artifact,
        "model": model,
        "sourceAudio": source_audio,
        "generatedAt": generated_at,
    }
    for key, value in optional_metadata.items():
        if value is not None:
            report[key] = value
    return report


def reconcile_transcript(
    transcript_payload: Any,
    asr_payload: dict[str, Any],
    *,
    section: int,
    fuzzy_threshold: float = FUZZY_THRESHOLD,
    source_evidence: Any | None = None,
    review_artifact: Any | None = None,
    model: str | None = None,
    source_audio: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    official_tokens = flatten_official_transcript(transcript_payload, section=section)
    asr_words = flatten_asr_words(asr_payload)
    asr_metrics = asr_payload.get("metrics") if isinstance(asr_payload.get("metrics"), dict) else {}
    return reconcile_tokens(
        official_tokens,
        asr_words,
        section=section,
        fuzzy_threshold=fuzzy_threshold,
        source_evidence=source_evidence,
        review_artifact=review_artifact,
        model=model,
        source_audio=source_audio,
        generated_at=generated_at,
        runtime_seconds=asr_metrics.get("runtimeSeconds"),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reconcile ASR word timings against official transcript tokens.")
    parser.add_argument("--transcript", required=True, help="Official transcript.json path.")
    parser.add_argument("--asr-evidence", required=True, help="asr-timing-evidence.json path.")
    parser.add_argument("--section", required=True, type=int, help="Listening section number.")
    parser.add_argument("--output", required=True, help="Output reconciliation-report.json path.")
    parser.add_argument("--fuzzy-threshold", type=float, default=FUZZY_THRESHOLD, help="Minimum normalized similarity for fuzzy pair mappings.")
    parser.add_argument("--source-evidence", default=None, help="Source ASR evidence path to record in the report.")
    parser.add_argument("--review-artifact", default=None, help="Review artifact path to record in the report.")
    parser.add_argument("--model", default=None, help="ASR model name to record in the report.")
    parser.add_argument("--source-audio", default=None, help="Source audio path to record in the report.")
    parser.add_argument("--generated-at", default=None, help="Generation timestamp to record in the report.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = reconcile_transcript(
        load_json(args.transcript),
        load_json(args.asr_evidence),
        section=args.section,
        fuzzy_threshold=args.fuzzy_threshold,
        source_evidence=args.source_evidence,
        review_artifact=args.review_artifact,
        model=args.model,
        source_audio=args.source_audio,
        generated_at=args.generated_at,
    )
    write_json(args.output, report)
    print(json.dumps({"output": args.output, "gateOutcome": report["gateOutcome"], "metrics": report["metrics"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
