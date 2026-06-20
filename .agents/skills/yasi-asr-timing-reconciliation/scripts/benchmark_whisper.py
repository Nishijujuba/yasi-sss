from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import whisper_evidence


MODEL_ORDER = ["small", "medium", "large-v3"]
PASSING_GATE = {
    "anchorCoverage": 0.95,
    "unmatchedRate": 0.02,
    "pendingReviewRate": 0.10,
    "longestUnanchoredGap": 8,
}


def validate_models(models: list[str]) -> list[str]:
    return [whisper_evidence.validate_model(model) for model in models]


def reconciliation_script() -> Path:
    return SCRIPT_DIR / "asr_timing_reconcile.py"


def require_reconciliation_script() -> Path:
    script = reconciliation_script()
    if not script.exists():
        raise FileNotFoundError(f"Reconciliation script not found: {script}")
    return script


def report_path_for(
    *,
    section: int | str,
    model: str,
    pack_id: str | None = None,
    output_root: Path | str | None = None,
) -> Path:
    return (
        whisper_evidence.output_dir_for_model(
            model,
            section=section,
            pack_id=pack_id,
            output_root=output_root,
        )
        / "reconciliation-report.json"
    )


def run_reconciliation_if_available(
    *,
    section: int | str,
    model: str,
    evidence_path: Path,
    pack_root: Path | str | None = None,
    pack_id: str | None = None,
    transcript: Path | str | None = None,
) -> None:
    script = reconciliation_script()
    if not script.exists():
        return

    command = [
        sys.executable,
        str(script),
        "--section",
        str(int(section)),
        "--model",
        model,
        "--evidence-input",
        str(evidence_path),
        "--draft",
    ]
    if pack_root is not None:
        command.extend(["--pack-root", str(pack_root)])
    if pack_id is not None:
        command.extend(["--pack-id", pack_id])
    if transcript is not None:
        command.extend(["--transcript", str(transcript)])
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    output_dir = evidence_path.parent
    (output_dir / "reconcile.stdout.log").write_text(
        completed.stdout or "", encoding="utf-8"
    )
    (output_dir / "reconcile.stderr.log").write_text(
        completed.stderr or "", encoding="utf-8"
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Reconciliation failed for model {model} with exit code {completed.returncode}"
        )


def run_benchmark(
    *,
    section: int | str,
    models: list[str],
    overwrite: bool = False,
    pack_root: Path | str | None = None,
    pack_id: str | None = None,
    source_audio: Path | str | None = None,
    transcript: Path | str | None = None,
    output_root: Path | str | None = None,
    whisper_cli: Path | str = whisper_evidence.DEFAULT_WHISPER_CLI,
    model_dir: Path | str | None = None,
) -> list[Path]:
    require_reconciliation_script()
    evidence_paths: list[Path] = []
    for model in validate_models(models):
        evidence_path = whisper_evidence.generate_evidence(
            model=model,
            section=section,
            pack_root=pack_root,
            pack_id=pack_id,
            source_audio=source_audio,
            output_root=output_root,
            whisper_cli=whisper_cli,
            model_dir=model_dir,
            overwrite=overwrite,
        )
        evidence_paths.append(evidence_path)
        run_reconciliation_if_available(
            section=section,
            model=model,
            evidence_path=evidence_path,
            pack_root=pack_root,
            pack_id=pack_id,
            transcript=transcript,
        )
    return evidence_paths


def metric_value(report: dict[str, Any], key: str) -> Any:
    metrics = report.get("metrics", {})
    if key in metrics:
        return metrics[key]
    return report.get(key)


def runtime_value(report: dict[str, Any]) -> Any:
    metrics = report.get("metrics", {})
    for key in ("runtimeSeconds", "runtime", "durationSeconds"):
        if key in metrics:
            return metrics[key]
        if key in report:
            return report[key]
    return None


def read_report(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def numeric_runtime_seconds(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    runtime_seconds = float(value)
    if not math.isfinite(runtime_seconds) or runtime_seconds < 0:
        return None
    return runtime_seconds


def passes_gate(row: dict[str, Any]) -> bool:
    if numeric_runtime_seconds(row.get("runtimeSeconds")) is None:
        return False
    try:
        return (
            float(row["anchorCoverage"]) >= PASSING_GATE["anchorCoverage"]
            and float(row["unmatchedRate"]) <= PASSING_GATE["unmatchedRate"]
            and float(row["pendingReviewRate"]) <= PASSING_GATE["pendingReviewRate"]
            and int(row["longestUnanchoredGap"])
            <= PASSING_GATE["longestUnanchoredGap"]
        )
    except (TypeError, ValueError):
        return False


def collect_comparison_rows(
    *,
    section: int | str,
    models: list[str],
    pack_id: str | None = None,
    output_root: Path | str | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for model in validate_models(models):
        path = report_path_for(section=section, model=model, pack_id=pack_id, output_root=output_root)
        report = read_report(path)
        if report is None:
            continue
        row = {
            "model": model,
            "anchorCoverage": metric_value(report, "anchorCoverage"),
            "unmatchedRate": metric_value(report, "unmatchedRate"),
            "pendingReviewRate": metric_value(report, "pendingReviewRate"),
            "longestUnanchoredGap": metric_value(report, "longestUnanchoredGap"),
            "runtimeSeconds": runtime_value(report),
            "gateOutcome": report.get("gateOutcome", ""),
            "reportPath": str(path),
        }
        rows.append(row)
    return rows


def format_cell(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def default_recommendation(rows: list[dict[str, Any]]) -> str:
    rank = {model: index for index, model in enumerate(MODEL_ORDER)}
    for row in sorted(rows, key=lambda item: rank.get(str(item["model"]), len(rank))):
        if passes_gate(row):
            return str(row["model"])
    return "none (rerun-asr)"


def print_comparison_table(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("No reconciliation reports found.")
        print("DEFAULT RECOMMENDATION: none (rerun-asr)")
        return

    headers = [
        "model",
        "anchorCoverage",
        "unmatchedRate",
        "pendingReviewRate",
        "longestUnanchoredGap",
        "runtimeSeconds",
        "gateOutcome",
    ]
    widths = {
        header: max(len(header), *(len(format_cell(row.get(header))) for row in rows))
        for header in headers
    }
    print(" | ".join(header.ljust(widths[header]) for header in headers))
    print(" | ".join("-" * widths[header] for header in headers))
    for row in rows:
        print(
            " | ".join(
                format_cell(row.get(header)).ljust(widths[header]) for header in headers
            )
        )
    print(f"DEFAULT RECOMMENDATION: {default_recommendation(rows)}")


def compare_models(
    *,
    section: int | str,
    models: list[str],
    pack_id: str | None = None,
    output_root: Path | str | None = None,
) -> list[dict[str, Any]]:
    rows = collect_comparison_rows(
        section=section,
        models=models,
        pack_id=pack_id,
        output_root=output_root,
    )
    print_comparison_table(rows)
    return rows


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark Whisper models for Yasi timing.")
    parser.add_argument("--section", type=int, default=1)
    parser.add_argument("--models", nargs="+", default=MODEL_ORDER)
    parser.add_argument("--pack-root", type=Path)
    parser.add_argument("--pack-id")
    parser.add_argument("--source-audio", type=Path)
    parser.add_argument("--transcript", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--whisper-cli", type=Path, default=whisper_evidence.DEFAULT_WHISPER_CLI)
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--compare-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    models = validate_models(args.models)
    if args.compare_only:
        compare_models(
            section=args.section,
            models=models,
            pack_id=args.pack_id,
            output_root=args.output_root,
        )
        return 0

    run_benchmark(
        section=args.section,
        models=models,
        overwrite=args.overwrite,
        pack_root=args.pack_root,
        pack_id=args.pack_id,
        source_audio=args.source_audio,
        transcript=args.transcript,
        output_root=args.output_root,
        whisper_cli=args.whisper_cli,
        model_dir=args.model_dir,
    )
    compare_models(
        section=args.section,
        models=models,
        pack_id=args.pack_id,
        output_root=args.output_root,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
