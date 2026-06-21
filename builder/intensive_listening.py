from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from pydantic import ValidationError

from builder.config import PACK_ROOT, SOURCE_DATA_ROOT
from builder.models import (
    INTENSIVE_LISTENING_SCHEMA_VERSION,
    IntensiveListeningAsset,
    IntensiveListeningBlank,
    IntensiveListeningCandidate,
    IntensiveListeningCandidateSource,
    IntensiveListeningSection,
    TranscriptSection,
)

INTENSIVE_LISTENING_ASSET = "intensive-listening.json"
CandidatePayload = dict[str, Any]

TOKEN_RE = re.compile(
    "[\u00a3$\u20ac]?\\d+(?:[,.]\\d+)*(?:-[A-Za-z0-9]+)?|"
    "[A-Za-z0-9]+(?:[\u2019\u2018'`][A-Za-z0-9]+)?(?:-[A-Za-z0-9]+)*"
)
CURRENCY = {"$", "\u00a3", "\u20ac"}


class IntensiveListeningBuildError(RuntimeError):
    """Raised when Intensive Listening data cannot be released."""


@dataclass(frozen=True)
class OfficialToken:
    section: int
    segment_order: int
    token_index: int
    text: str
    normalized: str


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise IntensiveListeningBuildError(f"required file is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise IntensiveListeningBuildError(f"invalid JSON in file: {path}") from exc


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def normalize_token(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text).strip()).lower()
    for mark in ("\u2019", "\u2018", "`"):
        value = value.replace(mark, "'")
    value = value.replace(",", "")
    for symbol in CURRENCY:
        value = value.replace(symbol, "")
    value = value.replace("-", "")
    value = value.replace("'", "")
    return re.sub(r"[^a-z0-9]+", "", value)


def tokenize_text(text: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    for match in TOKEN_RE.finditer(str(text)):
        raw = match.group(0).strip()
        normalized = normalize_token(raw)
        if normalized:
            tokens.append((raw, normalized))
    return tokens


def _coerce_transcript_sections(
    transcript_payload: Iterable[TranscriptSection | dict[str, Any]] | dict[str, Any],
) -> list[TranscriptSection]:
    if isinstance(transcript_payload, dict) and isinstance(transcript_payload.get("sections"), list):
        raw_sections = transcript_payload["sections"]
    else:
        raw_sections = transcript_payload

    sections: list[TranscriptSection] = []
    for index, item in enumerate(raw_sections):  # type: ignore[arg-type]
        if isinstance(item, TranscriptSection):
            sections.append(item)
            continue
        try:
            sections.append(TranscriptSection.model_validate(item))
        except ValidationError as exc:
            raise IntensiveListeningBuildError(
                f"transcript section {index + 1} failed schema validation: {exc}"
            ) from exc

    section_numbers = {section.section for section in sections}
    if section_numbers != {1, 2, 3, 4}:
        raise IntensiveListeningBuildError(
            "transcript must contain sections 1 through 4"
        )
    return sections


def _tokens_by_section_segment(
    transcript_payload: Iterable[TranscriptSection | dict[str, Any]] | dict[str, Any],
) -> dict[int, dict[int, list[OfficialToken]]]:
    sections = _coerce_transcript_sections(transcript_payload)
    by_section: dict[int, dict[int, list[OfficialToken]]] = {}
    for section in sections:
        section_segments: dict[int, list[OfficialToken]] = {}
        for segment in section.segments:
            segment_tokens: list[OfficialToken] = []
            for token_index, (text, normalized) in enumerate(tokenize_text(segment.text)):
                segment_tokens.append(
                    OfficialToken(
                        section=section.section,
                        segment_order=segment.order,
                        token_index=token_index,
                        text=text,
                        normalized=normalized,
                    )
                )
            section_segments[segment.order] = segment_tokens
        by_section[section.section] = section_segments
    return by_section


def _candidate_from_payload(item: Any, index: int) -> IntensiveListeningCandidate:
    try:
        return IntensiveListeningCandidate.model_validate(item)
    except ValidationError as exc:
        raise IntensiveListeningBuildError(
            f"candidate {index + 1} failed schema validation: {exc}"
        ) from exc


def _stable_blank_id(
    *,
    section: int,
    segment_order: int,
    start_token_index: int,
    end_token_index: int,
) -> str:
    return (
        f"il-s{section:02d}-seg{segment_order:03d}-"
        f"t{start_token_index:03d}-t{end_token_index:03d}"
    )


def _official_span(
    tokens_by_segment: dict[int, list[OfficialToken]],
    *,
    section: int,
    segment_order: int,
    start_token_index: int,
    end_token_index: int,
) -> list[OfficialToken]:
    segment_tokens = tokens_by_segment.get(segment_order)
    if segment_tokens is None:
        raise IntensiveListeningBuildError(
            f"section {section} segment {segment_order} is missing from transcript"
        )
    if not (0 <= start_token_index < end_token_index <= len(segment_tokens)):
        raise IntensiveListeningBuildError(
            f"section {section} segment {segment_order} token range "
            f"{start_token_index}..{end_token_index} is outside 0..{len(segment_tokens)}"
        )
    return segment_tokens[start_token_index:end_token_index]


def _answer_from_tokens(tokens: list[OfficialToken]) -> str:
    return " ".join(token.text for token in tokens)


def _normalized_sequence(text: str) -> list[str]:
    return [normalized for _, normalized in tokenize_text(text)]


def _validate_no_overlaps(blanks: Iterable[IntensiveListeningBlank], section: int) -> None:
    by_segment: dict[int, list[IntensiveListeningBlank]] = {}
    for blank in blanks:
        by_segment.setdefault(blank.segmentOrder, []).append(blank)

    for segment_order, segment_blanks in by_segment.items():
        sorted_blanks = sorted(
            segment_blanks,
            key=lambda blank: (blank.startTokenIndex, blank.endTokenIndex, blank.id),
        )
        previous: IntensiveListeningBlank | None = None
        for blank in sorted_blanks:
            if previous is not None and blank.startTokenIndex < previous.endTokenIndex:
                raise IntensiveListeningBuildError(
                    "intensive listening blanks overlap in "
                    f"section {section} segment {segment_order}: "
                    f"{previous.id} and {blank.id}"
                )
            previous = blank


def _validate_generated_blank_ids(blanks: Iterable[IntensiveListeningBlank]) -> None:
    seen: set[str] = set()
    for blank in blanks:
        if blank.id in seen:
            raise IntensiveListeningBuildError(
                f"duplicate intensive listening blank id: {blank.id}"
            )
        seen.add(blank.id)


def build_intensive_listening_asset(
    transcript_payload: Iterable[TranscriptSection | dict[str, Any]] | dict[str, Any],
    candidate_payloads: Iterable[CandidatePayload],
) -> IntensiveListeningAsset:
    tokens_by_section = _tokens_by_section_segment(transcript_payload)
    candidates = [
        _candidate_from_payload(item, index)
        for index, item in enumerate(candidate_payloads)
    ]

    blanks_by_section: dict[int, list[IntensiveListeningBlank]] = {
        section: [] for section in range(1, 5)
    }
    seen_ids: set[str] = set()

    for candidate in candidates:
        tokens_by_segment = tokens_by_section.get(candidate.section)
        if tokens_by_segment is None:
            raise IntensiveListeningBuildError(
                f"section {candidate.section} is missing from transcript"
            )

        span_tokens = _official_span(
            tokens_by_segment,
            section=candidate.section,
            segment_order=candidate.segmentOrder,
            start_token_index=candidate.startTokenIndex,
            end_token_index=candidate.endTokenIndex,
        )
        expected_sequence = [token.normalized for token in span_tokens]
        candidate_sequence = _normalized_sequence(candidate.text)
        if candidate_sequence != expected_sequence:
            raise IntensiveListeningBuildError(
                "candidate text mismatch for "
                f"section {candidate.section} segment {candidate.segmentOrder} "
                f"tokens {candidate.startTokenIndex}..{candidate.endTokenIndex}: "
                f"expected {_answer_from_tokens(span_tokens)!r}, found {candidate.text!r}"
            )

        blank_id = _stable_blank_id(
            section=candidate.section,
            segment_order=candidate.segmentOrder,
            start_token_index=candidate.startTokenIndex,
            end_token_index=candidate.endTokenIndex,
        )
        if blank_id in seen_ids:
            raise IntensiveListeningBuildError(
                f"duplicate intensive listening blank id: {blank_id}"
            )
        seen_ids.add(blank_id)

        blanks_by_section[candidate.section].append(
            IntensiveListeningBlank(
                id=blank_id,
                segmentOrder=candidate.segmentOrder,
                startTokenIndex=candidate.startTokenIndex,
                endTokenIndex=candidate.endTokenIndex,
                answer=_answer_from_tokens(span_tokens),
                acceptedVariants=[],
                reason=candidate.reason.strip(),
                tags=[tag.strip() for tag in candidate.tags],
            )
        )

    sections: list[IntensiveListeningSection] = []
    for section in range(1, 5):
        blanks = sorted(
            blanks_by_section[section],
            key=lambda blank: (blank.segmentOrder, blank.startTokenIndex, blank.endTokenIndex),
        )
        if not blanks:
            raise IntensiveListeningBuildError(
                f"section {section} has no intensive listening blanks"
            )
        _validate_no_overlaps(blanks, section)
        sections.append(IntensiveListeningSection(section=section, blanks=blanks))

    asset = IntensiveListeningAsset(
        schemaVersion=INTENSIVE_LISTENING_SCHEMA_VERSION,
        sections=sections,
    )
    validate_intensive_listening_asset(asset, transcript_payload)
    return asset


def load_candidate_sources(source_dir: Path = SOURCE_DATA_ROOT) -> list[CandidatePayload]:
    candidates: list[CandidatePayload] = []
    for section in range(1, 5):
        path = Path(source_dir) / f"intensive-listening-candidates-section-{section:02d}.json"
        payload = _read_json(path)
        try:
            source = IntensiveListeningCandidateSource.model_validate(payload)
        except ValidationError as exc:
            raise IntensiveListeningBuildError(
                f"candidate source {path} failed schema validation: {exc}"
            ) from exc
        if source.section != section:
            raise IntensiveListeningBuildError(
                f"candidate source {path} declares section {source.section}; expected {section}"
            )
        candidates.extend(
            candidate.model_dump(mode="json")
            for candidate in source.candidates
        )
    return candidates


def validate_intensive_listening_asset(
    asset_payload: IntensiveListeningAsset | dict[str, Any],
    transcript_payload: Iterable[TranscriptSection | dict[str, Any]] | dict[str, Any],
) -> IntensiveListeningAsset:
    try:
        asset = (
            asset_payload
            if isinstance(asset_payload, IntensiveListeningAsset)
            else IntensiveListeningAsset.model_validate(asset_payload)
        )
    except ValidationError as exc:
        raise IntensiveListeningBuildError(
            f"intensive listening asset failed schema validation: {exc}"
        ) from exc

    tokens_by_section = _tokens_by_section_segment(transcript_payload)
    all_blanks = [
        blank
        for section_payload in asset.sections
        for blank in section_payload.blanks
    ]
    _validate_generated_blank_ids(all_blanks)

    for section_payload in asset.sections:
        tokens_by_segment = tokens_by_section.get(section_payload.section)
        if tokens_by_segment is None:
            raise IntensiveListeningBuildError(
                f"section {section_payload.section} is missing from transcript"
            )
        for blank in section_payload.blanks:
            span_tokens = _official_span(
                tokens_by_segment,
                section=section_payload.section,
                segment_order=blank.segmentOrder,
                start_token_index=blank.startTokenIndex,
                end_token_index=blank.endTokenIndex,
            )
            expected_id = _stable_blank_id(
                section=section_payload.section,
                segment_order=blank.segmentOrder,
                start_token_index=blank.startTokenIndex,
                end_token_index=blank.endTokenIndex,
            )
            if blank.id != expected_id:
                raise IntensiveListeningBuildError(
                    f"intensive listening blank id {blank.id!r} must be {expected_id!r}"
                )
            expected_answer = _answer_from_tokens(span_tokens)
            if blank.answer != expected_answer:
                raise IntensiveListeningBuildError(
                    f"intensive listening answer mismatch for {blank.id}: "
                    f"expected {expected_answer!r}, found {blank.answer!r}"
                )
        _validate_no_overlaps(section_payload.blanks, section_payload.section)

    return asset


def export_intensive_listening(
    *,
    output_root: Path = PACK_ROOT,
    source_dir: Path = SOURCE_DATA_ROOT,
) -> IntensiveListeningAsset:
    output_root = Path(output_root)
    transcript_payload = _read_json(output_root / "transcript.json")
    candidates = load_candidate_sources(Path(source_dir))
    asset = build_intensive_listening_asset(transcript_payload, candidates)
    _write_json(
        output_root / INTENSIVE_LISTENING_ASSET,
        asset.model_dump(mode="json"),
    )
    return asset
