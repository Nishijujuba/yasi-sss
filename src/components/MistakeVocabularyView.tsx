import { useMemo, useRef, useState } from "react";
import { normalizeAnswer } from "../lib/marker";
import {
  type MistakeVocabularyCardState,
  type MistakeVocabularyNotebookState,
} from "../lib/mistakeVocabulary";
import type { LoadedPack, VocabularyItem } from "../types/pack";

interface MistakeVocabularyViewProps {
  pack: LoadedPack;
  notebook: MistakeVocabularyNotebookState;
  onGoHome: () => void;
  onRemoveCard: (cardKey: string) => void;
  onSubmitPractice: (cardKey: string, correct: boolean) => void;
}

interface CardEntry {
  key: string;
  card: MistakeVocabularyCardState;
}

interface PracticeRun {
  queue: CardEntry[];
  index: number;
  correct: number;
  reviewed: number;
  answer: string;
  revealed: boolean;
  currentCorrect: boolean;
  complete: boolean;
}

function resolveAsset(baseUrl: string, path: string): string {
  if (/^https?:\/\//.test(path) || path.startsWith("/")) {
    return path;
  }
  return `${baseUrl.replace(/\/$/, "")}/${path.replace(/^\//, "")}`;
}

function orderedEntries(notebook: MistakeVocabularyNotebookState): CardEntry[] {
  return Object.entries(notebook.cards)
    .map(([key, card]) => ({ key, card }))
    .sort((left, right) => {
      const createdAtComparison = left.card.createdAt.localeCompare(right.card.createdAt);
      return createdAtComparison === 0
        ? left.card.termId.localeCompare(right.card.termId)
        : createdAtComparison;
    });
}

function sampleEntries(entries: CardEntry[], rng: () => number = Math.random): CardEntry[] {
  if (entries.length <= 10) {
    return entries;
  }

  const pool = [...entries];
  const sample: CardEntry[] = [];
  while (sample.length < 10 && pool.length > 0) {
    const index = Math.min(Math.floor(rng() * pool.length), pool.length - 1);
    const [entry] = pool.splice(index, 1);
    sample.push(entry);
  }
  return sample;
}

function acceptedForms(item: VocabularyItem): string[] {
  return [item.term, ...item.acceptedVariants];
}

function answerMatches(item: VocabularyItem, answer: string): boolean {
  const normalized = normalizeAnswer(answer);
  return acceptedForms(item).some((form) => normalizeAnswer(form) === normalized);
}

export function MistakeVocabularyView({
  pack,
  notebook,
  onGoHome,
  onRemoveCard,
  onSubmitPractice,
}: MistakeVocabularyViewProps) {
  const audioRefs = useRef<Record<string, HTMLAudioElement | null>>({});
  const entries = useMemo(() => orderedEntries(notebook), [notebook]);
  const [run, setRun] = useState<PracticeRun | null>(null);

  function itemFor(card: MistakeVocabularyCardState): VocabularyItem | undefined {
    return pack.vocabularyById.get(card.termId);
  }

  function startRun(queue: CardEntry[]): void {
    if (queue.length === 0) {
      return;
    }
    setRun({
      queue,
      index: 0,
      correct: 0,
      reviewed: 0,
      answer: "",
      revealed: false,
      currentCorrect: false,
      complete: false,
    });
  }

  function submitCurrent(): void {
    if (run === null || run.revealed) {
      return;
    }
    const entry = run.queue[run.index];
    const item = itemFor(entry.card);
    if (item === undefined) {
      return;
    }
    const correct = answerMatches(item, run.answer);
    onSubmitPractice(entry.key, correct);
    setRun({
      ...run,
      correct: run.correct + (correct ? 1 : 0),
      reviewed: run.reviewed + 1,
      currentCorrect: correct,
      revealed: true,
    });
  }

  function advanceRun(): void {
    if (run === null || !run.revealed) {
      return;
    }
    if (run.index >= run.queue.length - 1) {
      setRun({ ...run, complete: true });
      return;
    }
    setRun({
      ...run,
      index: run.index + 1,
      answer: "",
      revealed: false,
      currentCorrect: false,
    });
  }

  const activeRun = run === null || run.complete ? null : run;
  const currentEntry = activeRun === null ? null : activeRun.queue[activeRun.index];
  const currentItem = currentEntry === null ? undefined : itemFor(currentEntry.card);

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

      {entries.length === 0 ? (
        <section className="feedback-card">
          <h2>错题本为空</h2>
          <p>提交后，他答错且有输入的填空题会自动进入这里。</p>
        </section>
      ) : (
        <>
          <section className="mistake-toolbar" aria-label="错题本操作">
            <strong>共 {entries.length} 张</strong>
            <button className="primary-submit" onClick={() => startRun(entries)} type="button">
              全量顺序练习
            </button>
            <button className="secondary-action" onClick={() => startRun(sampleEntries(entries))} type="button">
              随机 10
            </button>
          </section>

          {run?.complete ? (
            <section className="feedback-card" aria-label="本轮结果">
              本轮结果：{run.correct} / {run.reviewed}
            </section>
          ) : null}

          {activeRun !== null && currentEntry !== null && currentItem !== undefined ? (
            <section className="mistake-practice" aria-label="错题听写练习">
              <p>
                {activeRun.index + 1} / {activeRun.queue.length}
              </p>
              <audio
                ref={(element) => {
                  audioRefs.current[currentEntry.key] = element;
                }}
                src={resolveAsset(pack.baseUrl, currentItem.audio)}
              />
              <button
                className="secondary-action"
                onClick={() => {
                  void audioRefs.current[currentEntry.key]?.play();
                }}
                type="button"
              >
                播放
              </button>
              <label>
                听写答案
                <input
                  aria-label="听写答案"
                  disabled={activeRun.revealed}
                  value={activeRun.answer}
                  onChange={(event) => setRun({ ...activeRun, answer: event.target.value })}
                />
              </label>
              <button
                className="primary-submit"
                disabled={activeRun.answer.trim() === ""}
                onClick={submitCurrent}
                type="button"
              >
                提交听写
              </button>
              {activeRun.revealed ? (
                <div className="practice-reveal">
                  <p>{activeRun.currentCorrect ? "正确" : "错误"}</p>
                  <p>正确拼写：{currentItem.term}</p>
                  {currentItem.acceptedVariants.length === 0 ? null : (
                    <p>可接受形式：{currentItem.acceptedVariants.join(" / ")}</p>
                  )}
                  <p>{currentItem.meaningZh}</p>
                  <button className="secondary-action" onClick={advanceRun} type="button">
                    {activeRun.index >= activeRun.queue.length - 1 ? "完成本轮" : "下一张"}
                  </button>
                </div>
              ) : null}
            </section>
          ) : null}

          <section className="mistake-list" aria-label="错题词列表">
            {entries.map(({ key, card }) => {
              const item = itemFor(card);
              const title = item?.term ?? card.termId;
              return (
                <article aria-label={`错题词 ${title}`} className="mistake-card" key={key}>
                  {item === undefined ? (
                    <p>缺少词条：{card.termId}</p>
                  ) : (
                    <>
                      <audio
                        ref={(element) => {
                          audioRefs.current[key] = element;
                        }}
                        src={resolveAsset(pack.baseUrl, item.audio)}
                      />
                      <h2>{item.term}</h2>
                      {item.acceptedVariants.length === 0 ? null : (
                        <p>可接受形式：{item.acceptedVariants.join(" / ")}</p>
                      )}
                      <p>{item.meaningZh}</p>
                    </>
                  )}
                  <p>错误次数：{card.mistakeCount}</p>
                  <p>掌握次数：{card.masteryCount}</p>
                  <button
                    className="secondary-action"
                    disabled={item === undefined}
                    onClick={() => {
                      void audioRefs.current[key]?.play();
                    }}
                    type="button"
                  >
                    播放
                  </button>
                  <button className="secondary-action" onClick={() => onRemoveCard(key)} type="button">
                    移除
                  </button>
                </article>
              );
            })}
          </section>
        </>
      )}
    </main>
  );
}

export default MistakeVocabularyView;
