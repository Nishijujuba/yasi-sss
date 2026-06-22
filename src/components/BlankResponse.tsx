export interface BlankResponseProps {
  questionNumber: number;
  value: string;
  onChange: (value: string) => void;
  questionId?: string;
  disabled?: boolean;
  status?: "correct" | "incorrect" | "unanswered";
  expectedAnswer?: string;
  expectedAnswerRevealed?: boolean;
  onExpectedAnswerToggle?: () => void;
}

function EyeIcon() {
  return (
    <svg aria-hidden="true" className="blank-answer-toggle__icon" viewBox="0 0 24 24">
      <path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" />
      <circle cx="12" cy="12" r="2.6" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg aria-hidden="true" className="blank-answer-toggle__icon" viewBox="0 0 24 24">
      <path d="M3 3l18 18" />
      <path d="M10.6 5.2A9.5 9.5 0 0 1 12 5c6 0 9.5 7 9.5 7a18 18 0 0 1-3 3.8" />
      <path d="M6.2 6.9A17.8 17.8 0 0 0 2.5 12s3.5 7 9.5 7a9.4 9.4 0 0 0 4.1-.9" />
      <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
    </svg>
  );
}

export function BlankResponse({
  questionNumber,
  value,
  onChange,
  questionId,
  disabled = false,
  status,
  expectedAnswer,
  expectedAnswerRevealed = false,
  onExpectedAnswerToggle,
}: BlankResponseProps) {
  const expectedId =
    expectedAnswer === undefined || !expectedAnswerRevealed
      ? undefined
      : `${questionId ?? questionNumber}-expected-answer`;
  const toggleLabel = expectedAnswerRevealed
    ? `隐藏第 ${questionNumber} 题正确答案`
    : `显示第 ${questionNumber} 题正确答案`;

  return (
    <div className="blank-response-stack">
      <input
        aria-describedby={expectedId}
        aria-label={`第 ${questionNumber} 题`}
        className="blank-response"
        data-question-id={questionId}
        data-status={status ?? "pending"}
        disabled={disabled}
        onChange={(event) => onChange(event.currentTarget.value)}
        spellCheck={false}
        type="text"
        value={value}
      />
      {expectedAnswer === undefined ? null : (
        <button
          aria-label={toggleLabel}
          aria-pressed={expectedAnswerRevealed}
          className="blank-answer-toggle"
          title={toggleLabel}
          type="button"
          onClick={onExpectedAnswerToggle}
        >
          {expectedAnswerRevealed ? <EyeOffIcon /> : <EyeIcon />}
        </button>
      )}
      {expectedAnswer === undefined || !expectedAnswerRevealed ? null : (
        <span className="expected-answer" id={expectedId}>
          正确答案：{expectedAnswer}
        </span>
      )}
    </div>
  );
}

export default BlankResponse;
