import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import MarkingFeedback from "./MarkingFeedback";
import type { MarkResult, Question } from "../types/pack";

const questions: Question[] = [
  question("q1", 1, 1),
  question("q2", 2, 1),
  question("q11", 11, 2),
];

const sectionOneResult: MarkResult = {
  score: 1,
  total: 2,
  byQuestion: {
    q1: {
      questionId: "q1",
      correct: true,
      expected: ["Ardleigh"],
      actual: "Ardleigh",
    },
    q2: {
      questionId: "q2",
      correct: false,
      expected: ["newspaper"],
      actual: "",
    },
  },
  incorrectIds: ["q2"],
};

function question(id: string, number: number, section: number): Question {
  return {
    id,
    number,
    section,
    responseType: "blank",
    page: section === 1 ? "page-010.png" : "page-012.png",
    focusOrder: number,
    selectionLimit: null,
    options: [],
  };
}

describe("MarkingFeedback", () => {
  it("groups submitted results by section and excludes unsubmitted section counts", () => {
    render(
      <MarkingFeedback
        answers={{ q1: "Ardleigh" }}
        questions={questions}
        result={sectionOneResult}
        onNextIncorrect={vi.fn()}
      />,
    );

    expect(screen.getByText(/Raw score: 1 \/ 2/)).toBeTruthy();
    expect(screen.getByText("未答：1")).toBeTruthy();
    expect(screen.getByText("Section 01")).toBeTruthy();
    expect(screen.queryByText("Section 02")).toBeNull();
    expect(screen.queryByText("Q11")).toBeNull();

    const answers = screen.getByLabelText("正确答案");
    expect(within(answers).getByText("Q2")).toBeTruthy();
    expect(within(answers).getByText("正确答案：newspaper")).toBeTruthy();
  });
});
