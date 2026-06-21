import { useMemo, useRef, useState } from "react";
import type { IntensiveListeningArtifact, IntensiveListeningBlank, LoadedPack, TranscriptSection } from "../types/pack";
import type {
  IntensiveListeningMarking,
  IntensiveListeningSectionState,
  IntensiveListeningSessionState,
} from "../lib/intensiveListening";
import { tokenizeTranscriptText } from "../lib/transcriptTokens";
import AudioPlayer from "./AudioPlayer";

export type { IntensiveListeningArtifact, IntensiveListeningBlank, IntensiveListeningSection } from "../types/pack";
export type {
  IntensiveListeningMarking,
  IntensiveListeningSectionState,
  IntensiveListeningSessionState,
} from "../lib/intensiveListening";

export interface IntensiveListeningViewProps {
  pack: LoadedPack;
  activeSection: number;
  session: IntensiveListeningSessionState;
  unlockedSections: number[];
  audioPositions: Record<string, number>;
  onAnswerChange: (section: number, blankId: string, value: string) => void;
  onAudioPositionChange: (section: number, position: number) => void;
  onGoBack: () => void;
  onReset: (section: number) => void;
  onRevealAnswers: (section: number) => void;
  onRevealTranscript: (section: number) => void;
  onSectionChange: (section: number) => void;
  onSubmit: (section: number) => void;
}

function resolveAsset(baseUrl: string, path: string): string {
  if (/^https?:\/\//.test(path) || path.startsWith("/")) {
    return path;
  }
  return `${baseUrl.replace(/\/$/, "")}/${path.replace(/^\//, "")}`;
}

function sectionLabel(section: number): string {
  return String(section).padStart(2, "0");
}

function sectionStateFor(
  session: IntensiveListeningSessionState,
  section: number,
): IntensiveListeningSectionState {
  return (
    session.sections[String(section)] ?? {
      answers: {},
      marking: null,
      answerRevealed: false,
      transcriptRevealed: false,
    }
  );
}

function blanksByStartToken(blanks: IntensiveListeningBlank[]): Map<string, IntensiveListeningBlank> {
  const byStart = new Map<string, IntensiveListeningBlank>();
  for (const blank of blanks) {
    byStart.set(`${blank.segmentOrder}:${blank.startTokenIndex}`, blank);
  }
  return byStart;
}

function isTokenInsideBlank(blank: IntensiveListeningBlank, segmentOrder: number, tokenIndex: number): boolean {
  return (
    blank.segmentOrder === segmentOrder &&
    tokenIndex >= blank.startTokenIndex &&
    tokenIndex < blank.endTokenIndex
  );
}

function shouldHideTextPart(
  blanks: IntensiveListeningBlank[],
  segmentOrder: number,
  previousTokenIndex: number | null,
  nextTokenIndex: number | null,
): boolean {
  if (previousTokenIndex === null || nextTokenIndex === null) {
    return false;
  }
  return blanks.some(
    (blank) =>
      blank.segmentOrder === segmentOrder &&
      previousTokenIndex >= blank.startTokenIndex &&
      nextTokenIndex <= blank.endTokenIndex,
  );
}

function renderReferenceSegments(transcriptSection: TranscriptSection) {
  return transcriptSection.segments.map((segment) => (
    <p className="intensive-transcript__segment" key={segment.order}>
      {segment.speaker === null ? null : <strong>{segment.speaker}: </strong>}
      {segment.text}
    </p>
  ));
}

function markingStatus(marking: IntensiveListeningMarking | null, blankId: string): string | null {
  const result = marking?.[blankId];
  if (result === undefined) {
    return null;
  }
  return result.correct ? "拼写正确" : "拼写有误";
}

export function IntensiveListeningView({
  pack,
  activeSection,
  session,
  unlockedSections,
  audioPositions,
  onAnswerChange,
  onAudioPositionChange,
  onGoBack,
  onReset,
  onRevealAnswers,
  onRevealTranscript,
  onSectionChange,
  onSubmit,
}: IntensiveListeningViewProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [playbackRate, setPlaybackRate] = useState(1);
  const activeManifestSection =
    pack.manifest.sections.find((section) => section.number === activeSection) ?? pack.manifest.sections[0];
  const activeTranscriptSection = pack.transcript.find((section) => section.section === activeSection) ?? null;
  const drillSection =
    pack.intensiveListening?.sections.find((section) => section.section === activeSection) ?? null;
  const unlocked = unlockedSections.includes(activeSection);
  const currentState = sectionStateFor(session, activeSection);
  const blankByStart = useMemo(
    () => blanksByStartToken(drillSection?.blanks ?? []),
    [drillSection],
  );

  if (activeManifestSection === undefined) {
    return (
      <main className="intensive-shell" role="main">
        <section className="intensive-locked">
          <h1>精听不可用</h1>
          <p>练习包缺少 Section 配置。</p>
          <button className="secondary-action" onClick={onGoBack} type="button">
            返回练习
          </button>
        </section>
      </main>
    );
  }

  const audioSrc = resolveAsset(pack.baseUrl, activeManifestSection.audio);
  const canUseDrill = unlocked && drillSection !== null && activeTranscriptSection !== null;
  const label = sectionLabel(activeSection);

  function renderDrillSegments() {
    if (activeTranscriptSection === null || drillSection === null) {
      return null;
    }

    if (currentState.transcriptRevealed) {
      return renderReferenceSegments(activeTranscriptSection);
    }

    return activeTranscriptSection.segments.map((segment) => {
      const parts = tokenizeTranscriptText(segment.text);
      let previousWordIndex: number | null = null;

      return (
        <p className="intensive-transcript__segment" key={segment.order}>
          {segment.speaker === null ? null : <strong>{segment.speaker}: </strong>}
          {parts.map((part, partIndex) => {
            if (part.kind === "text") {
              const nextWord = parts
                .slice(partIndex + 1)
                .find((candidate) => candidate.kind === "word");
              if (
                shouldHideTextPart(
                  drillSection.blanks,
                  segment.order,
                  previousWordIndex,
                  nextWord?.kind === "word" ? nextWord.tokenIndex : null,
                )
              ) {
                return null;
              }
              return <span key={`${segment.order}:text:${partIndex}`}>{part.text}</span>;
            }

            const blank = blankByStart.get(`${segment.order}:${part.tokenIndex}`);
            const insideNonStartBlank = drillSection.blanks.some(
              (candidate) =>
                candidate.startTokenIndex !== part.tokenIndex &&
                isTokenInsideBlank(candidate, segment.order, part.tokenIndex),
            );
            previousWordIndex = part.tokenIndex;

            if (insideNonStartBlank) {
              return null;
            }

            if (blank === undefined) {
              return <span key={`${segment.order}:word:${part.tokenIndex}`}>{part.text}</span>;
            }

            const blankIndex = drillSection.blanks.findIndex((candidate) => candidate.id === blank.id) + 1;
            const answerValue = currentState.answers[blank.id] ?? "";
            const result = currentState.marking?.[blank.id];
            const status = markingStatus(currentState.marking, blank.id);
            return (
              <span className="intensive-blank" key={blank.id}>
                <input
                  aria-label={`精听空 ${blankIndex}`}
                  disabled={currentState.transcriptRevealed}
                  value={answerValue}
                  onChange={(event) => onAnswerChange(activeSection, blank.id, event.currentTarget.value)}
                />
                {status === null ? null : (
                  <span
                    className="intensive-blank__status"
                    data-status={result?.correct ? "correct" : "incorrect"}
                  >
                    {status}
                  </span>
                )}
                {currentState.answerRevealed && result !== undefined ? (
                  <span className="intensive-blank__answer">正确答案：{result.expected}</span>
                ) : null}
              </span>
            );
          })}
        </p>
      );
    });
  }

  return (
    <main className="intensive-shell" role="main">
      <header className="intensive-topbar">
        <div>
          <p className="eyebrow">Intensive Listening</p>
          <h1>Section {label} 精听</h1>
        </div>
        <nav aria-label="精听 Section" className="section-nav">
          {pack.manifest.sections.map((section) => {
            const sectionUnlocked = unlockedSections.includes(section.number);
            const hasDrill =
              pack.intensiveListening?.sections.some((drill) => drill.section === section.number) ?? false;
            return (
              <button
                aria-selected={section.number === activeSection}
                className="section-tab"
                data-active={section.number === activeSection ? "true" : undefined}
                disabled={!sectionUnlocked || !hasDrill}
                key={section.number}
                role="tab"
                type="button"
                onClick={() => onSectionChange(section.number)}
              >
                {sectionLabel(section.number)}
              </button>
            );
          })}
        </nav>
        <AudioPlayer
          audioRef={audioRef}
          initialPosition={audioPositions[String(activeSection)] ?? 0}
          playbackRate={playbackRate}
          section={activeSection}
          src={audioSrc}
          onPlaybackRateChange={setPlaybackRate}
          onPositionChange={onAudioPositionChange}
        />
      </header>

      {canUseDrill ? (
        <div className="intensive-body">
          <section aria-label={`Section ${label} 精听原文`} className="intensive-transcript">
            {renderDrillSegments()}
          </section>
          <aside aria-label="精听操作" className="action-rail">
            <button
              className="primary-submit"
              disabled={currentState.transcriptRevealed}
              onClick={() => onSubmit(activeSection)}
              type="button"
            >
              提交精听
            </button>
            <button
              className="secondary-action"
              disabled={currentState.transcriptRevealed}
              onClick={() => onRevealAnswers(activeSection)}
              type="button"
            >
              查看答案
            </button>
            <button className="secondary-action" onClick={() => onRevealTranscript(activeSection)} type="button">
              查看原文
            </button>
            <button className="secondary-action" onClick={() => onReset(activeSection)} type="button">
              重置精听
            </button>
            <button className="secondary-action" onClick={onGoBack} type="button">
              返回练习
            </button>
          </aside>
        </div>
      ) : (
        <section className="intensive-locked">
          <h1>Section {label} 精听未开放</h1>
          <p>{drillSection === null ? "当前 Section 缺少精听数据。" : "提交当前 Section 后开放精听。"}</p>
          <button className="secondary-action" onClick={onGoBack} type="button">
            返回练习
          </button>
        </section>
      )}
    </main>
  );
}

export default IntensiveListeningView;
