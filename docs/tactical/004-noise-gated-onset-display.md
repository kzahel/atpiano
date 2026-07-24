# Noise-Gated Onset Display

Topic: live-acoustic-transcription

Status: accepted from the first subjective live-piano review on 2026-07-24.

## Observation

The first microphone pass established that a played isolated note is detected,
but also exposed three failures in the evaluator:

- Basic Pitch emits notes from ordinary room noise before the piano is played;
- the equal-width 88-cell keyboard is not a piano layout: black keys consume
  horizontal space, white-key widths vary, and a highlight can cover only the
  artificial cell rather than the physical key; and
- the duration-oriented piano roll is visually noisy and unhelpful because
  live offsets are already known to be unstable.

The keyboard also used prediction orange for a recent provisional event while
the legend advertised provisional yellow. Orange had no honest legend entry.

## Objective

Make the live evaluator answer one narrower question well:

> Which pitches did the model hear, and which near-simultaneous pitches belong
> to the same onset group?

Suppress background-only candidates with an inspectable signal gate, render a
physically proportioned 88-key keyboard, and show accepted onsets as
duration-free quarter-note-like marks on a sequential grand staff.

This remains a diagnostic transcription view, not inferred notation. It must
not add tempo, meter, measures, rhythmic values, key signatures, hands, or
voice assignment.

## Gate Contract

- Use the first second after AudioWorklet capture begins as an explicit quiet
  room calibration period.
- Estimate the room floor as the median RMS of 50 ms calibration frames.
- Set the onset gate eight dB above that estimate, clamped to the range
  -48 through -34 dBFS.
- Reject all model candidates whose onset precedes the calibration boundary.
- For later candidates, measure RMS from 20 ms before through 120 ms after the
  source-sample onset and reject levels below the gate.
- Apply the gate before rolling reconciliation so rejected noise never gains a
  live event identity.
- Preserve every model-native probability window and record native, accepted,
  and rejected candidate counts plus the measured floor and threshold.
- Leave the exact full-file adapter untouched. Live-gated versus final
  disagreement remains visible after Stop.

The threshold is a first target-room policy, not a universal acoustic
classifier. A quiet-note miss or a noise burst that passes the gate is evidence
for adjustment or a model change, not something to hide.

## Onset Display Contract

- Lay out 52 equal-width white keys from A0 through C8.
- Overlay all 36 black keys at the correct boundary between adjacent white
  keys, at a consistent fraction of white-key width and height.
- Use one declared highlight color for any accepted recent onset; remove live
  lifecycle colors and their misleading legend.
- Keep a detected key lit briefly so it can be judged from playing position.
- Rebuild onset groups from the latest non-retracted event identities.
- Group onsets within 180 ms of the first onset in a group.
- Draw groups left to right on a grand staff and retain only the most recent
  groups that fit.
- Draw filled noteheads and stems with one visual duration. Use ledger lines
  and accidentals, but no barlines or playback head.
- Continue to retain revisions and offsets in artifacts even though this view
  deliberately ignores duration.

## Validation

- Unit-test room-floor calibration, pre-calibration rejection, background
  rejection, audible-onset acceptance, evidence counts, and manifest policy.
- Unit-test or statically expose the exact 52-white/36-black keyboard mapping
  and 180 ms grouping policy.
- Preserve WebSocket, capture, final-pass, and offline regression coverage.
- Run lint, all tests, JavaScript syntax checks, package build, and whitespace
  validation.
- Repeat the target-piano microphone pass after restart and record whether
  silence, soft notes, chords, and repeated notes behave acceptably.
