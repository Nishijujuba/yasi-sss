import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
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
    dictationAttempts: 0,
    dictationCorrect: 0,
    lastDictationResult: null,
    lastDictationAt: null,
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
    dictationAttempts: 0,
    dictationCorrect: 0,
    lastDictationResult: null,
    lastDictationAt: null,
  };
  return state;
}

function notebookWithArchive(): MistakeVocabularyNotebookState & {
  archivedCards: MistakeVocabularyNotebookState["cards"];
} {
  const state = notebook() as MistakeVocabularyNotebookState & {
    archivedCards: MistakeVocabularyNotebookState["cards"];
  };
  state.archivedCards = {
    "archived-429": {
      termId: "number-429",
      createdAt: "2026-06-15T04:00:00.000Z",
      mistakeCount: 3,
      lastIncorrectResponse: "four two nine",
      lastCapturedAt: "2026-06-15T04:10:00.000Z",
      practiceAttempts: 2,
      practiceCorrect: 1,
      masteryCount: 1,
      lastPracticeResult: "correct",
      lastPracticedAt: "2026-06-16T04:20:00.000Z",
      dictationAttempts: 1,
      dictationCorrect: 1,
      lastDictationResult: "correct",
      lastDictationAt: "2026-06-16T04:25:00.000Z",
    },
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
    dictationAttempts: 0,
    dictationCorrect: 0,
    lastDictationResult: null,
    lastDictationAt: null,
  };
  return state;
}

function priorityNotebook(): MistakeVocabularyNotebookState {
  const state = createEmptyMistakeVocabularyNotebook();
  state.cards.old = {
    termId: "ardleigh",
    createdAt: "2026-06-16T04:00:00.000Z",
    mistakeCount: 1,
    lastIncorrectResponse: "Ardley",
    lastCapturedAt: "2026-06-16T04:10:00.000Z",
    practiceAttempts: 5,
    practiceCorrect: 5,
    masteryCount: 5,
    lastPracticeResult: "correct",
    lastPracticedAt: "2026-06-16T04:30:00.000Z",
    dictationAttempts: 5,
    dictationCorrect: 5,
    lastDictationResult: "correct",
    lastDictationAt: "2026-06-16T04:35:00.000Z",
  };
  state.cards.priority = {
    termId: "photo-card",
    createdAt: "2026-06-16T05:00:00.000Z",
    mistakeCount: 1,
    lastIncorrectResponse: "photo",
    lastCapturedAt: "2026-06-16T05:10:00.000Z",
    practiceAttempts: 1,
    practiceCorrect: 0,
    masteryCount: 0,
    lastPracticeResult: "incorrect",
    lastPracticedAt: "2026-06-17T04:20:00.000Z",
    dictationAttempts: 0,
    dictationCorrect: 0,
    lastDictationResult: null,
    lastDictationAt: null,
  };
  return state;
}

function manyNotebook(count = 12): MistakeVocabularyNotebookState {
  const state = createEmptyMistakeVocabularyNotebook();
  for (let index = 0; index < count; index += 1) {
    const id = index % 2 === 0 ? "ardleigh" : "photo-card";
    state.cards[`card-${index}`] = {
      termId: id,
      createdAt: `2026-06-16T04:${String(index).padStart(2, "0")}:00.000Z`,
      mistakeCount: index + 1,
      lastIncorrectResponse: id === "ardleigh" ? "Ardley" : "photo",
      lastCapturedAt: `2026-06-16T05:${String(index).padStart(2, "0")}:00.000Z`,
      practiceAttempts: index,
      practiceCorrect: 0,
      masteryCount: 0,
      lastPracticeResult: "incorrect",
      lastPracticedAt: `2026-06-17T04:${String(index).padStart(2, "0")}:00.000Z`,
      dictationAttempts: 0,
      dictationCorrect: 0,
      lastDictationResult: null,
      lastDictationAt: null,
    };
  }
  return state;
}

describe("MistakeVocabularyView", () => {
  beforeEach(() => {
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
    vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => undefined);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  function renderMistakes({
    state = notebook(),
    onArchiveCard = vi.fn(),
    onRestoreCard = vi.fn(),
    onSubmitDictation = vi.fn(),
    onSubmitPractice = vi.fn(),
    onRemoveCard = vi.fn(),
  }: {
    state?: MistakeVocabularyNotebookState;
    onArchiveCard?: (cardKey: string) => void;
    onRestoreCard?: (cardKey: string) => void;
    onSubmitDictation?: (cardKey: string, correct: boolean) => void;
    onSubmitPractice?: (cardKey: string, correct: boolean) => void;
    onRemoveCard?: (cardKey: string) => void;
  } = {}) {
    return render(
      <MistakeVocabularyView
        notebook={state}
        onArchiveCard={onArchiveCard}
        onGoHome={vi.fn()}
        onRemoveCard={onRemoveCard}
        onRestoreCard={onRestoreCard}
        onSubmitDictation={onSubmitDictation}
        onSubmitPractice={onSubmitPractice}
        pack={pack}
      />,
    );
  }

  it("shows an empty state without example answers", () => {
    renderMistakes({ state: createEmptyMistakeVocabularyNotebook() });

    expect(screen.getByText("错题本为空")).toBeTruthy();
    expect(screen.queryByText("Ardleigh")).toBeNull();
  });

  it("keeps the archive entry reachable when active cards are empty", () => {
    const state = createEmptyMistakeVocabularyNotebook();
    state.archivedCards.ardleigh = notebook().cards.ardleigh;

    renderMistakes({ state });

    expect(screen.getByText("错题本为空")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "全部" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "查看归档" }));

    expect(screen.getByRole("heading", { name: "归档错题" })).toBeTruthy();
    expect(screen.getByLabelText("归档错题词 Ardleigh")).toBeTruthy();
  });

  it("renders card details and removes a card manually", () => {
    const onRemoveCard = vi.fn();

    renderMistakes({ onRemoveCard });

    const card = screen.getByLabelText("错题词 Ardleigh");
    expect(within(card).getByText("阿德利")).toBeTruthy();
    expect(within(card).getByText("错误次数：2")).toBeTruthy();

    fireEvent.click(within(card).getByRole("button", { name: "移除" }));

    expect(onRemoveCard).toHaveBeenCalledWith("ardleigh");
  });

  it("plays the official clip for a card", () => {
    const play = vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);

    renderMistakes();

    fireEvent.click(within(screen.getByLabelText("错题词 Ardleigh")).getByRole("button", { name: "播放" }));

    expect(play).toHaveBeenCalled();
  });

  it("runs listening review with run-level aid hiding, pause controls, and configurable delayed advance", () => {
    vi.useFakeTimers();
    const play = vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
    const pause = vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => undefined);
    const onSubmitPractice = vi.fn();

    const { container } = renderMistakes({ onSubmitPractice });

    fireEvent.click(screen.getByRole("tab", { name: "听音复习" }));
    fireEvent.change(screen.getByLabelText("间隔秒数"), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "全部" }));

    const review = screen.getByLabelText("听音复习");
    expect(within(review).getByText("正确拼写：Ardleigh")).toBeTruthy();
    expect(within(review).getByText("阿德利")).toBeTruthy();
    expect(screen.getByLabelText("错题词 Ardleigh")).toHaveAttribute("aria-current", "true");
    expect(play).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "隐藏拼写" }));
    fireEvent.click(screen.getByRole("button", { name: "隐藏含义" }));
    expect(within(review).queryByText("正确拼写：Ardleigh")).toBeNull();
    expect(within(review).queryByText("阿德利")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "暂停" }));
    expect(pause).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "继续" })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "继续" }));
    const audio = container.querySelector('audio[src="/packs/cambridge-10/test-1/listening/assets/audio/vocabulary/ardleigh.mp3"]');
    expect(audio).toBeTruthy();

    fireEvent.ended(audio as HTMLAudioElement);
    act(() => {
      vi.advanceTimersByTime(999);
    });
    expect(screen.getByLabelText("错题词 Ardleigh")).toHaveAttribute("aria-current", "true");

    act(() => {
      vi.advanceTimersByTime(1);
    });

    expect(screen.getByLabelText("错题词 photo card")).toHaveAttribute("aria-current", "true");
    expect(within(screen.getByLabelText("听音复习")).queryByText("正确拼写：photo card")).toBeNull();
    expect(within(screen.getByLabelText("听音复习")).queryByText("照片卡")).toBeNull();
    expect(onSubmitPractice).toHaveBeenCalledWith("ardleigh", true);
    expect(play).toHaveBeenCalledTimes(3);

    fireEvent.click(screen.getByRole("button", { name: "停止" }));
    expect(pause).toHaveBeenCalledTimes(2);
    expect(screen.queryByLabelText("听音复习")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "全部" }));
    expect(within(screen.getByLabelText("听音复习")).getByText("正确拼写：Ardleigh")).toBeTruthy();
    expect(within(screen.getByLabelText("听音复习")).getByText("阿德利")).toBeTruthy();
  });

  it("replays the first listening card when starting a new run at index zero", () => {
    const play = vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);

    renderMistakes();

    fireEvent.click(screen.getByRole("button", { name: "全部" }));
    fireEvent.click(screen.getByRole("button", { name: "全部" }));

    expect(play).toHaveBeenCalledTimes(2);
  });

  it("auto-plays dictation, starts the 3000 ms submit window after audio ends, and advances without manual buttons", () => {
    vi.useFakeTimers();
    const play = vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
    const onSubmitDictation = vi.fn();
    const onSubmitPractice = vi.fn();

    const { container } = renderMistakes({ onSubmitDictation, onSubmitPractice });

    fireEvent.click(screen.getByRole("tab", { name: "听写模式" }));
    fireEvent.click(screen.getByRole("button", { name: "全部" }));

    const dictation = screen.getByLabelText("错题听写练习");
    expect(within(dictation).queryByText("正确拼写：Ardleigh")).toBeNull();
    expect(within(dictation).queryByText("阿德利")).toBeNull();
    expect(within(dictation).queryByRole("button", { name: "播放" })).toBeNull();
    expect(within(dictation).queryByRole("button", { name: "提交听写" })).toBeNull();
    expect(play).toHaveBeenCalledTimes(1);

    fireEvent.change(screen.getByLabelText("听写答案"), { target: { value: "Ardleigh" } });
    act(() => {
      vi.advanceTimersByTime(3000);
    });
    expect(onSubmitDictation).not.toHaveBeenCalled();

    const firstAudio = container.querySelector(
      'audio[src="/packs/cambridge-10/test-1/listening/assets/audio/vocabulary/ardleigh.mp3"]',
    );
    expect(firstAudio).toBeTruthy();
    fireEvent.ended(firstAudio as HTMLAudioElement);
    act(() => {
      vi.advanceTimersByTime(2999);
    });
    expect(onSubmitDictation).not.toHaveBeenCalled();
    act(() => {
      vi.advanceTimersByTime(1);
    });

    expect(onSubmitDictation).toHaveBeenCalledWith("ardleigh", true);
    expect(onSubmitPractice).not.toHaveBeenCalled();
    expect(within(screen.getByLabelText("错题听写练习")).getByText("2 / 2")).toBeTruthy();
    expect(within(screen.getByLabelText("错题词 1")).getByText("本轮：正确")).toBeTruthy();
    expect(within(screen.getByLabelText("错题词 2")).getByText("本轮：待听写")).toBeTruthy();
    expect(screen.getByLabelText("错题词 2")).toHaveAttribute("aria-current", "true");
    expect(play).toHaveBeenCalledTimes(2);

    const secondAudio = container.querySelector(
      'audio[src="/packs/cambridge-10/test-1/listening/assets/audio/vocabulary/photo-card.mp3"]',
    );
    expect(secondAudio).toBeTruthy();
    fireEvent.ended(secondAudio as HTMLAudioElement);
    act(() => {
      vi.advanceTimersByTime(3000);
    });

    expect(onSubmitDictation).toHaveBeenLastCalledWith("photo card", false);
    expect(screen.getByText("最终准确率：50% (1 / 2)")).toBeTruthy();
    expect(within(screen.getByLabelText("错题词 Ardleigh")).getByText("本轮：正确")).toBeTruthy();
    expect(within(screen.getByLabelText("错题词 photo card")).getByText("本轮：错误")).toBeTruthy();
  });

  it("hides active card-list answer aids during an unrevealed dictation run", () => {
    vi.useFakeTimers();

    const { container } = renderMistakes();

    expect(screen.getByLabelText("错题词 Ardleigh")).toBeTruthy();
    expect(screen.getByText("Ardleigh")).toBeTruthy();
    expect(screen.getByText("阿德利")).toBeTruthy();
    expect(screen.getByText("可接受形式：photo cards")).toBeTruthy();

    fireEvent.click(screen.getByRole("tab", { name: "听写模式" }));
    fireEvent.click(screen.getByRole("button", { name: "全部" }));

    const list = screen.getByLabelText("错题词列表");
    expect(within(list).queryByText("Ardleigh")).toBeNull();
    expect(within(list).queryByText("photo card")).toBeNull();
    expect(within(list).queryByText("可接受形式：photo cards")).toBeNull();
    expect(within(list).queryByText("阿德利")).toBeNull();
    expect(within(list).queryByText("照片卡")).toBeNull();
    expect(screen.queryByLabelText("错题词 Ardleigh")).toBeNull();
    expect(screen.queryByLabelText("错题词 photo card")).toBeNull();

    const firstAudio = container.querySelector(
      'audio[src="/packs/cambridge-10/test-1/listening/assets/audio/vocabulary/ardleigh.mp3"]',
    );
    expect(firstAudio).toBeTruthy();
    fireEvent.change(screen.getByLabelText("听写答案"), { target: { value: "Ardleigh" } });
    fireEvent.ended(firstAudio as HTMLAudioElement);
    act(() => {
      vi.advanceTimersByTime(3000);
    });

    expect(screen.getByLabelText("错题词 2")).toHaveAttribute("aria-current", "true");
    expect(within(list).queryByText("Ardleigh")).toBeNull();
    expect(within(list).queryByText("photo card")).toBeNull();
    expect(within(list).queryByText("阿德利")).toBeNull();
    expect(within(list).queryByText("照片卡")).toBeNull();
  });

  it("uses state-layer priority order for full active queues", () => {
    const play = vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);

    renderMistakes({ state: priorityNotebook() });

    fireEvent.click(screen.getByRole("button", { name: "全部" }));

    expect(within(screen.getByLabelText("听音复习")).getByText("正确拼写：photo card")).toBeTruthy();
    expect(screen.getByLabelText("错题词 photo card")).toHaveAttribute("aria-current", "true");
    expect(play).toHaveBeenCalledTimes(1);
  });

  it("keeps a random 10 queue fixed for the run while advancing", () => {
    vi.useFakeTimers();
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
    const random = vi.spyOn(Math, "random").mockReturnValue(0);

    renderMistakes({ state: manyNotebook() });

    fireEvent.click(screen.getByRole("button", { name: "随机 10" }));

    expect(random).toHaveBeenCalledTimes(10);
    expect(within(screen.getByLabelText("听音复习")).getByText("1 / 10")).toBeTruthy();
    const firstCurrentCard = screen
      .getAllByLabelText("错题词 photo card")
      .find((card) => card.getAttribute("aria-current") === "true");
    expect(firstCurrentCard).toBeTruthy();
    expect(within(firstCurrentCard as HTMLElement).getByText("错误次数：12")).toBeTruthy();
    const firstAudio = (firstCurrentCard as HTMLElement).querySelector("audio");
    expect(firstAudio).toBeTruthy();

    fireEvent.ended(firstAudio as HTMLAudioElement);
    act(() => {
      vi.advanceTimersByTime(3000);
    });

    expect(random).toHaveBeenCalledTimes(10);
    expect(within(screen.getByLabelText("听音复习")).getByText("2 / 10")).toBeTruthy();
    const secondCurrentCard = screen
      .getAllByLabelText("错题词 Ardleigh")
      .find((card) => card.getAttribute("aria-current") === "true");
    expect(secondCurrentCard).toBeTruthy();
    expect(within(secondCurrentCard as HTMLElement).getByText("错误次数：11")).toBeTruthy();
  });

  it("auto-submits the latest dictation input after the 3000 ms window", () => {
    vi.useFakeTimers();
    const onSubmitDictation = vi.fn();

    const { container } = renderMistakes({ onSubmitDictation });

    fireEvent.click(screen.getByRole("tab", { name: "听写模式" }));
    fireEvent.click(screen.getByRole("button", { name: "全部" }));
    fireEvent.change(screen.getByLabelText("听写答案"), { target: { value: "wrong" } });
    act(() => {
      vi.advanceTimersByTime(3000);
    });
    expect(onSubmitDictation).not.toHaveBeenCalled();

    const audio = container.querySelector(
      'audio[src="/packs/cambridge-10/test-1/listening/assets/audio/vocabulary/ardleigh.mp3"]',
    );
    expect(audio).toBeTruthy();
    fireEvent.ended(audio as HTMLAudioElement);
    act(() => {
      vi.advanceTimersByTime(2500);
    });
    fireEvent.change(screen.getByLabelText("听写答案"), { target: { value: "Ardleigh" } });
    act(() => {
      vi.advanceTimersByTime(499);
    });
    expect(onSubmitDictation).not.toHaveBeenCalled();
    act(() => {
      vi.advanceTimersByTime(1);
    });

    expect(onSubmitDictation).toHaveBeenCalledWith("ardleigh", true);
  });

  it("resets the dictation timer when restarting a run on the same first card", () => {
    vi.useFakeTimers();
    const onSubmitDictation = vi.fn();

    const { container } = renderMistakes({ onSubmitDictation });

    fireEvent.click(screen.getByRole("tab", { name: "听写模式" }));
    fireEvent.click(screen.getByRole("button", { name: "全部" }));
    const firstAudio = container.querySelector(
      'audio[src="/packs/cambridge-10/test-1/listening/assets/audio/vocabulary/ardleigh.mp3"]',
    );
    expect(firstAudio).toBeTruthy();
    fireEvent.ended(firstAudio as HTMLAudioElement);
    act(() => {
      vi.advanceTimersByTime(2500);
    });
    fireEvent.click(screen.getByRole("button", { name: "全部" }));
    act(() => {
      vi.advanceTimersByTime(3000);
    });
    expect(onSubmitDictation).not.toHaveBeenCalled();

    const restartedAudio = container.querySelector(
      'audio[src="/packs/cambridge-10/test-1/listening/assets/audio/vocabulary/ardleigh.mp3"]',
    );
    expect(restartedAudio).toBeTruthy();
    fireEvent.ended(restartedAudio as HTMLAudioElement);
    act(() => {
      vi.advanceTimersByTime(2999);
    });
    expect(onSubmitDictation).not.toHaveBeenCalled();
    act(() => {
      vi.advanceTimersByTime(1);
    });

    expect(onSubmitDictation).toHaveBeenCalledWith("ardleigh", false);
  });

  it("disables archive and remove actions while a run is active", () => {
    renderMistakes();

    fireEvent.click(screen.getByRole("button", { name: "全部" }));
    const activeListeningCard = screen.getByLabelText("错题词 Ardleigh");
    expect(within(activeListeningCard).getByRole("button", { name: "归档" })).toBeDisabled();
    expect(within(activeListeningCard).getByRole("button", { name: "移除" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "停止" }));
    fireEvent.click(screen.getByRole("tab", { name: "听写模式" }));
    fireEvent.click(screen.getByRole("button", { name: "全部" }));

    const activeDictationCard = screen.getByLabelText("错题词 1");
    expect(within(activeDictationCard).getByRole("button", { name: "播放" })).toBeDisabled();
    expect(within(activeDictationCard).getByRole("button", { name: "归档" })).toBeDisabled();
    expect(within(activeDictationCard).getByRole("button", { name: "移除" })).toBeDisabled();
  });

  it("keeps spokenText hidden and excludes it from numeric dictation matching", () => {
    vi.useFakeTimers();
    const onSubmitDictation = vi.fn();

    renderMistakes({ state: numericNotebook(), onSubmitDictation });

    const card = screen.getByLabelText("错题词 429");
    expect(within(card).getByText("429")).toBeTruthy();
    expect(within(card).getByText("四百二十九")).toBeTruthy();
    expect(screen.queryByText("four hundred twenty-nine")).toBeNull();

    fireEvent.click(screen.getByRole("tab", { name: "听写模式" }));
    fireEvent.click(screen.getByRole("button", { name: "全部" }));
    fireEvent.change(screen.getByLabelText("听写答案"), {
      target: { value: "four hundred twenty-nine" },
    });
    const audio = document.querySelector('audio[src="/packs/cambridge-10/test-1/listening/assets/audio/vocabulary/number-429.mp3"]');
    expect(audio).toBeTruthy();
    fireEvent.ended(audio as HTMLAudioElement);
    act(() => {
      vi.advanceTimersByTime(3000);
    });

    expect(screen.getByText("最终准确率：0% (0 / 1)")).toBeTruthy();
    expect(screen.queryByText("four hundred twenty-nine")).toBeNull();
    expect(onSubmitDictation).toHaveBeenCalledWith("429", false);
  });

  it("archives active cards and opens an archive page with playback and restore only", () => {
    const play = vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
    const onArchiveCard = vi.fn();
    const onRestoreCard = vi.fn();

    renderMistakes({
      state: notebookWithArchive(),
      onArchiveCard,
      onRestoreCard,
    });

    fireEvent.click(within(screen.getByLabelText("错题词 Ardleigh")).getByRole("button", { name: "归档" }));
    expect(onArchiveCard).toHaveBeenCalledWith("ardleigh");

    fireEvent.click(screen.getByRole("button", { name: "查看归档" }));

    expect(screen.getByRole("heading", { name: "归档错题" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "全部" })).toBeNull();
    expect(screen.queryByRole("button", { name: "随机 10" })).toBeNull();
    expect(screen.queryByRole("button", { name: "暂停" })).toBeNull();
    expect(screen.queryByRole("button", { name: "继续" })).toBeNull();
    expect(screen.queryByRole("button", { name: "停止" })).toBeNull();

    const archivedCard = screen.getByLabelText("归档错题词 429");
    fireEvent.click(within(archivedCard).getByRole("button", { name: "播放" }));
    fireEvent.click(within(archivedCard).getByRole("button", { name: "恢复到错题本" }));

    expect(play).toHaveBeenCalled();
    expect(onRestoreCard).toHaveBeenCalledWith("archived-429");
  });
});
