import { createRef } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AudioPlayer } from "./AudioPlayer";

describe("AudioPlayer", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("does not restore position again when playback progress is saved", () => {
    const onPositionChange = vi.fn();
    const audioRef = createRef<HTMLAudioElement>();
    const { container, rerender } = render(
      <AudioPlayer
        audioRef={audioRef}
        initialPosition={12}
        section={1}
        src="/packs/example/section-01.mp3"
        onPositionChange={onPositionChange}
      />,
    );

    const audio = container.querySelector<HTMLAudioElement>("audio");
    expect(audio).not.toBeNull();

    let currentTime = 0;
    const setCurrentTime = vi.fn((nextTime: number) => {
      currentTime = nextTime;
    });
    Object.defineProperty(audio!, "currentTime", {
      configurable: true,
      get: () => currentTime,
      set: setCurrentTime,
    });

    fireEvent.loadedMetadata(audio!);
    expect(setCurrentTime).toHaveBeenLastCalledWith(12);

    setCurrentTime.mockClear();
    currentTime = 13;
    fireEvent.timeUpdate(audio!);
    expect(onPositionChange).toHaveBeenLastCalledWith(1, 13);

    rerender(
      <AudioPlayer
        audioRef={audioRef}
        initialPosition={13}
        section={1}
        src="/packs/example/section-01.mp3"
        onPositionChange={onPositionChange}
      />,
    );

    expect(setCurrentTime).not.toHaveBeenCalled();
  });

  it("does not report playback as active when the browser rejects play", async () => {
    const play = vi
      .spyOn(HTMLMediaElement.prototype, "play")
      .mockRejectedValueOnce(new DOMException("Blocked", "NotAllowedError"));
    const onPlayStateChange = vi.fn();
    const audioRef = createRef<HTMLAudioElement>();

    render(
      <AudioPlayer
        audioRef={audioRef}
        initialPosition={0}
        section={1}
        src="/packs/example/section-01.mp3"
        onPlayStateChange={onPlayStateChange}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "播放" }));

    await waitFor(() => expect(play).toHaveBeenCalledTimes(1));
    expect(onPlayStateChange).not.toHaveBeenCalledWith(true);
    expect(onPlayStateChange).toHaveBeenLastCalledWith(false);
  });
});
