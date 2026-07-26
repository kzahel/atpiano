import { describe, expect, it, vi } from "vitest";

import {
  moveScoreCursor,
  parseScoreAlignment,
  scoreAttackAtSample,
  sourceSampleAtScoreQuarter,
  type ScoreCursorLike,
} from "../../src/lib/score-alignment.js";

const scoreHash = "a".repeat(64);

function alignmentDocument() {
  return {
    schema_version: "atpiano.score-alignment.v2",
    session_id: "session-1",
    sample_rate_hz: 48_000,
    musicxml: { sha256: scoreHash },
    mapping: {
      algorithm: "monotonic-exact-pitch-lcs-v1",
      source_order: "onset-sample,pitch,duration,source-index",
      score_order: "attack-quarters,pitch,output-index",
    },
    rows: [
      {
        source_index: 0,
        event_id: "opening-chord-c",
        pitch: 60,
        onset_sample: 48_000,
        offset_sample: 72_000,
        status: "mapped",
        score_time_quarters: { numerator: 2, denominator: 1 },
      },
      {
        source_index: 1,
        event_id: "opening-chord-e",
        pitch: 64,
        onset_sample: 48_000,
        offset_sample: 72_000,
        status: "mapped",
        score_time_quarters: { numerator: 2, denominator: 1 },
      },
      {
        source_index: 2,
        event_id: "unmatched",
        pitch: 65,
        onset_sample: 72_000,
        offset_sample: 80_000,
        status: "unmatched",
        score_time_quarters: null,
      },
      {
        source_index: 3,
        event_id: "later-g",
        pitch: 67,
        onset_sample: 96_000,
        offset_sample: 120_000,
        status: "mapped",
        score_time_quarters: { numerator: 7, denominator: 2 },
      },
    ],
  };
}

describe("score playback alignment", () => {
  it("selects discrete score attacks within snapshot coverage", () => {
    const alignment = parseScoreAlignment(alignmentDocument(), {
      sessionId: "session-1",
      musicXmlSha256: scoreHash,
    });

    expect(scoreAttackAtSample(alignment, 47_999, 144_000)).toBeNull();
    expect(scoreAttackAtSample(alignment, 48_000, 144_000)).toBe(2);
    expect(scoreAttackAtSample(alignment, 80_000, 144_000)).toBe(2);
    expect(scoreAttackAtSample(alignment, 96_000, 144_000)).toBe(3.5);
    expect(scoreAttackAtSample(alignment, 144_001, 144_000)).toBeNull();
    expect(sourceSampleAtScoreQuarter(alignment, 2)).toBe(48_000);
    expect(sourceSampleAtScoreQuarter(alignment, 3)).toBe(96_000);
    expect(sourceSampleAtScoreQuarter(alignment, 99)).toBe(96_000);
  });

  it("rejects alignment from another MusicXML snapshot", () => {
    expect(() =>
      parseScoreAlignment(alignmentDocument(), {
        sessionId: "session-1",
        musicXmlSha256: "b".repeat(64),
      }),
    ).toThrow(/another score snapshot/);
  });

  it("normalizes same-tick transformer order onto the sample timeline", () => {
    const document = alignmentDocument();
    document.rows = [
      {
        source_index: 0,
        event_id: "later-low",
        pitch: 48,
        onset_sample: 48_009,
        offset_sample: 72_009,
        status: "mapped",
        score_time_quarters: { numerator: 3, denominator: 1 },
      },
      {
        source_index: 1,
        event_id: "earlier-high",
        pitch: 60,
        onset_sample: 48_003,
        offset_sample: 72_003,
        status: "mapped",
        score_time_quarters: { numerator: 2, denominator: 1 },
      },
    ];

    const alignment = parseScoreAlignment(document, {
      sessionId: "session-1",
      musicXmlSha256: scoreHash,
    });

    expect(alignment.rows.map((row) => row.event_id)).toEqual([
      "earlier-high",
      "later-low",
    ]);
    expect(scoreAttackAtSample(alignment, 48_002, 144_000)).toBeNull();
    expect(scoreAttackAtSample(alignment, 48_003, 144_000)).toBe(2);
    expect(scoreAttackAtSample(alignment, 48_009, 144_000)).toBe(3);
  });

  it("rejects score reversals on the source sample clock", () => {
    const document = alignmentDocument();
    document.rows[3]!.score_time_quarters = {
      numerator: 1,
      denominator: 1,
    };

    expect(() =>
      parseScoreAlignment(document, {
        sessionId: "session-1",
        musicXmlSha256: scoreHash,
      }),
    ).toThrow(/score order/);
  });

  it("rejects legacy token-index alignment semantics", () => {
    const document = {
      ...alignmentDocument(),
      schema_version: "atpiano.score-alignment.v1",
    };

    expect(() =>
      parseScoreAlignment(document, {
        sessionId: "session-1",
        musicXmlSha256: scoreHash,
      }),
    ).toThrow(/version/);
  });

  it("moves the OSMD cursor forward, backward, and out of coverage", () => {
    let index = 0;
    const positions = [0, 0.5, 0.875];
    const show = vi.fn();
    const hide = vi.fn();
    const cursor: ScoreCursorLike = {
      get Iterator() {
        return {
          CurrentSourceTimestamp: { RealValue: positions[index]! },
          EndReached: index === positions.length - 1,
        };
      },
      reset: vi.fn(() => {
        index = 0;
      }),
      next: vi.fn(() => {
        index = Math.min(positions.length - 1, index + 1);
      }),
      show,
      hide,
    };

    let prior = moveScoreCursor(cursor, 2, null);
    expect(index).toBe(1);
    expect(show).toHaveBeenCalledTimes(1);
    prior = moveScoreCursor(cursor, 3.5, prior);
    expect(index).toBe(2);
    prior = moveScoreCursor(cursor, 2, prior);
    expect(index).toBe(1);
    expect(cursor.reset).toHaveBeenCalledTimes(2);
    expect(moveScoreCursor(cursor, null, prior)).toBeNull();
    expect(hide).toHaveBeenCalledTimes(1);
  });
});
