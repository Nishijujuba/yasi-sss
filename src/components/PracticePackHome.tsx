import type { AnswerMap, LoadedPack, MarkResult } from "../types/pack";

export interface PracticePackHomeProps {
  pack: LoadedPack;
  answers: AnswerMap;
  activeSection?: number;
  result?: MarkResult | null;
  onStart: () => void;
  onOpenMistakes?: () => void;
}

export function PracticePackHome({
  pack,
  answers,
  activeSection,
  result = null,
  onStart,
  onOpenMistakes,
}: PracticePackHomeProps) {
  const answered = pack.questions.filter((question) => (answers[question.id] ?? "").trim() !== "").length;
  const total = pack.questions.length;
  const hasProgress = answered > 0 || result !== null;

  return (
    <main className="home-screen" role="main">
      <section aria-label="练习包" className="home-card">
        <p className="eyebrow">IELTS Listening Practice</p>
        <h1>{pack.manifest.title}</h1>
        <p>发布包：{pack.manifest.packId}</p>
        {activeSection === undefined ? null : (
          <p>当前 Section：{String(activeSection).padStart(2, "0")}</p>
        )}
        <p>
          进度：已作答 {answered} / {total}
        </p>
        {result === null ? null : (
          <p>
            上次 raw score：{result.score} / {result.total}
          </p>
        )}
        <button className="home-start" onClick={onStart} type="button">
          {hasProgress ? "继续练习" : "开始练习"}
        </button>
        <button className="secondary-action home-mistakes" onClick={onOpenMistakes} type="button">
          错题本
        </button>
      </section>
    </main>
  );
}

export default PracticePackHome;
