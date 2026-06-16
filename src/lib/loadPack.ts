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
} from "../types/pack";

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

  for (const key of ["questions", "answers", "overlays", "transcript"] as const) {
    if (typeof value.assets[key] !== "string") {
      throw new Error(`manifest.assets.${key} is required`);
    }
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

function assertTranscriptSection(value: unknown, index: number): asserts value is TranscriptSection {
  if (!isRecord(value)) throw new Error(`transcript[${index}] must be an object`);
  if (typeof value.section !== "number") throw new Error(`transcript[${index}].section is required`);
  if (!Array.isArray(value.segments)) throw new Error(`transcript[${index}].segments is required`);
}

async function fetchJson(url: string): Promise<unknown> {
  const response = await fetch(url);
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

  const [questionsJson, answersJson, overlaysJson, transcriptJson] = await Promise.all([
    fetchJson(joinUrl(normalizedBaseUrl, manifestJson.assets.questions)),
    fetchJson(joinUrl(normalizedBaseUrl, manifestJson.assets.answers)),
    fetchJson(joinUrl(normalizedBaseUrl, manifestJson.assets.overlays)),
    fetchJson(joinUrl(normalizedBaseUrl, manifestJson.assets.transcript)),
  ]);

  if (!Array.isArray(questionsJson)) throw new Error("questions asset must be an array");
  questionsJson.forEach(assertQuestion);
  if (!Array.isArray(answersJson)) throw new Error("answers asset must be an array");
  answersJson.forEach(assertAnswerRule);
  if (!Array.isArray(overlaysJson)) throw new Error("overlays asset must be an array");
  overlaysJson.forEach(assertOverlayRegion);
  if (!Array.isArray(transcriptJson)) throw new Error("transcript asset must be an array");
  transcriptJson.forEach(assertTranscriptSection);

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

  return {
    baseUrl: normalizedBaseUrl,
    manifest: manifestJson,
    questions: questionsJson,
    answers: answersJson,
    overlays: overlaysJson,
    transcript: transcriptJson,
    questionsById,
    answersByQuestionId,
    overlaysByQuestionId,
  };
}
