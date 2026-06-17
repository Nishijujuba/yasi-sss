import type { AnswerMap, MarkResult, Question } from "../types/pack";

export interface MarkingFeedbackProps {
  result: MarkResult | null;
  questions: Question[];
  answers: AnswerMap;
  onNextIncorrect?: () => void;
}

function formatExpected(expected: string[]): string {
  return expected.length === 0 ? "无" : expected.join(" / ");
}

function formatActual(actual: string): string {
  const trimmed = actual.trim();
  return trimmed === "" ? "未答" : `你的答案：${trimmed}`;
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

  const questionsById = new Map(questions.map((question) => [question.id, question]));
  const submittedQuestions = questions.filter((question) => result.byQuestion[question.id] !== undefined);
  const unanswered = submittedQuestions.filter((question) => {
    const questionResult = result.byQuestion[question.id];
    return questionResult !== undefined && questionResult.actual.trim() === "";
  }).length;
  const incorrect = submittedQuestions.filter((question) => {
    const questionResult = result.byQuestion[question.id];
    return questionResult !== undefined && !questionResult.correct && questionResult.actual.trim() !== "";
  }).length;
  const incorrectAnswers = result.incorrectIds
    .map((questionId) => {
      const question = questionsById.get(questionId);
      const questionResult = result.byQuestion[questionId];
      if (question === undefined || questionResult === undefined) {
        return null;
      }
      return { question, questionResult };
    })
    .filter((entry): entry is NonNullable<typeof entry> => entry !== null);
  const groupedAnswers = new Map<number, typeof incorrectAnswers>();
  for (const entry of incorrectAnswers) {
    const current = groupedAnswers.get(entry.question.section) ?? [];
    current.push(entry);
    groupedAnswers.set(entry.question.section, current);
  }
  const sectionGroups = [...groupedAnswers.entries()].sort(([left], [right]) => left - right);

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
      {sectionGroups.length === 0 ? null : (
        <div aria-label="正确答案" className="feedback-answers">
          <h3>正确答案</h3>
          {sectionGroups.map(([section, entries]) => (
            <section className="feedback-section" key={section}>
              <h4>Section {String(section).padStart(2, "0")}</h4>
              <ol>
                {entries.map(({ question, questionResult }) => (
                  <li key={question.id}>
                    <strong>Q{question.number}</strong>
                    <span className="feedback-answer__actual">{formatActual(questionResult.actual)}</span>
                    <span className="feedback-answer__expected">
                      正确答案：{formatExpected(questionResult.expected)}
                    </span>
                  </li>
                ))}
              </ol>
            </section>
          ))}
        </div>
      )}
    </section>
  );
}

export default MarkingFeedback;
