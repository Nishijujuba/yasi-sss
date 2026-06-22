import type { MarkResult, Question } from "../types/pack";
import { normalizeAnswer } from "./marker";

const PACK_ID = "cambridge-10-test-1-listening";
const NOTEBOOK_VERSION = 2;

export const MISTAKE_VOCABULARY_KEY = "yasi:cambridge-10:test-1:listening:mistake-vocabulary:v1";

export type PracticeResult = "correct" | "incorrect";

export interface MistakeVocabularyItem {
  id: string;
  term: string;
  spokenText: string;
  normalizedTerm: string;
  acceptedVariants: string[];
  meaningZh: string;
  audio: string;
}

export interface MistakeVocabularyPack {
  packId: string;
  questions: Question[];
  vocabulary: MistakeVocabularyItem[];
  questionsById: Map<string, Question>;
}

export interface MistakeVocabularyCardState {
  termId: string;
  createdAt: string;
  mistakeCount: number;
  lastIncorrectResponse: string;
  lastCapturedAt: string;
  practiceAttempts: number;
  practiceCorrect: number;
  masteryCount: number;
  lastPracticeResult: PracticeResult | null;
  lastPracticedAt: string | null;
  dictationAttempts: number;
  dictationCorrect: number;
  lastDictationResult: PracticeResult | null;
  lastDictationAt: string | null;
}

export interface MistakeVocabularyNotebookState {
  version: typeof NOTEBOOK_VERSION;
  packId: typeof PACK_ID;
  cards: Record<string, MistakeVocabularyCardState>;
  archivedCards: Record<string, MistakeVocabularyCardState>;
}

export interface CaptureMistakeVocabularyInput {
  pack: MistakeVocabularyPack;
  result: MarkResult;
  notebook: MistakeVocabularyNotebookState;
  capturedMistakes: Record<string, string>;
  capturedAt?: string;
}

export interface CaptureMistakeVocabularyResult {
  notebook: MistakeVocabularyNotebookState;
  capturedMistakes: Record<string, string>;
}

export interface MistakeVocabularyPracticeQueueEntry {
  key: string;
  card: MistakeVocabularyCardState;
}

type LegacyMistakeVocabularyCardState = Omit<
  MistakeVocabularyCardState,
  "dictationAttempts" | "dictationCorrect" | "lastDictationResult" | "lastDictationAt"
>;

interface LegacyMistakeVocabularyNotebookState {
  version: 1;
  packId: typeof PACK_ID;
  cards: Record<string, LegacyMistakeVocabularyCardState>;
}

export function createEmptyMistakeVocabularyNotebook(): MistakeVocabularyNotebookState {
  return {
    version: NOTEBOOK_VERSION,
    packId: PACK_ID,
    cards: {},
    archivedCards: {},
  };
}

export function saveMistakeVocabularyNotebook(notebook: MistakeVocabularyNotebookState): void {
  localStorage.setItem(MISTAKE_VOCABULARY_KEY, JSON.stringify(notebook));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isPracticeResult(value: unknown): value is PracticeResult | null {
  return value === "correct" || value === "incorrect" || value === null;
}

function isLegacyCardState(value: unknown): value is LegacyMistakeVocabularyCardState {
  return (
    isRecord(value) &&
    typeof value.termId === "string" &&
    typeof value.createdAt === "string" &&
    typeof value.mistakeCount === "number" &&
    typeof value.lastIncorrectResponse === "string" &&
    typeof value.lastCapturedAt === "string" &&
    typeof value.practiceAttempts === "number" &&
    typeof value.practiceCorrect === "number" &&
    typeof value.masteryCount === "number" &&
    isPracticeResult(value.lastPracticeResult) &&
    (typeof value.lastPracticedAt === "string" || value.lastPracticedAt === null)
  );
}

function isCardState(value: unknown): value is MistakeVocabularyCardState {
  if (!isRecord(value)) {
    return false;
  }

  const record = value;
  return (
    isLegacyCardState(value) &&
    typeof record.dictationAttempts === "number" &&
    typeof record.dictationCorrect === "number" &&
    isPracticeResult(record.lastDictationResult) &&
    (typeof record.lastDictationAt === "string" || record.lastDictationAt === null)
  );
}

function isLegacyNotebookState(value: unknown): value is LegacyMistakeVocabularyNotebookState {
  return (
    isRecord(value) &&
    value.version === 1 &&
    value.packId === PACK_ID &&
    isRecord(value.cards) &&
    Object.values(value.cards).every(isLegacyCardState)
  );
}

function hasOverlappingCardKeys(cards: Record<string, unknown>, archivedCards: Record<string, unknown>): boolean {
  return Object.keys(cards).some((key) => Object.hasOwn(archivedCards, key));
}

function isNotebookState(value: unknown): value is MistakeVocabularyNotebookState {
  return (
    isRecord(value) &&
    value.version === NOTEBOOK_VERSION &&
    value.packId === PACK_ID &&
    isRecord(value.cards) &&
    Object.values(value.cards).every(isCardState) &&
    isRecord(value.archivedCards) &&
    Object.values(value.archivedCards).every(isCardState) &&
    !hasOverlappingCardKeys(value.cards, value.archivedCards)
  );
}

function addDefaultDictationState(card: LegacyMistakeVocabularyCardState): MistakeVocabularyCardState {
  return {
    ...card,
    dictationAttempts: 0,
    dictationCorrect: 0,
    lastDictationResult: null,
    lastDictationAt: null,
  };
}

function migrateLegacyNotebook(notebook: LegacyMistakeVocabularyNotebookState): MistakeVocabularyNotebookState {
  return {
    version: NOTEBOOK_VERSION,
    packId: notebook.packId,
    cards: Object.fromEntries(
      Object.entries(notebook.cards).map(([key, card]) => [key, addDefaultDictationState(card)]),
    ),
    archivedCards: {},
  };
}

function archiveMalformedNotebook(raw: string): void {
  const archiveKey = `${MISTAKE_VOCABULARY_KEY}:archived:${new Date().toISOString()}`;
  localStorage.setItem(archiveKey, raw);
  localStorage.removeItem(MISTAKE_VOCABULARY_KEY);
}

export function loadMistakeVocabularyNotebook(): MistakeVocabularyNotebookState {
  const raw = localStorage.getItem(MISTAKE_VOCABULARY_KEY);
  if (raw === null) {
    return createEmptyMistakeVocabularyNotebook();
  }

  try {
    const parsed: unknown = JSON.parse(raw);
    if (isNotebookState(parsed)) {
      return parsed;
    }
    if (isLegacyNotebookState(parsed)) {
      return migrateLegacyNotebook(parsed);
    }
  } catch {
    // User-local state is archived so corrupted data can still be inspected.
  }

  archiveMalformedNotebook(raw);
  return createEmptyMistakeVocabularyNotebook();
}

export function removeMistakeCard(
  notebook: MistakeVocabularyNotebookState,
  cardKey: string,
): MistakeVocabularyNotebookState {
  const nextCards = { ...notebook.cards };
  delete nextCards[cardKey];
  return {
    ...notebook,
    cards: nextCards,
  };
}

export function archiveMistakeCard(
  notebook: MistakeVocabularyNotebookState,
  cardKey: string,
): MistakeVocabularyNotebookState {
  const card = notebook.cards[cardKey];
  if (card === undefined) {
    return notebook;
  }

  const nextCards = { ...notebook.cards };
  delete nextCards[cardKey];

  return {
    ...notebook,
    cards: nextCards,
    archivedCards: {
      ...notebook.archivedCards,
      [cardKey]: card,
    },
  };
}

export function restoreMistakeCard(
  notebook: MistakeVocabularyNotebookState,
  cardKey: string,
): MistakeVocabularyNotebookState {
  const card = notebook.archivedCards[cardKey];
  if (card === undefined) {
    return notebook;
  }

  const nextArchivedCards = { ...notebook.archivedCards };
  delete nextArchivedCards[cardKey];

  if (notebook.cards[cardKey] !== undefined) {
    return {
      ...notebook,
      archivedCards: nextArchivedCards,
    };
  }

  return {
    ...notebook,
    cards: {
      ...notebook.cards,
      [cardKey]: card,
    },
    archivedCards: nextArchivedCards,
  };
}

export function recordMistakePractice(
  notebook: MistakeVocabularyNotebookState,
  cardKey: string,
  correct: boolean,
  practicedAt = new Date().toISOString(),
): MistakeVocabularyNotebookState {
  const card = notebook.cards[cardKey];
  if (card === undefined) {
    return notebook;
  }

  return {
    ...notebook,
    cards: {
      ...notebook.cards,
      [cardKey]: {
        ...card,
        practiceAttempts: card.practiceAttempts + 1,
        practiceCorrect: card.practiceCorrect + (correct ? 1 : 0),
        masteryCount: card.masteryCount + (correct ? 1 : 0),
        lastPracticeResult: correct ? "correct" : "incorrect",
        lastPracticedAt: practicedAt,
      },
    },
  };
}

export function recordMistakeDictation(
  notebook: MistakeVocabularyNotebookState,
  cardKey: string,
  correct: boolean,
  dictatedAt = new Date().toISOString(),
): MistakeVocabularyNotebookState {
  const card = notebook.cards[cardKey];
  if (card === undefined) {
    return notebook;
  }

  return {
    ...notebook,
    cards: {
      ...notebook.cards,
      [cardKey]: {
        ...card,
        mistakeCount: card.mistakeCount + (correct ? 0 : 1),
        dictationAttempts: card.dictationAttempts + 1,
        dictationCorrect: card.dictationCorrect + (correct ? 1 : 0),
        lastDictationResult: correct ? "correct" : "incorrect",
        lastDictationAt: dictatedAt,
      },
    },
  };
}

export function matchesMistakeDictationAnswer(item: MistakeVocabularyItem, actual: string): boolean {
  const normalizedActual = normalizeAnswer(actual);
  if (normalizedActual === "") {
    return false;
  }

  return [item.term, ...item.acceptedVariants].some((accepted) => normalizeAnswer(accepted) === normalizedActual);
}

function findVocabularyItem(
  vocabulary: MistakeVocabularyItem[],
  normalizedCanonicalTerm: string,
): MistakeVocabularyItem | undefined {
  return vocabulary.find(
    (item) =>
      item.id === normalizedCanonicalTerm ||
      normalizeAnswer(item.term) === normalizedCanonicalTerm ||
      normalizeAnswer(item.normalizedTerm) === normalizedCanonicalTerm,
  );
}

function createCard(termId: string, incorrectResponse: string, capturedAt: string): MistakeVocabularyCardState {
  return {
    termId,
    createdAt: capturedAt,
    mistakeCount: 1,
    lastIncorrectResponse: incorrectResponse,
    lastCapturedAt: capturedAt,
    practiceAttempts: 0,
    practiceCorrect: 0,
    masteryCount: 0,
    lastPracticeResult: null,
    lastPracticedAt: null,
    dictationAttempts: 0,
    dictationCorrect: 0,
    lastDictationResult: null,
    lastDictationAt: null,
  };
}

export function captureMistakeVocabulary({
  pack,
  result,
  notebook,
  capturedMistakes,
  capturedAt = new Date().toISOString(),
}: CaptureMistakeVocabularyInput): CaptureMistakeVocabularyResult {
  const nextNotebook: MistakeVocabularyNotebookState = {
    ...notebook,
    cards: { ...notebook.cards },
    archivedCards: { ...notebook.archivedCards },
  };
  const nextCapturedMistakes = { ...capturedMistakes };

  for (const questionResult of Object.values(result.byQuestion)) {
    const question = pack.questionsById.get(questionResult.questionId);
    const trimmedActual = questionResult.actual.trim();

    if (
      question?.responseType !== "blank" ||
      trimmedActual === "" ||
      questionResult.correct ||
      questionResult.expected.length === 0
    ) {
      continue;
    }

    const normalizedActual = normalizeAnswer(questionResult.actual);
    const normalizedCanonicalTerm = normalizeAnswer(questionResult.expected[0]);
    if (normalizedCanonicalTerm === "") {
      continue;
    }

    const vocabularyItem = findVocabularyItem(pack.vocabulary, normalizedCanonicalTerm);
    const termId = vocabularyItem?.id ?? normalizedCanonicalTerm;
    const activeCard = nextNotebook.cards[normalizedCanonicalTerm];
    const archivedCard = nextNotebook.archivedCards[normalizedCanonicalTerm];
    const isDuplicateCaptured = nextCapturedMistakes[questionResult.questionId] === normalizedActual;
    if (isDuplicateCaptured && activeCard !== undefined) {
      continue;
    }

    const existingCard = activeCard ?? archivedCard;
    delete nextNotebook.archivedCards[normalizedCanonicalTerm];

    nextNotebook.cards[normalizedCanonicalTerm] =
      existingCard === undefined
        ? createCard(termId, trimmedActual, capturedAt)
        : {
            ...existingCard,
            mistakeCount: existingCard.mistakeCount + 1,
            lastIncorrectResponse: trimmedActual,
            lastCapturedAt: capturedAt,
          };
    nextCapturedMistakes[questionResult.questionId] = normalizedActual;
  }

  return {
    notebook: nextNotebook,
    capturedMistakes: nextCapturedMistakes,
  };
}

function reviewWrongCount(card: MistakeVocabularyCardState): number {
  return (
    card.practiceAttempts -
    card.practiceCorrect +
    card.dictationAttempts -
    card.dictationCorrect
  );
}

function reviewAccuracy(card: MistakeVocabularyCardState): number | null {
  const attempts = card.practiceAttempts + card.dictationAttempts;
  if (attempts === 0) {
    return null;
  }

  return (card.practiceCorrect + card.dictationCorrect) / attempts;
}

function maxIsoTimestamp(timestamps: Array<string | null>): string | null {
  const present = timestamps.filter((timestamp): timestamp is string => typeof timestamp === "string");
  if (present.length === 0) {
    return null;
  }

  return present.sort((left, right) => right.localeCompare(left))[0];
}

function latestWrongTimestamp(card: MistakeVocabularyCardState): string | null {
  return maxIsoTimestamp([
    card.lastPracticeResult === "incorrect" ? card.lastPracticedAt : null,
    card.lastDictationResult === "incorrect" ? card.lastDictationAt : null,
  ]);
}

function latestActivityTimestamp(card: MistakeVocabularyCardState): string {
  return (
    maxIsoTimestamp([card.lastPracticedAt, card.lastDictationAt, card.lastCapturedAt, card.createdAt]) ??
    card.createdAt
  );
}

function compareNumberDescending(left: number, right: number): number {
  return right - left;
}

function comparePracticeQueueEntries(
  left: MistakeVocabularyPracticeQueueEntry,
  right: MistakeVocabularyPracticeQueueEntry,
): number {
  const mistakeCountComparison = compareNumberDescending(left.card.mistakeCount, right.card.mistakeCount);
  if (mistakeCountComparison !== 0) {
    return mistakeCountComparison;
  }

  const leftWrongAt = latestWrongTimestamp(left.card);
  const rightWrongAt = latestWrongTimestamp(right.card);

  if (leftWrongAt !== null || rightWrongAt !== null) {
    if (leftWrongAt === null) {
      return 1;
    }
    if (rightWrongAt === null) {
      return -1;
    }
    const latestWrongComparison = rightWrongAt.localeCompare(leftWrongAt);
    if (latestWrongComparison !== 0) {
      return latestWrongComparison;
    }
  }

  const wrongCountComparison = compareNumberDescending(reviewWrongCount(left.card), reviewWrongCount(right.card));
  if (wrongCountComparison !== 0) {
    return wrongCountComparison;
  }

  const leftAccuracy = reviewAccuracy(left.card);
  const rightAccuracy = reviewAccuracy(right.card);
  if (leftAccuracy !== null && rightAccuracy !== null && leftAccuracy !== rightAccuracy) {
    return leftAccuracy - rightAccuracy;
  }

  const recencyComparison = latestActivityTimestamp(right.card).localeCompare(latestActivityTimestamp(left.card));
  if (recencyComparison !== 0) {
    return recencyComparison;
  }

  const termComparison = left.card.termId.localeCompare(right.card.termId);
  return termComparison === 0 ? left.key.localeCompare(right.key) : termComparison;
}

export function fullPracticeQueue(notebook: MistakeVocabularyNotebookState): MistakeVocabularyPracticeQueueEntry[] {
  return Object.entries(notebook.cards)
    .map(([key, card]) => ({ key, card }))
    .sort(comparePracticeQueueEntries);
}

export function randomPracticeQueue(
  notebook: MistakeVocabularyNotebookState,
  rng: () => number = Math.random,
): MistakeVocabularyPracticeQueueEntry[] {
  const orderedCards = fullPracticeQueue(notebook);
  if (orderedCards.length <= 10) {
    return orderedCards;
  }

  const pool = [...orderedCards];
  const sampled: MistakeVocabularyPracticeQueueEntry[] = [];
  while (sampled.length < 10 && pool.length > 0) {
    const index = Math.min(Math.floor(rng() * pool.length), pool.length - 1);
    const [card] = pool.splice(index, 1);
    sampled.push(card);
  }

  return sampled;
}
