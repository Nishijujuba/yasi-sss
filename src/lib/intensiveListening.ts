import type { IntensiveListeningSection } from "../types/pack";

export type {
  IntensiveListeningArtifact,
  IntensiveListeningBlank,
  IntensiveListeningSection,
} from "../types/pack";
export type {
  IntensiveListeningSectionState,
  IntensiveListeningSessionState,
} from "./intensiveListeningSession";

export type IntensiveListeningAnswerMap = Record<string, string>;

export interface IntensiveListeningBlankResult {
  blankId: string;
  correct: boolean;
  expected: string[];
  actual: string;
}

export interface IntensiveListeningMarkResult {
  score: number;
  total: number;
  byBlank: Record<string, IntensiveListeningBlankResult>;
  incorrectIds: string[];
}

export interface IntensiveListeningMarkingEntry {
  blankId: string;
  correct: boolean;
  expected: string;
  actual: string;
}

export type IntensiveListeningMarking = Record<string, IntensiveListeningMarkingEntry>;

export function normalizeIntensiveListeningAnswer(value: string): string {
  return value.trim().replace(/\s+/g, " ").toLowerCase();
}

export function markIntensiveListeningSection(
  section: IntensiveListeningSection,
  answers: IntensiveListeningAnswerMap,
): IntensiveListeningMarkResult {
  const byBlank: Record<string, IntensiveListeningBlankResult> = {};

  for (const blank of section.blanks) {
    const actual = answers[blank.id] ?? "";
    const expected = [blank.answer, ...blank.acceptedVariants];
    const normalizedActual = normalizeIntensiveListeningAnswer(actual);
    const correct = expected.some(
      (accepted) => normalizeIntensiveListeningAnswer(accepted) === normalizedActual,
    );

    byBlank[blank.id] = {
      blankId: blank.id,
      correct,
      expected,
      actual,
    };
  }

  const incorrectIds = section.blanks.filter((blank) => !byBlank[blank.id]?.correct).map((blank) => blank.id);

  return {
    score: section.blanks.length - incorrectIds.length,
    total: section.blanks.length,
    byBlank,
    incorrectIds,
  };
}

export function markingFromIntensiveListeningResult(
  result: IntensiveListeningMarkResult,
): IntensiveListeningMarking {
  return Object.fromEntries(
    Object.entries(result.byBlank).map(([blankId, blankResult]) => [
      blankId,
      {
        blankId,
        correct: blankResult.correct,
        expected: blankResult.expected[0] ?? "",
        actual: blankResult.actual,
      },
    ]),
  );
}
