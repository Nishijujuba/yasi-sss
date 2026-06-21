import { ExamWorkspace } from "./components/ExamWorkspace";
import IntensiveListeningView from "./components/IntensiveListeningView";
import { MistakeVocabularyView } from "./components/MistakeVocabularyView";
import { PackErrorScreen } from "./components/PackErrorScreen";
import { PracticePackHome } from "./components/PracticePackHome";
import { PracticeSessionProvider, usePracticeSession } from "./context/PracticeSessionContext";

function AppContent() {
  const session = usePracticeSession();

  if (session.loading) {
    return (
      <main className="app-loading" role="main">
        <h1>正在加载练习包</h1>
        <p>他正在读取已发布的 Cambridge IELTS 10 Test 1 Listening 练习包。</p>
      </main>
    );
  }

  if (session.error !== null || session.pack === null) {
    return <PackErrorScreen message={session.error ?? "练习包不可用"} />;
  }

  if (session.view === "workspace") {
    return (
      <ExamWorkspace
        activeSection={session.activeSection}
        answers={session.answers}
        audioPositions={session.audioPositions}
        canSubmit={session.canSubmit}
        nextIncorrectId={session.nextIncorrectId}
        onAnswerChange={session.setAnswer}
        onAnswersChange={session.setAnswers}
        onAudioPositionChange={session.setAudioPosition}
        onGoHome={session.goHome}
        onOpenIntensiveListening={session.openIntensiveListening}
        onReset={session.reset}
        onSectionChange={session.setActiveSection}
        onSubmit={session.submit}
        pack={session.pack}
        result={session.result}
      />
    );
  }

  if (session.view === "mistakes") {
    return (
      <MistakeVocabularyView
        notebook={session.notebook}
        onGoHome={session.goHome}
        onRemoveCard={session.removeMistakeCard}
        onSubmitPractice={session.submitMistakePractice}
        pack={session.pack}
      />
    );
  }

  if (session.view === "intensiveListening") {
    return (
      <IntensiveListeningView
        activeSection={session.activeSection}
        audioPositions={session.audioPositions}
        pack={session.pack}
        session={session.intensiveListeningSession}
        unlockedSections={session.intensiveListeningUnlockedSections}
        onAnswerChange={session.setIntensiveListeningAnswer}
        onAudioPositionChange={session.setAudioPosition}
        onGoBack={session.startPractice}
        onReset={session.resetIntensiveListening}
        onRevealAnswers={session.revealIntensiveListeningAnswers}
        onRevealTranscript={session.revealIntensiveListeningTranscript}
        onSectionChange={session.setActiveSection}
        onSubmit={session.submitIntensiveListening}
      />
    );
  }

  return (
    <PracticePackHome
      activeSection={session.activeSection}
      answers={session.answers}
      onOpenMistakes={session.openMistakeVocabulary}
      onStart={session.startPractice}
      pack={session.pack}
      result={session.result}
    />
  );
}

export default function App() {
  return (
    <PracticeSessionProvider>
      <AppContent />
    </PracticeSessionProvider>
  );
}
