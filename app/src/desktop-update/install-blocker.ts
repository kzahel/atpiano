import type { CapturePhase } from "../state/workspace-store.js";

interface UpdateActivity {
  readonly capturePhase: CapturePhase;
  readonly sessionStatuses: readonly string[];
  readonly scoreJobStatus: string | null | undefined;
}

export function updateInstallBlocker({
  capturePhase,
  sessionStatuses,
  scoreJobStatus,
}: UpdateActivity): string | null {
  if (["requesting", "warming", "recording", "stopping"].includes(capturePhase)) {
    return "Finish the current recording before installing an update.";
  }
  if (sessionStatuses.some((status) => status === "active" || status === "stopping")) {
    return "Wait for the current performance to finish settling before installing.";
  }
  if (scoreJobStatus === "pending" || scoreJobStatus === "running") {
    return "Wait for score generation to finish before installing.";
  }
  return null;
}
