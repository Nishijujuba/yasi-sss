from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from builder.config import OVERLAY_CONFIDENCE_GATE, SCHEMA_ROOT, SCHEMA_VERSION


class PackModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Rect(PackModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    w: float = Field(gt=0)
    h: float = Field(gt=0)
    normalized: bool = Field(default=False, exclude=True)

    @model_validator(mode="after")
    def validate_page_bounds(self) -> Rect:
        if self.normalized and (self.x + self.w > 1 or self.y + self.h > 1):
            raise ValueError("normalized rectangle must stay within the page")
        return self


class NormalizedRect(PackModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def validate_page_bounds(self) -> NormalizedRect:
        if self.x + self.w > 1 or self.y + self.h > 1:
            raise ValueError("normalized rectangle must stay within the page")
        return self


class ChoiceOption(PackModel):
    id: str
    label: str


class Question(PackModel):
    id: str
    number: int = Field(ge=1, le=40)
    section: int = Field(ge=1, le=4)
    responseType: Literal["blank", "single-choice", "multi-choice"]
    page: str
    focusOrder: int = Field(ge=1)
    selectionLimit: int | None = Field(default=None, ge=1)
    groupId: str | None = None
    options: list[ChoiceOption] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_response_shape(self) -> Question:
        if self.responseType == "blank":
            if self.options or self.selectionLimit is not None:
                raise ValueError("blank questions cannot define choices")
            return self
        if not self.options:
            raise ValueError("choice questions require options")
        if self.responseType == "single-choice" and self.selectionLimit not in {None, 1}:
            raise ValueError("single-choice selection limit must be one")
        if self.responseType == "multi-choice" and self.selectionLimit is None:
            raise ValueError("multi-choice questions require a selection limit")
        return self


class AnswerEvidence(PackModel):
    kind: Literal[
        "official-answer-key",
        "official-audioscript",
        "internet-candidate",
        "user-approval",
    ]
    source: str
    page: int | None = None
    detail: str
    sourceUrl: str | None = None
    accessedAt: str | None = None


class Answer(PackModel):
    questionIds: list[str] = Field(min_length=1)
    accepted: list[list[str]] = Field(min_length=1)
    orderIndependent: bool = False
    provenance: list[AnswerEvidence] = Field(min_length=1)
    reviewStatus: Literal["official", "user-confirmed"]

    @model_validator(mode="after")
    def validate_grouped_answers(self) -> Answer:
        expected_size = len(self.questionIds)
        for accepted_group in self.accepted:
            if len(accepted_group) != expected_size:
                raise ValueError("accepted answer group size must match questionIds")
        if expected_size > 1 and not self.orderIndependent:
            raise ValueError("multi-question answer groups must be order independent")
        return self


Confidence = Annotated[float, Field(ge=OVERLAY_CONFIDENCE_GATE, le=1)]


class Overlay(PackModel):
    questionId: str
    optionId: str | None = None
    page: str
    interactionType: Literal["blank", "choice-option"]
    pixel: Rect
    normalized: NormalizedRect
    deterministicConfidence: Confidence
    visionConfidence: Confidence
    confidence: Confidence
    validationEvidence: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_option_identity(self) -> Overlay:
        if self.interactionType == "choice-option" and self.optionId is None:
            raise ValueError("choice overlays require optionId")
        if self.interactionType == "blank" and self.optionId is not None:
            raise ValueError("blank overlays cannot define optionId")
        return self


class TranscriptSegment(PackModel):
    order: int = Field(ge=1)
    speaker: str | None = None
    text: str = Field(min_length=1)
    answerRefs: list[int] = Field(default_factory=list)
    startTime: None = None
    endTime: None = None


class TranscriptSection(PackModel):
    section: int = Field(ge=1, le=4)
    source: dict
    segments: list[TranscriptSegment] = Field(min_length=1)
    review: dict

    @model_validator(mode="after")
    def validate_segment_order(self) -> TranscriptSection:
        orders = [segment.order for segment in self.segments]
        if orders != list(range(1, len(orders) + 1)):
            raise ValueError("transcript segment order must be contiguous")
        return self


class SectionManifest(PackModel):
    number: int = Field(ge=1, le=4)
    title: str
    questionNumbers: list[int] = Field(min_length=10, max_length=10)
    audio: str
    pages: list[str] = Field(min_length=1)


class ManifestAssets(PackModel):
    questions: str
    answers: str
    overlays: str
    transcript: str


class BuildMetadata(PackModel):
    sourceCommit: str
    builtAt: datetime


class Manifest(PackModel):
    packId: str
    schemaVersion: Literal[SCHEMA_VERSION]
    status: Literal["building", "blocked", "released"]
    title: str
    sections: list[SectionManifest] = Field(min_length=4, max_length=4)
    assets: ManifestAssets
    build: BuildMetadata


class ReleasedManifest(Manifest):
    status: Literal["released"]


class PendingAnswerCandidate(PackModel):
    questionNumber: int = Field(ge=1, le=40)
    status: Literal["pending", "approved", "rejected"]
    candidate: str
    sourceUrl: str
    accessedAt: str
    questionCrop: str
    answerKeyCrop: str
    transcriptEvidence: str
    decision: str | None = None


class ReleaseReport(PackModel):
    status: Literal["blocked", "released"]
    questionCoverage: list[int]
    overlayCount: int = Field(ge=0)
    answerCount: int = Field(ge=0)
    transcriptSections: list[int]
    audioSections: list[int]
    pageAssets: list[str]
    pendingAnswerCandidates: int = Field(ge=0)
    errors: list[str] = Field(default_factory=list)


def validate_question_coverage(values: Iterable[int | Question]) -> None:
    numbers = [
        value.number if isinstance(value, Question) else int(value)
        for value in values
    ]
    if sorted(numbers) != list(range(1, 41)):
        raise ValueError("question coverage must be exactly 1 through 40")


def export_json_schemas(output_dir: Path = SCHEMA_ROOT) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    models: dict[str, type[BaseModel]] = {
        "manifest": Manifest,
        "released-manifest": ReleasedManifest,
        "questions": Question,
        "answers": Answer,
        "overlays": Overlay,
        "transcript-section": TranscriptSection,
        "answer-review": PendingAnswerCandidate,
        "release-report": ReleaseReport,
    }
    for name, model in models.items():
        output = output_dir / f"{name}.schema.json"
        output.write_text(
            json.dumps(model.model_json_schema(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    export_json_schemas()
