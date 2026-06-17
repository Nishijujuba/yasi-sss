import { describe, expect, it } from "vitest";
import { markAnswers, normalizeAnswer } from "./marker";
import type { AnswerRule, Question } from "../types/pack";

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
    id: "q6",
    number: 6,
    section: 1,
    responseType: "blank",
    page: "page-010.png",
    focusOrder: 6,
    selectionLimit: null,
    options: [],
  },
  {
    id: "q11",
    number: 11,
    section: 2,
    responseType: "choice",
    page: "page-012.png",
    focusOrder: 11,
    selectionLimit: 1,
    options: [
      { id: "A", label: "the gym" },
      { id: "B", label: "the tracks" },
      { id: "C", label: "the indoor pool" },
    ],
  },
  {
    id: "q12",
    number: 12,
    section: 2,
    responseType: "choice",
    page: "page-012.png",
    focusOrder: 12,
    selectionLimit: 1,
    options: [
      { id: "A", label: "the gym" },
      { id: "B", label: "the tracks" },
      { id: "C", label: "the indoor pool" },
    ],
  },
];

const rules: AnswerRule[] = [
  { questionIds: ["q1"], accepted: [["Ardleigh"]], orderIndependent: false },
  { questionIds: ["q6"], accepted: [["beach"], ["beaches"]], orderIndependent: false },
  { questionIds: ["q11", "q12"], accepted: [["A", "C"]], orderIndependent: true },
];

describe("normalizeAnswer", () => {
  it("trims, collapses whitespace, and lowercases English letters only", () => {
    expect(normalizeAnswer("  New\t  PAPER  ")).toBe("new paper");
    expect(normalizeAnswer("photo-card")).toBe("photo-card");
    expect(normalizeAnswer("cafe.")).toBe("cafe.");
  });
});

describe("markAnswers", () => {
  it("marks blank answers with exact accepted forms after normalization", () => {
    const result = markAnswers(questions, rules, { q1: " ardleigh ", q6: "beach" });

    expect(result.byQuestion.q1.correct).toBe(true);
    expect(result.byQuestion.q6.correct).toBe(true);
    expect(result.score).toBe(2);
  });

  it("does not accept spelling, punctuation, or semantic variants", () => {
    const result = markAnswers(questions, rules, {
      q1: "Ardley",
      q6: "beach.",
    });

    expect(result.byQuestion.q1.correct).toBe(false);
    expect(result.byQuestion.q6.correct).toBe(false);
    expect(result.score).toBe(0);
  });

  it("accepts q11 and q12 A/C in either order and rejects duplicate choices", () => {
    const reversed = markAnswers(questions, rules, { q11: "C", q12: "A" });
    const duplicate = markAnswers(questions, rules, { q11: "A", q12: "A" });

    expect(reversed.byQuestion.q11.correct).toBe(true);
    expect(reversed.byQuestion.q12.correct).toBe(true);
    expect(reversed.score).toBe(2);
    expect(duplicate.byQuestion.q11.correct).toBe(false);
    expect(duplicate.byQuestion.q12.correct).toBe(false);
    expect(duplicate.score).toBe(0);
  });
});
