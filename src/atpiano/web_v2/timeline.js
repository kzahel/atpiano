(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.atpianoTimeline = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

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

  return { materialize, visibleWindow, viewportQueryKey, noteGeometry };
});
