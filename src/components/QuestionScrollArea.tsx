import type { AnswerMap, MarkResult, OverlayRegion, Question } from "../types/pack";
import QuestionPage from "./QuestionPage";

export interface QuestionScrollAreaProps {
  baseUrl: string;
  pages: string[];
  questions: Question[];
  overlays: OverlayRegion[];
  answers: AnswerMap;
  result?: MarkResult | null;
  onAnswerChange: (questionId: string, value: string) => void;
  onAnswersChange?: (updates: AnswerMap) => void;
  revealedExpectedAnswers?: ReadonlySet<string>;
  onExpectedAnswerToggle?: (questionId: string) => void;
}

function basename(path: string): string {
  return path.split(/[\\/]/).at(-1) ?? path;
}

function resolveAsset(baseUrl: string, path: string): string {
  if (/^https?:\/\//.test(path) || path.startsWith("/")) {
    return path;
  }
  return `${baseUrl.replace(/\/$/, "")}/${path.replace(/^\//, "")}`;
}

export function QuestionScrollArea({
  baseUrl,
  pages,
  questions,
  overlays,
  answers,
  result,
  onAnswerChange,
  onAnswersChange,
  revealedExpectedAnswers,
  onExpectedAnswerToggle,
}: QuestionScrollAreaProps) {
  return (
    <section aria-label="题面滚动区" className="question-scroll">
      {pages.map((page) => {
        const pageName = basename(page);
        const pageQuestions = questions.filter((question) => question.page === pageName);
        const pageRegions = overlays.filter((region) => region.page === pageName);
        return (
          <QuestionPage
            answers={answers}
            imageSrc={resolveAsset(baseUrl, page)}
            key={page}
            pageName={pageName}
            questions={pageQuestions}
            regions={pageRegions}
            result={result}
            revealedExpectedAnswers={revealedExpectedAnswers}
            onAnswerChange={onAnswerChange}
            onAnswersChange={onAnswersChange}
            onExpectedAnswerToggle={onExpectedAnswerToggle}
          />
        );
      })}
    </section>
  );
}

export default QuestionScrollArea;
