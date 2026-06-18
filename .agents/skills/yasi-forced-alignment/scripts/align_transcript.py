#!/usr/bin/env python3
"""Generate yasi forced-alignment draft, review, and final timing artifacts."""

from __future__ import annotations

import argparse
import hashlib
import copy
import difflib
import json
import math
import os
import re
import subprocess
import sys
import threading
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
DEFAULT_DIRECT_ALIGN_WORKER = Path(__file__).with_name("qwen_direct_align.py")
DEFAULT_MODEL_ROOT = Path(r"D:\model-repo")
DEFAULT_ALIGNER = DEFAULT_MODEL_ROOT / "Qwen3-ForcedAligner-0.6B"
DEFAULT_FFMPEG = Path(r"D:\Project\video2pdf\kimi\tools\ffmpeg\bin\ffmpeg.exe")
DEFAULT_FFPROBE = Path(r"D:\Project\video2pdf\kimi\tools\ffmpeg\bin\ffprobe.exe")
DEFAULT_WHISPER = Path(r"D:\Project\video2pdf\kimi\.venv\Scripts\whisper.exe")
DEFAULT_SLICE_THRESHOLD_SECONDS = 180.0
DEFAULT_SLICE_SECONDS = 180.0
DEFAULT_LOCALIZATION_SCORE = 0.82
DEFAULT_SLICE_OVERLAP_SECONDS = 3.0
DEFAULT_TEXT_OVERLAP_TOKENS = 20
DEFAULT_CONTENT_START_SAFETY_SECONDS = 0.5
LOCALIZATION_SCHEMA_VERSION = "yasi.localization-transcript.v1"
LOCALIZED_SLICE_PLAN_SCHEMA_VERSION = "yasi.localized-slices.v1"

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
    slice_index: int | None = None
    slice_audio_start: float | None = None
    official_token_start: int | None = None
    official_token_end: int | None = None
    slice_qwen_json: str | None = None
    official_token_index: int | None = None


@dataclass(frozen=True)
class AudioSlice:
    index: int
    start: float
    end: float
    audio: Path
    basename: str


@dataclass(frozen=True)
class LocalizedSlice:
    index: int
    audio_start: float
    audio_end: float
    official_token_start: int
    official_token_end: int
    audio: Path
    text_path: Path
    basename: str
    text_preview: str


class LocalizationError(RuntimeError):
    pass


class LocalizationArgumentParser(argparse.ArgumentParser):
    def parse_args(self, args: list[str] | None = None, namespace: argparse.Namespace | None = None) -> argparse.Namespace:
        parsed = super().parse_args(args, namespace)
        if getattr(parsed, "localization_input", None):
            parsed.localizer = "existing"
        return parsed


def non_negative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be non-negative")
    return parsed


def localization_score(value: str) -> float:
    parsed = float(value)
    if parsed < 0 or parsed > 1:
        raise argparse.ArgumentTypeError("value must be in [0, 1]")
    return parsed


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be non-negative")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = LocalizationArgumentParser(
        description="Create yasi IELTS listening timing artifacts through Qwen direct transcript alignment, auto mapping, alignment review, and final frontend timings.",
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
    parser.add_argument("--qwen-python", default=str(DEFAULT_QWEN_PYTHON), help="Python executable for the Qwen model runtime venv.")
    parser.add_argument("--direct-align-worker", default=str(DEFAULT_DIRECT_ALIGN_WORKER), help="Qwen direct forced-align worker script.")
    parser.add_argument("--qwen-device-map", default="cuda:0", help="Transformers device_map passed to the Qwen worker.")
    parser.add_argument("--qwen-dtype", choices=("bfloat16", "float16", "float32"), default="float16", help="Torch dtype passed to the Qwen worker.")
    parser.add_argument("--qwen-timeout-seconds", type=float, default=1800.0, help="Timeout for each Qwen worker process. Use 0 to disable.")
    parser.add_argument("--min-free-gpu-memory-mib", type=int, default=0, help="Require this much free GPU memory before running Qwen. Use 0 to disable.")
    parser.add_argument("--ffmpeg", default=str(DEFAULT_FFMPEG), help="ffmpeg executable used to create three-minute audio slices.")
    parser.add_argument("--ffprobe", default=str(DEFAULT_FFPROBE), help="ffprobe executable used to measure section audio duration.")
    parser.add_argument("--whisper", default=str(DEFAULT_WHISPER), help="Whisper CLI executable used to create localization timestamps.")
    parser.add_argument("--localize-content-start", action="store_true", help="Use localization timestamps to find official content start and text-aware slice ranges.")
    parser.add_argument("--localizer", choices=("whisper", "qwen-asr", "existing"), default="whisper", help="Localization timestamp source.")
    parser.add_argument("--content-start-seconds", type=non_negative_float, default=None, help="Manual content-start timestamp override.")
    parser.add_argument("--localization-input", default=None, help="Existing localization transcript JSON to load instead of generating one.")
    parser.add_argument("--localization-output", default=None, help="Path for normalized localization transcript JSON.")
    parser.add_argument(
        "--min-localization-score",
        type=localization_score,
        default=DEFAULT_LOCALIZATION_SCORE,
        help="Minimum fuzzy content-start localization score.",
    )
    parser.add_argument(
        "--slice-threshold-seconds",
        type=float,
        default=DEFAULT_SLICE_THRESHOLD_SECONDS,
        help="Slice audio only when duration is greater than this threshold.",
    )
    parser.add_argument(
        "--slice-seconds",
        type=float,
        default=DEFAULT_SLICE_SECONDS,
        help="Maximum duration of each generated audio slice.",
    )
    parser.add_argument("--slice-overlap-seconds", type=non_negative_float, default=DEFAULT_SLICE_OVERLAP_SECONDS, help="Audio overlap applied to localized slices.")
    parser.add_argument("--text-overlap-tokens", type=non_negative_int, default=DEFAULT_TEXT_OVERLAP_TOKENS, help="Official token overlap applied to localized slices.")
    parser.add_argument("--language", default="English", help="Language passed to Qwen worker.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing generated artifacts.")
    parser.add_argument("--model-root", default=str(DEFAULT_MODEL_ROOT), help="Root containing local Qwen model directories.")
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


def probe_audio_duration(args: argparse.Namespace, audio: Path) -> float:
    cmd = [
        str(Path(args.ffprobe)),
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(audio),
    ]
    completed = subprocess.run(cmd, check=True, text=True, capture_output=True)
    for line in completed.stdout.splitlines():
        value = line.strip()
        if value:
            duration = float(value)
            if duration < 0:
                raise ValueError(f"ffprobe returned a negative duration for {audio}: {duration}")
            return duration
    raise RuntimeError(f"ffprobe returned no duration for {audio}")


def audio_slices_for(args: argparse.Namespace, audio: Path, work_dir: Path, section: int, duration: float) -> list[AudioSlice]:
    threshold = float(args.slice_threshold_seconds)
    slice_seconds = float(args.slice_seconds)
    if duration <= threshold:
        return []
    count = math.ceil(duration / slice_seconds)
    slices = []
    for index in range(count):
        start = round(index * slice_seconds, 3)
        end = round(min(duration, start + slice_seconds), 3)
        basename = f"section-{section:02d}.slice-{index + 1:03d}"
        slices.append(
            AudioSlice(
                index=index + 1,
                start=start,
                end=end,
                audio=work_dir / "slices" / f"{basename}.wav",
                basename=basename,
            )
        )
    return slices


def slice_summary(args: argparse.Namespace, slices: list[AudioSlice]) -> dict[str, Any]:
    return {
        "required": bool(slices),
        "thresholdSeconds": float(args.slice_threshold_seconds),
        "sliceSeconds": float(args.slice_seconds),
        "slices": [
            {
                "index": item.index,
                "start": item.start,
                "end": item.end,
                "duration": round(item.end - item.start, 3),
                "audio": str(item.audio),
                "basename": item.basename,
            }
            for item in slices
        ],
    }


def create_audio_slice(args: argparse.Namespace, source_audio: Path, audio_slice: AudioSlice) -> None:
    if audio_slice.audio.exists() and not args.overwrite:
        return
    audio_slice.audio.parent.mkdir(parents=True, exist_ok=True)
    duration = max(0.001, audio_slice.end - audio_slice.start)
    cmd = [
        str(Path(args.ffmpeg)),
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y" if args.overwrite else "-n",
        "-ss",
        f"{audio_slice.start:.3f}",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(source_audio),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(audio_slice.audio),
    ]
    subprocess.run(cmd, check=True, text=True, capture_output=True)


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


def official_token_records(section_payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "globalTokenIndex": token.global_index,
            "segmentOrder": token.segment_order,
            "tokenIndex": token.token_index,
            "text": token.text,
            "normalized": token.normalized,
        }
        for token in official_tokens(section_payload)
    ]


def localization_token_records(tokens: list[TimedToken]) -> list[dict[str, Any]]:
    return [
        {
            "text": token.text,
            "normalized": token.normalized,
            "start": round(token.start, 3),
            "end": round(token.end, 3),
            "sourceIndex": token.source_index,
        }
        for token in tokens
    ]


def localization_tokens_from_payload(payload: dict[str, Any]) -> list[TimedToken]:
    timed: list[TimedToken] = []
    source_index = 0

    def append_text(text: str, start: float | None, end: float | None, explicit_index: int | None = None) -> None:
        nonlocal source_index
        if start is None or end is None:
            return
        local_index = explicit_index if explicit_index is not None else source_index
        parts = split_timed_item(text, float(start), float(end), local_index)
        timed.extend(parts)
        source_index = max(source_index + 1, local_index + 1)

    for item in payload.get("tokens") or []:
        if not isinstance(item, dict):
            continue
        append_text(
            str(item.get("text") or item.get("word") or item.get("token") or ""),
            scalar_time(item, "start", "start_time", "startTime"),
            scalar_time(item, "end", "end_time", "endTime"),
            int(item["sourceIndex"]) if item.get("sourceIndex") is not None else None,
        )

    if timed:
        return timed

    raw_items = payload.get("timestamps") or payload.get("words") or payload.get("word_timestamps") or []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        append_text(
            str(item.get("text") or item.get("word") or item.get("token") or ""),
            scalar_time(item, "start", "start_time", "startTime"),
            scalar_time(item, "end", "end_time", "endTime"),
            int(item["sourceIndex"]) if item.get("sourceIndex") is not None else None,
        )

    if timed:
        return timed

    for segment in payload.get("segments") or []:
        if not isinstance(segment, dict):
            continue
        words = segment.get("words") or []
        if words:
            for word in words:
                if not isinstance(word, dict):
                    continue
                append_text(
                    str(word.get("word") or word.get("text") or word.get("token") or ""),
                    scalar_time(word, "start", "start_time", "startTime"),
                    scalar_time(word, "end", "end_time", "endTime"),
                    int(word["sourceIndex"]) if word.get("sourceIndex") is not None else None,
                )
            continue
        append_text(
            str(segment.get("text") or ""),
            scalar_time(segment, "start", "start_time", "startTime"),
            scalar_time(segment, "end", "end_time", "endTime"),
        )

    return timed


def normalize_localization_payload(payload: dict[str, Any], *, source_audio: Path | None = None, engine: str = "existing") -> dict[str, Any]:
    tokens = localization_tokens_from_payload(payload)
    normalized = {
        "schemaVersion": LOCALIZATION_SCHEMA_VERSION,
        "sourceAudio": str(source_audio) if source_audio else str(payload.get("sourceAudio") or ""),
        "engine": str(payload.get("engine") or engine),
        "generatedAt": str(payload.get("generatedAt") or utc_now()),
        "tokens": localization_token_records(tokens),
        "segments": payload.get("segments") or [],
    }
    for key in ("sourceAudioDurationSeconds", "officialTranscript", "transcriptHash", "cliParameters", "planHash"):
        if payload.get(key) is not None:
            normalized[key] = payload[key]
    return normalized


def enrich_localization_payload(
    payload: dict[str, Any],
    *,
    audio: Path,
    duration: float,
    transcript: Path,
    args: argparse.Namespace,
    plan_hash: str | None = None,
) -> dict[str, Any]:
    enriched = dict(payload)
    enriched["sourceAudio"] = str(audio)
    enriched["sourceAudioDurationSeconds"] = round(duration, 3)
    enriched["officialTranscript"] = str(transcript)
    enriched["transcriptHash"] = file_sha256(transcript)
    enriched["cliParameters"] = localization_cli_parameters(args)
    if plan_hash:
        enriched["planHash"] = plan_hash
    return normalize_localization_payload(enriched, source_audio=audio, engine=str(enriched.get("engine") or args.localizer))


def load_localization_transcript(path: Path) -> dict[str, Any]:
    return normalize_localization_payload(load_json(path), engine="existing")


def localization_output_path(args: argparse.Namespace, work_dir: Path, section: int) -> Path:
    if args.localization_output:
        return Path(args.localization_output)
    return work_dir / "localization" / f"section-{section:02d}.localization.json"


def localized_slice_plan_path(work_dir: Path, section: int) -> Path:
    return work_dir / "plans" / f"section-{section:02d}.localized-slices.json"


def generate_whisper_localization(args: argparse.Namespace, audio: Path, work_dir: Path, section: int) -> dict[str, Any]:
    whisper = Path(args.whisper)
    if not whisper.exists():
        raise LocalizationError(f"Whisper executable not found: {whisper}")
    output = localization_output_path(args, work_dir, section)
    output_dir = output.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(whisper),
        str(audio),
        "--model",
        "medium",
        "--language",
        "en",
        "--word_timestamps",
        "True",
        "--output_format",
        "json",
        "--output_dir",
        str(output_dir),
    ]
    completed = subprocess.run(cmd, check=True, text=True, capture_output=True)
    (output_dir / f"section-{section:02d}.whisper.stdout.log").write_text(output_text(completed.stdout), encoding="utf-8")
    (output_dir / f"section-{section:02d}.whisper.stderr.log").write_text(output_text(completed.stderr), encoding="utf-8")
    raw_output = output_dir / f"{audio.stem}.json"
    if not raw_output.exists():
        raise LocalizationError(f"Whisper completed but did not write expected JSON: {raw_output}")
    normalized = normalize_localization_payload(load_json(raw_output), source_audio=audio, engine="whisper")
    write_json(output, normalized, args.overwrite)
    return normalized


def generate_or_load_localization(args: argparse.Namespace, audio: Path, work_dir: Path, section: int) -> dict[str, Any]:
    if args.localization_input:
        normalized = load_localization_transcript(Path(args.localization_input))
        return normalized
    if args.localizer == "existing":
        raise LocalizationError("--localizer existing requires --localization-input.")
    if args.localizer == "qwen-asr":
        raise LocalizationError("qwen-asr localization generation is not configured; provide --localization-input.")
    return generate_whisper_localization(args, audio, work_dir, section)


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


def split_timed_item(
    text: str,
    start: float,
    end: float,
    source_index: int,
    *,
    slice_index: int | None = None,
    slice_audio_start: float | None = None,
    official_token_start: int | None = None,
    official_token_end: int | None = None,
    slice_qwen_json: str | None = None,
    official_token_index: int | None = None,
) -> list[TimedToken]:
    parts = tokenize_text(text)
    if not parts:
        return []
    duration = max(0.0, end - start)
    step = duration / len(parts) if parts else 0.0
    out = []
    for idx, (raw, normalized, _risks) in enumerate(parts):
        token_start = start + step * idx
        token_end = end if idx == len(parts) - 1 else start + step * (idx + 1)
        out.append(
            TimedToken(
                raw,
                normalized,
                token_start,
                token_end,
                source_index,
                slice_index=slice_index,
                slice_audio_start=slice_audio_start,
                official_token_start=official_token_start,
                official_token_end=official_token_end,
                slice_qwen_json=slice_qwen_json,
                official_token_index=official_token_index,
            )
        )
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
        timed.extend(
            split_timed_item(
                text,
                start,
                end,
                source_index,
                slice_index=item.get("sliceIndex"),
                slice_audio_start=item.get("sliceAudioStart"),
                official_token_start=item.get("officialTokenStart"),
                official_token_end=item.get("officialTokenEnd"),
                slice_qwen_json=item.get("sliceQwenJson"),
                official_token_index=item.get("officialTokenIndex"),
            )
        )

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


def locate_content_start(
    official: list[Token],
    localization: list[TimedToken],
    *,
    min_score: float,
    manual_seconds: float | None = None,
    prefix_token_count: int = 40,
    safety_margin_seconds: float = DEFAULT_CONTENT_START_SAFETY_SECONDS,
) -> dict[str, Any]:
    if manual_seconds is not None:
        return {"source": "manual", "contentStartSeconds": round(float(manual_seconds), 3), "score": 1.0}
    prefix = official[: max(1, min(prefix_token_count, len(official)))]
    if not prefix or not localization:
        raise LocalizationError("Cannot locate content start without official and localization tokens.")
    official_norms = [token.normalized for token in prefix]
    best: dict[str, Any] | None = None
    for start_index in range(len(localization)):
        min_window = min(20, len(official_norms), len(localization) - start_index)
        max_window = min(70, len(localization) - start_index)
        if min_window <= 0:
            continue
        for window_len in range(max(1, min_window), max_window + 1):
            window = localization[start_index : start_index + window_len]
            matcher = difflib.SequenceMatcher(a=official_norms, b=[token.normalized for token in window], autojunk=False)
            score = matcher.ratio()
            if best is None or score > best["score"]:
                blocks = [block for block in matcher.get_matching_blocks() if block.size > 0]
                if blocks:
                    first_block = blocks[0]
                    first_loc_index = start_index + first_block.b
                    raw_start = localization[first_loc_index].start
                else:
                    first_loc_index = start_index
                    raw_start = window[0].start
                best = {
                    "score": score,
                    "rawContentStartSeconds": raw_start,
                    "matchedOfficialTokenRange": [0, len(prefix)],
                    "matchedLocalizationTokenRange": [first_loc_index, start_index + window_len],
                    "officialPreview": " ".join(token.text for token in prefix[:12]),
                    "localizationPreview": " ".join(token.text for token in window[:12]),
                }
    if best is None or best["score"] < min_score:
        score = 0.0 if best is None else best["score"]
        raise LocalizationError(f"Localization content-start score {score:.3f} is below required {min_score:.3f}.")
    raw_start = float(best["rawContentStartSeconds"])
    best["source"] = "fuzzy"
    best["rawContentStartSeconds"] = round(raw_start, 3)
    best["safetyMarginSeconds"] = safety_margin_seconds
    best["contentStartSeconds"] = round(max(0.0, raw_start - safety_margin_seconds), 3)
    best["score"] = round(float(best["score"]), 6)
    return best


def build_coarse_token_time_map(
    official: list[Token],
    localization: list[TimedToken],
    *,
    content_start_seconds: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    usable = [token for token in localization if token.start >= content_start_seconds - 1e-6]
    ignored = len(localization) - len(usable)
    matcher = difflib.SequenceMatcher(
        a=[token.normalized for token in official],
        b=[token.normalized for token in usable],
        autojunk=False,
    )
    anchors: list[dict[str, Any]] = []
    diagnostics: dict[str, Any] = {"ignoredLocalizationTokenCount": ignored, "sequenceDiagnostics": []}
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                loc = usable[j1 + offset]
                anchors.append(
                    {
                        "officialTokenIndex": i1 + offset,
                        "time": round(loc.start, 3),
                        "localizationTokenIndex": loc.source_index,
                    }
                )
            continue
        diagnostics["sequenceDiagnostics"].append(
            {
                "tag": tag,
                "officialRange": [i1, i2],
                "localizationRange": [j1, j2],
                "officialSample": [token.text for token in official[i1 : min(i2, i1 + 6)]],
                "localizationSample": [token.text for token in usable[j1 : min(j2, j1 + 6)]],
            }
        )
    minimum = min(len(official), max(1, max(10, math.ceil(len(official) * 0.20))))
    diagnostics["anchorCount"] = len(anchors)
    diagnostics["minimumAnchorCount"] = minimum
    if len(anchors) < minimum:
        raise LocalizationError(f"Localization produced {len(anchors)} anchor(s), below required {minimum}.")
    if anchors and official:
        first_anchor = int(anchors[0]["officialTokenIndex"])
        last_anchor = int(anchors[-1]["officialTokenIndex"])
        head_margin = max(2, math.ceil(len(official) * 0.05))
        tail_margin = max(3, math.ceil(len(official) * 0.10))
        required_last = max(0, len(official) - tail_margin)
        diagnostics["coverage"] = {
            "firstOfficialTokenIndex": first_anchor,
            "lastOfficialTokenIndex": last_anchor,
            "headMargin": head_margin,
            "requiredLastOfficialTokenIndex": required_last,
        }
        if first_anchor > head_margin or last_anchor < required_last:
            raise LocalizationError(
                f"Localization anchor coverage is insufficient: first={first_anchor}, last={last_anchor}, required last>={required_last}."
            )
        max_gap = max(5, math.ceil(len(official) * 0.15))
        gaps = [
            int(current["officialTokenIndex"]) - int(previous["officialTokenIndex"])
            for previous, current in zip(anchors, anchors[1:])
        ]
        largest_gap = max(gaps) if gaps else 0
        diagnostics["coverage"]["maxAllowedOfficialTokenGap"] = max_gap
        diagnostics["coverage"]["largestOfficialTokenGap"] = largest_gap
        if largest_gap > max_gap:
            raise LocalizationError(
                f"Localization anchor coverage has a middle gap of {largest_gap} official tokens, above allowed {max_gap}."
            )
    return anchors, diagnostics


def official_token_at_or_before(time_seconds: float, anchors: list[dict[str, Any]]) -> int:
    before = [anchor for anchor in anchors if float(anchor["time"]) <= time_seconds]
    if before:
        return int(before[-1]["officialTokenIndex"])
    return int(anchors[0]["officialTokenIndex"]) if anchors else 0


def official_token_at_or_after(time_seconds: float, anchors: list[dict[str, Any]]) -> int:
    for anchor in anchors:
        if float(anchor["time"]) >= time_seconds:
            return int(anchor["officialTokenIndex"])
    return int(anchors[-1]["officialTokenIndex"]) if anchors else 0


def official_slice_text(official: list[Token], start: int, end: int) -> str:
    return " ".join(token.text for token in official[start:end])


def stable_plan_hash(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def localization_cli_parameters(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "localizer": args.localizer,
        "localizeContentStart": bool(args.localize_content_start),
        "contentStartSeconds": args.content_start_seconds,
        "minLocalizationScore": float(args.min_localization_score),
        "sliceThresholdSeconds": float(args.slice_threshold_seconds),
        "sliceSeconds": float(args.slice_seconds),
        "sliceOverlapSeconds": float(args.slice_overlap_seconds),
        "textOverlapTokens": int(args.text_overlap_tokens),
        "whisper": str(Path(args.whisper)),
        "localizationInput": args.localization_input,
        "localizationOutput": args.localization_output,
    }


def validate_localization_source(localization_payload: dict[str, Any], audio: Path) -> None:
    source = str(localization_payload.get("sourceAudio") or "")
    if not source:
        return
    source_path = Path(source)
    if source_path.name and source_path.name != audio.name:
        raise LocalizationError(f"Localization sourceAudio {source!r} does not match source audio {str(audio)!r}.")
    if source_path.parent != Path(".") and source_path.resolve() != audio.resolve():
        raise LocalizationError(f"Localization sourceAudio {source!r} does not match source audio {str(audio)!r}.")


def localized_slice_to_record(item: LocalizedSlice) -> dict[str, Any]:
    return {
        "index": item.index,
        "audioStart": item.audio_start,
        "audioEnd": item.audio_end,
        "start": item.audio_start,
        "end": item.audio_end,
        "duration": round(item.audio_end - item.audio_start, 3),
        "officialTokenStart": item.official_token_start,
        "officialTokenEnd": item.official_token_end,
        "audio": str(item.audio),
        "officialText": str(item.text_path),
        "basename": item.basename,
        "textPreview": item.text_preview,
    }


def build_localized_slice_plan(
    args: argparse.Namespace,
    *,
    audio: Path,
    work_dir: Path,
    section: int,
    duration: float,
    section_payload: dict[str, Any],
    transcript: Path,
    localization_payload: dict[str, Any],
    localization_artifact: Path,
    write_plan: bool,
) -> tuple[dict[str, Any], list[LocalizedSlice]]:
    official = official_tokens(section_payload)
    localization = localization_tokens_from_payload(localization_payload)
    validate_localization_source(localization_payload, audio)
    content_start = locate_content_start(
        official,
        localization,
        min_score=float(args.min_localization_score),
        manual_seconds=args.content_start_seconds,
    )
    anchors, diagnostics = build_coarse_token_time_map(
        official,
        localization,
        content_start_seconds=float(content_start["contentStartSeconds"]),
    )
    slice_seconds = float(args.slice_seconds)
    overlap = float(args.slice_overlap_seconds)
    text_overlap = int(args.text_overlap_tokens)
    start_at = float(content_start["contentStartSeconds"])
    if duration <= start_at:
        raise LocalizationError(f"Content start {start_at} is beyond audio duration {duration}.")
    count = max(1, math.ceil((duration - start_at) / slice_seconds))
    slices: list[LocalizedSlice] = []
    for index in range(count):
        base_start = start_at + index * slice_seconds
        base_end = min(duration, start_at + (index + 1) * slice_seconds)
        audio_start = round(max(start_at, base_start - (overlap if index else 0.0)), 3)
        audio_end = round(min(duration, base_end + (overlap if base_end < duration else 0.0)), 3)
        token_start = official_token_at_or_before(audio_start, anchors)
        token_end = official_token_at_or_after(audio_end, anchors) + 1
        token_start = max(0, token_start - (text_overlap if index else 0))
        token_end = min(len(official), token_end + (text_overlap if audio_end < duration else 0))
        if token_end <= token_start:
            raise LocalizationError(f"Localized slice {index + 1} has an empty official token range.")
        basename = f"section-{section:02d}.slice-{index + 1:03d}"
        text = official_slice_text(official, token_start, token_end)
        preview = text[:157] + "..." if len(text) > 160 else text
        slices.append(
            LocalizedSlice(
                index=index + 1,
                audio_start=audio_start,
                audio_end=audio_end,
                official_token_start=token_start,
                official_token_end=token_end,
                audio=work_dir / "slices" / f"{basename}.wav",
                text_path=work_dir / "slices" / f"{basename}.official.txt",
                basename=basename,
                text_preview=preview,
            )
        )
    plan = {
        "schemaVersion": LOCALIZED_SLICE_PLAN_SCHEMA_VERSION,
        "section": section,
        "sourceAudio": str(audio),
        "sourceAudioDurationSeconds": round(duration, 3),
        "officialTranscript": str(transcript),
        "transcriptHash": file_sha256(transcript),
        "localizationArtifact": str(localization_artifact),
        "cliParameters": localization_cli_parameters(args),
        "contentStart": content_start,
        "contentStartSeconds": content_start["contentStartSeconds"],
        "localizationScore": content_start.get("score"),
        "tokenCounts": {"official": len(official), "localization": len(localization)},
        "anchors": anchors,
        "diagnostics": diagnostics,
        "sliceSeconds": slice_seconds,
        "sliceOverlapSeconds": overlap,
        "textOverlapTokens": text_overlap,
        "slices": [localized_slice_to_record(item) for item in slices],
    }
    plan["planHash"] = stable_plan_hash({key: value for key, value in plan.items() if key != "planHash"})
    if write_plan:
        write_json(localized_slice_plan_path(work_dir, section), plan, args.overwrite)
    return plan, slices


def official_section_text(section_payload: dict[str, Any]) -> str:
    return " ".join(str(segment.get("text", "")).strip() for segment in section_payload.get("segments", []) if str(segment.get("text", "")).strip())


def official_text_path(work_dir: Path, basename: str) -> Path:
    return work_dir / f"{basename}.official.txt"


def build_direct_align_command(
    args: argparse.Namespace,
    audio: Path,
    work_dir: Path,
    section: int,
    *,
    basename: str | None = None,
    output_dir: Path | None = None,
    text_path_override: Path | None = None,
) -> tuple[list[str], Path, Path]:
    basename = basename or f"section-{section:02d}"
    qwen_json = (output_dir or work_dir) / f"{basename}.qwen.json"
    text_path = text_path_override or official_text_path(work_dir, basename)
    cmd = [
        str(Path(args.qwen_python)),
        str(Path(args.direct_align_worker)),
        "--input",
        str(audio),
        "--text-file",
        str(text_path),
        "--output-json",
        str(qwen_json),
        "--aligner-model",
        str(Path(args.model_root) / "Qwen3-ForcedAligner-0.6B"),
        "--language",
        args.language,
        "--device-map",
        args.qwen_device_map,
        "--dtype",
        args.qwen_dtype,
    ]
    if args.overwrite:
        cmd.append("--overwrite")
    return cmd, qwen_json, text_path


def wrapper_log_path(work_dir: Path, basename: str) -> Path:
    return work_dir / f"{basename}.wrapper.log.json"


def stream_log_path(log_path: Path, stream_name: str) -> Path:
    name = log_path.name
    prefix = name[: -len(".log.json")] if name.endswith(".log.json") else log_path.stem
    return log_path.with_name(f"{prefix}.{stream_name}.log")


def output_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def write_wrapper_log(
    log_path: Path,
    *,
    cmd: list[str],
    started_at: str,
    status: str,
    timeout_seconds: float | None,
    returncode: int | None,
    stdout: str | bytes | None,
    stderr: str | bytes | None,
) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "command": cmd,
        "status": status,
        "timeoutSeconds": timeout_seconds,
        "returnCode": returncode,
        "startedAt": started_at,
        "finishedAt": utc_now(),
        "stdoutLog": str(stream_log_path(log_path, "stdout")),
        "stderrLog": str(stream_log_path(log_path, "stderr")),
        "stdout": output_text(stdout)[-20000:],
        "stderr": output_text(stderr)[-20000:],
    }
    log_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def terminate_process_tree(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    if proc.poll() is None:
        proc.kill()


def qwen_child_environment() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def tee_stream(stream, chunks: list[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", errors="replace") as handle:
        while True:
            data = stream.readline()
            if data == "":
                break
            chunks.append(data)
            handle.write(data)
            handle.flush()


def run_wrapper(cmd: list[str], *, log_path: Path, timeout_seconds: float | None) -> subprocess.CompletedProcess[str]:
    timeout = None if timeout_seconds is None or timeout_seconds <= 0 else float(timeout_seconds)
    started_at = utc_now()
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=qwen_child_environment(),
    )
    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []
    stdout_thread = threading.Thread(
        target=tee_stream,
        args=(proc.stdout, stdout_chunks, stream_log_path(log_path, "stdout")),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=tee_stream,
        args=(proc.stderr, stderr_chunks, stream_log_path(log_path, "stderr")),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        terminate_process_tree(proc)
        proc.wait()
        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)
        stdout = "".join(stdout_chunks)
        stderr = "".join(stderr_chunks)
        write_wrapper_log(
            log_path,
            cmd=cmd,
            started_at=started_at,
            status="timeout",
            timeout_seconds=timeout,
            returncode=proc.returncode,
            stdout=stdout or exc.output,
            stderr=stderr or exc.stderr,
        )
        raise subprocess.TimeoutExpired(
            cmd,
            timeout,
            output=stdout or exc.output,
            stderr=(output_text(stderr or exc.stderr) + f"\nWrapper log: {log_path}").strip(),
        ) from exc
    stdout_thread.join(timeout=5)
    stderr_thread.join(timeout=5)
    stdout = "".join(stdout_chunks)
    stderr = "".join(stderr_chunks)

    status = "ok" if proc.returncode == 0 else "failed"
    write_wrapper_log(
        log_path,
        cmd=cmd,
        started_at=started_at,
        status=status,
        timeout_seconds=timeout,
        returncode=proc.returncode,
        stdout=stdout,
        stderr=stderr,
    )
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(
            proc.returncode,
            cmd,
            output=stdout,
            stderr=(stderr + f"\nWrapper log: {log_path}").strip(),
        )
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)


def offset_time_fields(item: dict[str, Any], offset: float) -> dict[str, Any]:
    out = copy.deepcopy(item)
    for key in ("start", "end", "start_time", "end_time", "startTime", "endTime"):
        if key in out and out[key] is not None:
            out[key] = round(float(out[key]) + offset, 6)
    return out


def offset_qwen_payload(payload: dict[str, Any], offset: float) -> dict[str, Any]:
    out = copy.deepcopy(payload)
    for key in ("timestamps", "words", "segments"):
        values = out.get(key)
        if isinstance(values, list):
            out[key] = [offset_time_fields(item, offset) if isinstance(item, dict) else item for item in values]
    return out


def merge_slice_qwen_payloads(
    args: argparse.Namespace,
    *,
    output_json: Path,
    original_audio: Path,
    text: str,
    slices: list[AudioSlice],
    slice_jsons: list[Path],
) -> None:
    timestamps: list[Any] = []
    segments: list[Any] = []
    slice_records: list[dict[str, Any]] = []
    language = args.language
    for audio_slice, slice_json in zip(slices, slice_jsons):
        payload = load_json(slice_json)
        shifted = offset_qwen_payload(payload, audio_slice.start)
        timestamps.extend(shifted.get("timestamps") or [])
        segments.extend(shifted.get("segments") or [])
        language = str(shifted.get("language") or language)
        slice_records.append(
            {
                "index": audio_slice.index,
                "start": audio_slice.start,
                "end": audio_slice.end,
                "audio": str(audio_slice.audio),
                "qwenJson": str(slice_json),
                "timestampCount": len(shifted.get("timestamps") or []),
                "segmentCount": len(shifted.get("segments") or []),
            }
        )

    payload = {
        "config": {
            "source": "transcript-slices",
            "aligner_model": str(Path(args.model_root) / "Qwen3-ForcedAligner-0.6B"),
            "language": language,
            "device_map": args.qwen_device_map,
            "dtype": args.qwen_dtype,
            "return_time_stamps": True,
            "sliceThresholdSeconds": float(args.slice_threshold_seconds),
            "sliceSeconds": float(args.slice_seconds),
        },
        "language": language,
        "text": text,
        "timestamps": timestamps,
        "segments": segments,
        "audio_path": str(original_audio),
        "slices": slice_records,
    }
    write_json(output_json, payload, args.overwrite)


def materialize_localized_slice(
    args: argparse.Namespace,
    source_audio: Path,
    localized_slice: LocalizedSlice,
    official: list[Token],
    *,
    plan_hash: str,
    plan_metadata: dict[str, Any] | None = None,
) -> None:
    manifest = localized_slice.audio.with_suffix(".manifest.json")
    if localized_slice.audio.exists() and localized_slice.text_path.exists() and not args.overwrite:
        if not manifest.exists():
            raise FileExistsError(f"Localized slice exists without manifest: {localized_slice.audio}")
        existing = load_json(manifest)
        if existing.get("planHash") != plan_hash:
            raise FileExistsError(f"Localized slice manifest hash mismatch for {localized_slice.audio}")
        return
    localized_slice.audio.parent.mkdir(parents=True, exist_ok=True)
    localized_slice.text_path.parent.mkdir(parents=True, exist_ok=True)
    localized_slice.text_path.write_text(
        official_slice_text(official, localized_slice.official_token_start, localized_slice.official_token_end) + "\n",
        encoding="utf-8",
    )
    duration = max(0.001, localized_slice.audio_end - localized_slice.audio_start)
    cmd = [
        str(Path(args.ffmpeg)),
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y" if args.overwrite else "-n",
        "-ss",
        f"{localized_slice.audio_start:.3f}",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(source_audio),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(localized_slice.audio),
    ]
    subprocess.run(cmd, check=True, text=True, capture_output=True)
    manifest_payload = {
        "planHash": plan_hash,
        "sliceIndex": localized_slice.index,
        "audioStart": localized_slice.audio_start,
        "audioEnd": localized_slice.audio_end,
        "officialTokenStart": localized_slice.official_token_start,
        "officialTokenEnd": localized_slice.official_token_end,
    }
    if plan_metadata:
        manifest_payload.update(
            {
                "sourceAudio": plan_metadata.get("sourceAudio"),
                "sourceAudioDurationSeconds": plan_metadata.get("sourceAudioDurationSeconds"),
                "officialTranscript": plan_metadata.get("officialTranscript"),
                "transcriptHash": plan_metadata.get("transcriptHash"),
                "cliParameters": plan_metadata.get("cliParameters"),
            }
        )
    write_json(manifest, manifest_payload, True)


def slice_boundary_distance(start: float, end: float, localized_slice: LocalizedSlice) -> float:
    midpoint = (start + end) / 2
    return min(midpoint - localized_slice.audio_start, localized_slice.audio_end - midpoint)


def localized_slice_candidates(
    payload: dict[str, Any],
    *,
    section: int,
    official: list[Token],
    localized_slice: LocalizedSlice,
    slice_qwen_json: Path,
) -> list[dict[str, Any]]:
    review_items: list[dict[str, Any]] = []
    timed = timed_tokens_from_qwen(payload, section, review_items)
    official_range = official[localized_slice.official_token_start : localized_slice.official_token_end]
    matcher = difflib.SequenceMatcher(
        a=[token.normalized for token in official_range],
        b=[token.normalized for token in timed],
        autojunk=False,
    )
    candidates: list[dict[str, Any]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            continue
        for offset in range(i2 - i1):
            official_token = official_range[i1 + offset]
            timed_token = timed[j1 + offset]
            start = round(timed_token.start + localized_slice.audio_start, 6)
            end = round(timed_token.end + localized_slice.audio_start, 6)
            candidates.append(
                {
                    "text": official_token.text,
                    "start_time": start,
                    "end_time": end,
                    "officialTokenIndex": official_token.global_index,
                    "sourceIndex": timed_token.source_index,
                    "sliceIndex": localized_slice.index,
                    "sliceAudioStart": localized_slice.audio_start,
                    "officialTokenStart": localized_slice.official_token_start,
                    "officialTokenEnd": localized_slice.official_token_end,
                    "sliceQwenJson": str(slice_qwen_json),
                    "boundaryDistance": round(slice_boundary_distance(start, end, localized_slice), 6),
                }
            )
    return candidates


def choose_localized_candidate(current: dict[str, Any] | None, candidate: dict[str, Any]) -> dict[str, Any]:
    if current is None:
        return candidate
    candidate_positive = candidate["end_time"] > candidate["start_time"]
    current_positive = current["end_time"] > current["start_time"]
    if candidate_positive != current_positive:
        return candidate if candidate_positive else current
    if candidate["boundaryDistance"] > current["boundaryDistance"] + 1e-9:
        return candidate
    if abs(candidate["boundaryDistance"] - current["boundaryDistance"]) <= 1e-9 and candidate["sliceIndex"] < current["sliceIndex"]:
        return candidate
    return current


def merge_localized_slice_qwen_payloads(
    args: argparse.Namespace,
    *,
    output_json: Path,
    original_audio: Path,
    text: str,
    official: list[Token],
    slices: list[LocalizedSlice],
    slice_jsons: list[Path],
    plan: dict[str, Any],
) -> None:
    by_official: dict[int, dict[str, Any]] = {}
    slice_records: list[dict[str, Any]] = []
    language = args.language
    for localized_slice, slice_json in zip(slices, slice_jsons):
        payload = load_json(slice_json)
        language = str(payload.get("language") or language)
        candidates = localized_slice_candidates(
            payload,
            section=int(plan["section"]),
            official=official,
            localized_slice=localized_slice,
            slice_qwen_json=slice_json,
        )
        for candidate in candidates:
            key = int(candidate["officialTokenIndex"])
            by_official[key] = choose_localized_candidate(by_official.get(key), candidate)
        record = localized_slice_to_record(localized_slice)
        record["qwenJson"] = str(slice_json)
        record["timestampCount"] = len(payload.get("timestamps") or [])
        slice_records.append(record)
    timestamps = [by_official[index] for index in sorted(by_official)]
    for item in timestamps:
        item.pop("boundaryDistance", None)
    localization = {
        "source": plan.get("contentStart", {}).get("source"),
        "contentStartSeconds": plan.get("contentStartSeconds"),
        "score": plan.get("localizationScore"),
        "artifact": plan.get("localizationArtifact"),
        "slicePlan": str(localized_slice_plan_path(output_json.parent.parent if output_json.parent.name == "slices" else output_json.parent, int(plan["section"]))),
        "slices": plan.get("slices") or [],
    }
    payload = {
        "config": {
            "source": "localized-transcript-slices",
            "aligner_model": str(Path(args.model_root) / "Qwen3-ForcedAligner-0.6B"),
            "language": language,
            "device_map": args.qwen_device_map,
            "dtype": args.qwen_dtype,
            "return_time_stamps": True,
            "sliceThresholdSeconds": float(args.slice_threshold_seconds),
            "sliceSeconds": float(args.slice_seconds),
            "sliceOverlapSeconds": float(args.slice_overlap_seconds),
            "textOverlapTokens": int(args.text_overlap_tokens),
        },
        "language": language,
        "text": text,
        "timestamps": timestamps,
        "segments": [],
        "audio_path": str(original_audio),
        "localization": localization,
        "slices": slice_records,
    }
    write_json(output_json, payload, args.overwrite)


def run_direct_align(
    args: argparse.Namespace,
    audio: Path,
    work_dir: Path,
    section: int,
    section_payload: dict[str, Any],
) -> tuple[subprocess.CompletedProcess[str], Path]:
    basename = f"section-{section:02d}"
    duration = probe_audio_duration(args, audio)
    slices = audio_slices_for(args, audio, work_dir, section, duration)
    cmd, qwen_json, text_path = build_direct_align_command(args, audio, work_dir, section, basename=basename)
    text = official_section_text(section_payload)
    if not text:
        raise ValueError(f"Section {section} has no transcript text to align.")
    text_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.write_text(text + "\n", encoding="utf-8")
    should_localize = bool(args.localize_content_start or args.localization_input or duration > float(args.slice_threshold_seconds))
    if should_localize:
        localization_payload = generate_or_load_localization(args, audio, work_dir, section)
        validate_localization_source(localization_payload, audio)
        localization_artifact = Path(args.localization_output) if args.localization_output else localization_output_path(args, work_dir, section)
        localization_payload = enrich_localization_payload(
            localization_payload,
            audio=audio,
            duration=duration,
            transcript=Path(args.transcript),
            args=args,
        )
        plan, localized_slices = build_localized_slice_plan(
            args,
            audio=audio,
            work_dir=work_dir,
            section=section,
            duration=duration,
            section_payload=section_payload,
            transcript=Path(args.transcript),
            localization_payload=localization_payload,
            localization_artifact=localization_artifact,
            write_plan=True,
        )
        localization_payload = enrich_localization_payload(
            localization_payload,
            audio=audio,
            duration=duration,
            transcript=Path(args.transcript),
            args=args,
            plan_hash=str(plan["planHash"]),
        )
        write_json(localization_artifact, localization_payload, args.overwrite)
        official = official_tokens(section_payload)
        completed_runs: list[subprocess.CompletedProcess[str]] = []
        slice_jsons: list[Path] = []
        for localized_slice in localized_slices:
            materialize_localized_slice(args, audio, localized_slice, official, plan_hash=str(plan["planHash"]), plan_metadata=plan)
            localized_slice.text_path.parent.mkdir(parents=True, exist_ok=True)
            localized_slice.text_path.write_text(
                official_slice_text(official, localized_slice.official_token_start, localized_slice.official_token_end) + "\n",
                encoding="utf-8",
            )
            slice_cmd, slice_qwen_json, _slice_text_path = build_direct_align_command(
                args,
                localized_slice.audio,
                work_dir,
                section,
                basename=localized_slice.basename,
                output_dir=localized_slice.audio.parent,
                text_path_override=localized_slice.text_path,
            )
            completed_runs.append(
                run_wrapper(
                    slice_cmd,
                    log_path=wrapper_log_path(localized_slice.audio.parent, f"{localized_slice.basename}.direct-align"),
                    timeout_seconds=args.qwen_timeout_seconds,
                )
            )
            slice_jsons.append(slice_qwen_json)
        merge_localized_slice_qwen_payloads(
            args,
            output_json=qwen_json,
            original_audio=audio,
            text=text,
            official=official,
            slices=localized_slices,
            slice_jsons=slice_jsons,
            plan=plan,
        )
        stdout = json.dumps({"qwenJson": str(qwen_json), "sliceCount": len(localized_slices), "localized": True}, ensure_ascii=False)
        stderr = "\n".join(run.stderr for run in completed_runs if run.stderr)
        return subprocess.CompletedProcess([str(Path(args.qwen_python)), str(Path(args.direct_align_worker)), "--localized-sliced"], 0, stdout, stderr), qwen_json

    if slices:
        completed_runs: list[subprocess.CompletedProcess[str]] = []
        slice_jsons: list[Path] = []
        for audio_slice in slices:
            create_audio_slice(args, audio, audio_slice)
            slice_cmd, slice_qwen_json, slice_text_path = build_direct_align_command(
                args,
                audio_slice.audio,
                work_dir,
                section,
                basename=audio_slice.basename,
            )
            slice_text_path.parent.mkdir(parents=True, exist_ok=True)
            slice_text_path.write_text(text + "\n", encoding="utf-8")
            completed_runs.append(
                run_wrapper(
                    slice_cmd,
                    log_path=wrapper_log_path(work_dir, f"{audio_slice.basename}.direct-align"),
                    timeout_seconds=args.qwen_timeout_seconds,
                )
            )
            slice_jsons.append(slice_qwen_json)
        merge_slice_qwen_payloads(
            args,
            output_json=qwen_json,
            original_audio=audio,
            text=text,
            slices=slices,
            slice_jsons=slice_jsons,
        )
        stdout = json.dumps({"qwenJson": str(qwen_json), "sliceCount": len(slices)}, ensure_ascii=False)
        stderr = "\n".join(run.stderr for run in completed_runs if run.stderr)
        return subprocess.CompletedProcess([str(Path(args.qwen_python)), str(Path(args.direct_align_worker)), "--sliced"], 0, stdout, stderr), qwen_json

    completed = run_wrapper(
        cmd,
        log_path=wrapper_log_path(work_dir, f"{basename}.direct-align"),
        timeout_seconds=args.qwen_timeout_seconds,
    )
    return completed, qwen_json


def check_gpu_preflight(args: argparse.Namespace) -> dict[str, Any]:
    minimum = int(args.min_free_gpu_memory_mib or 0)
    if minimum <= 0 or not str(args.qwen_device_map).lower().startswith("cuda"):
        return {"required": False}
    cmd = ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"]
    try:
        completed = subprocess.run(cmd, check=True, text=True, capture_output=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"GPU preflight failed to run nvidia-smi: {exc}") from exc
    values = [int(float(line.strip())) for line in completed.stdout.splitlines() if line.strip()]
    if not values:
        raise RuntimeError("GPU preflight found no GPU memory readings from nvidia-smi.")
    free_mib = max(values)
    result = {"required": True, "freeMiB": free_mib, "minimumFreeMiB": minimum}
    if free_mib < minimum:
        raise RuntimeError(f"Insufficient free GPU memory: {free_mib} MiB free, requires at least {minimum} MiB.")
    return result


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
        if source_token:
            if source_token.slice_index is not None:
                entry["sliceIndex"] = source_token.slice_index
            if source_token.slice_audio_start is not None:
                entry["sliceAudioStart"] = source_token.slice_audio_start
            if source_token.official_token_start is not None:
                entry["officialTokenStart"] = source_token.official_token_start
            if source_token.official_token_end is not None:
                entry["officialTokenEnd"] = source_token.official_token_end
            if source_token.slice_qwen_json is not None:
                entry["sliceQwenJson"] = source_token.slice_qwen_json
            if source_token.official_token_index is not None:
                entry["sourceOfficialTokenIndex"] = source_token.official_token_index
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

    completed, qwen_json = run_direct_align(args, audio, work_dir, section, transcript_sections[section])
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
        "localization": payload.get("localization"),
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
        "language": args.language,
        "qwenDeviceMap": args.qwen_device_map,
        "qwenDtype": args.qwen_dtype,
        "qwenTimeoutSeconds": args.qwen_timeout_seconds,
        "minFreeGpuMemoryMiB": args.min_free_gpu_memory_mib,
        "sliceThresholdSeconds": args.slice_threshold_seconds,
        "sliceSeconds": args.slice_seconds,
        "sliceOverlapSeconds": args.slice_overlap_seconds,
        "textOverlapTokens": args.text_overlap_tokens,
        "minLocalizationScore": args.min_localization_score,
        "qwenPython": str(Path(args.qwen_python)),
        "directAlignWorker": str(Path(args.direct_align_worker)),
        "modelRoot": str(Path(args.model_root)),
        "forcedAligner": str(DEFAULT_ALIGNER),
        "ffmpeg": str(Path(args.ffmpeg)),
        "ffprobe": str(Path(args.ffprobe)),
        "whisper": str(Path(args.whisper)),
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
                    "localization": section_payload.get("localization"),
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
        "localization": section_payload.get("autoMapping", {}).get("localization"),
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
        duration = probe_audio_duration(args, audio) if audio.exists() else None
        should_localize = bool(duration is not None and (args.localize_content_start or args.localization_input or duration > float(args.slice_threshold_seconds)))
        slices = [] if should_localize else audio_slices_for(args, audio, work_dir, section, duration) if duration is not None else []
        direct_cmd, direct_qwen_json, text_path = build_direct_align_command(args, audio, work_dir, section)
        item: dict[str, Any] = {
            "section": section,
            "audio": str(audio),
            "audioExists": audio.exists(),
            "audioDurationSeconds": round(duration, 3) if duration is not None else None,
            "officialSegmentCount": len(transcript_sections[section].get("segments", [])),
            "officialTokenCount": len(official_tokens(transcript_sections[section])),
            "qwenJson": str(direct_qwen_json),
            "officialText": str(text_path),
            "directAlignCommand": None if slices else direct_cmd,
            "directAlignLog": str(wrapper_log_path(work_dir, f"section-{section:02d}.direct-align")),
            "officialTextChars": len(official_section_text(transcript_sections[section])),
            "slicing": slice_summary(args, slices),
        }
        if should_localize and duration is not None:
            if not args.localization_input:
                item["localization"] = {
                    "required": True,
                    "localizer": args.localizer,
                    "localizationInput": None,
                    "whisper": str(Path(args.whisper)),
                    "whisperExists": Path(args.whisper).exists(),
                    "message": "Provide --localization-input for a full localized dry-run plan without running Whisper.",
                }
                item["directAlignCommand"] = None
                planned.append(item)
                continue
            localization_payload = load_localization_transcript(Path(args.localization_input))
            plan, localized_slices = build_localized_slice_plan(
                args,
                audio=audio,
                work_dir=work_dir,
                section=section,
                duration=duration,
                section_payload=transcript_sections[section],
                transcript=transcript,
                localization_payload=localization_payload,
                localization_artifact=Path(args.localization_input),
                write_plan=False,
            )
            item["localization"] = {
                "required": True,
                "source": plan.get("contentStart", {}).get("source"),
                "contentStartSeconds": plan.get("contentStartSeconds"),
                "score": plan.get("localizationScore"),
                "artifact": str(Path(args.localization_input)),
                "slicePlan": str(localized_slice_plan_path(work_dir, section)),
            }
            item["directAlignCommand"] = None
            item["slicing"] = {
                "required": bool(localized_slices),
                "thresholdSeconds": float(args.slice_threshold_seconds),
                "sliceSeconds": float(args.slice_seconds),
                "sliceOverlapSeconds": float(args.slice_overlap_seconds),
                "textOverlapTokens": int(args.text_overlap_tokens),
                "slices": [localized_slice_to_record(slice_item) for slice_item in localized_slices],
            }
            for slice_item, localized_slice in zip(item["slicing"]["slices"], localized_slices):
                slice_cmd, slice_qwen_json, _slice_text_path = build_direct_align_command(
                    args,
                    localized_slice.audio,
                    work_dir,
                    section,
                    basename=localized_slice.basename,
                    output_dir=localized_slice.audio.parent,
                    text_path_override=localized_slice.text_path,
                )
                slice_item["qwenJson"] = str(slice_qwen_json)
                slice_item["directAlignCommand"] = slice_cmd
                slice_item["directAlignLog"] = str(wrapper_log_path(localized_slice.audio.parent, f"{localized_slice.basename}.direct-align"))
            planned.append(item)
            continue
        if slices:
            for slice_item, audio_slice in zip(item["slicing"]["slices"], slices):
                slice_cmd, slice_qwen_json, slice_text_path = build_direct_align_command(
                    args,
                    audio_slice.audio,
                    work_dir,
                    section,
                    basename=audio_slice.basename,
                )
                slice_item["qwenJson"] = str(slice_qwen_json)
                slice_item["officialText"] = str(slice_text_path)
                slice_item["directAlignCommand"] = slice_cmd
                slice_item["directAlignLog"] = str(wrapper_log_path(work_dir, f"{audio_slice.basename}.direct-align"))
        planned.append(item)
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
        "directAlignWorkerExists": Path(args.direct_align_worker).exists(),
        "modelRootExists": Path(args.model_root).exists(),
        "forcedAlignerExists": DEFAULT_ALIGNER.exists(),
        "ffmpegExists": Path(args.ffmpeg).exists(),
        "ffprobeExists": Path(args.ffprobe).exists(),
        "gpuPreflight": {"minimumFreeMiB": args.min_free_gpu_memory_mib, "deviceMap": args.qwen_device_map},
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
    if args.qwen_timeout_seconds < 0:
        parser.error("--qwen-timeout-seconds must be 0 or a positive number.")
    if args.min_free_gpu_memory_mib < 0:
        parser.error("--min-free-gpu-memory-mib must be 0 or a positive integer.")
    if args.slice_threshold_seconds <= 0:
        parser.error("--slice-threshold-seconds must be positive.")
    if args.slice_seconds <= 0:
        parser.error("--slice-seconds must be positive.")


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
    gpu_preflight = check_gpu_preflight(args)
    sections = [align_section(args, section, transcript_sections, pack_root, work_dir) for section in selected_sections(args)]
    draft_artifact = build_timing_artifact(args, sections, pack_root, transcript, work_dir, review_output, False)
    draft_artifact["tool"]["gpuPreflight"] = gpu_preflight
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
    except subprocess.TimeoutExpired as exc:
        print(f"Qwen wrapper timed out after {exc.timeout} seconds", file=sys.stderr)
        print("Command:", " ".join(exc.cmd), file=sys.stderr)
        if exc.output:
            print("stdout:", output_text(exc.output)[-4000:], file=sys.stderr)
        if exc.stderr:
            print("stderr:", output_text(exc.stderr)[-4000:], file=sys.stderr)
        raise SystemExit(124)
