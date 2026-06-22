import { beforeEach, describe, expect, it, vi } from "vitest";
import type { MarkResult, Question } from "../types/pack";
import {
  MISTAKE_VOCABULARY_KEY,
  archiveMistakeCard,
  captureMistakeVocabulary,
  createEmptyMistakeVocabularyNotebook,
  fullPracticeQueue,
  loadMistakeVocabularyNotebook,
  matchesMistakeDictationAnswer,
  randomPracticeQueue,
  recordMistakeDictation,
  recordMistakePractice,
  removeMistakeCard,
  restoreMistakeCard,
  saveMistakeVocabularyNotebook,
  type MistakeVocabularyPack,
  type MistakeVocabularyNotebookState,
} from "./mistakeVocabulary";

type CardStateForTest = MistakeVocabularyNotebookState["cards"][string] & {
  dictationAttempts: number;
  dictationCorrect: number;
  lastDictationResult: "correct" | "incorrect" | null;
  lastDictationAt: string | null;
};

type NotebookStateForTest = Omit<MistakeVocabularyNotebookState, "cards" | "version"> & {
  version: 2;
  cards: Record<string, CardStateForTest>;
  archivedCards: Record<string, CardStateForTest>;
};

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
      spokenText: "Ardleigh",
      normalizedTerm: "ardleigh",
      acceptedVariants: [],
      meaningZh: "阿德利",
      audio: "assets/audio/vocabulary/ardleigh.mp3",
    },
    {
      id: "photo-card",
      term: "photo card",
      spokenText: "photo card",
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

function asV2(notebook: MistakeVocabularyNotebookState): NotebookStateForTest {
  return notebook as unknown as NotebookStateForTest;
}

function cardState(
  termId: string,
  timestamp: string,
  overrides: Partial<CardStateForTest> = {},
): CardStateForTest {
  return {
    termId,
    createdAt: timestamp,
    mistakeCount: 1,
    lastIncorrectResponse: `wrong-${termId}`,
    lastCapturedAt: timestamp,
    practiceAttempts: 0,
    practiceCorrect: 0,
    masteryCount: 0,
    lastPracticeResult: null,
    lastPracticedAt: null,
    dictationAttempts: 0,
    dictationCorrect: 0,
    lastDictationResult: null,
    lastDictationAt: null,
    ...overrides,
  };
}

function notebookWithCards(count: number): MistakeVocabularyNotebookState {
  const notebook = {
    version: 2,
    packId: "cambridge-10-test-1-listening",
    cards: {},
    archivedCards: {},
  } as unknown as MistakeVocabularyNotebookState;
  const base = Date.parse("2026-06-16T04:00:00.000Z");

  for (let index = 0; index < count; index += 1) {
    const id = `term-${index + 1}`;
    const timestamp = new Date(base + index * 1000).toISOString();
    asV2(notebook).cards[id] = cardState(id, timestamp, {
      lastIncorrectResponse: `wrong-${index + 1}`,
    });
  }

  return notebook;
}

describe("mistake vocabulary notebook", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.useRealTimers();
  });

  it("keeps the localStorage key stable while creating v2 notebook state", () => {
    expect(MISTAKE_VOCABULARY_KEY).toBe("yasi:cambridge-10:test-1:listening:mistake-vocabulary:v1");
    expect(createEmptyMistakeVocabularyNotebook()).toEqual({
      version: 2,
      packId: "cambridge-10-test-1-listening",
      cards: {},
      archivedCards: {},
    });
  });

  it("saves notebook state under the independent mistake vocabulary key", () => {
    const notebook = createEmptyMistakeVocabularyNotebook();

    saveMistakeVocabularyNotebook(notebook);

    expect(localStorage.getItem(MISTAKE_VOCABULARY_KEY)).toBe(JSON.stringify(notebook));
  });

  it("loads a valid v1 notebook by migrating it to v2", () => {
    const legacyCard = {
      termId: "ardleigh",
      createdAt: "2026-06-16T04:00:00.000Z",
      mistakeCount: 2,
      lastIncorrectResponse: "Ardley",
      lastCapturedAt: "2026-06-16T04:10:00.000Z",
      practiceAttempts: 1,
      practiceCorrect: 0,
      masteryCount: 0,
      lastPracticeResult: "incorrect",
      lastPracticedAt: "2026-06-16T04:20:00.000Z",
    };
    localStorage.setItem(
      MISTAKE_VOCABULARY_KEY,
      JSON.stringify({
        version: 1,
        packId: "cambridge-10-test-1-listening",
        cards: { ardleigh: legacyCard },
      }),
    );

    expect(loadMistakeVocabularyNotebook()).toEqual({
      version: 2,
      packId: "cambridge-10-test-1-listening",
      cards: {
        ardleigh: {
          ...legacyCard,
          dictationAttempts: 0,
          dictationCorrect: 0,
          lastDictationResult: null,
          lastDictationAt: null,
        },
      },
      archivedCards: {},
    });
  });

  it("loads a valid v2 notebook as-is and archives malformed state", () => {
    vi.setSystemTime(new Date("2026-06-16T04:30:00.000Z"));
    const notebook = notebookWithCards(1);
    asV2(notebook).archivedCards["term-2"] = cardState("term-2", "2026-06-16T03:59:00.000Z", {
      dictationAttempts: 3,
      dictationCorrect: 1,
      lastDictationResult: "incorrect",
      lastDictationAt: "2026-06-16T04:25:00.000Z",
    });
    localStorage.setItem(MISTAKE_VOCABULARY_KEY, JSON.stringify(notebook));

    expect(loadMistakeVocabularyNotebook()).toEqual(notebook);

    localStorage.setItem(MISTAKE_VOCABULARY_KEY, JSON.stringify({ version: 1, cards: [] }));

    expect(loadMistakeVocabularyNotebook()).toEqual(createEmptyMistakeVocabularyNotebook());
    expect(localStorage.getItem(MISTAKE_VOCABULARY_KEY)).toBeNull();
    expect(
      localStorage.getItem(`${MISTAKE_VOCABULARY_KEY}:archived:2026-06-16T04:30:00.000Z`),
    ).toBe(JSON.stringify({ version: 1, cards: [] }));
  });

  it("archives malformed v2 notebook state when active and archived keys overlap", () => {
    vi.setSystemTime(new Date("2026-06-16T04:31:00.000Z"));
    const notebook = notebookWithCards(1);
    asV2(notebook).archivedCards["term-1"] = cardState("archived-term-1", "2026-06-16T03:50:00.000Z");
    const raw = JSON.stringify(notebook);
    localStorage.setItem(MISTAKE_VOCABULARY_KEY, raw);

    expect(loadMistakeVocabularyNotebook()).toEqual(createEmptyMistakeVocabularyNotebook());
    expect(localStorage.getItem(MISTAKE_VOCABULARY_KEY)).toBeNull();
    expect(localStorage.getItem(`${MISTAKE_VOCABULARY_KEY}:archived:2026-06-16T04:31:00.000Z`)).toBe(raw);
  });

  it("removes only active cards and records practice outcomes", () => {
    vi.setSystemTime(new Date("2026-06-16T04:40:00.000Z"));
    const notebook = notebookWithCards(2);
    asV2(notebook).archivedCards["term-1"] = cardState("archived-term-1", "2026-06-16T03:50:00.000Z", {
      dictationAttempts: 2,
      dictationCorrect: 1,
      lastDictationResult: "correct",
      lastDictationAt: "2026-06-16T03:55:00.000Z",
    });

    const removed = removeMistakeCard(notebook, "term-1");
    const practiced = recordMistakePractice(removed, "term-2", true);

    expect(removed.cards["term-1"]).toBeUndefined();
    expect(asV2(removed).archivedCards["term-1"]).toEqual(asV2(notebook).archivedCards["term-1"]);
    expect(practiced.cards["term-2"]).toMatchObject({
      practiceAttempts: 1,
      practiceCorrect: 1,
      masteryCount: 1,
      lastPracticeResult: "correct",
      lastPracticedAt: "2026-06-16T04:40:00.000Z",
    });
  });

  it("archives and restores active cards while preserving statistics", () => {
    const notebook = notebookWithCards(1);
    asV2(notebook).cards["term-1"] = cardState("term-1", "2026-06-16T04:00:00.000Z", {
      mistakeCount: 3,
      practiceAttempts: 4,
      practiceCorrect: 2,
      masteryCount: 1,
      lastPracticeResult: "incorrect",
      lastPracticedAt: "2026-06-16T04:30:00.000Z",
      dictationAttempts: 2,
      dictationCorrect: 1,
      lastDictationResult: "correct",
      lastDictationAt: "2026-06-16T04:35:00.000Z",
    });
    const originalCard = asV2(notebook).cards["term-1"];

    expect(archiveMistakeCard(notebook, "missing")).toBe(notebook);

    const archived = archiveMistakeCard(notebook, "term-1");
    expect(asV2(archived).cards["term-1"]).toBeUndefined();
    expect(asV2(archived).archivedCards["term-1"]).toEqual(originalCard);

    expect(restoreMistakeCard(archived, "missing")).toBe(archived);

    const restored = restoreMistakeCard(archived, "term-1");
    expect(asV2(restored).cards["term-1"]).toEqual(originalCard);
    expect(asV2(restored).archivedCards["term-1"]).toBeUndefined();
  });

  it("restores overlapping cards by preserving active state and clearing the archived duplicate", () => {
    const notebook = notebookWithCards(1);
    const activeCard = cardState("term-1", "2026-06-16T04:00:00.000Z", {
      mistakeCount: 7,
      lastIncorrectResponse: "active-wrong",
      lastCapturedAt: "2026-06-16T04:20:00.000Z",
    });
    const archivedCard = cardState("term-1", "2026-06-16T03:00:00.000Z", {
      mistakeCount: 2,
      lastIncorrectResponse: "archived-wrong",
      lastCapturedAt: "2026-06-16T03:20:00.000Z",
    });
    asV2(notebook).cards["term-1"] = activeCard;
    asV2(notebook).archivedCards["term-1"] = archivedCard;

    const restored = restoreMistakeCard(notebook, "term-1");

    expect(restored.cards["term-1"]).toEqual(activeCard);
    expect(asV2(restored).archivedCards["term-1"]).toBeUndefined();
  });

  it("records dictation attempts and keeps missing cards unchanged", () => {
    const notebook = notebookWithCards(1);

    expect(recordMistakeDictation(notebook, "missing", false, "2026-06-16T04:41:00.000Z")).toBe(notebook);

    const incorrect = recordMistakeDictation(notebook, "term-1", false, "2026-06-16T04:41:00.000Z");
    expect(incorrect.cards["term-1"]).toMatchObject({
      mistakeCount: 2,
      dictationAttempts: 1,
      dictationCorrect: 0,
      lastDictationResult: "incorrect",
      lastDictationAt: "2026-06-16T04:41:00.000Z",
    });

    const correct = recordMistakeDictation(incorrect, "term-1", true, "2026-06-16T04:42:00.000Z");
    expect(correct.cards["term-1"]).toMatchObject({
      mistakeCount: 2,
      dictationAttempts: 2,
      dictationCorrect: 1,
      lastDictationResult: "correct",
      lastDictationAt: "2026-06-16T04:42:00.000Z",
    });
  });

  it("matches dictation answers against term and accepted variants only", () => {
    const photoCard = pack.vocabulary[1];
    const numericItem = {
      id: "2020",
      term: "2020",
      spokenText: "twenty twenty",
      normalizedTerm: "2020",
      acceptedVariants: [],
      meaningZh: "年份",
      audio: "assets/audio/vocabulary/2020.mp3",
    };

    expect(matchesMistakeDictationAnswer(photoCard, "photo card")).toBe(true);
    expect(matchesMistakeDictationAnswer(photoCard, " PHOTO CARDS ")).toBe(true);
    expect(matchesMistakeDictationAnswer(photoCard, "")).toBe(false);
    expect(matchesMistakeDictationAnswer(numericItem, "2020")).toBe(true);
    expect(matchesMistakeDictationAnswer(numericItem, "twenty twenty")).toBe(false);
  });

  it("records blank dictation input as an incorrect attempt through the matcher result", () => {
    const notebook = notebookWithCards(1);
    const correct = matchesMistakeDictationAnswer(pack.vocabulary[0], "   ");

    const recorded = recordMistakeDictation(notebook, "term-1", correct, "2026-06-16T04:43:00.000Z");

    expect(correct).toBe(false);
    expect(recorded.cards["term-1"]).toMatchObject({
      dictationAttempts: 1,
      dictationCorrect: 0,
      lastDictationResult: "incorrect",
      lastDictationAt: "2026-06-16T04:43:00.000Z",
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
      dictationAttempts: 0,
      dictationCorrect: 0,
      lastDictationResult: null,
      lastDictationAt: null,
    });
    expect(asV2(captured.notebook).archivedCards).toEqual({});
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

  it("recaptures the same stale wrong response when the active card was removed", () => {
    const submitted = result({
      q1: { questionId: "q1", correct: false, expected: ["Ardleigh"], actual: "Ardley" },
    });
    const first = captureMistakeVocabulary({
      pack,
      result: submitted,
      notebook: createEmptyMistakeVocabularyNotebook(),
      capturedMistakes: {},
      capturedAt: "2026-06-16T04:10:00.000Z",
    });
    const removed = removeMistakeCard(first.notebook, "ardleigh");

    const recaptured = captureMistakeVocabulary({
      pack,
      result: submitted,
      notebook: removed,
      capturedMistakes: first.capturedMistakes,
      capturedAt: "2026-06-16T04:20:00.000Z",
    });

    expect(recaptured.notebook.cards.ardleigh).toMatchObject({
      termId: "ardleigh",
      mistakeCount: 1,
      lastIncorrectResponse: "Ardley",
      lastCapturedAt: "2026-06-16T04:20:00.000Z",
    });
    expect(recaptured.capturedMistakes).toEqual({ q1: "ardley" });
  });

  it("reactivates archived cards on later capture without splitting the card key", () => {
    const notebook = createEmptyMistakeVocabularyNotebook();
    asV2(notebook).archivedCards.ardleigh = cardState("ardleigh", "2026-06-16T03:00:00.000Z", {
      mistakeCount: 4,
      practiceAttempts: 5,
      practiceCorrect: 2,
      masteryCount: 1,
      lastPracticeResult: "incorrect",
      lastPracticedAt: "2026-06-16T03:30:00.000Z",
      dictationAttempts: 3,
      dictationCorrect: 1,
      lastDictationResult: "incorrect",
      lastDictationAt: "2026-06-16T03:40:00.000Z",
    });

    const captured = captureMistakeVocabulary({
      pack,
      result: result({
        q1: { questionId: "q1", correct: false, expected: ["Ardleigh"], actual: "Ardli" },
      }),
      notebook,
      capturedMistakes: {},
      capturedAt: "2026-06-16T04:50:00.000Z",
    });

    expect(Object.keys(captured.notebook.cards)).toEqual(["ardleigh"]);
    expect(asV2(captured.notebook).archivedCards.ardleigh).toBeUndefined();
    expect(captured.notebook.cards.ardleigh).toEqual({
      ...asV2(notebook).archivedCards.ardleigh,
      mistakeCount: 5,
      lastIncorrectResponse: "Ardli",
      lastCapturedAt: "2026-06-16T04:50:00.000Z",
    });
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

  it("prioritizes higher visible mistake counts before review tie-breakers", () => {
    const notebook = notebookWithCards(0);
    asV2(notebook).cards = {
      "recent-review-wrong": cardState("recent-review-wrong", "2026-06-16T04:00:00.000Z", {
        mistakeCount: 1,
        dictationAttempts: 1,
        dictationCorrect: 0,
        lastDictationResult: "incorrect",
        lastDictationAt: "2026-06-17T05:00:00.000Z",
      }),
      "more-visible-mistakes": cardState("more-visible-mistakes", "2026-06-16T04:00:00.000Z", {
        mistakeCount: 3,
        practiceAttempts: 5,
        practiceCorrect: 5,
        masteryCount: 5,
        lastPracticeResult: "correct",
        lastPracticedAt: "2026-06-16T04:30:00.000Z",
        dictationAttempts: 5,
        dictationCorrect: 5,
        lastDictationResult: "correct",
        lastDictationAt: "2026-06-16T04:35:00.000Z",
      }),
    };

    expect(fullPracticeQueue(notebook).map((entry) => entry.key)).toEqual([
      "more-visible-mistakes",
      "recent-review-wrong",
    ]);
  });

  it("creates a keyed full practice queue ordered by error priority", () => {
    const notebook = notebookWithCards(0);
    asV2(notebook).cards = {
      "dictation-newer-wrong": cardState("dictation-newer-wrong", "2026-06-16T04:00:00.000Z", {
        dictationAttempts: 1,
        dictationCorrect: 0,
        lastDictationResult: "incorrect",
        lastDictationAt: "2026-06-16T05:00:00.000Z",
      }),
      "practice-older-wrong": cardState("practice-older-wrong", "2026-06-16T04:00:00.000Z", {
        practiceAttempts: 5,
        practiceCorrect: 0,
        lastPracticeResult: "incorrect",
        lastPracticedAt: "2026-06-16T04:50:00.000Z",
      }),
      "more-review-wrong": cardState("more-review-wrong", "2026-06-16T04:00:00.000Z", {
        practiceAttempts: 3,
        practiceCorrect: 1,
        lastPracticeResult: "correct",
        lastPracticedAt: "2026-06-16T04:40:00.000Z",
      }),
      "lower-accuracy": cardState("lower-accuracy", "2026-06-16T04:00:00.000Z", {
        mistakeCount: 2,
        dictationAttempts: 2,
        dictationCorrect: 1,
        lastDictationResult: "correct",
        lastDictationAt: "2026-06-16T04:30:00.000Z",
      }),
      "higher-accuracy": cardState("higher-accuracy", "2026-06-16T04:00:00.000Z", {
        mistakeCount: 2,
        dictationAttempts: 4,
        dictationCorrect: 3,
        lastDictationResult: "correct",
        lastDictationAt: "2026-06-16T04:35:00.000Z",
      }),
      "more-original-mistakes": cardState("more-original-mistakes", "2026-06-16T04:00:00.000Z", {
        mistakeCount: 5,
      }),
      "recent-capture": cardState("recent-capture", "2026-06-16T04:20:00.000Z"),
      zulu: cardState("zulu", "2026-06-16T04:10:00.000Z"),
      alpha: cardState("alpha", "2026-06-16T04:10:00.000Z"),
    };

    expect(fullPracticeQueue(notebook).map((entry) => ({ key: entry.key, termId: entry.card.termId }))).toEqual([
      { key: "more-original-mistakes", termId: "more-original-mistakes" },
      { key: "lower-accuracy", termId: "lower-accuracy" },
      { key: "higher-accuracy", termId: "higher-accuracy" },
      { key: "dictation-newer-wrong", termId: "dictation-newer-wrong" },
      { key: "practice-older-wrong", termId: "practice-older-wrong" },
      { key: "more-review-wrong", termId: "more-review-wrong" },
      { key: "recent-capture", termId: "recent-capture" },
      { key: "alpha", termId: "alpha" },
      { key: "zulu", termId: "zulu" },
    ]);
  });

  it("creates a one-time random sample of ten cards with injected RNG", () => {
    const notebook = notebookWithCards(12);
    const rngValues = [0.75, 0.5, 0.25, 0, 0.9, 0.1, 0.2, 0.3, 0.4, 0.6, 0.8];
    const rng = () => rngValues.shift() ?? 0;

    expect(randomPracticeQueue(notebook, rng).map((entry) => entry.key)).toEqual([
      "term-3",
      "term-7",
      "term-10",
      "term-12",
      "term-1",
      "term-11",
      "term-8",
      "term-6",
      "term-5",
      "term-4",
    ]);
  });

  it("uses all cards for random practice when the notebook has fewer than ten", () => {
    expect(randomPracticeQueue(notebookWithCards(3), () => 0).map((entry) => entry.key)).toEqual([
      "term-3",
      "term-2",
      "term-1",
    ]);
  });
});
