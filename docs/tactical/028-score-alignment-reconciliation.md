# 028 — Score Alignment Reconciliation

Topic: performance-to-notation

Status: **complete on 2026-07-26.**

## Motivation

The public 20:32 microphone session
`20260726T183203-d19b9f410710` reproducibly failed score publication with:

```text
score alignment positions are not monotonic
```

The retained two-minute source is complete. It contains 1,201 selected score
notes. The transformer retained 1,180 generated token positions and produced
one local score-time reversal around source rows 66–69.

The reversal exposed a deeper contract error. The first alignment adapter
treated a generated token index as the identity of the source note at the
same index. MIDI2ScoreTransformer is trained with independently padded
performance and score sequences, and generated padding positions do not
preserve that identity. After a dropped position, the shortcut can attach a
source event to a different rendered pitch. The reported artifact mapped only
539 of its 1,180 rendered output notes to a source row of the same pitch.
Weakening the monotonic guard would therefore publish a cursor known to be
incorrect.

## Bounded Correction

- Tag post-transformer notes with output-token identity only.
- After score post-processing and tie creation, collect one rendered attack
  per output token.
- Reconcile source attacks and score attacks in monotonic order using exact
  MIDI pitch and a longest-common-subsequence alignment.
- Record unmatched source notes and inserted score notes explicitly.
- Validate score monotonicity on the authoritative raw source-sample order.
- Require every mapped MusicXML segment to retain the mapped source pitch.
- Publish the corrected semantics as `atpiano.score-alignment.v2`; older v1
  artifacts continue to engrave but do not drive a cursor.

## Acceptance

- The retained 20:32 session publishes a score and alignment without changing
  its source events, MIDI, or MusicXML inference.
- Every mapped source row has the same MIDI pitch as all of its rendered
  segments.
- Mapped score attacks are monotonic after rows are ordered by source sample.
- Dropped transformer slots cannot shift later source identities.
- Focused Python and browser tests, the production build, and the migration
  regression pass.

## Execution Record

The adapter now tags generated notes only with their generated output index.
After music21 post-processing has created chords and tie fragments, it groups
those fragments back into rendered attacks. A dynamic-programming
longest-common-subsequence pass reconciles raw-sample-ordered source attacks
and score-time-ordered rendered attacks using exact MIDI pitch. Rank
displacement breaks repeated-pitch ambiguity without reducing the maximum
number of exact matches.

Server validation requires the v2 mapping descriptor, checks every rendered
segment pitch against its mapped source pitch, and checks score monotonicity
after ordering rows on the authoritative source sample clock. The browser
performs the same sample-clock ordering check. It rejects v1 for cursor use,
but alignment query failure remains isolated from MusicXML engraving.

### Reported-session evidence

The retained session started at 20:32 local time and contains 6,115,584 source
samples at 48 kHz (`127.408` seconds) and 1,201 selected committed notes. Its
first failed adapter result retained 1,180 generated output tokens and 1,202
rendered MusicXML note elements. Only 539 generated notes happened to have
the same pitch as the source row with the same token index, confirming that
the old identity shortcut was unsafe.

The corrected pinned-checkpoint rerun completed in 11.47 subprocess seconds.
It published 844 exact-pitch source mappings, 357 unmatched source notes, and
341 inserted rendered tie segments covering all 1,202 MusicXML note elements.
All 844 mapped rows agree with every rendered segment pitch and the source
timeline has zero score-position reversals. The automatic score contains 75
measures, two parts, and four voices.

After restarting `scripts/share-atpiano`, a score job submitted through
`https://atpiano.graehlarts.com` completed as
`job-score:b120da053dd049eb` with no error. A clean headless Chromium session
loaded that public URL, selected the 20:32 session, rendered its committed
score, exposed both engraving choices, and showed no alignment or score-job
failure.

### Automated evidence

`uv run atpiano migration-regression` passed with report
`results/migration-regression/20260726T185731Z/report.json`. It records 124
passing Python tests, 46 passing Vitest tests, five passing TypeScript node
tests, contract-generation parity, Ruff, npm audit with zero vulnerabilities,
and all legacy JavaScript checks. The production Vite build also passed with
only the existing OSMD chunk-size advisory.
