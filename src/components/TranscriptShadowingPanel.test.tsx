import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TranscriptShadowingPanel, type TranscriptTimingSection } from "./TranscriptShadowingPanel";
import type { TranscriptSection } from "../types/pack";

const transcriptSection: TranscriptSection = {
  section: 1,
  segments: [
    {
      order: 1,
      speaker: "TRAVEL AGENT",
      text: "Good morning. World Tours.",
      answerRefs: [],
      startTime: null,
      endTime: null,
    },
    {
      order: 2,
      speaker: "ANDREA",
      text: "It’s £525.",
      answerRefs: [1],
      startTime: null,
      endTime: null,
    },
  ],
};

const timingSection: TranscriptTimingSection = {
  section: 1,
  wordTimings: [
    { section: 1, segmentOrder: 1, tokenIndex: 0, token: "Good", start: 0, end: 0.25 },
    { section: 1, segmentOrder: 1, tokenIndex: 1, token: "morning", start: 0.3, end: 0.6 },
    { section: 1, segmentOrder: 1, tokenIndex: 2, token: "World", start: 0.7, end: 0.9 },
    { section: 1, segmentOrder: 1, tokenIndex: 3, token: "Tours", start: 0.95, end: 1.2 },
    { section: 1, segmentOrder: 2, tokenIndex: 0, token: "It’s", start: 1.4, end: 1.6 },
    { section: 1, segmentOrder: 2, tokenIndex: 1, token: "£525", start: 1.65, end: 1.9 },
  ],
};

describe("TranscriptShadowingPanel", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("highlights the active word and segment", () => {
    render(
      <TranscriptShadowingPanel
        currentTime={0.35}
        onSeek={vi.fn()}
        timingSection={timingSection}
        transcriptSection={transcriptSection}
      />,
    );

    const activeWord = screen.getByRole("button", { name: "morning" });
    expect(activeWord).toHaveClass("transcript-word--active");
    expect(activeWord).toHaveAttribute("aria-current", "true");

    const activeSegment = screen.getByTestId("transcript-segment-1");
    expect(activeSegment).toHaveClass("transcript-segment--active");
    expect(screen.getByTestId("transcript-segment-2")).not.toHaveClass("transcript-segment--active");
  });

  it("accepts keyed pack timing records with startTime and endTime intervals", () => {
    render(
      <TranscriptShadowingPanel
        currentTime={1.7}
        onSeek={vi.fn()}
        timingSection={
          {
            section: 1,
            wordTimings: {
              "2:0": { section: 1, segmentOrder: 2, tokenIndex: 0, startTime: 1.4, endTime: 1.6 },
              "2:1": { section: 1, segmentOrder: 2, tokenIndex: 1, startTime: 1.65, endTime: 1.9 },
            },
          } as unknown as TranscriptTimingSection
        }
        transcriptSection={transcriptSection}
      />,
    );

    expect(screen.getByRole("button", { name: "£525" })).toHaveClass("transcript-word--active");
    expect(screen.getByTestId("transcript-segment-2")).toHaveClass("transcript-segment--active");
  });

  it("keeps the segment active during a timing gap without marking a word active", () => {
    render(
      <TranscriptShadowingPanel
        currentTime={0.65}
        onSeek={vi.fn()}
        timingSection={timingSection}
        transcriptSection={transcriptSection}
      />,
    );

    expect(screen.getByTestId("transcript-segment-1")).toHaveClass("transcript-segment--active");
    expect(document.querySelector(".transcript-word--active")).toBeNull();
  });

  it("shows timing review markers only when enabled", () => {
    const reviewedTimingSection: TranscriptTimingSection = {
      section: 1,
      wordTimings: [
        {
          section: 1,
          segmentOrder: 1,
          tokenIndex: 1,
          token: "morning",
          start: 0.3,
          end: 0.6,
          riskTypes: ["answer-near"],
          review: { decision: "corrected", reviewId: "s01-g0001" },
        },
      ],
    };
    const { rerender } = render(
      <TranscriptShadowingPanel
        currentTime={0}
        onSeek={vi.fn()}
        timingSection={reviewedTimingSection}
        transcriptSection={transcriptSection}
      />,
    );

    expect(screen.getByRole("button", { name: "morning" })).not.toHaveClass(
      "transcript-word--review-corrected",
    );

    rerender(
      <TranscriptShadowingPanel
        currentTime={0}
        onSeek={vi.fn()}
        showTimingReviewMarkers
        timingSection={reviewedTimingSection}
        transcriptSection={transcriptSection}
      />,
    );

    expect(screen.getByRole("button", { name: "morning" })).toHaveClass("transcript-word--review-corrected");
  });

  it("shows review markers for untimed preview tokens", () => {
    const previewTimingSection: TranscriptTimingSection = {
      section: 1,
      wordTimings: [
        {
          section: 1,
          segmentOrder: 1,
          tokenIndex: 1,
          token: "morning",
          start: undefined,
          end: undefined,
          requiresReview: true,
          riskTypes: ["answer-near"],
          review: { decision: "pending", reviewId: "s01-g0001" },
        },
      ],
    };

    render(
      <TranscriptShadowingPanel
        currentTime={0}
        onSeek={vi.fn()}
        showTimingReviewMarkers
        timingSection={previewTimingSection}
        transcriptSection={transcriptSection}
      />,
    );

    const untimedWord = screen.getByText("morning");
    expect(untimedWord).toHaveClass("transcript-word--untimed");
    expect(untimedWord).toHaveClass("transcript-word--review-required");
  });

  it("seeks to a word start when the learner clicks a word", () => {
    const onSeek = vi.fn();
    render(
      <TranscriptShadowingPanel
        currentTime={0}
        onSeek={onSeek}
        timingSection={timingSection}
        transcriptSection={transcriptSection}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "World" }));

    expect(onSeek).toHaveBeenCalledWith(0.7);
  });

  it("does not render speaker labels, answer references, or copy controls", () => {
    render(
      <TranscriptShadowingPanel
        currentTime={0}
        onSeek={vi.fn()}
        timingSection={timingSection}
        transcriptSection={transcriptSection}
      />,
    );

    expect(screen.queryByText("TRAVEL AGENT")).toBeNull();
    expect(screen.queryByText("ANDREA")).toBeNull();
    expect(screen.queryByText("Q1")).toBeNull();
    expect(screen.queryByRole("button", { name: /copy|复制/i })).toBeNull();
  });

  it("disables follow after manual transcript wheel scroll and restores it with the follow control", () => {
    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;
    const { rerender } = render(
      <TranscriptShadowingPanel
        currentTime={0.35}
        onSeek={vi.fn()}
        timingSection={timingSection}
        transcriptSection={transcriptSection}
      />,
    );

    expect(scrollIntoView).toHaveBeenCalledTimes(1);

    fireEvent.wheel(screen.getByRole("region", { name: "Section 01 原文跟读" }));
    rerender(
      <TranscriptShadowingPanel
        currentTime={0.8}
        onSeek={vi.fn()}
        timingSection={timingSection}
        transcriptSection={transcriptSection}
      />,
    );

    expect(scrollIntoView).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "跟随当前词" }));

    expect(scrollIntoView).toHaveBeenCalledTimes(2);
  });

  it("keeps following after its own automatic scroll event", () => {
    const originalScrollIntoView = Element.prototype.scrollIntoView;
    const scrollIntoView = vi.fn(function (this: Element) {
      this.closest(".transcript-shadowing-panel")?.dispatchEvent(new Event("scroll"));
    });
    Element.prototype.scrollIntoView = scrollIntoView;

    try {
      const { rerender } = render(
        <TranscriptShadowingPanel
          currentTime={0.35}
          onSeek={vi.fn()}
          timingSection={timingSection}
          transcriptSection={transcriptSection}
        />,
      );

      expect(scrollIntoView).toHaveBeenCalledTimes(1);

      rerender(
        <TranscriptShadowingPanel
          currentTime={1.7}
          onSeek={vi.fn()}
          timingSection={timingSection}
          transcriptSection={transcriptSection}
        />,
      );

      expect(screen.getByRole("button", { name: "£525" })).toHaveClass("transcript-word--active");
      expect(scrollIntoView).toHaveBeenCalledTimes(2);
    } finally {
      Element.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("wraps only word tokens as clickable controls", () => {
    render(
      <TranscriptShadowingPanel
        currentTime={0}
        onSeek={vi.fn()}
        timingSection={timingSection}
        transcriptSection={transcriptSection}
      />,
    );

    const firstSegment = screen.getByTestId("transcript-segment-1");
    expect(within(firstSegment).getAllByRole("button").map((button) => button.textContent)).toEqual([
      "Good",
      "morning",
      "World",
      "Tours",
    ]);
    expect(firstSegment).toHaveTextContent("Good morning. World Tours.");
  });
});
