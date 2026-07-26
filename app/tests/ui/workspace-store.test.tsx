import { beforeEach, describe, expect, it } from "vitest";

import type { Capture } from "../../src/runtime/atpiano-runtime.js";
import { useWorkspaceStore } from "../../src/state/workspace-store.js";

const capture: Capture = {
  schema_version: "atpiano.contract.v1",
  workspace_id: "local",
  session_id: "session-current",
  capture_id: "capture-current",
  status: "recording",
  source: "microphone",
  sample_rate_hz: 48_000,
  accepted_through_sample: 0,
  started_at: "2026-07-26T10:00:00Z",
  stopped_at: null,
  error_id: null,
};

describe("workspace state", () => {
  beforeEach(() => {
    useWorkspaceStore.setState({
      selectedSessionId: null,
      newIntent: false,
      showRoll: true,
      showKeyboard: true,
      showScore: true,
      inspectionSample: null,
      captureState: {
        phase: "idle",
        operationId: null,
        capture: null,
        error: null,
      },
    });
  });

  it("keeps New intent unpersisted until capture identifies a session", () => {
    useWorkspaceStore.getState().beginNew();

    expect(useWorkspaceStore.getState().newIntent).toBe(true);
    expect(useWorkspaceStore.getState().selectedSessionId).toBeNull();

    useWorkspaceStore.getState().beginCapture("request-1");
    useWorkspaceStore.getState().recordCapture("request-1", capture);

    expect(useWorkspaceStore.getState().newIntent).toBe(false);
    expect(useWorkspaceStore.getState().selectedSessionId).toBe("session-current");
  });

  it("rejects a late completion from an earlier capture intent", () => {
    useWorkspaceStore.getState().beginCapture("request-old");
    useWorkspaceStore.getState().beginCapture("request-current");
    useWorkspaceStore.getState().recordCapture("request-old", capture);

    expect(useWorkspaceStore.getState().captureState.phase).toBe("requesting");
    expect(useWorkspaceStore.getState().captureState.operationId).toBe(
      "request-current",
    );
    expect(useWorkspaceStore.getState().selectedSessionId).toBeNull();
  });

  it("keeps view toggles independent", () => {
    useWorkspaceStore.getState().toggleView("roll");

    expect(useWorkspaceStore.getState().showRoll).toBe(false);
    expect(useWorkspaceStore.getState().showKeyboard).toBe(true);
    expect(useWorkspaceStore.getState().showScore).toBe(true);
  });
});
