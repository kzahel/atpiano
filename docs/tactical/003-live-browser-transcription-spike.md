# Live Browser Transcription Spike

Topic: live-acoustic-transcription

Status: completed and subjectively reviewed on 2026-07-24. The transport,
rolling adapter, and final backfill remain; the first duration-oriented live
evaluator was rejected and is superseded by tactical 004.

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

## Execution Record

The first end-to-end lane is implemented in the existing loopback workbench.
It deliberately selects one justified configuration before attempting the
larger sweep:

```text
transport schema: atpiano.live-stream.v1
session schema: atpiano.live-session.v1
audio payload: mono little-endian PCM16
binary header: 48 bytes
model: stock Spotify Basic Pitch 0.4.0 Core ML package
model input: 43,844 samples at 22,050 Hz (1.988390 s)
schedule hop: 0.250 s
left guard: 0.116100 s
right guard: 0.232200 s
commit horizon: 1.000 s
final match: same pitch and onset within 80 ms
```

The page opens a same-origin WebSocket and waits for the model to warm before
connecting its AudioWorklet. Every block carries its sequence, first source
sample, frame count, rate, page send time, and worklet time. The server rejects
gaps, duplicates, reordering, sample-rate changes, invalid lengths, and
oversized sessions instead of repairing them. It retains exact PCM, per-block
receipt evidence, clock observations, and browser-paint acknowledgements.
Page-side queue growth above 4 MiB is an explicit transport failure.

Rolling inference uses high-quality deterministic resampling and a cached,
unmodified Basic Pitch model. Each native probability window is preserved as
NPZ with source coordinates and timing. The reconciler gives a stable identity
to same-pitch estimates across overlapping windows, emits material revisions,
commits tracks after one second, and retracts unmatched provisional tracks
after 750 ms.

The live evaluator shows:

- recent onset pitch names grouped over a declared 180 ms diagnostic window;
- an 88-key highlight;
- a ten-second scrolling piano roll;
- provisional open tails distinct from committed notes;
- source head, window count, first-visible timing, and transport state; and
- live-versus-final additions, removals, matches, and timing changes.

Stop validates the acknowledged block and frame totals, writes the exact
session WAV and manifests, and automatically queues the existing untouched
full-file adapter. Live history is copied into that immutable run and matched
against the final notes. The original review, notation, and oracle paths remain
available after completion.

### Deterministic and target-hardware evidence

Protocol tests cover exact PCM round trips, continuity rejection, clock and
paint persistence, stable revision identities, and the complete WebSocket to
final-run path. A direct 34.688-second target-take processing check completed
132 windows in 2.009 seconds after a 0.372-second model load, so the M4 Pro
comfortably keeps up with the selected 250 ms hop.

The same target take was then sent through the real workbench WebSocket at
wall-clock cadence. It produced run
`20260724T130652-50255becb667` under the ignored `results/workbench` tree:

```text
audio duration: 34.688 s
wall-clock stream elapsed: 34.670 s
maximum sender schedule lateness: 0.045 s
rolling windows: 132
live tracks: 159
live committed tracks: 140
live retractions: 18
exact-final notes: 133
live/final onset matches: 127
final additions: 6
live removals: 13

source onset to first server emission:
  p50 0.428 s
  p95 1.649 s
  max 1.876 s

matched live-to-final onset change:
  p50 0.006 s
  p95 0.034 s
  max 0.061 s

matched live-to-final offset change:
  p50 0.013 s
  p95 0.866 s
  max 2.105 s
```

This replay did not execute in a browser, so it has no browser clock-fit or
paint latency. The artifacts state that explicitly instead of treating server
emission as display time. An actual page session records those observations.

The result supports the onset-first interaction: most exact-final notes had a
nearby live onset, while offsets were much less stable. It does not show that
all notes arrive within one second, nor does exact-final output serve as
acoustic ground truth.

### Commands and validation

```text
uv run ruff check .
uv run pytest -q
node --check src/atpiano/web/app.js
node --check src/atpiano/web/capture-processor.js
git diff --check
```

All lint checks passed and all 22 tests passed. JavaScript syntax and whitespace
checks passed. The real-model wall-clock replay above additionally exercised
the selected Core ML model, raw-window preservation, event streaming, capture
persistence, background final adapter, notation generation, and
reconciliation on the target hardware.

### Remaining decision evidence

The implementation is ready for the user's subjective microphone pass, which
must cover isolated notes, intervals, block and rolled chords, repeated notes,
low bass, high treble, dense harmony, sustain, and silence. That pass decides
whether the live lane is already useful.

The original sweep, aligned real-piano deadline scoring, CPU/memory telemetry,
page-throttling tests, input-device changes, reconnect semantics, and an
intentional slower-than-real-time policy are not yet implemented. They should
be selected from observed failures rather than expanded pre-emptively. If
onset feedback is not satisfying, preserve this transport and event boundary
and open a separate causal or pedal-aware model bakeoff.

### Subjective decision

The user confirmed that a played isolated note was detected, validating the
basic live path, but rejected this tactical's evaluator:

- notes appeared from room noise before the piano was played;
- the duration roll was not useful because note tails were unreliable;
- the 88 equal-cell strip was not a physical piano keyboard; and
- keyboard orange disagreed with the provisional-yellow legend.

The accepted correction is recorded in
[`004-noise-gated-onset-display.md`](004-noise-gated-onset-display.md). It
retains this tactical's transport, clocks, raw windows, revisions, and final
backfill while adding an explicit signal gate and replacing duration graphics
with a physical keyboard and grouped grand-staff onsets.
