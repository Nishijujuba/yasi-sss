from __future__ import annotations

import importlib
import json
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
    answers_path = root / "answers.json"
    questions_path = root / "questions.json"
    vocabulary_path = root / "vocabulary.json"
    windows_path = root / "answer-audio-windows.json"
    section_audio_dir = root / "assets" / "audio"
    output_dir = section_audio_dir / "vocabulary"
    ffmpeg = root / "ffmpeg.exe"
    ffprobe = root / "ffprobe.exe"

    _write_json(
        answers_path,
        [
            {
                "questionIds": ["q1"],
                "accepted": [["Ardleigh"]],
                "orderIndependent": False,
                "provenance": [
                    {
                        "kind": "official-answer-key",
                        "source": "answer-key.pdf",
                        "page": 151,
                        "detail": "TEST 1 LISTENING",
                    }
                ],
                "reviewStatus": "official",
            }
        ],
    )
    _write_json(
        questions_path,
        [
            {
                "id": "q1",
                "number": 1,
                "section": 1,
                "responseType": "blank",
                "page": "page-010.png",
                "focusOrder": 1,
            }
        ],
    )
    _write_json(
        vocabulary_path,
        [
            {
                "id": "ardleigh",
                "term": "Ardleigh",
                "normalizedTerm": "ardleigh",
                "acceptedVariants": [],
                "meaningZh": "地名",
                "audio": "assets/audio/vocabulary/ardleigh.mp3",
            }
        ],
    )
    _write_json(
        windows_path,
        [
            {
                "vocabularyId": "ardleigh",
                "questionId": "q1",
                "section": 1,
                "startTime": 10.0,
                "endTime": 11.0,
                "paddingBefore": 0.25,
                "paddingAfter": 0.5,
            }
        ],
    )
    section_audio_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    (section_audio_dir / "section-01.mp3").write_bytes(b"section")
    ffmpeg.write_bytes(b"ffmpeg")
    ffprobe.write_bytes(b"ffprobe")

    return {
        "answers_path": answers_path,
        "questions_path": questions_path,
        "vocabulary_path": vocabulary_path,
        "windows_path": windows_path,
        "section_audio_dir": section_audio_dir,
        "output_dir": output_dir,
        "ffmpeg": ffmpeg,
        "ffprobe": ffprobe,
    }


def test_vocabulary_audio_clips_run_expected_ffmpeg_command_and_publish_temp_output(
    monkeypatch,
):
    module = _load_module()
    root = _unique_test_dir("vocabulary-audio-command")
    paths = _write_minimal_inputs(root)
    temp_output_dir = root / "待删除" / "vocabulary-audio"
    commands = []

    def fake_replace(self, target):
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.read_bytes())
        return target

    def fake_run(command, *, capture_output, text, check, encoding, errors):
        assert encoding == "utf-8"
        assert errors == "replace"
        executable = Path(command[0])
        if executable == paths["ffmpeg"]:
            commands.append(command)
            Path(command[-1]).write_bytes(b"mp3")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        if executable == paths["ffprobe"]:
            target = Path(command[-1])
            duration = "1.75" if target.name.startswith(".ardleigh.") else "300.0"
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
    monkeypatch.setattr(Path, "replace", fake_replace)
    monkeypatch.setattr(module, "TEMP_OUTPUT_DIR", temp_output_dir)

    outputs = module.build_vocabulary_audio_clips(
        answers_path=paths["answers_path"],
        questions_path=paths["questions_path"],
        vocabulary_path=paths["vocabulary_path"],
        windows_path=paths["windows_path"],
        section_audio_dir=paths["section_audio_dir"],
        output_dir=paths["output_dir"],
        ffmpeg_path=paths["ffmpeg"],
        ffprobe_path=paths["ffprobe"],
    )

    assert outputs == [paths["output_dir"] / "ardleigh.mp3"]
    assert outputs[0].read_bytes() == b"mp3"
    assert len(commands) == 1
    command = commands[0]
    assert command[:-1] == [
        str(paths["ffmpeg"]),
        "-y",
        "-ss",
        "9.750",
        "-i",
        str(paths["section_audio_dir"] / "section-01.mp3"),
        "-t",
        "1.750",
        "-vn",
        "-codec:a",
        "libmp3lame",
        "-q:a",
        "2",
    ]
    temp_output = Path(command[-1])
    assert temp_output.parent == temp_output_dir
    assert temp_output.name.startswith(".ardleigh.")
    assert temp_output.name.endswith(".tmp.mp3")


def test_vocabulary_audio_clips_reject_duration_mismatch_and_keep_temp_under_trash(
    monkeypatch,
):
    module = _load_module()
    root = _unique_test_dir("vocabulary-audio-duration")
    paths = _write_minimal_inputs(root)
    temp_output_dir = root / "待删除" / "vocabulary-audio"
    temp_outputs = []

    def fake_run(command, *, capture_output, text, check, encoding, errors):
        executable = Path(command[0])
        if executable == paths["ffmpeg"]:
            temp_output = Path(command[-1])
            temp_output.write_bytes(b"mp3")
            temp_outputs.append(temp_output)
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        if executable == paths["ffprobe"]:
            target = Path(command[-1])
            duration = "2.20" if target.name.startswith(".ardleigh.") else "300.0"
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
    monkeypatch.setattr(module, "TEMP_OUTPUT_DIR", temp_output_dir)

    with pytest.raises(AudioValidationError, match="Duration mismatch"):
        module.build_vocabulary_audio_clips(
            answers_path=paths["answers_path"],
            questions_path=paths["questions_path"],
            vocabulary_path=paths["vocabulary_path"],
            windows_path=paths["windows_path"],
            section_audio_dir=paths["section_audio_dir"],
            output_dir=paths["output_dir"],
            ffmpeg_path=paths["ffmpeg"],
            ffprobe_path=paths["ffprobe"],
        )

    assert temp_outputs
    assert all(temp_output.parent == temp_output_dir for temp_output in temp_outputs)
    assert not (paths["output_dir"] / "ardleigh.mp3").exists()


def test_vocabulary_audio_clips_copy_new_output_when_atomic_publish_is_denied(
    monkeypatch,
):
    module = _load_module()
    root = _unique_test_dir("vocabulary-audio-copy-fallback")
    paths = _write_minimal_inputs(root)
    temp_output_dir = root / "待删除" / "vocabulary-audio"
    temp_outputs = []

    def fake_replace(self, target):
        raise PermissionError("atomic move denied")

    def fake_run(command, *, capture_output, text, check, encoding, errors):
        executable = Path(command[0])
        if executable == paths["ffmpeg"]:
            temp_output = Path(command[-1])
            temp_output.write_bytes(b"mp3")
            temp_outputs.append(temp_output)
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        if executable == paths["ffprobe"]:
            target = Path(command[-1])
            duration = "1.75" if target.name.startswith(".ardleigh.") else "300.0"
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
    monkeypatch.setattr(Path, "replace", fake_replace)
    monkeypatch.setattr(module, "TEMP_OUTPUT_DIR", temp_output_dir)
    monkeypatch.setattr(module, "TRASH_DIR", root / "待删除")

    outputs = module.build_vocabulary_audio_clips(
        answers_path=paths["answers_path"],
        questions_path=paths["questions_path"],
        vocabulary_path=paths["vocabulary_path"],
        windows_path=paths["windows_path"],
        section_audio_dir=paths["section_audio_dir"],
        output_dir=paths["output_dir"],
        ffmpeg_path=paths["ffmpeg"],
        ffprobe_path=paths["ffprobe"],
    )

    assert outputs == [paths["output_dir"] / "ardleigh.mp3"]
    assert outputs[0].read_bytes() == b"mp3"
    assert temp_outputs
    assert all(temp_output.parent == temp_output_dir for temp_output in temp_outputs)


def test_vocabulary_audio_clips_reject_window_duration_outside_gate():
    module = _load_module()
    paths = _write_minimal_inputs(_unique_test_dir("vocabulary-audio-gate"))
    _write_json(
        paths["windows_path"],
        [
            {
                "vocabularyId": "ardleigh",
                "questionId": "q1",
                "section": 1,
                "startTime": 10.0,
                "endTime": 10.1,
                "paddingBefore": 0.05,
                "paddingAfter": 0.05,
            }
        ],
    )

    with pytest.raises(AudioValidationError, match="0.25s..6.0s"):
        module.build_vocabulary_audio_clips(
            answers_path=paths["answers_path"],
            questions_path=paths["questions_path"],
            vocabulary_path=paths["vocabulary_path"],
            windows_path=paths["windows_path"],
            section_audio_dir=paths["section_audio_dir"],
            output_dir=paths["output_dir"],
            ffmpeg_path=paths["ffmpeg"],
            ffprobe_path=paths["ffprobe"],
        )
