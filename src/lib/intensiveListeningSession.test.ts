import { beforeEach, describe, expect, it } from "vitest";
import type { LoadedPack, PackManifest, Question } from "../types/pack";
import { MISTAKE_VOCABULARY_KEY } from "./mistakeVocabulary";
import type { PracticeSession } from "./session";
import { SESSION_KEY } from "./session";
import {
  createEmptyIntensiveListeningSession,
  intensiveListeningSessionKey,
  isIntensiveListeningSectionUnlocked,
  loadIntensiveListeningSession,
  markIntensiveListeningSessionSection,
  revealIntensiveListeningAnswers,
  revealIntensiveListeningTranscript,
  saveIntensiveListeningSession,
  setIntensiveListeningAnswer,
} from "./intensiveListeningSession";

const manifest: PackManifest = {
  packId: "cambridge-10-test-1-listening",
  schemaVersion: 1,
  status: "released",
  title: "Cambridge IELTS 10 Test 1 Listening",
  sections: [],
  assets: {
    questions: "questions.json",
    answers: "answers.json",
    overlays: "overlays.json",
    transcript: "transcript.json",
    vocabulary: "vocabulary.json",
    intensiveListening: "intensive-listening.json",
  },
};

const questions: Question[] = [
  {
    id: "q1",
    number: 1,
    section: 1,
    responseType: "blank",
    page: "page-010.png",
    focusOrder: 1,
    selectionLimit: null,
    options: [],
  },
  {
    id: "q2",
    number: 2,
    section: 1,
    responseType: "blank",
    page: "page-010.png",
    focusOrder: 2,
    selectionLimit: null,
    options: [],
  },
  {
    id: "q11",
    number: 11,
    section: 2,
    responseType: "blank",
    page: "page-012.png",
    focusOrder: 11,
    selectionLimit: null,
    options: [],
  },
];

const pack: LoadedPack = {
  baseUrl: "/packs/cambridge-10/test-1/listening",
  manifest,
  questions,
  answers: [],
  overlays: [],
  transcript: [],
  transcriptTimings: null,
  vocabulary: [],
  intensiveListening: {
    schemaVersion: "yasi.intensive-listening.v1",
    sections: [
      {
        section: 1,
        blanks: [
          {
            id: "il-s01-seg001-t000-t001",
            segmentOrder: 1,
            startTokenIndex: 0,
            endTokenIndex: 1,
            answer: "Ardleigh",
            acceptedVariants: [],
            reason: "Proper noun spelling.",
            tags: ["spelling-risk"],
          },
        ],
      },
      {
        section: 2,
        blanks: [
          {
            id: "il-s02-seg001-t000-t001",
            segmentOrder: 1,
            startTokenIndex: 0,
            endTokenIndex: 1,
            answer: "newspaper",
            acceptedVariants: [],
            reason: "Common IELTS form-completion noun.",
            tags: ["form-completion"],
          },
        ],
      },
    ],
  },
  questionsById: new Map(questions.map((question) => [question.id, question])),
  answersByQuestionId: new Map(),
  overlaysByQuestionId: new Map(),
  vocabularyById: new Map(),
};

const submittedSectionOneSession: PracticeSession = {
  version: 3,
  packId: "cambridge-10-test-1-listening",
  answers: { q1: "Ardleigh" },
  activeSection: 1,
  submitted: true,
  results: {
    score: 1,
    total: 2,
    byQuestion: {
      q1: { questionId: "q1", correct: true, expected: ["Ardleigh"], actual: "Ardleigh" },
      q2: { questionId: "q2", correct: false, expected: ["tickets"], actual: "" },
    },
    incorrectIds: ["q2"],
  },
  audioPositions: { "1": 12 },
  capturedMistakes: { q2: "wrong" },
  transcriptViewed: false,
};

describe("intensive listening session helpers", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("uses an independent pack-scoped localStorage key", () => {
    expect(intensiveListeningSessionKey("cambridge-10-test-1-listening")).toBe(
      "yasi:cambridge-10-test-1-listening:intensive-listening:v1",
    );
  });

  it("stores per-section answers, marking result, and reveal flags independently", () => {
    localStorage.setItem(SESSION_KEY, JSON.stringify(submittedSectionOneSession));
    localStorage.setItem(MISTAKE_VOCABULARY_KEY, JSON.stringify({ version: 1, cards: {} }));

    const empty = createEmptyIntensiveListeningSession(pack.manifest.packId);
    const answered = setIntensiveListeningAnswer(empty, 1, "il-s01-seg001-t000-t001", " ardleigh ");
    const marked = markIntensiveListeningSessionSection(pack, answered, 1);
    const answerRevealed = revealIntensiveListeningAnswers(marked, 1);
    const transcriptRevealed = revealIntensiveListeningTranscript(answerRevealed, 1);
    saveIntensiveListeningSession(transcriptRevealed);

    expect(loadIntensiveListeningSession(pack.manifest.packId)).toEqual({
      version: 1,
      packId: "cambridge-10-test-1-listening",
      sections: {
        "1": {
          answers: { "il-s01-seg001-t000-t001": " ardleigh " },
          marking: {
            "il-s01-seg001-t000-t001": {
              blankId: "il-s01-seg001-t000-t001",
              correct: true,
              expected: "Ardleigh",
              actual: " ardleigh ",
            },
          },
          result: {
            score: 1,
            total: 1,
            byBlank: {
              "il-s01-seg001-t000-t001": {
                blankId: "il-s01-seg001-t000-t001",
                correct: true,
                expected: ["Ardleigh"],
                actual: " ardleigh ",
              },
            },
            incorrectIds: [],
          },
          answerRevealed: true,
          transcriptRevealed: true,
        },
      },
    });
    expect(localStorage.getItem(SESSION_KEY)).toBe(JSON.stringify(submittedSectionOneSession));
    expect(localStorage.getItem(MISTAKE_VOCABULARY_KEY)).toBe(JSON.stringify({ version: 1, cards: {} }));
  });

  it("unlocks a section from original practice submission results without mutating practice state", () => {
    const before = JSON.stringify(submittedSectionOneSession);

    expect(isIntensiveListeningSectionUnlocked(pack, submittedSectionOneSession, 1)).toBe(true);
    expect(isIntensiveListeningSectionUnlocked(pack, submittedSectionOneSession, 2)).toBe(false);
    expect(JSON.stringify(submittedSectionOneSession)).toBe(before);
  });

  it("does not unlock from typed exam answers alone", () => {
    const unsubmitted = {
      ...submittedSectionOneSession,
      submitted: false,
      results: null,
    };

    expect(isIntensiveListeningSectionUnlocked(pack, unsubmitted, 1)).toBe(false);
  });
});
