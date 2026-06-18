#!/usr/bin/env python3
"""Launch yasi forced-alignment as a detached background job."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(r"D:\Project\yasi")
PROJECT_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
ALIGN_SCRIPT = PROJECT_ROOT / ".agents" / "skills" / "yasi-forced-alignment" / "scripts" / "align_transcript.py"
DEFAULT_JOB_ROOT = PROJECT_ROOT / "待删除" / "yasi-forced-alignment" / "jobs"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Start a yasi forced-alignment command in the background and write a monitorable job file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--job-root", default=str(DEFAULT_JOB_ROOT), help="Directory for job JSON and top-level logs.")
    parser.add_argument("--job-name", default=None, help="Readable job name prefix.")
    parser.add_argument("--project-python", default=str(PROJECT_PYTHON), help="Project Python used to run align_transcript.py.")
    parser.add_argument("--align-script", default=str(ALIGN_SCRIPT), help="Alignment orchestration script.")
    parser.add_argument("--dry-run", action="store_true", help="Write the job file without starting the process.")
    parser.add_argument("align_args", nargs=argparse.REMAINDER, help="Arguments passed to align_transcript.py after --.")
    return parser


def normalize_remainder(args: list[str]) -> list[str]:
    return args[1:] if args and args[0] == "--" else args


def slug(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-").lower()
    return text or "alignment"


def next_job_id(job_root: Path, job_name: str | None) -> str:
    prefix = slug(job_name or "alignment")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = f"{stamp}-{prefix}"
    path = job_root / f"{candidate}.json"
    counter = 2
    while path.exists():
        candidate = f"{stamp}-{prefix}-{counter}"
        path = job_root / f"{candidate}.json"
        counter += 1
    return candidate


def planned_sections(align_args: list[str]) -> list[int]:
    if "--all-sections" in align_args:
        return [1, 2, 3, 4]
    sections: list[int] = []
    for idx, value in enumerate(align_args):
        if value == "--section" and idx + 1 < len(align_args):
            sections.append(int(align_args[idx + 1]))
    return sorted(set(sections))


def command_for(project_python: Path, align_script: Path, align_args: list[str]) -> list[str]:
    return [str(project_python), str(align_script), *align_args]


def creation_flags() -> int:
    flags = 0
    flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    flags |= getattr(subprocess, "DETACHED_PROCESS", 0)
    return flags


def child_environment() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def write_job(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    align_args = normalize_remainder(args.align_args)
    if not align_args:
        raise SystemExit("Pass align_transcript.py arguments after --.")

    job_root = Path(args.job_root)
    job_id = next_job_id(job_root, args.job_name)
    stdout = job_root / f"{job_id}.stdout.log"
    stderr = job_root / f"{job_id}.stderr.log"
    job_path = job_root / f"{job_id}.json"
    project_python = Path(args.project_python)
    align_script = Path(args.align_script)
    cmd = command_for(project_python, align_script, align_args)

    payload: dict[str, Any] = {
        "schemaVersion": "yasi.alignment-job.v1",
        "jobId": job_id,
        "status": "planned" if args.dry_run else "running",
        "createdAt": utc_now(),
        "cwd": str(PROJECT_ROOT),
        "pid": None,
        "command": cmd,
        "alignArgs": align_args,
        "sections": planned_sections(align_args),
        "stdout": str(stdout),
        "stderr": str(stderr),
        "environment": {
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        },
    }

    if not args.dry_run:
        job_root.mkdir(parents=True, exist_ok=True)
        stdout_handle = stdout.open("w", encoding="utf-8")
        stderr_handle = stderr.open("w", encoding="utf-8")
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(PROJECT_ROOT),
                stdout=stdout_handle,
                stderr=stderr_handle,
                stdin=subprocess.DEVNULL,
                env=child_environment(),
                creationflags=creation_flags(),
            )
        finally:
            stdout_handle.close()
            stderr_handle.close()
        payload["pid"] = proc.pid
        payload["startedAt"] = utc_now()

    write_job(job_path, payload)
    print(json.dumps({"job": str(job_path), "pid": payload["pid"], "status": payload["status"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
