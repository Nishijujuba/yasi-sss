from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone

from builder.config import PACK_ROOT, REVIEW_ROOT, SCHEMA_VERSION
from builder.convert_audio import convert_audio_sections
from builder.detect_overlays import write_overlay_proposals
from builder.models import BuildMetadata, Manifest, ManifestAssets, SectionManifest
from builder.overlay_review import draw_review_images, finalize_overlays
from builder.render_pages import render_question_pages
from builder.validate_pack import export_answers_and_transcript, validate_pack


def _source_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return completed.stdout.strip() or "unknown"


def _manifest() -> Manifest:
    return Manifest(
        packId="cambridge-10-test-1-listening",
        schemaVersion=SCHEMA_VERSION,
        status="released",
        title="Cambridge IELTS 10 Test 1 Listening",
        sections=[
            SectionManifest(
                number=1,
                title="Listening Section 01",
                questionNumbers=list(range(1, 11)),
                audio="assets/audio/section-01.mp3",
                pages=["assets/pages/page-010.png", "assets/pages/page-011.png"],
            ),
            SectionManifest(
                number=2,
                title="Listening Section 02",
                questionNumbers=list(range(11, 21)),
                audio="assets/audio/section-02.mp3",
                pages=["assets/pages/page-012.png", "assets/pages/page-013.png"],
            ),
            SectionManifest(
                number=3,
                title="Listening Section 03",
                questionNumbers=list(range(21, 31)),
                audio="assets/audio/section-03.mp3",
                pages=["assets/pages/page-014.png", "assets/pages/page-015.png"],
            ),
            SectionManifest(
                number=4,
                title="Listening Section 04",
                questionNumbers=list(range(31, 41)),
                audio="assets/audio/section-04.mp3",
                pages=["assets/pages/page-016.png"],
            ),
        ],
        assets=ManifestAssets(
            questions="questions.json",
            answers="answers.json",
            overlays="overlays.json",
            transcript="transcript.json",
        ),
        build=BuildMetadata(
            sourceCommit=_source_commit(),
            builtAt=datetime.now(timezone.utc),
        ),
    )


def write_manifest() -> Manifest:
    manifest = _manifest()
    PACK_ROOT.mkdir(parents=True, exist_ok=True)
    (PACK_ROOT / "manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    return manifest


def build_pack():
    render_question_pages()
    write_overlay_proposals()
    draw_review_images()
    finalize_overlays()
    export_answers_and_transcript()
    convert_audio_sections()
    write_manifest()
    report = validate_pack(PACK_ROOT)
    REVIEW_ROOT.mkdir(parents=True, exist_ok=True)
    (REVIEW_ROOT / "release-report.json").write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    report = build_pack()
    print(f"pack {report.status}: {len(report.questionCoverage)} questions")


if __name__ == "__main__":
    main()
