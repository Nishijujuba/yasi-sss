#!/usr/bin/env python3
"""One-shot or bounded monitoring for yasi forced-alignment background jobs."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(r"D:\Project\yasi")
DEFAULT_JOB_ROOT = PROJECT_ROOT / "待删除" / "yasi-forced-alignment" / "jobs"
DEFAULT_WORK_DIR = PROJECT_ROOT / "待删除" / "yasi-forced-alignment"
DEFAULT_PACK_ROOT = PROJECT_ROOT / "public" / "packs" / "cambridge-10" / "test-1" / "listening"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report status for a yasi forced-alignment background job without blocking Codex on model inference.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("job", nargs="?", default=None, help="Job JSON path. Omit with --latest.")
    parser.add_argument("--latest", action="store_true", help="Use the newest job JSON in --job-root.")
    parser.add_argument("--job-root", default=str(DEFAULT_JOB_ROOT), help="Directory containing job JSON files.")
    parser.add_argument("--work-dir", default=str(DEFAULT_WORK_DIR), help="Alignment work directory.")
    parser.add_argument("--pack-root", default=str(DEFAULT_PACK_ROOT), help="Listening pack root.")
    parser.add_argument("--tail-chars", type=int, default=3000, help="Characters of each log tail to include.")
    parser.add_argument("--watch", action="store_true", help="Print JSON snapshots until the process exits or --max-seconds is reached.")
    parser.add_argument("--interval", type=float, default=15.0, help="Seconds between --watch snapshots.")
    parser.add_argument("--max-seconds", type=float, default=0.0, help="Maximum watch duration. Use 0 for no watch limit.")
    return parser


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_job(job_root: Path) -> Path:
    jobs = sorted(job_root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not jobs:
        raise FileNotFoundError(f"No job JSON files under {job_root}")
    return jobs[0]


def resolve_job(args: argparse.Namespace) -> Path:
    if args.latest:
        return latest_job(Path(args.job_root))
    if not args.job:
        raise SystemExit("Pass a job path or --latest.")
    return Path(args.job)


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    if os.name == "nt":
        return windows_pid_alive(pid)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def windows_pid_alive(pid: int) -> bool:
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                f"try {{ $p=[System.Diagnostics.Process]::GetProcessById({pid}); "
                "if ($p.HasExited) { 'exited' } else { 'running' } } catch { 'missing' }"
            ),
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if completed.returncode == 0:
        state = completed.stdout.strip().lower()
        if state == "running":
            return True
        if state in {"exited", "missing"}:
            return False
    fallback = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    return fallback.returncode == 0 and str(pid) in fallback.stdout


def tail_text(path: Path, chars: int) -> str:
    if not path.exists():
        return ""
    data = path.read_text(encoding="utf-8", errors="replace")
    return data[-chars:]


def file_snapshot(path: Path, tail_chars: int = 0) -> dict[str, Any]:
    item: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
    }
    if tail_chars > 0:
        item["tail"] = tail_text(path, tail_chars)
    return item


def windows_process_table() -> list[dict[str, Any]]:
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
                "Get-CimInstance Win32_Process | "
                "Select-Object ProcessId,ParentProcessId,Name,CommandLine | "
                "ConvertTo-Json -Compress"
            ),
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        return []
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        return []
    rows = []
    for item in payload:
        if isinstance(item, dict) and item.get("ProcessId") is not None:
            rows.append(
                {
                    "pid": int(item.get("ProcessId")),
                    "parentPid": int(item.get("ParentProcessId") or 0),
                    "name": item.get("Name"),
                    "commandLine": item.get("CommandLine"),
                    "known": True,
                }
            )
    return rows


def process_tree(pid: int | None) -> list[dict[str, Any]]:
    if not pid:
        return []
    if os.name != "nt":
        return [{"pid": int(pid), "parentPid": None, "name": None, "commandLine": None, "known": False}]
    rows = windows_process_table()
    by_pid = {int(item["pid"]): item for item in rows}
    children: dict[int, list[int]] = {}
    for item in rows:
        children.setdefault(int(item.get("parentPid") or 0), []).append(int(item["pid"]))
    out = []
    stack = [int(pid)]
    seen: set[int] = set()
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        out.append(
            by_pid.get(
                current,
                {"pid": current, "parentPid": None, "name": None, "commandLine": None, "known": False},
            )
        )
        stack.extend(reversed(children.get(current, [])))
    return out


def nvidia_snapshot(job_pids: set[int] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"available": False}
    job_pids = job_pids or set()
    free = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.free,memory.used,utilization.gpu", "--format=csv,noheader,nounits"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if free.returncode == 0:
        rows = []
        for line in free.stdout.splitlines():
            parts = [part.strip() for part in line.split(",")]
            if len(parts) >= 3:
                rows.append({"freeMiB": parts[0], "usedMiB": parts[1], "utilizationPercent": parts[2]})
        result.update({"available": True, "gpus": rows})

    apps = subprocess.run(
        ["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader,nounits"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    compute = []
    if apps.returncode == 0:
        reader = csv.reader(apps.stdout.splitlines())
        for row in reader:
            if len(row) >= 3:
                pid_text = row[0].strip()
                try:
                    pid_value = int(pid_text)
                except ValueError:
                    pid_value = None
                compute.append(
                    {
                        "pid": pid_text,
                        "process": row[1].strip(),
                        "usedMemoryMiB": row[2].strip(),
                        "inJobProcessTree": bool(pid_value is not None and pid_value in job_pids),
                    }
                )
    result["computeApps"] = compute
    return result


def planned_sections(job: dict[str, Any]) -> list[int]:
    sections = job.get("sections") or []
    if sections:
        return [int(item) for item in sections]
    args = job.get("alignArgs") or []
    if "--all-sections" in args:
        return [1, 2, 3, 4]
    out = []
    for idx, value in enumerate(args):
        if value == "--section" and idx + 1 < len(args):
            out.append(int(args[idx + 1]))
    return sorted(set(out))


def section_artifacts(section: int, work_dir: Path, pack_root: Path, tail_chars: int = 0) -> dict[str, Any]:
    prefix = f"section-{section:02d}"
    qwen_json = work_dir / f"{prefix}.qwen.json"
    direct_log = work_dir / f"{prefix}.direct-align.wrapper.log.json"
    wrapper_log = work_dir / f"{prefix}.wrapper.log.json"
    slice_dir = work_dir / "slices"
    slice_stems: set[str] = set()
    for slice_qwen in slice_dir.glob(f"{prefix}.slice-*.qwen.json"):
        slice_stems.add(slice_qwen.name[: -len(".qwen.json")])
    for slice_log in slice_dir.glob(f"{prefix}.slice-*.direct-align.wrapper.log.json"):
        slice_stems.add(slice_log.name[: -len(".direct-align.wrapper.log.json")])
    for slice_stream in slice_dir.glob(f"{prefix}.slice-*.direct-align.wrapper.*.log"):
        slice_stems.add(slice_stream.name.split(".direct-align.wrapper.", 1)[0])
    slice_artifacts = []
    for stem in sorted(slice_stems):
        slice_artifacts.append(
            {
                "index": len(slice_artifacts) + 1,
                "qwenJson": file_snapshot(slice_dir / f"{stem}.qwen.json"),
                "directAlignLog": file_snapshot(slice_dir / f"{stem}.direct-align.wrapper.log.json"),
                "directAlignStdout": file_snapshot(slice_dir / f"{stem}.direct-align.wrapper.stdout.log", tail_chars),
                "directAlignStderr": file_snapshot(slice_dir / f"{stem}.direct-align.wrapper.stderr.log", tail_chars),
            }
        )
    return {
        "section": section,
        "qwenJson": file_snapshot(qwen_json),
        "localizationJson": file_snapshot(work_dir / "localization" / f"{prefix}.localization.json"),
        "localizedSlicePlan": file_snapshot(work_dir / "plans" / f"{prefix}.localized-slices.json"),
        "sliceArtifacts": slice_artifacts,
        "directAlignLog": file_snapshot(direct_log),
        "directAlignStdout": file_snapshot(work_dir / f"{prefix}.direct-align.wrapper.stdout.log", tail_chars),
        "directAlignStderr": file_snapshot(work_dir / f"{prefix}.direct-align.wrapper.stderr.log", tail_chars),
        "wrapperLog": file_snapshot(wrapper_log),
        "wrapperStdout": file_snapshot(work_dir / f"{prefix}.wrapper.stdout.log", tail_chars),
        "wrapperStderr": file_snapshot(work_dir / f"{prefix}.wrapper.stderr.log", tail_chars),
        "draftOutput": str(pack_root / "transcript-timings.draft.json"),
        "reviewOutput": str(pack_root / "alignment-review.json"),
        "finalOutput": str(pack_root / "transcript-timings.json"),
    }


def parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def elapsed_seconds(job: dict[str, Any]) -> float | None:
    started = parse_utc(job.get("startedAt") or job.get("createdAt"))
    if started is None:
        return None
    return round((datetime.now(timezone.utc) - started).total_seconds(), 1)


def snapshot(job_path: Path, args: argparse.Namespace) -> dict[str, Any]:
    job = load_json(job_path)
    pid = job.get("pid")
    alive = pid_alive(int(pid)) if pid else False
    tree = process_tree(int(pid)) if pid else []
    tree_pids = {int(item["pid"]) for item in tree if item.get("pid") is not None}
    stdout = Path(job.get("stdout", ""))
    stderr = Path(job.get("stderr", ""))
    work_dir = Path(args.work_dir)
    pack_root = Path(args.pack_root)
    process_tree_note = None
    if pid and tree and not any(item.get("known") for item in tree):
        process_tree_note = "Windows process table was not readable from this shell; GPU compute apps are still reported globally."
    return {
        "job": str(job_path),
        "jobId": job.get("jobId"),
        "pid": pid,
        "alive": alive,
        "status": "running" if alive else "exited",
        "createdAt": job.get("createdAt"),
        "startedAt": job.get("startedAt"),
        "elapsedSeconds": elapsed_seconds(job),
        "command": job.get("command"),
        "processTree": tree,
        "processTreeNote": process_tree_note,
        "sections": [section_artifacts(section, work_dir, pack_root, args.tail_chars) for section in planned_sections(job)],
        "stdoutPath": str(stdout),
        "stderrPath": str(stderr),
        "stdoutTail": tail_text(stdout, args.tail_chars),
        "stderrTail": tail_text(stderr, args.tail_chars),
        "gpu": nvidia_snapshot(tree_pids),
    }


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    job_path = resolve_job(args)
    started = time.monotonic()
    while True:
        snap = snapshot(job_path, args)
        print(json.dumps(snap, ensure_ascii=False, indent=None if args.watch else 2), flush=True)
        if not args.watch or not snap["alive"]:
            break
        if args.max_seconds > 0 and time.monotonic() - started >= args.max_seconds:
            break
        time.sleep(max(1.0, args.interval))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
