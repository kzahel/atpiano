import {
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

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

  it("publishes segment transitions, completion, and a fresh restart", async () => {
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
    render(
      <PlaybackProvider
        sessionId="session-1"
        sources={[
          {
            artifactId: "audio-1",
            url: "data:audio/wav;base64,UklGRg==",
            startSample: 0,
            endSample: 48_000,
          },
          {
            artifactId: "audio-2",
            url: "data:audio/wav;base64,UklGRg==",
            startSample: 48_000,
            endSample: 96_000,
          },
        ]}
        totalSamples={96_000}
        sampleRateHz={48_000}
      >
        <AudioPlayback unavailableReason="Unavailable" />
      </PlaybackProvider>,
    );
    fireEvent.click(screen.getByRole("button", {
      name: "Play recorded audio",
    }));
    usePlaybackStore.getState().detachScore();
    const audio = document.querySelector("audio")!;

    fireEvent.ended(audio);

    await waitFor(() =>
      expect(usePlaybackStore.getState()).toMatchObject({
        status: "playing",
        positionSample: 48_000,
        scoreFollow: "detached",
      })
    );

    fireEvent.ended(audio);

    expect(usePlaybackStore.getState()).toMatchObject({
      status: "ended",
      positionSample: 96_000,
      scoreFollow: "detached",
    });

    fireEvent.click(screen.getByRole("button", {
      name: "Play recorded audio",
    }));

    await waitFor(() =>
      expect(usePlaybackStore.getState()).toMatchObject({
        status: "playing",
        positionSample: 0,
        scoreFollow: "following",
      })
    );
  });

  it("publishes media failure and resets for another source", async () => {
    const view = render(
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
    usePlaybackStore.getState().detachScore();

    fireEvent.error(document.querySelector("audio")!);

    expect(usePlaybackStore.getState()).toMatchObject({
      status: "error",
      error: "Recorded audio could not be played.",
      scoreFollow: "detached",
    });

    view.rerender(
      <PlaybackProvider
        sessionId="session-2"
        sources={[
          {
            artifactId: "audio-2",
            url: "data:audio/wav;base64,UklGRg==",
            startSample: 0,
            endSample: 48_000,
          },
        ]}
        totalSamples={48_000}
        sampleRateHz={48_000}
      >
        <AudioPlayback unavailableReason="Unavailable" />
      </PlaybackProvider>,
    );

    await waitFor(() =>
      expect(usePlaybackStore.getState()).toMatchObject({
        sessionId: "session-2",
        sourceKey: "audio-2",
        status: "idle",
        positionSample: 0,
        scoreFollow: "following",
        error: null,
      })
    );
  });
});
