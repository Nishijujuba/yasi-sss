import { type KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { tokenizeTranscriptText } from "../lib/transcriptTokens";
import type { TranscriptSection } from "../types/pack";

export interface TranscriptWordTiming {
  section: number;
  segmentOrder: number;
  tokenIndex: number;
  token?: string;
  matchType?: string;
  match?: string;
  riskTypes?: string[];
  reasons?: string[];
  requiresReview?: boolean;
  review?: Record<string, unknown>;
  start?: number | null;
  end?: number | null;
  startTime?: number | null;
  endTime?: number | null;
}

export interface TranscriptTimingSection {
  section: number;
  wordTimings: TranscriptWordTiming[] | Record<string, TranscriptWordTiming>;
}

export interface TranscriptShadowingPanelProps {
  transcriptSection: TranscriptSection;
  timingSection?: TranscriptTimingSection | null;
  currentTime: number;
  onSeek: (start: number) => void;
  defaultFollow?: boolean;
  showTimingReviewMarkers?: boolean;
}

function timingKey(segmentOrder: number, tokenIndex: number): string {
  return `${segmentOrder}:${tokenIndex}`;
}

function classNames(...names: Array<string | false | null | undefined>): string {
  return names.filter(Boolean).join(" ");
}

interface NormalizedTranscriptWordTiming {
  section: number;
  segmentOrder: number;
  tokenIndex: number;
  token?: string;
  matchType?: string;
  match?: string;
  riskTypes?: string[];
  reasons?: string[];
  requiresReview?: boolean;
  review?: Record<string, unknown>;
  start: number;
  end: number;
}

function intervalStart(timing: TranscriptWordTiming): number | null {
  return typeof timing.start === "number" ? timing.start : typeof timing.startTime === "number" ? timing.startTime : null;
}

function intervalEnd(timing: TranscriptWordTiming): number | null {
  return typeof timing.end === "number" ? timing.end : typeof timing.endTime === "number" ? timing.endTime : null;
}

function normalizeWordTimings(
  timingSection: TranscriptTimingSection | null | undefined,
): NormalizedTranscriptWordTiming[] {
  const rawTimings = timingSection?.wordTimings;
  const timings = Array.isArray(rawTimings) ? rawTimings : Object.values(rawTimings ?? {});

  return timings
    .map((timing) => {
      const start = intervalStart(timing);
      const end = intervalEnd(timing);
      if (start === null || end === null) {
        return null;
      }
      return { ...timing, start, end };
    })
    .filter((timing): timing is NormalizedTranscriptWordTiming => timing !== null);
}

type ReviewMarkerTiming = Pick<
  TranscriptWordTiming,
  "requiresReview" | "riskTypes" | "review" | "matchType" | "match" | "reasons"
>;

function reviewDecision(timing: ReviewMarkerTiming): string {
  const decision = timing.review?.decision;
  return typeof decision === "string" ? decision : "";
}

function reviewMarkerClass(timing: ReviewMarkerTiming | undefined, showMarkers: boolean): string | false {
  if (!showMarkers || timing === undefined) {
    return false;
  }
  const decision = reviewDecision(timing);
  if (decision === "corrected") {
    return "transcript-word--review-corrected";
  }
  if (decision === "approved") {
    return "transcript-word--review-approved";
  }
  if (timing.requiresReview || timing.review !== undefined) {
    return "transcript-word--review-required";
  }
  return false;
}

function useActiveSegmentOrder(
  wordTimings: NormalizedTranscriptWordTiming[],
  currentTime: number,
  activeTiming: NormalizedTranscriptWordTiming | null,
): number | null {
  return useMemo(() => {
    if (activeTiming !== null) {
      return activeTiming.segmentOrder;
    }

    const intervals = new Map<number, { start: number; end: number }>();
    for (const timing of wordTimings) {
      const current = intervals.get(timing.segmentOrder);
      if (current === undefined) {
        intervals.set(timing.segmentOrder, { start: timing.start, end: timing.end });
      } else {
        current.start = Math.min(current.start, timing.start);
        current.end = Math.max(current.end, timing.end);
      }
    }

    for (const [segmentOrder, interval] of intervals) {
      if (interval.start <= currentTime && currentTime < interval.end) {
        return segmentOrder;
      }
    }

    return null;
  }, [activeTiming, currentTime, wordTimings]);
}

export function TranscriptShadowingPanel({
  transcriptSection,
  timingSection = null,
  currentTime,
  onSeek,
  defaultFollow = true,
  showTimingReviewMarkers = false,
}: TranscriptShadowingPanelProps) {
  const [isFollowing, setIsFollowing] = useState(defaultFollow);
  const activeWordRef = useRef<HTMLSpanElement | null>(null);
  const rawWordTimings = useMemo(() => {
    const rawTimings = timingSection?.wordTimings;
    return Array.isArray(rawTimings) ? rawTimings : Object.values(rawTimings ?? {});
  }, [timingSection]);
  const wordTimings = useMemo(() => normalizeWordTimings(timingSection), [timingSection]);
  const activeTiming = useMemo(
    () => wordTimings.find((timing) => timing.start <= currentTime && currentTime < timing.end) ?? null,
    [currentTime, wordTimings],
  );
  const activeSegmentOrder = useActiveSegmentOrder(wordTimings, currentTime, activeTiming);
  const wordTimingsByToken = useMemo(() => {
    const out = new Map<string, NormalizedTranscriptWordTiming>();
    for (const timing of wordTimings) {
      out.set(timingKey(timing.segmentOrder, timing.tokenIndex), timing);
    }
    return out;
  }, [wordTimings]);
  const reviewMarkersByToken = useMemo(() => {
    const out = new Map<string, TranscriptWordTiming>();
    for (const timing of rawWordTimings) {
      if (timing.requiresReview || timing.review !== undefined) {
        out.set(timingKey(timing.segmentOrder, timing.tokenIndex), timing);
      }
    }
    return out;
  }, [rawWordTimings]);
  const activeTimingIdentity =
    activeTiming === null ? "none" : timingKey(activeTiming.segmentOrder, activeTiming.tokenIndex);

  useEffect(() => {
    if (!isFollowing || activeWordRef.current === null) {
      return;
    }

    activeWordRef.current.scrollIntoView?.({ block: "center", inline: "nearest" });
  }, [activeTimingIdentity, isFollowing]);

  function pauseFollowing() {
    setIsFollowing(false);
  }

  function handleWordKeyDown(event: KeyboardEvent<HTMLSpanElement>, start: number) {
    if (event.key !== "Enter" && event.key !== " ") {
      return;
    }
    event.preventDefault();
    onSeek(start);
  }

  return (
    <section
      aria-label={`Section ${String(transcriptSection.section).padStart(2, "0")} 原文跟读`}
      className="transcript-shadowing-panel"
      onPointerDown={(event) => {
        if (event.currentTarget === event.target) {
          pauseFollowing();
        }
      }}
      onTouchStart={pauseFollowing}
      onWheel={pauseFollowing}
      role="region"
    >
      <div className="transcript-shadowing-panel__toolbar">
        <button
          className="transcript-shadowing-panel__follow"
          onClick={() => setIsFollowing(true)}
          type="button"
        >
          跟随当前词
        </button>
      </div>
      <div className="transcript-shadowing-panel__segments">
        {transcriptSection.segments.map((segment) => (
          <p
            className={classNames(
              "transcript-segment",
              segment.order === activeSegmentOrder && "transcript-segment--active",
            )}
            data-testid={`transcript-segment-${segment.order}`}
            key={segment.order}
          >
            {tokenizeTranscriptText(segment.text).map((part, partIndex) => {
              if (part.kind === "text") {
                return <span key={`text-${partIndex}`}>{part.text}</span>;
              }

              const timing = wordTimingsByToken.get(timingKey(segment.order, part.tokenIndex));
              const isActive =
                activeTiming?.segmentOrder === segment.order && activeTiming.tokenIndex === part.tokenIndex;

              if (timing === undefined) {
                const reviewMarker = reviewMarkersByToken.get(timingKey(segment.order, part.tokenIndex));
                return (
                  <span
                    className={classNames(
                      "transcript-word",
                      "transcript-word--untimed",
                      reviewMarkerClass(reviewMarker, showTimingReviewMarkers),
                    )}
                    key={`word-${part.tokenIndex}`}
                  >
                    {part.text}
                  </span>
                );
              }

              return (
                <span
                  aria-current={isActive ? "true" : undefined}
                  className={classNames(
                    "transcript-word",
                    reviewMarkerClass(timing, showTimingReviewMarkers),
                    isActive && "transcript-word--active",
                  )}
                  key={`word-${part.tokenIndex}`}
                  onClick={() => onSeek(timing.start)}
                  onKeyDown={(event) => handleWordKeyDown(event, timing.start)}
                  ref={isActive ? activeWordRef : null}
                  role="button"
                  tabIndex={0}
                >
                  {isActive ? <strong className="transcript-word__label">{part.text}</strong> : part.text}
                </span>
              );
            })}
          </p>
        ))}
      </div>
    </section>
  );
}

export default TranscriptShadowingPanel;
