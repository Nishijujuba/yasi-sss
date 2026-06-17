from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from builder.config import FFPROBE, PACK_ROOT, SOURCE_DATA_ROOT
from builder.convert_audio import AudioValidationError, probe_duration_seconds
from pydantic import ValidationError

from builder.models import (
    Answer,
    AnswerAudioWindow,
    Overlay,
    PendingAnswerCandidate,
    Question,
    ReleaseReport,
    ReleasedManifest,
    TranscriptSection,
    VocabularyItem,
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


def load_source_vocabulary(path: Path = SOURCE_DATA_ROOT / "vocabulary.json") -> list[VocabularyItem]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return [VocabularyItem.model_validate(item) for item in payload]


def load_answer_audio_windows(
    path: Path = SOURCE_DATA_ROOT / "answer-audio-windows.json",
) -> list[AnswerAudioWindow]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return [AnswerAudioWindow.model_validate(item) for item in payload]


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


def export_vocabulary(*, output_root: Path = PACK_ROOT) -> list[VocabularyItem]:
    vocabulary = load_source_vocabulary()
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "vocabulary.json").write_text(
        json.dumps(
            [item.model_dump() for item in vocabulary],
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return vocabulary


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


def _normalize_term(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _canonical_blank_terms(
    answers: Iterable[Answer],
    questions: Iterable[Question],
) -> dict[str, tuple[str, list[str], Question]]:
    questions_by_id = {question.id: question for question in questions}
    canonical: dict[str, tuple[str, list[str], Question]] = {}
    seen: list[str] = []

    for answer in answers:
        if len(answer.questionIds) != 1:
            continue
        question = questions_by_id[answer.questionIds[0]]
        if question.responseType != "blank":
            continue

        term = answer.accepted[0][0]
        normalized = _normalize_term(term)
        variants = [
            accepted_group[0]
            for accepted_group in answer.accepted[1:]
            if accepted_group
        ]
        if normalized in canonical:
            raise ReleaseBlocked(f"duplicate blank canonical vocabulary term: {term}")
        canonical[normalized] = (term, variants, question)
        seen.append(term)

    if len(canonical) != 33:
        raise ReleaseBlocked(
            "vocabulary coverage requires 33 single blank canonical terms; "
            f"found {len(canonical)}"
        )
    return canonical


def _validate_unique_vocabulary_items(vocabulary: list[VocabularyItem]) -> None:
    ids = [item.id for item in vocabulary]
    duplicate_ids = sorted({item_id for item_id in ids if ids.count(item_id) > 1})
    if duplicate_ids:
        raise ReleaseBlocked("duplicate vocabulary ids: " + ", ".join(duplicate_ids))

    normalized_terms = [_normalize_term(item.normalizedTerm) for item in vocabulary]
    duplicates = sorted(
        {
            normalized
            for normalized in normalized_terms
            if normalized_terms.count(normalized) > 1
        }
    )
    if duplicates:
        raise ReleaseBlocked(
            "duplicate vocabulary normalized terms: " + ", ".join(duplicates)
        )


def _probe_required_duration(path: Path, description: str) -> float:
    try:
        return probe_duration_seconds(path, ffprobe_path=FFPROBE)
    except AudioValidationError as exc:
        raise ReleaseBlocked(f"{description} duration validation failed: {exc}") from exc


def _validate_vocabulary_release_gate(
    *,
    pack_root: Path,
    manifest: ReleasedManifest,
    questions: list[Question],
    answers: list[Answer],
    section_durations: dict[int, float],
    answer_audio_windows_path: Path,
) -> tuple[list[VocabularyItem], list[AnswerAudioWindow], int]:
    vocabulary = _validate_model_list(
        VocabularyItem,
        _read_json(pack_root / manifest.assets.vocabulary),
        "vocabulary",
    )
    windows = _validate_model_list(
        AnswerAudioWindow,
        _read_json(answer_audio_windows_path),
        "answer audio windows",
    )

    _validate_unique_vocabulary_items(vocabulary)
    canonical = _canonical_blank_terms(answers, questions)
    vocabulary_by_normalized = {
        _normalize_term(item.normalizedTerm): item for item in vocabulary
    }

    missing = sorted(set(canonical) - set(vocabulary_by_normalized))
    if missing:
        raise ReleaseBlocked(
            "vocabulary coverage missing canonical terms: " + ", ".join(missing)
        )

    extra = sorted(set(vocabulary_by_normalized) - set(canonical))
    if extra:
        raise ReleaseBlocked("extra vocabulary items: " + ", ".join(extra))

    for normalized, (term, variants, _) in canonical.items():
        item = vocabulary_by_normalized[normalized]
        if item.term != term:
            raise ReleaseBlocked(
                f"vocabulary canonical term mismatch for {item.id}: "
                f"expected {term}, found {item.term}"
            )
        if _normalize_term(item.normalizedTerm) != normalized:
            raise ReleaseBlocked(
                f"vocabulary normalizedTerm mismatch for {item.id}: {item.normalizedTerm}"
            )
        if item.acceptedVariants != variants:
            raise ReleaseBlocked(
                f"vocabulary acceptedVariants mismatch for {item.id}"
            )
        if not item.meaningZh.strip():
            raise ReleaseBlocked(f"vocabulary item {item.id} meaningZh is empty")

    vocabulary_by_id = {item.id: item for item in vocabulary}
    windows_by_vocabulary_id: dict[str, AnswerAudioWindow] = {}
    for window in windows:
        if window.vocabularyId in windows_by_vocabulary_id:
            raise ReleaseBlocked(
                f"duplicate answer audio window for vocabulary: {window.vocabularyId}"
            )
        windows_by_vocabulary_id[window.vocabularyId] = window

    missing_windows = sorted(set(vocabulary_by_id) - set(windows_by_vocabulary_id))
    if missing_windows:
        raise ReleaseBlocked(
            "vocabulary audio windows missing: " + ", ".join(missing_windows)
        )

    extra_windows = sorted(set(windows_by_vocabulary_id) - set(vocabulary_by_id))
    if extra_windows:
        raise ReleaseBlocked(
            "extra vocabulary audio windows: " + ", ".join(extra_windows)
        )

    questions_by_id = {question.id: question for question in questions}
    clip_count = 0
    for item in vocabulary:
        normalized = _normalize_term(item.normalizedTerm)
        _, _, canonical_question = canonical[normalized]
        window = windows_by_vocabulary_id[item.id]
        question = questions_by_id.get(window.questionId)
        if question is None:
            raise ReleaseBlocked(
                f"answer audio window {item.id} references unknown question {window.questionId}"
            )
        if question.id != canonical_question.id:
            raise ReleaseBlocked(
                f"answer audio window {item.id} question mismatch: "
                f"expected {canonical_question.id}, found {question.id}"
            )
        if window.section != question.section:
            raise ReleaseBlocked(
                f"answer audio window {item.id} section mismatch: "
                f"question {question.id} is section {question.section}, "
                f"window uses section {window.section}"
            )

        section_duration = section_durations[window.section]
        padded_start = window.startTime - window.paddingBefore
        padded_end = window.endTime + window.paddingAfter
        if padded_start < 0 or padded_end > section_duration:
            raise ReleaseBlocked(
                f"answer audio window {item.id} exceeds section duration "
                f"{section_duration:.3f}s"
            )

        clip_path = _require_asset(pack_root, item.audio)
        clip_duration = _probe_required_duration(clip_path, f"vocabulary clip {item.id}")
        if clip_duration < 0.25 or clip_duration > 6.0:
            raise ReleaseBlocked(
                f"vocabulary clip duration for {item.id} is {clip_duration:.3f}s; "
                "expected 0.25s..6.0s"
            )
        clip_count += 1

    return vocabulary, windows, clip_count


def validate_pack(
    pack_root: Path = PACK_ROOT,
    *,
    answer_audio_windows_path: Path = SOURCE_DATA_ROOT / "answer-audio-windows.json",
) -> ReleaseReport:
    pack_root = Path(pack_root)
    answer_audio_windows_path = Path(answer_audio_windows_path)
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
    section_durations: dict[int, float] = {}
    for section in manifest.sections:
        section_audio_path = _require_asset(pack_root, section.audio)
        section_durations[section.number] = _probe_required_duration(
            section_audio_path,
            f"section {section.number} audio",
        )
        audio_sections.append(section.number)
        for page in section.pages:
            _require_asset(pack_root, page)
            page_assets.append(page)

    question_numbers = sorted(question.number for question in questions)
    answer_numbers = sorted(covered_numbers(answers))
    if question_numbers != list(range(1, 41)) or answer_numbers != list(range(1, 41)):
        raise ReleaseBlocked("questions and answers must cover 1 through 40")

    vocabulary, windows, clip_count = _validate_vocabulary_release_gate(
        pack_root=pack_root,
        manifest=manifest,
        questions=questions,
        answers=answers,
        section_durations=section_durations,
        answer_audio_windows_path=answer_audio_windows_path,
    )

    return ReleaseReport(
        status="released",
        questionCoverage=question_numbers,
        overlayCount=len(overlays),
        answerCount=len(answer_numbers),
        vocabularyCount=len(vocabulary),
        windowCount=len(windows),
        clipCount=clip_count,
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
