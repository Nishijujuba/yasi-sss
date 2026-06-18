from __future__ import annotations

import json
import subprocess
import sys
import uuid
from importlib import util as importlib_util
from pathlib import Path

import pytest


def _load_skill_script(filename: str, module_name: str):
    script_path = Path(f".agents/skills/yasi-forced-alignment/scripts/{filename}").resolve()
    if str(script_path.parent) not in sys.path:
        sys.path.insert(0, str(script_path.parent))
    spec = importlib_util.spec_from_file_location(module_name, script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib_util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_alignment_script():
    return _load_skill_script("align_transcript.py", "test_align_transcript_script_module")


def _test_run_dir(name: str) -> Path:
    path = Path("tmp") / "test-runs" / f"{name}-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _localization_payload(words: list[str], start: float = 42.3, step: float = 8.0) -> dict:
    return {
        "schemaVersion": "yasi.localization-transcript.v1",
        "sourceAudio": "section-01.mp3",
        "engine": "existing",
        "generatedAt": "2026-06-18T00:00:00Z",
        "tokens": [
            {
                "text": word,
                "normalized": "".join(ch for ch in word.lower() if ch.isalnum()),
                "start": round(start + index * step, 3),
                "end": round(start + index * step + 0.35, 3),
                "sourceIndex": index,
            }
            for index, word in enumerate(words)
        ],
        "segments": [],
    }


def test_parser_rejects_removed_asr_route():
    module = _load_alignment_script()

    with pytest.raises(SystemExit):
        module.build_parser().parse_args(["--section", "1", "--alignment-source", "asr"])


def test_parser_accepts_localization_contract_and_rejects_invalid_values():
    module = _load_alignment_script()
    parser = module.build_parser()

    args = parser.parse_args(
        [
            "--section",
            "1",
            "--localize-content-start",
            "--localizer",
            "whisper",
            "--content-start-seconds",
            "42.3",
            "--localization-input",
            "existing.localization.json",
            "--localization-output",
            "normalized.localization.json",
            "--min-localization-score",
            "0.82",
            "--slice-overlap-seconds",
            "3",
            "--text-overlap-tokens",
            "20",
            "--whisper",
            "whisper.exe",
        ]
    )

    assert args.localize_content_start is True
    assert args.localizer == "existing"
    assert args.content_start_seconds == 42.3
    assert args.localization_input == "existing.localization.json"
    assert args.localization_output == "normalized.localization.json"
    assert args.min_localization_score == 0.82
    assert args.slice_overlap_seconds == 3.0
    assert args.text_overlap_tokens == 20
    assert args.whisper == "whisper.exe"

    invalid_cases = [
        ["--section", "1", "--content-start-seconds", "-0.1"],
        ["--section", "1", "--min-localization-score", "1.01"],
        ["--section", "1", "--min-localization-score", "-0.01"],
        ["--section", "1", "--slice-overlap-seconds", "-1"],
        ["--section", "1", "--text-overlap-tokens", "-1"],
    ]
    for argv in invalid_cases:
        with pytest.raises(SystemExit):
            parser.parse_args(argv)


def test_official_and_localization_token_records_share_normalization():
    module = _load_alignment_script()

    official = module.official_token_records({"segments": [{"order": 7, "text": "Hello, co-op costs £4.50"}]})
    localization = module.localization_tokens_from_payload(
        {
            "tokens": [
                {"text": "Hello", "start": 42.31, "end": 42.62, "sourceIndex": 86},
                {"text": "co-op", "start": 42.7, "end": 43.0, "sourceIndex": 87},
            ]
        }
    )

    assert official[0] == {
        "globalTokenIndex": 0,
        "segmentOrder": 7,
        "tokenIndex": 0,
        "text": "Hello",
        "normalized": "hello",
    }
    assert official[1]["normalized"] == "coop"
    assert official[3]["normalized"] == "450"
    assert module.localization_token_records(localization)[:2] == [
        {"text": "Hello", "normalized": "hello", "start": 42.31, "end": 42.62, "sourceIndex": 86},
        {"text": "co-op", "normalized": "coop", "start": 42.7, "end": 43.0, "sourceIndex": 87},
    ]


def test_load_localization_transcript_normalizes_common_timestamp_shapes():
    module = _load_alignment_script()
    run_dir = _test_run_dir("load-localization")
    payload_path = run_dir / "whisper.json"
    payload_path.write_text(
        json.dumps(
            {
                "segments": [
                    {
                        "start": 1.0,
                        "end": 2.0,
                        "text": "hello world",
                        "words": [
                            {"word": " hello", "start": 1.0, "end": 1.25},
                            {"word": "world", "start": 1.3, "end": 1.6},
                        ],
                    },
                    {"start": 3.0, "end": 4.0, "text": "fallback segment"},
                ]
            }
        ),
        encoding="utf-8",
    )

    loaded = module.load_localization_transcript(payload_path)
    tokens = loaded["tokens"]

    assert loaded["schemaVersion"] == "yasi.localization-transcript.v1"
    assert [item["text"] for item in tokens[:2]] == ["hello", "world"]
    assert tokens[0]["normalized"] == "hello"
    assert tokens[0]["sourceIndex"] == 0
    assert tokens[1]["start"] == 1.3


def test_generate_whisper_localization_uses_local_tool_paths_and_logs(monkeypatch):
    module = _load_alignment_script()
    run_dir = _test_run_dir("whisper-localization")
    work_dir = run_dir / "work"
    audio = run_dir / "section-01.mp3"
    whisper = run_dir / "whisper.exe"
    audio.write_bytes(b"fake mp3")
    whisper.write_text("fake executable", encoding="utf-8")
    output = work_dir / "localization" / "section-01.localization.json"
    args = module.build_parser().parse_args(
        [
            "--section",
            "1",
            "--localizer",
            "whisper",
            "--whisper",
            str(whisper),
            "--localization-output",
            str(output),
            "--overwrite",
        ]
    )
    calls = []

    def fake_run(cmd: list[str], **_kwargs):
        calls.append(cmd)
        output_dir = Path(cmd[cmd.index("--output_dir") + 1])
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "section-01.json").write_text(
            json.dumps({"segments": [{"words": [{"word": "hello", "start": 0.5, "end": 0.8}]}]}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, stdout="whisper ok", stderr="whisper warn")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    normalized = module.generate_whisper_localization(args, audio, work_dir, 1)

    assert calls[0][:2] == [str(whisper), str(audio)]
    assert calls[0][calls[0].index("--model") + 1] == "medium"
    assert calls[0][calls[0].index("--language") + 1] == "en"
    assert calls[0][calls[0].index("--word_timestamps") + 1] == "True"
    assert normalized["engine"] == "whisper"
    assert output.exists()
    assert (work_dir / "localization" / "section-01.whisper.stdout.log").read_text(encoding="utf-8") == "whisper ok"
    assert (work_dir / "localization" / "section-01.whisper.stderr.log").read_text(encoding="utf-8") == "whisper warn"


def test_missing_localizer_executable_fails_before_worker_run():
    module = _load_alignment_script()
    run_dir = _test_run_dir("missing-localizer")
    args = module.build_parser().parse_args(
        [
            "--section",
            "1",
            "--localizer",
            "whisper",
            "--whisper",
            str(run_dir / "missing-whisper.exe"),
        ]
    )

    with pytest.raises(module.LocalizationError, match="Whisper"):
        module.generate_or_load_localization(args, run_dir / "section-01.mp3", run_dir / "work", 1)


def test_locate_content_start_fuzzy_match_and_manual_override():
    module = _load_alignment_script()
    official = module.official_tokens({"segments": [{"order": 1, "text": "hello welcome to the tour"}]})
    localization = module.localization_tokens_from_payload(
        _localization_payload(
            ["example", "instructions", "now", "listen", "hello", "welcome", "to", "the", "tour"],
            start=10.0,
            step=8.075,
        )
    )

    evidence = module.locate_content_start(official, localization, min_score=0.82)
    manual = module.locate_content_start(official, localization, min_score=0.82, manual_seconds=42.3)

    assert evidence["source"] == "fuzzy"
    assert evidence["rawContentStartSeconds"] == 42.3
    assert evidence["contentStartSeconds"] == 41.8
    assert evidence["score"] >= 0.82
    assert evidence["matchedOfficialTokenRange"] == [0, 5]
    assert manual == {"source": "manual", "contentStartSeconds": 42.3, "score": 1.0}


def test_locate_content_start_rejects_low_score():
    module = _load_alignment_script()
    official = module.official_tokens({"segments": [{"order": 1, "text": "hello welcome to the tour"}]})
    localization = module.localization_tokens_from_payload(_localization_payload(["alpha", "bravo", "charlie", "delta", "echo"], start=1.0))

    with pytest.raises(module.LocalizationError, match="score"):
        module.locate_content_start(official, localization, min_score=0.82)


def test_build_coarse_token_time_map_ignores_instruction_tokens():
    module = _load_alignment_script()
    text = "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima"
    official = module.official_tokens({"segments": [{"order": 1, "text": text}]})
    localization = module.localization_tokens_from_payload(
        _localization_payload(["instructions", "before", *text.split()], start=20.0, step=4.0)
    )

    anchors, diagnostics = module.build_coarse_token_time_map(official, localization, content_start_seconds=28.0)

    assert anchors[0] == {"officialTokenIndex": 0, "time": 28.0, "localizationTokenIndex": 2}
    assert anchors[-1]["officialTokenIndex"] == 11
    assert diagnostics["ignoredLocalizationTokenCount"] == 2
    assert diagnostics["anchorCount"] == 12


def test_build_coarse_token_time_map_rejects_clustered_anchor_coverage():
    module = _load_alignment_script()
    words = [f"word{index}" for index in range(20)]
    official = module.official_tokens({"segments": [{"order": 1, "text": " ".join(words)}]})
    localization = module.localization_tokens_from_payload(_localization_payload(words[:10], start=1.0, step=1.0))

    with pytest.raises(module.LocalizationError, match="coverage"):
        module.build_coarse_token_time_map(official, localization, content_start_seconds=1.0)


def test_build_coarse_token_time_map_rejects_middle_anchor_gap():
    module = _load_alignment_script()
    words = [f"word{index}" for index in range(30)]
    official = module.official_tokens({"segments": [{"order": 1, "text": " ".join(words)}]})
    localization_words = [*words[:12], *words[18:]]
    localization = module.localization_tokens_from_payload(_localization_payload(localization_words, start=1.0, step=1.0))

    with pytest.raises(module.LocalizationError, match="coverage"):
        module.build_coarse_token_time_map(official, localization, content_start_seconds=1.0)


def test_localized_slice_plan_records_stale_artifact_metadata_and_rejects_wrong_source_audio():
    module = _load_alignment_script()
    run_dir = _test_run_dir("localized-plan-metadata")
    audio = run_dir / "section-01.mp3"
    transcript = run_dir / "transcript.json"
    audio.write_bytes(b"fake mp3")
    transcript.write_text("transcript-hash-input\n", encoding="utf-8")
    words = "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima".split()
    args = module.build_parser().parse_args(
        [
            "--section",
            "1",
            "--localizer",
            "existing",
            "--localization-input",
            str(run_dir / "section-01.localization.json"),
            "--content-start-seconds",
            "0",
            "--slice-seconds",
            "100",
            "--slice-overlap-seconds",
            "3",
            "--text-overlap-tokens",
            "2",
        ]
    )
    payload = _localization_payload(words, start=0.0, step=10.0)

    plan, _slices = module.build_localized_slice_plan(
        args,
        audio=audio,
        work_dir=run_dir / "work",
        section=1,
        duration=260.0,
        section_payload={"segments": [{"order": 1, "text": " ".join(words)}]},
        transcript=transcript,
        localization_payload=payload,
        localization_artifact=run_dir / "section-01.localization.json",
        write_plan=False,
    )

    assert plan["sourceAudio"] == str(audio)
    assert plan["sourceAudioDurationSeconds"] == 260.0
    assert plan["transcriptHash"] == module.file_sha256(transcript)
    assert plan["cliParameters"]["sliceSeconds"] == 100.0
    assert plan["planHash"]

    enriched = module.enrich_localization_payload(payload, audio=audio, duration=260.0, transcript=transcript, args=args, plan_hash=plan["planHash"])
    assert enriched["sourceAudio"] == str(audio)
    assert enriched["sourceAudioDurationSeconds"] == 260.0
    assert enriched["officialTranscript"] == str(transcript)
    assert enriched["transcriptHash"] == module.file_sha256(transcript)
    assert enriched["cliParameters"]["textOverlapTokens"] == 2
    assert enriched["planHash"] == plan["planHash"]

    stale_payload = {**payload, "sourceAudio": str(run_dir / "section-02.mp3")}
    with pytest.raises(module.LocalizationError, match="sourceAudio"):
        module.build_localized_slice_plan(
            args,
            audio=audio,
            work_dir=run_dir / "work",
            section=1,
            duration=260.0,
            section_payload={"segments": [{"order": 1, "text": " ".join(words)}]},
            transcript=transcript,
            localization_payload=stale_payload,
            localization_artifact=run_dir / "section-01.localization.json",
            write_plan=False,
        )

    stale_same_basename = {**payload, "sourceAudio": str(run_dir / "other-pack" / "section-01.mp3")}
    with pytest.raises(module.LocalizationError, match="sourceAudio"):
        module.build_localized_slice_plan(
            args,
            audio=audio,
            work_dir=run_dir / "work",
            section=1,
            duration=260.0,
            section_payload={"segments": [{"order": 1, "text": " ".join(words)}]},
            transcript=transcript,
            localization_payload=stale_same_basename,
            localization_artifact=run_dir / "section-01.localization.json",
            write_plan=False,
        )


def test_dry_run_generates_localized_slice_plan_with_official_token_ranges(monkeypatch):
    module = _load_alignment_script()
    run_dir = _test_run_dir("dry-run-localized")
    pack_root = run_dir / "pack"
    audio = pack_root / "assets" / "audio" / "section-01.mp3"
    audio.parent.mkdir(parents=True, exist_ok=True)
    audio.write_bytes(b"fake mp3")
    official_words = "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima".split()
    localization_path = run_dir / "section-01.localization.json"
    localization_path.write_text(json.dumps(_localization_payload(official_words, start=42.3, step=18.0)), encoding="utf-8")
    args = module.build_parser().parse_args(
        [
            "--section",
            "1",
            "--dry-run",
            "--pack-root",
            str(pack_root),
            "--localize-content-start",
            "--localizer",
            "existing",
            "--localization-input",
            str(localization_path),
            "--content-start-seconds",
            "42.3",
            "--slice-seconds",
            "100",
            "--slice-overlap-seconds",
            "3",
            "--text-overlap-tokens",
            "2",
        ]
    )
    monkeypatch.setattr(module, "probe_audio_duration", lambda _args, _audio: 260.0)

    plan = module.dry_run_plan(
        args,
        {1: {"segments": [{"order": 1, "text": " ".join(official_words)}]}},
        pack_root,
        run_dir / "transcript.json",
        run_dir / "work",
    )

    section = plan["plannedSections"][0]
    slices = section["slicing"]["slices"]
    assert section["localization"]["contentStartSeconds"] == 42.3
    assert section["localization"]["score"] == 1.0
    assert section["slicing"]["required"] is True
    assert all(item["audioEnd"] - item["audioStart"] <= 106 for item in slices)
    assert all(item["officialTokenEnd"] > item["officialTokenStart"] for item in slices)
    assert slices[0]["audioStart"] == 42.3
    assert slices[0]["textPreview"].startswith("alpha bravo")
    assert "--text-file" in slices[0]["directAlignCommand"]
    assert Path(slices[0]["officialText"]).name == "section-01.slice-001.official.txt"


def test_materialize_localized_slice_writes_audio_command_and_official_text(monkeypatch):
    module = _load_alignment_script()
    run_dir = _test_run_dir("materialize-localized")
    audio = run_dir / "section-01.mp3"
    audio.write_bytes(b"fake mp3")
    args = module.build_parser().parse_args(["--section", "1", "--overwrite", "--ffmpeg", "ffmpeg.exe"])
    official = module.official_tokens({"segments": [{"order": 1, "text": "alpha bravo charlie delta"}]})
    localized_slice = module.LocalizedSlice(
        index=1,
        audio_start=42.3,
        audio_end=90.3,
        official_token_start=1,
        official_token_end=3,
        audio=run_dir / "work" / "slices" / "section-01.slice-001.wav",
        text_path=run_dir / "work" / "slices" / "section-01.slice-001.official.txt",
        basename="section-01.slice-001",
        text_preview="bravo charlie",
    )
    calls = []

    def fake_run(cmd: list[str], **_kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    module.materialize_localized_slice(args, audio, localized_slice, official, plan_hash="hash-1")

    assert calls[0] == [
        "ffmpeg.exe",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-ss",
        "42.300",
        "-t",
        "48.000",
        "-i",
        str(audio),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(localized_slice.audio),
    ]
    assert localized_slice.text_path.read_text(encoding="utf-8") == "bravo charlie\n"


def test_run_direct_align_localized_slices_use_slice_text_and_dedupe_overlap(monkeypatch):
    module = _load_alignment_script()
    run_dir = _test_run_dir("run-localized")
    work_dir = run_dir / "work"
    audio = run_dir / "section-01.mp3"
    audio.write_bytes(b"fake mp3")
    official_words = "alpha bravo charlie delta echo foxtrot golf hotel".split()
    localization_path = run_dir / "section-01.localization.json"
    localization_path.write_text(json.dumps(_localization_payload(official_words, start=42.0, step=30.0)), encoding="utf-8")
    args = module.build_parser().parse_args(
        [
            "--section",
            "1",
            "--overwrite",
            "--localize-content-start",
            "--localizer",
            "existing",
            "--localization-input",
            str(localization_path),
            "--content-start-seconds",
            "42.0",
            "--slice-seconds",
            "120",
            "--slice-overlap-seconds",
            "5",
            "--text-overlap-tokens",
            "1",
        ]
    )
    calls = []
    monkeypatch.setattr(module, "probe_audio_duration", lambda _args, _audio: 260.0)
    monkeypatch.setattr(module, "materialize_localized_slice", lambda *_args, **_kwargs: None)

    def fake_run_wrapper(cmd: list[str], **kwargs):
        calls.append((cmd, kwargs))
        qwen_json = Path(cmd[cmd.index("--output-json") + 1])
        text_file = Path(cmd[cmd.index("--text-file") + 1])
        words = text_file.read_text(encoding="utf-8").split()
        qwen_json.parent.mkdir(parents=True, exist_ok=True)
        qwen_json.write_text(
            json.dumps(
                {
                    "language": "English",
                    "text": " ".join(words),
                    "timestamps": [
                        {"text": word, "start_time": 1.0 + index, "end_time": 1.4 + index}
                        for index, word in enumerate(words)
                    ],
                    "segments": [],
                    "audio_path": cmd[cmd.index("--input") + 1],
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, stdout="{}", stderr="")

    monkeypatch.setattr(module, "run_wrapper", fake_run_wrapper)

    completed, qwen_json = module.run_direct_align(
        args,
        audio,
        work_dir,
        1,
        {"segments": [{"order": 1, "text": " ".join(official_words)}]},
    )

    payload = json.loads(qwen_json.read_text(encoding="utf-8"))
    text_files = [Path(call[0][call[0].index("--text-file") + 1]) for call in calls]
    assert completed.returncode == 0
    assert len(calls) >= 2
    assert all(path.name.endswith(".official.txt") for path in text_files)
    assert any(path.read_text(encoding="utf-8") != " ".join(official_words) + "\n" for path in text_files)
    assert payload["config"]["source"] == "localized-transcript-slices"
    assert payload["localization"]["contentStartSeconds"] == 42.0
    assert len({item["officialTokenIndex"] for item in payload["timestamps"]}) == len(payload["timestamps"])
    assert payload["timestamps"][0]["start_time"] == 43.0
    assert {"sliceIndex", "sliceAudioStart", "officialTokenStart", "officialTokenEnd", "sliceQwenJson"}.issubset(payload["timestamps"][0])


def test_run_direct_align_rejects_stale_localization_input_before_worker(monkeypatch):
    module = _load_alignment_script()
    run_dir = _test_run_dir("run-stale-localization")
    work_dir = run_dir / "work"
    audio = run_dir / "section-01.mp3"
    audio.write_bytes(b"fake mp3")
    official_words = "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima".split()
    localization_path = run_dir / "section-01.localization.json"
    stale_payload = _localization_payload(official_words, start=0.0, step=10.0)
    stale_payload["sourceAudio"] = str(run_dir / "other-pack" / "section-01.mp3")
    localization_path.write_text(json.dumps(stale_payload), encoding="utf-8")
    args = module.build_parser().parse_args(
        [
            "--section",
            "1",
            "--overwrite",
            "--localize-content-start",
            "--localizer",
            "existing",
            "--localization-input",
            str(localization_path),
            "--content-start-seconds",
            "0",
        ]
    )
    monkeypatch.setattr(module, "probe_audio_duration", lambda _args, _audio: 260.0)
    monkeypatch.setattr(module, "materialize_localized_slice", lambda *_args, **_kwargs: pytest.fail("worker materialization should not run"))
    monkeypatch.setattr(module, "run_wrapper", lambda *_args, **_kwargs: pytest.fail("Qwen worker should not run"))

    with pytest.raises(module.LocalizationError, match="sourceAudio"):
        module.run_direct_align(
            args,
            audio,
            work_dir,
            1,
            {"segments": [{"order": 1, "text": " ".join(official_words)}]},
        )


def test_direct_align_command_uses_worker_and_official_text_path():
    module = _load_alignment_script()
    args = module.build_parser().parse_args(
        [
            "--section",
            "1",
            "--qwen-device-map",
            "cuda:0",
            "--qwen-dtype",
            "float16",
        ]
    )

    cmd, qwen_json, text_path = module.build_direct_align_command(args, Path("section-01.mp3"), Path("work"), 1)

    assert qwen_json == Path("work") / "section-01.qwen.json"
    assert text_path == Path("work") / "section-01.official.txt"
    assert cmd[0] == str(Path(args.qwen_python))
    assert cmd[1] == str(Path(args.direct_align_worker))
    assert cmd[cmd.index("--input") + 1] == "section-01.mp3"
    assert cmd[cmd.index("--text-file") + 1] == str(text_path)
    assert cmd[cmd.index("--output-json") + 1] == str(qwen_json)
    assert cmd[cmd.index("--dtype") + 1] == "float16"


def test_launcher_forces_utf8_child_environment():
    module = _load_skill_script("launch_alignment_job.py", "test_launch_alignment_job_module")

    env = module.child_environment()
    command = module.command_for(Path("python.exe"), Path("align_transcript.py"), ["--section", "1"])

    assert env["PYTHONUTF8"] == "1"
    assert env["PYTHONIOENCODING"] == "utf-8"
    assert command == ["python.exe", "align_transcript.py", "--section", "1"]


def test_monitor_snapshot_reports_logs_gpu_and_artifacts(monkeypatch):
    module = _load_skill_script("monitor_alignment_job.py", "test_monitor_alignment_job_module")
    run_dir = _test_run_dir("monitor-snapshot")
    job_path = run_dir / "job.json"
    stdout = run_dir / "stdout.log"
    stderr = run_dir / "stderr.log"
    work_dir = run_dir / "work"
    pack_root = run_dir / "pack"
    qwen_json = work_dir / "section-01.qwen.json"
    qwen_json.parent.mkdir(parents=True, exist_ok=True)
    qwen_json.write_text("{}", encoding="utf-8")
    localization_json = work_dir / "localization" / "section-01.localization.json"
    localization_json.parent.mkdir(parents=True, exist_ok=True)
    localization_json.write_text("{}", encoding="utf-8")
    slice_plan_json = work_dir / "plans" / "section-01.localized-slices.json"
    slice_plan_json.parent.mkdir(parents=True, exist_ok=True)
    slice_plan_json.write_text("{}", encoding="utf-8")
    slice_qwen_json = work_dir / "slices" / "section-01.slice-001.qwen.json"
    slice_qwen_json.parent.mkdir(parents=True, exist_ok=True)
    slice_qwen_json.write_text("{}", encoding="utf-8")
    slice_log = work_dir / "slices" / "section-01.slice-001.direct-align.wrapper.log.json"
    slice_log.write_text("{}", encoding="utf-8")
    failed_slice_log = work_dir / "slices" / "section-01.slice-002.direct-align.wrapper.log.json"
    failed_slice_log.write_text('{"status":"timeout"}', encoding="utf-8")
    direct_stderr = work_dir / "section-01.direct-align.wrapper.stderr.log"
    direct_stderr.write_text("load-aligner\n", encoding="utf-8")
    stdout.write_text("section 1 ok\n", encoding="utf-8")
    stderr.write_text("warning line\n", encoding="utf-8")
    job_path.write_text(
        json.dumps(
            {
                "jobId": "job-1",
                "pid": None,
                "createdAt": "2026-06-18T00:00:00Z",
                "command": ["python.exe", "align_transcript.py", "--section", "1"],
                "alignArgs": ["--section", "1"],
                "sections": [1],
                "stdout": str(stdout),
                "stderr": str(stderr),
            }
        ),
        encoding="utf-8",
    )
    args = module.build_parser().parse_args(
        [
            str(job_path),
            "--work-dir",
            str(work_dir),
            "--pack-root",
            str(pack_root),
            "--tail-chars",
            "100",
        ]
    )

    def fake_run(cmd: list[str], **_kwargs):
        if "--query-gpu=memory.free,memory.used,utilization.gpu" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="7000, 1000, 12\n", stderr="")
        if "--query-compute-apps=pid,process_name,used_memory" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="1234, python.exe, 2048\n", stderr="")
        raise AssertionError(cmd)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    snapshot = module.snapshot(job_path, args)

    assert snapshot["alive"] is False
    assert snapshot["status"] == "exited"
    assert snapshot["elapsedSeconds"] is not None
    assert snapshot["stdoutPath"] == str(stdout)
    assert snapshot["stderrPath"] == str(stderr)
    assert snapshot["stdoutTail"] == "section 1 ok\n"
    assert snapshot["stderrTail"] == "warning line\n"
    assert snapshot["gpu"]["gpus"] == [{"freeMiB": "7000", "usedMiB": "1000", "utilizationPercent": "12"}]
    assert snapshot["gpu"]["computeApps"] == [
        {"pid": "1234", "process": "python.exe", "usedMemoryMiB": "2048", "inJobProcessTree": False}
    ]
    assert snapshot["sections"][0]["qwenJson"]["exists"] is True
    assert snapshot["sections"][0]["localizationJson"]["exists"] is True
    assert snapshot["sections"][0]["localizedSlicePlan"]["exists"] is True
    assert snapshot["sections"][0]["sliceArtifacts"][0]["qwenJson"]["exists"] is True
    assert snapshot["sections"][0]["sliceArtifacts"][0]["directAlignLog"]["exists"] is True
    assert snapshot["sections"][0]["sliceArtifacts"][1]["qwenJson"]["exists"] is False
    assert snapshot["sections"][0]["sliceArtifacts"][1]["directAlignLog"]["exists"] is True
    assert snapshot["sections"][0]["directAlignStderr"]["tail"] == "load-aligner\n"


def test_monitor_process_tree_follows_windows_descendants(monkeypatch):
    module = _load_skill_script("monitor_alignment_job.py", "test_monitor_alignment_job_tree_module")
    monkeypatch.setattr(
        module,
        "windows_process_table",
        lambda: [
            {"pid": 10, "parentPid": 1, "name": "python.exe", "commandLine": "align", "known": True},
            {"pid": 20, "parentPid": 10, "name": "python.exe", "commandLine": "qwen", "known": True},
            {"pid": 30, "parentPid": 999, "name": "other.exe", "commandLine": "other", "known": True},
        ],
    )
    monkeypatch.setattr(module.os, "name", "nt")

    tree = module.process_tree(10)

    assert [item["pid"] for item in tree] == [10, 20]


def test_monitor_nvidia_snapshot_marks_job_tree_process(monkeypatch):
    module = _load_skill_script("monitor_alignment_job.py", "test_monitor_alignment_job_gpu_module")

    def fake_run(cmd: list[str], **_kwargs):
        if "--query-gpu=memory.free,memory.used,utilization.gpu" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="7000, 1000, 12\n", stderr="")
        if "--query-compute-apps=pid,process_name,used_memory" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="20, python.exe, 2048\n30, other.exe, 128\n", stderr="")
        raise AssertionError(cmd)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    snapshot = module.nvidia_snapshot({10, 20})

    assert snapshot["computeApps"] == [
        {"pid": "20", "process": "python.exe", "usedMemoryMiB": "2048", "inJobProcessTree": True},
        {"pid": "30", "process": "other.exe", "usedMemoryMiB": "128", "inJobProcessTree": False},
    ]


def test_monitor_windows_pid_alive_uses_powershell_state(monkeypatch):
    module = _load_skill_script("monitor_alignment_job.py", "test_monitor_alignment_job_pid_module")
    calls = []

    def fake_run(cmd: list[str], **_kwargs):
        calls.append(cmd)
        assert cmd[:3] == ["powershell", "-NoProfile", "-Command"]
        return subprocess.CompletedProcess(cmd, 0, stdout="running\n", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module.windows_pid_alive(7856) is True
    assert len(calls) == 1


def test_run_direct_align_writes_official_text_and_uses_runner(monkeypatch):
    module = _load_alignment_script()
    run_dir = _test_run_dir("direct-align")
    work_dir = run_dir / "work"
    audio = run_dir / "section-01.mp3"
    audio.write_bytes(b"fake mp3")
    args = module.build_parser().parse_args(
        [
            "--section",
            "1",
            "--overwrite",
        ]
    )
    calls = []

    def fake_run_wrapper(cmd: list[str], **kwargs):
        calls.append((cmd, kwargs))
        qwen_json = Path(cmd[cmd.index("--output-json") + 1])
        qwen_json.parent.mkdir(parents=True, exist_ok=True)
        qwen_json.write_text(
            json.dumps({"language": "English", "text": "hello world", "timestamps": [], "segments": []}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, stdout="{}", stderr="")

    monkeypatch.setattr(module, "run_wrapper", fake_run_wrapper)
    monkeypatch.setattr(module, "probe_audio_duration", lambda _args, _audio: 120.0)

    completed, qwen_json = module.run_direct_align(
        args,
        audio,
        work_dir,
        1,
        {"segments": [{"order": 1, "text": "hello"}, {"order": 2, "text": "world"}]},
    )

    assert completed.returncode == 0
    assert qwen_json.exists()
    assert (work_dir / "section-01.official.txt").read_text(encoding="utf-8") == "hello world\n"
    assert calls[0][1]["log_path"] == work_dir / "section-01.direct-align.wrapper.log.json"


def test_run_wrapper_timeout_writes_diagnostic_log():
    module = _load_alignment_script()
    log_path = _test_run_dir("wrapper-timeout") / "wrapper.log.json"

    with pytest.raises(subprocess.TimeoutExpired):
        module.run_wrapper(
            [sys.executable, "-c", "import time; time.sleep(5)"],
            log_path=log_path,
            timeout_seconds=0.2,
        )

    payload = json.loads(log_path.read_text(encoding="utf-8"))
    assert payload["status"] == "timeout"
    assert payload["timeoutSeconds"] == 0.2
    assert payload["command"][0] == sys.executable


def test_gpu_preflight_rejects_low_free_memory(monkeypatch):
    module = _load_alignment_script()
    args = module.build_parser().parse_args(["--section", "1", "--min-free-gpu-memory-mib", "6000"])

    def fake_run(cmd: list[str], **_kwargs):
        assert cmd[:2] == ["nvidia-smi", "--query-gpu=memory.free"]
        return subprocess.CompletedProcess(cmd, 0, stdout="2048\n", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="Insufficient free GPU memory"):
        module.check_gpu_preflight(args)


def test_dry_run_reports_direct_align_only():
    module = _load_alignment_script()
    run_dir = _test_run_dir("dry-run-direct")
    pack_root = run_dir / "pack"
    audio = pack_root / "assets" / "audio" / "section-01.mp3"
    audio.parent.mkdir(parents=True, exist_ok=True)
    audio.write_bytes(b"fake mp3")
    args = module.build_parser().parse_args(
        [
            "--section",
            "1",
            "--dry-run",
            "--pack-root",
            str(pack_root),
        ]
    )
    module.probe_audio_duration = lambda _args, _audio: 120.0

    plan = module.dry_run_plan(args, {1: {"segments": [{"order": 1, "text": "hello world"}]}}, pack_root, run_dir / "transcript.json", run_dir / "work")

    section = plan["plannedSections"][0]
    assert "directAlignCommand" in section
    assert section["directAlignCommand"] is not None
    assert section["audioDurationSeconds"] == 120.0
    assert section["slicing"]["required"] is False
    assert "wrapperCommand" not in section
    assert plan["directAlignWorkerExists"] is True
    assert "qwenWrapperExists" not in plan


def test_dry_run_plans_three_minute_audio_slices_for_long_input(monkeypatch):
    module = _load_alignment_script()
    run_dir = _test_run_dir("dry-run-slices")
    pack_root = run_dir / "pack"
    audio = pack_root / "assets" / "audio" / "section-01.mp3"
    audio.parent.mkdir(parents=True, exist_ok=True)
    audio.write_bytes(b"fake mp3")
    words = "hello world again today".split()
    localization_path = run_dir / "section-01.localization.json"
    localization_path.write_text(json.dumps(_localization_payload(words, start=0.0, step=100.0)), encoding="utf-8")
    args = module.build_parser().parse_args(
        [
            "--section",
            "1",
            "--dry-run",
            "--pack-root",
            str(pack_root),
            "--localizer",
            "existing",
            "--localization-input",
            str(localization_path),
            "--content-start-seconds",
            "0",
        ]
    )
    monkeypatch.setattr(module, "probe_audio_duration", lambda _args, _audio: 361.25)

    plan = module.dry_run_plan(
        args,
        {1: {"segments": [{"order": 1, "text": " ".join(words)}]}},
        pack_root,
        run_dir / "transcript.json",
        run_dir / "work",
    )

    section = plan["plannedSections"][0]
    assert section["audioDurationSeconds"] == 361.25
    assert section["slicing"]["required"] is True
    assert section["slicing"]["thresholdSeconds"] == 180.0
    assert section["slicing"]["sliceSeconds"] == 180.0
    assert [(item["audioStart"], item["audioEnd"]) for item in section["slicing"]["slices"]] == [
        (0.0, 183.0),
        (177.0, 361.25),
        (357.0, 361.25),
    ]
    assert all("officialTokenStart" in item for item in section["slicing"]["slices"])
    assert section["directAlignCommand"] is None
    assert [Path(item["audio"]).suffix for item in section["slicing"]["slices"]] == [".wav", ".wav", ".wav"]


def test_probe_audio_duration_uses_configured_ffprobe(monkeypatch):
    module = _load_alignment_script()
    args = module.build_parser().parse_args(["--section", "1", "--ffprobe", "custom-ffprobe.exe"])
    calls = []

    def fake_run(cmd: list[str], **_kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="181.75\n", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module.probe_audio_duration(args, Path("section-01.mp3")) == 181.75
    assert calls[0][0] == "custom-ffprobe.exe"
    assert calls[0][-1] == "section-01.mp3"


def test_plain_slice_merge_offsets_timestamps(monkeypatch):
    module = _load_alignment_script()
    run_dir = _test_run_dir("plain-slice-merge")
    work_dir = run_dir / "work"
    audio = run_dir / "section-01.mp3"
    audio.write_bytes(b"fake mp3")
    args = module.build_parser().parse_args(["--section", "1", "--overwrite"])
    slices = [
        module.AudioSlice(index=1, start=0.0, end=180.0, audio=work_dir / "slices" / "section-01.slice-001.wav", basename="section-01.slice-001"),
        module.AudioSlice(index=2, start=180.0, end=360.0, audio=work_dir / "slices" / "section-01.slice-002.wav", basename="section-01.slice-002"),
        module.AudioSlice(index=3, start=360.0, end=361.25, audio=work_dir / "slices" / "section-01.slice-003.wav", basename="section-01.slice-003"),
    ]
    slice_jsons = []
    for audio_slice in slices:
        qwen_json = work_dir / f"{audio_slice.basename}.qwen.json"
        qwen_json.parent.mkdir(parents=True, exist_ok=True)
        qwen_json.write_text(
            json.dumps(
                {
                    "language": "English",
                    "text": "hello world",
                    "timestamps": [{"text": "hello", "start_time": 0.1, "end_time": 0.4}],
                    "segments": [],
                    "audio_path": str(audio_slice.audio),
                }
            ),
            encoding="utf-8",
        )
        slice_jsons.append(qwen_json)

    module.merge_slice_qwen_payloads(
        args,
        output_json=work_dir / "section-01.qwen.json",
        original_audio=audio,
        text="hello world",
        slices=slices,
        slice_jsons=slice_jsons,
    )

    payload = json.loads((work_dir / "section-01.qwen.json").read_text(encoding="utf-8"))
    assert [item["start_time"] for item in payload["timestamps"]] == [0.1, 180.1, 360.1]
    assert payload["config"]["source"] == "transcript-slices"
    assert len(payload["slices"]) == 3


def test_validate_rejects_verified_localized_section_without_slice_provenance():
    align_module = _load_alignment_script()
    validate_module = _load_skill_script("validate_timings.py", "test_validate_timings_localization_module")
    transcript_sections = {1: {"segments": [{"order": 1, "text": "alpha bravo"}]}}
    expected = align_module.official_tokens(transcript_sections[1])
    payload = {
        "schemaVersion": align_module.SCHEMA_VERSION,
        "status": "verified",
        "tool": {"minLocalizationScore": 0.82},
        "sections": [
            {
                "section": 1,
                "status": "verified",
                "localization": {
                    "source": "existing",
                    "score": 0.91,
                    "slicePlan": "section-01.localized-slices.json",
                    "slices": [{"index": 1, "officialTokenStart": 0, "officialTokenEnd": 2}],
                },
                "wordTimings": [
                    {
                        "section": 1,
                        "segmentOrder": token.segment_order,
                        "tokenIndex": token.token_index,
                        "globalTokenIndex": token.global_index,
                        "token": token.text,
                        "normalized": token.normalized,
                        "risks": [],
                        "start": float(index),
                        "end": float(index) + 0.25,
                        "match": "exact",
                    }
                    for index, token in enumerate(expected)
                ],
                "reviewItems": [],
                "diagnostics": {},
            }
        ],
        "reviewItems": [],
    }

    errors = validate_module.validate(
        payload,
        transcript_sections,
        require_all_sections=False,
        require_verified=True,
        require_review_trace=False,
        review_payload=None,
    )

    assert any("slice provenance" in error for error in errors)


def test_validate_rejects_low_score_and_empty_localized_slice_range():
    align_module = _load_alignment_script()
    validate_module = _load_skill_script("validate_timings.py", "test_validate_timings_low_score_module")
    transcript_sections = {1: {"segments": [{"order": 1, "text": "alpha"}]}}
    token = align_module.official_tokens(transcript_sections[1])[0]
    payload = {
        "schemaVersion": align_module.SCHEMA_VERSION,
        "status": "verified",
        "tool": {"minLocalizationScore": 0.82},
        "sections": [
            {
                "section": 1,
                "status": "verified",
                "localization": {
                    "source": "existing",
                    "score": 0.5,
                    "slicePlan": "section-01.localized-slices.json",
                    "slices": [{"index": 1, "officialTokenStart": 1, "officialTokenEnd": 1}],
                },
                "wordTimings": [
                    {
                        "section": 1,
                        "segmentOrder": token.segment_order,
                        "tokenIndex": token.token_index,
                        "globalTokenIndex": token.global_index,
                        "token": token.text,
                        "normalized": token.normalized,
                        "risks": [],
                        "start": 1.0,
                        "end": 1.2,
                        "match": "exact",
                        "sliceIndex": 1,
                        "sliceQwenJson": "section-01.slice-001.qwen.json",
                    }
                ],
                "reviewItems": [],
                "diagnostics": {},
            }
        ],
        "reviewItems": [],
    }

    errors = validate_module.validate(
        payload,
        transcript_sections,
        require_all_sections=False,
        require_verified=True,
        require_review_trace=False,
        review_payload=None,
    )

    assert any("localization score" in error for error in errors)
    assert any("empty official token range" in error for error in errors)
