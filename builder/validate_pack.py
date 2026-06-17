from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from builder.config import PACK_ROOT, SOURCE_DATA_ROOT
from pydantic import ValidationError

from builder.models import (
    Answer,
    Overlay,
    PendingAnswerCandidate,
    Question,
    ReleaseReport,
    ReleasedManifest,
    TranscriptSection,
    validate_answer_membership,
    validate_questions,
)


class ReleaseBlocked(RuntimeError):
    """Raised when source data is insufficient for a released practice pack."""


def _question_number(question_id: str) -> int:
    match = re.fullmatch(r"q([1-9]|[1-3][0-9]|40)", question_id)
    if not match:
        raise ReleaseBlocked(f"invalid question id in answers: {question_id}")
    return int(match.group(1))


def load_source_answers(path: Path = SOURCE_DATA_ROOT / "answers.json") -> list[Answer]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Answer.model_validate(item) for item in payload]


def load_source_transcript(source_dir: Path = SOURCE_DATA_ROOT) -> list[TranscriptSection]:
    sections: list[TranscriptSection] = []
    for section_number in range(1, 5):
        path = Path(source_dir) / f"transcript-section-{section_number:02d}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        sections.append(TranscriptSection.model_validate(payload))
    return sections


def covered_numbers(answers: Iterable[Answer]) -> set[int]:
    return {
        _question_number(question_id)
        for answer in answers
        for question_id in answer.questionIds
    }


def validate_answer_authority(
    answers_or_candidates: Iterable[Answer | PendingAnswerCandidate],
) -> None:
    for item in answers_or_candidates:
        if isinstance(item, PendingAnswerCandidate):
            if item.status != "approved":
                raise ReleaseBlocked(
                    f"question {item.questionNumber} requires user approval"
                )
            continue

        if item.reviewStatus not in {"official", "user-confirmed"}:
            raise ReleaseBlocked(
                f"{','.join(item.questionIds)} lacks approved answer authority"
            )
        if not item.provenance:
            raise ReleaseBlocked(f"{','.join(item.questionIds)} lacks provenance")
        if any(
            evidence.kind == "internet-candidate"
            for evidence in item.provenance
        ) and item.reviewStatus != "user-confirmed":
            raise ReleaseBlocked(
                f"{','.join(item.questionIds)} internet candidate requires user approval"
            )


def validate_transcript_sections(
    transcript: Iterable[TranscriptSection],
    answers: Iterable[Answer],
) -> None:
    section_list = list(transcript)
    if {section.section for section in section_list} != {1, 2, 3, 4}:
        raise ReleaseBlocked("transcript must contain sections 1 through 4")

    referenced_numbers = {
        answer_ref
        for section in section_list
        for segment in section.segments
        for answer_ref in segment.answerRefs
    }
    missing = covered_numbers(answers) - referenced_numbers
    if missing:
        raise ReleaseBlocked(
            "transcript answerRefs missing questions: "
            + ", ".join(str(number) for number in sorted(missing))
        )

    for section in section_list:
        if not section.source.get("pages"):
            raise ReleaseBlocked(f"transcript section {section.section} lacks source pages")
        if section.review.get("status") != "reviewed":
            raise ReleaseBlocked(f"transcript section {section.section} is not reviewed")
        for segment in section.segments:
            if segment.startTime is not None or segment.endTime is not None:
                raise ReleaseBlocked("transcript timing fields must stay reserved as null")


def export_answers_and_transcript(
    *,
    output_root: Path = PACK_ROOT,
) -> tuple[list[Answer], list[TranscriptSection]]:
    answers = load_source_answers()
    transcript = load_source_transcript()
    validate_answer_authority(answers)
    if covered_numbers(answers) != set(range(1, 41)):
        raise ReleaseBlocked("answers must cover questions 1 through 40")
    validate_transcript_sections(transcript, answers)

    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "answers.json").write_text(
        json.dumps([answer.model_dump() for answer in answers], indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    (output_root / "transcript.json").write_text(
        json.dumps(
            [section.model_dump() for section in transcript],
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return answers, transcript


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReleaseBlocked(f"required pack file is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ReleaseBlocked(f"invalid JSON in pack file: {path}") from exc


def _require_asset(pack_root: Path, relative_path: str) -> Path:
    path = pack_root / relative_path
    if not path.is_file():
        raise ReleaseBlocked(f"required asset is missing: {relative_path}")
    if path.stat().st_size <= 0:
        raise ReleaseBlocked(f"required asset is empty: {relative_path}")
    return path


def _validate_model_list(model_type, payload: object, label: str):
    if not isinstance(payload, list):
        raise ReleaseBlocked(f"{label} must be a JSON array")
    try:
        return [model_type.model_validate(item) for item in payload]
    except ValidationError as exc:
        raise ReleaseBlocked(f"{label} failed schema validation: {exc}") from exc


def validate_pack(pack_root: Path = PACK_ROOT) -> ReleaseReport:
    pack_root = Path(pack_root)
    try:
        manifest = ReleasedManifest.model_validate(_read_json(pack_root / "manifest.json"))
    except ValidationError as exc:
        raise ReleaseBlocked(f"manifest must be released: {exc}") from exc

    questions = _validate_model_list(
        Question,
        _read_json(pack_root / manifest.assets.questions),
        "questions",
    )
    validate_questions(questions)

    answers = _validate_model_list(
        Answer,
        _read_json(pack_root / manifest.assets.answers),
        "answers",
    )
    validate_answer_authority(answers)
    validate_answer_membership(answers, questions)

    overlays = _validate_model_list(
        Overlay,
        _read_json(pack_root / manifest.assets.overlays),
        "overlays",
    )
    transcript = _validate_model_list(
        TranscriptSection,
        _read_json(pack_root / manifest.assets.transcript),
        "transcript",
    )
    validate_transcript_sections(transcript, answers)

    question_ids = {question.id for question in questions}
    overlay_question_ids = {overlay.questionId for overlay in overlays}
    missing_overlay_questions = question_ids - overlay_question_ids - {"q12"}
    if missing_overlay_questions:
        raise ReleaseBlocked(
            "missing overlays for questions: "
            + ", ".join(sorted(missing_overlay_questions))
        )

    page_assets: list[str] = []
    audio_sections: list[int] = []
    for section in manifest.sections:
        _require_asset(pack_root, section.audio)
        audio_sections.append(section.number)
        for page in section.pages:
            _require_asset(pack_root, page)
            page_assets.append(page)

    question_numbers = sorted(question.number for question in questions)
    answer_numbers = sorted(covered_numbers(answers))
    if question_numbers != list(range(1, 41)) or answer_numbers != list(range(1, 41)):
        raise ReleaseBlocked("questions and answers must cover 1 through 40")

    return ReleaseReport(
        status="released",
        questionCoverage=question_numbers,
        overlayCount=len(overlays),
        answerCount=len(answer_numbers),
        transcriptSections=sorted(section.section for section in transcript),
        audioSections=sorted(audio_sections),
        pageAssets=sorted(set(page_assets)),
        pendingAnswerCandidates=0,
        errors=[],
    )


def main() -> None:
    answers, transcript = export_answers_and_transcript()
    print(f"wrote {len(answers)} answer entries and {len(transcript)} transcript sections")


if __name__ == "__main__":
    main()
