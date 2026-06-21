import type { LoadedPack } from "../types/pack";
import {
  markIntensiveListeningSection,
  markingFromIntensiveListeningResult,
  type IntensiveListeningAnswerMap,
  type IntensiveListeningMarking,
  type IntensiveListeningMarkResult,
} from "./intensiveListening";
import type { PracticeSession } from "./session";

export const INTENSIVE_LISTENING_SESSION_VERSION = 1;

export interface IntensiveListeningSectionState {
  answers: IntensiveListeningAnswerMap;
  marking: IntensiveListeningMarking | null;
  result?: IntensiveListeningMarkResult | null;
  answerRevealed: boolean;
  transcriptRevealed: boolean;
}

export interface IntensiveListeningSessionState {
  version: typeof INTENSIVE_LISTENING_SESSION_VERSION;
  packId: string;
  sections: Record<string, IntensiveListeningSectionState>;
}

export function intensiveListeningSessionKey(packId: string): string {
  return `yasi:${packId}:intensive-listening:v1`;
}

function emptySectionState(): IntensiveListeningSectionState {
  return {
    answers: {},
    marking: null,
    result: null,
    answerRevealed: false,
    transcriptRevealed: false,
  };
}

export function createEmptyIntensiveListeningSession(packId: string): IntensiveListeningSessionState {
  return {
    version: INTENSIVE_LISTENING_SESSION_VERSION,
    packId,
    sections: {},
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isStringRecord(value: unknown): value is Record<string, string> {
  return isRecord(value) && Object.values(value).every((entry) => typeof entry === "string");
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((entry) => typeof entry === "string");
}

function isBlankResult(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.blankId === "string" &&
    typeof value.correct === "boolean" &&
    isStringArray(value.expected) &&
    typeof value.actual === "string"
  );
}

function isMarkResult(value: unknown): value is IntensiveListeningMarkResult {
  return (
    isRecord(value) &&
    typeof value.score === "number" &&
    typeof value.total === "number" &&
    isRecord(value.byBlank) &&
    Object.values(value.byBlank).every(isBlankResult) &&
    isStringArray(value.incorrectIds)
  );
}

function isMarkingEntry(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.blankId === "string" &&
    typeof value.correct === "boolean" &&
    typeof value.expected === "string" &&
    typeof value.actual === "string"
  );
}

function isMarking(value: unknown): value is IntensiveListeningMarking {
  return isRecord(value) && Object.values(value).every(isMarkingEntry);
}

function isSectionState(value: unknown): value is IntensiveListeningSectionState {
  return (
    isRecord(value) &&
    isStringRecord(value.answers) &&
    (value.marking === null || isMarking(value.marking)) &&
    (value.result === undefined || value.result === null || isMarkResult(value.result)) &&
    typeof value.answerRevealed === "boolean" &&
    typeof value.transcriptRevealed === "boolean"
  );
}

function isSessionState(value: unknown, packId: string): value is IntensiveListeningSessionState {
  return (
    isRecord(value) &&
    value.version === INTENSIVE_LISTENING_SESSION_VERSION &&
    value.packId === packId &&
    isRecord(value.sections) &&
    Object.values(value.sections).every(isSectionState)
  );
}

function archiveSession(key: string, raw: string): void {
  localStorage.setItem(`${key}:archived:${new Date().toISOString()}`, raw);
  localStorage.removeItem(key);
}

export function loadIntensiveListeningSession(packId: string): IntensiveListeningSessionState | null {
  const key = intensiveListeningSessionKey(packId);
  const raw = localStorage.getItem(key);
  if (raw === null) {
    return null;
  }

  try {
    const parsed: unknown = JSON.parse(raw);
    if (isSessionState(parsed, packId)) {
      return parsed;
    }
  } catch {
    // Invalid JSON is still user state, so it is archived instead of discarded.
  }

  archiveSession(key, raw);
  return null;
}

export function saveIntensiveListeningSession(session: IntensiveListeningSessionState): void {
  localStorage.setItem(intensiveListeningSessionKey(session.packId), JSON.stringify(session));
}

export function resetIntensiveListeningSession(packId: string): IntensiveListeningSessionState {
  const reset = createEmptyIntensiveListeningSession(packId);
  saveIntensiveListeningSession(reset);
  return reset;
}

function sectionKey(section: number): string {
  return String(section);
}

function currentSectionState(
  state: IntensiveListeningSessionState,
  section: number,
): IntensiveListeningSectionState {
  return state.sections[sectionKey(section)] ?? emptySectionState();
}

function replaceSectionState(
  state: IntensiveListeningSessionState,
  section: number,
  sectionState: IntensiveListeningSectionState,
): IntensiveListeningSessionState {
  return {
    ...state,
    sections: {
      ...state.sections,
      [sectionKey(section)]: sectionState,
    },
  };
}

export function setIntensiveListeningAnswer(
  state: IntensiveListeningSessionState,
  section: number,
  blankId: string,
  answer: string,
): IntensiveListeningSessionState {
  const current = currentSectionState(state, section);
  return replaceSectionState(state, section, {
    ...current,
    answers: {
      ...current.answers,
      [blankId]: answer,
    },
    marking: null,
    result: null,
  });
}

export function markIntensiveListeningSessionSection(
  pack: LoadedPack,
  state: IntensiveListeningSessionState,
  section: number,
): IntensiveListeningSessionState {
  const artifact = pack.intensiveListening;
  if (artifact == null) {
    throw new Error("Intensive Listening artifact is not loaded");
  }

  const drillSection = artifact.sections.find((entry) => entry.section === section);
  if (drillSection === undefined) {
    throw new Error(`Intensive Listening section ${section} is not available`);
  }

  const current = currentSectionState(state, section);
  const result = markIntensiveListeningSection(drillSection, current.answers);
  return replaceSectionState(state, section, {
    ...current,
    marking: markingFromIntensiveListeningResult(result),
    result,
  });
}

export function revealIntensiveListeningAnswers(
  state: IntensiveListeningSessionState,
  section: number,
): IntensiveListeningSessionState {
  const current = currentSectionState(state, section);
  return replaceSectionState(state, section, {
    ...current,
    answerRevealed: true,
  });
}

export function revealIntensiveListeningTranscript(
  state: IntensiveListeningSessionState,
  section: number,
): IntensiveListeningSessionState {
  const current = currentSectionState(state, section);
  return replaceSectionState(state, section, {
    ...current,
    transcriptRevealed: true,
  });
}

export function isIntensiveListeningSectionUnlocked(
  pack: LoadedPack,
  practiceSession: PracticeSession | null,
  section: number,
): boolean {
  if (practiceSession === null || !practiceSession.submitted || practiceSession.results === null) {
    return false;
  }

  return pack.questions.some(
    (question) => question.section === section && practiceSession.results?.byQuestion[question.id] !== undefined,
  );
}
