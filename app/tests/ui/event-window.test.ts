import { describe, expect, it } from "vitest";

import { eventWindow, liveFrameCount } from "../../src/lib/event-window.js";

describe("live event window", () => {
  it("follows the advancing audio horizon before the session snapshot updates", () => {
    expect(liveFrameCount(0, 96_000)).toBe(96_000);
    expect(eventWindow(0, 96_000, 5_760_000)).toEqual({
      startSample: 0,
      endSample: 96_000,
    });
  });

  it("keeps a bounded tail for long stored or active sessions", () => {
    expect(eventWindow(8_000_000, 8_100_000, 5_760_000)).toEqual({
      startSample: 2_340_000,
      endSample: 8_100_000,
    });
  });
});
