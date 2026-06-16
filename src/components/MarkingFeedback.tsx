import type { AnswerMap, MarkResult, Question } from "../types/pack";

export interface MarkingFeedbackProps {
  result: MarkResult | null;
  questions: Question[];
  answers: AnswerMap;
  onNextIncorrect?: () => void;
}

export function MarkingFeedback({ result, questions, answers, onNextIncorrect }: MarkingFeedbackProps) {
  if (result === null) {
    const answered = questions.filter((question) => (answers[question.id] ?? "").trim() !== "").length;
    return (
      <section aria-label="练习进度" className="feedback-card">
        已作答 {answered} / {questions.length}
      </section>
    );
  }

  const unanswered = questions.filter((question) => (answers[question.id] ?? "").trim() === "").length;
  const incorrect = Math.max(result.incorrectIds.length - unanswered, 0);

  return (
    <section aria-label="判分反馈" className="feedback-card">
      <h2>
        Raw score: {result.score} / {result.total}
      </h2>
      <p>正确：{result.score}</p>
      <p>错误：{incorrect}</p>
      <p>未答：{unanswered}</p>
      <button disabled={result.incorrectIds.length === 0} onClick={onNextIncorrect} type="button">
        下一错误题
      </button>
    </section>
  );
}

export default MarkingFeedback;
