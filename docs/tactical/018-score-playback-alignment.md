# 018 — Score Playback Alignment

Topic: performance-to-notation

Status: **active. A real x86_64 Linux checkpoint run on 2026-07-26 exposed a
pre-inference ordering mismatch when distinct source attacks quantize to the
same MIDI tick. The alignment guard correctly blocked publication; the input
ordering contract must be corrected before further real snapshot evidence.**

## Motivation

Recorded-audio playback already drives one exact source-sample inspection
position and the detected-key view follows it. The piano roll does not draw
that position, and the committed MusicXML score has no cursor. Adding the roll
line is direct source-timeline presentation. The score requires a durable
bridge between performed source time and inferred musical score time.

The current committed snapshot writes source-timed MIDI and then runs
MIDI2ScoreTransformer. Its MusicXML contains measures, divisions, voices,
rests, and quantized durations, but the published snapshot retains only the
global commit sample. MIDI note identity and source-to-score correspondence
are lost before the browser renders the result.

## Outcome

Publish a versioned score-alignment artifact with every successful committed
snapshot. It maps selected source-event identities and source samples to the
transformer's musical positions and rendered MusicXML note identities. The
shared inspection sample then drives:

- the recorded-audio transport;
- the exact detected-key view;
- a source-sample piano-roll playhead; and
- OpenSheetMusicDisplay's score cursor.

The first score cursor advances at mapped musical attacks. It does not claim
continuous tempo reconstruction between attacks.

## Invariants

- The audio sample clock remains the authoritative playback timeline.
- Score alignment is generated from the exact selected source events and
  exact MusicXML bytes in one snapshot job.
- MusicXML and alignment from different snapshot generations are never mixed.
- Quantization may move a score position but never overwrites source timing.
- Chord members may share a score position.
- One source note may map to multiple rendered MusicXML elements after ties.
- Insertions, deletions, ambiguities, and unmatched notes remain explicit.
- Old score snapshots without alignment still render without a cursor.
- Pathological transformer output remains rejected before publication.
- No cursor is inferred by stretching the complete recording uniformly over
  the score or by inspecting SVG coordinates.

## Implementation Slices

### 1. Alignment feasibility and adapter evidence

- Freeze source-note identity and ordering beside snapshot MIDI.
- Retain the transformer's position-aligned output evidence before music21
  engraving and post-processing obscure token correspondence.
- Reconcile post-processed score notes, chords, and tie fragments with source
  identities.
- Validate the screenshot session, the golden musical fixture, and the known
  pathological score case before selecting the durable representation.

### 2. Artifact and contract

- Add a versioned, checksummed alignment JSON artifact beside snapshot MIDI
  and MusicXML.
- Record source event ID, source onset and offset samples, score position,
  rendered note IDs, mapping status, and snapshot provenance.
- Publish MusicXML, input MIDI, alignment, and the snapshot manifest
  atomically.
- Expose the alignment artifact through the shared runtime contract without
  weakening explicit workspace and session addressing.

### 3. Synchronized rendering

- Retain the OSMD instance and enable its built-in cursor.
- Translate the shared inspection sample to the latest mapped score attack.
- Support forward playback, backward seeking, pause, score reflow, and score
  refresh.
- Hide the score cursor before mapped coverage and beyond the snapshot
  horizon.
- Draw the same inspection position as a vertical piano-roll playhead.
- Sample the media element clock frequently enough that dense score attacks
  are not silently skipped by sparse `timeupdate` delivery.

### 4. Hardening and evidence

- Unit-test alignment, ties, chords, repeated pitches, rests, unmatched notes,
  and monotonic lookup.
- Component-test score and roll cursor behavior, old artifacts, session
  switching, snapshot refresh, and forward/backward seeking.
- Run the real pinned checkpoint against representative retained sessions.
- Run the full migration regression and record exact structural, browser, and
  subjective evidence here.

## Acceptance

- Every selected source note is mapped or explicitly accounted for as
  unmatched.
- Every published mapped row names the exact source event and score position.
- Alignment positions remain monotonic in source-onset order.
- Chords, ties, repeated pitches, leading silence, and internal rests do not
  produce misleading cursor jumps.
- Playback and manual seeking update keyboard, roll, and score from the same
  inspection sample.
- Old snapshots and missing alignment fail soft without breaking engraving.
- The known real score snapshot follows audible attacks in manual review.
- Focused tests, TypeScript checks, application build, Python checks, and the
  migration regression pass.

## Current Real-Runtime Evidence

The pinned Python 3.11 runtime, upstream commit, and 389,829,880-byte
checkpoint installed successfully on x86_64 Linux. A complete 42-second
shared-workbench session supplied 151 closed committed notes at a full
2,016,000-sample horizon. Snapshot creation wrote `source-notes.json` and
`committed.mid`, then the adapter rejected them before model inference:

```text
ValueError: score input-note order differs from MIDI
```

The first mismatch is deterministic and cross-platform. Exact source attacks
at samples 47,497 and 47,507 are ordered as pitches 64 then 60. Both round to
the same MIDI tick; the pinned transformer's `midi_to_list` then orders that
attack as pitches 60 then 64. `score_input_notes_document` currently sorts by
exact onset sample, pitch, duration, and event ID, so it does not always
fulfill its stated “transformer's MIDI-note order” contract. Linux exposed
the first retained collision, but there is no evidence that operating-system
iteration order or model nondeterminism caused it; the same input conversion
has the same ordering conflict on macOS.

Do not remove or relax `_verify_midi_order`. Correct the source-note ordering
to account for the exact MIDI tick conversion while retaining the original
sample coordinates and event IDs. Add focused coverage for attacks that
collide only after tick rounding, then repeat the real checkpoint run before
continuing to browser cursor evidence.

## Deliberate Exclusions

- No live or progressive engraving.
- No claim that inferred meter, beat, tempo, or notation is musically final.
- No smooth interpolated cursor or recovered continuous tempo curve in the
  first slice.
- No public distribution or hosted operation of MIDI2ScoreTransformer.
- No Phase 4 application-core extraction.

## Rollback

Alignment is an additive snapshot artifact and cursor rendering is
conditional on its presence. Reverting this series leaves existing MusicXML,
MIDI, playback, keyboard, and historical snapshot behavior intact.
