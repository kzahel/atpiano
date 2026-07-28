import type {
  RuntimeCapabilities,
  Session,
} from "../runtime/atpiano-runtime.js";
import type { CaptureState } from "../state/workspace-store.js";

const phaseCopy: Record<CaptureState["phase"], string> = {
  idle: "Ready for a new performance",
  requesting: "Requesting access…",
  warming: "Warming recognition models…",
  recording: "Listening for notes",
  stopping: "Closing microphone capture…",
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
  const stopping = captureState.phase === "stopping";
  const fixtureMode = capabilities?.runtime_mode === "fixture";
  const fixtureReplayAvailable =
    fixtureMode && capabilities.capture_sources.includes("replay");
  return (
    <section className="capture-deck" aria-labelledby="capture-title">
      <div>
        <p className="eyebrow">New performance</p>
        <h2 id="capture-title">What would you like to play?</h2>
        <p className="capture-copy">
          {fixtureReplayAvailable
            ? "Start with your piano, or run the bundled deterministic test recording. "
            : "Start a new performance using your piano. "}
          Notes appear as you play; corrected notes settle behind them.
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
        {fixtureReplayAvailable && (
          <button
            className="button secondary"
            type="button"
            disabled={busy}
            onClick={onReplay}
          >
            <span aria-hidden="true">▶</span>
            Run test recording
          </button>
        )}
        {(recording || stopping) && captureState.capture?.source === "microphone" && (
          <button
            className="button stop"
            type="button"
            disabled={stopping}
            onClick={onStop}
          >
            {stopping ? "Settling…" : "Stop & settle"}
          </button>
        )}
      </div>
      <div className={`capture-status ${captureState.phase}`} role="status">
        <i aria-hidden="true" />
        <span>
          <strong>{phaseCopy[captureState.phase]}</strong>
          {activeSession && (
            <small>
              Active session · {activeSession.display_name ?? activeSession.session_id}
              {activeSession.correction_mode
                ? ` · ${activeSession.correction_mode} correction`
                : ""}
            </small>
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
