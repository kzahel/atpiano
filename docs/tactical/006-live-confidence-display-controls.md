# Live Confidence Display Controls

Topic: live-acoustic-transcription

Status: accepted on 2026-07-24.

## Motivation

Strict onset decoding makes the live stream useful enough that remaining
errors are narrower: a strong low-note strike can still produce a confident
upper-octave onset. The pianist needs to see the model's onset score at the
notehead to distinguish marginal candidates from confident model mistakes.

The current staff also hard-codes a 180 ms onset-grouping window. That can hide
recognition timing and turn a close melodic or harmonic error into an apparent
chord.

## Objective

Add local, reversible view controls for raw versus grouped onsets, grouping
distance, and onset-confidence labels. Do not alter model inference,
reconciliation, normalized events, or the untouched exact-final adapter.

## Included

- grouped and raw sequential staff modes;
- a configurable 0–250 ms grouping window;
- an 80 ms default suitable for ordinary chord strikes;
- a debug toggle that prints the live onset confidence beside each notehead;
- clear copy that confidence is a model score, not calibrated certainty;
- immediate rerendering while recording;
- browser-local preference persistence;
- capture metadata recording the selected display settings; and
- focused static-page, JavaScript syntax, and regression validation.

## Display Contract

Grouped mode anchors a group at its first onset and admits later onsets only
within the selected distance from that anchor. It does not chain adjacent
onsets into an indefinitely wide group. Duplicate pitches within one group
retain the strongest confidence.

Raw mode assigns one horizontal slot to every accepted onset identity,
including simultaneous pitches. It is intentionally diagnostic rather than
compact notation.

The confidence label uses the normalized live event's `confidence`. Under the
selected strict Basic Pitch policy this is the explicit onset-head peak. The
display must call it an onset score and must not imply calibrated probability.

## Excluded

- confidence-based suppression;
- color or opacity affecting event acceptance;
- harmonic-overtone classification;
- changing the keyboard highlight lifecycle;
- changing final/offline confidence semantics; and
- server-side preference or account storage.

## Validation

- controls and explanatory copy are served by the real workbench;
- grouped and raw aggregation logic has deterministic tests;
- settings survive a page reload through local browser storage;
- capture metadata retains the view settings used during the take;
- existing WebSocket, recognition, final-backfill, and artifact tests pass;
- JavaScript syntax, lint, package build, and whitespace checks pass; and
- the local workbench is restarted for subjective review.
