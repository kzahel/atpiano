import { useEffect, useRef, useState } from "react";

import type {
  DesktopScoreAcquisitionProgress,
  DesktopScoreLinkId,
  DesktopScoreRuntimeClient,
  DesktopScoreRuntimeStatus,
} from "../runtime/desktop-runtime.js";

function formatBytes(bytes: number): string {
  if (bytes >= 1_000_000_000) {
    return `${(bytes / 1_000_000_000).toFixed(1)} GB`;
  }
  return `${(bytes / 1_000_000).toFixed(bytes < 10_000_000 ? 1 : 0)} MB`;
}

function formatExactBytes(bytes: number): string {
  return `${bytes.toLocaleString("en-US")} bytes`;
}

function shortIdentity(value: string): string {
  return `${value.slice(0, 12)}…${value.slice(-8)}`;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

const phaseLabels: Record<DesktopScoreAcquisitionProgress["phase"], string> = {
  preparing: "Preparing private local storage…",
  source: "Downloading the pinned research source…",
  "verifying-source": "Verifying the research source…",
  checkpoint: "Downloading the research checkpoint…",
  installing: "Installing the verified model locally…",
  complete: "The research model is installed.",
};

export function DesktopScoreRuntimeDialog({
  open,
  manager,
  operationBlocker = null,
  onClose,
}: {
  readonly open: boolean;
  readonly manager: DesktopScoreRuntimeClient;
  readonly operationBlocker?: string | null;
  readonly onClose: () => void;
}) {
  const dialogRef = useRef<HTMLElement>(null);
  const invokingElement = useRef<HTMLElement | null>(null);
  const [status, setStatus] = useState<DesktopScoreRuntimeStatus | null>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [progress, setProgress] =
    useState<DesktopScoreAcquisitionProgress | null>(null);
  const [operation, setOperation] = useState<"idle" | "acquire" | "remove" | "relaunch">(
    "idle",
  );
  const [error, setError] = useState<string | null>(null);
  const [confirmRemoval, setConfirmRemoval] = useState(false);

  useEffect(() => {
    if (!open) return;
    invokingElement.current = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    setAcknowledged(false);
    setStatus(null);
    setProgress(null);
    setOperation("idle");
    setError(null);
    setConfirmRemoval(false);
    let disposed = false;
    let unlisten: (() => void) | undefined;
    void manager.status().then((value) => {
      if (!disposed) setStatus(value);
    }).catch((reason) => {
      if (!disposed) setError(errorMessage(reason));
    });
    void manager.monitor((value) => {
      if (!disposed) setProgress(value);
    }).then((release) => {
      if (disposed) release();
      else unlisten = release;
    }).catch((reason) => {
      if (!disposed) setError(errorMessage(reason));
    });
    window.setTimeout(() => dialogRef.current?.focus(), 0);
    return () => {
      disposed = true;
      unlisten?.();
      invokingElement.current?.focus();
    };
  }, [manager, open]);

  if (!open) return null;

  const busy = operation !== "idle";
  const installed = status?.state === "available";
  const progressPercent = progress && progress.totalBytes > 0
    ? Math.min(100, Math.round(
      (progress.completedBytes / progress.totalBytes) * 100,
    ))
    : undefined;

  const close = () => {
    if (!busy) onClose();
  };
  const acquire = async () => {
    if (!acknowledged || !status?.supportAvailable || busy || operationBlocker) {
      return;
    }
    setOperation("acquire");
    setError(null);
    try {
      setStatus(await manager.acquire());
    } catch (reason) {
      setError(errorMessage(reason));
      try {
        setStatus(await manager.status());
      } catch {
        // Preserve the actionable acquisition error.
      }
    } finally {
      setOperation("idle");
    }
  };
  const remove = async () => {
    if (!confirmRemoval || busy || operationBlocker) return;
    setOperation("remove");
    setError(null);
    try {
      setStatus(await manager.remove());
      setConfirmRemoval(false);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setOperation("idle");
    }
  };
  const relaunch = async () => {
    if (busy || operationBlocker) return;
    setOperation("relaunch");
    setError(null);
    try {
      await manager.relaunch();
    } catch (reason) {
      setError(errorMessage(reason));
      setOperation("idle");
    }
  };
  const openLink = async (linkId: DesktopScoreLinkId) => {
    try {
      await manager.openLink(linkId);
    } catch (reason) {
      setError(errorMessage(reason));
    }
  };

  return (
    <div
      className="score-model-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) close();
      }}
    >
      <section
        className="score-model-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="score-model-title"
        tabIndex={-1}
        ref={dialogRef}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault();
            close();
            return;
          }
          if (event.key !== "Tab") return;
          const focusable = Array.from(
            dialogRef.current?.querySelectorAll<HTMLElement>(
              "button:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex='-1'])",
            ) ?? [],
          );
          if (focusable.length === 0) return;
          const first = focusable[0];
          const last = focusable.at(-1)!;
          if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
          } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
          }
        }}
      >
        <div className="score-model-heading">
          <div>
            <p className="eyebrow">Optional research model</p>
            <h2 id="score-model-title">
              {status?.modelName ?? "Enable score generation"}
            </h2>
          </div>
          <button
            type="button"
            aria-label="Close research model dialog"
            disabled={busy}
            onClick={close}
          >
            ×
          </button>
        </div>

        {status === null && error === null && (
          <p role="status">Loading the signed acquisition notice…</p>
        )}
        {status === null && error !== null && (
          <p className="surface-feedback error" role="alert">{error}</p>
        )}
        {status && (
            <>
              <p className="score-model-purpose">{status.purpose}</p>
              <p className="score-model-notice">{status.notice}</p>
              <p>
                Downloaded Python source will run locally on this device. The
                source archive is {formatExactBytes(status.sourceBytes)} and
                the checkpoint is {formatExactBytes(status.checkpointBytes)}.
                The combined download is {formatBytes(status.downloadBytes)};
                the complete installed model needs about {formatBytes(
                  status.installedSpaceEstimateBytes,
                )}.
              </p>
              <div className="score-model-links" aria-label="Research model references">
                {([
                  ["repository", "Source repository"],
                  ["checkpoint", "Checkpoint release"],
                  ["paper", "Research paper"],
                  ["acquisition-record", "Atpiano acquisition record"],
                ] as const).map(([id, label]) => (
                  <button type="button" key={id} onClick={() => void openLink(id)}>
                    {label} ↗
                  </button>
                ))}
              </div>

              {!status.supportAvailable && (
                <p className="surface-feedback error" role="alert">
                  This build does not contain the signed score-support layer.
                  No model download can start.
                </p>
              )}
              {status.state === "invalid" && (
                <p className="surface-feedback error" role="alert">
                  {status.error ?? "The installed research model is invalid."}
                </p>
              )}
              {operationBlocker && (
                <p className="desktop-update-blocker" role="status">
                  {operationBlocker}
                </p>
              )}

              {!installed && status.state !== "invalid" && (
                <label className="score-model-acknowledgement">
                  <input
                    type="checkbox"
                    checked={acknowledged}
                    disabled={busy}
                    onChange={(event) => setAcknowledged(event.currentTarget.checked)}
                  />
                  <span>{status.acknowledgement}</span>
                </label>
              )}

              {progress && operation === "acquire" && (
                <div className="score-model-progress" role="status" aria-live="polite">
                  <span>{phaseLabels[progress.phase]}</span>
                  <progress max={100} value={progressPercent} />
                  <small>
                    {formatBytes(progress.completedBytes)} of {formatBytes(progress.totalBytes)}
                  </small>
                </div>
              )}

              {error && (
                <p className="surface-feedback error" role="alert">{error}</p>
              )}

              {installed && (
                <div className="score-model-installed" role="status">
                  <strong>Research model installed</strong>
                  <span>
                    {status.installedBytes
                      ? `${formatBytes(status.installedBytes)} installed locally. `
                      : ""}
                    Relaunch Atpiano to enable score generation.
                  </span>
                </div>
              )}

              {(installed || status.state === "invalid") && (
                <details className="score-model-provenance">
                  <summary>Installed model details</summary>
                  <dl>
                    <div><dt>Contract</dt><dd>{status.contractId}</dd></div>
                    <div><dt>Notice</dt><dd>{status.noticeVersion}</dd></div>
                    <div title={status.sourceCommit}>
                      <dt>Source commit</dt><dd>{shortIdentity(status.sourceCommit)}</dd>
                    </div>
                    <div title={status.checkpointSha256}>
                      <dt>Checkpoint SHA-256</dt>
                      <dd>{shortIdentity(status.checkpointSha256)}</dd>
                    </div>
                    <div><dt>Support layer</dt><dd>{status.supportLayerId}</dd></div>
                    <div><dt>Execution</dt><dd>{status.executionBackend}</dd></div>
                  </dl>
                </details>
              )}

              {(installed || status.state === "invalid") && (
                <label className="score-model-removal">
                  <input
                    type="checkbox"
                    checked={confirmRemoval}
                    disabled={busy}
                    onChange={(event) => setConfirmRemoval(event.currentTarget.checked)}
                  />
                  <span>
                    Remove the research model. Sessions and already generated
                    score artifacts will be preserved.
                  </span>
                </label>
              )}
            </>
          )}

        <div className="score-model-actions">
          {operation === "acquire" && (
            <button type="button" className="button secondary" onClick={() => void manager.cancel()}>
              Cancel download
            </button>
          )}
          {operation === "idle" && !installed && status?.state !== "invalid" && (
            <>
              <button type="button" className="button secondary" onClick={close}>
                Cancel
              </button>
              <button
                type="button"
                className="button primary"
                disabled={
                  !acknowledged ||
                  !status?.supportAvailable ||
                  operationBlocker !== null
                }
                onClick={() => void acquire()}
              >
                Download research model
              </button>
            </>
          )}
          {operation === "idle" && (installed || status?.state === "invalid") && (
            <>
              <button
                type="button"
                className="button secondary"
                disabled={!confirmRemoval || operationBlocker !== null}
                onClick={() => void remove()}
              >
                Remove research model
              </button>
              {installed && (
                <button
                  type="button"
                  className="button primary"
                  disabled={operationBlocker !== null}
                  onClick={() => void relaunch()}
                >
                  Relaunch to enable scores
                </button>
              )}
            </>
          )}
          {operation === "remove" && <span role="status">Removing local model…</span>}
          {operation === "relaunch" && <span role="status">Relaunching Atpiano…</span>}
        </div>
      </section>
    </div>
  );
}
