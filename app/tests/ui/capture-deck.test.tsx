import { fireEvent, render, screen } from "@testing-library/react";
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
  capture_sources: ["microphone", "upload", "replay"],
  correction: {
    configured_mode: "delayed",
    default_mode: "delayed",
    reason: "test fixture policy",
    backend_profile_path: null,
    backend_profile_status: "not-configured",
    backend_profile_id: null,
    backend_profile_recommendation: null,
  },
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
        onImport={vi.fn()}
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
      screen.getByRole("button", { name: "Import recording" }),
    ).toBeTruthy();
    expect(
      screen.getByText(/import a WAV or MP3 recording/),
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
        onImport={vi.fn()}
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

  it("warns when automatic correction lacks a measured profile", () => {
    render(
      <CaptureDeck
        capabilities={{
          ...localCapabilities,
          correction: {
            configured_mode: "auto",
            default_mode: "after-stop",
            reason: "backend profile is missing",
            backend_profile_path: "results/backend-profile/backend-profile.json",
            backend_profile_status: "missing",
            backend_profile_id: null,
            backend_profile_recommendation: null,
          },
        }}
        captureState={{
          phase: "idle",
          operationId: null,
          capture: null,
          error: null,
        }}
        activeSession={undefined}
        onMicrophone={vi.fn()}
        onImport={vi.fn()}
        onReplay={vi.fn()}
        onStop={vi.fn()}
        onDismissError={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("alert").textContent,
    ).toMatch(/Background settling profile unavailable/);
    expect(screen.getByRole("alert").textContent).toMatch(/after Stop/);
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
        onImport={vi.fn()}
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

  it("passes the chosen recording file without exposing fixture language", () => {
    const onImport = vi.fn();
    const view = render(
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
        onImport={onImport}
        onReplay={vi.fn()}
        onStop={vi.fn()}
        onDismissError={vi.fn()}
      />,
    );
    const file = new File(["audio"], "Nocturne.mp3", {
      type: "audio/mpeg",
    });

    fireEvent.change(
      screen.getByLabelText("Choose WAV or MP3 recording"),
      { target: { files: [file] } },
    );

    expect(onImport).toHaveBeenCalledWith(file);
    expect(screen.queryByText(/fixture replay/i)).toBeNull();
    view.rerender(
      <CaptureDeck
        capabilities={localCapabilities}
        captureState={{
          phase: "requesting",
          operationId: "import-1",
          capture: null,
          error: null,
        }}
        activeSession={undefined}
        onMicrophone={vi.fn()}
        onImport={onImport}
        onReplay={vi.fn()}
        onStop={vi.fn()}
        onDismissError={vi.fn()}
      />,
    );
    expect(screen.getByText("Uploading Nocturne.mp3…")).toBeTruthy();
    expect(
      screen.getByRole("progressbar", {
        name: "Recording upload progress",
      }),
    ).toBeTruthy();
  });
});
