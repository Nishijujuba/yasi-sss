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
  archiveMistakeCard,
  captureMistakeVocabulary,
  loadMistakeVocabularyNotebook,
  recordMistakeDictation,
  recordMistakePractice,
  removeMistakeCard,
  restoreMistakeCard,
  saveMistakeVocabularyNotebook,
  type MistakeVocabularyNotebookState,
} from "../lib/mistakeVocabulary";
import { hasAnyAnswer, markAttemptedSections } from "../lib/scopedSubmission";
import {
  createEmptySession,
  loadSession,
  SESSION_PACK_ID,
  saveSession,
  type PracticeSession,
} from "../lib/session";
import type { AnswerMap, LoadedPack, MarkResult } from "../types/pack";
import {
  createEmptyIntensiveListeningSession,
  isIntensiveListeningSectionUnlocked,
  loadIntensiveListeningSession,
  markIntensiveListeningSessionSection,
  revealIntensiveListeningAnswers as revealIntensiveListeningSessionAnswers,
  revealIntensiveListeningTranscript as revealIntensiveListeningSessionTranscript,
  saveIntensiveListeningSession,
  setIntensiveListeningAnswer as setIntensiveListeningSessionAnswer,
} from "../lib/intensiveListeningSession";
import type { IntensiveListeningSessionState } from "../lib/intensiveListeningSession";

type PracticeView = "home" | "workspace" | "mistakes" | "intensiveListening";

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
  openIntensiveListening: (section?: number) => void;
  result: MarkResult | null;
  nextIncorrectId: string | null;
  audioPositions: Record<string, number>;
  setAudioPosition: (section: number, position: number) => void;
  transcriptViewed: boolean;
  markTranscriptViewed: () => void;
  canSubmit: boolean;
  notebook: MistakeVocabularyNotebookState;
  archiveMistakeCard: (cardKey: string) => void;
  restoreMistakeCard: (cardKey: string) => void;
  submitMistakeDictation: (cardKey: string, correct: boolean) => void;
  submitMistakePractice: (cardKey: string, correct: boolean) => void;
  removeMistakeCard: (cardKey: string) => void;
  intensiveListeningSession: IntensiveListeningSessionState;
  intensiveListeningUnlockedSections: number[];
  intensiveListeningAvailable: boolean;
  intensiveListeningUnlocked: boolean;
  setIntensiveListeningAnswer: (section: number, blankId: string, value: string) => void;
  submitIntensiveListening: (section: number) => void;
  revealIntensiveListeningAnswers: (section: number) => void;
  revealIntensiveListeningTranscript: (section: number) => void;
  resetIntensiveListening: (section: number) => void;
}

const PracticeSessionContext = createContext<PracticeSessionContextValue | null>(null);

type TranscriptViewedSession = PracticeSession & {
  transcriptViewed?: boolean;
};

function intensiveListeningDrill(pack: LoadedPack | null, section: number) {
  return pack?.intensiveListening?.sections.find((entry) => entry.section === section) ?? null;
}

function intensiveListeningUnlockedSections(pack: LoadedPack | null, practiceSession: PracticeSession): number[] {
  if (pack === null) {
    return [];
  }
  return pack.manifest.sections
    .map((section) => section.number)
    .filter((section) => intensiveListeningDrill(pack, section) !== null)
    .filter((section) => isIntensiveListeningSectionUnlocked(pack, practiceSession, section));
}

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

function hasViewedTranscript(session: PracticeSession): boolean {
  return (session as TranscriptViewedSession).transcriptViewed === true;
}

export function PracticeSessionProvider({ children }: { children: ReactNode }) {
  const [pack, setPack] = useState<LoadedPack | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<PracticeView>("home");
  const [session, setSession] = useState<PracticeSession>(() => loadSession() ?? createEmptySession());
  const [notebook, setNotebook] = useState<MistakeVocabularyNotebookState>(() => loadMistakeVocabularyNotebook());
  const [intensiveSession, setIntensiveSession] = useState<IntensiveListeningSessionState>(
    () => loadIntensiveListeningSession(SESSION_PACK_ID) ?? createEmptyIntensiveListeningSession(SESSION_PACK_ID),
  );

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

  useEffect(() => {
    if (pack === null) {
      return;
    }
    const packId = pack.manifest.packId;
    setIntensiveSession((current) => {
      if (current.packId === packId) {
        return current;
      }
      return loadIntensiveListeningSession(packId) ?? createEmptyIntensiveListeningSession(packId);
    });
  }, [pack]);

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

  const updateIntensiveListeningSession = useCallback(
    (updater: (current: IntensiveListeningSessionState) => IntensiveListeningSessionState) => {
      setIntensiveSession((current) => {
        const next = updater(current);
        saveIntensiveListeningSession(next);
        return next;
      });
    },
    [],
  );

  const openIntensiveListening = useCallback((section = session.activeSection) => {
    if (pack === null || intensiveListeningDrill(pack, section) === null) {
      return;
    }
    if (!isIntensiveListeningSectionUnlocked(pack, session, section)) {
      return;
    }
    updateAndSave(setSession, (current) => ({
      ...current,
      activeSection: section,
    }));
    setView("intensiveListening");
  }, [pack, session]);

  const setIntensiveListeningAnswer = useCallback(
    (section: number, blankId: string, value: string) => {
      updateIntensiveListeningSession((current) =>
        setIntensiveListeningSessionAnswer(current, section, blankId, value),
      );
    },
    [updateIntensiveListeningSession],
  );

  const submitIntensiveListening = useCallback(
    (section: number) => {
      if (pack === null) {
        return;
      }
      updateIntensiveListeningSession((current) => {
        try {
          return markIntensiveListeningSessionSection(pack, current, section);
        } catch {
          return current;
        }
      });
    },
    [pack, updateIntensiveListeningSession],
  );

  const revealIntensiveListeningAnswers = useCallback(
    (section: number) => {
      if (pack === null) {
        return;
      }
      updateIntensiveListeningSession((current) => {
        try {
          const currentSection = current.sections[String(section)];
          const marked =
            currentSection?.marking === null || currentSection?.marking === undefined
              ? markIntensiveListeningSessionSection(pack, current, section)
              : current;
          return revealIntensiveListeningSessionAnswers(marked, section);
        } catch {
          return current;
        }
      });
    },
    [pack, updateIntensiveListeningSession],
  );

  const revealIntensiveListeningTranscript = useCallback(
    (section: number) => {
      if (pack === null) {
        return;
      }
      updateIntensiveListeningSession((current) => {
        try {
          const currentSection = current.sections[String(section)];
          const marked =
            currentSection?.marking === null || currentSection?.marking === undefined
              ? markIntensiveListeningSessionSection(pack, current, section)
              : current;
          return revealIntensiveListeningSessionTranscript(
            revealIntensiveListeningSessionAnswers(marked, section),
            section,
          );
        } catch {
          return current;
        }
      });
    },
    [pack, updateIntensiveListeningSession],
  );

  const resetIntensiveListening = useCallback(
    (section: number) => {
      updateIntensiveListeningSession((current) => {
        const nextSections = Object.fromEntries(
          Object.entries(current.sections).filter(([key]) => key !== String(section)),
        );
        return {
          ...current,
          sections: nextSections,
        };
      });
    },
    [updateIntensiveListeningSession],
  );

  const setAudioPosition = useCallback((section: number, position: number) => {
    updateAndSave(setSession, (current) => ({
      ...current,
      audioPositions: { ...current.audioPositions, [String(section)]: position },
    }));
  }, []);

  const markTranscriptViewed = useCallback(() => {
    updateAndSave(
      setSession,
      (current) =>
        ({
          ...current,
          transcriptViewed: true,
        }) as PracticeSession,
    );
  }, []);

  const submitMistakePractice = useCallback((cardKey: string, correct: boolean) => {
    setNotebook((current) => {
      const next = recordMistakePractice(current, cardKey, correct);
      saveMistakeVocabularyNotebook(next);
      return next;
    });
  }, []);

  const submitMistakeDictation = useCallback((cardKey: string, correct: boolean) => {
    setNotebook((current) => {
      const next = recordMistakeDictation(current, cardKey, correct);
      saveMistakeVocabularyNotebook(next);
      return next;
    });
  }, []);

  const clearCapturedMistakeSignatures = useCallback((cardKey: string) => {
    if (pack === null) {
      return;
    }
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
  }, [pack]);

  const archiveMistakeCardInNotebook = useCallback((cardKey: string) => {
    setNotebook((current) => {
      const next = archiveMistakeCard(current, cardKey);
      saveMistakeVocabularyNotebook(next);
      return next;
    });
    clearCapturedMistakeSignatures(cardKey);
  }, [clearCapturedMistakeSignatures]);

  const restoreMistakeCardInNotebook = useCallback((cardKey: string) => {
    setNotebook((current) => {
      const next = restoreMistakeCard(current, cardKey);
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
    clearCapturedMistakeSignatures(cardKey);
  }, [clearCapturedMistakeSignatures]);

  const unlockedIntensiveListeningSections = useMemo(
    () => intensiveListeningUnlockedSections(pack, session),
    [pack, session],
  );
  const activeIntensiveListeningAvailable = intensiveListeningDrill(pack, session.activeSection) !== null;
  const activeIntensiveListeningUnlocked = unlockedIntensiveListeningSections.includes(session.activeSection);

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
      openIntensiveListening,
      result: session.results,
      nextIncorrectId: session.results?.incorrectIds[0] ?? null,
      audioPositions: session.audioPositions,
      setAudioPosition,
      transcriptViewed: hasViewedTranscript(session),
      markTranscriptViewed,
      canSubmit: hasAnyAnswer(session.answers),
      notebook,
      archiveMistakeCard: archiveMistakeCardInNotebook,
      restoreMistakeCard: restoreMistakeCardInNotebook,
      submitMistakeDictation,
      submitMistakePractice,
      removeMistakeCard: removeMistakeCardFromNotebook,
      intensiveListeningSession: intensiveSession,
      intensiveListeningUnlockedSections: unlockedIntensiveListeningSections,
      intensiveListeningAvailable: activeIntensiveListeningAvailable,
      intensiveListeningUnlocked: activeIntensiveListeningUnlocked,
      setIntensiveListeningAnswer,
      submitIntensiveListening,
      revealIntensiveListeningAnswers,
      revealIntensiveListeningTranscript,
      resetIntensiveListening,
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
      openIntensiveListening,
      setAudioPosition,
      markTranscriptViewed,
      notebook,
      archiveMistakeCardInNotebook,
      restoreMistakeCardInNotebook,
      submitMistakeDictation,
      submitMistakePractice,
      removeMistakeCardFromNotebook,
      intensiveSession,
      unlockedIntensiveListeningSections,
      activeIntensiveListeningAvailable,
      activeIntensiveListeningUnlocked,
      setIntensiveListeningAnswer,
      submitIntensiveListening,
      revealIntensiveListeningAnswers,
      revealIntensiveListeningTranscript,
      resetIntensiveListening,
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

export function useOptionalPracticeSession(): PracticeSessionContextValue | null {
  return useContext(PracticeSessionContext);
}
