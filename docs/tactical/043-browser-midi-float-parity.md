# 043 — Browser MIDI Float Parity

Topic: performance-to-notation

Status: **complete and live on 2026-07-28.**

## Motivation

The retained family session `20260726T191133-04261c1ba54b` rendered its
refreshed 30-measure MusicXML score but showed:

```text
The score remains readable, but its playback cursor could not load.
```

The selected r2 alignment was valid according to the producer and server. Its
hash matched the artifact catalog, all 464 source rows were present, and the
MusicXML hash and source identity agreed. The browser parser nevertheless
reproduced `Score alignment MIDI order is invalid`.

## Root Cause

The first rejected source-order pair begins at rows 229 and 230:

- sample `1556530`, pitch 65; and
- sample `1556525`, pitch 77.

At 48 kHz the second onset is algebraically MIDI tick `31130.5`. The browser
used exact rational arithmetic and ties-to-even, producing tick `31130`.
Python's producer calls `mido.second2tick`, which first computes floating-point
seconds and seconds-per-tick. That intermediate lies just above the half-tick,
so Python produces tick `31131`. Both producer rows therefore share tick
`31131` and are ordered by pitch. The browser alone saw a false reversal.

The earlier Tactical 035 correction was directionally incomplete: matching
Python's rounding rule is insufficient when the producer rounds a
floating-point conversion rather than the algebraically exact ratio.

## Implementation

- Mirror `mido.second2tick`'s operation order in the browser: source seconds,
  floating-point seconds-per-tick, then division.
- Apply Python's ties-to-even rule to that resulting JavaScript number.
- Keep the complete transformer ordering key and source-sample normalization
  unchanged.
- Add the retained row pair as a focused regression while preserving the
  earlier exact-half-tick regression.

This is a consumer compatibility correction. It does not weaken alignment
validation, alter source evidence, regenerate MusicXML, or require a score
pipeline revision.

## Validation

- The focused score-alignment suite passes with eight tests.
- The complete refreshed 464-row target alignment parses with 332 mapped
  attacks.
- The prior 1,804-row half-tick regression alignment still parses with 1,211
  mapped attacks.
- All 94 frontend tests, six TypeScript node tests, TypeScript checking, and
  the production Vite build pass.
- The complete migration regression passes with 222 Python tests, 94 Vitest
  tests, six TypeScript node tests, generated-contract parity, zero high
  severity audit findings, Ruff, retained JavaScript syntax, and Git
  whitespace. Its report is
  `results/migration-regression/20260728T142755Z/report.json`.

## Live Evidence

The already-active authenticated share service restarted onto the rebuilt
application. The public session URL returned HTTP 200 and anonymous
capability access remained protected with HTTP 401.

Clean Chromium and WebKit sessions loaded the exact target with no score or
cursor advisory. Seeking recorded audio to source sample `51840` made OSMD
cursor element `cursorImg-0` visible in both browsers. The retained
`20260727T185541-a2298f1afaaf` regression score also loaded without a cursor
advisory. Temporary local-operator sessions were revoked after validation.

A subsequent complete retained-session sweep exercised all nine current
recordings in both Chromium and WebKit. All 18 checks returned the application
with HTTP 200, rendered inline SVG notation without a score or page error,
made `cursorImg-0` visible after seeking to each score's first mapped attack,
and rendered the complete score reader. Reader pagination ranged from one page
for the shortest score to 28 pages for the 104-measure score. There were no
engraving, alignment, cursor, or reader failures.
