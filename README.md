# atpiano

Atpiano is an experimental acoustic-piano transcription service. It listens to
a nearby piano, turns the captured audio into timestamped note events, and
makes those events available to a piano roll or other consumers with useful
quality at real-ish latency.

The first goal is not to select a permanent model or build the final user
interface. It is to measure the latency/quality frontier of available
transcription models and the effects of windowing, overlap, look-ahead,
batching, post-processing, execution backend, and recording conditions.

## Project Boundary

Atpiano owns:

- timestamped audio capture or ingestion from a local microphone or a remote
  phone;
- acoustic-piano transcription;
- reconciliation of overlapping or revised model output; and
- a normalized, timestamped note-event stream.

A separate visualization and analysis program will consume those events. It
will also accept direct MIDI from an enabled keyboard, so harmonic, chord, and
piano-roll behavior does not depend on acoustic transcription.

The first implementation should be a deterministic live-replay benchmark. It
will replay aligned recordings at wall-clock cadence, exercise models as if
audio were arriving live, and report both transcription quality and
capture-to-event latency. Live Mac microphone and phone streaming are later
input adapters to the same pipeline.

## Project Status

The project is in discovery. Python and Spotify Basic Pitch are the first
prototype stack, not permanent selections. A deterministic MIDI-derived
fixture, untouched offline reference, wall-clock replay benchmark, and local
browser live-transcription workbench are runnable on Apple Silicon.

Current direction and research questions live in [`docs/topics/`](docs/topics/README.md).
Acoustic-model benchmarking, live browser transcription, and downstream
performance-to-notation conversion have separate owners there.

## Browser Workbench (v1 MVP)

The current workbench remains the runnable v1 MVP. The planned three-phase v2
is a separate live web application; it may reuse proven internals but does not
replace this command, its session artifacts, or its review path. See
[`docs/tactical/009-three-phase-unbounded-sessions.md`](docs/tactical/009-three-phase-unbounded-sessions.md).

Use the pinned Python 3.10 environment:

```text
uv sync
```

Then start the one local server:

```text
uv run atpiano workbench
```

The command opens a browser page. Grant microphone access and press **Start
live recognition**. The page warms the local Basic Pitch model, then asks for
one second of quiet room sound to calibrate an automatic onset-energy gate.
After the status changes to **Listening**, accepted pitches light a
physically proportioned 88-key keyboard and appear from left to right as
onset-first notes on a grand staff. Nearby onsets form one group using a
configurable window that defaults to 80 ms. Source-onset gaps are visible by
default, with absolute source time and raw-onset modes available for closer
diagnosis.

The staff uses a deliberately rough 120 BPM rhythm preset by default. When the
next onset arrives, it revises the preceding mark to the nearest sixteenth,
eighth, quarter, half, or whole glyph. Other fixed-tempo presets and neutral
quarter marks are selectable. These glyphs represent inter-onset spacing, not
detected key duration, tempo inference, meter, or a finished score.

Press **Stop** to flush and hash the exact captured PCM, save the session WAV
and live event history, and automatically run the untouched full-file Basic
Pitch adapter. The completed audio, MIDI, normalized events, native live
windows, noise-gate decisions, timing evidence, final reconciliation, run
report, piano roll, and experimental score appear in the same page. No second
Transcribe action is needed.

The score view shows its tempo, beat, meter, key, quantization, and hand-split
assumptions. Change them and press **Regenerate local score** to retain and
review another interpretation. Score rendering uses a pinned
OpenSheetMusicDisplay bundle from a CDN, so it needs internet access; the
MusicXML artifact remains downloadable if that bundle is unavailable.

The same page supports a consentful two-phase comparison with Ivory:

1. download and submit the original WAV to test Ivory's complete
   audio-to-score pipeline;
2. download and submit the atpiano prediction MIDI in a separate Ivory job to
   test its notation conversion with note detection held constant; and
3. import each unedited MusicXML result into its labeled workbench lane.

The workbench does not upload audio automatically or handle Ivory accounts,
payments, or credentials. Imported oracle scores remain under the ignored
local run directory. Ivory's free preview was observed to block MusicXML
download, so importing its result currently requires a paid plan.

The first target-piano review found the local Partitura score technically
valid but unreadable, while the Ivory preview was easy for the user to sight
read. Treat notation as a diagnostic experiment, not a current product
capability. The current workbench therefore emphasizes live pitch onsets and
broad chord shape rather than score notation.

The workbench binds only to `127.0.0.1` and stores generated artifacts under
the ignored `results/workbench` directory by default. Browser takes are
limited to two minutes and the server accepts at most 64 MiB per upload. A
recording has no aligned MIDI, so its quality metrics are explicitly unscored;
the piano roll is for listening and subjective inspection.

The two-minute limit is a prototype resource bound, not a Basic Pitch or audio
API limit. The browser and live processor retain session PCM, and the benchmark
preserves every overlapping native model window before copying it into the
final run. The two latest two-minute evidence jobs each occupy about 274 MiB,
including roughly 117 MiB of live native windows. Raise or remove the limit
only after choosing a longer-session retention and compaction policy.

Live recognition uses sample-indexed PCM16 blocks over a same-origin loopback
WebSocket. The first local target-recording replay measured 0.43-second median
and 1.65-second p95 source-onset-to-server-emission latency. Those are
prototype measurements, not a promise for every note or a substitute for
browser microphone review. Browser clock exchanges and paint acknowledgements
are retained so an actual page session can also report delivery latency.
Notation remains a separate artifact consumer and does not change the
acoustic model output.

## Benchmark Commands

The lower-level commands remain available for reproducible experiments.

Generate a deterministic MIDI-derived WAV and aligned reference:

```text
uv run atpiano fixture ../atpiano-artifacts/smoke-input
```

Run the untouched Basic Pitch file path:

```text
uv run atpiano offline \
  ../atpiano-artifacts/smoke-input/input.json \
  ../atpiano-artifacts/offline
```

Or replay the same samples at real wall-clock cadence:

```text
uv run atpiano replay \
  ../atpiano-artifacts/smoke-input/input.json \
  ../atpiano-artifacts/replay
```

Review a completed run in the local browser UI:

```text
uv run atpiano review ../atpiano-artifacts/replay
```

The native fixed-duration capture adapter is also retained for instrumentation
experiments:

```text
uv sync --extra capture
uv run atpiano record ../atpiano-artifacts/my-piano --seconds 30
```

Generated inputs, checkpoints, recordings, and run results do not belong in
Git. Each run records hashes, runtime/model versions, parameters, stage timing,
native outputs, normalized event revisions, scores, and a compact report.

## Project Map

- [`docs/topics/`](docs/topics/README.md) — focused, living decisions, evidence,
  gaps, and recommended direction
- [`docs/tactical/`](docs/tactical/README.md) — bounded implementation plans and
  execution records
- [`AGENTS.md`](AGENTS.md) — repository guidance for coding agents
- [`topics.md`](topics.md) — commit-series topic string log

## Working Principles

- Measure end-to-end latency from the audio sample clock to emitted note
  events; model inference time alone is not product latency.
- Preserve raw model output and timing evidence so post-processing can be
  compared without rerunning inference.
- Keep source timestamps separate from arrival and display timestamps.
- Treat recent acoustic events as revisable when a model needs future context.
- Compare against an offline/full-context quality ceiling before optimizing a
  streaming path.
- Keep model checkpoints, datasets, recordings, and generated benchmark
  artifacts outside Git.
