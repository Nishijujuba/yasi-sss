import type { AnswerMap, MarkResult } from "../types/pack";

const LEGACY_SESSION_KEY_V1 = "yasi:cambridge-10:test-1:listening:session:v1";
const LEGACY_SESSION_KEY_V2 = "yasi:cambridge-10:test-1:listening:session:v2";

export const SESSION_KEY = "yasi:cambridge-10:test-1:listening:session:v3";
export const SESSION_VERSION = 3;
export const SESSION_PACK_ID = "cambridge-10-test-1-listening";

interface PracticeSessionV2 {
  version: 2;
  packId: typeof SESSION_PACK_ID;
  answers: AnswerMap;
  activeSection: number;
  submitted: boolean;
  results: MarkResult | null;
  audioPositions: Record<string, number>;
  capturedMistakes: Record<string, string>;
}

export interface PracticeSession {
  version: 3;
  packId: typeof SESSION_PACK_ID;
  answers: AnswerMap;
  activeSection: number;
  submitted: boolean;
  results: MarkResult | null;
  audioPositions: Record<string, number>;
  capturedMistakes: Record<string, string>;
  transcriptViewed: boolean;
}

export function createEmptySession(activeSection = 1): PracticeSession {
  return {
    version: SESSION_VERSION,
    packId: SESSION_PACK_ID,
    answers: {},
    activeSection,
    submitted: false,
    results: null,
    audioPositions: {},
    capturedMistakes: {},
    transcriptViewed: false,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isStringRecord(value: unknown): value is Record<string, string> {
  return isRecord(value) && Object.values(value).every((entry) => typeof entry === "string");
}

function isNumberRecord(value: unknown): value is Record<string, number> {
  return isRecord(value) && Object.values(value).every((entry) => typeof entry === "number");
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((entry) => typeof entry === "string");
}

function isQuestionResult(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.questionId === "string" &&
    typeof value.correct === "boolean" &&
    isStringArray(value.expected) &&
    typeof value.actual === "string"
  );
}

function isMarkResult(value: unknown): value is MarkResult {
  return (
    isRecord(value) &&
    typeof value.score === "number" &&
    typeof value.total === "number" &&
    isRecord(value.byQuestion) &&
    Object.values(value.byQuestion).every(isQuestionResult) &&
    isStringArray(value.incorrectIds)
  );
}

function hasPracticeSessionFields(value: Record<string, unknown>): boolean {
  return (
    value.packId === SESSION_PACK_ID &&
    isStringRecord(value.answers) &&
    typeof value.activeSection === "number" &&
    Number.isInteger(value.activeSection) &&
    value.activeSection >= 1 &&
    typeof value.submitted === "boolean" &&
    (value.results === null || isMarkResult(value.results)) &&
    isNumberRecord(value.audioPositions) &&
    isStringRecord(value.capturedMistakes)
  );
}

function isPracticeSessionV2(value: unknown): value is PracticeSessionV2 {
  if (!isRecord(value)) {
    return false;
  }

  return value.version === 2 && hasPracticeSessionFields(value);
}

function isPracticeSession(value: unknown): value is PracticeSession {
  if (!isRecord(value)) {
    return false;
  }

  return (
    value.version === SESSION_VERSION &&
    hasPracticeSessionFields(value) &&
    typeof value.transcriptViewed === "boolean"
  );
}

function archiveSession(key: string, raw: string): void {
  const archiveKey = `${key}:archived:${new Date().toISOString()}`;
  localStorage.setItem(archiveKey, raw);
  localStorage.removeItem(key);
}

export function loadSession(): PracticeSession | null {
  const raw = localStorage.getItem(SESSION_KEY);
  if (raw !== null) {
    try {
      const parsed: unknown = JSON.parse(raw);
      if (isPracticeSession(parsed)) {
        return parsed;
      }
    } catch {
      // Invalid JSON is still user state, so it is archived instead of discarded.
    }

    archiveSession(SESSION_KEY, raw);
    return null;
  }

  const legacyRawV2 = localStorage.getItem(LEGACY_SESSION_KEY_V2);
  if (legacyRawV2 !== null) {
    try {
      const parsed: unknown = JSON.parse(legacyRawV2);
      if (isPracticeSessionV2(parsed)) {
        const migrated: PracticeSession = {
          ...parsed,
          version: SESSION_VERSION,
          transcriptViewed: false,
        };
        saveSession(migrated);
        localStorage.removeItem(LEGACY_SESSION_KEY_V2);
        return migrated;
      }
    } catch {
      // Invalid JSON is still user state, so it is archived instead of discarded.
    }

    archiveSession(LEGACY_SESSION_KEY_V2, legacyRawV2);
    return null;
  }

  const legacyRaw = localStorage.getItem(LEGACY_SESSION_KEY_V1);
  if (legacyRaw !== null) {
    archiveSession(LEGACY_SESSION_KEY_V1, legacyRaw);
  }
  return null;
}

export function saveSession(session: PracticeSession): void {
  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function resetSession(): PracticeSession {
  const current = loadSession();
  const reset = createEmptySession(current?.activeSection ?? 1);
  saveSession(reset);
  return reset;
}
