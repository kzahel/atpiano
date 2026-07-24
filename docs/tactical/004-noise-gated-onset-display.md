# Noise-Gated Onset Display

Topic: live-acoustic-transcription

Status: implemented on 2026-07-24; second subjective live-piano review remains.

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

## Execution Record

The live processor now calibrates the declared gate directly from the retained
source PCM. Gate decisions happen before rolling reconciliation, while every
unmodified Basic Pitch probability window remains available. The recognition
manifest records the policy and aggregate counts, each window timing row
records native/accepted/rejected counts, and `gate.jsonl` records pitch, onset,
measured dBFS, threshold, decision, and reason for every native candidate.

The browser shows **Calibrating** and asks the pianist to remain quiet for one
second. After the server has enough source samples, it displays the measured
room floor and threshold and changes to **Listening**. The gate affects only
the provisional live lane; Stop still runs the untouched full-file adapter so
disagreement is inspectable.

The duration canvas and lifecycle legend are removed. The replacement:

- builds exactly 52 equal white keys and overlays 36 black keys at their
  physical boundaries;
- lights the complete accepted key for 1.8 seconds with one color;
- does not relight a key merely because its event commits later;
- removes a still-lit onset if that identity retracts;
- rebuilds 180 ms onset groups from latest non-retracted identities; and
- draws the groups sequentially as filled noteheads and stems on a grand
  staff, with accidentals and ledger lines but no rhythmic semantics.

The two microphone sessions underlying the feedback were retained as failed
jobs `20260724T134000-5e1c8bd9c117` and
`20260724T134321-64e32730188c`. Their old client reached the two-minute limit
with one AudioWorklet block in flight, causing the server to reject the block
instead of finalizing. The browser now initiates Stop as soon as a complete
block reaches the limit, and the server permits that one bounded in-flight
block.

### Gate evidence from the reported room

The failed jobs still preserved their exact PCM and 473 native rolling windows
each. Re-decoding those already-preserved windows and applying the new gate
without rerunning inference produced:

| Job | Room floor | Gate | Native window candidates | Accepted | Rejected |
|---|---:|---:|---:|---:|---:|
| `20260724T134000-5e1c8bd9c117` | -55.71 dBFS | -47.71 dBFS | 1,902 | 1,646 | 256 |
| `20260724T134321-64e32730188c` | -61.85 dBFS | -48.00 dBFS | 1,164 | 917 | 247 |

These are overlapping-window candidate decisions, not unique note counts.
The gate rejects 13.5% and 21.2% respectively, including repeated quiet
background candidates before or between playing. It cannot show how many
rejections were musically correct because the sessions have no aligned MIDI.

As a quiet-note safety check, the earlier 34.688-second target take calibrated
to -60.72 dBFS and the -48 dBFS threshold accepted all 1,282 native rolling
candidates. Its exact-final note attacks ranged down to -40.57 dBFS in the
declared onset window. This does not guarantee every future soft note, but it
shows the first threshold separates that take's observed attacks from its
room floor.

### Validation

```text
uv run ruff check .
uv run pytest -q
node --check src/atpiano/web/app.js
node --check src/atpiano/web/capture-processor.js
git diff --check
uv build
```

All lint and syntax checks passed and all 23 tests passed. Tests cover gate
calibration, pre-calibration suppression, below-threshold rejection,
audible-onset acceptance, decision artifacts, transport exposure, and existing
capture/final-pass behavior. The built wheel contains the live processor and
all revised web assets. The second subjective microphone pass remains the
decision check.
