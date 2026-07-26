import { create } from "zustand";

import type { Capture } from "../runtime/atpiano-runtime.js";

export type CapturePhase =
  | "idle"
  | "requesting"
  | "warming"
  | "recording"
  | "stopping"
  | "failed";

export interface CaptureState {
  readonly phase: CapturePhase;
  readonly operationId: string | null;
  readonly capture: Capture | null;
  readonly error: string | null;
}

interface WorkspaceState {
  selectedSessionId: string | null;
  newIntent: boolean;
  showRoll: boolean;
  showKeyboard: boolean;
  showScore: boolean;
  followHead: boolean;
  inspectionSample: number | null;
  captureState: CaptureState;
  selectSession(sessionId: string): void;
  beginNew(): void;
  toggleView(view: "roll" | "keyboard" | "score"): void;
  setFollowHead(value: boolean): void;
  setInspectionSample(value: number | null): void;
  beginCapture(operationId: string): void;
  warmCapture(operationId: string): void;
  recordCapture(operationId: string, capture: Capture): void;
  stopCapture(operationId: string): void;
  completeCapture(operationId: string): void;
  failCapture(operationId: string, error: unknown): void;
  resetCapture(): void;
}

const idleCapture: CaptureState = {
  phase: "idle",
  operationId: null,
  capture: null,
  error: null,
};

function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  selectedSessionId: null,
  newIntent: false,
  showRoll: true,
  showKeyboard: true,
  showScore: true,
  followHead: true,
  inspectionSample: null,
  captureState: idleCapture,
  selectSession: (sessionId) =>
    set({
      selectedSessionId: sessionId,
      newIntent: false,
      inspectionSample: null,
    }),
  beginNew: () =>
    set({
      selectedSessionId: null,
      newIntent: true,
      inspectionSample: null,
    }),
  toggleView: (view) =>
    set((state) => {
      if (view === "roll") return { showRoll: !state.showRoll };
      if (view === "keyboard") return { showKeyboard: !state.showKeyboard };
      return { showScore: !state.showScore };
    }),
  setFollowHead: (followHead) => set({ followHead }),
  setInspectionSample: (inspectionSample) => set({ inspectionSample }),
  beginCapture: (operationId) =>
    set({
      captureState: {
        phase: "requesting",
        operationId,
        capture: null,
        error: null,
      },
    }),
  warmCapture: (operationId) =>
    set((state) =>
      state.captureState.operationId === operationId
        ? { captureState: { ...state.captureState, phase: "warming" } }
        : {},
    ),
  recordCapture: (operationId, capture) =>
    set((state) =>
      state.captureState.operationId === operationId
        ? {
            captureState: {
              phase: "recording",
              operationId,
              capture,
              error: null,
            },
            selectedSessionId: capture.session_id,
            newIntent: false,
          }
        : {},
    ),
  stopCapture: (operationId) =>
    set((state) =>
      state.captureState.operationId === operationId
        ? { captureState: { ...state.captureState, phase: "stopping" } }
        : {},
    ),
  completeCapture: (operationId) =>
    set((state) =>
      state.captureState.operationId === operationId
        ? { captureState: idleCapture }
        : {},
    ),
  failCapture: (operationId, error) =>
    set((state) =>
      state.captureState.operationId === operationId
        ? {
            captureState: {
              ...state.captureState,
              phase: "failed",
              error: message(error),
            },
          }
        : {},
    ),
  resetCapture: () => set({ captureState: idleCapture }),
}));
