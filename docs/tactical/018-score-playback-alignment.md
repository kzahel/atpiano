# 018 — Score Playback Alignment

Topic: performance-to-notation

Status: **complete.**

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

## Linux Tick-Collision Evidence

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

The `_verify_midi_order` guard was retained. This result became the input to
the post-completion correction and repeated real checkpoint evidence recorded
below.

## Deliberate Exclusions

- No live or progressive engraving.
- No claim that inferred meter, beat, tempo, or notation is musically final.
- No smooth interpolated cursor or recovered continuous tempo curve in the
  first slice.
- No public distribution or hosted operation of MIDI2ScoreTransformer.
- No Phase 4 application-core extraction.

## Execution Record

Commits `6f94387` and `808d05c` landed the bounded implementation. Each
successful score snapshot now freezes the ordered source-note document,
propagates stable source tokens through transformer detokenization and
music21 post-processing, assigns unique MusicXML note IDs, and publishes a
checksummed `atpiano.score-alignment.v1` artifact. Rows retain exact source
event IDs and samples, rational quarter-note positions, every rendered tie
segment, and explicit unmatched or inserted accounting.

The browser accepts alignment only when its session and full MusicXML hash
match the selected score artifact. Recorded-audio playback samples the media
clock on animation frames, updates the existing shared inspection sample, and
drives the keyboard, the source-linear piano-roll line, and OSMD's built-in
cursor. Score movement is deliberately discrete at mapped attacks. Opening
silence, a position beyond the score horizon, missing alignment, and invalid
alignment hide only the score cursor; engraving remains available.

### Transformer evidence

The pinned checkpoint was run against retained session
`20260726T113845-517f8d425847` at commit sample `1,804,288`
(`37.589333` seconds at 48 kHz). It selected 57 source notes and produced 66
pitched MusicXML elements because ties split some notes. All 57 source rows
mapped, all 66 rendered segments were identified, and the artifact reported
zero unmatched source notes and zero inserted score segments. Adapter
inference took `2.255318` seconds in the final isolated validation run.

The known pathological one-note probe produced 510 rendered notes. Alignment
did not disguise that expansion: it recorded one mapped source note and 509
inserted score segments, after which the existing plausibility gate rejected
the snapshot. This preserves useful diagnostic evidence without publishing a
misleading score.

### Browser evidence

The final build was served from the isolated workspace
`results/score-playback-alignment-validation` and exercised in headless
Chromium at 1440 and 1024 CSS pixels:

- leading silence at sample `96,000` showed the roll line and hid the score
  cursor;
- actual MP3 playback advanced the shared position from sample `156,000` to
  `209,760`, moved the roll line from about 8.6% to 11.6%, and changed the
  score cursor from hidden to visible as playback crossed the first mapped
  attack;
- forward seeks to samples `240,000`, `600,000`, `1,200,000`, and
  `1,680,000` advanced the cursor across the first and second score systems;
- a backward seek to `240,000` restored the earlier cursor position;
- resizing to 1024 CSS pixels retained the visible cursor with no horizontal
  page overflow; and
- the original pre-alignment snapshot rendered one score SVG with no cursor,
  warning, or browser console error.

### Automated evidence

`uv run atpiano migration-regression` passed at revision `808d05c`; its report
is
`results/migration-regression/20260726T132944Z/report.json`. The gate recorded
85 passing Python tests, 27 passing Vitest tests, five passing TypeScript node
tests, six legacy live-view tests, contract-generation parity, Ruff, npm audit
with zero vulnerabilities, and all legacy JavaScript syntax checks. The
production Vite build also passed; its only warning was the existing OSMD
chunk-size advisory.

### Post-completion tick-collision correction

Session `20260726T134843-17b0729ad6ca` exposed a real ordering edge after the
initial closeout. Source notes at samples `1,421,403` and `1,421,409` collapse
onto the same exported MIDI tick. The transformer orders that tick by pitch,
while the first source-note sidecar ordered it by the six-sample raw-onset
difference. The adapter rejected the mismatch before inference with
`score input-note order differs from MIDI`.

Commits `0650ce0`, `8ac8380`, and `9da53b2` corrected the contract and failure
presentation. Source identities now use the exporter's exact MIDI tick
conversion and the transformer's onset, pitch, and duration ordering. After
validation, the browser sorts rows back onto the authoritative raw-sample
timeline for lookup. A lost score-job poll also becomes an explicit failed
state instead of leaving the control indefinitely disabled.

The corrected exact session selected 86 notes, produced 87 pitched MusicXML
elements, mapped all 86 source rows, and reported zero unmatched notes and
zero inserted score segments. In Chromium at 1024 CSS pixels, seeking to
sample `1,200,000` displayed the score, placed the roll line at 43.5237%, and
showed the OSMD cursor with no render or console errors. The final
`uv run atpiano migration-regression` passed at revision `9da53b2`; its report
is `results/migration-regression/20260726T140248Z/report.json` and records 86
Python tests, 29 Vitest tests, five TypeScript node tests, contract parity,
Ruff, npm audit, and legacy JavaScript checks.

### Later v1 identity correction

The larger retained public session
`20260726T183203-d19b9f410710` disproved one premise of the v1 execution
record. Generated score token positions are not stable source-note identities
when the independently padded output sequence contains deletions. A v1 row
could therefore remain monotonic while naming a rendered note of another
pitch. The reported session made the defect visible as a score-time reversal,
but weakening that guard would not have fixed the underlying identity drift.

[`028-score-alignment-reconciliation.md`](028-score-alignment-reconciliation.md)
supersedes the v1 mapping semantics with an explicitly reconciled v2 artifact.
The v1 artifacts above remain historical evidence for the original cursor and
tick-order work, not the current source-to-score identity contract.

## Rollback

Alignment is an additive snapshot artifact and cursor rendering is
conditional on its presence. Reverting this series leaves existing MusicXML,
MIDI, playback, keyboard, and historical snapshot behavior intact.
