import { describe, expect, it } from "vitest";
import type { IntensiveListeningSection } from "../types/pack";
import { markIntensiveListeningSection, normalizeIntensiveListeningAnswer } from "./intensiveListening";

const section: IntensiveListeningSection = {
  section: 1,
  blanks: [
    {
      id: "il-s01-seg001-t000-t001",
      segmentOrder: 1,
      startTokenIndex: 0,
      endTokenIndex: 1,
      answer: "Good morning",
      acceptedVariants: ["good-morning"],
      reason: "Greeting phrase.",
      tags: ["phrase"],
    },
    {
      id: "il-s01-seg002-t003-t004",
      segmentOrder: 2,
      startTokenIndex: 3,
      endTokenIndex: 4,
      answer: "Ardleigh",
      acceptedVariants: [],
      reason: "Proper noun spelling.",
      tags: ["spelling-risk"],
    },
  ],
};

describe("intensive listening marking", () => {
  it("normalizes answers by trimming, collapsing whitespace, and lowercasing", () => {
    expect(normalizeIntensiveListeningAnswer("  Good \n\t MORNING  ")).toBe("good morning");
  });

  it("strictly marks section blanks against answer and accepted variants", () => {
    const result = markIntensiveListeningSection(section, {
      "il-s01-seg001-t000-t001": "  GOOD   MORNING ",
      "il-s01-seg002-t003-t004": "ardley",
    });

    expect(result).toEqual({
      score: 1,
      total: 2,
      byBlank: {
        "il-s01-seg001-t000-t001": {
          blankId: "il-s01-seg001-t000-t001",
          correct: true,
          expected: ["Good morning", "good-morning"],
          actual: "  GOOD   MORNING ",
        },
        "il-s01-seg002-t003-t004": {
          blankId: "il-s01-seg002-t003-t004",
          correct: false,
          expected: ["Ardleigh"],
          actual: "ardley",
        },
      },
      incorrectIds: ["il-s01-seg002-t003-t004"],
    });
  });

  it("accepts explicit variants after applying the same strict normalization", () => {
    const result = markIntensiveListeningSection(section, {
      "il-s01-seg001-t000-t001": " GOOD-MORNING ",
      "il-s01-seg002-t003-t004": "ARDLEIGH",
    });

    expect(result.score).toBe(2);
    expect(result.incorrectIds).toEqual([]);
  });
});
