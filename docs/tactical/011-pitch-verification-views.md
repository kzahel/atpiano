# 011 — Pitch Verification Views

Topic: live-acoustic-transcription

Status: in progress on 2026-07-26.

## Motivation

The corrected-note workbench piano roll verifies timing, duration, revision,
and horizon behavior, but its semitone rows lack enough landmarks for a player
to verify detected pitches at a glance. The roll remains useful and must not be
removed; it becomes one independently selectable view rather than the only
view.

Readable score engraving remains Lane C work. Adding a staff now would require
unsettled choices about onset grouping, duration, rhythm, meter, key, hand
split, enharmonic spelling, and layout. This slice instead adds exact-pitch
views that consume the existing note events without changing their semantics.

## Interaction Contract

The Performance card exposes independent visualization toggles:

- **Piano roll** keeps the virtualized 15–120 second note timeline and gains an
  aligned 88-key pitch gutter with octave landmarks.
- **Keyboard** shows a physically ordered 88-key keyboard. By default it
  follows the latest detected attack in the visible event range. Provisional
  keys use amber and corrected keys use mint.
- Clicking the roll or moving the keyboard inspection slider pins the keyboard
  to notes sounding at an exact source-sample time.
- **Follow latest attack** returns the keyboard to live behavior.
- Either view can be shown alone or both can be shown together.

The keyboard readout names every highlighted MIDI pitch using scientific pitch
notation. It does not infer a chord name, key, rhythm, meter, or score.

## Implementation Plan

1. Add pure pitch naming and keyboard-snapshot selection helpers with Node
   tests for chords, lifecycle preference, and pinned inspection.
2. Add view toggles, an aligned keyboard gutter, an 88-key readout, an
   inspection-time slider, and a follow control to the separate v2 frontend.
3. Preserve bounded viewport queries and draw work proportional to the fixed
   88-key range plus the visible event batch.
4. Exercise the generated chord/Alberti fixture through the real replay API,
   run the v1/v2 regression suite, update the living topic, and commit.

## Acceptance

- the existing piano roll remains available;
- users can independently show the roll and keyboard;
- C octave labels and the A0/C8 endpoints anchor the roll;
- the latest fixture attack lights named keys;
- a pinned time selects notes by source-sample onset and offset;
- provisional and corrected keys remain visually distinct;
- no microphone is required for validation; and
- v1 remains unchanged.

