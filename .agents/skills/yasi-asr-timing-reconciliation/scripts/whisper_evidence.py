from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "yasi.asr-timing-evidence.v1"
ENGINE = "whisper"
ALLOWED_MODELS = {"small", "medium", "large-v3"}
DEFAULT_MODEL = "small"
DEFAULT_WHISPER_CLI = Path(r"D:\Project\video2pdf\kimi\.venv\Scripts\whisper.exe")


def find_repo_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__)).resolve()
    for candidate in (current.parent, *current.parents):
        if (candidate / "public").exists() and (candidate / ".agents").exists():
            return candidate
    return Path.cwd()


REPO_ROOT = find_repo_root()
DEFAULT_OUTPUT_ROOT = (
    REPO_ROOT / "\u5f85\u5220\u9664" / "yasi-asr-timing-reconciliation"
)


def section_label(section: int | str) -> str:
    return f"section-{int(section):02d}"


def default_pack_root() -> Path:
    return REPO_ROOT / "public" / "packs" / "cambridge-10" / "test-1" / "listening"


def default_source_audio(section: int | str, *, pack_root: Path | str | None = None) -> Path:
    root = Path(pack_root) if pack_root is not None else default_pack_root()
    return root / "assets" / "audio" / f"{section_label(section)}.mp3"


def default_model_dir() -> Path:
    home = os.environ.get("USERPROFILE")
    if home:
        return Path(home) / ".cache" / "whisper"
    return Path.home() / ".cache" / "whisper"


def validate_model(model: str) -> str:
    if model not in ALLOWED_MODELS:
        allowed = ", ".join(sorted(ALLOWED_MODELS))
        raise ValueError(f"Unsupported Whisper model: {model}. Allowed models: {allowed}")
    return model


def output_dir_for_model(
    model: str,
    *,
    section: int | str = 1,
    pack_id: str | None = None,
    output_root: Path | str | None = None,
) -> Path:
    validate_model(model)
    root = Path(output_root) if output_root is not None else DEFAULT_OUTPUT_ROOT
    if pack_id:
        root = root / pack_id
    return root / section_label(section) / model


def build_whisper_command(
    *,
    source_audio: Path | str,
    model: str,
    output_dir: Path | str,
    whisper_cli: Path | str = DEFAULT_WHISPER_CLI,
    model_dir: Path | str | None = None,
) -> list[str]:
    validate_model(model)
    resolved_model_dir = Path(model_dir) if model_dir is not None else default_model_dir()
    return [
        str(whisper_cli),
        str(source_audio),
        "--model",
        model,
        "--model_dir",
        str(resolved_model_dir),
        "--language",
        "en",
        "--word_timestamps",
        "True",
        "--output_format",
        "json",
        "--output_dir",
        str(output_dir),
    ]


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize_word(word: str) -> str:
    lowered = word.strip().lower().replace("\u2019", "'")
    return "".join(re.findall(r"[a-z0-9']+", lowered))


def find_whisper_json(output_dir: Path, source_audio: Path) -> Path:
    expected = output_dir / f"{source_audio.stem}.json"
    if expected.exists():
        return expected

    json_files = sorted(
        path for path in output_dir.glob("*.json") if path.name != "asr-timing-evidence.json"
    )
    if len(json_files) == 1:
        return json_files[0]
    if not json_files:
        raise FileNotFoundError(f"Whisper did not produce a JSON file in {output_dir}")
    raise FileExistsError(f"Multiple Whisper JSON files found in {output_dir}")


def normalize_whisper_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    words: list[dict[str, Any]] = []
    for segment in payload.get("segments", []):
        for item in segment.get("words", []) or []:
            raw_word = str(item.get("word", "")).strip()
            if not raw_word:
                continue
            if item.get("start") is None or item.get("end") is None:
                continue
            words.append(
                {
                    "index": len(words),
                    "word": raw_word,
                    "normalized": normalize_word(raw_word),
                    "start": float(item["start"]),
                    "end": float(item["end"]),
                }
            )
    return words


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def generate_evidence(
    *,
    source_audio: Path | str | None = None,
    pack_root: Path | str | None = None,
    pack_id: str | None = None,
    model: str,
    section: int | str = 1,
    output_root: Path | str | None = None,
    output_dir: Path | str | None = None,
    whisper_cli: Path | str = DEFAULT_WHISPER_CLI,
    model_dir: Path | str | None = None,
    overwrite: bool = False,
    generated_at: str | None = None,
) -> Path:
    validate_model(model)
    audio_path = Path(source_audio) if source_audio is not None else default_source_audio(section, pack_root=pack_root)
    run_output_dir = (
        Path(output_dir)
        if output_dir is not None
        else output_dir_for_model(model, section=section, pack_id=pack_id, output_root=output_root)
    )
    run_output_dir.mkdir(parents=True, exist_ok=True)

    evidence_path = run_output_dir / "asr-timing-evidence.json"
    if evidence_path.exists() and not overwrite:
        return evidence_path

    command = build_whisper_command(
        source_audio=audio_path,
        model=model,
        output_dir=run_output_dir,
        whisper_cli=whisper_cli,
        model_dir=model_dir,
    )
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    started_at = time.perf_counter()
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    runtime_seconds = time.perf_counter() - started_at

    write_text(run_output_dir / "whisper.stdout.log", completed.stdout or "")
    write_text(run_output_dir / "whisper.stderr.log", completed.stderr or "")
    if completed.returncode != 0:
        raise RuntimeError(
            f"Whisper failed for model {model} with exit code {completed.returncode}"
        )

    whisper_json_path = find_whisper_json(run_output_dir, audio_path)
    whisper_payload = json.loads(whisper_json_path.read_text(encoding="utf-8"))
    evidence = {
        "schemaVersion": SCHEMA_VERSION,
        "engine": ENGINE,
        "model": model,
        "command": command,
        "sourceAudio": str(audio_path),
        "generatedAt": generated_at or utc_timestamp(),
        "metrics": {"runtimeSeconds": runtime_seconds},
        "words": normalize_whisper_payload(whisper_payload),
    }
    evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return evidence_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Yasi Whisper timing evidence.")
    parser.add_argument("--section", type=int, default=1)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--pack-root", type=Path)
    parser.add_argument("--pack-id")
    parser.add_argument("--source-audio", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--whisper-cli", type=Path, default=DEFAULT_WHISPER_CLI)
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        evidence_path = generate_evidence(
            source_audio=args.source_audio,
            pack_root=args.pack_root,
            pack_id=args.pack_id,
            model=args.model,
            section=args.section,
            output_root=args.output_root,
            output_dir=args.output_dir,
            whisper_cli=args.whisper_cli,
            model_dir=args.model_dir,
            overwrite=args.overwrite,
        )
    except Exception as exc:
        raise SystemExit(str(exc)) from exc
    print(evidence_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
