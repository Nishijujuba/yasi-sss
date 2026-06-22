import type { AnswerMap, MarkResult, OverlayRegion, Question } from "../types/pack";
import InteractionOverlay from "./InteractionOverlay";

export interface QuestionPageProps {
  imageSrc: string;
  pageName: string;
  questions: Question[];
  regions: OverlayRegion[];
  answers: AnswerMap;
  result?: MarkResult | null;
  onAnswerChange: (questionId: string, value: string) => void;
  onAnswersChange?: (updates: AnswerMap) => void;
  revealedExpectedAnswers?: ReadonlySet<string>;
  onExpectedAnswerToggle?: (questionId: string) => void;
}

function companionFor(question: Question, questions: Question[]): string | undefined {
  if (question.responseType !== "multi-choice" || question.selectionLimit !== 2) {
    return undefined;
  }
  const companion = questions.find(
    (candidate) =>
      candidate.id !== question.id &&
      candidate.section === question.section &&
      candidate.responseType === question.responseType &&
      candidate.selectionLimit === question.selectionLimit &&
      candidate.page === question.page,
  );
  return companion?.id;
}

export function QuestionPage({
  imageSrc,
  pageName,
  questions,
  regions,
  answers,
  result,
  onAnswerChange,
  onAnswersChange,
  revealedExpectedAnswers,
  onExpectedAnswerToggle,
}: QuestionPageProps) {
  const byId = new Map(questions.map((question) => [question.id, question]));

  return (
    <article aria-label={`${pageName} 题面`} className="question-page">
      <img alt={`${pageName} 原始题面`} draggable={false} src={imageSrc} />
      <div aria-label={`${pageName} 答题层`} className="overlay-layer">
        {regions.map((region) => {
          const question = byId.get(region.questionId);
          if (question === undefined) {
            return null;
          }
          return (
            <InteractionOverlay
              answers={answers}
              companionQuestionId={companionFor(question, questions)}
              key={`${region.questionId}-${region.optionId ?? "blank"}`}
              question={question}
              region={region}
              result={result}
              revealedExpectedAnswers={revealedExpectedAnswers}
              onAnswerChange={onAnswerChange}
              onAnswersChange={onAnswersChange}
              onExpectedAnswerToggle={onExpectedAnswerToggle}
            />
          );
        })}
      </div>
    </article>
  );
}

export default QuestionPage;
