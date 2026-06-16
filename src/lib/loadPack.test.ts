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
  transcript: [{ section: 1, segments: [] }],
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
    ]);

    const pack = await loadPack("/packs/cambridge-10/test-1/listening");

    expect(pack.manifest).toEqual(baseManifest);
    expect(pack.questions).toEqual(assets.questions);
    expect(pack.answers).toEqual(assets.answers);
    expect(pack.overlays).toEqual(assets.overlays);
    expect(pack.transcript).toEqual(assets.transcript);
    expect(pack.questionsById.get("q1")).toEqual(assets.questions[0]);
    expect(pack.answersByQuestionId.get("q1")).toEqual(assets.answers[0]);
    expect(pack.overlaysByQuestionId.get("q1")).toEqual(assets.overlays);
    expect(fetchMock).toHaveBeenNthCalledWith(1, "/packs/cambridge-10/test-1/listening/manifest.json");
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/packs/cambridge-10/test-1/listening/questions.json");
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

  it("rejects overlays below the runtime confidence gate", async () => {
    mockJsonFetch([
      baseManifest,
      assets.questions,
      assets.answers,
      [{ ...assets.overlays[0], visionConfidence: 0.84 }],
      assets.transcript,
    ]);

    await expect(loadPack("/packs/cambridge-10/test-1/listening")).rejects.toThrow(/0.85/);
  });
});
