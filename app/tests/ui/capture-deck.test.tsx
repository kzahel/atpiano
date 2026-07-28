import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CaptureDeck } from "../../src/components/capture-deck.js";
import type {
  Capture,
  RuntimeCapabilities,
} from "../../src/runtime/atpiano-runtime.js";

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

const localCapabilities: RuntimeCapabilities = {
  schema_version: "atpiano.contract.v1",
  runtime_mode: "local",
  supported_schema_versions: ["atpiano.contract.v1"],
  supported_pcm_protocol_versions: ["atpiano.pcm.v1"],
  capture_sources: ["microphone", "replay"],
  score_available: true,
  recoverable_delete: true,
  max_pcm_block_frames: 1_048_576,
  max_event_range_samples: 5_760_000,
};

describe("capture deck", () => {
  it("keeps deterministic replay out of the player-facing runtime", () => {
    render(
      <CaptureDeck
        capabilities={localCapabilities}
        captureState={{
          phase: "idle",
          operationId: null,
          capture: null,
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
      screen.queryByRole("button", { name: "Run test recording" }),
    ).toBeNull();
    expect(screen.queryByText(/deterministic/)).toBeNull();
    expect(
      screen.getByText(/Start a new performance using your piano/),
    ).toBeTruthy();
  });

  it("retains deterministic replay in explicit fixture mode", () => {
    render(
      <CaptureDeck
        capabilities={{ ...localCapabilities, runtime_mode: "fixture" }}
        captureState={{
          phase: "idle",
          operationId: null,
          capture: null,
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
      screen.getByRole("button", { name: "Run test recording" }),
    ).toBeTruthy();
    expect(screen.getByText(/deterministic test recording/)).toBeTruthy();
  });

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
