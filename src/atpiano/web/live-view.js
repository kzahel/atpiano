(function installLiveView(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.atpianoLiveView = api;
})(typeof globalThis === "undefined" ? window : globalThis, function liveViewFactory() {
  "use strict";

  const SETTINGS_SCHEMA = "atpiano.live-display-settings.v1";
  const STORAGE_KEY = SETTINGS_SCHEMA;
  const MIN_GROUP_WINDOW_MS = 0;
  const MAX_GROUP_WINDOW_MS = 250;
  const DEFAULT_SETTINGS = Object.freeze({
    mode: "grouped",
    groupWindowMs: 80,
    showConfidence: false,
  });

  function normalizedSettings(value = {}) {
    const mode = value.mode === "raw" ? "raw" : "grouped";
    const requestedWindow = Number(value.groupWindowMs);
    const groupWindowMs = Number.isFinite(requestedWindow)
      ? Math.round(
          Math.min(
            MAX_GROUP_WINDOW_MS,
            Math.max(MIN_GROUP_WINDOW_MS, requestedWindow)
          )
        )
      : DEFAULT_SETTINGS.groupWindowMs;
    return {
      mode,
      groupWindowMs,
      showConfidence: value.showConfidence === true,
    };
  }

  function settingsDocument(value) {
    return {
      schema_version: SETTINGS_SCHEMA,
      ...normalizedSettings(value),
    };
  }

  function noteForEvent(event) {
    return {
      eventId: event.event_id,
      onsetSample: event.onset_sample,
      pitch: event.pitch,
      confidence: Number.isFinite(event.confidence) ? event.confidence : null,
    };
  }

  function groupEvents(events, sampleRate, requestedSettings) {
    if (!(sampleRate > 0)) return [];
    const settings = normalizedSettings(requestedSettings);
    const accepted = [...events]
      .filter(
        (event) =>
          event.lifecycle !== "retracted" &&
          event.pitch >= 21 &&
          event.pitch <= 108
      )
      .sort(
        (left, right) =>
          left.onset_sample - right.onset_sample ||
          left.pitch - right.pitch ||
          String(left.event_id).localeCompare(String(right.event_id))
      );
    if (settings.mode === "raw") {
      return accepted.map((event) => ({
        onsetSample: event.onset_sample,
        notes: [noteForEvent(event)],
      }));
    }

    const groups = [];
    const windowSamples = (settings.groupWindowMs / 1000) * sampleRate;
    for (const event of accepted) {
      let group = groups[groups.length - 1];
      if (!group || event.onset_sample - group.onsetSample > windowSamples) {
        group = { onsetSample: event.onset_sample, notes: [] };
        groups.push(group);
      }
      const note = noteForEvent(event);
      const duplicateIndex = group.notes.findIndex(
        (existing) => existing.pitch === note.pitch
      );
      if (duplicateIndex < 0) {
        group.notes.push(note);
      } else {
        const previous = group.notes[duplicateIndex];
        if ((note.confidence ?? -1) > (previous.confidence ?? -1)) {
          group.notes[duplicateIndex] = note;
        }
      }
    }
    return groups;
  }

  return {
    DEFAULT_SETTINGS,
    MAX_GROUP_WINDOW_MS,
    MIN_GROUP_WINDOW_MS,
    SETTINGS_SCHEMA,
    STORAGE_KEY,
    groupEvents,
    normalizedSettings,
    settingsDocument,
  };
});
