"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const {
  groupEvents,
  normalizedSettings,
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
    }),
    {
      mode: "grouped",
      groupWindowMs: 250,
      showConfidence: false,
    }
  );
  assert.deepEqual(settingsDocument({ mode: "raw", groupWindowMs: 40 }), {
    schema_version: "atpiano.live-display-settings.v1",
    mode: "raw",
    groupWindowMs: 40,
    showConfidence: false,
  });
});
