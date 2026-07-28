import { useRef, useState, type ChangeEvent } from "react";

import type {
  Profile,
  RuntimeCapabilities,
  Session,
} from "../runtime/atpiano-runtime.js";
import type { CaptureState } from "../state/workspace-store.js";
import { PerformerSelect } from "./profile-controls.js";

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
  profiles = [],
  performerProfileId = null,
  onPerformerChange = () => {},
  onMicrophone,
  onImport,
  onReplay,
  onStop,
  onDismissError,
}: {
  readonly capabilities: RuntimeCapabilities | undefined;
  readonly captureState: CaptureState;
  readonly activeSession: Session | undefined;
  readonly profiles: readonly Profile[];
  readonly performerProfileId: string | null;
  readonly onPerformerChange: (profileId: string | null) => void;
  readonly onMicrophone: () => void;
  readonly onImport: (file: File) => void;
  readonly onReplay: () => void;
  readonly onStop: () => void;
  readonly onDismissError: () => void;
}) {
  const uploadInput = useRef<HTMLInputElement>(null);
  const [importName, setImportName] = useState<string | null>(null);
  const busy = ["requesting", "warming", "recording", "stopping"].includes(
    captureState.phase,
  );
  const recording = captureState.phase === "recording";
  const stopping = captureState.phase === "stopping";
  const fixtureMode = capabilities?.runtime_mode === "fixture";
  const fixtureReplayAvailable =
    fixtureMode && capabilities.capture_sources.includes("replay");
  const importAvailable =
    capabilities?.capture_sources.includes("upload") ?? false;
  const importing =
    importName !== null &&
    ["requesting", "warming"].includes(captureState.phase);
  const chooseImport = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = "";
    if (!file) return;
    setImportName(file.name);
    onImport(file);
  };
  const statusCopy = importing
    ? `Uploading ${importName}…`
    : phaseCopy[captureState.phase];
  return (
    <section className="capture-deck" aria-labelledby="capture-title">
      <div>
        <p className="eyebrow">New performance</p>
        <h2 id="capture-title">What would you like to play?</h2>
        <p className="capture-copy">
          {fixtureReplayAvailable
            ? "Play through your microphone, import a WAV or MP3, or run the bundled deterministic test recording. "
            : importAvailable
              ? "Play through your microphone, or import a WAV or MP3 recording. "
              : "Start a new performance using your piano. "}
          Notes appear as you play; live estimates settle behind them.
        </p>
      </div>
      <div className="capture-actions">
        <PerformerSelect
          profiles={profiles}
          value={performerProfileId}
          disabled={busy}
          onChange={onPerformerChange}
        />
        <button
          className="button primary"
          type="button"
          disabled={busy || !capabilities?.capture_sources.includes("microphone")}
          onClick={onMicrophone}
        >
          <span aria-hidden="true">●</span>
          Start microphone
        </button>
        {importAvailable && (
          <>
            <input
              ref={uploadInput}
              className="recording-file-input"
              type="file"
              accept=".wav,.mp3,audio/wav,audio/mpeg"
              aria-label="Choose WAV or MP3 recording"
              disabled={busy}
              onChange={chooseImport}
            />
            <button
              className="button secondary"
              type="button"
              disabled={busy}
              onClick={() => uploadInput.current?.click()}
            >
              <span aria-hidden="true">↑</span>
              Import recording
            </button>
          </>
        )}
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
          <strong>{statusCopy}</strong>
          {importing && (
            <progress aria-label="Recording upload progress" />
          )}
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
          <button
            type="button"
            onClick={() => {
              setImportName(null);
              onDismissError();
            }}
          >
            Dismiss
          </button>
        )}
      </div>
    </section>
  );
}
