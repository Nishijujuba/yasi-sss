from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path

from pydantic import ValidationError

from builder.config import AUDIO_ASSET_ROOT, FFMPEG, FFPROBE, SOURCE_DATA_ROOT
from builder.convert_audio import (
    AudioValidationError,
    _replace_with_retries,
    _require_existing_file,
    _run_captured,
    _same_file_content,
    assert_duration_match,
    probe_duration_seconds,
)
from builder.models import Answer, AnswerAudioWindow, Question, VocabularyItem


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRASH_DIR = PROJECT_ROOT / "待删除"
TEMP_OUTPUT_DIR = TRASH_DIR / "vocabulary-audio"
DEFAULT_OUTPUT_DIR = AUDIO_ASSET_ROOT / "vocabulary"


def _read_json(path: Path) -> object:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AudioValidationError(f"required vocabulary audio input is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise AudioValidationError(f"invalid JSON in vocabulary audio input: {path}") from exc


def _load_model_list(model_type, path: Path, label: str):
    payload = _read_json(path)
    if not isinstance(payload, list):
        raise AudioValidationError(f"{label} must be a JSON array")
    try:
        return [model_type.model_validate(item) for item in payload]
    except ValidationError as exc:
        raise AudioValidationError(f"{label} failed schema validation: {exc}") from exc


def _normalize_term(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _temporary_output_path(output_path: Path) -> Path:
    TEMP_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return TEMP_OUTPUT_DIR / f".{output_path.stem}.{uuid.uuid4().hex}.tmp{output_path.suffix}"


def _archive_temp_file(path: Path) -> None:
    if not path.exists():
        return
    if path.resolve().parent == TEMP_OUTPUT_DIR.resolve():
        return
    TRASH_DIR.mkdir(exist_ok=True)
    archive_path = TRASH_DIR / f"{uuid.uuid4().hex}-{path.name}"
    try:
        _replace_with_retries(path, archive_path)
    except OSError:
        return


def _canonical_by_question(
    answers: list[Answer],
    questions: list[Question],
) -> dict[str, tuple[str, list[str], Question]]:
    questions_by_id = {question.id: question for question in questions}
    canonical: dict[str, tuple[str, list[str], Question]] = {}
    for answer in answers:
        if len(answer.questionIds) != 1:
            continue
        question = questions_by_id.get(answer.questionIds[0])
        if question is None or question.responseType != "blank":
            continue
        canonical[question.id] = (
            answer.accepted[0][0],
            [group[0] for group in answer.accepted[1:] if group],
            question,
        )
    return canonical


def _window_for_item(
    item: VocabularyItem,
    windows_by_vocabulary_id: dict[str, AnswerAudioWindow],
) -> AnswerAudioWindow:
    try:
        return windows_by_vocabulary_id[item.id]
    except KeyError as exc:
        raise AudioValidationError(f"missing answer audio window for vocabulary {item.id}") from exc


def _validate_item_window(
    item: VocabularyItem,
    window: AnswerAudioWindow,
    canonical_by_question: dict[str, tuple[str, list[str], Question]],
) -> Question:
    try:
        term, variants, question = canonical_by_question[window.questionId]
    except KeyError as exc:
        raise AudioValidationError(
            f"answer audio window {item.id} references unknown blank question {window.questionId}"
        ) from exc

    if item.term != term or _normalize_term(item.normalizedTerm) != _normalize_term(term):
        raise AudioValidationError(f"vocabulary {item.id} does not match canonical answer for {question.id}")
    if item.acceptedVariants != variants:
        raise AudioValidationError(f"vocabulary {item.id} accepted variants do not match answers")
    if window.section != question.section:
        raise AudioValidationError(
            f"answer audio window {item.id} section mismatch: "
            f"question {question.id} is section {question.section}, window uses section {window.section}"
        )
    return question


def _padded_clip_bounds(window: AnswerAudioWindow) -> tuple[float, float, float]:
    clip_start = window.startTime - window.paddingBefore
    clip_end = window.endTime + window.paddingAfter
    clip_duration = clip_end - clip_start
    if clip_start < 0:
        raise AudioValidationError(f"answer audio window {window.vocabularyId} starts before section audio")
    if clip_duration < 0.25 or clip_duration > 6.0:
        raise AudioValidationError(
            f"vocabulary clip window for {window.vocabularyId} is {clip_duration:.3f}s; expected 0.25s..6.0s"
        )
    return clip_start, clip_end, clip_duration


def build_vocabulary_audio_clips(
    *,
    answers_path: Path = SOURCE_DATA_ROOT / "answers.json",
    questions_path: Path = SOURCE_DATA_ROOT / "questions.json",
    vocabulary_path: Path = SOURCE_DATA_ROOT / "vocabulary.json",
    windows_path: Path = SOURCE_DATA_ROOT / "answer-audio-windows.json",
    section_audio_dir: Path = AUDIO_ASSET_ROOT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    ffmpeg_path: Path = FFMPEG,
    ffprobe_path: Path = FFPROBE,
    tolerance_seconds: float = 0.10,
) -> list[Path]:
    answers = _load_model_list(Answer, Path(answers_path), "answers")
    questions = _load_model_list(Question, Path(questions_path), "questions")
    vocabulary = _load_model_list(VocabularyItem, Path(vocabulary_path), "vocabulary")
    windows = _load_model_list(AnswerAudioWindow, Path(windows_path), "answer audio windows")

    ffmpeg_path = Path(ffmpeg_path)
    ffprobe_path = Path(ffprobe_path)
    section_audio_dir = Path(section_audio_dir)
    output_dir = Path(output_dir)

    _require_existing_file(ffmpeg_path, "ffmpeg executable")
    _require_existing_file(ffprobe_path, "ffprobe executable")
    output_dir.mkdir(parents=True, exist_ok=True)

    canonical_by_question = _canonical_by_question(answers, questions)
    windows_by_vocabulary_id: dict[str, AnswerAudioWindow] = {}
    for window in windows:
        if window.vocabularyId in windows_by_vocabulary_id:
            raise AudioValidationError(f"duplicate answer audio window for vocabulary {window.vocabularyId}")
        windows_by_vocabulary_id[window.vocabularyId] = window

    outputs: list[Path] = []
    section_durations: dict[int, float] = {}

    for item in vocabulary:
        window = _window_for_item(item, windows_by_vocabulary_id)
        _validate_item_window(item, window, canonical_by_question)
        clip_start, clip_end, clip_duration = _padded_clip_bounds(window)
        section_path = section_audio_dir / f"section-{window.section:02d}.mp3"
        _require_existing_file(section_path, f"section {window.section} audio")
        if window.section not in section_durations:
            section_durations[window.section] = probe_duration_seconds(
                section_path,
                ffprobe_path=ffprobe_path,
            )
        if clip_end > section_durations[window.section]:
            raise AudioValidationError(
                f"answer audio window {item.id} exceeds section duration {section_durations[window.section]:.3f}s"
            )

        output_path = output_dir / f"{item.id}.mp3"
        temp_output_path = _temporary_output_path(output_path)
        command = [
            str(ffmpeg_path),
            "-y",
            "-ss",
            f"{clip_start:.3f}",
            "-i",
            str(section_path),
            "-t",
            f"{clip_duration:.3f}",
            "-vn",
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "2",
            str(temp_output_path),
        ]

        try:
            _run_captured(command)
        except subprocess.CalledProcessError as exc:
            _archive_temp_file(temp_output_path)
            details = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            raise AudioValidationError(f"ffmpeg failed for vocabulary {item.id}: {details}") from exc

        try:
            if not temp_output_path.exists() or temp_output_path.stat().st_size == 0:
                raise AudioValidationError(f"Vocabulary clip output is missing or empty: {temp_output_path}")
            output_duration = probe_duration_seconds(temp_output_path, ffprobe_path=ffprobe_path)
            assert_duration_match(
                section_path,
                clip_duration,
                temp_output_path,
                output_duration,
                tolerance_seconds=tolerance_seconds,
            )
        except AudioValidationError:
            _archive_temp_file(temp_output_path)
            raise

        try:
            if _same_file_content(temp_output_path, output_path):
                _archive_temp_file(temp_output_path)
                outputs.append(output_path)
                continue
            _replace_with_retries(temp_output_path, output_path)
        except OSError as exc:
            _archive_temp_file(temp_output_path)
            if output_path.exists() and output_path.stat().st_size > 0:
                raise AudioValidationError(
                    f"Could not publish vocabulary clip {temp_output_path} to {output_path}: {exc}. "
                    "The existing output differs from the newly generated file."
                ) from exc
            try:
                output_path.write_bytes(temp_output_path.read_bytes())
            except OSError as fallback_exc:
                raise AudioValidationError(
                    f"Could not publish vocabulary clip {temp_output_path} to {output_path}: {exc}; "
                    f"fallback copy also failed: {fallback_exc}"
                ) from fallback_exc
        outputs.append(output_path)

    return outputs


def main() -> int:
    try:
        outputs = build_vocabulary_audio_clips()
    except AudioValidationError as exc:
        print(f"Vocabulary audio generation failed: {exc}", file=sys.stderr)
        return 1

    for output in outputs:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
