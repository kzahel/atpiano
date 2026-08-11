import { relaunch } from "@tauri-apps/plugin-process";
import {
  check as checkForTauriUpdate,
  type DownloadEvent,
  type Update,
} from "@tauri-apps/plugin-updater";
import { useCallback, useEffect, useRef, useState } from "react";

import { installPolicy } from "./policy.js";
import { scheduleAutomaticChecks } from "./schedule.js";
import type { CheckReason, UpdaterState } from "./state.js";

const UPDATE_CHECK_TIMEOUT_MS = 20_000;
const RECOVERED_INSTALL_ERROR = "atpiano:desktop-update-install-error";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function initialState(): UpdaterState {
  try {
    const message = window.sessionStorage.getItem(RECOVERED_INSTALL_ERROR);
    if (message) {
      window.sessionStorage.removeItem(RECOVERED_INSTALL_ERROR);
      return { phase: "error", operation: "install", message };
    }
  } catch {
    // Session storage is a recovery aid, not a prerequisite for the updater.
  }
  return { phase: "idle" };
}

interface DesktopUpdaterOptions {
  readonly enabled: boolean;
  readonly packageType: string;
  readonly installBlocker: string | null;
  readonly prepareInstall: () => Promise<void>;
  readonly resumeAfterFailure: () => Promise<void>;
}

export interface DesktopUpdater {
  readonly state: UpdaterState;
  check(reason?: CheckReason): Promise<void>;
  install(): Promise<void>;
  dismiss(): void;
}

export function useDesktopUpdater({
  enabled,
  packageType,
  installBlocker,
  prepareInstall,
  resumeAfterFailure,
}: DesktopUpdaterOptions): DesktopUpdater {
  const [state, setState] = useState<UpdaterState>(initialState);
  const updateRef = useRef<Update | null>(null);
  const checkRef = useRef<Promise<void> | null>(null);
  const downloadedRef = useRef(false);
  const blockerRef = useRef(installBlocker);
  const prepareRef = useRef(prepareInstall);
  const resumeRef = useRef(resumeAfterFailure);
  blockerRef.current = installBlocker;
  prepareRef.current = prepareInstall;
  resumeRef.current = resumeAfterFailure;

  const closeUpdate = useCallback(() => {
    const update = updateRef.current;
    updateRef.current = null;
    downloadedRef.current = false;
    if (update) void update.close().catch(console.error);
  }, []);

  const check = useCallback(async (reason: CheckReason = "manual") => {
    if (!enabled) return;
    if (checkRef.current) {
      await checkRef.current;
      return;
    }
    const request = (async () => {
      if (reason === "manual") setState({ phase: "checking", reason });
      try {
        const policy = installPolicy(packageType);
        if (!policy.canInstallInApp) {
          if (reason === "manual") {
            setState({
              phase: "manual-install",
              packageLabel: policy.packageLabel,
            });
          }
          return;
        }
        if (reason !== "manual" && updateRef.current) return;
        closeUpdate();
        const update = await checkForTauriUpdate({
          headers: { "X-Check-Reason": reason },
          timeout: UPDATE_CHECK_TIMEOUT_MS,
        });
        if (update) {
          updateRef.current = update;
          setState({
            phase: "available",
            version: update.version,
            notes: update.body,
            reason,
            downloaded: false,
          });
        } else if (reason === "manual") {
          setState({ phase: "up-to-date", reason });
        } else {
          setState({ phase: "idle", lastReason: reason });
        }
      } catch (error) {
        if (reason === "manual") {
          setState({
            phase: "error",
            operation: "check",
            message: errorMessage(error),
          });
        } else {
          console.error(`Automatic ${reason} update check failed:`, error);
        }
      } finally {
        checkRef.current = null;
      }
    })();
    checkRef.current = request;
    await request;
  }, [closeUpdate, enabled, packageType]);

  const install = useCallback(async () => {
    const update = updateRef.current;
    if (!update) {
      await check("manual");
      return;
    }
    const version = update.version;
    if (blockerRef.current) {
      setState({
        phase: "available",
        version,
        notes: update.body,
        reason: "manual",
        downloaded: downloadedRef.current,
      });
      return;
    }

    let prepared = false;
    try {
      if (!downloadedRef.current) {
        let downloadedBytes = 0;
        let totalBytes: number | undefined;
        setState({ phase: "downloading", version, downloadedBytes });
        await update.download((event: DownloadEvent) => {
          if (event.event === "Started") {
            downloadedBytes = 0;
            totalBytes = event.data.contentLength;
          } else if (event.event === "Progress") {
            downloadedBytes += event.data.chunkLength;
          } else {
            downloadedRef.current = true;
          }
          setState({
            phase: "downloading",
            version,
            downloadedBytes,
            totalBytes,
          });
        });
        downloadedRef.current = true;
      }

      if (blockerRef.current) {
        setState({
          phase: "available",
          version,
          notes: update.body,
          reason: "manual",
          downloaded: true,
        });
        return;
      }

      setState({ phase: "installing", version });
      await prepareRef.current();
      prepared = true;
      await update.install();
      await relaunch();
    } catch (error) {
      const message = errorMessage(error);
      if (!prepared) {
        setState({ phase: "error", operation: "install", message, version });
        return;
      }
      try {
        await resumeRef.current();
        window.sessionStorage.setItem(RECOVERED_INSTALL_ERROR, message);
        window.location.reload();
      } catch (recoveryError) {
        setState({
          phase: "error",
          operation: "install",
          message: `${message} The local engine also could not restart: ${errorMessage(recoveryError)}`,
          version,
        });
      }
    }
  }, [check]);

  const dismiss = useCallback(() => {
    closeUpdate();
    setState({ phase: "idle" });
  }, [closeUpdate]);

  useEffect(() => {
    if (!enabled) return;
    return scheduleAutomaticChecks((reason) => void check(reason));
  }, [check, enabled]);
  useEffect(() => closeUpdate, [closeUpdate]);

  return { state, check, install, dismiss };
}
