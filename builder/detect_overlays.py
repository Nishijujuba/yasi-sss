from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
from PIL import Image

from builder.config import PAGE_ASSET_ROOT, PACK_ROOT, REVIEW_ROOT, SOURCE_DATA_ROOT
from builder.models import NormalizedRect, Question, Rect, validate_questions


QUESTIONS_SOURCE = SOURCE_DATA_ROOT / "questions.json"
PUBLIC_QUESTIONS = PACK_ROOT / "questions.json"
OVERLAY_PROPOSALS = REVIEW_ROOT / "overlay-proposals.json"


class DetectionError(RuntimeError):
    """Raised when deterministic page-geometry detection cannot be trusted."""


@dataclass(frozen=True)
class DetectedRegion:
    pixel: Rect
    deterministic_confidence: float
    evidence: list[str]


@dataclass(frozen=True)
class _LineCandidate:
    y: float
    x1: int
    x2: int
    run_count: int
    row_count: int

    @property
    def score(self) -> float:
        return (self.x2 - self.x1) * self.run_count


@dataclass(frozen=True)
class _TextBand:
    x1: int
    y1: int
    x2: int
    y2: int
    dark_pixels: int


def _grayscale_array(image: Image.Image) -> np.ndarray:
    return np.asarray(image.convert("L"))


def _small_runs_for_row(active_row: np.ndarray) -> list[tuple[int, int]]:
    xs = np.flatnonzero(active_row)
    if xs.size == 0:
        return []

    breaks = np.flatnonzero(np.diff(xs) > 1)
    starts = np.concatenate(([xs[0]], xs[breaks + 1]))
    ends = np.concatenate((xs[breaks], [xs[-1]]))
    return [
        (int(start), int(end))
        for start, end in zip(starts, ends)
        if 1 <= end - start + 1 <= 5
    ]


def _row_line_sequences(
    runs: Sequence[tuple[int, int]],
    *,
    max_gap: int = 13,
) -> list[tuple[int, int, int]]:
    if not runs:
        return []

    sequences: list[tuple[int, int, int]] = []
    start_x, previous_x = runs[0]
    count = 1

    for run_start, run_end in runs[1:]:
        gap = run_start - previous_x
        if gap <= max_gap:
            previous_x = run_end
            count += 1
            continue
        sequences.append((start_x, previous_x, count))
        start_x, previous_x = run_start, run_end
        count = 1
    sequences.append((start_x, previous_x, count))
    return sequences


def _cluster_line_rows(candidates: Iterable[_LineCandidate]) -> list[_LineCandidate]:
    sorted_candidates = sorted(candidates, key=lambda candidate: candidate.y)
    clusters: list[list[_LineCandidate]] = []
    for candidate in sorted_candidates:
        if not clusters or candidate.y - clusters[-1][-1].y > 6:
            clusters.append([candidate])
            continue
        clusters[-1].append(candidate)

    merged: list[_LineCandidate] = []
    for cluster in clusters:
        weight = sum(item.run_count for item in cluster)
        if weight <= 0:
            continue
        y = sum(item.y * item.run_count for item in cluster) / weight
        merged.append(
            _LineCandidate(
                y=y,
                x1=min(item.x1 for item in cluster),
                x2=max(item.x2 for item in cluster),
                run_count=max(item.run_count for item in cluster),
                row_count=len(cluster),
            )
        )
    return merged


def _thin_line_candidates(image: Image.Image) -> list[_LineCandidate]:
    grayscale = _grayscale_array(image)
    dark = grayscale < 150
    height, width = dark.shape

    padded = np.pad(dark, ((3, 3), (0, 0)), constant_values=False)
    vertical_density = sum(padded[offset : offset + height] for offset in range(7))
    thin_dark = dark & (vertical_density <= 3)

    row_candidates: list[_LineCandidate] = []
    for y in range(height):
        small_runs = _small_runs_for_row(thin_dark[y])
        if len(small_runs) < 8:
            continue
        for x1, x2, count in _row_line_sequences(small_runs):
            span = x2 - x1
            if count < 8 or span < 60:
                continue
            if x1 < 70 or x2 > width - 30:
                continue
            row_candidates.append(
                _LineCandidate(y=float(y), x1=x1, x2=x2, run_count=count, row_count=1)
            )

    return sorted(_cluster_line_rows(row_candidates), key=lambda item: item.y)


def _official_blank_y_anchors(expected_count: int, skip_leading: int) -> list[float] | None:
    anchors_by_shape: dict[tuple[int, int], list[float]] = {
        (6, 1): [688, 749, 912, 1074, 1128, 1235, 1342],
        (4, 0): [423, 525, 585, 686],
        (8, 0): [428, 470, 514, 614, 656, 698, 742, 784],
        (5, 0): [344, 402, 459, 517, 574],
        (10, 0): [480, 523, 566, 704, 790, 914, 956, 997, 1135, 1177],
    }
    return anchors_by_shape.get((expected_count, skip_leading))


def _select_layout_candidates(
    candidates: Sequence[_LineCandidate],
    *,
    expected_count: int,
    skip_leading: int,
) -> list[_LineCandidate]:
    anchors = _official_blank_y_anchors(expected_count, skip_leading)
    if anchors is None:
        minimum_score = 1500
        candidate_pool = [
            candidate for candidate in candidates if candidate.score >= minimum_score
        ]
        return sorted(candidate_pool, key=lambda item: item.score, reverse=True)[
            : expected_count + skip_leading
        ][skip_leading:]

    remaining = list(candidates)
    selected: list[_LineCandidate] = []
    for anchor in anchors:
        nearby = [
            candidate
            for candidate in remaining
            if abs(candidate.y - anchor) <= 18
        ]
        if not nearby:
            continue
        chosen = min(
            nearby,
            key=lambda candidate: (
                abs(candidate.y - anchor),
                -candidate.score,
            ),
        )
        selected.append(chosen)
        remaining.remove(chosen)

    if len(selected) != len(anchors):
        return selected[skip_leading:]
    return sorted(selected, key=lambda item: item.y)[skip_leading:]


def detect_blank_regions(
    image: Image.Image,
    *,
    expected_count: int,
    skip_leading: int = 0,
) -> list[DetectedRegion]:
    width, height = image.size
    line_candidates = _thin_line_candidates(image)
    selected = _select_layout_candidates(
        line_candidates,
        expected_count=expected_count,
        skip_leading=skip_leading,
    )
    if len(selected) != expected_count:
        raise DetectionError(
            f"expected {expected_count} blank regions, found {len(selected)}"
        )

    regions: list[DetectedRegion] = []
    for index, candidate in enumerate(selected, start=1):
        x = max(0, candidate.x1 - 8)
        y = max(0, int(round(candidate.y)) - 22)
        w = min(width - x, candidate.x2 - candidate.x1 + 16)
        h = min(height - y, 36)
        confidence = min(
            0.99,
            0.86
            + min(candidate.run_count, 48) / 48 * 0.10
            + min(candidate.x2 - candidate.x1, 220) / 220 * 0.03,
        )
        regions.append(
            DetectedRegion(
                pixel=Rect(x=x, y=y, w=w, h=h),
                deterministic_confidence=confidence,
                evidence=[
                    f"blank line {index}: y={candidate.y:.1f}",
                    f"small-dot runs={candidate.run_count}",
                    f"span={candidate.x2 - candidate.x1}px",
                ],
            )
        )
    return regions


def _merge_row_bands(active_rows: np.ndarray, *, max_gap: int = 3) -> list[tuple[int, int]]:
    ys = np.flatnonzero(active_rows)
    if ys.size == 0:
        return []

    bands: list[tuple[int, int]] = []
    start = int(ys[0])
    previous = int(ys[0])
    for y in ys[1:]:
        y_int = int(y)
        if y_int - previous <= max_gap:
            previous = y_int
            continue
        bands.append((start, previous))
        start = previous = y_int
    bands.append((start, previous))
    return bands


def _text_bands(binary_crop: np.ndarray) -> list[_TextBand]:
    row_dark_counts = binary_crop.sum(axis=1)
    active_rows = row_dark_counts >= 8
    bands: list[_TextBand] = []
    for y1, y2 in _merge_row_bands(active_rows):
        band = binary_crop[y1 : y2 + 1]
        dark_pixels = int(band.sum())
        if y2 - y1 + 1 < 3 or dark_pixels < 85:
            continue
        active_columns = np.flatnonzero(band.any(axis=0))
        if active_columns.size == 0:
            continue
        bands.append(
            _TextBand(
                x1=int(active_columns[0]),
                y1=y1,
                x2=int(active_columns[-1]),
                y2=y2,
                dark_pixels=dark_pixels,
            )
        )
    return bands


def _choice_bands_for_expected_shape(
    bands: list[_TextBand],
    *,
    group_count: int,
    options_per_group: int,
) -> list[_TextBand]:
    expected = group_count * options_per_group
    if group_count == 1:
        selected = bands[-expected:]
    else:
        source_group_size = options_per_group + 1
        required = group_count * source_group_size
        source = bands[-required:]
        selected = []
        for group_index in range(group_count):
            start = group_index * source_group_size
            selected.extend(source[start + 1 : start + source_group_size])

    if len(selected) != expected:
        raise DetectionError(
            f"expected {expected} choice regions, found {len(selected)}"
        )
    return selected


def detect_choice_regions(
    image: Image.Image,
    *,
    crop: tuple[int, int, int, int],
    group_count: int,
    options_per_group: int,
) -> list[DetectedRegion]:
    crop_left, crop_top, crop_right, crop_bottom = crop
    if crop_left >= crop_right or crop_top >= crop_bottom:
        raise DetectionError(f"invalid crop rectangle: {crop}")

    grayscale = _grayscale_array(image.crop(crop))
    binary = grayscale < 170
    bands = _text_bands(binary)
    selected = _choice_bands_for_expected_shape(
        bands,
        group_count=group_count,
        options_per_group=options_per_group,
    )

    regions: list[DetectedRegion] = []
    for index, band in enumerate(selected, start=1):
        x = max(0, crop_left + band.x1 - 10)
        y = max(0, crop_top + band.y1 - 7)
        w = band.x2 - band.x1 + 20
        h = band.y2 - band.y1 + 14
        confidence = min(0.99, 0.90 + min(band.dark_pixels, 1200) / 1200 * 0.09)
        regions.append(
            DetectedRegion(
                pixel=Rect(x=x, y=y, w=w, h=h),
                deterministic_confidence=confidence,
                evidence=[
                    f"choice row {index}: crop={crop}",
                    f"text-band dark pixels={band.dark_pixels}",
                ],
            )
        )
    return regions


def material_overlap(first: Rect, second: Rect, *, threshold: float = 0.15) -> bool:
    x1 = max(first.x, second.x)
    y1 = max(first.y, second.y)
    x2 = min(first.x + first.w, second.x + second.w)
    y2 = min(first.y + first.h, second.y + second.h)
    if x2 <= x1 or y2 <= y1:
        return False

    intersection = (x2 - x1) * (y2 - y1)
    smaller_area = min(first.w * first.h, second.w * second.h)
    return intersection / smaller_area > threshold


def load_source_questions(path: Path = QUESTIONS_SOURCE) -> list[Question]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    questions = [Question.model_validate(item) for item in payload]
    validate_questions(questions)
    return questions


def normalize_rect(pixel: Rect, *, page_width: int, page_height: int) -> NormalizedRect:
    return NormalizedRect(
        x=pixel.x / page_width,
        y=pixel.y / page_height,
        w=pixel.w / page_width,
        h=pixel.h / page_height,
    )


def _proposal(
    *,
    question_id: str,
    option_id: str | None,
    page_name: str,
    interaction_type: str,
    region: DetectedRegion,
    page_width: int,
    page_height: int,
) -> dict:
    normalized = normalize_rect(
        region.pixel,
        page_width=page_width,
        page_height=page_height,
    )
    return {
        "questionId": question_id,
        "optionId": option_id,
        "page": page_name,
        "interactionType": interaction_type,
        "pixel": region.pixel.model_dump(),
        "normalized": normalized.model_dump(),
        "deterministicConfidence": round(region.deterministic_confidence, 4),
        "validationEvidence": region.evidence,
    }


def build_overlay_proposals(page_dir: Path = PAGE_ASSET_ROOT) -> list[dict]:
    load_source_questions()
    page_dir = Path(page_dir)
    proposals: list[dict] = []

    blank_specs = [
        ("page-010.png", [f"q{number}" for number in range(1, 7)], 6, 1),
        ("page-011.png", [f"q{number}" for number in range(7, 11)], 4, 0),
        ("page-013.png", [f"q{number}" for number in range(13, 21)], 8, 0),
        ("page-015.png", [f"q{number}" for number in range(26, 31)], 5, 0),
        ("page-016.png", [f"q{number}" for number in range(31, 41)], 10, 0),
    ]
    for page_name, question_ids, expected_count, skip_leading in blank_specs:
        with Image.open(page_dir / page_name) as image:
            regions = detect_blank_regions(
                image,
                expected_count=expected_count,
                skip_leading=skip_leading,
            )
            width, height = image.size
        for question_id, region in zip(question_ids, regions):
            proposals.append(
                _proposal(
                    question_id=question_id,
                    option_id=None,
                    page_name=page_name,
                    interaction_type="blank",
                    region=region,
                    page_width=width,
                    page_height=height,
                )
            )

    with Image.open(page_dir / "page-012.png") as image:
        choice_regions = detect_choice_regions(
            image,
            crop=(140, 330, 700, 500),
            group_count=1,
            options_per_group=5,
        )
        width, height = image.size
    for option_id, region in zip(["A", "B", "C", "D", "E"], choice_regions):
        proposals.append(
            _proposal(
                question_id="q11",
                option_id=option_id,
                page_name="page-012.png",
                interaction_type="choice-option",
                region=region,
                page_width=width,
                page_height=height,
            )
        )

    with Image.open(page_dir / "page-014.png") as image:
        choice_regions = detect_choice_regions(
            image,
            crop=(150, 340, 950, 1050),
            group_count=5,
            options_per_group=3,
        )
        width, height = image.size
    single_choice_targets = [
        (f"q{question_number}", option_id)
        for question_number in range(21, 26)
        for option_id in ["A", "B", "C"]
    ]
    for (question_id, option_id), region in zip(single_choice_targets, choice_regions):
        proposals.append(
            _proposal(
                question_id=question_id,
                option_id=option_id,
                page_name="page-014.png",
                interaction_type="choice-option",
                region=region,
                page_width=width,
                page_height=height,
            )
        )

    return proposals


def write_overlay_proposals(
    output_path: Path = OVERLAY_PROPOSALS,
    questions_output_path: Path = PUBLIC_QUESTIONS,
) -> list[dict]:
    questions = load_source_questions()
    questions_output_path.parent.mkdir(parents=True, exist_ok=True)
    questions_output_path.write_text(
        json.dumps([question.model_dump() for question in questions], indent=2) + "\n",
        encoding="utf-8",
    )

    proposals = build_overlay_proposals()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(proposals, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return proposals


def main() -> None:
    proposals = write_overlay_proposals()
    print(f"wrote {len(proposals)} overlay proposals to {OVERLAY_PROPOSALS}")


if __name__ == "__main__":
    main()
