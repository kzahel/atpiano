import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { AudioPlayback } from "../../src/components/audio-playback.js";
import { PlaybackProvider } from "../../src/components/playback-provider.js";
import {
  resetPlaybackStore,
  usePlaybackStore,
} from "../../src/state/playback-store.js";
import { useWorkspaceStore } from "../../src/state/workspace-store.js";

describe("recorded audio playback", () => {
  beforeEach(() => {
    resetPlaybackStore();
    useWorkspaceStore.setState({ inspectionSample: null });
  });

  it("maps the session scrubber to the shared inspection sample", () => {
    render(
      <PlaybackProvider
        sessionId="session-1"
        sources={[
          {
            artifactId: "audio-1",
            url: "data:audio/wav;base64,UklGRg==",
            startSample: 0,
            endSample: 96_000,
          },
        ]}
        totalSamples={96_000}
        sampleRateHz={48_000}
      >
        <AudioPlayback unavailableReason="Unavailable" />
      </PlaybackProvider>,
    );

    fireEvent.change(screen.getByRole("slider"), {
      target: { value: "48_000" },
    });

    expect(useWorkspaceStore.getState().inspectionSample).toBe(48_000);
    expect(usePlaybackStore.getState().positionSample).toBe(48_000);
    expect(
      screen.getByText("00:01.0", { selector: "output", exact: false }),
    ).toBeTruthy();
  });
});
