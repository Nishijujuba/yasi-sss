import type { MarkResult, Question } from "../types/pack";
import { normalizeAnswer } from "./marker";

const PACK_ID = "cambridge-10-test-1-listening";

export const MISTAKE_VOCABULARY_KEY = "yasi:cambridge-10:test-1:listening:mistake-vocabulary:v1";

export type PracticeResult = "correct" | "incorrect";

export interface MistakeVocabularyItem {
  id: string;
  term: string;
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
}

export interface MistakeVocabularyNotebookState {
  version: 1;
  packId: typeof PACK_ID;
  cards: Record<string, MistakeVocabularyCardState>;
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

export function createEmptyMistakeVocabularyNotebook(): MistakeVocabularyNotebookState {
  return {
    version: 1,
    packId: PACK_ID,
    cards: {},
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

function isCardState(value: unknown): value is MistakeVocabularyCardState {
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

function isNotebookState(value: unknown): value is MistakeVocabularyNotebookState {
  return (
    isRecord(value) &&
    value.version === 1 &&
    value.packId === PACK_ID &&
    isRecord(value.cards) &&
    Object.values(value.cards).every(isCardState)
  );
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
    if (nextCapturedMistakes[questionResult.questionId] === normalizedActual) {
      continue;
    }

    const normalizedCanonicalTerm = normalizeAnswer(questionResult.expected[0]);
    if (normalizedCanonicalTerm === "") {
      continue;
    }

    const vocabularyItem = findVocabularyItem(pack.vocabulary, normalizedCanonicalTerm);
    const termId = vocabularyItem?.id ?? normalizedCanonicalTerm;
    const existingCard = nextNotebook.cards[normalizedCanonicalTerm];

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

export function fullPracticeQueue(notebook: MistakeVocabularyNotebookState): MistakeVocabularyCardState[] {
  return Object.values(notebook.cards).sort((left, right) => {
    const createdAtComparison = left.createdAt.localeCompare(right.createdAt);
    return createdAtComparison === 0 ? left.termId.localeCompare(right.termId) : createdAtComparison;
  });
}

export function randomPracticeQueue(
  notebook: MistakeVocabularyNotebookState,
  rng: () => number = Math.random,
): MistakeVocabularyCardState[] {
  const orderedCards = fullPracticeQueue(notebook);
  if (orderedCards.length <= 10) {
    return orderedCards;
  }

  const pool = [...orderedCards];
  const sampled: MistakeVocabularyCardState[] = [];
  while (sampled.length < 10 && pool.length > 0) {
    const index = Math.min(Math.floor(rng() * pool.length), pool.length - 1);
    const [card] = pool.splice(index, 1);
    sampled.push(card);
  }

  return sampled;
}
