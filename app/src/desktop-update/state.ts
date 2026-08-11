export type CheckReason = "startup" | "periodic" | "manual";

export type UpdaterState =
  | { phase: "idle"; lastReason?: Exclude<CheckReason, "manual"> }
  | { phase: "checking"; reason: CheckReason }
  | { phase: "up-to-date"; reason: "manual" }
  | {
      phase: "available";
      version: string;
      notes?: string | undefined;
      reason: CheckReason;
      downloaded: boolean;
    }
  | { phase: "manual-install"; packageLabel: string }
  | {
      phase: "downloading";
      version: string;
      downloadedBytes: number;
      totalBytes?: number | undefined;
    }
  | { phase: "installing"; version: string }
  | {
      phase: "error";
      operation: "check" | "install";
      message: string;
      version?: string;
    };

export function progressPercent(state: UpdaterState): number | undefined {
  if (
    state.phase !== "downloading" ||
    !state.totalBytes ||
    state.totalBytes <= 0
  ) {
    return undefined;
  }
  return Math.min(
    100,
    Math.round((state.downloadedBytes / state.totalBytes) * 100),
  );
}
