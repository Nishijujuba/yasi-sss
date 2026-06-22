import { useEffect, useMemo, useRef, useState } from "react";
import type { AnswerMap, LoadedPack, MarkResult } from "../types/pack";
import { useOptionalPracticeSession } from "../context/PracticeSessionContext";
import AudioPlayer from "./AudioPlayer";
import MarkingFeedback from "./MarkingFeedback";
import PackErrorScreen from "./PackErrorScreen";
import PracticeActions from "./PracticeActions";
import QuestionScrollArea from "./QuestionScrollArea";
import SectionNavigation from "./SectionNavigation";
import TranscriptShadowingPanel, {
  type TranscriptTimingSection as PanelTimingSection,
} from "./TranscriptShadowingPanel";
import type { TranscriptTimingSection as PackTimingSection } from "../types/pack";

export interface AudioController {
  pause: (section: number) => void;
  play?: (section: number) => void;
  seek?: (section: number, deltaSeconds: number) => void;
  getPosition?: (section: number) => number;
}

export interface ExamWorkspaceProps {
  pack?: LoadedPack | null;
  activeSection?: number;
  answers?: AnswerMap;
  result?: MarkResult | null;
  audioPositions?: Record<string, number>;
  audioController?: AudioController;
  onAnswerChange?: (questionId: string, value: string) => void;
  onAnswersChange?: (updates: AnswerMap) => void;
  onSectionChange?: (section: number) => void;
  onSubmit?: () => MarkResult | null | void;
  onReset?: () => void;
  onGoHome?: () => void;
  onAudioPositionChange?: (section: number, position: number) => void;
  onOpenIntensiveListening?: (section: number) => void;
  transcriptViewed?: boolean;
  onMarkTranscriptViewed?: () => void;
  nextIncorrectId?: string | null;
  canSubmit?: boolean;
}

const EMPTY_ANSWERS: AnswerMap = {};
const EMPTY_AUDIO_POSITIONS: Record<string, number> = {};

function resolveAsset(baseUrl: string, path: string): string {
  if (/^https?:\/\//.test(path) || path.startsWith("/")) {
    return path;
  }
  return `${baseUrl.replace(/\/$/, "")}/${path.replace(/^\//, "")}`;
}

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  const tag = target.tagName.toLowerCase();
  return tag === "input" || tag === "textarea" || tag === "select" || target.isContentEditable;
}

function focusQuestion(questionId: string): void {
  const control = document.querySelector<HTMLElement>(
    `[data-question-id="${questionId}"] input, [data-question-id="${questionId}"] button, [data-question-id="${questionId}"]`,
  );
  control?.scrollIntoView?.({ behavior: "smooth", block: "center" });
  control?.focus();
}

function timingSectionFor(pack: LoadedPack, section: number): PackTimingSection | null {
  const timings = pack.transcriptTimings;
  if (
    (timings?.status !== "verified" && timings?.status !== "preview") ||
    !Array.isArray(timings.sections)
  ) {
    return null;
  }
  return (
    timings.sections.find(
      (entry) =>
        entry.section === section &&
        (entry.status === "verified" || entry.status === "preview") &&
        entry.wordTimings.length > 0,
    ) ?? null
  );
}

function toPanelTimingSection(timingSection: PackTimingSection): PanelTimingSection {
  return {
    section: timingSection.section,
    wordTimings: Object.values(timingSection.wordTimings).map((timing) => ({
      section: timing.section,
      segmentOrder: timing.segmentOrder,
      tokenIndex: timing.tokenIndex,
      token: "",
      matchType: timing.matchType,
      match: timing.match,
      riskTypes: timing.riskTypes,
      reasons: timing.reasons,
      requiresReview: timing.requiresReview,
      review: timing.review,
      start: timing.start,
      end: timing.end,
    })),
  };
}

function hasIntensiveListeningDrill(pack: LoadedPack, section: number): boolean {
  return pack.intensiveListening?.sections.some((entry) => entry.section === section) ?? false;
}

function hasSubmittedSection(pack: LoadedPack, result: MarkResult | null, section: number): boolean {
  if (result === null) {
    return false;
  }
  return pack.questions.some(
    (question) => question.section === section && result.byQuestion[question.id] !== undefined,
  );
}

export function ExamWorkspace({
  pack,
  activeSection = 1,
  answers = EMPTY_ANSWERS,
  result = null,
  audioPositions = EMPTY_AUDIO_POSITIONS,
  audioController,
  onAnswerChange,
  onAnswersChange,
  onSectionChange,
  onSubmit,
  onReset,
  onGoHome,
  onAudioPositionChange,
  onOpenIntensiveListening,
  transcriptViewed,
  onMarkTranscriptViewed,
  nextIncorrectId,
  canSubmit = true,
}: ExamWorkspaceProps) {
  const practiceSession = useOptionalPracticeSession();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [currentSection, setCurrentSection] = useState(activeSection);
  const [localResult, setLocalResult] = useState<MarkResult | null>(null);
  const [localPositions, setLocalPositions] = useState<Record<string, number>>(audioPositions);
  const [playing, setPlaying] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [pendingFocusQuestionId, setPendingFocusQuestionId] = useState<string | null>(null);
  const [transcriptPanelOpen, setTranscriptPanelOpen] = useState(false);
  const [currentAudioTime, setCurrentAudioTime] = useState(localPositions[String(activeSection)] ?? 0);
  const [revealedExpectedAnswers, setRevealedExpectedAnswers] = useState<ReadonlySet<string>>(() => new Set());

  useEffect(() => {
    setCurrentSection(activeSection);
  }, [activeSection]);

  useEffect(() => {
    setLocalPositions(audioPositions);
  }, [audioPositions]);

  useEffect(() => {
    setCurrentAudioTime(localPositions[String(currentSection)] ?? 0);
  }, [currentSection, localPositions]);

  useEffect(() => {
    if (result === null) {
      setLocalResult(null);
    }
    setRevealedExpectedAnswers(new Set());
  }, [result]);

  const active = useMemo(() => {
    if (pack === null || pack === undefined) {
      return undefined;
    }
    return pack.manifest.sections.find((section) => section.number === currentSection) ?? pack.manifest.sections[0];
  }, [pack, currentSection]);

  useEffect(() => {
    if (pendingFocusQuestionId === null || pack === null || pack === undefined) {
      return;
    }
    const question = pack.questionsById.get(pendingFocusQuestionId);
    if (question !== undefined && question.section === currentSection) {
      focusQuestion(pendingFocusQuestionId);
      setPendingFocusQuestionId(null);
    }
  }, [currentSection, pack, pendingFocusQuestionId]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent): void {
      if (isTypingTarget(event.target)) {
        return;
      }

      if (event.key === "Enter" && !event.altKey && !event.ctrlKey && !event.metaKey && !event.shiftKey) {
        event.preventDefault();
        if (audioRef.current === null) {
          audioController?.play?.(currentSection);
          return;
        }
        if (playing) {
          audioRef.current.pause();
          audioController?.pause(currentSection);
          setPlaying(false);
        } else {
          void audioRef.current.play();
          audioController?.play?.(currentSection);
          setPlaying(true);
        }
      }

      if (event.altKey && event.key === "ArrowLeft") {
        event.preventDefault();
        if (audioRef.current !== null) {
          audioRef.current.currentTime = Math.max(audioRef.current.currentTime - 5, 0);
        }
        audioController?.seek?.(currentSection, -5);
      }

      if (event.altKey && event.key === "ArrowRight") {
        event.preventDefault();
        if (audioRef.current !== null) {
          audioRef.current.currentTime += 5;
        }
        audioController?.seek?.(currentSection, 5);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [audioController, currentSection, playing]);

  if (pack === null || pack === undefined) {
    return <PackErrorScreen message="没有可用的练习包。" />;
  }

  if (active === undefined) {
    return <PackErrorScreen message="练习包缺少 Section 配置。" />;
  }

  const loadedPack = pack;
  const effectiveResult = result ?? localResult;
  const effectiveTranscriptViewed = transcriptViewed ?? practiceSession?.transcriptViewed ?? false;
  const markTranscriptViewed = onMarkTranscriptViewed ?? practiceSession?.markTranscriptViewed;
  const sectionQuestions = loadedPack.questions.filter((question) => question.section === active.number);
  const sectionQuestionIds = new Set(sectionQuestions.map((question) => question.id));
  const activeSubmittedQuestionCount =
    effectiveResult === null
      ? 0
      : sectionQuestions.filter((question) => effectiveResult.byQuestion[question.id] !== undefined).length;
  const activeIncorrectIds =
    effectiveResult?.incorrectIds.filter((questionId) => sectionQuestionIds.has(questionId)) ?? [];
  const activeNextIncorrectId =
    nextIncorrectId !== null && nextIncorrectId !== undefined && sectionQuestionIds.has(nextIncorrectId)
      ? nextIncorrectId
      : activeIncorrectIds[0] ?? null;
  const audioSrc = resolveAsset(loadedPack.baseUrl, active.audio);
  const activeTranscriptSection = loadedPack.transcript.find((section) => section.section === active.number) ?? null;
  const activeTimingSection = timingSectionFor(loadedPack, active.number);
  const canOpenTranscriptPanel = activeTimingSection !== null && activeTranscriptSection !== null;
  const showTranscriptPanel = transcriptPanelOpen && activeTimingSection !== null && activeTranscriptSection !== null;
  const showTimingReviewMarkers = showTranscriptPanel && (effectiveResult !== null || effectiveTranscriptViewed || transcriptPanelOpen);
  const intensiveListeningAvailable = hasIntensiveListeningDrill(loadedPack, active.number);
  const intensiveListeningUnlocked = hasSubmittedSection(loadedPack, effectiveResult, active.number);

  function recordAudioPosition(section: number, position: number): void {
    if (section === currentSection) {
      setCurrentAudioTime(position);
    }
    onAudioPositionChange?.(section, position);
  }

  function pauseAndSave(section: number): void {
    audioController?.pause(section);
    if (audioRef.current !== null) {
      if (!audioRef.current.paused) {
        audioRef.current.pause();
      }
      recordAudioPosition(section, audioRef.current.currentTime);
      setLocalPositions((current) => ({ ...current, [String(section)]: audioRef.current?.currentTime ?? 0 }));
    }
    const externalPosition = audioController?.getPosition?.(section);
    if (externalPosition !== undefined) {
      setLocalPositions((current) => ({ ...current, [String(section)]: externalPosition }));
      recordAudioPosition(section, externalPosition);
    }
    setPlaying(false);
  }

  function selectSection(nextSection: number): void {
    if (nextSection === currentSection) {
      return;
    }
    pauseAndSave(currentSection);
    setCurrentSection(nextSection);
    onSectionChange?.(nextSection);
  }

  function submit(): void {
    if (!canSubmit) {
      return;
    }
    setRevealedExpectedAnswers(new Set());
    const next = onSubmit?.();
    if (next !== undefined) {
      setLocalResult(next);
    }
  }

  function changeAnswer(questionId: string, value: string): void {
    setLocalResult(null);
    setRevealedExpectedAnswers(new Set());
    onAnswerChange?.(questionId, value);
  }

  function changeAnswers(updates: AnswerMap): void {
    setLocalResult(null);
    setRevealedExpectedAnswers(new Set());
    onAnswersChange?.(updates);
  }

  function toggleExpectedAnswer(questionId: string): void {
    setRevealedExpectedAnswers((current) => {
      const next = new Set(current);
      if (next.has(questionId)) {
        next.delete(questionId);
      } else {
        next.add(questionId);
      }
      return next;
    });
  }

  function nextIncorrect(): void {
    const id = activeNextIncorrectId;
    if (id !== null) {
      const question = loadedPack.questionsById.get(id);
      if (question !== undefined && question.section !== currentSection) {
        setPendingFocusQuestionId(id);
        selectSection(question.section);
        return;
      }
      focusQuestion(id);
    }
  }

  function toggleTranscriptPanel(): void {
    if (!canOpenTranscriptPanel) {
      return;
    }
    setTranscriptPanelOpen((open) => !open);
    if (!transcriptPanelOpen && !effectiveTranscriptViewed) {
      markTranscriptViewed?.();
    }
  }

  function seekToTranscriptPosition(position: number): void {
    const currentPosition =
      audioRef.current?.currentTime ?? audioController?.getPosition?.(currentSection) ?? localPositions[String(currentSection)] ?? 0;
    if (audioRef.current !== null) {
      audioRef.current.currentTime = position;
    }
    audioController?.seek?.(currentSection, position - currentPosition);
    setLocalPositions((current) => ({ ...current, [String(currentSection)]: position }));
    recordAudioPosition(currentSection, position);
  }

  return (
    <main className="workspace-shell" role="main">
      <header className="workspace-topbar">
        <div>
          <div className="eyebrow">{pack.manifest.title}</div>
          <div>{active.title}</div>
        </div>
        <SectionNavigation activeSection={active.number} sections={pack.manifest.sections} onSelect={selectSection} />
        <AudioPlayer
          audioController={audioController}
          audioRef={audioRef}
          initialPosition={localPositions[String(active.number)] ?? 0}
          playbackRate={playbackRate}
          section={active.number}
          src={audioSrc}
          onPlaybackRateChange={setPlaybackRate}
          onPlayStateChange={setPlaying}
          onPositionChange={recordAudioPosition}
        />
      </header>

      <div className={showTranscriptPanel ? "workspace-body workspace-body--with-transcript" : "workspace-body"}>
        <QuestionScrollArea
          answers={answers}
          baseUrl={loadedPack.baseUrl}
          overlays={loadedPack.overlays}
          pages={active.pages}
          questions={sectionQuestions}
          revealedExpectedAnswers={revealedExpectedAnswers}
          result={effectiveResult}
          onAnswerChange={changeAnswer}
          onAnswersChange={changeAnswers}
          onExpectedAnswerToggle={toggleExpectedAnswer}
        />
        {showTranscriptPanel && activeTimingSection !== null && activeTranscriptSection !== null ? (
          <TranscriptShadowingPanel
            currentTime={currentAudioTime}
            showTimingReviewMarkers={showTimingReviewMarkers}
            timingSection={toPanelTimingSection(activeTimingSection)}
            transcriptSection={activeTranscriptSection}
            onSeek={seekToTranscriptPosition}
          />
        ) : null}
        <div className="workspace-side-panel">
          <PracticeActions
            hasIncorrect={activeIncorrectIds.length > 0}
            hasResult={activeSubmittedQuestionCount > 0}
            onGoHome={onGoHome}
            onNextIncorrect={nextIncorrect}
            onReset={() => {
              setPlaybackRate(1);
              setLocalResult(null);
              setRevealedExpectedAnswers(new Set());
              setLocalPositions({});
              onReset?.();
            }}
            onSubmit={submit}
            canSubmit={canSubmit}
            transcriptShadowingAvailable={canOpenTranscriptPanel}
            transcriptShadowingOpen={showTranscriptPanel}
            onToggleTranscriptShadowing={toggleTranscriptPanel}
            intensiveListeningAvailable={intensiveListeningAvailable}
            intensiveListeningUnlocked={intensiveListeningUnlocked}
            onOpenIntensiveListening={() => onOpenIntensiveListening?.(active.number)}
          />
          <MarkingFeedback
            answers={answers}
            questions={sectionQuestions}
            result={effectiveResult}
            transcriptViewed={effectiveTranscriptViewed}
            onNextIncorrect={nextIncorrect}
          />
        </div>
      </div>
    </main>
  );
}

export default ExamWorkspace;
