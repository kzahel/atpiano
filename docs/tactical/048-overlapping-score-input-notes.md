# 048 — Overlapping Score Input Notes

Topic: performance-to-notation

Status: **complete and live on 2026-07-30.**

## Motivation

Public session `20260730T175918-aa11aa63cb5a` failed automatic score
generation. Its visible error was itself a Pydantic validation failure because
the score-job exception exceeded the public error contract's 500-character
limit. The final line inside that secondary error was:

```text
ValueError: score input-note order differs from MIDI
```

The retained score input contained 151 notes. Source note 111, pitch 46, ran
from sample 2,849,542 to 2,976,217. It overlapped an earlier pitch-46 note that
ran from sample 2,685,315 to 2,878,440. Both were written on MIDI channel 0.
Standard MIDI note-off events identify channel and pitch, not a source-note
identity, so PrettyMIDI closed both active pitch-46 notes at the earlier
note-off. The transformer's parsed second note therefore ended at sample
2,878,440 instead of 2,976,217 and correctly rejected it against the frozen
source-note artifact.

## Implemented Contract

The normalized MIDI exporter now assigns overlapping instances of the same
pitch to separate melodic channels. Non-overlapping notes remain on channel 0;
channel 9 remains excluded because it is the General MIDI percussion channel.
Controller intervals are broadcast to every melodic channel used by the
export so downloadable MIDI retains pedal behavior. More than 15 simultaneous
instances of one pitch fail explicitly instead of producing ambiguous MIDI.

This preserves every authoritative source onset and offset. It does not trim
the earlier note, rewrite the source-note artifact, relax the transformer's
input check, or infer note time from model completion.

Score-pipeline revision r4 records the changed producer semantics. Existing
scores remain readable as older-compatible snapshots.

Subprocess failures now report the adapter's concise final cause. The
application layer independently bounds every structured error message to 500
characters while preserving its beginning and final cause, so an unexpected
long exception cannot make failed-job polling violate its own contract.

## Validation

- A focused PrettyMIDI regression round-trips the exact two retained pitch-46
  intervals on channels 0 and 1.
- All 151 retained source notes pass the pinned transformer's real
  `midi_to_list` reader and strict input verifier.
- An isolated full r4 inference generated 60,164-byte MusicXML in 4.02 seconds,
  mapping 124 source notes and retaining 27 explicit unmatched notes.
- The focused Python suites passed 35 tests.
- The complete migration regression passed with 254 Python tests, 12
  TypeScript Node tests, 105 frontend tests, generated-contract parity,
  TypeScript, npm audit, Ruff, JavaScript syntax, and Git whitespace. Its
  report is
  `results/migration-regression/20260730T181059Z/report.json`.
- The production Vite build passed.

The retained public session was regenerated through r4 with the same 151-note
input and the shared service restarted. A passwordless operator check through
the public origin read the 60,164-byte selected MusicXML and a 1,024-byte MP3
range, reported the expected delayed correction profile, and verified operator
session revocation. The public session URL returned HTTP 200 and anonymous
capabilities remained protected with HTTP 401.

The deployed Chromium validation rendered this exact session as inline SVG,
showed cursor positions at the opening, middle, and final mapped attacks, and
rendered all three reader pages without a failure, console error, or page
exception. The broader run passed all 13 sessions that have scores; its sole
inventory failure was the unrelated zero-note Pixel 9 diagnostic capture,
which has no score snapshot. The report is
`results/score-validation/20260730-overlap-fix.json`.
