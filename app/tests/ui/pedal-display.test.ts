import { describe, expect, it } from "vitest";

import { pedalDisplaySegment } from "../../src/lib/pedal-display.js";
import type {
  EventRevision,
  Horizon,
} from "../../src/runtime/atpiano-runtime.js";

const horizon: Horizon = {
  schema_version: "atpiano.contract.v1",
  workspace_id: "local",
  session_id: "session-live",
  transcription_run_id: "run-live",
  sample_rate_hz: 48_000,
  audio_head_sample: 960_000,
  provisional_sample: 840_000,
  commit_sample: 720_000,
  recorded_at: "2026-07-26T12:00:00Z",
};

function pedal(overrides: Partial<EventRevision> = {}): EventRevision {
  return {
    schema_version: "atpiano.contract.v1",
    workspace_id: "local",
    session_id: "session-live",
    transcription_run_id: "run-live",
    event_id: "pedal-1",
    revision: 1,
    lane: "commit",
    lifecycle: "committed",
    kind: "sustain",
    onset_sample: 480_000,
    offset_sample: 900_000,
    offset_state: "closed",
    pitch: null,
    velocity: 96,
    confidence: null,
    supersedes_revision: null,
    ...overrides,
  } as EventRevision;
}

describe("piano-roll pedal display", () => {
  it("never draws a committed pedal past the commit horizon", () => {
    expect(
      pedalDisplaySegment(pedal(), horizon, 960_000, 48_000),
    ).toEqual({
      start: 480_000,
      end: 720_000,
      suspectLongEstimate: false,
    });
  });

  it("flags a session-spanning estimate instead of presenting it as certain", () => {
    expect(
      pedalDisplaySegment(
        pedal({
          kind: "soft-pedal",
          onset_sample: 120_000,
          offset_sample: 1_440_000,
        }),
        undefined,
        1_800_000,
        48_000,
      ),
    ).toEqual({
      start: 120_000,
      end: 1_440_000,
      suspectLongEstimate: true,
    });
  });

  it("keeps sustain and soft pedal kinds eligible as separate lanes", () => {
    expect(pedalDisplaySegment(pedal(), horizon, 960_000, 48_000)).not.toBeNull();
    expect(
      pedalDisplaySegment(
        pedal({ kind: "soft-pedal" }),
        horizon,
        960_000,
        48_000,
      ),
    ).not.toBeNull();
    expect(
      pedalDisplaySegment(
        pedal({ kind: "note" }),
        horizon,
        960_000,
        48_000,
      ),
    ).toBeNull();
  });
});
