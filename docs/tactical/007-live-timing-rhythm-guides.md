# Live Timing And Rhythm Guides

Topic: live-acoustic-transcription

Status: planned on 2026-07-24.

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

## Gaps

Preset rhythm is only a visual heuristic. Subjective review must determine
whether it makes runs and chord shapes easier to read or merely adds false
precision. Any future automatic tempo or notation work remains owned by
`performance-to-notation` and requires separate evidence.
