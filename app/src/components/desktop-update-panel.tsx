import { invoke } from "@tauri-apps/api/core";
import { useCallback, useMemo, useState } from "react";

import { progressPercent, type UpdaterState } from "../desktop-update/state.js";
import { useDesktopUpdater } from "../desktop-update/use-desktop-updater.js";
import type { DesktopReleaseInfo } from "../runtime/desktop-runtime.js";

function shortIdentity(value: string): string {
  return value.length > 20 ? `${value.slice(0, 10)}…${value.slice(-7)}` : value;
}

function statusCopy(state: UpdaterState): { title: string; body: string } {
  switch (state.phase) {
    case "idle":
      return {
        title: "Desktop updates",
        body: state.lastReason
          ? `The silent ${state.lastReason} check found no update.`
          : "Atpiano checks quietly after startup and once each day.",
      };
    case "checking":
      return {
        title: "Checking for updates",
        body: "Looking for a signed compatible desktop release.",
      };
    case "up-to-date":
      return {
        title: "Atpiano is up to date",
        body: "No newer compatible desktop release is available.",
      };
    case "available":
      return {
        title: `Atpiano ${state.version} is available`,
        body: state.downloaded
          ? "The signed update is downloaded and ready to install."
          : "Review the update, then choose Install and relaunch.",
      };
    case "manual-install":
      return {
        title: "Use the original package channel",
        body: `${state.packageLabel} installations are not replaced in-app.`,
      };
    case "downloading":
      return {
        title: `Downloading Atpiano ${state.version}`,
        body: state.totalBytes
          ? `${Math.round(state.downloadedBytes / 1_048_576)} of ${Math.round(state.totalBytes / 1_048_576)} MB`
          : `${Math.round(state.downloadedBytes / 1_048_576)} MB received`,
      };
    case "installing":
      return {
        title: `Installing Atpiano ${state.version}`,
        body: "The local engine is stopping. Atpiano will relaunch after replacement.",
      };
    case "error":
      return {
        title: state.operation === "check"
          ? "Update check failed"
          : "Update installation failed",
        body: state.message,
      };
  }
}

export function DesktopUpdatePanel({
  releaseInfo,
  installBlocker,
  onManageScoreModel,
}: {
  readonly releaseInfo: DesktopReleaseInfo;
  readonly installBlocker: string | null;
  readonly onManageScoreModel?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const prepareInstall = useCallback(
    () => invoke<void>("desktop_prepare_update_install"),
    [],
  );
  const resumeAfterFailure = useCallback(
    () => invoke<void>("desktop_resume_after_update_failure"),
    [],
  );
  const updater = useDesktopUpdater({
    enabled: true,
    packageType: releaseInfo.packageType,
    installBlocker,
    prepareInstall,
    resumeAfterFailure,
  });
  const copy = useMemo(() => statusCopy(updater.state), [updater.state]);
  const progress = progressPercent(updater.state);
  const busy = updater.state.phase === "checking" ||
    updater.state.phase === "downloading" ||
    updater.state.phase === "installing";
  const canInstall = updater.state.phase === "available" ||
    (updater.state.phase === "error" && updater.state.operation === "install");
  const attention = updater.state.phase === "available" ||
    updater.state.phase === "error";

  return (
    <div className="desktop-update-control">
      <button
        className={`desktop-update-trigger${attention ? " attention" : ""}`}
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <span aria-hidden="true">{attention ? "●" : "○"}</span>
        Atpiano {releaseInfo.appVersion}
      </button>
      {open && (
        <section className="desktop-update-panel" aria-label="Desktop updates">
          <div className="desktop-update-heading">
            <div>
              <p className="eyebrow">Signed desktop release</p>
              <h2>{copy.title}</h2>
            </div>
            <button type="button" onClick={() => setOpen(false)} aria-label="Close updates">
              ×
            </button>
          </div>
          <p className="desktop-update-copy">{copy.body}</p>
          {canInstall && installBlocker && (
            <p className="desktop-update-blocker" role="status">
              {installBlocker}
            </p>
          )}
          {updater.state.phase === "downloading" && (
            <progress
              max={100}
              value={progress}
              aria-label="Desktop update download progress"
            />
          )}
          {updater.state.phase === "available" && updater.state.notes && (
            <p className="desktop-update-notes">{updater.state.notes}</p>
          )}
          <div className="desktop-update-actions">
            <button
              className="button primary"
              type="button"
              disabled={busy || (canInstall && installBlocker !== null)}
              onClick={() => void (
                canInstall ? updater.install() : updater.check("manual")
              )}
            >
              {canInstall ? "Install and relaunch" : busy ? "Working…" : "Check now"}
            </button>
            {updater.state.phase !== "idle" && !busy && (
              <button className="button secondary" type="button" onClick={updater.dismiss}>
                Dismiss
              </button>
            )}
          </div>
          {onManageScoreModel && (
            <button
              className="desktop-score-manage"
              type="button"
              onClick={() => {
                setOpen(false);
                onManageScoreModel();
              }}
            >
              Manage research score model
            </button>
          )}
          <details className="desktop-release-identities">
            <summary>Installed build details</summary>
            <dl>
              <div><dt>App</dt><dd>{releaseInfo.appVersion}</dd></div>
              <div title={releaseInfo.webClientBuildId}>
                <dt>Web client</dt><dd>{shortIdentity(releaseInfo.webClientBuildId)}</dd>
              </div>
              <div><dt>Python sidecar</dt><dd>{releaseInfo.sidecarVersion}</dd></div>
              <div><dt>Model pack</dt><dd>{releaseInfo.modelPackId}</dd></div>
              <div title={releaseInfo.modelPackSha256}>
                <dt>Model hash</dt><dd>{shortIdentity(releaseInfo.modelPackSha256)}</dd>
              </div>
              <div title={releaseInfo.installationId}>
                <dt>Install ID</dt><dd>{shortIdentity(releaseInfo.installationId)}</dd>
              </div>
              <div><dt>Target</dt><dd>{releaseInfo.platform} / {releaseInfo.architecture}</dd></div>
            </dl>
          </details>
        </section>
      )}
    </div>
  );
}
