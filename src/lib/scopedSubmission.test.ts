import { describe, expect, it } from "vitest";
import type { AnswerMap, AnswerRule, LoadedPack, OverlayRegion, PackManifest, Question, TranscriptSection } from "../types/pack";
import {
  deriveAttemptedSections,
  hasAnyAnswer,
  markAttemptedSections,
  submittedQuestionsForSections,
  submittedRulesForQuestions,
} from "./scopedSubmission";

const questions: Question[] = Array.from({ length: 20 }, (_, index) => {
  const number = index + 1;
  return {
    id: `q${number}`,
    number,
    section: number <= 10 ? 1 : 2,
    responseType: "blank",
    page: number <= 10 ? "page-010.png" : "page-012.png",
    focusOrder: number,
    selectionLimit: null,
    options: [],
  };
});

const rules: AnswerRule[] = questions.map((question) => ({
  questionIds: [question.id],
  accepted: [[`answer ${question.number}`]],
  orderIndependent: false,
}));

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
  },
};

const pack: LoadedPack = {
  baseUrl: "/packs/cambridge-10/test-1/listening",
  manifest,
  questions,
  answers: rules,
  overlays: [],
  transcript: [],
  transcriptTimings: null,
  vocabulary: [],
  questionsById: new Map(questions.map((question) => [question.id, question])),
  answersByQuestionId: new Map(rules.map((rule) => [rule.questionIds[0], rule])),
  overlaysByQuestionId: new Map<string, OverlayRegion[]>(),
  vocabularyById: new Map(),
};

describe("section-scoped submission", () => {
  it("treats any non-empty response as submission readiness", () => {
    expect(hasAnyAnswer({})).toBe(false);
    expect(hasAnyAnswer({ q1: "   " })).toBe(false);
    expect(hasAnyAnswer({ q1: "Ardleigh" })).toBe(true);
  });

  it("derives attempted listening sections from non-empty answers", () => {
    const answers: AnswerMap = { q2: "newspaper", q13: "A", q17: "   " };

    expect(deriveAttemptedSections(questions, answers)).toEqual(new Set([1, 2]));
  });

  it("submits only questions and answer rules inside attempted sections", () => {
    const attemptedSections = new Set([1]);
    const submittedQuestions = submittedQuestionsForSections(questions, attemptedSections);

    expect(submittedQuestions).toHaveLength(10);
    expect(submittedQuestions.map((question) => question.id)).toEqual([
      "q1",
      "q2",
      "q3",
      "q4",
      "q5",
      "q6",
      "q7",
      "q8",
      "q9",
      "q10",
    ]);
    expect(submittedRulesForQuestions(rules, submittedQuestions)).toHaveLength(10);
  });

  it("marks Section 01-only submission with denominator 10 and no Section 02 result", () => {
    const result = markAttemptedSections(pack, { q1: "answer 1" });

    expect(result.total).toBe(10);
    expect(result.score).toBe(1);
    expect(Object.keys(result.byQuestion)).toHaveLength(10);
    expect(result.byQuestion.q10).toBeDefined();
    expect(result.byQuestion.q11).toBeUndefined();
    expect(result.incorrectIds).not.toContain("q11");
  });
});
