import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AudioPlayback } from "../../src/components/audio-playback.js";

describe("recorded audio playback", () => {
  it("maps the session scrubber to the shared inspection sample", () => {
    const onInspect = vi.fn();
    render(
      <AudioPlayback
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
        inspectionSample={null}
        onInspect={onInspect}
        unavailableReason="Unavailable"
      />,
    );

    fireEvent.change(screen.getByRole("slider"), {
      target: { value: "48_000" },
    });

    expect(onInspect).toHaveBeenLastCalledWith(48_000);
    expect(
      screen.getByText("00:01.0", { selector: "output", exact: false }),
    ).toBeTruthy();
  });
});
