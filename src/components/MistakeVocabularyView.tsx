import { useEffect, useMemo, useRef, useState } from "react";
import {
  fullPracticeQueue,
  matchesMistakeDictationAnswer,
  randomPracticeQueue,
  type MistakeVocabularyCardState,
  type MistakeVocabularyNotebookState,
  type MistakeVocabularyPracticeQueueEntry,
  type PracticeResult,
} from "../lib/mistakeVocabulary";
import type { LoadedPack, VocabularyItem } from "../types/pack";

interface MistakeVocabularyViewProps {
  pack: LoadedPack;
  notebook: MistakeVocabularyNotebookState;
  onGoHome: () => void;
  onArchiveCard: (cardKey: string) => void;
  onRemoveCard: (cardKey: string) => void;
  onRestoreCard: (cardKey: string) => void;
  onSubmitDictation: (cardKey: string, correct: boolean) => void;
  onSubmitPractice: (cardKey: string, correct: boolean) => void;
}

type CardEntry = MistakeVocabularyPracticeQueueEntry;

type StudyMode = "listening" | "dictation";
type PageMode = "active" | "archive";

interface ListeningRun {
  id: number;
  queue: CardEntry[];
  index: number;
  paused: boolean;
  showSpelling: boolean;
  showMeaning: boolean;
  reviewedKeys: string[];
  complete: boolean;
}

interface DictationRun {
  id: number;
  queue: CardEntry[];
  index: number;
  correct: number;
  reviewed: number;
  results: Record<string, PracticeResult>;
  answer: string;
  complete: boolean;
}

const DEFAULT_LISTENING_DELAY_SECONDS = 3;
const DICTATION_AUTO_SUBMIT_DELAY_MS = 3000;

function resolveAsset(baseUrl: string, path: string): string {
  if (/^https?:\/\//.test(path) || path.startsWith("/")) {
    return path;
  }
  return `${baseUrl.replace(/\/$/, "")}/${path.replace(/^\//, "")}`;
}

function secondsToMilliseconds(seconds: number): number {
  return Math.max(0, Math.round(seconds * 1000));
}

function orderedEntriesFromCards(cards: Record<string, MistakeVocabularyCardState>): CardEntry[] {
  return Object.entries(cards)
    .map(([key, card]) => ({ key, card }))
    .sort((left, right) => {
      const createdAtComparison = left.card.createdAt.localeCompare(right.card.createdAt);
      return createdAtComparison === 0
        ? left.card.termId.localeCompare(right.card.termId)
        : createdAtComparison;
    });
}

export function MistakeVocabularyView({
  pack,
  notebook,
  onArchiveCard,
  onGoHome,
  onRemoveCard,
  onRestoreCard,
  onSubmitDictation,
  onSubmitPractice,
}: MistakeVocabularyViewProps) {
  const audioRefs = useRef<Record<string, HTMLAudioElement | null>>({});
  const dictationInputRef = useRef<HTMLInputElement | null>(null);
  const listeningAdvanceTimerRef = useRef<number | null>(null);
  const dictationSubmitTimerRef = useRef<number | null>(null);
  const listeningRunRef = useRef<ListeningRun | null>(null);
  const dictationRunRef = useRef<DictationRun | null>(null);
  const nextRunIdRef = useRef(1);
  const entries = useMemo(() => fullPracticeQueue(notebook), [notebook]);
  const archivedEntries = useMemo(
    () => orderedEntriesFromCards(notebook.archivedCards ?? {}),
    [notebook.archivedCards],
  );
  const [pageMode, setPageMode] = useState<PageMode>("active");
  const [studyMode, setStudyMode] = useState<StudyMode>("listening");
  const [listeningDelaySeconds, setListeningDelaySeconds] = useState(DEFAULT_LISTENING_DELAY_SECONDS);
  const [listeningRun, setListeningRun] = useState<ListeningRun | null>(null);
  const [dictationRun, setDictationRun] = useState<DictationRun | null>(null);

  function itemFor(card: MistakeVocabularyCardState): VocabularyItem | undefined {
    return pack.vocabularyById.get(card.termId);
  }

  function clearListeningAdvanceTimer(): void {
    if (listeningAdvanceTimerRef.current !== null) {
      window.clearTimeout(listeningAdvanceTimerRef.current);
      listeningAdvanceTimerRef.current = null;
    }
  }

  function clearDictationSubmitTimer(): void {
    if (dictationSubmitTimerRef.current !== null) {
      window.clearTimeout(dictationSubmitTimerRef.current);
      dictationSubmitTimerRef.current = null;
    }
  }

  function pauseCardAudio(cardKey: string, reset = false): void {
    const audio = audioRefs.current[cardKey];
    if (audio === null || audio === undefined) {
      return;
    }
    audio.pause();
    if (reset) {
      audio.currentTime = 0;
    }
  }

  function stopListeningRun(): void {
    const current = listeningRunRef.current;
    const currentKey = current?.queue[current.index]?.key;
    if (currentKey !== undefined) {
      pauseCardAudio(currentKey, true);
    }
    clearListeningAdvanceTimer();
    setListeningRun(null);
  }

  function stopDictationRun(): void {
    const current = dictationRunRef.current;
    const currentKey = current?.queue[current.index]?.key;
    if (currentKey !== undefined) {
      pauseCardAudio(currentKey, true);
    }
    clearDictationSubmitTimer();
    setDictationRun(null);
  }

  function stopRuns(): void {
    stopListeningRun();
    stopDictationRun();
  }

  function startListeningRun(queue: CardEntry[]): void {
    if (queue.length === 0) {
      return;
    }
    stopDictationRun();
    stopListeningRun();
    setStudyMode("listening");
    setListeningRun({
      id: nextRunIdRef.current,
      queue,
      index: 0,
      paused: false,
      showSpelling: true,
      showMeaning: true,
      reviewedKeys: [],
      complete: false,
    });
    nextRunIdRef.current += 1;
  }

  function startDictationRun(queue: CardEntry[]): void {
    if (queue.length === 0) {
      return;
    }
    stopListeningRun();
    stopDictationRun();
    setStudyMode("dictation");
    setDictationRun({
      id: nextRunIdRef.current,
      queue,
      index: 0,
      correct: 0,
      reviewed: 0,
      results: {},
      answer: "",
      complete: false,
    });
    nextRunIdRef.current += 1;
  }

  function playCardAudio(cardKey: string): void {
    void audioRefs.current[cardKey]?.play();
  }

  function playCurrentListeningAudio(run: ListeningRun): void {
    if (run.complete || run.paused) {
      return;
    }
    const entry = run.queue[run.index];
    if (entry !== undefined) {
      playCardAudio(entry.key);
    }
  }

  function playCurrentDictationAudio(run: DictationRun): void {
    if (run.complete) {
      return;
    }
    const entry = run.queue[run.index];
    if (entry !== undefined) {
      playCardAudio(entry.key);
    }
  }

  function advanceListeningRun(): void {
    clearListeningAdvanceTimer();
    const current = listeningRunRef.current;
    if (current === null || current.complete) {
      return;
    }

    const currentKey = current.queue[current.index]?.key;
    const reviewedKeys =
      currentKey === undefined || current.reviewedKeys.includes(currentKey)
        ? current.reviewedKeys
        : [...current.reviewedKeys, currentKey];
    if (currentKey !== undefined && !current.reviewedKeys.includes(currentKey)) {
      onSubmitPractice(currentKey, true);
    }

    if (current.index >= current.queue.length - 1) {
      setListeningRun({
        ...current,
        reviewedKeys,
        complete: true,
      });
      return;
    }

    setListeningRun({
      ...current,
      reviewedKeys,
      index: current.index + 1,
    });
  }

  function handleAudioEnded(cardKey: string): void {
    const currentListening = listeningRunRef.current;
    if (currentListening !== null && !currentListening.paused && !currentListening.complete) {
      const entry = currentListening.queue[currentListening.index];
      if (entry?.key !== cardKey) {
        return;
      }
      clearListeningAdvanceTimer();
      listeningAdvanceTimerRef.current = window.setTimeout(() => {
        advanceListeningRun();
      }, secondsToMilliseconds(listeningDelaySeconds));
      return;
    }

    const currentDictation = dictationRunRef.current;
    if (currentDictation === null || currentDictation.complete) {
      return;
    }
    const entry = currentDictation.queue[currentDictation.index];
    if (entry?.key !== cardKey) {
      return;
    }
    clearDictationSubmitTimer();
    dictationSubmitTimerRef.current = window.setTimeout(() => {
      submitDictationCurrent();
    }, DICTATION_AUTO_SUBMIT_DELAY_MS);
  }

  function submitDictationCurrent(): void {
    clearDictationSubmitTimer();
    const current = dictationRunRef.current;
    if (current === null || current.complete) {
      return;
    }
    const entry = current.queue[current.index];
    const item = itemFor(entry.card);
    if (item === undefined) {
      return;
    }
    const correct = matchesMistakeDictationAnswer(item, current.answer);
    const result: PracticeResult = correct ? "correct" : "incorrect";
    const nextCorrect = current.correct + (correct ? 1 : 0);
    const nextReviewed = current.reviewed + 1;
    const nextResults = {
      ...current.results,
      [entry.key]: result,
    };
    onSubmitDictation(entry.key, correct);
    if (current.index >= current.queue.length - 1) {
      setDictationRun({
        ...current,
        correct: nextCorrect,
        reviewed: nextReviewed,
        results: nextResults,
        answer: "",
        complete: true,
      });
      return;
    }

    setDictationRun({
      ...current,
      correct: nextCorrect,
      reviewed: nextReviewed,
      results: nextResults,
      index: current.index + 1,
      answer: "",
    });
  }

  useEffect(() => {
    listeningRunRef.current = listeningRun;
  }, [listeningRun]);

  useEffect(() => {
    dictationRunRef.current = dictationRun;
  }, [dictationRun]);

  useEffect(() => {
    if (listeningRun === null || listeningRun.complete || listeningRun.paused) {
      return;
    }
    playCurrentListeningAudio(listeningRun);
  }, [listeningRun?.id, listeningRun?.index, listeningRun?.paused, listeningRun?.complete]);

  useEffect(() => {
    if (dictationRun === null || dictationRun.complete) {
      return;
    }
    playCurrentDictationAudio(dictationRun);
    dictationInputRef.current?.focus();
  }, [dictationRun?.id, dictationRun?.index, dictationRun?.complete]);

  useEffect(() => {
    return () => {
      clearListeningAdvanceTimer();
      clearDictationSubmitTimer();
    };
  }, []);

  const activeListeningRun = listeningRun === null || listeningRun.complete ? null : listeningRun;
  const listeningEntry = activeListeningRun === null ? null : activeListeningRun.queue[activeListeningRun.index];
  const listeningItem = listeningEntry === null ? undefined : itemFor(listeningEntry.card);
  const activeDictationRun = dictationRun === null || dictationRun.complete ? null : dictationRun;
  const dictationEntry = activeDictationRun === null ? null : activeDictationRun.queue[activeDictationRun.index];
  const dictationItem = dictationEntry === null ? undefined : itemFor(dictationEntry.card);
  const dictationAccuracy =
    dictationRun === null || dictationRun.reviewed === 0
      ? 0
      : Math.round((dictationRun.correct / dictationRun.reviewed) * 100);

  function switchStudyMode(nextMode: StudyMode): void {
    stopRuns();
    setStudyMode(nextMode);
  }

  function openArchive(): void {
    stopRuns();
    setPageMode("archive");
  }

  function openActiveCards(): void {
    setPageMode("active");
  }

  function startSelectedQueue(queue: CardEntry[]): void {
    if (studyMode === "listening") {
      startListeningRun(queue);
      return;
    }
    startDictationRun(queue);
  }

  function startFullQueue(): void {
    startSelectedQueue(fullPracticeQueue(notebook));
  }

  function startRandomQueue(): void {
    startSelectedQueue(randomPracticeQueue(notebook));
  }

  function renderModeTabs() {
    return (
      <div aria-label="复习模式" className="mistake-tabs" role="tablist">
        <button
          aria-selected={studyMode === "listening"}
          className="secondary-action"
          onClick={() => switchStudyMode("listening")}
          role="tab"
          type="button"
        >
          听音复习
        </button>
        <button
          aria-selected={studyMode === "dictation"}
          className="secondary-action"
          onClick={() => switchStudyMode("dictation")}
          role="tab"
          type="button"
        >
          听写模式
        </button>
      </div>
    );
  }

  function renderActiveToolbar() {
    const hasListeningRun = activeListeningRun !== null;
    return (
      <section className="mistake-toolbar" aria-label="错题本操作">
        <strong>共 {entries.length} 张</strong>
        {renderModeTabs()}
        {studyMode === "listening" ? (
          <label className="mistake-delay-control">
            间隔秒数
            <input
              aria-label="间隔秒数"
              min="0"
              step="1"
              type="number"
              value={listeningDelaySeconds}
              onChange={(event) => {
                const nextSeconds = Number(event.currentTarget.value);
                setListeningDelaySeconds(Number.isFinite(nextSeconds) ? Math.max(0, nextSeconds) : 0);
              }}
            />
          </label>
        ) : null}
        <div className="mistake-toolbar-group">
          <button className="primary-submit" onClick={startFullQueue} type="button">
            全部
          </button>
          <button className="secondary-action" onClick={startRandomQueue} type="button">
            随机 10
          </button>
          {studyMode === "listening" && hasListeningRun ? (
            <>
              {activeListeningRun.paused ? (
                <button
                  className="secondary-action"
                  onClick={() => setListeningRun({ ...activeListeningRun, paused: false })}
                  type="button"
                >
                  继续
                </button>
              ) : (
                <button
                  className="secondary-action"
                  onClick={() => {
                    clearListeningAdvanceTimer();
                    const currentKey = activeListeningRun.queue[activeListeningRun.index]?.key;
                    if (currentKey !== undefined) {
                      pauseCardAudio(currentKey);
                    }
                    setListeningRun({ ...activeListeningRun, paused: true });
                  }}
                  type="button"
                >
                  暂停
                </button>
              )}
              <button className="secondary-action" onClick={stopListeningRun} type="button">
                停止
              </button>
            </>
          ) : null}
          {studyMode === "dictation" && activeDictationRun !== null ? (
            <button className="secondary-action" onClick={stopDictationRun} type="button">
              停止
            </button>
          ) : null}
        </div>
        <button className="secondary-action" onClick={openArchive} type="button">
          查看归档
        </button>
      </section>
    );
  }

  function renderListeningRun() {
    if (listeningRun?.complete) {
      return (
        <section className="feedback-card" aria-label="听音复习结果">
          听音复习完成：{listeningRun.queue.length} 张
        </section>
      );
    }
    if (activeListeningRun === null || listeningEntry === null || listeningItem === undefined) {
      return null;
    }
    return (
      <section className="mistake-practice" aria-label="听音复习">
        <p className="mistake-run-meta">
          {activeListeningRun.index + 1} / {activeListeningRun.queue.length}
        </p>
        <div className="mistake-aids">
          <button
            aria-pressed={activeListeningRun.showSpelling}
            className="mistake-icon-toggle"
            onClick={() =>
              setListeningRun({
                ...activeListeningRun,
                showSpelling: !activeListeningRun.showSpelling,
              })
            }
            type="button"
          >
            {activeListeningRun.showSpelling ? "隐藏拼写" : "显示拼写"}
          </button>
          <button
            aria-pressed={activeListeningRun.showMeaning}
            className="mistake-icon-toggle"
            onClick={() =>
              setListeningRun({
                ...activeListeningRun,
                showMeaning: !activeListeningRun.showMeaning,
              })
            }
            type="button"
          >
            {activeListeningRun.showMeaning ? "隐藏含义" : "显示含义"}
          </button>
        </div>
        {activeListeningRun.showSpelling ? <p>正确拼写：{listeningItem.term}</p> : null}
        {listeningItem.acceptedVariants.length > 0 && activeListeningRun.showSpelling ? (
          <p>可接受形式：{listeningItem.acceptedVariants.join(" / ")}</p>
        ) : null}
        {activeListeningRun.showMeaning ? <p>{listeningItem.meaningZh}</p> : null}
      </section>
    );
  }

  function renderDictationRun() {
    if (dictationRun?.complete) {
      return (
        <section className="feedback-card" aria-label="听写结果">
          最终准确率：{dictationAccuracy}% ({dictationRun.correct} / {dictationRun.reviewed})
        </section>
      );
    }
    if (activeDictationRun === null || dictationEntry === null || dictationItem === undefined) {
      return null;
    }
    return (
      <section className="mistake-practice" aria-label="错题听写练习">
        <p className="mistake-run-meta">
          {activeDictationRun.index + 1} / {activeDictationRun.queue.length}
        </p>
        <label>
          听写答案
          <input
            aria-label="听写答案"
            ref={dictationInputRef}
            value={activeDictationRun.answer}
            onChange={(event) => setDictationRun({ ...activeDictationRun, answer: event.target.value })}
          />
        </label>
      </section>
    );
  }

  function renderCard(entry: CardEntry, archived: boolean, index: number) {
    const { key, card } = entry;
    const item = itemFor(card);
    const title = item?.term ?? card.termId;
    const isCurrentListeningCard = activeListeningRun?.queue[activeListeningRun.index]?.key === key;
    const isCurrentDictationCard = activeDictationRun?.queue[activeDictationRun.index]?.key === key;
    const isCurrentCard = isCurrentListeningCard || isCurrentDictationCard;
    const hideAnswerAids = !archived && activeDictationRun !== null;
    const disableCardPlayback = !archived && activeDictationRun !== null;
    const disableActiveCardMutation = !archived && (activeListeningRun !== null || activeDictationRun !== null);
    const cardLabel = hideAnswerAids ? `错题词 ${index + 1}` : `${archived ? "归档错题词" : "错题词"} ${title}`;
    const dictationQueueIncludesCard =
      !archived && studyMode === "dictation" && dictationRun?.queue.some((queued) => queued.key === key);
    const dictationRoundStatus =
      dictationQueueIncludesCard === true ? (dictationRun?.results[key] ?? "pending") : null;
    const dictationRoundStatusText =
      dictationRoundStatus === "correct" ? "正确" : dictationRoundStatus === "incorrect" ? "错误" : "待听写";

    return (
      <article
        aria-current={isCurrentCard ? "true" : undefined}
        aria-label={cardLabel}
        className={`mistake-card${isCurrentCard ? " mistake-card--active" : ""}`}
        key={key}
      >
        {item === undefined ? (
          <p>缺少词条：{card.termId}</p>
        ) : (
          <>
            <audio
              onEnded={() => handleAudioEnded(key)}
              ref={(element) => {
                audioRefs.current[key] = element;
              }}
              src={resolveAsset(pack.baseUrl, item.audio)}
            />
            {hideAnswerAids ? (
              <h2>待听写</h2>
            ) : (
              <>
                <h2>{item.term}</h2>
                {item.acceptedVariants.length === 0 ? null : <p>可接受形式：{item.acceptedVariants.join(" / ")}</p>}
                <p>{item.meaningZh}</p>
              </>
            )}
          </>
        )}
        {isCurrentCard ? <p className="mistake-current-marker">当前</p> : null}
        {dictationRoundStatus !== null ? (
          <p className={`mistake-round-status mistake-round-status--${dictationRoundStatus}`}>
            本轮：{dictationRoundStatusText}
          </p>
        ) : null}
        <p>错误次数：{card.mistakeCount}</p>
        <p>掌握次数：{card.masteryCount}</p>
        <div className="mistake-card-actions">
          <button
            className="secondary-action"
            disabled={item === undefined || disableCardPlayback}
            onClick={() => playCardAudio(key)}
            type="button"
          >
            播放
          </button>
          {archived ? (
            <button className="secondary-action" onClick={() => onRestoreCard(key)} type="button">
              恢复到错题本
            </button>
          ) : (
            <>
              <button
                className="secondary-action"
                disabled={disableActiveCardMutation}
                onClick={() => onArchiveCard(key)}
                type="button"
              >
                归档
              </button>
              <button
                className="secondary-action"
                disabled={disableActiveCardMutation}
                onClick={() => onRemoveCard(key)}
                type="button"
              >
                移除
              </button>
            </>
          )}
        </div>
      </article>
    );
  }

  function renderActiveCards() {
    if (entries.length === 0) {
      return (
        <>
          <section className="mistake-toolbar" aria-label="错题本操作">
            <strong>共 0 张</strong>
            <button className="secondary-action" onClick={openArchive} type="button">
              查看归档
            </button>
          </section>
          <section className="feedback-card">
            <h2>错题本为空</h2>
            <p>提交后，他答错且有输入的填空题会自动进入这里。</p>
          </section>
        </>
      );
    }
    return (
      <>
        {renderActiveToolbar()}
        {studyMode === "listening" ? renderListeningRun() : renderDictationRun()}
        <section className="mistake-list" aria-label="错题词列表">
          {entries.map((entry, index) => renderCard(entry, false, index))}
        </section>
      </>
    );
  }

  function renderArchiveCards() {
    return (
      <>
        <section className="mistake-toolbar" aria-label="归档操作">
          <div>
            <h2>归档错题</h2>
            <p>共 {archivedEntries.length} 张</p>
          </div>
          <button className="secondary-action" onClick={openActiveCards} type="button">
            返回错题本
          </button>
        </section>
        {archivedEntries.length === 0 ? (
          <section className="feedback-card">
            <h2>暂无归档错题</h2>
          </section>
        ) : (
          <section className="mistake-list" aria-label="归档错题词列表">
            {archivedEntries.map((entry, index) => renderCard(entry, true, index))}
          </section>
        )}
      </>
    );
  }

  return (
    <main className="mistake-screen" role="main">
      <header className="mistake-header">
        <div>
          <p className="eyebrow">Mistake Vocabulary</p>
          <h1>错题本</h1>
        </div>
        <button className="secondary-action" onClick={onGoHome} type="button">
          返回首页
        </button>
      </header>

      {pageMode === "archive" ? renderArchiveCards() : renderActiveCards()}
    </main>
  );
}

export default MistakeVocabularyView;
