export interface BlankResponseProps {
  questionNumber: number;
  value: string;
  onChange: (value: string) => void;
  questionId?: string;
  disabled?: boolean;
  status?: "correct" | "incorrect" | "unanswered";
  expectedAnswer?: string;
}

export function BlankResponse({
  questionNumber,
  value,
  onChange,
  questionId,
  disabled = false,
  status,
  expectedAnswer,
}: BlankResponseProps) {
  const expectedId = expectedAnswer === undefined ? undefined : `${questionId ?? questionNumber}-expected-answer`;

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
        <span className="expected-answer" id={expectedId}>
          正确答案：{expectedAnswer}
        </span>
      )}
    </div>
  );
}

export default BlankResponse;
