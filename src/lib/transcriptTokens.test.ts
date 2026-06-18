import { describe, expect, it } from "vitest";
import { tokenizeTranscriptText } from "./transcriptTokens";

describe("tokenizeTranscriptText", () => {
  it("preserves punctuation and spacing while indexing only official word tokens", () => {
    const parts = tokenizeTranscriptText("Good morning.  World Tours!");

    expect(parts).toEqual([
      { kind: "word", text: "Good", tokenIndex: 0 },
      { kind: "text", text: " " },
      { kind: "word", text: "morning", tokenIndex: 1 },
      { kind: "text", text: ".  " },
      { kind: "word", text: "World", tokenIndex: 2 },
      { kind: "text", text: " " },
      { kind: "word", text: "Tours", tokenIndex: 3 },
      { kind: "text", text: "!" },
    ]);
  });

  it("matches yasi alignment token indexing for apostrophes, currency, and hyphenated text", () => {
    const parts = tokenizeTranscriptText("It’s £525 for A-R-D-L-E-I-G-H Road.");

    expect(parts.filter((part) => part.kind === "word")).toEqual([
      { kind: "word", text: "It’s", tokenIndex: 0 },
      { kind: "word", text: "£525", tokenIndex: 1 },
      { kind: "word", text: "for", tokenIndex: 2 },
      { kind: "word", text: "A-R-D-L-E-I-G-H", tokenIndex: 3 },
      { kind: "word", text: "Road", tokenIndex: 4 },
    ]);
  });
});
