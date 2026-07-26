import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CaptureDeck } from "../../src/components/capture-deck.js";
import type { Capture } from "../../src/runtime/atpiano-runtime.js";

const capture: Capture = {
  schema_version: "atpiano.contract.v1",
  workspace_id: "local",
  session_id: "session-stopping",
  capture_id: "capture-stopping",
  status: "stopping",
  source: "microphone",
  sample_rate_hz: 48_000,
  accepted_through_sample: 96_000,
  started_at: "2026-07-26T12:00:00Z",
  stopped_at: null,
  error_id: null,
};

describe("capture deck", () => {
  it("keeps Stop visible but disabled while final notes settle", () => {
    render(
      <CaptureDeck
        capabilities={undefined}
        captureState={{
          phase: "stopping",
          operationId: "stop-1",
          capture,
          error: null,
        }}
        activeSession={undefined}
        onMicrophone={vi.fn()}
        onReplay={vi.fn()}
        onStop={vi.fn()}
        onDismissError={vi.fn()}
      />,
    );

    expect(
      (screen.getByRole("button", { name: "Settling…" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    expect(screen.getByText("Closing microphone capture…")).toBeTruthy();
  });
});
