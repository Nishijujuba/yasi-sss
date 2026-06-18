from __future__ import annotations

import base64
import importlib
import json
import re
import subprocess
import uuid
from pathlib import Path

import pytest

from builder.convert_audio import AudioValidationError


def _load_module():
    try:
        return importlib.import_module("builder.vocabulary_audio")
    except ModuleNotFoundError:
        pytest.fail("builder.vocabulary_audio module is required")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _unique_test_dir(name: str) -> Path:
    path = Path("tmp") / "test-runs" / f"{name}-{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    return path


def _write_minimal_inputs(root: Path) -> dict[str, Path]:
    vocabulary_path = root / "vocabulary.json"
    output_dir = root / "assets" / "audio" / "vocabulary"
    ffmpeg = root / "ffmpeg.exe"
    ffprobe = root / "ffprobe.exe"

    _write_json(
        vocabulary_path,
        [
            {
                "id": "ardleigh",
                "term": "Ardleigh",
                "normalizedTerm": "ardleigh",
                "acceptedVariants": [],
                "meaningZh": "地名",
                "spokenText": "ard lee",
                "audio": "assets/audio/vocabulary/ardleigh.mp3",
            }
        ],
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg.write_bytes(b"ffmpeg")
    ffprobe.write_bytes(b"ffprobe")

    return {
        "vocabulary_path": vocabulary_path,
        "output_dir": output_dir,
        "ffmpeg": ffmpeg,
        "ffprobe": ffprobe,
    }


class FakeSynthesizer:
    def __init__(self, *, fail: Exception | None = None, write_wav: bool = True):
        self.calls: list[tuple[str, Path]] = []
        self.fail = fail
        self.write_wav = write_wav

    def synthesize_to_wav(self, text: str, output_path: Path) -> None:
        self.calls.append((text, Path(output_path)))
        if self.fail is not None:
            raise self.fail
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if self.write_wav:
            output_path.write_bytes(b"wav")


def test_vocabulary_audio_generates_tts_mp3_from_spoken_text_and_publishes_output(
    monkeypatch,
):
    module = _load_module()
    root = _unique_test_dir("vocabulary-audio-tts")
    paths = _write_minimal_inputs(root)
    temp_output_dir = root / "待删除" / "vocabulary-audio"
    synthesizer = FakeSynthesizer()
    ffmpeg_commands = []

    def fake_run(command, *, capture_output, text, check, encoding, errors):
        assert encoding == "utf-8"
        assert errors == "replace"
        executable = Path(command[0])
        if executable == paths["ffmpeg"]:
            ffmpeg_commands.append(command)
            Path(command[-1]).write_bytes(b"mp3")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        if executable == paths["ffprobe"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    {
                        "streams": [{"codec_type": "audio"}],
                        "format": {"duration": "1.25"},
                    }
                ),
                stderr="",
            )

        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(module, "TEMP_OUTPUT_DIR", temp_output_dir)

    outputs = module.build_vocabulary_audio_clips(
        vocabulary_path=paths["vocabulary_path"],
        output_dir=paths["output_dir"],
        ffmpeg_path=paths["ffmpeg"],
        ffprobe_path=paths["ffprobe"],
        synthesizer=synthesizer,
    )

    assert outputs == [paths["output_dir"] / "ardleigh.mp3"]
    assert outputs[0].read_bytes() == b"mp3"
    assert len(synthesizer.calls) == 1
    spoken_text, wav_path = synthesizer.calls[0]
    assert spoken_text == "ard lee"
    assert spoken_text != "Ardleigh"
    assert wav_path.parent == temp_output_dir
    assert wav_path.name.startswith(".ardleigh.")
    assert wav_path.name.endswith(".tmp.wav")

    assert len(ffmpeg_commands) == 1
    mp3_temp_output = Path(ffmpeg_commands[0][-1])
    assert ffmpeg_commands[0][:-1] == [
        str(paths["ffmpeg"]),
        "-y",
        "-i",
        str(wav_path),
        "-vn",
        "-codec:a",
        "libmp3lame",
        "-q:a",
        "2",
    ]
    assert mp3_temp_output.parent == temp_output_dir
    assert mp3_temp_output.name.startswith(".ardleigh.")
    assert mp3_temp_output.name.endswith(".tmp.mp3")


def test_vocabulary_audio_rejects_duplicate_output_paths_before_tts():
    module = _load_module()
    root = _unique_test_dir("vocabulary-audio-duplicate-output")
    paths = _write_minimal_inputs(root)
    vocabulary = json.loads(paths["vocabulary_path"].read_text(encoding="utf-8"))
    vocabulary.append(
        {
            **vocabulary[0],
            "id": "ardleigh-duplicate",
            "term": "Ardleigh duplicate",
            "normalizedTerm": "ardleigh duplicate",
        }
    )
    _write_json(paths["vocabulary_path"], vocabulary)
    synthesizer = FakeSynthesizer()

    with pytest.raises(AudioValidationError, match="duplicate vocabulary audio path"):
        module.build_vocabulary_audio_clips(
            vocabulary_path=paths["vocabulary_path"],
            output_dir=paths["output_dir"],
            ffmpeg_path=paths["ffmpeg"],
            ffprobe_path=paths["ffprobe"],
            synthesizer=synthesizer,
        )

    assert synthesizer.calls == []


def test_system_speech_synthesizer_reports_missing_microsoft_zira_desktop():
    module = _load_module()

    def fake_runner(command):
        raise subprocess.CalledProcessError(
            1,
            command,
            output="",
            stderr=(
                "Required TTS voice 'Microsoft Zira Desktop' is not installed. "
                "Installed voices: Microsoft David Desktop"
            ),
        )

    synthesizer = module.WindowsSpeechSynthesizer(command_runner=fake_runner)

    with pytest.raises(AudioValidationError, match="Microsoft Zira Desktop.*not installed"):
        synthesizer.synthesize_to_wav("ard lee", Path("tmp") / "zira-missing.wav")


def test_system_speech_synthesizer_uses_encoded_payload_for_values_with_spaces():
    module = _load_module()
    root = _unique_test_dir("vocabulary-audio-encoded-payload")
    output_path = root / "spoken text.wav"
    commands = []

    def fake_runner(command):
        commands.append(command)
        output_path.write_bytes(b"wav")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    synthesizer = module.WindowsSpeechSynthesizer(command_runner=fake_runner)

    synthesizer.synthesize_to_wav("hello world", output_path)

    assert len(commands) == 1
    command = commands[0]
    assert "-EncodedCommand" in command
    assert "hello world" not in command
    assert str(output_path) not in command
    encoded_script = command[command.index("-EncodedCommand") + 1]
    script = base64.b64decode(encoded_script).decode("utf-16-le")
    payload_match = re.search(r"FromBase64String\('([^']+)'\)", script)
    assert payload_match is not None
    payload = json.loads(base64.b64decode(payload_match.group(1)).decode("utf-8"))
    assert payload == {
        "Text": "hello world",
        "OutputPath": str(output_path),
        "VoiceName": "Microsoft Zira Desktop",
    }


def test_vocabulary_audio_wraps_tts_failure_as_audio_validation_error():
    module = _load_module()
    root = _unique_test_dir("vocabulary-audio-tts-failure")
    paths = _write_minimal_inputs(root)
    synthesizer = FakeSynthesizer(fail=RuntimeError("speech engine failed"))

    with pytest.raises(AudioValidationError, match="TTS synthesis failed.*speech engine failed"):
        module.build_vocabulary_audio_clips(
            vocabulary_path=paths["vocabulary_path"],
            output_dir=paths["output_dir"],
            ffmpeg_path=paths["ffmpeg"],
            ffprobe_path=paths["ffprobe"],
            synthesizer=synthesizer,
        )

    assert not (paths["output_dir"] / "ardleigh.mp3").exists()


def test_vocabulary_audio_rejects_ffmpeg_failure(monkeypatch):
    module = _load_module()
    root = _unique_test_dir("vocabulary-audio-ffmpeg-failure")
    paths = _write_minimal_inputs(root)
    synthesizer = FakeSynthesizer()

    def fake_run(command, *, capture_output, text, check, encoding, errors):
        if Path(command[0]) == paths["ffmpeg"]:
            raise subprocess.CalledProcessError(1, command, output="", stderr="ffmpeg exploded")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(AudioValidationError, match="ffmpeg failed.*ffmpeg exploded"):
        module.build_vocabulary_audio_clips(
            vocabulary_path=paths["vocabulary_path"],
            output_dir=paths["output_dir"],
            ffmpeg_path=paths["ffmpeg"],
            ffprobe_path=paths["ffprobe"],
            synthesizer=synthesizer,
        )


@pytest.mark.parametrize(
    ("ffmpeg_payload", "duration", "expected_message"),
    [
        (None, "1.25", "missing or empty"),
        (b"", "1.25", "missing or empty"),
        (b"mp3", "0.24", "expected 0.25s..6.0s"),
        (b"mp3", "6.01", "expected 0.25s..6.0s"),
    ],
)
def test_vocabulary_audio_rejects_missing_empty_or_abnormal_mp3_output(
    monkeypatch,
    ffmpeg_payload,
    duration,
    expected_message,
):
    module = _load_module()
    root = _unique_test_dir("vocabulary-audio-invalid-output")
    paths = _write_minimal_inputs(root)
    synthesizer = FakeSynthesizer()

    def fake_run(command, *, capture_output, text, check, encoding, errors):
        executable = Path(command[0])
        if executable == paths["ffmpeg"]:
            if ffmpeg_payload is not None:
                Path(command[-1]).write_bytes(ffmpeg_payload)
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        if executable == paths["ffprobe"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    {
                        "streams": [{"codec_type": "audio"}],
                        "format": {"duration": duration},
                    }
                ),
                stderr="",
            )

        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(AudioValidationError, match=expected_message):
        module.build_vocabulary_audio_clips(
            vocabulary_path=paths["vocabulary_path"],
            output_dir=paths["output_dir"],
            ffmpeg_path=paths["ffmpeg"],
            ffprobe_path=paths["ffprobe"],
            synthesizer=synthesizer,
        )

    assert not (paths["output_dir"] / "ardleigh.mp3").exists()
