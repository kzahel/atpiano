# Live Browser Transcription Spike

Topic: live-acoustic-transcription

Status: accepted on 2026-07-24. Implementation has not started.

## Objective

Determine whether the current browser capture and rolling Basic Pitch adapter
can provide useful live onset, pitch, and broad chord-shape feedback while
preserving the quality of the existing full-recording path after Stop.

This is a bounded architecture and latency experiment. It does not select a
permanent model or build a production streaming service.

The first user-facing decision is not whether note offsets or score notation
are correct. It is whether the pianist can tell, while the performance remains
in short-term memory, that the intended single notes, intervals, and broad
chord shapes were recognized.

## Hypothesis

On the current Apple host, model computation is fast enough that an
approximately one-second provisional lane is plausible. A sample-indexed
browser transport plus rolling windows can show recent onsets without waiting
for definitive offsets, and the exact stock full-file adapter can later
reconcile the session to the same result the user already judged useful.

The experiment should reject this hypothesis if transport gaps, unstable
window edges, excessive revisions, CPU queueing, or unacceptable quality at
the one-second deadline are observed.

## Included

- a versioned binary PCM block envelope;
- loopback WebSocket transport from the existing AudioWorklet;
- source-sample continuity, host clock mapping, and browser-paint timing;
- bounded host buffering and explicit gap/backpressure behavior;
- deterministic WAV replay through the browser transport before microphone
  use;
- the existing rolling Basic Pitch adapter behind the current model contract;
- a small hop, edge-guard, and commit-horizon sweep;
- normalized provisional, revised, committed, and retracted events;
- a minimal live debug piano roll, keyboard highlight, and recent pitch-set
  view;
- lossless session-WAV persistence and raw per-window model output;
- the exact existing full-file adapter after Stop;
- stable final-pass reconciliation and an inspectable revision history; and
- quality-at-deadline plus stage-by-stage latency reports.

## Excluded

- a new neural model or model conversion;
- phone, LAN, public, or multi-user serving;
- HTTPS and authentication;
- compressed audio transport;
- production UI polish;
- sheet-music generation or harmonic analysis;
- training or fine-tuning;
- hiding final-pass disagreement; and
- claiming Basic Pitch is causal or permanently selected.

## Phase A: Transport Without A Model

Define a binary message with at least:

- schema version and message kind;
- session identity;
- monotonically increasing block sequence;
- first source sample and frame count;
- source sample rate and channel count;
- worklet clock observation; and
- little-endian PCM payload.

Replay a known WAV through the same page-side block sender used for live
capture. Reassemble it on the server and require:

- exact frame count and SHA-256 after agreed PCM serialization;
- no silent repair of gaps, duplicates, or out-of-order blocks;
- bounded queue high-water marks;
- explicit behavior when the sender is slower or faster than real time;
- a final acknowledged flush; and
- a fitted browser-to-host clock mapping with residuals.

Do not connect a model until this phase is deterministic.

## Phase B: Rolling Preview

Feed the host ring buffer to the existing rolling Basic Pitch adapter. Keep
the experiment matrix intentionally small, for example:

- hop: 100, 250, 500, and 1,000 ms;
- the current edge guards plus at most two justified alternatives; and
- commit horizons centered on 1 and 2 seconds.

The exact values may change after inspecting the adapter's frame coordinates,
but every value must be in the run manifest. Retain native probabilities per
window and source-sample coordinates.

Run the matrix first on:

1. the aligned deterministic fixture;
2. a checksummed aligned real-piano diagnostic subset;
3. the existing target-piano recording; and
4. focused silence, repeated-note, chord, bass, treble, and pedal clips.

Use deterministic replay for metrics. A live microphone pass is subjective
confirmation, not the measurement source.

The preview contract is onset-first:

- emit a visible provisional note as soon as its onset is available;
- let an open-ended or fading tail state that the offset is not known;
- revise onset, velocity, confidence, and offset without replacing a stable
  identity unnecessarily;
- close, retract, or commit the note only with explicit event evidence; and
- group recent onsets into a declared diagnostic pitch set without claiming a
  chord name.

The grouping window must be recorded and tested on block chords, rolled
chords, repeated notes, and fast melodic motion. It must not silently turn
every run into one chord.

## Phase C: Exact Final Backfill

On Stop:

1. finish and hash the lossless session WAV;
2. run the untouched full-file Basic Pitch adapter with its ordinary
   parameters;
3. match rolling identities to final notes by pitch and timing;
4. preserve additions, removals, timing changes, and attribute changes; and
5. let the UI switch between “as seen live” and “best final”.

The final MIDI and note JSON must be byte-equivalent to running the same
offline adapter directly on the saved session WAV, excluding run identity and
timing metadata. If equivalence is impossible, document the exact reason and
compare normalized note content.

## Phase D: Minimal Debug UI

Extend only enough UI to judge the experiment:

- horizontally scrolling piano roll;
- distinct provisional and committed styling;
- a visible live/playback head;
- 88-key pitch highlights and a recent-onset pitch-name cluster;
- open or fading provisional tails so long or unknown offsets do not dominate;
- queue, gap, and connection status;
- a Stop transition into final reconciliation; and
- a concise before/after revision summary.

The transcription service should still emit normalized events. The debug
page consumes them; it must not become the only event boundary.

## Measurements

For every run record:

- capture callback and page batching delay;
- browser send queue and transport delay;
- host receive and resampling delay;
- future-context, scheduler, and inference delay;
- reconciliation, delivery, and browser-paint delay;
- onset-to-first-provisional and onset-to-commit p50, p95, and max;
- onset precision/recall/F1 visible at 250 ms, 1 second, and 3 seconds;
- final note, offset, frame, and velocity metrics where references exist;
- revision, retraction, duplicate, and stuck-note rates;
- final-pass additions, removals, and time changes;
- CPU, memory, and queue high-water marks; and
- cold/warm runtime state.

Report algorithmic look-ahead and scheduling wait even if inference is fast.
Do not infer musical time from packet arrival or completion timestamps.

## Failure And Recovery Cases

Exercise:

- permission denial and input-device change;
- one missing, duplicate, and out-of-order block;
- page throttling or delayed main-thread handling;
- browser reload or socket close during capture;
- inference temporarily slower than real time;
- Stop during a model window;
- empty input and long silence;
- rejected oversized session; and
- browser cancellation of an artifact response.

Ordinary client disconnects during response writes already stop without a
traceback. Retain that case as a regression test.

## Decision Gates

After deterministic transport:

- continue only if source continuity and clock evidence are trustworthy.

After rolling preview:

- keep Basic Pitch as the first preview lane if feedback is subjectively
  useful, the pianist can judge intended notes and broad chord shape, and
  quality/revision cost at one second is acceptable;
- otherwise use the evidence to set a concrete target for a causal model
  bakeoff rather than tuning indefinitely.

After final backfill:

- continue toward a user-facing live workbench only if the final result
  reproduces the existing full-file path and revisions are understandable.

No new model should enter this tactical. If needed, open a separate adapter
bakeoff for the streaming onset/offset/pedal model, causal research baseline,
and any verified Mobile-AMT release.

## Validation

- transport protocol and clock-mapping unit tests;
- deterministic replay integration tests, including gaps and backpressure;
- replay/offline parity tests;
- event lifecycle and stable-identity tests;
- browser JavaScript syntax and interaction tests;
- existing offline/replay/workbench regression suite;
- repeated cold and warm timing trials;
- target-piano subjective review covering single notes, intervals, triads,
  rolled chords, repeated notes, bass, treble, and dense harmony;
- `git diff --check`, lint, tests, and package build; and
- exact commands, artifacts, failures, and recommendation added here before
  marking the tactical complete.
