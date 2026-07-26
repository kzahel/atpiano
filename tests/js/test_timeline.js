"use strict";

const assert = require("node:assert/strict");
const timeline = require("../../src/atpiano/web_v2/timeline.js");

const events = [
  {
    event_id: "same",
    revision: 1,
    lifecycle: "provisional",
    onset_sample: 10,
  },
  {
    event_id: "same",
    revision: 2,
    lifecycle: "committed",
    onset_sample: 12,
  },
  {
    event_id: "gone",
    revision: 1,
    lifecycle: "provisional",
    onset_sample: 20,
  },
  {
    event_id: "gone",
    revision: 2,
    lifecycle: "retracted",
    onset_sample: 20,
  },
];

assert.deepEqual(
  timeline.materialize(events).map((event) => [event.event_id, event.lifecycle]),
  [["same", "committed"]]
);

assert.deepEqual(timeline.visibleWindow(3700, 60, 0, true), {
  startS: 3640,
  endS: 3700,
  spanS: 60,
  maximumStart: 3640,
});
assert.deepEqual(timeline.visibleWindow(3700, 60, 120, false), {
  startS: 120,
  endS: 180,
  spanS: 60,
  maximumStart: 3640,
});

const emptyReplayKey = timeline.viewportQueryKey("replay", 0, 100, 0, 0, "active");
assert.notEqual(
  emptyReplayKey,
  timeline.viewportQueryKey("replay", 0, 100, 0, 50, "active")
);
assert.notEqual(
  emptyReplayKey,
  timeline.viewportQueryKey("replay", 0, 100, 0, 0, "complete")
);

assert.equal(timeline.midiName(21), "A0");
assert.equal(timeline.midiName(60), "C4");
assert.equal(timeline.midiName(108), "C8");
assert.equal(timeline.isBlackKey(61), true);
assert.equal(timeline.isBlackKey(60), false);
const keyboardLayout = timeline.keyboardLayout();
assert.equal(keyboardLayout.length, 88);
assert.equal(
  keyboardLayout.filter((key) => key.kind === "white").length,
  52
);
assert.equal(
  keyboardLayout.filter((key) => key.kind === "black").length,
  36
);
assert.deepEqual(
  keyboardLayout
    .filter((key) => key.landmark)
    .map((key) => key.landmark),
  ["A0", "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8"]
);

const keyboardEvents = [
  {
    event_id: "c-committed",
    lifecycle: "committed",
    pitch: 60,
    onset_sample: 100,
    offset_sample: 300,
  },
  {
    event_id: "c-provisional",
    lifecycle: "provisional",
    pitch: 60,
    onset_sample: 158,
    offset_sample: 320,
  },
  {
    event_id: "e",
    lifecycle: "provisional",
    pitch: 64,
    onset_sample: 104,
    offset_sample: 250,
  },
  {
    event_id: "g",
    lifecycle: "committed",
    pitch: 67,
    onset_sample: 160,
    offset_sample: null,
  },
];
const latestKeys = timeline.keyboardSnapshot(keyboardEvents, 1000);
assert.equal(latestKeys.mode, "latest");
assert.equal(latestKeys.sample, 160);
assert.deepEqual(
  latestKeys.notes.map((event) => [event.pitch, event.lifecycle]),
  [
    [60, "committed"],
    [64, "provisional"],
    [67, "committed"],
  ]
);
const pinnedKeys = timeline.keyboardSnapshot(keyboardEvents, 1000, 0.26);
assert.equal(pinnedKeys.mode, "pinned");
assert.deepEqual(
  pinnedKeys.notes.map((event) => event.pitch),
  [60, 67]
);

const geometry = timeline.noteGeometry(
  { onset_sample: 100, offset_sample: 200, pitch: 60 },
  100,
  0,
  4,
  400,
  21,
  108,
  440
);
assert.equal(geometry.x, 100);
assert.equal(geometry.width, 100);
assert.equal(geometry.y, 240);
