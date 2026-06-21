import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import PracticePackHome from "./PracticePackHome";
import type { LoadedPack, Question } from "../types/pack";

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
];

const pack: LoadedPack = {
  baseUrl: "/packs/cambridge-10/test-1/listening",
  manifest: {
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
  },
  questions,
  answers: [],
  overlays: [],
  transcript: [],
  transcriptTimings: null,
  vocabulary: [],
  questionsById: new Map(questions.map((question) => [question.id, question])),
  answersByQuestionId: new Map(),
  overlaysByQuestionId: new Map(),
  vocabularyById: new Map(),
};

describe("PracticePackHome", () => {
  afterEach(() => {
    cleanup();
  });

  it("opens the mistake vocabulary notebook from a dedicated home entry", () => {
    const onOpenMistakes = vi.fn();

    render(
      <PracticePackHome
        answers={{}}
        onOpenMistakes={onOpenMistakes}
        onStart={vi.fn()}
        pack={pack}
        result={null}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "错题本" }));

    expect(onOpenMistakes).toHaveBeenCalledOnce();
  });

  it("does not render section drill entries on the home screen", () => {
    render(
      <PracticePackHome
        activeSection={1}
        answers={{}}
        onOpenMistakes={vi.fn()}
        onStart={vi.fn()}
        pack={pack}
        result={null}
      />,
    );

    expect(screen.queryByRole("button", { name: "精听" })).toBeNull();
    expect(screen.queryByRole("button", { name: "原文跟读" })).toBeNull();
    expect(screen.queryByText("提交当前 Section 后开放精听")).toBeNull();
  });
});
