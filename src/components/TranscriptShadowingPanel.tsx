import { type KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { tokenizeTranscriptText } from "../lib/transcriptTokens";
import type { TranscriptSection } from "../types/pack";

export interface TranscriptWordTiming {
  section: number;
  segmentOrder: number;
  tokenIndex: number;
  token?: string;
  start?: number;
  end?: number;
  startTime?: number;
  endTime?: number;
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
}: TranscriptShadowingPanelProps) {
  const [isFollowing, setIsFollowing] = useState(defaultFollow);
  const activeWordRef = useRef<HTMLSpanElement | null>(null);
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
  const activeTimingIdentity =
    activeTiming === null ? "none" : timingKey(activeTiming.segmentOrder, activeTiming.tokenIndex);

  useEffect(() => {
    if (!isFollowing || activeWordRef.current === null) {
      return;
    }

    activeWordRef.current.scrollIntoView?.({ block: "center", inline: "nearest" });
  }, [activeTimingIdentity, isFollowing]);

  function handleTranscriptScroll() {
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
      onScroll={handleTranscriptScroll}
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
                return (
                  <span className="transcript-word transcript-word--untimed" key={`word-${part.tokenIndex}`}>
                    {part.text}
                  </span>
                );
              }

              return (
                <span
                  aria-current={isActive ? "true" : undefined}
                  className={classNames("transcript-word", isActive && "transcript-word--active")}
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
