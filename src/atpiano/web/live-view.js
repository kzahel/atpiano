(function installLiveView(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.atpianoLiveView = api;
})(typeof globalThis === "undefined" ? window : globalThis, function liveViewFactory() {
  "use strict";

  const SETTINGS_SCHEMA = "atpiano.live-display-settings.v2";
  const LEGACY_STORAGE_KEY = "atpiano.live-display-settings.v1";
  const STORAGE_KEY = SETTINGS_SCHEMA;
  const MIN_GROUP_WINDOW_MS = 0;
  const MAX_GROUP_WINDOW_MS = 250;
  const RHYTHM_BPM_PRESETS = Object.freeze([0, 60, 80, 100, 120, 140, 160]);
  const RHYTHM_VALUES = Object.freeze([
    Object.freeze({ name: "sixteenth", beats: 0.25 }),
    Object.freeze({ name: "eighth", beats: 0.5 }),
    Object.freeze({ name: "quarter", beats: 1 }),
    Object.freeze({ name: "half", beats: 2 }),
    Object.freeze({ name: "whole", beats: 4 }),
  ]);
  const TIMING_MODES = Object.freeze(["off", "relative", "absolute", "both"]);
  const DEFAULT_SETTINGS = Object.freeze({
    mode: "grouped",
    groupWindowMs: 80,
    showConfidence: false,
    timingMode: "relative",
    rhythmBpm: 120,
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
    const timingMode = TIMING_MODES.includes(value.timingMode)
      ? value.timingMode
      : DEFAULT_SETTINGS.timingMode;
    const requestedRhythmBpm = Number(value.rhythmBpm);
    const rhythmBpm = RHYTHM_BPM_PRESETS.includes(requestedRhythmBpm)
      ? requestedRhythmBpm
      : DEFAULT_SETTINGS.rhythmBpm;
    return {
      mode,
      groupWindowMs,
      showConfidence: value.showConfidence === true,
      timingMode,
      rhythmBpm,
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

  function rhythmValueForInterval(intervalSamples, sampleRate, bpm) {
    if (!(intervalSamples >= 0) || !(sampleRate > 0) || !(bpm > 0)) return null;
    const intervalBeats = (intervalSamples * bpm) / (sampleRate * 60);
    return RHYTHM_VALUES.reduce((closest, candidate) =>
      Math.abs(candidate.beats - intervalBeats) <
      Math.abs(closest.beats - intervalBeats)
        ? candidate
        : closest
    );
  }

  function decorateGroups(groups, sampleRate, requestedSettings) {
    if (!(sampleRate > 0)) return [];
    const settings = normalizedSettings(requestedSettings);
    return groups.map((group, index) => {
      const previous = groups[index - 1];
      const next = groups[index + 1];
      return {
        ...group,
        onsetSeconds: group.onsetSample / sampleRate,
        previousDeltaMs: previous
          ? ((group.onsetSample - previous.onsetSample) / sampleRate) * 1000
          : null,
        rhythmValue: next
          ? rhythmValueForInterval(
              next.onsetSample - group.onsetSample,
              sampleRate,
              settings.rhythmBpm
            )
          : null,
      };
    });
  }

  return {
    DEFAULT_SETTINGS,
    LEGACY_STORAGE_KEY,
    MAX_GROUP_WINDOW_MS,
    MIN_GROUP_WINDOW_MS,
    RHYTHM_BPM_PRESETS,
    RHYTHM_VALUES,
    SETTINGS_SCHEMA,
    STORAGE_KEY,
    TIMING_MODES,
    decorateGroups,
    groupEvents,
    normalizedSettings,
    rhythmValueForInterval,
    settingsDocument,
  };
});
