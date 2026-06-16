export interface KeyboardShortcutActions {
  togglePlayPause: () => void;
  seekBy: (seconds: number) => void;
}

function isAnswerEntryTarget(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) {
    return false;
  }

  return Boolean(
    target.closest(
      'input, textarea, select, button, [contenteditable="true"], [data-answer-entry], .answer-entry',
    ),
  );
}

export function handlePracticeKeyboard(
  event: KeyboardEvent,
  actions: KeyboardShortcutActions,
): boolean {
  if (event.key === "Enter" && !event.altKey && !event.ctrlKey && !event.metaKey && !event.shiftKey) {
    if (isAnswerEntryTarget(event.target)) {
      return false;
    }
    event.preventDefault();
    actions.togglePlayPause();
    return true;
  }

  if (event.altKey && event.key === "ArrowLeft") {
    event.preventDefault();
    actions.seekBy(-5);
    return true;
  }

  if (event.altKey && event.key === "ArrowRight") {
    event.preventDefault();
    actions.seekBy(5);
    return true;
  }

  return false;
}
