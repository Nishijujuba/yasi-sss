import { useEffect, useState } from "react";
import type { Question } from "../types/pack";

export type ChoiceValue = string | string[];

export interface ChoiceResponseProps {
  question: Question;
  value: ChoiceValue;
  onChange: (value: ChoiceValue) => void;
  optionId?: string;
  disabled?: boolean;
  describedBy?: string;
}

function selectedValues(value: ChoiceValue): string[] {
  if (Array.isArray(value)) {
    return value.filter(Boolean);
  }
  return value === "" ? [] : [value];
}

export function isMultiChoice(question: Question): boolean {
  return question.responseType === "multi-choice" || (question.selectionLimit ?? 1) > 1;
}

export function ChoiceResponse({
  question,
  value,
  onChange,
  optionId,
  disabled = false,
  describedBy,
}: ChoiceResponseProps) {
  const multi = isMultiChoice(question);
  const limit = question.selectionLimit ?? (multi ? question.options.length : 1);
  const [current, setCurrent] = useState<string[]>(() => selectedValues(value));
  const options =
    optionId === undefined ? question.options : question.options.filter((option) => option.id === optionId);

  useEffect(() => {
    setCurrent(selectedValues(value));
  }, [value]);

  function emit(next: string[]): void {
    setCurrent(next);
    onChange(multi ? next : next[0] ?? "");
  }

  function toggle(nextId: string): void {
    if (!multi) {
      emit([nextId]);
      return;
    }
    if (current.includes(nextId)) {
      emit(current.filter((entry) => entry !== nextId));
      return;
    }
    if (current.length >= limit) {
      emit(current);
      return;
    }
    emit([...current, nextId]);
  }

  return (
    <fieldset aria-label={`第 ${question.number} 题选项`} className="choice-response" data-question-id={question.id}>
      {options.map((option) => {
        const checked = current.includes(option.id);
        return (
          <label
            className="choice-option"
            data-overlay-only={optionId === undefined ? "false" : "true"}
            data-selected={checked ? "true" : "false"}
            key={option.id}
          >
            <input
              aria-describedby={describedBy}
              aria-label={`第 ${question.number} 题 ${option.id} ${option.label}`}
              checked={checked}
              disabled={disabled}
              name={`choice-${question.id}`}
              onChange={() => toggle(option.id)}
              type={multi ? "checkbox" : "radio"}
              value={option.id}
            />
            {optionId === undefined ? (
              <>
                <span aria-hidden="true">{option.id}</span>
                <span>{option.label}</span>
              </>
            ) : null}
          </label>
        );
      })}
    </fieldset>
  );
}

export default ChoiceResponse;
