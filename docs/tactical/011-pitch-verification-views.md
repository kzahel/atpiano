# 011 — Pitch Verification Views

Topic: live-acoustic-transcription

Status: complete on 2026-07-26.

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

## Execution Record

Implemented two independent **Piano roll** and **Keyboard** toggles in the v2
Performance card. Both default on, and either can be used alone. The existing
roll retains its viewport, correction colors, commit horizon, and pedal band.
Its time geometry now starts after a fixed pitch gutter whose white/black key
pattern and A0, C-octave, and C8 labels align with all 88 semitone rows.

The new full-width keyboard uses 52 white and 36 black keys in physical order.
It follows the latest detected attack in the currently indexed range and
groups attacks within 80 ms. If more than one identity selects the same pitch,
a committed state wins over a provisional one. Every active key shows its
scientific pitch name, with provisional keys in amber and corrected keys in
mint.

Clicking the roll or moving **Inspect source time** pins an exact
source-sample position and selects notes whose onset/offset interval contains
it. The roll marks that position, the keyboard lists all sounding pitch names,
and **Follow latest attack** resumes the moving view. Pinning freezes the
timeline window so the inspected events do not scroll out while reviewing
them.

Pure JavaScript coverage verifies:

```text
88-key layout: 52 white / 36 black
landmarks: A0, C1–C8
MIDI names and black-key classification
80 ms latest-attack chord grouping
committed-over-provisional pitch preference
pinned source-time duration selection
```

The actual completed 42-second generated musical run was served through the
loopback indexed-event API. Its final 30-second viewport returned 123
materialized events. The latest attack resolved to `C5`; pinned source times
produced exact multi-key sets including:

```text
12.25 s: D3 · A3 · A4 · D5 · F5
13.55 s: B3 · D4 · F4 · B4
```

Final regression evidence:

```text
uv run ruff check .                         pass
uv run pytest -q                            47 passed
node tests/js/test_timeline.js              pass
node --check src/atpiano/web_v2/app.js      pass
```

No browser microphone was activated. The Sites capability workflow preserved
the established loopback-only boundary; this repository still has no
`.openai/hosting.json`, so no deployment was created.
