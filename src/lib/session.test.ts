import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  SESSION_KEY,
  loadSession,
  resetSession,
  saveSession,
  type PracticeSession,
} from "./session";

const session: PracticeSession = {
  version: 1,
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
};

describe("session storage lifecycle", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.useRealTimers();
  });

  it("saves and restores the v1 practice session key", () => {
    saveSession(session);

    expect(localStorage.getItem(SESSION_KEY)).not.toBeNull();
    expect(loadSession()).toEqual(session);
  });

  it("archives schema-incompatible values to a timestamp key", () => {
    vi.setSystemTime(new Date("2026-06-16T04:00:00.000Z"));
    localStorage.setItem(SESSION_KEY, JSON.stringify({ version: 99, activeSection: 1 }));

    expect(loadSession()).toBeNull();
    expect(localStorage.getItem(SESSION_KEY)).toBeNull();
    expect(localStorage.getItem(`${SESSION_KEY}:archived:2026-06-16T04:00:00.000Z`)).toBe(
      JSON.stringify({ version: 99, activeSection: 1 }),
    );
  });

  it("resets answers, results, and audio positions while preserving activeSection", () => {
    saveSession(session);

    const reset = resetSession();

    expect(reset).toEqual({
      version: 1,
      packId: "cambridge-10-test-1-listening",
      answers: {},
      activeSection: 2,
      submitted: false,
      results: null,
      audioPositions: {},
    });
    expect(loadSession()).toEqual(reset);
  });
});
