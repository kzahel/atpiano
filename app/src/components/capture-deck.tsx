import type {
  RuntimeCapabilities,
  Session,
} from "../runtime/atpiano-runtime.js";
import type { CaptureState } from "../state/workspace-store.js";

const phaseCopy: Record<CaptureState["phase"], string> = {
  idle: "Ready for a new performance",
  requesting: "Requesting access…",
  warming: "Warming recognition models…",
  recording: "Listening and correcting",
  stopping: "Settling the final notes…",
  failed: "Capture needs attention",
};

export function CaptureDeck({
  capabilities,
  captureState,
  activeSession,
  onMicrophone,
  onReplay,
  onStop,
  onDismissError,
}: {
  readonly capabilities: RuntimeCapabilities | undefined;
  readonly captureState: CaptureState;
  readonly activeSession: Session | undefined;
  readonly onMicrophone: () => void;
  readonly onReplay: () => void;
  readonly onStop: () => void;
  readonly onDismissError: () => void;
}) {
  const busy = ["requesting", "warming", "recording", "stopping"].includes(
    captureState.phase,
  );
  const recording = captureState.phase === "recording";
  return (
    <section className="capture-deck" aria-labelledby="capture-title">
      <div>
        <p className="eyebrow">New performance</p>
        <h2 id="capture-title">What would you like to play?</h2>
        <p className="capture-copy">
          Start with your piano, or replay the deterministic musical fixture.
          Fast notes appear first; corrected notes settle behind them.
        </p>
      </div>
      <div className="capture-actions">
        <button
          className="button primary"
          type="button"
          disabled={busy || !capabilities?.capture_sources.includes("microphone")}
          onClick={onMicrophone}
        >
          <span aria-hidden="true">●</span>
          Start microphone
        </button>
        <button
          className="button secondary"
          type="button"
          disabled={busy || !capabilities?.capture_sources.includes("replay")}
          onClick={onReplay}
        >
          <span aria-hidden="true">▶</span>
          Replay musical fixture
        </button>
        {recording && captureState.capture?.source === "microphone" && (
          <button className="button stop" type="button" onClick={onStop}>
            Stop &amp; settle
          </button>
        )}
      </div>
      <div className={`capture-status ${captureState.phase}`} role="status">
        <i aria-hidden="true" />
        <span>
          <strong>{phaseCopy[captureState.phase]}</strong>
          {activeSession && (
            <small>Active session · {activeSession.display_name ?? activeSession.session_id}</small>
          )}
          {captureState.error && <small>{captureState.error}</small>}
        </span>
        {captureState.phase === "failed" && (
          <button type="button" onClick={onDismissError}>Dismiss</button>
        )}
      </div>
    </section>
  );
}
