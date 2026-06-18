import { afterEach, describe, expect, it, vi } from "vitest";
import { loadPack } from "./loadPack";

const baseManifest = {
  packId: "cambridge-10-test-1-listening",
  schemaVersion: 1,
  status: "released",
  title: "Cambridge IELTS 10 Test 1 Listening",
  sections: [
    {
      number: 1,
      title: "Section 1",
      questionNumbers: [1],
      audio: "assets/audio/section-01.mp3",
      pages: ["assets/pages/page-010.png"],
    },
  ],
  assets: {
    questions: "questions.json",
    answers: "answers.json",
    overlays: "overlays.json",
    transcript: "transcript.json",
    vocabulary: "vocabulary.json",
  },
};

const assets = {
  questions: [
    {
      id: "q1",
      number: 1,
      section: 1,
      responseType: "blank",
      page: "page-010.png",
      focusOrder: 1,
      selectionLimit: null,
      options: [],
    },
  ],
  answers: [{ questionIds: ["q1"], accepted: [["Ardleigh"]], orderIndependent: false }],
  overlays: [
    {
      questionId: "q1",
      optionId: null,
      page: "page-010.png",
      interactionType: "blank",
      pixel: { x: 10, y: 20, w: 100, h: 30 },
      normalized: { x: 0.1, y: 0.2, w: 0.2, h: 0.05 },
      deterministicConfidence: 0.95,
      visionConfidence: 0.96,
      confidence: 0.95,
      validationEvidence: ["test evidence"],
    },
  ],
  transcript: [
    {
      section: 1,
      segments: [
        {
          order: 1,
          speaker: "TRAVEL AGENT",
          text: "Good morning.",
          answerRefs: [],
          startTime: null,
          endTime: null,
        },
      ],
    },
  ],
  vocabulary: [
    {
      id: "ardleigh",
      term: "Ardleigh",
      spokenText: "Ardleigh",
      normalizedTerm: "ardleigh",
      acceptedVariants: [],
      meaningZh: "阿德利",
      audio: "assets/audio/vocabulary/ardleigh.mp3",
    },
  ],
};

const verifiedTranscriptTimings = {
  schemaVersion: "yasi.transcript-timings.v1",
  status: "verified",
  sections: [
    {
      section: 1,
      status: "verified",
      wordTimings: [
        {
          section: 1,
          segmentOrder: 1,
          tokenIndex: 0,
          token: "Good",
          normalized: "good",
          start: 0.1,
          end: 0.25,
        },
        {
          section: 1,
          segmentOrder: 1,
          tokenIndex: 1,
          token: "morning",
          normalized: "morning",
          start: 0.3,
          end: 0.6,
        },
      ],
    },
  ],
};

function mockJsonFetch(payloads: unknown[]) {
  const fetchMock = vi.fn(async () => {
    const payload = payloads.shift();
    return {
      ok: true,
      status: 200,
      json: async () => payload,
    } as Response;
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("loadPack", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads only released manifests with all declared JSON assets", async () => {
    const fetchMock = mockJsonFetch([
      baseManifest,
      assets.questions,
      assets.answers,
      assets.overlays,
      assets.transcript,
      assets.vocabulary,
    ]);

    const pack = await loadPack("/packs/cambridge-10/test-1/listening");

    expect(pack.manifest).toEqual(baseManifest);
    expect(pack.questions).toEqual(assets.questions);
    expect(pack.answers).toEqual(assets.answers);
    expect(pack.overlays).toEqual(assets.overlays);
    expect(pack.transcript).toEqual(assets.transcript);
    expect(pack.transcriptTimings).toBeNull();
    expect(pack.vocabulary).toEqual(assets.vocabulary);
    expect(pack.vocabulary[0].spokenText).toBe("Ardleigh");
    expect(pack.questionsById.get("q1")).toEqual(assets.questions[0]);
    expect(pack.answersByQuestionId.get("q1")).toEqual(assets.answers[0]);
    expect(pack.overlaysByQuestionId.get("q1")).toEqual(assets.overlays);
    expect(pack.vocabularyById.get("ardleigh")).toEqual(assets.vocabulary[0]);
    expect(pack.vocabularyById.get("ardleigh")?.spokenText).toBe("Ardleigh");
    expect(fetchMock).toHaveBeenNthCalledWith(1, "/packs/cambridge-10/test-1/listening/manifest.json");
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/packs/cambridge-10/test-1/listening/questions.json");
    expect(fetchMock).toHaveBeenNthCalledWith(6, "/packs/cambridge-10/test-1/listening/vocabulary.json");
  });

  it("loads a verified optional transcript timing artifact declared by the manifest", async () => {
    const manifest = {
      ...baseManifest,
      assets: {
        ...baseManifest.assets,
        transcriptTimings: "transcript-timings.json",
      },
    };
    const fetchMock = mockJsonFetch([
      manifest,
      assets.questions,
      assets.answers,
      assets.overlays,
      assets.transcript,
      assets.vocabulary,
      verifiedTranscriptTimings,
    ]);

    const pack = await loadPack("/packs/cambridge-10/test-1/listening");

    expect(pack.transcriptTimings).toEqual(verifiedTranscriptTimings);
    expect(fetchMock).toHaveBeenNthCalledWith(
      7,
      "/packs/cambridge-10/test-1/listening/transcript-timings.json",
    );
  });

  it("rejects draft transcript timing artifacts", async () => {
    mockJsonFetch([
      {
        ...baseManifest,
        assets: { ...baseManifest.assets, transcriptTimings: "transcript-timings.json" },
      },
      assets.questions,
      assets.answers,
      assets.overlays,
      assets.transcript,
      assets.vocabulary,
      { ...verifiedTranscriptTimings, status: "draft" },
    ]);

    await expect(loadPack("/packs/cambridge-10/test-1/listening")).rejects.toThrow(
      /transcriptTimings\.status/i,
    );
  });

  it("rejects transcript timing sections that are not verified", async () => {
    mockJsonFetch([
      {
        ...baseManifest,
        assets: { ...baseManifest.assets, transcriptTimings: "transcript-timings.json" },
      },
      assets.questions,
      assets.answers,
      assets.overlays,
      assets.transcript,
      assets.vocabulary,
      {
        ...verifiedTranscriptTimings,
        sections: [{ ...verifiedTranscriptTimings.sections[0], status: "draft" }],
      },
    ]);

    await expect(loadPack("/packs/cambridge-10/test-1/listening")).rejects.toThrow(
      /transcriptTimings\.sections\[0\]\.status/i,
    );
  });

  it("rejects transcript timings with non-positive intervals", async () => {
    mockJsonFetch([
      {
        ...baseManifest,
        assets: { ...baseManifest.assets, transcriptTimings: "transcript-timings.json" },
      },
      assets.questions,
      assets.answers,
      assets.overlays,
      assets.transcript,
      assets.vocabulary,
      {
        ...verifiedTranscriptTimings,
        sections: [
          {
            ...verifiedTranscriptTimings.sections[0],
            wordTimings: verifiedTranscriptTimings.sections[0].wordTimings.map((timing, index) =>
              index === 0 ? { ...timing, end: 0.1 } : timing,
            ),
          },
        ],
      },
    ]);

    await expect(loadPack("/packs/cambridge-10/test-1/listening")).rejects.toThrow(
      /positive interval/i,
    );
  });

  it("rejects transcript timing entries whose section does not match their parent section", async () => {
    mockJsonFetch([
      {
        ...baseManifest,
        assets: { ...baseManifest.assets, transcriptTimings: "transcript-timings.json" },
      },
      assets.questions,
      assets.answers,
      assets.overlays,
      assets.transcript,
      assets.vocabulary,
      {
        ...verifiedTranscriptTimings,
        sections: [
          {
            ...verifiedTranscriptTimings.sections[0],
            wordTimings: verifiedTranscriptTimings.sections[0].wordTimings.map((timing, index) =>
              index === 0 ? { ...timing, section: 2 } : timing,
            ),
          },
        ],
      },
    ]);

    await expect(loadPack("/packs/cambridge-10/test-1/listening")).rejects.toThrow(
      /section mismatch/i,
    );
  });

  it("rejects duplicate transcript timing identities", async () => {
    mockJsonFetch([
      {
        ...baseManifest,
        assets: { ...baseManifest.assets, transcriptTimings: "transcript-timings.json" },
      },
      assets.questions,
      assets.answers,
      assets.overlays,
      assets.transcript,
      assets.vocabulary,
      {
        ...verifiedTranscriptTimings,
        sections: [
          {
            ...verifiedTranscriptTimings.sections[0],
            wordTimings: [
              ...verifiedTranscriptTimings.sections[0].wordTimings,
              {
                section: 1,
                segmentOrder: 1,
                tokenIndex: 0,
                token: "Good",
                normalized: "good",
                start: 0.7,
                end: 0.9,
              },
            ],
          },
        ],
      },
    ]);

    await expect(loadPack("/packs/cambridge-10/test-1/listening")).rejects.toThrow(
      /duplicate/i,
    );
  });

  it("rejects transcript timing entries that do not map to a frontend transcript token", async () => {
    mockJsonFetch([
      {
        ...baseManifest,
        assets: { ...baseManifest.assets, transcriptTimings: "transcript-timings.json" },
      },
      assets.questions,
      assets.answers,
      assets.overlays,
      assets.transcript,
      assets.vocabulary,
      {
        ...verifiedTranscriptTimings,
        sections: [
          {
            ...verifiedTranscriptTimings.sections[0],
            wordTimings: [
              ...verifiedTranscriptTimings.sections[0].wordTimings,
              {
                section: 1,
                segmentOrder: 1,
                tokenIndex: 2,
                token: "extra",
                normalized: "extra",
                start: 0.7,
                end: 0.9,
              },
            ],
          },
        ],
      },
    ]);

    await expect(loadPack("/packs/cambridge-10/test-1/listening")).rejects.toThrow(
      /tokenIndex/i,
    );
  });

  it("rejects non-released manifests", async () => {
    mockJsonFetch([{ ...baseManifest, status: "draft" }]);

    await expect(loadPack("/packs/cambridge-10/test-1/listening")).rejects.toThrow(/released/i);
  });

  it("rejects manifests with missing required fields", async () => {
    const { assets: _assets, ...invalidManifest } = baseManifest;
    mockJsonFetch([invalidManifest]);

    await expect(loadPack("/packs/cambridge-10/test-1/listening")).rejects.toThrow(/assets/i);
  });

  it("rejects manifests without a vocabulary asset declaration", async () => {
    const { vocabulary: _vocabulary, ...manifestAssets } = baseManifest.assets;
    mockJsonFetch([{ ...baseManifest, assets: manifestAssets }]);

    await expect(loadPack("/packs/cambridge-10/test-1/listening")).rejects.toThrow(
      /manifest\.assets\.vocabulary/i,
    );
  });

  it("rejects overlays below the runtime confidence gate", async () => {
    mockJsonFetch([
      baseManifest,
      assets.questions,
      assets.answers,
      [{ ...assets.overlays[0], visionConfidence: 0.84 }],
      assets.transcript,
      assets.vocabulary,
    ]);

    await expect(loadPack("/packs/cambridge-10/test-1/listening")).rejects.toThrow(/0.85/);
  });

  it("rejects malformed vocabulary assets with clear diagnostics", async () => {
    mockJsonFetch([
      baseManifest,
      assets.questions,
      assets.answers,
      assets.overlays,
      assets.transcript,
      [{ ...assets.vocabulary[0], meaningZh: "" }],
    ]);

    await expect(loadPack("/packs/cambridge-10/test-1/listening")).rejects.toThrow(
      /vocabulary\[0\]\.meaningZh/i,
    );
  });

  it("rejects vocabulary assets missing spokenText", async () => {
    const { spokenText: _spokenText, ...vocabularyWithoutSpokenText } = assets.vocabulary[0];
    mockJsonFetch([
      baseManifest,
      assets.questions,
      assets.answers,
      assets.overlays,
      assets.transcript,
      [vocabularyWithoutSpokenText],
    ]);

    await expect(loadPack("/packs/cambridge-10/test-1/listening")).rejects.toThrow(
      /vocabulary\[0\]\.spokenText/i,
    );
  });

  it("rejects duplicate vocabulary ids with clear diagnostics", async () => {
    mockJsonFetch([
      baseManifest,
      assets.questions,
      assets.answers,
      assets.overlays,
      assets.transcript,
      [
        assets.vocabulary[0],
        {
          ...assets.vocabulary[0],
          term: "another Ardleigh",
          normalizedTerm: "another ardleigh",
        },
      ],
    ]);

    await expect(loadPack("/packs/cambridge-10/test-1/listening")).rejects.toThrow(
      /duplicate vocabulary id: ardleigh/i,
    );
  });
});
