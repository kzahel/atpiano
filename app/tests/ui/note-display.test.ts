import { describe, expect, it } from "vitest";

import { noteDisplaySegments } from "../../src/lib/note-display.js";
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

function note(
  overrides: Partial<EventRevision> = {},
): EventRevision {
  return {
    schema_version: "atpiano.contract.v1",
    workspace_id: "local",
    session_id: "session-live",
    transcription_run_id: "run-live",
    event_id: "note-1",
    revision: 1,
    lane: "commit",
    lifecycle: "committed",
    kind: "note",
    onset_sample: 600_000,
    offset_sample: 900_000,
    offset_state: "closed",
    pitch: 60,
    velocity: 96,
    confidence: 0.9,
    supersedes_revision: null,
    ...overrides,
  } as EventRevision;
}

describe("piano-roll note display", () => {
  it("never draws a committed segment past the commit horizon", () => {
    expect(noteDisplaySegments(note(), horizon, 48_000)).toEqual({
      solidStart: 600_000,
      solidEnd: 720_000,
      tailStart: null,
      tailEnd: null,
    });
  });

  it("renders an open corrected note as a stub and dotted tail to commit", () => {
    expect(
      noteDisplaySegments(
        note({ offset_sample: null, offset_state: "open" }),
        horizon,
        48_000,
      ),
    ).toEqual({
      solidStart: 600_000,
      solidEnd: 608_640,
      tailStart: 608_640,
      tailEnd: 720_000,
    });
  });

  it("does not draw impossible committed events beyond the horizon", () => {
    expect(
      noteDisplaySegments(
        note({ onset_sample: 800_000, offset_sample: 850_000 }),
        horizon,
        48_000,
      ),
    ).toBeNull();
  });
});
