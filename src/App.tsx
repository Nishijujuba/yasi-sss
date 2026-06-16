import { ExamWorkspace } from "./components/ExamWorkspace";
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
        nextIncorrectId={session.nextIncorrectId}
        onAnswerChange={session.setAnswer}
        onAnswersChange={session.setAnswers}
        onAudioPositionChange={session.setAudioPosition}
        onGoHome={session.goHome}
        onReset={session.reset}
        onSectionChange={session.setActiveSection}
        onSubmit={session.submit}
        pack={session.pack}
        result={session.result}
      />
    );
  }

  return (
    <PracticePackHome
      activeSection={session.activeSection}
      answers={session.answers}
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
