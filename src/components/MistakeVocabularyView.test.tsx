import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import MistakeVocabularyView from "./MistakeVocabularyView";
import type { LoadedPack, VocabularyItem } from "../types/pack";
import {
  createEmptyMistakeVocabularyNotebook,
  type MistakeVocabularyNotebookState,
} from "../lib/mistakeVocabulary";

const vocabulary: VocabularyItem[] = [
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
  {
    id: "number-429",
    term: "429",
    spokenText: "four hundred twenty-nine",
    normalizedTerm: "429",
    acceptedVariants: [],
    meaningZh: "四百二十九",
    audio: "assets/audio/vocabulary/number-429.mp3",
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
  questions: [],
  answers: [],
  overlays: [],
  transcript: [],
  transcriptTimings: null,
  vocabulary,
  questionsById: new Map(),
  answersByQuestionId: new Map(),
  overlaysByQuestionId: new Map(),
  vocabularyById: new Map(vocabulary.map((item) => [item.id, item])),
};

function notebook(): MistakeVocabularyNotebookState {
  const state = createEmptyMistakeVocabularyNotebook();
  state.cards.ardleigh = {
    termId: "ardleigh",
    createdAt: "2026-06-16T04:00:00.000Z",
    mistakeCount: 2,
    lastIncorrectResponse: "Ardley",
    lastCapturedAt: "2026-06-16T04:10:00.000Z",
    practiceAttempts: 0,
    practiceCorrect: 0,
    masteryCount: 0,
    lastPracticeResult: null,
    lastPracticedAt: null,
  };
  state.cards["photo card"] = {
    termId: "photo-card",
    createdAt: "2026-06-16T04:05:00.000Z",
    mistakeCount: 1,
    lastIncorrectResponse: "photo",
    lastCapturedAt: "2026-06-16T04:12:00.000Z",
    practiceAttempts: 1,
    practiceCorrect: 1,
    masteryCount: 1,
    lastPracticeResult: "correct",
    lastPracticedAt: "2026-06-16T04:20:00.000Z",
  };
  return state;
}

function numericNotebook(): MistakeVocabularyNotebookState {
  const state = createEmptyMistakeVocabularyNotebook();
  state.cards["429"] = {
    termId: "number-429",
    createdAt: "2026-06-16T04:00:00.000Z",
    mistakeCount: 1,
    lastIncorrectResponse: "four two nine",
    lastCapturedAt: "2026-06-16T04:10:00.000Z",
    practiceAttempts: 0,
    practiceCorrect: 0,
    masteryCount: 0,
    lastPracticeResult: null,
    lastPracticedAt: null,
  };
  return state;
}

describe("MistakeVocabularyView", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("shows an empty state without example answers", () => {
    render(
      <MistakeVocabularyView
        notebook={createEmptyMistakeVocabularyNotebook()}
        onGoHome={vi.fn()}
        onRemoveCard={vi.fn()}
        onSubmitPractice={vi.fn()}
        pack={pack}
      />,
    );

    expect(screen.getByText("错题本为空")).toBeTruthy();
    expect(screen.queryByText("Ardleigh")).toBeNull();
  });

  it("renders card details and removes a card manually", () => {
    const onRemoveCard = vi.fn();

    render(
      <MistakeVocabularyView
        notebook={notebook()}
        onGoHome={vi.fn()}
        onRemoveCard={onRemoveCard}
        onSubmitPractice={vi.fn()}
        pack={pack}
      />,
    );

    const card = screen.getByLabelText("错题词 Ardleigh");
    expect(within(card).getByText("阿德利")).toBeTruthy();
    expect(within(card).getByText("错误次数：2")).toBeTruthy();

    fireEvent.click(within(card).getByRole("button", { name: "移除" }));

    expect(onRemoveCard).toHaveBeenCalledWith("ardleigh");
  });

  it("plays the official clip for a card", () => {
    const play = vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);

    render(
      <MistakeVocabularyView
        notebook={notebook()}
        onGoHome={vi.fn()}
        onRemoveCard={vi.fn()}
        onSubmitPractice={vi.fn()}
        pack={pack}
      />,
    );

    fireEvent.click(within(screen.getByLabelText("错题词 Ardleigh")).getByRole("button", { name: "播放" }));

    expect(play).toHaveBeenCalled();
  });

  it("runs full ordered practice and reveals spelling, variants, meaning, and run result", () => {
    const onSubmitPractice = vi.fn();

    render(
      <MistakeVocabularyView
        notebook={notebook()}
        onGoHome={vi.fn()}
        onRemoveCard={vi.fn()}
        onSubmitPractice={onSubmitPractice}
        pack={pack}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "全量顺序练习" }));
    fireEvent.change(screen.getByLabelText("听写答案"), { target: { value: "Ardleigh" } });
    fireEvent.click(screen.getByRole("button", { name: "提交听写" }));

    const practice = screen.getByLabelText("错题听写练习");
    expect(screen.getByText("正确拼写：Ardleigh")).toBeTruthy();
    expect(within(practice).getByText("阿德利")).toBeTruthy();
    expect(onSubmitPractice).toHaveBeenCalledWith("ardleigh", true);

    fireEvent.click(screen.getByRole("button", { name: "下一张" }));
    fireEvent.change(screen.getByLabelText("听写答案"), { target: { value: "photo card" } });
    fireEvent.click(screen.getByRole("button", { name: "提交听写" }));

    expect(within(screen.getByLabelText("错题听写练习")).getByText("可接受形式：photo cards")).toBeTruthy();
    expect(onSubmitPractice).toHaveBeenCalledWith("photo card", true);

    fireEvent.click(screen.getByRole("button", { name: "完成本轮" }));

    expect(screen.getByText("本轮结果：2 / 2")).toBeTruthy();
  });

  it("keeps spokenText hidden and excludes it from numeric practice matching", () => {
    const onSubmitPractice = vi.fn();

    render(
      <MistakeVocabularyView
        notebook={numericNotebook()}
        onGoHome={vi.fn()}
        onRemoveCard={vi.fn()}
        onSubmitPractice={onSubmitPractice}
        pack={pack}
      />,
    );

    const card = screen.getByLabelText("错题词 429");
    expect(within(card).getByText("429")).toBeTruthy();
    expect(within(card).getByText("四百二十九")).toBeTruthy();
    expect(screen.queryByText("four hundred twenty-nine")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "全量顺序练习" }));
    fireEvent.change(screen.getByLabelText("听写答案"), {
      target: { value: "four hundred twenty-nine" },
    });
    fireEvent.click(screen.getByRole("button", { name: "提交听写" }));

    const practice = screen.getByLabelText("错题听写练习");
    expect(within(practice).getByText("错误")).toBeTruthy();
    expect(within(practice).getByText("正确拼写：429")).toBeTruthy();
    expect(within(practice).getByText("四百二十九")).toBeTruthy();
    expect(screen.queryByText("four hundred twenty-nine")).toBeNull();
    expect(onSubmitPractice).toHaveBeenCalledWith("429", false);
  });
});
