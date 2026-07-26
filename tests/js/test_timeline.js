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
