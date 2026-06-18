from __future__ import annotations

import base64
import json
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Callable, Protocol

from pydantic import ValidationError

from builder.config import AUDIO_ASSET_ROOT, FFMPEG, FFPROBE, SOURCE_DATA_ROOT
from builder.convert_audio import (
    AudioValidationError,
    _replace_with_retries,
    _require_existing_file,
    _run_captured,
    _same_file_content,
    probe_duration_seconds,
)
from builder.models import VocabularyItem


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRASH_DIR = PROJECT_ROOT / "待删除"
TEMP_OUTPUT_DIR = TRASH_DIR / "vocabulary-audio"
DEFAULT_OUTPUT_DIR = AUDIO_ASSET_ROOT / "vocabulary"
DEFAULT_TTS_VOICE = "Microsoft Zira Desktop"
CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]


class SpeechSynthesizer(Protocol):
    def synthesize_to_wav(self, text: str, output_path: Path) -> None:
        """Write synthesized speech to a WAV file."""


class WindowsSpeechSynthesizer:
    def __init__(
        self,
        *,
        voice_name: str = DEFAULT_TTS_VOICE,
        powershell_path: str = "powershell.exe",
        command_runner: CommandRunner = _run_captured,
    ):
        self.voice_name = voice_name
        self.powershell_path = powershell_path
        self.command_runner = command_runner

    def synthesize_to_wav(self, text: str, output_path: Path) -> None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "Text": text,
            "OutputPath": str(output_path),
            "VoiceName": self.voice_name,
        }
        payload_base64 = base64.b64encode(
            json.dumps(payload, ensure_ascii=False).encode("utf-8")
        ).decode("ascii")
        script = r"""
& {
    $ErrorActionPreference = 'Stop'
    $PayloadJson = [System.Text.Encoding]::UTF8.GetString(
        [System.Convert]::FromBase64String('__PAYLOAD_BASE64__')
    )
    $Payload = $PayloadJson | ConvertFrom-Json
    $Text = [string]$Payload.Text
    $OutputPath = [string]$Payload.OutputPath
    $VoiceName = [string]$Payload.VoiceName
    Add-Type -AssemblyName System.Speech
    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
    try {
        $installedVoices = @($synth.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name })
        if ($installedVoices -notcontains $VoiceName) {
            $voiceList = if ($installedVoices.Count -gt 0) { $installedVoices -join ', ' } else { '<none>' }
            throw "Required TTS voice '$VoiceName' is not installed. Installed voices: $voiceList"
        }
        $synth.SelectVoice($VoiceName)
        $synth.SetOutputToWaveFile($OutputPath)
        [void]$synth.Speak($Text)
    }
    finally {
        if ($null -ne $synth) {
            $synth.Dispose()
        }
    }
}
""".strip().replace("__PAYLOAD_BASE64__", payload_base64)
        encoded_script = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
        command = [
            self.powershell_path,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-EncodedCommand",
            encoded_script,
        ]

        try:
            self.command_runner(command)
        except subprocess.CalledProcessError as exc:
            details = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            if self.voice_name in details and "not installed" in details:
                raise AudioValidationError(details) from exc
            raise AudioValidationError(
                f"TTS synthesis failed with {self.voice_name}: {details}"
            ) from exc
        except OSError as exc:
            raise AudioValidationError(
                f"TTS synthesis failed with {self.voice_name}: {exc}"
            ) from exc

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise AudioValidationError(f"TTS synthesis produced missing or empty WAV: {output_path}")


def _read_json(path: Path) -> object:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AudioValidationError(f"required vocabulary audio input is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise AudioValidationError(f"invalid JSON in vocabulary audio input: {path}") from exc


def _load_model_list(model_type, path: Path, label: str):
    payload = _read_json(path)
    if not isinstance(payload, list):
        raise AudioValidationError(f"{label} must be a JSON array")
    try:
        return [model_type.model_validate(item) for item in payload]
    except ValidationError as exc:
        raise AudioValidationError(f"{label} failed schema validation: {exc}") from exc


def _temporary_output_path(output_path: Path, *, suffix: str | None = None) -> Path:
    TEMP_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    temp_suffix = output_path.suffix if suffix is None else suffix
    return TEMP_OUTPUT_DIR / f".{output_path.stem}.{uuid.uuid4().hex}.tmp{temp_suffix}"


def _expected_audio_path(item: VocabularyItem) -> str:
    return f"assets/audio/vocabulary/{item.id}.mp3"


def _validate_audio_destinations(vocabulary: list[VocabularyItem]) -> None:
    seen: dict[str, str] = {}
    for item in vocabulary:
        expected = _expected_audio_path(item)
        if item.audio in seen:
            raise AudioValidationError(
                f"duplicate vocabulary audio path {item.audio}: {seen[item.audio]}, {item.id}"
            )
        if item.audio != expected:
            raise AudioValidationError(
                f"vocabulary {item.id} audio path must be {expected}; found {item.audio}"
            )
        seen[item.audio] = item.id


def _archive_temp_file(path: Path) -> None:
    if not path.exists():
        return
    if path.resolve().parent == TEMP_OUTPUT_DIR.resolve():
        return
    TRASH_DIR.mkdir(exist_ok=True)
    archive_path = TRASH_DIR / f"{uuid.uuid4().hex}-{path.name}"
    try:
        _replace_with_retries(path, archive_path)
    except OSError:
        return


def build_vocabulary_audio_clips(
    *,
    vocabulary_path: Path = SOURCE_DATA_ROOT / "vocabulary.json",
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    ffmpeg_path: Path = FFMPEG,
    ffprobe_path: Path = FFPROBE,
    synthesizer: SpeechSynthesizer | None = None,
) -> list[Path]:
    vocabulary = _load_model_list(VocabularyItem, Path(vocabulary_path), "vocabulary")
    _validate_audio_destinations(vocabulary)

    ffmpeg_path = Path(ffmpeg_path)
    ffprobe_path = Path(ffprobe_path)
    output_dir = Path(output_dir)
    synthesizer = synthesizer or WindowsSpeechSynthesizer()

    _require_existing_file(ffmpeg_path, "ffmpeg executable")
    _require_existing_file(ffprobe_path, "ffprobe executable")
    output_dir.mkdir(parents=True, exist_ok=True)

    outputs: list[Path] = []
    for item in vocabulary:
        output_path = output_dir / f"{item.id}.mp3"
        temp_wav_path = _temporary_output_path(output_path, suffix=".wav")
        temp_output_path = _temporary_output_path(output_path)
        try:
            synthesizer.synthesize_to_wav(item.spokenText, temp_wav_path)
        except AudioValidationError:
            _archive_temp_file(temp_wav_path)
            raise
        except Exception as exc:
            _archive_temp_file(temp_wav_path)
            raise AudioValidationError(
                f"TTS synthesis failed for vocabulary {item.id}: {exc}"
            ) from exc

        try:
            if not temp_wav_path.exists() or temp_wav_path.stat().st_size == 0:
                raise AudioValidationError(f"TTS WAV output is missing or empty: {temp_wav_path}")
        except AudioValidationError:
            _archive_temp_file(temp_wav_path)
            raise

        command = [
            str(ffmpeg_path),
            "-y",
            "-i",
            str(temp_wav_path),
            "-vn",
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "2",
            str(temp_output_path),
        ]

        try:
            _run_captured(command)
        except subprocess.CalledProcessError as exc:
            _archive_temp_file(temp_output_path)
            details = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            raise AudioValidationError(f"ffmpeg failed for vocabulary {item.id}: {details}") from exc

        try:
            if not temp_output_path.exists() or temp_output_path.stat().st_size == 0:
                raise AudioValidationError(f"Vocabulary clip output is missing or empty: {temp_output_path}")
            output_duration = probe_duration_seconds(temp_output_path, ffprobe_path=ffprobe_path)
            if output_duration < 0.25 or output_duration > 6.0:
                raise AudioValidationError(
                    f"vocabulary clip duration for {item.id} is {output_duration:.3f}s; "
                    "expected 0.25s..6.0s"
                )
        except AudioValidationError:
            _archive_temp_file(temp_output_path)
            raise

        try:
            if _same_file_content(temp_output_path, output_path):
                _archive_temp_file(temp_output_path)
                outputs.append(output_path)
                continue
            _replace_with_retries(temp_output_path, output_path)
        except OSError as exc:
            _archive_temp_file(temp_output_path)
            if output_path.exists() and output_path.stat().st_size > 0:
                raise AudioValidationError(
                    f"Could not publish vocabulary clip {temp_output_path} to {output_path}: {exc}. "
                    "The existing output differs from the newly generated file."
                ) from exc
            try:
                output_path.write_bytes(temp_output_path.read_bytes())
            except OSError as fallback_exc:
                raise AudioValidationError(
                    f"Could not publish vocabulary clip {temp_output_path} to {output_path}: {exc}; "
                    f"fallback copy also failed: {fallback_exc}"
                ) from fallback_exc
        outputs.append(output_path)

    return outputs


def main() -> int:
    try:
        outputs = build_vocabulary_audio_clips()
    except AudioValidationError as exc:
        print(f"Vocabulary audio generation failed: {exc}", file=sys.stderr)
        return 1

    for output in outputs:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
