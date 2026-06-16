export interface BlankResponseProps {
  questionNumber: number;
  value: string;
  onChange: (value: string) => void;
  questionId?: string;
  disabled?: boolean;
  status?: "correct" | "incorrect" | "unanswered";
}

export function BlankResponse({
  questionNumber,
  value,
  onChange,
  questionId,
  disabled = false,
  status,
}: BlankResponseProps) {
  return (
    <input
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
  );
}

export default BlankResponse;
