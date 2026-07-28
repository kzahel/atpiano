import {
  fireEvent,
  render,
  waitFor,
} from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  MusicXmlScore,
  scorePanelFollowTop,
} from "../../src/components/musicxml-score.js";
import type { ScoreAlignment } from "../../src/lib/score-alignment.js";
import {
  resetPlaybackStore,
  usePlaybackStore,
} from "../../src/state/playback-store.js";

const alignment: ScoreAlignment = {
  schema_version: "atpiano.score-alignment.v2",
  session_id: "session-1",
  sample_rate_hz: 48_000,
  musicxml: { sha256: "a".repeat(64) },
  rows: [
    {
      source_index: 0,
      event_id: "opening-chord-c",
      pitch: 60,
      onset_sample: 100,
      offset_sample: 150,
      status: "mapped",
      score_time_quarters: { numerator: 0, denominator: 1 },
    },
    {
      source_index: 1,
      event_id: "later-chord-c",
      pitch: 60,
      onset_sample: 200,
      offset_sample: 250,
      status: "mapped",
      score_time_quarters: { numerator: 4, denominator: 1 },
    },
  ],
};

describe("rendered score playback", () => {
  beforeEach(() => {
    resetPlaybackStore();
  });

  it("moves only when the cursor leaves the visible comfort band", () => {
    expect(scorePanelFollowTop({
      viewportTop: 100,
      viewportHeight: 200,
      scrollTop: 300,
      scrollHeight: 1_000,
      cursorTop: 180,
      cursorHeight: 20,
    })).toBeNull();
    expect(scorePanelFollowTop({
      viewportTop: 100,
      viewportHeight: 200,
      scrollTop: 0,
      scrollHeight: 1_000,
      cursorTop: 700,
      cursorHeight: 20,
    })).toBe(510);
  });

  it("restores notehead highlights across movement and coverage loss", async () => {
    const view = render(
      <MusicXmlScore
        xml="<score-partwise />"
        alignment={alignment}
        inspectionSample={100}
        scoreHorizonSample={300}
      />,
    );

    await waitFor(() =>
      expect(
        view.container.querySelectorAll(
          '[data-cursor-index="0"].playback-note-active',
        ),
      ).toHaveLength(2)
    );

    view.rerender(
      <MusicXmlScore
        xml="<score-partwise />"
        alignment={alignment}
        inspectionSample={200}
        scoreHorizonSample={300}
      />,
    );
    await waitFor(() =>
      expect(
        view.container.querySelectorAll(
          '[data-cursor-index="1"].playback-note-active',
        ),
      ).toHaveLength(2)
    );
    expect(
      view.container.querySelectorAll(
        '[data-cursor-index="0"].playback-note-active',
      ),
    ).toHaveLength(0);

    view.rerender(
      <MusicXmlScore
        xml="<score-partwise />"
        alignment={alignment}
        inspectionSample={100}
        scoreHorizonSample={300}
      />,
    );
    await waitFor(() =>
      expect(
        view.container.querySelectorAll(
          '[data-cursor-index="0"].playback-note-active',
        ),
      ).toHaveLength(2)
    );

    view.rerender(
      <MusicXmlScore
        xml="<score-partwise />"
        alignment={alignment}
        inspectionSample={301}
        scoreHorizonSample={300}
      />,
    );
    await waitFor(() =>
      expect(
        view.container.querySelectorAll(".playback-note-active"),
      ).toHaveLength(0)
    );
  });

  it("keeps automatic follow inside the panel and detaches on scroll intent", async () => {
    usePlaybackStore.getState().configure({
      sessionId: "session-1",
      sourceKey: "audio-1",
      available: true,
      totalSamples: 300,
      sampleRateHz: 48_000,
    });
    usePlaybackStore.getState().setStatus("playing");
    const scrollTo = vi.spyOn(window, "scrollTo");
    const view = render(
      <MusicXmlScore
        xml="<score-partwise />"
        alignment={alignment}
        inspectionSample={100}
        scoreHorizonSample={300}
      />,
    );
    await waitFor(() =>
      expect(
        view.container.querySelector('[data-cursor-index="0"]'),
      ).toBeTruthy()
    );
    const panel = view.container.querySelector(".score-paper")!;
    const cursor = view.container.querySelector("img")!;
    Object.defineProperties(panel, {
      clientHeight: { configurable: true, value: 200 },
      scrollHeight: { configurable: true, value: 1_000 },
    });
    vi.spyOn(panel, "getBoundingClientRect").mockReturnValue({
      top: 100,
      bottom: 300,
      left: 0,
      right: 500,
      width: 500,
      height: 200,
      x: 0,
      y: 100,
      toJSON: () => ({}),
    });
    vi.spyOn(cursor, "getBoundingClientRect").mockImplementation(() => ({
      top: 700 - panel.scrollTop,
      bottom: 720 - panel.scrollTop,
      left: 0,
      right: 10,
      width: 10,
      height: 20,
      x: 0,
      y: 700 - panel.scrollTop,
      toJSON: () => ({}),
    }));

    view.rerender(
      <MusicXmlScore
        xml="<score-partwise />"
        alignment={alignment}
        inspectionSample={200}
        scoreHorizonSample={300}
      />,
    );
    await waitFor(() => expect(panel.scrollTop).toBe(510));
    fireEvent.scroll(panel);
    expect(usePlaybackStore.getState().scoreFollow).toBe("following");
    expect(scrollTo).not.toHaveBeenCalled();

    fireEvent.wheel(window);
    expect(usePlaybackStore.getState().scoreFollow).toBe("detached");
  });
});
