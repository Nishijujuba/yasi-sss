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
import { markAnswers } from "../lib/marker";
import {
  createEmptySession,
  loadSession,
  saveSession,
  type PracticeSession,
} from "../lib/session";
import type { AnswerMap, LoadedPack, MarkResult } from "../types/pack";

type PracticeView = "home" | "workspace";

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
  result: MarkResult | null;
  nextIncorrectId: string | null;
  audioPositions: Record<string, number>;
  setAudioPosition: (section: number, position: number) => void;
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

export function PracticeSessionProvider({ children }: { children: ReactNode }) {
  const [pack, setPack] = useState<LoadedPack | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<PracticeView>("home");
  const [session, setSession] = useState<PracticeSession>(() => loadSession() ?? createEmptySession());

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

    const result = markAnswers(pack.questions, pack.answers, session.answers);
    updateAndSave(setSession, (current) => ({
      ...current,
      submitted: true,
      results: result,
    }));
    return result;
  }, [pack, session.answers]);

  const reset = useCallback(() => {
    updateAndSave(setSession, (current) => createEmptySession(current.activeSection));
  }, []);

  const goHome = useCallback(() => {
    setView("home");
  }, []);

  const startPractice = useCallback(() => {
    setView("workspace");
  }, []);

  const setAudioPosition = useCallback((section: number, position: number) => {
    updateAndSave(setSession, (current) => ({
      ...current,
      audioPositions: { ...current.audioPositions, [String(section)]: position },
    }));
  }, []);

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
      result: session.results,
      nextIncorrectId: session.results?.incorrectIds[0] ?? null,
      audioPositions: session.audioPositions,
      setAudioPosition,
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
      setAudioPosition,
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
