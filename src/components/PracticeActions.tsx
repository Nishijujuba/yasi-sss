import { useState } from "react";

export interface PracticeActionsProps {
  onSubmit?: () => void;
  onReset?: () => void;
  onGoHome?: () => void;
  onNextIncorrect?: () => void;
  hasResult?: boolean;
  hasIncorrect?: boolean;
}

export function PracticeActions({
  onSubmit,
  onReset,
  onGoHome,
  onNextIncorrect,
  hasResult = false,
  hasIncorrect = false,
}: PracticeActionsProps) {
  const [confirmingReset, setConfirmingReset] = useState(false);

  return (
    <aside aria-label="练习操作" className="action-rail">
      <section aria-label="快捷键说明" className="shortcut-panel">
        <strong>快捷键</strong>
        <p>Enter：播放 / 暂停</p>
        <p>Alt + ← / →：跳转 5 秒</p>
      </section>

      <button className="primary-submit" onClick={onSubmit} type="button">
        提交答案
      </button>
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

      <button disabled type="button">
        精听
      </button>
      <button disabled type="button">
        原文跟读
      </button>
    </aside>
  );
}

export default PracticeActions;
