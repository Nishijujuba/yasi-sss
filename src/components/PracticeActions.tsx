import { useState } from "react";

export interface PracticeActionsProps {
  onSubmit?: () => void;
  onReset?: () => void;
  onGoHome?: () => void;
  onNextIncorrect?: () => void;
  hasResult?: boolean;
  hasIncorrect?: boolean;
  canSubmit?: boolean;
  transcriptShadowingAvailable?: boolean;
  transcriptShadowingOpen?: boolean;
  transcriptShadowingHint?: string;
  onToggleTranscriptShadowing?: () => void;
  intensiveListeningAvailable?: boolean;
  intensiveListeningUnlocked?: boolean;
  intensiveListeningHint?: string;
  onOpenIntensiveListening?: () => void;
}

export function PracticeActions({
  onSubmit,
  onReset,
  onGoHome,
  onNextIncorrect,
  hasResult = false,
  hasIncorrect = false,
  canSubmit = true,
  transcriptShadowingAvailable = false,
  transcriptShadowingOpen = false,
  transcriptShadowingHint = "等待逐词时间轴",
  onToggleTranscriptShadowing,
  intensiveListeningAvailable = false,
  intensiveListeningUnlocked = false,
  intensiveListeningHint,
  onOpenIntensiveListening,
}: PracticeActionsProps) {
  const [confirmingReset, setConfirmingReset] = useState(false);
  const canOpenIntensiveListening = intensiveListeningAvailable && intensiveListeningUnlocked;
  const resolvedIntensiveListeningHint =
    intensiveListeningHint ??
    (intensiveListeningAvailable ? "提交当前 Section 后开放精听" : "等待精听数据");

  return (
    <aside aria-label="练习操作" className="action-rail">
      <section aria-label="快捷键说明" className="shortcut-panel">
        <strong>快捷键</strong>
        <p>Enter：播放 / 暂停</p>
        <p>Alt + ← / →：跳转 5 秒</p>
      </section>

      <button className="primary-submit" disabled={!canSubmit} onClick={onSubmit} type="button">
        提交答案
      </button>
      {canSubmit ? null : <p className="action-hint">先完成至少一个答案</p>}
      <button
        className="secondary-action"
        disabled={!hasResult || !hasIncorrect}
        onClick={onNextIncorrect}
        type="button"
      >
        下一错误题
      </button>
      <button className="secondary-action" onClick={onGoHome} type="button">
        返回首页
      </button>

      {confirmingReset ? (
        <div aria-label="确认重置" className="reset-confirm" role="group">
          <p>重置会清空答案、判分结果和音频位置，并保留当前 Section。</p>
          <button
            className="secondary-action"
            onClick={() => {
              onReset?.();
              setConfirmingReset(false);
            }}
            type="button"
          >
            确认重置
          </button>
          <button className="secondary-action" onClick={() => setConfirmingReset(false)} type="button">
            取消
          </button>
        </div>
      ) : (
        <button className="secondary-action" onClick={() => setConfirmingReset(true)} type="button">
          重置练习
        </button>
      )}

      <button
        className="secondary-action"
        disabled={!canOpenIntensiveListening}
        onClick={onOpenIntensiveListening}
        type="button"
      >
        精听
      </button>
      {canOpenIntensiveListening ? null : <p className="action-hint">{resolvedIntensiveListeningHint}</p>}
      <button
        className="secondary-action"
        disabled={!transcriptShadowingAvailable}
        onClick={onToggleTranscriptShadowing}
        type="button"
      >
        {transcriptShadowingAvailable ? (transcriptShadowingOpen ? "收起原文" : "打开原文") : "原文跟读"}
      </button>
      {transcriptShadowingAvailable ? null : <p className="action-hint">{transcriptShadowingHint}</p>}
    </aside>
  );
}

export default PracticeActions;
