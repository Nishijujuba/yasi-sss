import { createRef, useState } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AudioPlayer } from "./AudioPlayer";

function ControlledAudioPlayer() {
  const [playbackRate, setPlaybackRate] = useState(1);
  const audioRef = createRef<HTMLAudioElement>();
  return (
    <AudioPlayer
      audioRef={audioRef}
      initialPosition={0}
      playbackRate={playbackRate}
      section={1}
      src="/packs/example/section-01.mp3"
      onPlaybackRateChange={setPlaybackRate}
    />
  );
}

describe("AudioPlayer", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("changes native playback rate without moving the current audio time", () => {
    const { container } = render(<ControlledAudioPlayer />);

    const audio = container.querySelector<HTMLAudioElement>("audio");
    expect(audio).not.toBeNull();
    audio!.currentTime = 42;
    Object.defineProperty(audio!, "paused", { configurable: true, value: true });

    fireEvent.click(screen.getByRole("button", { name: "1.25x" }));

    expect(audio!.playbackRate).toBe(1.25);
    expect(audio!.currentTime).toBe(42);
    expect(audio!.paused).toBe(true);
    expect(screen.getByRole("button", { name: "1.25x" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "1.25x" })).toHaveAttribute("data-active", "true");
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
    currentTime = 27;
    rerender(
      <AudioPlayer
        audioRef={audioRef}
        initialPosition={12}
        section={1}
        src="/packs/example/section-01.mp3"
        onPositionChange={onPositionChange}
      />,
    );

    expect(setCurrentTime).not.toHaveBeenCalled();

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
