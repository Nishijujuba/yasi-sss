from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Iterable


class AudioValidationError(RuntimeError):
    """Raised when audio conversion or validation cannot be completed safely."""


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FFMPEG_PATH = Path(r"D:\Project\video2pdf\kimi\tools\ffmpeg\bin\ffmpeg.exe")
DEFAULT_FFPROBE_PATH = Path(r"D:\Project\video2pdf\kimi\tools\ffmpeg\bin\ffprobe.exe")
DEFAULT_SOURCES = [
    PROJECT_ROOT / "resources" / "剑桥" / "剑桥雅思10" / "剑桥雅思10音频" / "test1" / "01 Track 1.wma",
    PROJECT_ROOT / "resources" / "剑桥" / "剑桥雅思10" / "剑桥雅思10音频" / "test1" / "02 Track 2.wma",
    PROJECT_ROOT / "resources" / "剑桥" / "剑桥雅思10" / "剑桥雅思10音频" / "test1" / "03 Track 3.wma",
    PROJECT_ROOT / "resources" / "剑桥" / "剑桥雅思10" / "剑桥雅思10音频" / "test1" / "04 Track 4.wma",
]
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "public" / "packs" / "cambridge-10" / "test-1" / "listening" / "assets" / "audio"
)


def _require_existing_file(path: Path, description: str) -> None:
    if not path.exists():
        raise AudioValidationError(f"{description} not found: {path}")
    if not path.is_file():
        raise AudioValidationError(f"{description} is not a file: {path}")


def _run_captured(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )


def probe_duration_seconds(media_path: Path, *, ffprobe_path: Path = DEFAULT_FFPROBE_PATH) -> float:
    """Return media duration after proving ffprobe found an audio stream."""

    ffprobe_path = Path(ffprobe_path)
    media_path = Path(media_path)
    _require_existing_file(ffprobe_path, "ffprobe executable")
    _require_existing_file(media_path, "Media file")

    command = [
        str(ffprobe_path),
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        str(media_path),
    ]
    try:
        result = _run_captured(command)
    except subprocess.CalledProcessError as exc:
        details = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise AudioValidationError(f"ffprobe failed for {media_path}: {details}") from exc

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AudioValidationError(f"ffprobe returned invalid JSON for {media_path}") from exc

    streams = payload.get("streams", [])
    if not any(stream.get("codec_type") == "audio" for stream in streams):
        raise AudioValidationError(f"No audio stream found in {media_path}")

    duration_text = payload.get("format", {}).get("duration")
    try:
        duration = float(duration_text)
    except (TypeError, ValueError) as exc:
        raise AudioValidationError(f"ffprobe did not report a valid duration for {media_path}") from exc

    if duration <= 0:
        raise AudioValidationError(f"ffprobe reported a non-positive duration for {media_path}: {duration}")
    return duration


def assert_duration_match(
    source_path: Path,
    source_duration_seconds: float,
    output_path: Path,
    output_duration_seconds: float,
    *,
    tolerance_seconds: float = 0.10,
) -> None:
    """Validate that converted output duration stays within the allowed drift."""

    delta = abs(source_duration_seconds - output_duration_seconds)
    if delta > tolerance_seconds:
        raise AudioValidationError(
            "Duration mismatch between "
            f"{source_path} ({source_duration_seconds:.3f}s) and "
            f"{output_path} ({output_duration_seconds:.3f}s): "
            f"delta {delta:.3f}s exceeds {tolerance_seconds:.3f}s"
        )


def convert_audio_sections(
    *,
    sources: Iterable[Path] = DEFAULT_SOURCES,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    ffmpeg_path: Path = DEFAULT_FFMPEG_PATH,
    ffprobe_path: Path = DEFAULT_FFPROBE_PATH,
    tolerance_seconds: float = 0.10,
) -> list[Path]:
    """Convert Cambridge IELTS 10 Test 1 Listening WMA tracks into MP3 sections."""

    ffmpeg_path = Path(ffmpeg_path)
    ffprobe_path = Path(ffprobe_path)
    output_dir = Path(output_dir)
    source_paths = [Path(source) for source in sources]

    _require_existing_file(ffmpeg_path, "ffmpeg executable")
    _require_existing_file(ffprobe_path, "ffprobe executable")
    for source_path in source_paths:
        if not source_path.exists():
            raise AudioValidationError(f"Source audio not found: {source_path}")
        if not source_path.is_file():
            raise AudioValidationError(f"Source audio is not a file: {source_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []

    for index, source_path in enumerate(source_paths, start=1):
        source_duration = probe_duration_seconds(source_path, ffprobe_path=ffprobe_path)
        output_path = output_dir / f"section-{index:02d}.mp3"
        command = [
            str(ffmpeg_path),
            "-y",
            "-i",
            str(source_path),
            "-vn",
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "2",
            str(output_path),
        ]

        try:
            _run_captured(command)
        except subprocess.CalledProcessError as exc:
            details = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            raise AudioValidationError(f"ffmpeg failed for {source_path}: {details}") from exc

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise AudioValidationError(f"Converted output is missing or empty: {output_path}")

        output_duration = probe_duration_seconds(output_path, ffprobe_path=ffprobe_path)
        assert_duration_match(
            source_path,
            source_duration,
            output_path,
            output_duration,
            tolerance_seconds=tolerance_seconds,
        )
        outputs.append(output_path)

    return outputs


def main() -> int:
    try:
        outputs = convert_audio_sections()
    except AudioValidationError as exc:
        print(f"Audio conversion failed: {exc}", file=sys.stderr)
        return 1

    for output in outputs:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
