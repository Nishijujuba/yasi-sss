import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import "../styles.css";
import { BlankResponse } from "./BlankResponse";

describe("BlankResponse", () => {
  it("keeps the answer reveal toggle visually transparent inside the blank edge", () => {
    render(
      <BlankResponse
        expectedAnswer="method"
        questionNumber={39}
        value=""
        onChange={vi.fn()}
        onExpectedAnswerToggle={vi.fn()}
      />,
    );

    const toggle = screen.getByRole("button", { name: "显示第 39 题正确答案" });
    const stack = toggle.closest(".blank-response-stack");
    const style = getComputedStyle(toggle);

    expect(stack).not.toBeNull();
    expect(getComputedStyle(stack!).maxWidth).toBe("160px");
    expect(style.backgroundColor).toBe("rgba(0, 0, 0, 0)");
    expect(style.borderColor).toBe("rgba(0, 0, 0, 0)");
    expect(style.right).toBe("4px");
  });
});
