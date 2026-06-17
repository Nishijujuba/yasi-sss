import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ChoiceResponse } from "./ChoiceResponse";
import type { Question } from "../types/pack";

const multiChoiceQuestion: Question = {
  id: "q11",
  number: 11,
  section: 2,
  responseType: "multi-choice",
  page: "page-012.png",
  focusOrder: 11,
  selectionLimit: 2,
  options: [
    { id: "A", label: "the gym" },
    { id: "B", label: "the tracks" },
    { id: "C", label: "the indoor pool" },
    { id: "D", label: "the outdoor pool" },
    { id: "E", label: "the sports training for children" },
  ],
};

describe("ChoiceResponse", () => {
  it("enforces the two-option limit for questions 11 and 12", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(<ChoiceResponse question={multiChoiceQuestion} value={[]} onChange={onChange} />);

    await user.click(screen.getByRole("checkbox", { name: /A/ }));
    await user.click(screen.getByRole("checkbox", { name: /C/ }));
    await user.click(screen.getByRole("checkbox", { name: /E/ }));

    expect(onChange).toHaveBeenLastCalledWith(["A", "C"]);
  });

  it("renders an overlay-only option without duplicating printed option text", () => {
    const onChange = vi.fn();
    const { container } = render(
      <ChoiceResponse
        optionId="A"
        question={multiChoiceQuestion}
        value={[]}
        onChange={onChange}
      />,
    );

    const label = container.querySelector(".choice-option");
    expect(label?.textContent).toBe("");
    expect(container.querySelector("input")?.getAttribute("aria-label")).toContain("A the gym");
  });
});
