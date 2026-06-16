import json
import subprocess
from types import SimpleNamespace
from pathlib import Path

import pytest

import builder.convert_audio as convert_audio_module
from builder.convert_audio import (
    AudioValidationError,
    assert_duration_match,
    convert_audio_sections,
    probe_duration_seconds,
)


def _key(path):
    return str(Path(path)).lower()


def _patch_virtual_files(monkeypatch, files, sizes=None, contents=None):
    file_keys = {_key(path) for path in files}
    sizes = {_key(path): size for path, size in (sizes or {}).items()}
    contents = {_key(path): content for path, content in (contents or {}).items()}

    monkeypatch.setattr(Path, "exists", lambda self: _key(self) in file_keys)
    monkeypatch.setattr(Path, "is_file", lambda self: _key(self) in file_keys)
    monkeypatch.setattr(Path, "mkdir", lambda self, parents=False, exist_ok=False: None)
    monkeypatch.setattr(Path, "stat", lambda self: SimpleNamespace(st_size=sizes.get(_key(self), 1)))
    monkeypatch.setattr(Path, "read_bytes", lambda self: contents[_key(self)])
    return file_keys, sizes, contents


def test_assert_duration_match_allows_small_drift_and_rejects_outside_tolerance():
    assert_duration_match(Path("source.wma"), 10.00, Path("section.mp3"), 10.09, tolerance_seconds=0.10)

    with pytest.raises(AudioValidationError, match="Duration mismatch"):
        assert_duration_match(Path("source.wma"), 10.00, Path("section.mp3"), 10.11, tolerance_seconds=0.10)


def test_probe_duration_seconds_requires_existing_ffprobe_and_media(monkeypatch):
    media = Path(r"C:\fake\source.wma")
    ffprobe = Path(r"C:\fake\ffprobe.exe")
    _patch_virtual_files(monkeypatch, [media])

    with pytest.raises(AudioValidationError, match="ffprobe executable not found"):
        probe_duration_seconds(media, ffprobe_path=ffprobe)

    _patch_virtual_files(monkeypatch, [ffprobe])
    with pytest.raises(AudioValidationError, match="Media file not found"):
        probe_duration_seconds(media, ffprobe_path=ffprobe)


def test_probe_duration_seconds_rejects_media_without_audio_stream(monkeypatch):
    media = Path(r"C:\fake\source.wma")
    ffprobe = Path(r"C:\fake\ffprobe.exe")
    _patch_virtual_files(monkeypatch, [media, ffprobe])

    def fake_run(command, *, capture_output, text, check, encoding, errors):
        assert encoding == "utf-8"
        assert errors == "replace"
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"streams": [{"codec_type": "video"}], "format": {"duration": "12.5"}}),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(AudioValidationError, match="No audio stream"):
        probe_duration_seconds(media, ffprobe_path=ffprobe)


def test_convert_audio_sections_runs_expected_ffmpeg_command_and_validates_outputs(monkeypatch):
    sources = []
    for index in range(1, 5):
        source = Path(r"C:\fake") / f"0{index} Track {index}.wma"
        sources.append(source)

    ffmpeg = Path(r"C:\fake\ffmpeg.exe")
    ffprobe = Path(r"C:\fake\ffprobe.exe")
    output_dir = Path(r"C:\fake\audio")
    files, sizes, contents = _patch_virtual_files(monkeypatch, [*sources, ffmpeg, ffprobe])
    commands = []

    def fake_replace(self, target):
        source_key = _key(self)
        target_key = _key(target)
        files.add(target_key)
        sizes[target_key] = sizes[source_key]
        contents[target_key] = contents[source_key]
        return Path(target)

    def fake_run(command, *, capture_output, text, check, encoding, errors):
        assert encoding == "utf-8"
        assert errors == "replace"
        if Path(command[0]) == ffmpeg:
            commands.append(command)
            output_key = _key(command[-1])
            files.add(output_key)
            sizes[output_key] = 3
            contents[output_key] = b"mp3"
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        if Path(command[0]) == ffprobe:
            target = Path(command[-1])
            duration = "42.05" if target.suffix == ".mp3" else "42.00"
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps({"streams": [{"codec_type": "audio"}], "format": {"duration": duration}}),
                stderr="",
            )

        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(Path, "replace", fake_replace)

    outputs = convert_audio_sections(
        sources=sources,
        output_dir=output_dir,
        ffmpeg_path=ffmpeg,
        ffprobe_path=ffprobe,
    )

    assert outputs == [output_dir / f"section-0{index}.mp3" for index in range(1, 5)]
    assert [output.read_bytes() for output in outputs] == [b"mp3"] * 4
    assert [command[:-1] for command in commands] == [
        [
            str(ffmpeg),
            "-y",
            "-i",
            str(source),
            "-vn",
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "2",
        ]
        for index, source in enumerate(sources, start=1)
    ]
    for index, command in enumerate(commands, start=1):
        output = Path(command[-1])
        assert output.name.startswith(f".section-0{index}.")
        assert output.name.endswith(".tmp.mp3")


def test_convert_audio_sections_accepts_valid_existing_output_when_publish_is_locked(monkeypatch):
    source = Path(r"C:\fake\01 Track 1.wma")
    ffmpeg = Path(r"C:\fake\ffmpeg.exe")
    ffprobe = Path(r"C:\fake\ffprobe.exe")
    output_dir = Path(r"C:\fake\audio")
    output_path = output_dir / "section-01.mp3"
    files, sizes, contents = _patch_virtual_files(
        monkeypatch,
        [source, ffmpeg, ffprobe, output_path],
        sizes={output_path: 3},
        contents={output_path: b"existing mp3"},
    )
    monkeypatch.setattr(convert_audio_module.time, "sleep", lambda seconds: None)

    def fake_replace(self, target):
        raise PermissionError("locked")

    def fake_run(command, *, capture_output, text, check, encoding, errors):
        assert encoding == "utf-8"
        assert errors == "replace"
        if Path(command[0]) == ffmpeg:
            output_key = _key(command[-1])
            files.add(output_key)
            sizes[output_key] = 3
            contents[output_key] = b"existing mp3"
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        if Path(command[0]) == ffprobe:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps({"streams": [{"codec_type": "audio"}], "format": {"duration": "42.00"}}),
                stderr="",
            )

        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(Path, "replace", fake_replace)

    outputs = convert_audio_sections(
        sources=[source],
        output_dir=output_dir,
        ffmpeg_path=ffmpeg,
        ffprobe_path=ffprobe,
    )

    assert outputs == [output_path]
    assert output_path.read_bytes() == b"existing mp3"


def test_convert_audio_sections_rejects_locked_stale_existing_output(monkeypatch):
    source = Path(r"C:\fake\01 Track 1.wma")
    ffmpeg = Path(r"C:\fake\ffmpeg.exe")
    ffprobe = Path(r"C:\fake\ffprobe.exe")
    output_dir = Path(r"C:\fake\audio")
    output_path = output_dir / "section-01.mp3"
    files, sizes, contents = _patch_virtual_files(
        monkeypatch,
        [source, ffmpeg, ffprobe, output_path],
        sizes={output_path: 3},
        contents={output_path: b"old mp3"},
    )
    monkeypatch.setattr(convert_audio_module.time, "sleep", lambda seconds: None)

    def fake_replace(self, target):
        raise PermissionError("locked")

    def fake_run(command, *, capture_output, text, check, encoding, errors):
        assert encoding == "utf-8"
        assert errors == "replace"
        if Path(command[0]) == ffmpeg:
            output_key = _key(command[-1])
            files.add(output_key)
            sizes[output_key] = 3
            contents[output_key] = b"new mp3"
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        if Path(command[0]) == ffprobe:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps({"streams": [{"codec_type": "audio"}], "format": {"duration": "42.00"}}),
                stderr="",
            )

        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(Path, "replace", fake_replace)

    with pytest.raises(AudioValidationError, match="existing output differs"):
        convert_audio_sections(
            sources=[source],
            output_dir=output_dir,
            ffmpeg_path=ffmpeg,
            ffprobe_path=ffprobe,
        )


def test_convert_audio_sections_reports_missing_ffmpeg_and_source_file(monkeypatch):
    source = Path(r"C:\fake\source.wma")
    ffmpeg = Path(r"C:\fake\ffmpeg.exe")
    ffprobe = Path(r"C:\fake\ffprobe.exe")
    _patch_virtual_files(monkeypatch, [ffprobe])

    with pytest.raises(AudioValidationError, match="ffmpeg executable not found"):
        convert_audio_sections(
            sources=[source],
            output_dir=Path(r"C:\fake\audio"),
            ffmpeg_path=ffmpeg,
            ffprobe_path=ffprobe,
        )

    _patch_virtual_files(monkeypatch, [ffmpeg, ffprobe])
    with pytest.raises(AudioValidationError, match="Source audio not found"):
        convert_audio_sections(
            sources=[source],
            output_dir=Path(r"C:\fake\audio"),
            ffmpeg_path=ffmpeg,
            ffprobe_path=ffprobe,
        )
