# Live Confidence Display Controls

Topic: live-acoustic-transcription

Status: complete on 2026-07-24.

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

## Implemented Result

The live panel now exposes three local display controls:

- **Staff display:** `Group nearby onsets` or `Raw onset sequence`;
- **Chord window:** 0–250 ms in 10 ms steps, defaulting to 80 ms; and
- **Show onset scores:** optional two-decimal labels next to every notehead.

Raw mode allocates one horizontal staff position per accepted event identity,
even for simultaneous pitches. Grouped mode remains anchored at the first
onset; it does not chain nearby events into a growing group. If the same pitch
appears twice inside one group, the display retains the event with the
stronger onset score.

The controls rerender existing live events immediately and persist through
browser-local storage. The range control is visibly disabled in raw mode.
Enabling onset scores reveals explanatory copy that the 0–1 values are Basic
Pitch model scores rather than calibrated probabilities.

The selected settings are versioned as
`atpiano.live-display-settings.v1`. Initial settings travel with the live
start metadata, and final settings travel with Stop and are retained in
`browser-capture.json`. They do not affect model input, decoder thresholds,
gate decisions, reconciliation, normalized events, or final transcription.

## Evidence

The user's first strict-onset subjective run is workbench job
`20260724T144840-82ee228fd1bf`. The strict 0.6 rolling decoder completed 473
windows over almost two minutes with 154 committed identities and two
retractions. The user judged it to work “pretty great,” while identifying a
narrower remaining error: a lower E strike can also trigger the octave above
on the resonant target piano.

That result motivates visible confidence evidence. A high onset score on the
upper E would indicate a confident model error rather than a marginal decoder
threshold crossing; a low score would support a later measured confidence or
harmonic-verifier experiment. The display itself makes no suppression
decision.

## Validation Result

```text
node --test tests/test_live_view.js
4 passed

uv run pytest
28 passed

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

The real workbench page test verifies that the new script and all three
controls are served. Focused capture tests verify that the final settings
override is retained in browser capture metadata.

## Gaps And Next Direction

Confidence labels diagnose but cannot establish whether an upper-octave event
is a physical strike or a lower-note harmonic. Use the labels during the next
low-note review and retain representative score pairs. If the false upper
octaves occupy a separable score range, test that hypothesis against real
octave dyads before changing acceptance. If they are confidently wrong, use
the controlled harmonic-evidence or piano-specific model experiment instead
of merely raising the global onset threshold.
