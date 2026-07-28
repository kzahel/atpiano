import { beforeEach, describe, expect, it } from "vitest";

import {
  resetPlaybackStore,
  usePlaybackStore,
} from "../../src/state/playback-store.js";

describe("selected-session playback state", () => {
  beforeEach(resetPlaybackStore);

  it("retains user detachment for one source and resets for another", () => {
    const configuration = {
      sessionId: "session-1",
      sourceKey: "audio-1",
      available: true,
      totalSamples: 96_000,
      sampleRateHz: 48_000,
    };
    usePlaybackStore.getState().configure(configuration);
    usePlaybackStore.getState().setStatus("playing");
    usePlaybackStore.getState().setPosition(48_000);
    usePlaybackStore.getState().detachScore();

    usePlaybackStore.getState().configure({
      ...configuration,
      totalSamples: 120_000,
    });
    expect(usePlaybackStore.getState()).toMatchObject({
      sessionId: "session-1",
      status: "playing",
      positionSample: 48_000,
      totalSamples: 120_000,
      scoreFollow: "detached",
    });

    usePlaybackStore.getState().configure({
      ...configuration,
      sessionId: "session-2",
      sourceKey: "audio-2",
    });
    expect(usePlaybackStore.getState()).toMatchObject({
      sessionId: "session-2",
      status: "idle",
      positionSample: 0,
      scoreFollow: "following",
      error: null,
    });
  });

  it("publishes media errors without changing follow intent", () => {
    usePlaybackStore.getState().configure({
      sessionId: "session-1",
      sourceKey: "audio-1",
      available: true,
      totalSamples: 96_000,
      sampleRateHz: 48_000,
    });
    usePlaybackStore.getState().detachScore();
    usePlaybackStore.getState().setError("decode failed");

    expect(usePlaybackStore.getState()).toMatchObject({
      status: "error",
      error: "decode failed",
      scoreFollow: "detached",
    });
  });
});
