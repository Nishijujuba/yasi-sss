import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  SESSION_KEY,
  loadSession,
  resetSession,
  saveSession,
  type PracticeSession,
} from "./session";

const OLD_SESSION_KEY = "yasi:cambridge-10:test-1:listening:session:v1";
const V2_SESSION_KEY = "yasi:cambridge-10:test-1:listening:session:v2";

const session: PracticeSession = {
  version: 3,
  packId: "cambridge-10-test-1-listening",
  answers: { q1: "Ardleigh" },
  activeSection: 2,
  submitted: true,
  results: {
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
  },
  audioPositions: { "1": 12.5 },
  capturedMistakes: { q2: "ardley" },
  transcriptViewed: true,
};

describe("session storage lifecycle", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.useRealTimers();
  });

  it("saves and restores the v3 practice session key with transcriptViewed", () => {
    saveSession(session);

    expect(SESSION_KEY).toBe("yasi:cambridge-10:test-1:listening:session:v3");
    expect(localStorage.getItem(SESSION_KEY)).not.toBeNull();
    expect(loadSession()).toEqual(session);
  });

  it("migrates valid v2 sessions to v3 with transcriptViewed false", () => {
    const v2Session = {
      version: 2,
      packId: "cambridge-10-test-1-listening",
      answers: { q1: "Ardleigh" },
      activeSection: 2,
      submitted: false,
      results: null,
      audioPositions: { "1": 14 },
      capturedMistakes: { q2: "ardley" },
    };
    localStorage.setItem(V2_SESSION_KEY, JSON.stringify(v2Session));

    const migrated = loadSession();

    expect(migrated).toEqual({ ...v2Session, version: 3, transcriptViewed: false });
    expect(localStorage.getItem(V2_SESSION_KEY)).toBeNull();
    expect(localStorage.getItem(SESSION_KEY)).toBe(JSON.stringify(migrated));
  });

  it("archives v1 sessions to a timestamp key", () => {
    vi.setSystemTime(new Date("2026-06-16T04:00:00.000Z"));
    const v1Session = {
      version: 1,
      packId: "cambridge-10-test-1-listening",
      answers: { q1: "Ardleigh" },
      activeSection: 1,
      submitted: false,
      results: null,
      audioPositions: {},
    };
    localStorage.setItem(OLD_SESSION_KEY, JSON.stringify(v1Session));

    expect(loadSession()).toBeNull();
    expect(localStorage.getItem(OLD_SESSION_KEY)).toBeNull();
    expect(localStorage.getItem(`${OLD_SESSION_KEY}:archived:2026-06-16T04:00:00.000Z`)).toBe(
      JSON.stringify(v1Session),
    );
  });

  it("archives schema-incompatible v3 values to a timestamp key", () => {
    vi.setSystemTime(new Date("2026-06-16T04:03:00.000Z"));
    localStorage.setItem(SESSION_KEY, JSON.stringify({ version: 3, activeSection: 1 }));

    expect(loadSession()).toBeNull();
    expect(localStorage.getItem(SESSION_KEY)).toBeNull();
    expect(localStorage.getItem(`${SESSION_KEY}:archived:2026-06-16T04:03:00.000Z`)).toBe(
      JSON.stringify({ version: 3, activeSection: 1 }),
    );
  });

  it("archives sessions with malformed marking results", () => {
    vi.setSystemTime(new Date("2026-06-16T04:05:00.000Z"));
    const malformed = { ...session, results: { incorrectIds: [1] } };
    localStorage.setItem(SESSION_KEY, JSON.stringify(malformed));

    expect(loadSession()).toBeNull();
    expect(localStorage.getItem(SESSION_KEY)).toBeNull();
    expect(localStorage.getItem(`${SESSION_KEY}:archived:2026-06-16T04:05:00.000Z`)).toBe(
      JSON.stringify(malformed),
    );
  });

  it("resets answers, results, and audio positions while preserving activeSection", () => {
    saveSession(session);

    const reset = resetSession();

    expect(reset).toEqual({
      version: 3,
      packId: "cambridge-10-test-1-listening",
      answers: {},
      activeSection: 2,
      submitted: false,
      results: null,
      audioPositions: {},
      capturedMistakes: {},
      transcriptViewed: false,
    });
    expect(loadSession()).toEqual(reset);
  });
});
