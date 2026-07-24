"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const {
  decorateGroups,
  groupEvents,
  normalizedSettings,
  rhythmValueForInterval,
  settingsDocument,
} = require("../src/atpiano/web/live-view.js");

function event(id, onsetSample, pitch, confidence = 0.7) {
  return {
    event_id: id,
    onset_sample: onsetSample,
    pitch,
    confidence,
    lifecycle: "committed",
  };
}

test("grouping stays anchored to the first onset", () => {
  const groups = groupEvents(
    [
      event("first", 0, 60),
      event("second", 70, 64),
      event("third", 130, 67),
    ],
    1_000,
    { mode: "grouped", groupWindowMs: 80 }
  );

  assert.deepEqual(
    groups.map((group) => group.notes.map((note) => note.pitch)),
    [[60, 64], [67]]
  );
});

test("grouped duplicates keep the strongest onset score", () => {
  const groups = groupEvents(
    [event("weak", 100, 60, 0.61), event("strong", 120, 60, 0.92)],
    1_000,
    { mode: "grouped", groupWindowMs: 80 }
  );

  assert.equal(groups.length, 1);
  assert.equal(groups[0].notes.length, 1);
  assert.equal(groups[0].notes[0].eventId, "strong");
  assert.equal(groups[0].notes[0].confidence, 0.92);
});

test("raw mode gives every event its own staff slot", () => {
  const groups = groupEvents(
    [event("one", 100, 60), event("two", 100, 64)],
    1_000,
    { mode: "raw", groupWindowMs: 250 }
  );

  assert.deepEqual(
    groups.map((group) => group.notes.map((note) => note.pitch)),
    [[60], [64]]
  );
});

test("display settings are normalized and versioned", () => {
  assert.deepEqual(
    normalizedSettings({
      mode: "invalid",
      groupWindowMs: 900,
      showConfidence: "yes",
      timingMode: "invalid",
      rhythmBpm: 90,
    }),
    {
      mode: "grouped",
      groupWindowMs: 250,
      showConfidence: false,
      timingMode: "relative",
      rhythmBpm: 120,
    }
  );
  assert.deepEqual(
    settingsDocument({
      mode: "raw",
      groupWindowMs: 40,
      timingMode: "both",
      rhythmBpm: 80,
    }),
    {
      schema_version: "atpiano.live-display-settings.v2",
      mode: "raw",
      groupWindowMs: 40,
      showConfidence: false,
      timingMode: "both",
      rhythmBpm: 80,
    }
  );
});

test("rhythm preset revises each group from the following onset", () => {
  const groups = groupEvents(
    [event("one", 0, 60), event("two", 250, 62), event("three", 750, 64)],
    1_000,
    { mode: "raw" }
  );
  const decorated = decorateGroups(groups, 1_000, { rhythmBpm: 120 });

  assert.equal(decorated[0].rhythmValue.name, "eighth");
  assert.equal(decorated[1].rhythmValue.name, "quarter");
  assert.equal(decorated[2].rhythmValue, null);
  assert.equal(decorated[0].previousDeltaMs, null);
  assert.equal(decorated[1].previousDeltaMs, 250);
  assert.equal(decorated[2].onsetSeconds, 0.75);
});

test("timing retains the Basic Pitch frame interval on the source clock", () => {
  const groups = groupEvents(
    [event("lower", 0, 50), event("octave", 256, 62)],
    22_050,
    { mode: "raw" }
  );
  const decorated = decorateGroups(groups, 22_050, { rhythmBpm: 0 });

  assert.ok(Math.abs(decorated[1].previousDeltaMs - 11.609977) < 0.000001);
  assert.equal(decorated[0].rhythmValue, null);
  assert.equal(rhythmValueForInterval(250, 1_000, 120).name, "eighth");
});
