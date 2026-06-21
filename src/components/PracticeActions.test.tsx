import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import PracticeActions from "./PracticeActions";

describe("PracticeActions", () => {
  afterEach(() => {
    cleanup();
  });

  it("opens Intensive Listening from the action rail when the current section is unlocked", () => {
    const onOpenIntensiveListening = vi.fn();

    render(
      <PracticeActions
        intensiveListeningAvailable
        intensiveListeningUnlocked
        onOpenIntensiveListening={onOpenIntensiveListening}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "精听" }));

    expect(onOpenIntensiveListening).toHaveBeenCalledOnce();
  });

  it("keeps Intensive Listening locked before current section submission", () => {
    const onOpenIntensiveListening = vi.fn();

    render(
      <PracticeActions
        intensiveListeningAvailable
        intensiveListeningUnlocked={false}
        onOpenIntensiveListening={onOpenIntensiveListening}
      />,
    );

    expect(screen.getByRole("button", { name: "精听" })).toBeDisabled();
    expect(screen.getByText("提交当前 Section 后开放精听")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "精听" }));
    expect(onOpenIntensiveListening).not.toHaveBeenCalled();
  });
});
