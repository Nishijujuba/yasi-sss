import type {
  AnswerRule,
  ChoiceOption,
  LoadedPack,
  OverlayRegion,
  PackManifest,
  PackSection,
  Question,
  Rect,
  TranscriptSection,
  TranscriptSegment,
  TranscriptTimingArtifact,
  TranscriptWordTiming,
  VocabularyItem,
} from "../types/pack";
import { tokenizeTranscriptText } from "./transcriptTokens";

const OVERLAY_CONFIDENCE_GATE = 0.85;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((entry) => typeof entry === "string");
}

function isNumberArray(value: unknown): value is number[] {
  return Array.isArray(value) && value.every((entry) => typeof entry === "number");
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function assertChoiceOption(value: unknown, index: number, optionIndex: number): asserts value is ChoiceOption {
  if (!isRecord(value)) throw new Error(`questions[${index}].options[${optionIndex}] must be an object`);
  if (typeof value.id !== "string") throw new Error(`questions[${index}].options[${optionIndex}].id is required`);
  if (typeof value.label !== "string") {
    throw new Error(`questions[${index}].options[${optionIndex}].label is required`);
  }
}

function assertRect(value: unknown, path: string, normalized: boolean): asserts value is Rect {
  if (!isRecord(value)) throw new Error(`${path} must be an object`);
  const { x, y, w, h } = value;
  for (const key of ["x", "y", "w", "h"] as const) {
    if (typeof value[key] !== "number" || Number.isNaN(value[key])) {
      throw new Error(`${path}.${key} must be a number`);
    }
  }
  if (typeof x !== "number" || typeof y !== "number" || typeof w !== "number" || typeof h !== "number") {
    throw new Error(`${path} must contain numeric rectangle values`);
  }
  if (w <= 0 || h <= 0) throw new Error(`${path} must have positive width and height`);
  if (normalized) {
    if (x < 0 || y < 0 || x + w > 1 || y + h > 1) {
      throw new Error(`${path} must stay within normalized page bounds`);
    }
  }
}

function assertPackSection(value: unknown, index: number): asserts value is PackSection {
  if (!isRecord(value)) {
    throw new Error(`manifest.sections[${index}] must be an object`);
  }
  if (typeof value.number !== "number") throw new Error(`manifest.sections[${index}].number is required`);
  if (typeof value.title !== "string") throw new Error(`manifest.sections[${index}].title is required`);
  if (!isNumberArray(value.questionNumbers)) {
    throw new Error(`manifest.sections[${index}].questionNumbers is required`);
  }
  if (typeof value.audio !== "string") throw new Error(`manifest.sections[${index}].audio is required`);
  if (!isStringArray(value.pages)) throw new Error(`manifest.sections[${index}].pages is required`);
}

function assertManifest(value: unknown): asserts value is PackManifest {
  if (!isRecord(value)) {
    throw new Error("manifest must be an object");
  }
  if (typeof value.packId !== "string") throw new Error("manifest.packId is required");
  if (typeof value.schemaVersion !== "number") throw new Error("manifest.schemaVersion is required");
  if (value.status !== "released") throw new Error("manifest must be released");
  if (typeof value.title !== "string") throw new Error("manifest.title is required");
  if (!Array.isArray(value.sections)) throw new Error("manifest.sections is required");
  value.sections.forEach(assertPackSection);
  if (!isRecord(value.assets)) throw new Error("manifest.assets is required");

  for (const key of ["questions", "answers", "overlays", "transcript", "vocabulary"] as const) {
    if (typeof value.assets[key] !== "string") {
      throw new Error(`manifest.assets.${key} is required`);
    }
  }
  if (value.assets.transcriptTimings !== undefined && typeof value.assets.transcriptTimings !== "string") {
    throw new Error("manifest.assets.transcriptTimings must be a string");
  }
}

function assertQuestion(value: unknown, index: number): asserts value is Question {
  if (!isRecord(value)) throw new Error(`questions[${index}] must be an object`);
  if (typeof value.id !== "string") throw new Error(`questions[${index}].id is required`);
  if (typeof value.number !== "number") throw new Error(`questions[${index}].number is required`);
  if (typeof value.section !== "number") throw new Error(`questions[${index}].section is required`);
  if (
    value.responseType !== "blank" &&
    value.responseType !== "single-choice" &&
    value.responseType !== "multi-choice" &&
    value.responseType !== "choice"
  ) {
    throw new Error(`questions[${index}].responseType is required`);
  }
  if (typeof value.page !== "string") throw new Error(`questions[${index}].page is required`);
  if (typeof value.focusOrder !== "number") throw new Error(`questions[${index}].focusOrder is required`);
  if (value.selectionLimit !== null && typeof value.selectionLimit !== "number") {
    throw new Error(`questions[${index}].selectionLimit is required`);
  }
  if (!Array.isArray(value.options)) throw new Error(`questions[${index}].options is required`);
  value.options.forEach((option, optionIndex) => assertChoiceOption(option, index, optionIndex));
}

function assertAnswerRule(value: unknown, index: number): asserts value is AnswerRule {
  if (!isRecord(value)) throw new Error(`answers[${index}] must be an object`);
  if (!isStringArray(value.questionIds)) throw new Error(`answers[${index}].questionIds is required`);
  if (
    !Array.isArray(value.accepted) ||
    !value.accepted.every((tuple) => Array.isArray(tuple) && tuple.every((entry) => typeof entry === "string"))
  ) {
    throw new Error(`answers[${index}].accepted is required`);
  }
  if (typeof value.orderIndependent !== "boolean") {
    throw new Error(`answers[${index}].orderIndependent is required`);
  }
}

function assertOverlayRegion(value: unknown, index: number): asserts value is OverlayRegion {
  if (!isRecord(value)) throw new Error(`overlays[${index}] must be an object`);
  if (typeof value.questionId !== "string") throw new Error(`overlays[${index}].questionId is required`);
  if (value.optionId !== null && typeof value.optionId !== "string") {
    throw new Error(`overlays[${index}].optionId is required`);
  }
  if (typeof value.page !== "string") throw new Error(`overlays[${index}].page is required`);
  if (value.interactionType !== "blank" && value.interactionType !== "choice-option") {
    throw new Error(`overlays[${index}].interactionType is required`);
  }
  assertRect(value.pixel, `overlays[${index}].pixel`, false);
  assertRect(value.normalized, `overlays[${index}].normalized`, true);
  for (const key of ["deterministicConfidence", "visionConfidence", "confidence"] as const) {
    if (typeof value[key] !== "number" || value[key] < OVERLAY_CONFIDENCE_GATE || value[key] > 1) {
      throw new Error(`overlays[${index}].${key} must be at least ${OVERLAY_CONFIDENCE_GATE}`);
    }
  }
  if (!isStringArray(value.validationEvidence)) {
    throw new Error(`overlays[${index}].validationEvidence is required`);
  }
}

function assertTranscriptSegment(
  value: unknown,
  sectionIndex: number,
  segmentIndex: number,
): asserts value is TranscriptSegment {
  if (!isRecord(value)) {
    throw new Error(`transcript[${sectionIndex}].segments[${segmentIndex}] must be an object`);
  }
  if (typeof value.order !== "number") {
    throw new Error(`transcript[${sectionIndex}].segments[${segmentIndex}].order is required`);
  }
  if (typeof value.text !== "string") {
    throw new Error(`transcript[${sectionIndex}].segments[${segmentIndex}].text is required`);
  }
}

function assertTranscriptSection(value: unknown, index: number): asserts value is TranscriptSection {
  if (!isRecord(value)) throw new Error(`transcript[${index}] must be an object`);
  if (typeof value.section !== "number") throw new Error(`transcript[${index}].section is required`);
  if (!Array.isArray(value.segments)) throw new Error(`transcript[${index}].segments is required`);
  value.segments.forEach((segment, segmentIndex) => assertTranscriptSegment(segment, index, segmentIndex));
}

function buildTranscriptTokenCounts(transcript: TranscriptSection[]): Map<string, number> {
  const tokenCounts = new Map<string, number>();
  for (const section of transcript) {
    for (const segment of section.segments) {
      const tokenCount = tokenizeTranscriptText(segment.text).filter((part) => part.kind === "word").length;
      tokenCounts.set(`${section.section}:${segment.order}`, tokenCount);
    }
  }
  return tokenCounts;
}

function assertTranscriptWordTiming(
  value: unknown,
  path: string,
  options: { requireTiming: boolean },
): asserts value is TranscriptWordTiming {
  if (!isRecord(value)) throw new Error(`${path} must be an object`);
  if (!Number.isInteger(value.section)) throw new Error(`${path}.section is required`);
  if (!Number.isInteger(value.segmentOrder)) throw new Error(`${path}.segmentOrder is required`);
  if (!Number.isInteger(value.tokenIndex)) throw new Error(`${path}.tokenIndex is required`);
  if (
    options.requireTiming ||
    (value.start !== undefined && value.start !== null) ||
    (value.end !== undefined && value.end !== null)
  ) {
    if (!isFiniteNumber(value.start) || !isFiniteNumber(value.end)) {
      throw new Error(`${path} must include numeric start and end`);
    }
    if (value.start < 0 || value.end <= value.start) {
      throw new Error(`${path} must have a positive interval`);
    }
  }
  if (value.riskTypes !== undefined && !isStringArray(value.riskTypes)) {
    throw new Error(`${path}.riskTypes must be a string array`);
  }
  if (value.reasons !== undefined && !isStringArray(value.reasons)) {
    throw new Error(`${path}.reasons must be a string array`);
  }
  if (value.requiresReview !== undefined && typeof value.requiresReview !== "boolean") {
    throw new Error(`${path}.requiresReview must be a boolean`);
  }
  if (value.review !== undefined && !isRecord(value.review)) {
    throw new Error(`${path}.review must be an object`);
  }
}

function assertTranscriptTimingArtifact(
  value: unknown,
  transcript: TranscriptSection[],
): asserts value is TranscriptTimingArtifact {
  if (!isRecord(value)) throw new Error("transcriptTimings must be an object");
  if (value.schemaVersion !== "yasi.transcript-timings.v1") {
    throw new Error("transcriptTimings.schemaVersion must be yasi.transcript-timings.v1");
  }
  if (value.status !== "verified" && value.status !== "preview") {
    throw new Error("transcriptTimings.status must be verified or preview");
  }
  if (!Array.isArray(value.sections)) {
    throw new Error("transcriptTimings.sections is required");
  }

  const tokenCounts = buildTranscriptTokenCounts(transcript);
  value.sections.forEach((sectionTiming, sectionIndex) => {
    const sectionPath = `transcriptTimings.sections[${sectionIndex}]`;
    if (!isRecord(sectionTiming)) throw new Error(`${sectionPath} must be an object`);
    if (!Number.isInteger(sectionTiming.section)) throw new Error(`${sectionPath}.section is required`);
    if (sectionTiming.status !== value.status) {
      throw new Error(`${sectionPath}.status must match transcriptTimings.status`);
    }
    if (!Array.isArray(sectionTiming.wordTimings)) throw new Error(`${sectionPath}.wordTimings must be an array`);

    const seenIdentities = new Set<string>();
    sectionTiming.wordTimings.forEach((timing, timingIndex) => {
      const timingPath = `${sectionPath}.wordTimings[${timingIndex}]`;
      assertTranscriptWordTiming(timing, timingPath, { requireTiming: value.status === "verified" });
      if (timing.section !== sectionTiming.section) {
        throw new Error(`${timingPath} section mismatch`);
      }

      const identity = `${timing.section}:${timing.segmentOrder}:${timing.tokenIndex}`;
      if (seenIdentities.has(identity)) {
        throw new Error(`${timingPath} duplicate timing identity ${identity}`);
      }
      seenIdentities.add(identity);

      const tokenCount = tokenCounts.get(`${timing.section}:${timing.segmentOrder}`);
      if (tokenCount === undefined) {
        throw new Error(`${timingPath}.segmentOrder must map to an existing transcript segment`);
      }
      if (timing.tokenIndex < 0 || timing.tokenIndex >= tokenCount) {
        throw new Error(`${timingPath}.tokenIndex must map to a frontend transcript token`);
      }
    });
  });
}

function assertVocabularyItem(value: unknown, index: number): asserts value is VocabularyItem {
  if (!isRecord(value)) throw new Error(`vocabulary[${index}] must be an object`);
  if (typeof value.id !== "string" || value.id.trim() === "") {
    throw new Error(`vocabulary[${index}].id is required`);
  }
  if (typeof value.term !== "string" || value.term.trim() === "") {
    throw new Error(`vocabulary[${index}].term is required`);
  }
  if (typeof value.spokenText !== "string" || value.spokenText.trim() === "") {
    throw new Error(`vocabulary[${index}].spokenText is required`);
  }
  if (typeof value.normalizedTerm !== "string" || value.normalizedTerm.trim() === "") {
    throw new Error(`vocabulary[${index}].normalizedTerm is required`);
  }
  if (!isStringArray(value.acceptedVariants)) {
    throw new Error(`vocabulary[${index}].acceptedVariants is required`);
  }
  if (typeof value.meaningZh !== "string" || value.meaningZh.trim() === "") {
    throw new Error(`vocabulary[${index}].meaningZh is required`);
  }
  if (typeof value.audio !== "string" || value.audio.trim() === "") {
    throw new Error(`vocabulary[${index}].audio is required`);
  }
}

function assertUniqueVocabularyIds(vocabulary: VocabularyItem[]): void {
  const seen = new Set<string>();
  for (const item of vocabulary) {
    if (seen.has(item.id)) {
      throw new Error(`duplicate vocabulary id: ${item.id}`);
    }
    seen.add(item.id);
  }
}

async function fetchJson(url: string): Promise<unknown> {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to fetch ${url}: ${response.status}`);
  }
  return response.json();
}

function joinUrl(baseUrl: string, path: string): string {
  return `${baseUrl.replace(/\/+$/, "")}/${path.replace(/^\/+/, "")}`;
}

export async function loadPack(baseUrl = "/packs/cambridge-10/test-1/listening"): Promise<LoadedPack> {
  const normalizedBaseUrl = baseUrl.replace(/\/+$/, "");
  const manifestJson = await fetchJson(joinUrl(normalizedBaseUrl, "manifest.json"));
  assertManifest(manifestJson);

  const [questionsJson, answersJson, overlaysJson, transcriptJson, vocabularyJson, transcriptTimingsJson] =
    await Promise.all([
      fetchJson(joinUrl(normalizedBaseUrl, manifestJson.assets.questions)),
      fetchJson(joinUrl(normalizedBaseUrl, manifestJson.assets.answers)),
      fetchJson(joinUrl(normalizedBaseUrl, manifestJson.assets.overlays)),
      fetchJson(joinUrl(normalizedBaseUrl, manifestJson.assets.transcript)),
      fetchJson(joinUrl(normalizedBaseUrl, manifestJson.assets.vocabulary)),
      manifestJson.assets.transcriptTimings === undefined
        ? Promise.resolve(null)
        : fetchJson(joinUrl(normalizedBaseUrl, manifestJson.assets.transcriptTimings)),
    ]);

  if (!Array.isArray(questionsJson)) throw new Error("questions asset must be an array");
  questionsJson.forEach(assertQuestion);
  if (!Array.isArray(answersJson)) throw new Error("answers asset must be an array");
  answersJson.forEach(assertAnswerRule);
  if (!Array.isArray(overlaysJson)) throw new Error("overlays asset must be an array");
  overlaysJson.forEach(assertOverlayRegion);
  if (!Array.isArray(transcriptJson)) throw new Error("transcript asset must be an array");
  transcriptJson.forEach(assertTranscriptSection);
  if (!Array.isArray(vocabularyJson)) throw new Error("vocabulary asset must be an array");
  vocabularyJson.forEach(assertVocabularyItem);
  assertUniqueVocabularyIds(vocabularyJson);
  if (transcriptTimingsJson !== null) {
    assertTranscriptTimingArtifact(transcriptTimingsJson, transcriptJson);
  }

  const questionsById = new Map(questionsJson.map((question) => [question.id, question]));
  const answersByQuestionId = new Map<string, AnswerRule>();
  for (const answer of answersJson) {
    for (const questionId of answer.questionIds) {
      answersByQuestionId.set(questionId, answer);
    }
  }
  const overlaysByQuestionId = new Map<string, OverlayRegion[]>();
  for (const overlay of overlaysJson) {
    const current = overlaysByQuestionId.get(overlay.questionId) ?? [];
    current.push(overlay);
    overlaysByQuestionId.set(overlay.questionId, current);
  }
  const vocabularyById = new Map(vocabularyJson.map((item) => [item.id, item]));

  return {
    baseUrl: normalizedBaseUrl,
    manifest: manifestJson,
    questions: questionsJson,
    answers: answersJson,
    overlays: overlaysJson,
    transcript: transcriptJson,
    transcriptTimings: transcriptTimingsJson,
    vocabulary: vocabularyJson,
    questionsById,
    answersByQuestionId,
    overlaysByQuestionId,
    vocabularyById,
  };
}
