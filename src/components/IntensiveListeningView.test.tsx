import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type {
  IntensiveListeningArtifact,
  IntensiveListeningMarking,
  IntensiveListeningSessionState,
} from "../lib/intensiveListening";
import IntensiveListeningView from "./IntensiveListeningView";
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

const intensiveListening: IntensiveListeningArtifact = {
  schemaVersion: "yasi.intensive-listening.v1",
  sections: [
    {
      section: 1,
      blanks: [
        {
          id: "il-s01-seg001-t005-t007",
          segmentOrder: 1,
          startTokenIndex: 5,
          endTokenIndex: 7,
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
          id: "il-s02-seg001-t002-t003",
          segmentOrder: 1,
          startTokenIndex: 2,
          endTokenIndex: 3,
          answer: "membership",
          acceptedVariants: [],
          reason: "Common IELTS spelling risk.",
          tags: ["spelling-risk"],
        },
      ],
    },
  ],
};

function fakePack(): LoadedPack & { intensiveListening: IntensiveListeningArtifact } {
  return {
    baseUrl: "/packs/cambridge-10/test-1/listening",
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
        vocabulary: "vocabulary.json",
        intensiveListening: "intensive-listening.json",
      } as LoadedPack["manifest"]["assets"] & { intensiveListening: string },
    },
    questions,
    answers: [],
    overlays: [],
    transcript: [
      {
        section: 1,
        segments: [
          {
            order: 1,
            speaker: "WOMAN",
            text: "Good morning. I need a photo card today.",
            answerRefs: [],
            startTime: null,
            endTime: null,
          },
          {
            order: 2,
            speaker: "MAN",
            text: "The appointment is at nine.",
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
    transcriptTimings: null,
    vocabulary: [],
    questionsById: new Map(questions.map((question) => [question.id, question])),
    answersByQuestionId: new Map(),
    overlaysByQuestionId: new Map(),
    vocabularyById: new Map(),
    intensiveListening,
  };
}

const emptySession: IntensiveListeningSessionState = {
  version: 1,
  packId: "cambridge-10-test-1-listening",
  sections: {},
};

describe("IntensiveListeningView", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders a locked section as unavailable without exposing blank answers", () => {
    render(
      <IntensiveListeningView
        activeSection={2}
        audioPositions={{}}
        pack={fakePack()}
        session={emptySession}
        unlockedSections={[1]}
        onAnswerChange={vi.fn()}
        onAudioPositionChange={vi.fn()}
        onGoBack={vi.fn()}
        onReset={vi.fn()}
        onRevealAnswers={vi.fn()}
        onRevealTranscript={vi.fn()}
        onSectionChange={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: /Section 02 精听未开放/ })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "01" })).toBeEnabled();
    expect(screen.getByRole("tab", { name: "02" })).toBeDisabled();
    expect(screen.queryByText(/membership/)).toBeNull();
  });

  it("renders complete section audioscript with selected token spans replaced by inputs", () => {
    render(
      <IntensiveListeningView
        activeSection={1}
        audioPositions={{}}
        pack={fakePack()}
        session={{
          ...emptySession,
          sections: {
            "1": {
              answers: { "il-s01-seg001-t005-t007": "foto card" },
              marking: null,
              answerRevealed: false,
              transcriptRevealed: false,
            },
          },
        }}
        unlockedSections={[1]}
        onAnswerChange={vi.fn()}
        onAudioPositionChange={vi.fn()}
        onGoBack={vi.fn()}
        onReset={vi.fn()}
        onRevealAnswers={vi.fn()}
        onRevealTranscript={vi.fn()}
        onSectionChange={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    const transcript = screen.getByLabelText("Section 01 精听原文");
    expect(transcript).toHaveTextContent("Good morning. I need a");
    expect(transcript).toHaveTextContent("today.");
    expect(transcript).toHaveTextContent("The appointment is at nine.");
    expect(screen.queryByText(/photo card/)).toBeNull();
    expect(screen.getByLabelText("精听空 1")).toHaveValue("foto card");
  });

  it("submits, reveals answers, reveals transcript distinctly, and makes transcript reveal reference-only", () => {
    const marking: IntensiveListeningMarking = {
      "il-s01-seg001-t005-t007": {
        blankId: "il-s01-seg001-t005-t007",
        actual: "foto card",
        expected: "photo card",
        correct: false,
      },
    };
    const onSubmit = vi.fn();
    const onRevealAnswers = vi.fn();
    const onRevealTranscript = vi.fn();

    const { rerender } = render(
      <IntensiveListeningView
        activeSection={1}
        audioPositions={{}}
        pack={fakePack()}
        session={{
          ...emptySession,
          sections: {
            "1": {
              answers: { "il-s01-seg001-t005-t007": "foto card" },
              marking,
              answerRevealed: true,
              transcriptRevealed: false,
            },
          },
        }}
        unlockedSections={[1]}
        onAnswerChange={vi.fn()}
        onAudioPositionChange={vi.fn()}
        onGoBack={vi.fn()}
        onReset={vi.fn()}
        onRevealAnswers={onRevealAnswers}
        onRevealTranscript={onRevealTranscript}
        onSectionChange={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "提交精听" }));
    fireEvent.click(screen.getByRole("button", { name: "查看答案" }));
    fireEvent.click(screen.getByRole("button", { name: "查看原文" }));

    expect(onSubmit).toHaveBeenCalledWith(1);
    expect(onRevealAnswers).toHaveBeenCalledWith(1);
    expect(onRevealTranscript).toHaveBeenCalledWith(1);
    expect(screen.getByText("正确答案：photo card")).toBeTruthy();
    expect(screen.getByText("拼写有误")).toBeTruthy();

    rerender(
      <IntensiveListeningView
        activeSection={1}
        audioPositions={{}}
        pack={fakePack()}
        session={{
          ...emptySession,
          sections: {
            "1": {
              answers: { "il-s01-seg001-t005-t007": "foto card" },
              marking,
              answerRevealed: true,
              transcriptRevealed: true,
            },
          },
        }}
        unlockedSections={[1]}
        onAnswerChange={vi.fn()}
        onAudioPositionChange={vi.fn()}
        onGoBack={vi.fn()}
        onReset={vi.fn()}
        onRevealAnswers={onRevealAnswers}
        onRevealTranscript={onRevealTranscript}
        onSectionChange={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    expect(screen.getByText("Good morning. I need a photo card today.")).toBeTruthy();
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.getByRole("button", { name: "提交精听" })).toBeDisabled();
  });

  it("resets only Intensive Listening state through the dedicated reset handler", () => {
    const onReset = vi.fn();
    const onGoBack = vi.fn();

    render(
      <IntensiveListeningView
        activeSection={1}
        audioPositions={{}}
        pack={fakePack()}
        session={emptySession}
        unlockedSections={[1]}
        onAnswerChange={vi.fn()}
        onAudioPositionChange={vi.fn()}
        onGoBack={onGoBack}
        onReset={onReset}
        onRevealAnswers={vi.fn()}
        onRevealTranscript={vi.fn()}
        onSectionChange={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "重置精听" }));
    fireEvent.click(screen.getByRole("button", { name: "返回练习" }));

    expect(onReset).toHaveBeenCalledWith(1);
    expect(onGoBack).toHaveBeenCalledOnce();
  });
});
