import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ExamWorkspace, type AudioController } from "./ExamWorkspace";
import type { LoadedPack, MarkResult, OverlayRegion, Question } from "../types/pack";

function fakePack(): LoadedPack {
  const vocabulary = [
    {
      id: "ardleigh",
      term: "Ardleigh",
      normalizedTerm: "ardleigh",
      acceptedVariants: [],
      meaningZh: "阿德利",
      spokenText: "Ardleigh",
      audio: "assets/audio/vocabulary/ardleigh.mp3",
    },
  ];

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
      id: "q11",
      number: 11,
      section: 2,
      responseType: "multi-choice",
      page: "page-012.png",
      focusOrder: 11,
      selectionLimit: 2,
      options: [
        { id: "A", label: "the gym" },
        { id: "C", label: "the indoor pool" },
      ],
    },
    {
      id: "q13",
      number: 13,
      section: 2,
      responseType: "blank",
      page: "page-012.png",
      focusOrder: 13,
      selectionLimit: null,
      options: [],
    },
  ];
  const overlays: OverlayRegion[] = [
    {
      questionId: "q1",
      optionId: null,
      page: "page-010.png",
      interactionType: "blank",
      pixel: { x: 100, y: 100, w: 80, h: 30 },
      normalized: { x: 0.1, y: 0.1, w: 0.1, h: 0.03 },
      deterministicConfidence: 1,
      visionConfidence: 1,
      confidence: 1,
      validationEvidence: [],
    },
    {
      questionId: "q11",
      optionId: "A",
      page: "page-012.png",
      interactionType: "choice-option",
      pixel: { x: 120, y: 140, w: 24, h: 24 },
      normalized: { x: 0.12, y: 0.14, w: 0.03, h: 0.03 },
      deterministicConfidence: 1,
      visionConfidence: 1,
      confidence: 1,
      validationEvidence: [],
    },
    {
      questionId: "q13",
      optionId: null,
      page: "page-012.png",
      interactionType: "blank",
      pixel: { x: 180, y: 180, w: 80, h: 30 },
      normalized: { x: 0.18, y: 0.18, w: 0.1, h: 0.03 },
      deterministicConfidence: 1,
      visionConfidence: 1,
      confidence: 1,
      validationEvidence: [],
    },
  ];

  return {
    baseUrl: "/packs/cambridge-10/test-1/listening/",
    manifest: {
      packId: "cambridge-10-test-1-listening",
      schemaVersion: 1,
      status: "released",
      title: "Cambridge IELTS 10 Test 1 Listening",
      sections: [
        {
          number: 1,
          title: "Listening Section 01",
          questionNumbers: [1],
          audio: "assets/audio/section-01.mp3",
          pages: ["assets/pages/page-010.png"],
        },
        {
          number: 2,
          title: "Listening Section 02",
          questionNumbers: [11, 13],
          audio: "assets/audio/section-02.mp3",
          pages: ["assets/pages/page-012.png"],
        },
      ],
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
    overlays,
    transcript: [],
    transcriptTimings: null,
    vocabulary,
    questionsById: new Map(questions.map((question) => [question.id, question])),
    answersByQuestionId: new Map(),
    overlaysByQuestionId: new Map([["q1", overlays]]),
    vocabularyById: new Map(vocabulary.map((item) => [item.id, item])),
  };
}

function packWithSectionOneTimings(): LoadedPack {
  return {
    ...fakePack(),
    transcript: [
      {
        section: 1,
        segments: [
          {
            order: 1,
            speaker: "MAN",
            text: "Good morning.",
            answerRefs: [],
            startTime: null,
            endTime: null,
          },
        ],
      },
    ],
    transcriptTimings: {
      schemaVersion: "yasi.transcript-timings.v1",
      status: "verified",
      sections: [
        {
          section: 1,
          status: "verified",
          wordTimings: [
            {
              section: 1,
              segmentOrder: 1,
              tokenIndex: 0,
              token: "Good",
              normalized: "good",
              start: 42.5,
              end: 42.9,
              requiresReview: true,
              riskTypes: ["answer-near"],
              review: { decision: "approved", reviewId: "s01-g0000" },
            },
          ],
        },
      ],
    },
  };
}

function packWithIntensiveListening(): LoadedPack {
  return {
    ...fakePack(),
    manifest: {
      ...fakePack().manifest,
      assets: {
        ...fakePack().manifest.assets,
        intensiveListening: "intensive-listening.json",
      },
    },
    transcript: [
      {
        section: 1,
        segments: [
          {
            order: 1,
            speaker: "WOMAN",
            text: "Good morning. I need a photo card.",
            answerRefs: [],
            startTime: null,
            endTime: null,
          },
        ],
      },
      {
        section: 2,
        segments: [
          {
            order: 1,
            speaker: "MAN",
            text: "Bring your membership card.",
            answerRefs: [],
            startTime: null,
            endTime: null,
          },
        ],
      },
    ],
    intensiveListening: {
      schemaVersion: "yasi.intensive-listening.v1",
      sections: [
        {
          section: 1,
          blanks: [
            {
              id: "il-s01-seg001-t005-t006",
              segmentOrder: 1,
              startTokenIndex: 5,
              endTokenIndex: 6,
              answer: "photo card",
              acceptedVariants: [],
              reason: "IELTS noun phrase with spelling value.",
              tags: ["noun-phrase"],
            },
          ],
        },
        {
          section: 2,
          blanks: [
            {
              id: "il-s02-seg001-t002-t002",
              segmentOrder: 1,
              startTokenIndex: 2,
              endTokenIndex: 2,
              answer: "membership",
              acceptedVariants: [],
              reason: "Common IELTS spelling risk.",
              tags: ["spelling-risk"],
            },
          ],
        },
      ],
    },
  } as LoadedPack;
}

function packWithTwoBlankSectionOne(): LoadedPack {
  const pack = fakePack();
  const secondBlank: Question = {
    id: "q2",
    number: 2,
    section: 1,
    responseType: "blank",
    page: "page-010.png",
    focusOrder: 2,
    selectionLimit: null,
    options: [],
  };
  const secondOverlay: OverlayRegion = {
    questionId: "q2",
    optionId: null,
    page: "page-010.png",
    interactionType: "blank",
    pixel: { x: 220, y: 100, w: 80, h: 30 },
    normalized: { x: 0.22, y: 0.1, w: 0.1, h: 0.03 },
    deterministicConfidence: 1,
    visionConfidence: 1,
    confidence: 1,
    validationEvidence: [],
  };

  return {
    ...pack,
    manifest: {
      ...pack.manifest,
      sections: pack.manifest.sections.map((section) =>
        section.number === 1 ? { ...section, questionNumbers: [1, 2] } : section,
      ),
    },
    questions: [...pack.questions, secondBlank],
    overlays: [...pack.overlays, secondOverlay],
    questionsById: new Map([...pack.questions, secondBlank].map((question) => [question.id, question])),
    overlaysByQuestionId: new Map([
      ["q1", [pack.overlays[0]]],
      ["q2", [secondOverlay]],
    ]),
  };
}

const submittedResult: MarkResult = {
  score: 0,
  total: 2,
  byQuestion: {
    q1: {
      questionId: "q1",
      correct: false,
      expected: ["Ardleigh"],
      actual: "",
    },
    q11: {
      questionId: "q11",
      correct: false,
      expected: ["A", "C"],
      actual: "",
    },
  },
  incorrectIds: ["q1", "q11"],
};

describe("ExamWorkspace", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("pauses current audio when switching section", async () => {
    const audioController: AudioController = {
      pause: vi.fn(),
      play: vi.fn(),
      seek: vi.fn(),
      getPosition: vi.fn(() => 48),
    };

    render(
      <ExamWorkspace
        pack={fakePack()}
        activeSection={1}
        audioController={audioController}
        answers={{}}
        onAnswerChange={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: "02" }));

    expect(audioController.pause).toHaveBeenCalledWith(1);
  });

  it("clears the local marking result when an answer changes after submit", () => {
    const onAnswerChange = vi.fn();
    const { container } = render(
      <ExamWorkspace
        pack={fakePack()}
        activeSection={1}
        answers={{}}
        onAnswerChange={onAnswerChange}
        onSubmit={() => submittedResult}
      />,
    );

    const submitButton = container.querySelector<HTMLButtonElement>(".primary-submit");
    expect(submitButton).not.toBeNull();
    fireEvent.click(submitButton!);
    expect(screen.getByText(/Raw score: 0 \/ 1/)).toBeTruthy();
    const questionScroll = container.querySelector<HTMLElement>(".question-scroll");
    expect(questionScroll).not.toBeNull();
    expect(within(questionScroll!).getByRole("button", { name: "显示第 1 题正确答案" })).toBeTruthy();
    expect(within(questionScroll!).queryByText("正确答案：Ardleigh")).toBeNull();

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Ardleigh" } });

    expect(onAnswerChange).toHaveBeenCalledWith("q1", "Ardleigh");
    expect(screen.queryByText(/Raw score/)).toBeNull();
    expect(screen.queryByText("正确答案：Ardleigh")).toBeNull();
  });

  it("shows accepted answer forms after submitting without replacing the user's answer", () => {
    const { container } = render(
      <ExamWorkspace
        pack={fakePack()}
        activeSection={1}
        answers={{ q1: "Ardley" }}
        onAnswerChange={vi.fn()}
        onSubmit={() => ({
          ...submittedResult,
          byQuestion: {
            ...submittedResult.byQuestion,
            q1: {
              questionId: "q1",
              correct: false,
              expected: ["Ardleigh"],
              actual: "Ardley",
            },
          },
        })}
      />,
    );

    const submitButton = container.querySelector<HTMLButtonElement>(".primary-submit");
    expect(submitButton).not.toBeNull();
    fireEvent.click(submitButton!);

    expect(within(container).getByRole("textbox")).toHaveValue("Ardley");
    const questionScroll = container.querySelector<HTMLElement>(".question-scroll");
    expect(questionScroll).not.toBeNull();
    expect(within(questionScroll!).getByRole("button", { name: "显示第 1 题正确答案" })).toBeTruthy();
    expect(within(questionScroll!).queryByText("正确答案：Ardleigh")).toBeNull();
  });

  it("reveals blank accepted answers one at a time and keeps each toggle across section switches", () => {
    const { container } = render(
      <ExamWorkspace
        pack={packWithTwoBlankSectionOne()}
        activeSection={1}
        answers={{ q1: "Ardley", q2: "Bristl" }}
        onAnswerChange={vi.fn()}
        onSubmit={() => ({
          score: 0,
          total: 2,
          byQuestion: {
            q1: {
              questionId: "q1",
              correct: false,
              expected: ["Ardleigh"],
              actual: "Ardley",
            },
            q2: {
              questionId: "q2",
              correct: false,
              expected: ["Bristol"],
              actual: "Bristl",
            },
          },
          incorrectIds: ["q1", "q2"],
        })}
      />,
    );

    fireEvent.click(container.querySelector<HTMLButtonElement>(".primary-submit")!);

    const questionScroll = container.querySelector<HTMLElement>(".question-scroll");
    expect(questionScroll).not.toBeNull();
    const questionLayer = within(questionScroll!);

    expect(questionLayer.queryByText("正确答案：Ardleigh")).toBeNull();
    expect(questionLayer.queryByText("正确答案：Bristol")).toBeNull();

    fireEvent.click(questionLayer.getByRole("button", { name: "显示第 1 题正确答案" }));

    expect(questionLayer.getByText("正确答案：Ardleigh")).toBeTruthy();
    expect(questionLayer.queryByText("正确答案：Bristol")).toBeNull();
    expect(questionLayer.getByRole("button", { name: "隐藏第 1 题正确答案" })).toBeTruthy();
    expect(questionLayer.getByRole("button", { name: "显示第 2 题正确答案" })).toBeTruthy();

    fireEvent.click(screen.getByRole("tab", { name: "02" }));
    fireEvent.click(screen.getByRole("tab", { name: "01" }));

    expect(within(container.querySelector<HTMLElement>(".question-scroll")!).getByText("正确答案：Ardleigh")).toBeTruthy();
    expect(within(container.querySelector<HTMLElement>(".question-scroll")!).queryByText("正确答案：Bristol")).toBeNull();
  });

  it("shows accepted choice answers after submitting", () => {
    const { container } = render(
      <ExamWorkspace
        pack={fakePack()}
        activeSection={2}
        answers={{ q11: "B" }}
        onAnswerChange={vi.fn()}
        onSubmit={() => ({
          ...submittedResult,
          byQuestion: {
            ...submittedResult.byQuestion,
            q11: {
              questionId: "q11",
              correct: false,
              expected: ["A", "C"],
              actual: "B",
            },
          },
        })}
      />,
    );

    const submitButton = container.querySelector<HTMLButtonElement>(".primary-submit");
    expect(submitButton).not.toBeNull();
    fireEvent.click(submitButton!);

    expect(within(container).getByText("你的答案：B")).toBeTruthy();
    expect(within(container).getByText("正确答案：A / C")).toBeTruthy();
  });

  it("disables submit and shows readiness hint before any answer is entered", () => {
    render(
      <ExamWorkspace
        pack={fakePack()}
        activeSection={1}
        answers={{}}
        canSubmit={false}
        onAnswerChange={vi.fn()}
      />,
    );

    const submitButton = screen.getByRole("button", { name: "提交答案" });
    expect(submitButton).toBeDisabled();
    expect(screen.getByText("先完成至少一个答案")).toBeTruthy();
  });

  it("disables transcript shadowing when the active section has no verified timings", () => {
    render(
      <ExamWorkspace
        pack={fakePack()}
        activeSection={1}
        answers={{}}
        onAnswerChange={vi.fn()}
      />,
    );

    const shadowingButton = screen.getByRole("button", { name: "原文跟读" });

    expect(shadowingButton).toBeDisabled();
    expect(screen.getByText("等待逐词时间轴")).toBeTruthy();
  });

  it("opens the Section 01 transcript panel and records transcript viewing", () => {
    const onMarkTranscriptViewed = vi.fn();
    const { container } = render(
      <ExamWorkspace
        pack={packWithSectionOneTimings()}
        activeSection={1}
        answers={{}}
        onAnswerChange={vi.fn()}
        onMarkTranscriptViewed={onMarkTranscriptViewed}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "打开原文" }));

    expect(onMarkTranscriptViewed).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText("Section 01 原文跟读")).toBeTruthy();
    expect(screen.getByRole("button", { name: "收起原文" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Good" })).toHaveClass("transcript-word--review-approved");
    expect(container.querySelector(".workspace-body")).toHaveClass("workspace-body--with-transcript");
  });

  it("opens transcript shadowing when timing status is preview", () => {
    const pack = packWithSectionOneTimings();
    pack.transcriptTimings = {
      ...pack.transcriptTimings!,
      status: "preview",
      sections: pack.transcriptTimings!.sections.map((section) => ({ ...section, status: "preview" })),
    };
    render(
      <ExamWorkspace
        pack={pack}
        activeSection={1}
        answers={{}}
        onAnswerChange={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "打开原文" }));

    expect(screen.getByLabelText("Section 01 原文跟读")).toBeTruthy();
  });

  it("opens the transcript panel without changing native audio time or play state", () => {
    const playSpy = vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
    const pauseSpy = vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => undefined);
    const { container } = render(
      <ExamWorkspace
        pack={packWithSectionOneTimings()}
        activeSection={1}
        answers={{}}
        onAnswerChange={vi.fn()}
      />,
    );
    const audio = container.querySelector<HTMLAudioElement>("audio");
    expect(audio).not.toBeNull();
    audio!.currentTime = 37;
    Object.defineProperty(audio!, "paused", { configurable: true, value: false });

    fireEvent.click(screen.getByRole("button", { name: "打开原文" }));

    expect(audio!.currentTime).toBe(37);
    expect(playSpy).not.toHaveBeenCalled();
    expect(pauseSpy).not.toHaveBeenCalled();
  });

  it("seeks native audio and records position when a transcript token is clicked", () => {
    const onAudioPositionChange = vi.fn();
    const { container } = render(
      <ExamWorkspace
        pack={packWithSectionOneTimings()}
        activeSection={1}
        answers={{}}
        onAnswerChange={vi.fn()}
        onAudioPositionChange={onAudioPositionChange}
      />,
    );
    const audio = container.querySelector<HTMLAudioElement>("audio");
    expect(audio).not.toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "打开原文" }));
    fireEvent.click(screen.getByRole("button", { name: "Good" }));

    expect(audio!.currentTime).toBe(42.5);
    expect(onAudioPositionChange).toHaveBeenLastCalledWith(1, 42.5);
  });

  it("does not reveal answers for an unsubmitted section after section-scoped submit", () => {
    const { container } = render(
      <ExamWorkspace
        pack={fakePack()}
        activeSection={1}
        answers={{ q1: "Ardley" }}
        canSubmit
        onAnswerChange={vi.fn()}
        onSubmit={() => ({
          score: 0,
          total: 1,
          byQuestion: {
            q1: {
              questionId: "q1",
              correct: false,
              expected: ["Ardleigh"],
              actual: "Ardley",
            },
          },
          incorrectIds: ["q1"],
        })}
      />,
    );

    fireEvent.click(container.querySelector<HTMLButtonElement>(".primary-submit")!);

    expect(screen.getByText(/Raw score: 0 \/ 1/)).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "02" }));
    expect(screen.queryByText("正确答案：A / C")).toBeNull();
  });

  it("shows active-section feedback only and keeps actions above scoring", () => {
    const { container } = render(
      <ExamWorkspace
        pack={fakePack()}
        activeSection={1}
        answers={{ q1: "Ardley" }}
        canSubmit
        onAnswerChange={vi.fn()}
        onSubmit={() => ({
          score: 0,
          total: 1,
          byQuestion: {
            q1: {
              questionId: "q1",
              correct: false,
              expected: ["Ardleigh"],
              actual: "Ardley",
            },
          },
          incorrectIds: ["q1"],
        })}
      />,
    );

    fireEvent.click(container.querySelector<HTMLButtonElement>(".primary-submit")!);
    fireEvent.click(screen.getByRole("tab", { name: "02" }));

    const sidePanel = container.querySelector(".workspace-side-panel");
    const actionRail = sidePanel?.querySelector(".action-rail");
    const feedbackCard = sidePanel?.querySelector(".feedback-card");

    expect(screen.queryByText(/Raw score: 0 \/ 1/)).toBeNull();
    expect(screen.queryByText("Section 01")).toBeNull();
    expect(screen.queryByText("正确答案：Ardleigh")).toBeNull();
    expect(screen.getByLabelText("练习进度")).toHaveTextContent("已作答 0 / 2");
    expect(screen.getByRole("button", { name: "下一错误题" })).toBeDisabled();
    expect(actionRail).not.toBeNull();
    expect(feedbackCard).not.toBeNull();
    expect(sidePanel?.children[0]).toBe(actionRail);
    expect(sidePanel?.children[1]).toBe(feedbackCard);
  });

  it("does not mark unsubmitted section answers as incorrect when result omits that question", () => {
    render(
      <ExamWorkspace
        pack={fakePack()}
        activeSection={1}
        answers={{ q1: "Ardley", q13: "library" }}
        result={{
          score: 0,
          total: 1,
          byQuestion: {
            q1: {
              questionId: "q1",
              correct: false,
              expected: ["Ardleigh"],
              actual: "Ardley",
            },
          },
          incorrectIds: ["q1"],
        }}
        onAnswerChange={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: "02" }));

    expect(screen.getByLabelText("第 13 题")).not.toHaveAttribute("data-status", "incorrect");
  });

  it("keeps next-incorrect navigation scoped to the active section", () => {
    Element.prototype.scrollIntoView = vi.fn();
    const onSectionChange = vi.fn();

    render(
      <ExamWorkspace
        pack={fakePack()}
        activeSection={1}
        answers={{ q11: "B" }}
        result={{
          score: 0,
          total: 1,
          byQuestion: {
            q11: {
              questionId: "q11",
              correct: false,
              expected: ["A", "C"],
              actual: "B",
            },
          },
          incorrectIds: ["q11"],
        }}
        nextIncorrectId="q11"
        onAnswerChange={vi.fn()}
        onSectionChange={onSectionChange}
      />,
    );

    expect(screen.getByRole("button", { name: "下一错误题" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "下一错误题" }));

    expect(onSectionChange).not.toHaveBeenCalled();
    expect(screen.getByRole("tab", { name: "01" })).toHaveAttribute("data-active", "true");
  });

  it("groups feedback and practice actions in a scrollable side panel", () => {
    const { container } = render(
      <ExamWorkspace
        pack={fakePack()}
        activeSection={1}
        answers={{}}
        onAnswerChange={vi.fn()}
      />,
    );

    const sidePanel = container.querySelector(".workspace-side-panel");

    expect(sidePanel).not.toBeNull();
    expect(sidePanel?.querySelector(".feedback-card")).not.toBeNull();
    expect(sidePanel?.querySelector(".action-rail")).not.toBeNull();
  });

  it("opens Intensive Listening only for the current submitted section", () => {
    const onOpenIntensiveListening = vi.fn();

    render(
      <ExamWorkspace
        pack={packWithIntensiveListening()}
        activeSection={1}
        answers={{ q1: "Ardleigh" }}
        result={{
          score: 1,
          total: 1,
          byQuestion: {
            q1: {
              questionId: "q1",
              correct: true,
              expected: ["Ardleigh"],
              actual: "Ardleigh",
            },
          },
          incorrectIds: [],
        }}
        onAnswerChange={vi.fn()}
        onOpenIntensiveListening={onOpenIntensiveListening}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "精听" }));
    expect(onOpenIntensiveListening).toHaveBeenCalledWith(1);

    fireEvent.click(screen.getByRole("tab", { name: "02" }));

    expect(screen.getByRole("button", { name: "精听" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "精听" }));
    expect(onOpenIntensiveListening).toHaveBeenCalledTimes(1);
  });

  it("retains playback rate across section switches without requiring audio controller rate methods", () => {
    const audioController: AudioController = {
      pause: vi.fn(),
    };
    const { container } = render(
      <ExamWorkspace
        pack={fakePack()}
        activeSection={1}
        answers={{}}
        audioController={audioController}
        onAnswerChange={vi.fn()}
      />,
    );

    const audio = container.querySelector<HTMLAudioElement>("audio");
    expect(audio).not.toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "1.25x" }));
    expect(audio!.playbackRate).toBe(1.25);
    expect(screen.getByRole("button", { name: "1.25x" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "1.25x" })).toHaveAttribute("data-active", "true");

    fireEvent.click(screen.getByRole("tab", { name: "02" }));

    const sectionTwoAudio = container.querySelector<HTMLAudioElement>("audio");
    expect(sectionTwoAudio).not.toBeNull();
    expect(sectionTwoAudio!.playbackRate).toBe(1.25);
    expect(screen.getByRole("button", { name: "1.25x" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "1.25x" })).toHaveAttribute("data-active", "true");
  });

  it("resets playback rate to normal speed when the practice is reset", () => {
    const onReset = vi.fn();
    const { container } = render(
      <ExamWorkspace
        pack={fakePack()}
        activeSection={1}
        answers={{}}
        audioController={{ pause: vi.fn() }}
        onAnswerChange={vi.fn()}
        onReset={onReset}
      />,
    );

    const audio = container.querySelector<HTMLAudioElement>("audio");
    expect(audio).not.toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "1.25x" }));
    expect(audio!.playbackRate).toBe(1.25);

    fireEvent.click(screen.getByRole("button", { name: "重置练习" }));
    fireEvent.click(screen.getByRole("button", { name: "确认重置" }));

    expect(onReset).toHaveBeenCalledTimes(1);
    expect(audio!.playbackRate).toBe(1);
    expect(screen.getByRole("button", { name: "1x" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "1x" })).toHaveAttribute("data-active", "true");
  });

  it("wires built-in audio controls to the native audio element", () => {
    const playSpy = vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
    const pauseSpy = vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => undefined);
    const onAudioPositionChange = vi.fn();

    const { container } = render(
      <ExamWorkspace
        pack={fakePack()}
        activeSection={1}
        answers={{}}
        audioPositions={{ "1": 12 }}
        onAudioPositionChange={onAudioPositionChange}
      />,
    );
    const audio = container.querySelector<HTMLAudioElement>("audio");
    const buttons = container.querySelectorAll<HTMLButtonElement>(".audio-player__controls button");

    expect(audio).not.toBeNull();
    expect(buttons).toHaveLength(4);

    fireEvent.loadedMetadata(audio!);
    expect(audio!.currentTime).toBe(12);

    fireEvent.click(buttons[0]);
    expect(playSpy).toHaveBeenCalled();

    audio!.currentTime = 10;
    fireEvent.click(buttons[2]);
    expect(audio!.currentTime).toBe(5);
    expect(onAudioPositionChange).toHaveBeenLastCalledWith(1, 5);

    fireEvent.click(buttons[3]);
    expect(audio!.currentTime).toBe(10);
    expect(onAudioPositionChange).toHaveBeenLastCalledWith(1, 10);

    Object.defineProperty(audio!, "paused", { configurable: true, value: false });
    fireEvent.click(buttons[1]);
    expect(pauseSpy).toHaveBeenCalled();
  });
});
