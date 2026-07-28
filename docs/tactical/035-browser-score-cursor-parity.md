# 035 — Browser Score Cursor Parity

Topic: performance-to-notation

Status: **implemented; live verification pending on 2026-07-28.**

## Motivation

The retained family session `20260727T185541-a2298f1afaaf` rendered its
selected 701,346-byte MusicXML score but showed:

```text
The score remains readable, but its playback cursor could not load.
```

The authenticated alignment metadata and 1,163,579-byte content response both
returned HTTP 200. Running the selected artifact through the browser parser
reproduced `Score alignment MIDI order is invalid`, while the server-side
artifact validation and MusicXML provenance remained valid.

The first rejected pair exposed a cross-language rounding mismatch. Source
sample `3,063,125` at 48 kHz is exactly MIDI tick `61,262.5` under the fixed
480-ticks-per-beat, 120-BPM export contract. Python `round` selects the even
tick `61,262`; JavaScript `Math.round` selected `61,263`. The following source
row rounded to `61,262`, so the browser alone saw a false reversal.

## Implementation

1. Reproduce the producer's positive rational, ties-to-even MIDI-tick
   conversion with exact `bigint` arithmetic in the browser parser.
2. Validate the complete transformer ordering key: tick, pitch, tick
   duration, exact onset sample, exact offset sample, and event identity.
3. Continue sorting accepted cursor rows onto the exact source-sample clock
   before validating score monotonicity or answering playback lookups.
4. Retain score engraving as an independent degraded path if a genuinely
   invalid or incompatible cursor artifact is encountered.

## Validation

- A focused browser regression uses the rejected live-session sample pair and
  proves it is accepted and normalized into exact source-sample order.
- All seven focused score-alignment tests and TypeScript checking pass.
- The complete selected retained artifact parses with 1,804 source rows and
  1,211 mapped cursor attacks.

## Review Boundary

This is a browser/producer contract correction. It does not alter retained
source events, regenerate a score, mutate an alignment artifact, or weaken
the v2 provenance, mapping, and monotonicity guards.
