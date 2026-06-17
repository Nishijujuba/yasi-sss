import type { CSSProperties } from "react";
import type { AnswerMap, MarkResult, OverlayRegion, Question } from "../types/pack";
import BlankResponse from "./BlankResponse";
import ChoiceResponse, { type ChoiceValue, isMultiChoice } from "./ChoiceResponse";

export interface InteractionOverlayProps {
  region: OverlayRegion;
  question: Question;
  answers: AnswerMap;
  result?: MarkResult | null;
  onAnswerChange: (questionId: string, value: string) => void;
  onAnswersChange?: (updates: AnswerMap) => void;
  companionQuestionId?: string;
}

function resultStatus(questionId: string, value: string, result?: MarkResult | null) {
  if (result === null || result === undefined) {
    return undefined;
  }
  if (value.trim() === "") {
    return "unanswered" as const;
  }
  return result.byQuestion[questionId]?.correct ? ("correct" as const) : ("incorrect" as const);
}

function expectedAnswer(questionId: string, result?: MarkResult | null): string | undefined {
  const questionResult = result?.byQuestion[questionId];
  if (questionResult === undefined || questionResult.correct || questionResult.expected.length === 0) {
    return undefined;
  }
  return questionResult.expected.join(" / ");
}

function multiValue(question: Question, answers: AnswerMap, companionQuestionId?: string): string[] {
  const first = answers[question.id];
  const second = companionQuestionId === undefined ? undefined : answers[companionQuestionId];
  return [first, second].filter((value): value is string => value !== undefined && value !== "");
}

export function InteractionOverlay({
  region,
  question,
  answers,
  result,
  onAnswerChange,
  onAnswersChange,
  companionQuestionId,
}: InteractionOverlayProps) {
  const rect = region.normalized;
  const style = {
    "--x": rect.x,
    "--y": rect.y,
    "--w": rect.w,
    "--h": rect.h,
  } as CSSProperties;

  if (question.responseType === "blank") {
    const value = answers[question.id] ?? "";
    return (
      <div className="interaction-overlay" data-question-id={question.id} style={style}>
        <BlankResponse
          expectedAnswer={expectedAnswer(question.id, result)}
          questionId={question.id}
          questionNumber={question.number}
          status={resultStatus(question.id, value, result)}
          value={value}
          onChange={(next) => onAnswerChange(question.id, next)}
        />
      </div>
    );
  }

  const multi = isMultiChoice(question);
  const value: ChoiceValue = multi
    ? multiValue(question, answers, companionQuestionId)
    : answers[question.id] ?? "";

  function handleChoiceChange(next: ChoiceValue): void {
    if (!Array.isArray(next)) {
      onAnswerChange(question.id, next);
      return;
    }

    const updates: AnswerMap = { [question.id]: next[0] ?? "" };
    if (companionQuestionId !== undefined) {
      updates[companionQuestionId] = next[1] ?? "";
    }

    if (onAnswersChange !== undefined) {
      onAnswersChange(updates);
      return;
    }
    for (const [id, answer] of Object.entries(updates)) {
      onAnswerChange(id, answer);
    }
  }

  return (
    <div className="interaction-overlay" data-question-id={question.id} style={style}>
      <ChoiceResponse
        optionId={region.optionId ?? undefined}
        question={question}
        value={value}
        onChange={handleChoiceChange}
      />
    </div>
  );
}

export default InteractionOverlay;
