import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { loadPack } from "../lib/loadPack";
import { normalizeAnswer } from "../lib/marker";
import {
  captureMistakeVocabulary,
  loadMistakeVocabularyNotebook,
  recordMistakePractice,
  removeMistakeCard,
  saveMistakeVocabularyNotebook,
  type MistakeVocabularyNotebookState,
} from "../lib/mistakeVocabulary";
import { hasAnyAnswer, markAttemptedSections } from "../lib/scopedSubmission";
import {
  createEmptySession,
  loadSession,
  saveSession,
  type PracticeSession,
} from "../lib/session";
import type { AnswerMap, LoadedPack, MarkResult } from "../types/pack";

type PracticeView = "home" | "workspace" | "mistakes";

interface PracticeSessionContextValue {
  pack: LoadedPack | null;
  loading: boolean;
  error: string | null;
  view: PracticeView;
  activeSection: number;
  answers: AnswerMap;
  setAnswer: (questionId: string, value: string) => void;
  setAnswers: (updates: AnswerMap) => void;
  setActiveSection: (section: number) => void;
  submit: () => MarkResult | null;
  reset: () => void;
  goHome: () => void;
  startPractice: () => void;
  openMistakeVocabulary: () => void;
  result: MarkResult | null;
  nextIncorrectId: string | null;
  audioPositions: Record<string, number>;
  setAudioPosition: (section: number, position: number) => void;
  canSubmit: boolean;
  notebook: MistakeVocabularyNotebookState;
  submitMistakePractice: (cardKey: string, correct: boolean) => void;
  removeMistakeCard: (cardKey: string) => void;
}

const PracticeSessionContext = createContext<PracticeSessionContextValue | null>(null);

function updateAndSave(
  setSession: (updater: (session: PracticeSession) => PracticeSession) => void,
  updater: (session: PracticeSession) => PracticeSession,
): void {
  setSession((session) => {
    const next = updater(session);
    saveSession(next);
    return next;
  });
}

function capturedQuestionIdsForCard(pack: LoadedPack, cardKey: string): Set<string> {
  const normalizedCardKey = normalizeAnswer(cardKey);
  const ids = new Set<string>();

  for (const answer of pack.answers) {
    if (answer.questionIds.length !== 1) {
      continue;
    }
    const questionId = answer.questionIds[0];
    const question = pack.questionsById.get(questionId);
    if (question?.responseType !== "blank") {
      continue;
    }
    const canonical = answer.accepted[0]?.[0] ?? "";
    const normalizedCanonical = normalizeAnswer(canonical);
    const vocabularyItem = pack.vocabulary.find((item) => normalizeAnswer(item.term) === normalizedCanonical);
    if (normalizedCardKey === normalizedCanonical || cardKey === vocabularyItem?.id) {
      ids.add(questionId);
    }
  }

  return ids;
}

export function PracticeSessionProvider({ children }: { children: ReactNode }) {
  const [pack, setPack] = useState<LoadedPack | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<PracticeView>("home");
  const [session, setSession] = useState<PracticeSession>(() => loadSession() ?? createEmptySession());
  const [notebook, setNotebook] = useState<MistakeVocabularyNotebookState>(() => loadMistakeVocabularyNotebook());

  useEffect(() => {
    let cancelled = false;

    async function run() {
      try {
        const loaded = await loadPack();
        if (!cancelled) {
          setPack(loaded);
          setError(null);
        }
      } catch (caught) {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : "Failed to load pack");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void run();

    return () => {
      cancelled = true;
    };
  }, []);

  const setAnswer = useCallback((questionId: string, value: string) => {
    updateAndSave(setSession, (current) => ({
      ...current,
      answers: { ...current.answers, [questionId]: value },
      submitted: false,
      results: null,
    }));
  }, []);

  const setAnswers = useCallback((updates: AnswerMap) => {
    updateAndSave(setSession, (current) => ({
      ...current,
      answers: { ...current.answers, ...updates },
      submitted: false,
      results: null,
    }));
  }, []);

  const setActiveSection = useCallback((section: number) => {
    updateAndSave(setSession, (current) => ({
      ...current,
      activeSection: section,
    }));
  }, []);

  const submit = useCallback(() => {
    if (pack === null) {
      return null;
    }
    if (!hasAnyAnswer(session.answers)) {
      return null;
    }

    const result = markAttemptedSections(pack, session.answers);
    const captured = captureMistakeVocabulary({
      pack: {
        packId: pack.manifest.packId,
        questions: pack.questions,
        vocabulary: pack.vocabulary,
        questionsById: pack.questionsById,
      },
      result,
      notebook,
      capturedMistakes: session.capturedMistakes,
    });
    saveMistakeVocabularyNotebook(captured.notebook);
    setNotebook(captured.notebook);
    updateAndSave(setSession, (current) => ({
      ...current,
      submitted: true,
      results: result,
      capturedMistakes: captured.capturedMistakes,
    }));
    return result;
  }, [notebook, pack, session.answers, session.capturedMistakes]);

  const reset = useCallback(() => {
    updateAndSave(setSession, (current) => createEmptySession(current.activeSection));
  }, []);

  const goHome = useCallback(() => {
    setView("home");
  }, []);

  const startPractice = useCallback(() => {
    setView("workspace");
  }, []);

  const openMistakeVocabulary = useCallback(() => {
    setView("mistakes");
  }, []);

  const setAudioPosition = useCallback((section: number, position: number) => {
    updateAndSave(setSession, (current) => ({
      ...current,
      audioPositions: { ...current.audioPositions, [String(section)]: position },
    }));
  }, []);

  const submitMistakePractice = useCallback((cardKey: string, correct: boolean) => {
    setNotebook((current) => {
      const next = recordMistakePractice(current, cardKey, correct);
      saveMistakeVocabularyNotebook(next);
      return next;
    });
  }, []);

  const removeMistakeCardFromNotebook = useCallback((cardKey: string) => {
    setNotebook((current) => {
      const next = removeMistakeCard(current, cardKey);
      saveMistakeVocabularyNotebook(next);
      return next;
    });
    if (pack !== null) {
      const questionIds = capturedQuestionIdsForCard(pack, cardKey);
      updateAndSave(setSession, (current) => {
        const nextCapturedMistakes = { ...current.capturedMistakes };
        for (const questionId of questionIds) {
          delete nextCapturedMistakes[questionId];
        }
        return {
          ...current,
          capturedMistakes: nextCapturedMistakes,
        };
      });
    }
  }, [pack]);

  const value = useMemo<PracticeSessionContextValue>(
    () => ({
      pack,
      loading,
      error,
      view,
      activeSection: session.activeSection,
      answers: session.answers,
      setAnswer,
      setAnswers,
      setActiveSection,
      submit,
      reset,
      goHome,
      startPractice,
      openMistakeVocabulary,
      result: session.results,
      nextIncorrectId: session.results?.incorrectIds[0] ?? null,
      audioPositions: session.audioPositions,
      setAudioPosition,
      canSubmit: hasAnyAnswer(session.answers),
      notebook,
      submitMistakePractice,
      removeMistakeCard: removeMistakeCardFromNotebook,
    }),
    [
      pack,
      loading,
      error,
      view,
      session,
      setAnswer,
      setAnswers,
      setActiveSection,
      submit,
      reset,
      goHome,
      startPractice,
      openMistakeVocabulary,
      setAudioPosition,
      notebook,
      submitMistakePractice,
      removeMistakeCardFromNotebook,
    ],
  );

  return <PracticeSessionContext.Provider value={value}>{children}</PracticeSessionContext.Provider>;
}

export function usePracticeSession(): PracticeSessionContextValue {
  const value = useContext(PracticeSessionContext);
  if (value === null) {
    throw new Error("usePracticeSession must be used within PracticeSessionProvider");
  }
  return value;
}
