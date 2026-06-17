import { beforeEach, describe, expect, it, vi } from "vitest";
import type { MarkResult, Question } from "../types/pack";
import {
  MISTAKE_VOCABULARY_KEY,
  captureMistakeVocabulary,
  createEmptyMistakeVocabularyNotebook,
  fullPracticeQueue,
  loadMistakeVocabularyNotebook,
  randomPracticeQueue,
  recordMistakePractice,
  removeMistakeCard,
  saveMistakeVocabularyNotebook,
  type MistakeVocabularyPack,
  type MistakeVocabularyNotebookState,
} from "./mistakeVocabulary";

const questions: Question[] = [
  blankQuestion("q1", 1),
  blankQuestion("q2", 2),
  choiceQuestion("q3", 3),
  blankQuestion("q4", 4),
];

const pack: MistakeVocabularyPack = {
  packId: "cambridge-10-test-1-listening",
  questions,
  vocabulary: [
    {
      id: "ardleigh",
      term: "Ardleigh",
      normalizedTerm: "ardleigh",
      acceptedVariants: [],
      meaningZh: "阿德利",
      audio: "assets/audio/vocabulary/ardleigh.mp3",
    },
    {
      id: "photo-card",
      term: "photo card",
      normalizedTerm: "photo card",
      acceptedVariants: ["photo cards"],
      meaningZh: "照片卡",
      audio: "assets/audio/vocabulary/photo-card.mp3",
    },
  ],
  questionsById: new Map(questions.map((question) => [question.id, question])),
};

function blankQuestion(id: string, number: number): Question {
  return {
    id,
    number,
    section: 1,
    responseType: "blank",
    page: "page-010.png",
    focusOrder: number,
    selectionLimit: null,
    options: [],
  };
}

function choiceQuestion(id: string, number: number): Question {
  return {
    id,
    number,
    section: 1,
    responseType: "choice",
    page: "page-010.png",
    focusOrder: number,
    selectionLimit: 1,
    options: [
      { id: "A", label: "A" },
      { id: "B", label: "B" },
    ],
  };
}

function result(byQuestion: MarkResult["byQuestion"]): MarkResult {
  const incorrectIds = Object.values(byQuestion)
    .filter((questionResult) => !questionResult.correct)
    .map((questionResult) => questionResult.questionId);

  return {
    score: Object.keys(byQuestion).length - incorrectIds.length,
    total: Object.keys(byQuestion).length,
    byQuestion,
    incorrectIds,
  };
}

function notebookWithCards(count: number): MistakeVocabularyNotebookState {
  const notebook = createEmptyMistakeVocabularyNotebook();
  const base = Date.parse("2026-06-16T04:00:00.000Z");

  for (let index = 0; index < count; index += 1) {
    const id = `term-${index + 1}`;
    notebook.cards[id] = {
      termId: id,
      createdAt: new Date(base + index * 1000).toISOString(),
      mistakeCount: 1,
      lastIncorrectResponse: `wrong-${index + 1}`,
      lastCapturedAt: new Date(base + index * 1000).toISOString(),
      practiceAttempts: 0,
      practiceCorrect: 0,
      masteryCount: 0,
      lastPracticeResult: null,
      lastPracticedAt: null,
    };
  }

  return notebook;
}

describe("mistake vocabulary notebook", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.useRealTimers();
  });

  it("saves notebook state under the independent mistake vocabulary key", () => {
    const notebook = createEmptyMistakeVocabularyNotebook();

    saveMistakeVocabularyNotebook(notebook);

    expect(localStorage.getItem(MISTAKE_VOCABULARY_KEY)).toBe(JSON.stringify(notebook));
  });

  it("loads a valid notebook and archives malformed state", () => {
    vi.setSystemTime(new Date("2026-06-16T04:30:00.000Z"));
    const notebook = notebookWithCards(1);
    localStorage.setItem(MISTAKE_VOCABULARY_KEY, JSON.stringify(notebook));

    expect(loadMistakeVocabularyNotebook()).toEqual(notebook);

    localStorage.setItem(MISTAKE_VOCABULARY_KEY, JSON.stringify({ version: 1, cards: [] }));

    expect(loadMistakeVocabularyNotebook()).toEqual(createEmptyMistakeVocabularyNotebook());
    expect(localStorage.getItem(MISTAKE_VOCABULARY_KEY)).toBeNull();
    expect(
      localStorage.getItem(`${MISTAKE_VOCABULARY_KEY}:archived:2026-06-16T04:30:00.000Z`),
    ).toBe(JSON.stringify({ version: 1, cards: [] }));
  });

  it("removes cards and records practice outcomes", () => {
    vi.setSystemTime(new Date("2026-06-16T04:40:00.000Z"));
    const notebook = notebookWithCards(2);

    const removed = removeMistakeCard(notebook, "term-1");
    const practiced = recordMistakePractice(removed, "term-2", true);

    expect(removed.cards["term-1"]).toBeUndefined();
    expect(practiced.cards["term-2"]).toMatchObject({
      practiceAttempts: 1,
      practiceCorrect: 1,
      masteryCount: 1,
      lastPracticeResult: "correct",
      lastPracticedAt: "2026-06-16T04:40:00.000Z",
    });
  });

  it("captures only non-empty incorrect blank responses and stores no question history on the card", () => {
    const submitted = result({
      q1: { questionId: "q1", correct: false, expected: ["Ardleigh"], actual: "Ardley" },
      q2: { questionId: "q2", correct: false, expected: ["photo card"], actual: "" },
      q3: { questionId: "q3", correct: false, expected: ["B"], actual: "A" },
      q4: { questionId: "q4", correct: true, expected: ["photo card"], actual: "photo card" },
    });

    const captured = captureMistakeVocabulary({
      pack,
      result: submitted,
      notebook: createEmptyMistakeVocabularyNotebook(),
      capturedMistakes: {},
      capturedAt: "2026-06-16T04:10:00.000Z",
    });

    expect(Object.keys(captured.notebook.cards)).toEqual(["ardleigh"]);
    expect(captured.notebook.cards.ardleigh).toEqual({
      termId: "ardleigh",
      createdAt: "2026-06-16T04:10:00.000Z",
      mistakeCount: 1,
      lastIncorrectResponse: "Ardley",
      lastCapturedAt: "2026-06-16T04:10:00.000Z",
      practiceAttempts: 0,
      practiceCorrect: 0,
      masteryCount: 0,
      lastPracticeResult: null,
      lastPracticedAt: null,
    });
    expect(captured.capturedMistakes).toEqual({ q1: "ardley" });
    expect(captured.notebook.cards.ardleigh).not.toHaveProperty("questionId");
    expect(captured.notebook.cards.ardleigh).not.toHaveProperty("questionNumber");
  });

  it("keeps duplicate submissions idempotent and increments changed wrong responses", () => {
    const firstResult = result({
      q1: { questionId: "q1", correct: false, expected: ["Ardleigh"], actual: "Ardley" },
    });
    const first = captureMistakeVocabulary({
      pack,
      result: firstResult,
      notebook: createEmptyMistakeVocabularyNotebook(),
      capturedMistakes: {},
      capturedAt: "2026-06-16T04:10:00.000Z",
    });

    const duplicate = captureMistakeVocabulary({
      pack,
      result: result({
        q1: { questionId: "q1", correct: false, expected: ["Ardleigh"], actual: " ardley " },
      }),
      notebook: first.notebook,
      capturedMistakes: first.capturedMistakes,
      capturedAt: "2026-06-16T04:11:00.000Z",
    });

    const changed = captureMistakeVocabulary({
      pack,
      result: result({
        q1: { questionId: "q1", correct: false, expected: ["Ardleigh"], actual: "Ardly" },
      }),
      notebook: duplicate.notebook,
      capturedMistakes: duplicate.capturedMistakes,
      capturedAt: "2026-06-16T04:12:00.000Z",
    });

    expect(duplicate.notebook.cards.ardleigh.mistakeCount).toBe(1);
    expect(duplicate.notebook.cards.ardleigh.lastCapturedAt).toBe("2026-06-16T04:10:00.000Z");
    expect(changed.notebook.cards.ardleigh.mistakeCount).toBe(2);
    expect(changed.notebook.cards.ardleigh.lastIncorrectResponse).toBe("Ardly");
    expect(changed.capturedMistakes).toEqual({ q1: "ardly" });
  });

  it("uses the normalized canonical term as the card key and stores the vocabulary id", () => {
    const captured = captureMistakeVocabulary({
      pack,
      result: result({
        q4: { questionId: "q4", correct: false, expected: ["photo card", "photo cards"], actual: "photo" },
      }),
      notebook: createEmptyMistakeVocabularyNotebook(),
      capturedMistakes: {},
      capturedAt: "2026-06-16T04:15:00.000Z",
    });

    expect(Object.keys(captured.notebook.cards)).toEqual(["photo card"]);
    expect(captured.notebook.cards["photo card"].termId).toBe("photo-card");
  });

  it("creates a full practice queue ordered by card creation time", () => {
    const notebook = notebookWithCards(3);
    notebook.cards["term-1"].createdAt = "2026-06-16T04:03:00.000Z";
    notebook.cards["term-3"].createdAt = "2026-06-16T04:01:00.000Z";

    expect(fullPracticeQueue(notebook).map((card) => card.termId)).toEqual([
      "term-2",
      "term-3",
      "term-1",
    ]);
  });

  it("creates a one-time random sample of ten cards with injected RNG", () => {
    const notebook = notebookWithCards(12);
    const rngValues = [0.75, 0.5, 0.25, 0, 0.9, 0.1, 0.2, 0.3, 0.4, 0.6, 0.8];
    const rng = () => rngValues.shift() ?? 0;

    expect(randomPracticeQueue(notebook, rng).map((card) => card.termId)).toEqual([
      "term-10",
      "term-6",
      "term-3",
      "term-1",
      "term-12",
      "term-2",
      "term-5",
      "term-7",
      "term-8",
      "term-9",
    ]);
  });

  it("uses all cards for random practice when the notebook has fewer than ten", () => {
    expect(randomPracticeQueue(notebookWithCards(3), () => 0).map((card) => card.termId)).toEqual([
      "term-1",
      "term-2",
      "term-3",
    ]);
  });
});
