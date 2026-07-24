# Live Timing And Rhythm Guides

Topic: live-acoustic-transcription

Status: complete on 2026-07-24.

## Motivation

The sequential onset staff is legible enough to diagnose pitch, but equal
quarter-note-like marks hide the timing evidence that separates a scale,
rolled chord, simultaneous strike, and attack-synchronous harmonic error. The
user wants direct source-onset timing and a deliberately approximate rhythmic
shape without reviving the failed full-score inference path.

The latest descending-scale take demonstrates both needs. Most visible onsets
are roughly 197–250 ms apart, while a suspicious upper octave follows its
lower pitch by one Basic Pitch frame, about 11.6 ms.

## Objective

Add optional absolute and previous-onset timing labels plus preset-based rough
rhythm glyphs to the existing live staff. Keep grouping, timing, and rhythm as
reversible browser presentation decisions that do not alter transcription,
event identity, reconciliation, or the final adapter.

## Included

- timing-label modes for off, previous-onset delta, source-onset time, or both;
- timing derived from `onset_sample / sample_rate`, never packet arrival;
- explanatory copy for Basic Pitch's approximately 11.6 ms onset-frame grid;
- a neutral rhythm mode and common fixed-tempo presets;
- 120 BPM as the initial rough-rhythm preset;
- nearest sixteenth, eighth, quarter, half, or whole glyph selection;
- revision of the previous onset group's glyph when the next group arrives;
- the current final group shown as a neutral quarter-like pending mark;
- immediate rerendering, browser-local persistence, and capture metadata;
- migration of the earlier display preference document; and
- deterministic presentation tests plus full project validation.

## Display Contract

Grouped mode labels and estimates intervals between group anchors. Raw mode
does the same between individual accepted event identities, including a zero
delta for simultaneous events.

The rhythm guide uses the inter-onset interval, not the model's note offset.
For preset tempo `bpm`, one beat is `60 / bpm` seconds. The interval is mapped
to the nearest value among:

```text
sixteenth = 1/4 beat
eighth    = 1/2 beat
quarter   = 1 beat
half      = 2 beats
whole     = 4 beats
```

The interval from group N to group N+1 determines group N's glyph. The last
group has no following interval and remains a quarter-like pending mark. Long
or short intervals clamp to the available values. This is an intentionally
fake spacing aid: it makes no claim about key release, sustain, tempo
inference, meter, rests, voices, ties, or score readability.

## Excluded

- automatic tempo, beat, downbeat, meter, or pickup inference;
- model offset or pedal interpretation;
- rests, ties, beams, tuplets, barlines, or key signatures;
- changes to recognition acceptance, confidence, grouping, or lifecycle; and
- MusicXML or the paused performance-to-notation converter.

## Validation

- source and delta timing are deterministic at multiple sample rates;
- grouped and raw timing retain their existing anchor semantics;
- rhythm values revise the prior group and leave the last group pending;
- settings v1 migrate to v2 and invalid values normalize safely;
- capture artifacts retain the selected timing and rhythm settings;
- the real workbench serves and wires the new controls and explanatory copy;
- JavaScript syntax, Node tests, Python tests, lint, build, and whitespace
  checks pass.

## Implemented Result

The live panel now adds two settings:

- **Timing labels:** previous-onset gaps, absolute source time, both, or off;
- **Rough rhythm:** neutral quarter marks or fixed 60, 80, 100, 120, 140,
  or 160 BPM presets.

Relative timing and 120 BPM are the initial defaults. Absolute times render as
`minutes:seconds.milliseconds`; deltas render as rounded milliseconds. Both
come from each normalized event's source `onset_sample` and the capture sample
rate. They never use WebSocket arrival, model completion, or browser paint
time.

Each group is decorated only after the existing raw/grouped aggregation.
Grouped mode therefore measures from group anchor to group anchor. Raw mode
exposes every event identity, including zero-millisecond simultaneous onsets.
Changing any control immediately reinterprets retained live events without
rerunning the model.

At a nonzero preset, the gap to the next onset selects the preceding group's
sixteenth, eighth, quarter, half, or whole glyph. The final group remains the
existing quarter-like mark because its next interval is unknown. Selecting
neutral mode leaves every group quarter-like. There are deliberately no
rests, ties, beams, barlines, or note-offset semantics.

Display settings now use `atpiano.live-display-settings.v2`. The browser reads
the earlier v1 storage key when v2 is absent and fills the new defaults. The
capture writer accepts both schema versions, while new starts and Stops retain
the selected v2 timing mode and rhythm preset in `browser-capture.json`.

## Evidence

Basic Pitch 0.4.0 predicts on a 256-sample hop at 22,050 Hz:

```text
256 / 22,050 = 0.011609977 s = 11.609977 ms
```

The source recording can have a much finer sample period, but model onsets
remain quantized to approximately this frame grid. The workbench explains
that distinction beside the timing control.

The retained descending-scale session
`20260724T152536-b607d6fd4434` includes visible inter-onset gaps around
197–250 ms. Its final lower-pitch/upper-octave pair appears at 116.563 s and
116.574 s: an 11.6 ms difference, exactly one model frame. Timing labels make
that attack-synchronous harmonic behavior directly visible.

At the default 120 BPM, a beat is 500 ms, so the scale's roughly 200–250 ms
gaps map to eighth-note glyphs. This is useful expected behavior, not evidence
of inferred tempo or duration.

## Validation Result

```text
node --test tests/test_live_view.js
6 passed

uv run pytest
29 passed

uv run ruff check .
passed

node --check src/atpiano/web/live-view.js
node --check src/atpiano/web/app.js
passed

uv build
passed

git diff --check
passed
```

The deterministic browser tests cover anchored grouping, raw ordering,
strongest-score duplicate handling, settings normalization, prior-glyph rhythm
revision, the pending final mark, and the exact 11.609977 ms Basic Pitch frame
interval. Capture tests cover v2 preservation, rejected unsupported presets,
and v1 compatibility. The real page test verifies both controls and their
explanatory copy.

## Gaps And Next Direction

Preset rhythm is only a visual heuristic. Subjective review must determine
whether it makes runs and chord shapes easier to read or merely adds false
precision. Any future automatic tempo or notation work remains owned by
`performance-to-notation` and requires separate evidence.
