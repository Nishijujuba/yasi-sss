export interface PackErrorScreenProps {
  message: string;
  onRetry?: () => void;
}

export function PackErrorScreen({ message, onRetry }: PackErrorScreenProps) {
  return (
    <main className="pack-error-screen" role="alert">
      <h1>练习包加载失败</h1>
      <p>{message}</p>
      <p>
        练习包是发布产物。manifest、题面图片、音频、答案或 overlay 任何一环漂移，都会影响练习完整性。
      </p>
      {onRetry === undefined ? null : (
        <button onClick={onRetry} type="button">
          重新加载
        </button>
      )}
    </main>
  );
}

export default PackErrorScreen;
