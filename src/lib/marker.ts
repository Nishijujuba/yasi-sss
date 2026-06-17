import type { AnswerMap, AnswerRule, MarkResult, Question, QuestionResult } from "../types/pack";

export function normalizeAnswer(value: string): string {
  return value.trim().replace(/\s+/g, " ").toLowerCase();
}

function normalizedTuple(values: string[]): string[] {
  return values.map(normalizeAnswer);
}

function sameOrdered(actual: string[], accepted: string[]): boolean {
  return actual.length === accepted.length && actual.every((value, index) => value === accepted[index]);
}

function sameUnordered(actual: string[], accepted: string[]): boolean {
  if (actual.length !== accepted.length) {
    return false;
  }

  const remaining = [...accepted];
  for (const value of actual) {
    const index = remaining.indexOf(value);
    if (index === -1) {
      return false;
    }
    remaining.splice(index, 1);
  }
  return remaining.length === 0;
}

function tupleMatches(actual: string[], accepted: string[], orderIndependent: boolean): boolean {
  return orderIndependent ? sameUnordered(actual, accepted) : sameOrdered(actual, accepted);
}

function resultForQuestion(
  questionId: string,
  correct: boolean,
  expected: string[],
  actual: string,
): QuestionResult {
  return { questionId, correct, expected, actual };
}

export function markAnswers(
  questions: Question[],
  rules: AnswerRule[],
  answers: AnswerMap,
): MarkResult {
  const questionIds = questions.map((question) => question.id);
  const byQuestion: Record<string, QuestionResult> = {};

  for (const id of questionIds) {
    byQuestion[id] = resultForQuestion(id, false, [], answers[id] ?? "");
  }

  for (const rule of rules) {
    const actualTuple = rule.questionIds.map((id) => normalizeAnswer(answers[id] ?? ""));
    const acceptedTuples = rule.accepted.map(normalizedTuple);
    const matchingTuple = acceptedTuples.find((accepted) =>
      tupleMatches(actualTuple, accepted, rule.orderIndependent),
    );
    const correct = matchingTuple !== undefined;
    const expected = rule.accepted[0] ?? [];

    for (const id of rule.questionIds) {
      byQuestion[id] = resultForQuestion(id, correct, expected, answers[id] ?? "");
    }
  }

  const incorrectIds = questionIds.filter((id) => !byQuestion[id]?.correct);

  return {
    score: questionIds.length - incorrectIds.length,
    total: questionIds.length,
    byQuestion,
    incorrectIds,
  };
}
