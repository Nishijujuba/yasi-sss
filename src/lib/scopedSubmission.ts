import type { AnswerMap, AnswerRule, LoadedPack, MarkResult, Question } from "../types/pack";
import { markAnswers } from "./marker";

export function hasAnyAnswer(answers: AnswerMap): boolean {
  return Object.values(answers).some((answer) => answer.trim() !== "");
}

export function deriveAttemptedSections(questions: Question[], answers: AnswerMap): Set<number> {
  const attemptedSections = new Set<number>();

  for (const question of questions) {
    if ((answers[question.id] ?? "").trim() !== "") {
      attemptedSections.add(question.section);
    }
  }

  return attemptedSections;
}

export function submittedQuestionsForSections(
  questions: Question[],
  attemptedSections: Set<number>,
): Question[] {
  return questions.filter((question) => attemptedSections.has(question.section));
}

export function submittedRulesForQuestions(
  rules: AnswerRule[],
  submittedQuestions: Question[],
): AnswerRule[] {
  const submittedQuestionIds = new Set(submittedQuestions.map((question) => question.id));
  return rules.filter((rule) => rule.questionIds.every((questionId) => submittedQuestionIds.has(questionId)));
}

export function markAttemptedSections(pack: LoadedPack, answers: AnswerMap): MarkResult {
  const attemptedSections = deriveAttemptedSections(pack.questions, answers);
  const submittedQuestions = submittedQuestionsForSections(pack.questions, attemptedSections);
  const submittedRules = submittedRulesForQuestions(pack.answers, submittedQuestions);

  return markAnswers(submittedQuestions, submittedRules, answers);
}
