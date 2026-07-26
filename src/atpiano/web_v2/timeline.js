(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.atpianoTimeline = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const NOTE_NAMES = [
    "C",
    "C#",
    "D",
    "D#",
    "E",
    "F",
    "F#",
    "G",
    "G#",
    "A",
    "A#",
    "B",
  ];

  function isBlackKey(pitch) {
    return [1, 3, 6, 8, 10].includes(((Number(pitch) % 12) + 12) % 12);
  }

  function midiName(pitch) {
    const value = Number(pitch);
    if (!Number.isInteger(value)) return "—";
    const pitchClass = ((value % 12) + 12) % 12;
    return `${NOTE_NAMES[pitchClass]}${Math.floor(value / 12) - 1}`;
  }

  function keyboardLayout(pitchMin = 21, pitchMax = 108) {
    const pitches = [];
    for (let pitch = pitchMin; pitch <= pitchMax; pitch += 1) {
      pitches.push(pitch);
    }
    const whitePitches = pitches.filter((pitch) => !isBlackKey(pitch));
    const whiteWidth = 100 / whitePitches.length;
    const blackWidth = whiteWidth * 0.64;
    const keys = pitches.map((pitch) => {
      const black = isBlackKey(pitch);
      const name = midiName(pitch);
      const landmark =
        pitch === pitchMin || pitch === pitchMax || pitch % 12 === 0
          ? name
          : "";
      return {
        pitch,
        name,
        landmark,
        kind: black ? "black" : "white",
        widthPercent: black ? blackWidth : whiteWidth,
        leftPercent: black
          ? whitePitches.filter((value) => value < pitch).length * whiteWidth -
            blackWidth / 2
          : null,
      };
    });
    return [
      ...keys.filter((key) => key.kind === "white"),
      ...keys.filter((key) => key.kind === "black"),
    ];
  }

  function materialize(events) {
    const latest = new Map();
    for (const event of events) {
      const current = latest.get(event.event_id);
      if (!current || Number(event.revision) > Number(current.revision)) {
        if (event.lifecycle === "retracted") latest.delete(event.event_id);
        else latest.set(event.event_id, event);
      }
    }
    return [...latest.values()].sort(
      (left, right) =>
        left.onset_sample - right.onset_sample ||
        String(left.event_id).localeCompare(String(right.event_id))
    );
  }

  function visibleWindow(durationS, windowS, seekS, follow) {
    const duration = Math.max(0, Number(durationS) || 0);
    const span = Math.max(1, Math.min(Number(windowS) || 30, 120));
    const maximumStart = Math.max(0, duration - span);
    const start = follow
      ? maximumStart
      : Math.max(0, Math.min(Number(seekS) || 0, maximumStart));
    return { startS: start, endS: start + span, spanS: span, maximumStart };
  }

  function viewportQueryKey(
    sessionId,
    startSample,
    endSample,
    eventSequence,
    audioHead,
    status
  ) {
    return [
      sessionId,
      startSample,
      endSample,
      eventSequence,
      audioHead,
      status,
    ].join(":");
  }

  function keyboardSnapshot(
    events,
    sampleRate,
    pinnedS = null,
    attackWindowS = 0.08
  ) {
    const rate = Math.max(1, Number(sampleRate) || 1);
    const notes = events.filter(
      (event) =>
        event.lifecycle !== "retracted" &&
        Number.isInteger(event.pitch) &&
        Number.isInteger(event.onset_sample)
    );
    if (notes.length === 0) {
      return { mode: pinnedS == null ? "latest" : "pinned", sample: null, notes: [] };
    }

    let sample;
    let selected;
    if (pinnedS == null) {
      sample = Math.max(...notes.map((event) => event.onset_sample));
      const attackWindow = Math.max(0, Math.round(attackWindowS * rate));
      selected = notes.filter(
        (event) => Math.abs(event.onset_sample - sample) <= attackWindow
      );
    } else {
      sample = Math.max(0, Math.round((Number(pinnedS) || 0) * rate));
      selected = notes.filter(
        (event) =>
          event.onset_sample <= sample &&
          (event.offset_sample == null || event.offset_sample >= sample)
      );
    }

    const priority = { provisional: 1, committed: 2 };
    const byPitch = new Map();
    for (const event of selected) {
      const current = byPitch.get(event.pitch);
      if (
        !current ||
        (priority[event.lifecycle] || 0) > (priority[current.lifecycle] || 0) ||
        ((priority[event.lifecycle] || 0) ===
          (priority[current.lifecycle] || 0) &&
          event.onset_sample > current.onset_sample)
      ) {
        byPitch.set(event.pitch, event);
      }
    }
    return {
      mode: pinnedS == null ? "latest" : "pinned",
      sample,
      notes: [...byPitch.values()].sort(
        (left, right) => left.pitch - right.pitch
      ),
    };
  }

  function noteGeometry(
    event,
    sampleRate,
    startS,
    spanS,
    width,
    pitchMin,
    pitchMax,
    height
  ) {
    const onsetS = event.onset_sample / sampleRate;
    const rawOffsetS =
      event.offset_sample == null ? startS + spanS : event.offset_sample / sampleRate;
    const offsetS = Math.max(onsetS, rawOffsetS);
    const x = ((onsetS - startS) / spanS) * width;
    const endX = ((offsetS - startS) / spanS) * width;
    const rowHeight = height / (pitchMax - pitchMin + 1);
    const y = (pitchMax - event.pitch) * rowHeight;
    return {
      x,
      y,
      width: Math.max(2, endX - x),
      height: Math.max(2, rowHeight - 1),
    };
  }

  return {
    isBlackKey,
    keyboardLayout,
    keyboardSnapshot,
    materialize,
    midiName,
    visibleWindow,
    viewportQueryKey,
    noteGeometry,
  };
});
