import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ExamWorkspace, type AudioController } from "./ExamWorkspace";
import type { LoadedPack, MarkResult, OverlayRegion, Question } from "../types/pack";

function fakePack(): LoadedPack {
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
          questionNumbers: [11],
          audio: "assets/audio/section-02.mp3",
          pages: ["assets/pages/page-012.png"],
        },
      ],
      assets: {
        questions: "questions.json",
        answers: "answers.json",
        overlays: "overlays.json",
        transcript: "transcript.json",
      },
    },
    questions,
    answers: [],
    overlays,
    transcript: [],
    questionsById: new Map(questions.map((question) => [question.id, question])),
    answersByQuestionId: new Map(),
    overlaysByQuestionId: new Map([["q1", overlays]]),
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
    expect(screen.getByText(/Raw score: 0 \/ 2/)).toBeTruthy();

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Ardleigh" } });

    expect(onAnswerChange).toHaveBeenCalledWith("q1", "Ardleigh");
    expect(screen.queryByText(/Raw score/)).toBeNull();
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
