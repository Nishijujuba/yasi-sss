import { useEffect, type RefObject } from "react";
import type { AudioController } from "./ExamWorkspace";

export interface AudioPlayerProps {
  section: number;
  src: string;
  initialPosition?: number;
  audioController?: AudioController;
  audioRef?: RefObject<HTMLAudioElement | null>;
  onPositionChange?: (section: number, position: number) => void;
  onPlayStateChange?: (playing: boolean) => void;
}

export function AudioPlayer({
  section,
  src,
  initialPosition = 0,
  audioController,
  audioRef,
  onPositionChange,
  onPlayStateChange,
}: AudioPlayerProps) {
  const label = String(section).padStart(2, "0");

  function restorePosition(audio: HTMLAudioElement): void {
    if (!Number.isFinite(initialPosition)) {
      return;
    }
    try {
      audio.currentTime = Math.max(initialPosition, 0);
    } catch {
      return;
    }
  }

  function play(): void {
    const audio = audioRef?.current ?? null;
    if (audio !== null) {
      void audio.play();
      onPlayStateChange?.(true);
    }
    audioController?.play?.(section);
  }

  function pause(): void {
    const audio = audioRef?.current ?? null;
    if (audio !== null && !audio.paused) {
      audio.pause();
      onPlayStateChange?.(false);
      onPositionChange?.(section, audio.currentTime);
    }
    audioController?.pause(section);
  }

  function seek(deltaSeconds: number): void {
    const audio = audioRef?.current ?? null;
    if (audio !== null) {
      const nextPosition = Math.max(audio.currentTime + deltaSeconds, 0);
      audio.currentTime = nextPosition;
      onPositionChange?.(section, nextPosition);
    }
    audioController?.seek?.(section, deltaSeconds);
  }

  useEffect(() => {
    const audio = audioRef?.current ?? null;
    if (audio !== null) {
      restorePosition(audio);
    }
  }, [audioRef, initialPosition, src]);

  return (
    <section aria-label={`Section ${label} 音频`} className="audio-player">
      <div className="audio-player__header">
        <strong>音频 Section {label}</strong>
        <span aria-label="保存的播放位置">约 {Math.floor(initialPosition)} 秒</span>
      </div>
      <audio
        controls
        onPause={(event) => {
          onPlayStateChange?.(false);
          onPositionChange?.(section, event.currentTarget.currentTime);
        }}
        onLoadedMetadata={(event) => restorePosition(event.currentTarget)}
        onPlay={() => onPlayStateChange?.(true)}
        onTimeUpdate={(event) => onPositionChange?.(section, event.currentTarget.currentTime)}
        preload="metadata"
        ref={audioRef}
        src={src}
      />
      <div className="audio-player__controls">
        <button type="button" onClick={play}>
          播放
        </button>
        <button type="button" onClick={pause}>
          暂停
        </button>
        <button type="button" onClick={() => seek(-5)}>
          后退 5 秒
        </button>
        <button type="button" onClick={() => seek(5)}>
          前进 5 秒
        </button>
      </div>
    </section>
  );
}

export default AudioPlayer;
