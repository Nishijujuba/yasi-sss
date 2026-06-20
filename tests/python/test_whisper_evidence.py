import importlib.util
import json
import subprocess
import uuid
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
WHISPER_EVIDENCE = (
    REPO_ROOT
    / ".agents"
    / "skills"
    / "yasi-asr-timing-reconciliation"
    / "scripts"
    / "whisper_evidence.py"
)
BENCHMARK_WHISPER = (
    REPO_ROOT
    / ".agents"
    / "skills"
    / "yasi-asr-timing-reconciliation"
    / "scripts"
    / "benchmark_whisper.py"
)
TEST_SCRATCH_ROOT = REPO_ROOT / "待删除" / "pytest-whisper-evidence"


def load_whisper_evidence():
    spec = importlib.util.spec_from_file_location("whisper_evidence", WHISPER_EVIDENCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_benchmark_whisper():
    spec = importlib.util.spec_from_file_location(
        "benchmark_whisper", BENCHMARK_WHISPER
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def option_value(command, option):
    return command[command.index(option) + 1]


def make_test_root():
    path = TEST_SCRATCH_ROOT / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=False)
    return path


def write_reconciliation_report(benchmark_whisper, output_root, *, model, metrics):
    report_path = benchmark_whisper.report_path_for(
        section=1,
        model=model,
        output_root=output_root,
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps({"metrics": metrics, "gateOutcome": "pass"}),
        encoding="utf-8",
    )
    return report_path


def passing_quality_metrics(**overrides):
    metrics = {
        "anchorCoverage": 0.99,
        "unmatchedRate": 0.01,
        "pendingReviewRate": 0.05,
        "longestUnanchoredGap": 4,
        "runtimeSeconds": 123.45,
    }
    metrics.update(overrides)
    return metrics


def test_allowed_models_and_rejects_invalid_model():
    whisper_evidence = load_whisper_evidence()

    assert whisper_evidence.ALLOWED_MODELS == {"small", "medium", "large-v3"}
    assert whisper_evidence.DEFAULT_MODEL == "small"
    assert whisper_evidence.parse_args(["--section", "1"]).model == "small"
    for model in whisper_evidence.ALLOWED_MODELS:
        assert whisper_evidence.validate_model(model) == model

    with pytest.raises(ValueError, match="Unsupported Whisper model"):
        whisper_evidence.validate_model("tiny")


def test_benchmark_comparison_requires_runtime_for_default_recommendation():
    benchmark_whisper = load_benchmark_whisper()
    output_root = make_test_root()
    metrics = passing_quality_metrics()
    metrics.pop("runtimeSeconds")
    write_reconciliation_report(
        benchmark_whisper,
        output_root,
        model="small",
        metrics=metrics,
    )

    rows = benchmark_whisper.collect_comparison_rows(
        section=1,
        models=["small"],
        output_root=output_root,
    )

    assert rows[0]["runtimeSeconds"] is None
    assert benchmark_whisper.passes_gate(rows[0]) is False
    assert benchmark_whisper.default_recommendation(rows) == "none (rerun-asr)"


def test_benchmark_comparison_requires_numeric_runtime_for_default_recommendation():
    benchmark_whisper = load_benchmark_whisper()
    output_root = make_test_root()
    write_reconciliation_report(
        benchmark_whisper,
        output_root,
        model="small",
        metrics=passing_quality_metrics(runtimeSeconds="fast"),
    )

    rows = benchmark_whisper.collect_comparison_rows(
        section=1,
        models=["small"],
        output_root=output_root,
    )

    assert rows[0]["runtimeSeconds"] == "fast"
    assert benchmark_whisper.passes_gate(rows[0]) is False
    assert benchmark_whisper.default_recommendation(rows) == "none (rerun-asr)"


def test_benchmark_comparison_rejects_string_runtime_for_default_recommendation():
    benchmark_whisper = load_benchmark_whisper()
    output_root = make_test_root()
    write_reconciliation_report(
        benchmark_whisper,
        output_root,
        model="small",
        metrics=passing_quality_metrics(runtimeSeconds="123.45"),
    )

    rows = benchmark_whisper.collect_comparison_rows(
        section=1,
        models=["small"],
        output_root=output_root,
    )

    assert rows[0]["runtimeSeconds"] == "123.45"
    assert benchmark_whisper.passes_gate(rows[0]) is False
    assert benchmark_whisper.default_recommendation(rows) == "none (rerun-asr)"


def test_full_benchmark_fails_before_asr_when_reconciliation_script_is_missing(
    monkeypatch,
):
    benchmark_whisper = load_benchmark_whisper()
    output_root = make_test_root()
    missing_script = output_root / "missing-reconcile.py"
    called = {"generate_evidence": False}

    def fake_generate_evidence(**kwargs):
        called["generate_evidence"] = True
        return output_root / "section-01" / "small" / "asr-timing-evidence.json"

    monkeypatch.setattr(
        benchmark_whisper.whisper_evidence,
        "generate_evidence",
        fake_generate_evidence,
    )
    monkeypatch.setattr(
        benchmark_whisper,
        "reconciliation_script",
        lambda: missing_script,
    )

    with pytest.raises(FileNotFoundError, match="Reconciliation script not found"):
        benchmark_whisper.run_benchmark(
            section=1,
            models=["small"],
            output_root=output_root,
        )

    assert called["generate_evidence"] is False


def test_generate_evidence_builds_whisper_command_and_normalizes_json(monkeypatch):
    whisper_evidence = load_whisper_evidence()
    test_root = make_test_root()
    home = test_root / "home"
    source_audio = test_root / "section-01.mp3"
    output_root = test_root / "runs"
    whisper_cli = test_root / "whisper.exe"
    source_audio.write_bytes(b"fake audio")
    monkeypatch.setenv("USERPROFILE", str(home))

    captured = {}

    def fake_run(command, capture_output, text, check, env):
        captured["command"] = command
        captured["env"] = env
        assert capture_output is True
        assert text is True
        assert check is False

        output_dir = Path(option_value(command, "--output_dir"))
        output_dir.mkdir(parents=True, exist_ok=True)
        whisper_payload = {
            "segments": [
                {
                    "words": [
                        {"word": " Hello,", "start": 0.5, "end": 0.9},
                        {"word": "WORLD!", "start": 0.9, "end": 1.2},
                    ]
                }
            ]
        }
        (output_dir / "section-01.json").write_text(
            json.dumps(whisper_payload), encoding="utf-8"
        )
        return subprocess.CompletedProcess(
            command, 0, stdout="whisper stdout", stderr="whisper stderr"
        )

    monkeypatch.setattr(whisper_evidence.subprocess, "run", fake_run)

    evidence_path = whisper_evidence.generate_evidence(
        source_audio=source_audio,
        model="small",
        output_root=output_root,
        whisper_cli=whisper_cli,
        generated_at="2026-06-18T00:00:00Z",
    )

    expected_output_dir = output_root / "section-01" / "small"
    command = captured["command"]
    assert captured["env"]["PYTHONUTF8"] == "1"
    assert command[0] == str(whisper_cli)
    assert command[1] == str(source_audio)
    assert option_value(command, "--model") == "small"
    assert option_value(command, "--model_dir") == str(home / ".cache" / "whisper")
    assert option_value(command, "--output_format") == "json"
    assert option_value(command, "--word_timestamps") == "True"
    assert Path(option_value(command, "--output_dir")) == expected_output_dir

    assert (expected_output_dir / "whisper.stdout.log").read_text(
        encoding="utf-8"
    ) == "whisper stdout"
    assert (expected_output_dir / "whisper.stderr.log").read_text(
        encoding="utf-8"
    ) == "whisper stderr"

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["schemaVersion"] == "yasi.asr-timing-evidence.v1"
    assert evidence["engine"] == "whisper"
    assert evidence["model"] == "small"
    assert evidence["command"] == command
    assert evidence["sourceAudio"] == str(source_audio)
    assert evidence["generatedAt"] == "2026-06-18T00:00:00Z"
    assert isinstance(evidence["metrics"]["runtimeSeconds"], float)
    assert evidence["metrics"]["runtimeSeconds"] >= 0
    assert evidence["words"] == [
        {
            "index": 0,
            "word": "Hello,",
            "normalized": "hello",
            "start": 0.5,
            "end": 0.9,
        },
        {
            "index": 1,
            "word": "WORLD!",
            "normalized": "world",
            "start": 0.9,
            "end": 1.2,
        },
    ]


def test_generate_evidence_can_resolve_source_audio_from_pack_root(monkeypatch):
    whisper_evidence = load_whisper_evidence()
    test_root = make_test_root()
    pack_root = test_root / "public" / "packs" / "cambridge-10" / "test-2" / "listening"
    audio_path = pack_root / "assets" / "audio" / "section-03.mp3"
    output_root = test_root / "runs"
    whisper_cli = test_root / "whisper.exe"
    audio_path.parent.mkdir(parents=True)
    audio_path.write_bytes(b"fake audio")

    captured = {}

    def fake_run(command, capture_output, text, check, env):
        captured["command"] = command
        output_dir = Path(option_value(command, "--output_dir"))
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "section-03.json").write_text(
            json.dumps({"segments": [{"words": [{"word": "Hello", "start": 1.0, "end": 1.2}]}]}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(whisper_evidence.subprocess, "run", fake_run)

    evidence_path = whisper_evidence.generate_evidence(
        model="small",
        section=3,
        pack_root=pack_root,
        pack_id="cambridge-10-test-2-listening",
        output_root=output_root,
        whisper_cli=whisper_cli,
        generated_at="2026-06-20T00:00:00Z",
    )

    assert captured["command"][1] == str(audio_path)
    assert Path(option_value(captured["command"], "--output_dir")) == (
        output_root / "cambridge-10-test-2-listening" / "section-03" / "small"
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["sourceAudio"] == str(audio_path)
