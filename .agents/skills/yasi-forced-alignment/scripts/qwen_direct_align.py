#!/usr/bin/env python3
"""Run Qwen3-ForcedAligner directly against official transcript text."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import torch


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Directly align an audio file to known transcript text with Qwen3-ForcedAligner.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", required=True, help="Audio file to align.")
    parser.add_argument("--text-file", required=True, help="UTF-8 transcript text file.")
    parser.add_argument("--output-json", required=True, help="Qwen-compatible JSON output path.")
    parser.add_argument("--aligner-model", required=True, help="Qwen3-ForcedAligner model path.")
    parser.add_argument("--language", default="English", help="Language name passed to the aligner.")
    parser.add_argument("--device-map", default="cuda:0", help="Transformers device_map.")
    parser.add_argument("--dtype", choices=("bfloat16", "float16", "float32"), default="float16")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing output JSON.")
    return parser


def torch_dtype(name: str) -> torch.dtype:
    return {
        "bfloat16": torch.bfloat16,
        "float16": torch.float16,
        "float32": torch.float32,
    }[name]


def result_items(result: Any) -> list[dict[str, Any]]:
    return [
        {
            "text": str(getattr(item, "text", "")),
            "start_time": float(getattr(item, "start_time", 0.0)),
            "end_time": float(getattr(item, "end_time", 0.0)),
        }
        for item in getattr(result, "items", result)
    ]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    audio = Path(args.input)
    text_file = Path(args.text_file)
    output_json = Path(args.output_json)

    if output_json.exists() and not args.overwrite:
        raise FileExistsError(f"Refusing to overwrite existing output: {output_json}")
    if not audio.exists():
        raise FileNotFoundError(audio)
    if not text_file.exists():
        raise FileNotFoundError(text_file)

    text = text_file.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Transcript text file is empty: {text_file}")

    print(json.dumps({"stage": "load-aligner", "model": args.aligner_model, "dtype": args.dtype, "deviceMap": args.device_map}), file=sys.stderr, flush=True)
    from qwen_asr import Qwen3ForcedAligner

    aligner = Qwen3ForcedAligner.from_pretrained(
        args.aligner_model,
        dtype=torch_dtype(args.dtype),
        device_map=args.device_map,
    )

    print(json.dumps({"stage": "align", "audio": str(audio), "textChars": len(text), "language": args.language}), file=sys.stderr, flush=True)
    results = aligner.align(audio=str(audio), text=text, language=args.language)
    if len(results) != 1:
        raise RuntimeError(f"Expected one aligner result, got {len(results)}")
    items = result_items(results[0])

    payload = {
        "config": {
            "source": "transcript",
            "aligner_model": args.aligner_model,
            "language": args.language,
            "device_map": args.device_map,
            "dtype": args.dtype,
            "return_time_stamps": True,
        },
        "language": args.language,
        "text": text,
        "timestamps": items,
        "segments": [],
        "audio_path": str(audio),
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"json": str(output_json), "timestampCount": len(items)}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
